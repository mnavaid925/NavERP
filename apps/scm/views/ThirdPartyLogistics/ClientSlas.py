"""SCM 4.17 Third-Party Logistics (3PL) — ``ClientSLA``: the service-level register and its recompute.

Full CRUD (list / create / detail / edit / delete) plus the two measurement verbs:
:func:`clientsla_recompute` (one promise) and :func:`clientsla_recompute_all` (this workspace's active
promises). **This module measures nothing itself** — every figure comes from
``ClientSLA.recompute()``, which walks the as-built rows for the metric; the views fetch, filter,
lock, audit and render.

FOLDER-NAME NOTE (do not "fix" it): the backend package is ``ThirdPartyLogistics/`` while the
templates live under ``templates/scm/3pl/``. That asymmetry is the house rule — all sixteen shipped
scm template folders use a short slug while the Python package uses the NavERP.md sub-module title in
PascalCase. ``CustomerPortal/PortalAccounts.py`` carries the same note.

--------------------------------------------------------------------------------------------------
THREE THINGS EVERY PAGE HERE HAS TO GET RIGHT
--------------------------------------------------------------------------------------------------

**1. ``None`` is not zero, and the templates are told so by name.** ``last_measured_value`` is NULL
until something has actually been measured, and the list must render that as **"Not measured"** —
never as 0 and never as a blank cell. On a ``lower_is_better`` metric a 0 reads as *perfect*, so the
lie points in the most flattering possible direction. The same rule governs ``variance``,
``credit_basis_run`` and ``metric_meta.default_target``; each is named in the context contract below
with its ``None`` meaning.

**2. Both recompute verbs are POST-only and take the row lock.** ``recompute()`` increments
``breach_count`` on a transition into ``breached``, so two concurrent POSTs (a double-click, a retry)
would each read the pre-increment value and both add one. The row is taken ``FOR UPDATE`` and the
``is_active`` precheck is evaluated INSIDE the lock — a guard that runs outside it answers about the
state the request started in (the 4.13 TOCTOU finding). The audit row is written inside the same
transaction, so a failure between commit and logging cannot leave a measurement with no trail.

**3. The sweep is one transaction PER ROW, not one for the sweep.** A single transaction over every
active SLA would hold every row lock for the duration and roll back the good measurements along with
the one that failed. Per-row atomicity means a sweep is resumable by simply pressing the button
again, which is the same posture 4.15's detector takes.

--------------------------------------------------------------------------------------------------
WHY AN INACTIVE SLA CANNOT BE RECOMPUTED
--------------------------------------------------------------------------------------------------
``is_active=False`` is a promise that is not in force. ``recompute()`` writes evidence columns and can
increment ``breach_count``, so running it against a paused SLA would record a breach of something
nobody currently owes — and that count is what the client detail page and ``open_sla_breaches()``
report. Both verbs refuse it: the sweep by filtering ``is_active=True``, the single-row verb with a
message. ``can_recompute`` in the detail context mirrors that refusal exactly, because **hiding a
button does not stop a direct POST** and offering a one-click failure is worse than not offering it.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant

from apps.scm.forms import ClientSLAForm
from apps.scm.models import (
    ClientBillingRun,
    ClientSLA,
    LogisticsClient,
    SLA_METRIC_CHOICES,
    SLA_STATUS_CHOICES,
)


#: Ceiling on how many SLAs one sweep measures. Every row costs a handful of queries against the
#: shipment / order / count / ledger tables, so an unbounded sweep is a request anybody can start from
#: a button and nobody can stop. The message SAYS when the cap bit — a capped sweep that reported
#: nothing would look like a sweep that found nothing (the 4.15 detector's ruling).
MAX_SWEEP_ROWS = 200

#: The billing-run statuses whose total is a real fee figure. A draft or calculated run is a working
#: document and a void one is a retraction; sizing a service credit off either would put a number in
#: front of a client that nobody has signed off.
_BILLED_RUN_STATUSES = ("approved", "invoiced")

#: Printed under the list table wherever a measured value is absent. There is deliberately NO
#: matching `CREDIT_NOTE`: the detail page's credit panel writes the same caveat four different ways
#: — one per branch of "not breaching / breached with no billed period / breached" plus the closing
#: "applied to nothing" paragraph — and a single constant cannot be branch-aware. A second, weaker
#: copy passed into the context and never printed was two sources of the same prose free to drift,
#: which is exactly what happened here.

NOT_MEASURED_NOTE = (
    "A promise that has never been measured shows as No Data, not as zero. The two are different "
    "statements: zero on a damage-rate target would read as flawless, and zero on an on-time target "
    "would read as total failure, when in both cases the honest answer is that nothing has been "
    "counted yet. Press Recompute to measure the current window."
)


def _client_qs(tenant):
    """This workspace's 3PL clients, for the ``?client=`` dropdown.

    ``.none()`` for a tenant-less caller rather than a filter on NULL, so a superuser
    (``tenant=None``) gets an empty dropdown instead of a filter that silently matches every
    workspace's rows — the ``_item_qs`` / ``_location_qs`` idiom from ``views/_helpers.py``, verbatim.

    Declared HERE rather than promoted to ``views/_helpers.py``: the three sibling 4.17 view modules
    are written independently in the same working tree, and a shared helper two agents each believe
    they own is how one of them gets deleted. Backend Package Structure rule 5 puts a helper wanted by
    a second SUB-MODULE in ``_helpers.py``; that consolidation is a follow-up, and this is the note
    for whoever does it.

    ``select_related("party")`` because ``LogisticsClient.__str__`` is ``"{code} · {party}"`` and every
    ``<option>`` renders it — without the join that is one query per option.
    """
    if tenant is None:
        return LogisticsClient.objects.none()
    return LogisticsClient.objects.filter(tenant=tenant).select_related("party").order_by("code", "id")


def _credit_basis(sla):
    """``(run, fees)`` — the last BILLED period for this client, and its total.

    ``(None, 0)`` when the client has never had a run approved or invoiced, and the detail page must
    SAY so rather than printing a credit of 0.00 as though the breach were worth nothing: "we have not
    billed this client yet" and "this breach earns no credit" are different sentences, and only one of
    them is true.

    Ordered ``-period_end, -id`` — the same ordering ``ClientBillingRun.Meta`` declares and the same
    one ``LogisticsClient.last_billing_run()`` uses, so the client page and this page can never name
    different runs as "the last one".
    """
    run = (ClientBillingRun.objects
           .filter(tenant_id=sla.tenant_id, client_id=sla.client_id,
                   status__in=_BILLED_RUN_STATUSES)
           .order_by("-period_end", "-id").first())
    return run, (run.total if run is not None else Decimal("0"))


def _recompute_message(request, sla, result):
    """Turn one ``recompute()`` result into a sentence somebody can act on.

    ``no_data`` gets an INFO message carrying the resolver's own reason, not a success — reporting
    "measured" for a window with no evidence in it is precisely the conflation the whole sub-module is
    built to avoid.
    """
    if result["status"] == "no_data":
        messages.info(request, f"{sla.number} could not be measured — {result['summary']}")
        return
    label = sla.get_status_display()
    text = (f"{sla.number} measured {sla.last_measured_value} against a target of "
            f"{sla.target_value} — {label}. {result['summary']}.")
    if result["status"] == "breached":
        messages.warning(request, text)
    else:
        messages.success(request, text)


def _audit_recompute(user, sla, result):
    """The audit row every measurement writes. Called INSIDE the caller's transaction.

    ``value`` is stringified because ``AuditLog.changes`` is JSON and a ``Decimal`` is not
    JSON-serialisable — a measurement that raised ``TypeError`` while being recorded would roll back
    the measurement itself.
    """
    write_audit_log(user, sla, "update", {
        "action": "recompute",
        "status": result["status"],
        "value": None if result["value"] is None else str(sla.last_measured_value),
        "sample_size": result["sample_size"],
        "window": f"{result['window'][0]} .. {result['window'][1]}",
    })


# =================================================================================================
# The register
# =================================================================================================
@login_required
def clientsla_list(request):
    """Every service promise in the workspace, with what the ledger last said about it.

    **Filter GET params** (every one applied BEFORE pagination, by ``crud_list``):

    * ``q`` — free text over ``number`` / ``name`` / ``client__code`` / ``client__party__name``
    * ``client`` — a pk, through ``crud_list``'s ``as_db_int`` guard (L11: ``?client=abc``,
      ``?client=²`` and a 21-digit value all SKIP the filter rather than raising out of ``.filter()``).
      Compare it in the template with ``|stringformat:"d"`` — **never** ``|slugify``.
    * ``metric`` — a ``SLA_METRIC_CHOICES`` value (plain string compare)
    * ``status`` — a ``SLA_STATUS_CHOICES`` value (plain string compare)
    * ``active`` — the literal strings ``"True"`` / ``"False"``, which ``crud_list`` maps to real
      booleans; a junk value is caught inside ``crud_list`` and the filter is skipped.

    **Context**, exhaustively:

    * ``object_list`` / ``page_obj`` / ``q`` — from ``crud_list``. Guard prev/next with
      ``has_previous`` / ``has_next`` (L9).
    * ``clients`` — the ``LogisticsClient`` queryset behind the ``?client=`` dropdown.
    * ``metric_choices`` — ``SLA_METRIC_CHOICES``.
    * ``sla_status_choices`` — ``SLA_STATUS_CHOICES``. **This exact name, not ``status_choices``**, so
      it cannot be confused with a rate-card or billing-run status list on a shared partial.
    * ``stats`` — a dict with EXACTLY ``total`` / ``meeting`` / ``at_risk`` / ``breached`` /
      ``no_data`` (ints). Workspace-wide and deliberately NOT recomputed per filter: "4 breached" is a
      fact somebody has to act on, and a number that changed as you browsed would be useless.
    * ``not_measured_note`` (str) — print it beside the table's empty/unmeasured state.

    **Per row**, safe to read without a query: ``obj.number``, ``obj.client.code``, ``obj.name``,
    ``obj.get_metric_display``, ``obj.target_value``, ``obj.unit`` / ``obj.get_unit_display``,
    ``obj.last_measured_value`` (**``None`` renders as "Not measured"**), ``obj.last_measured_at``,
    ``obj.status`` / ``obj.get_status_display`` / ``obj.status_css`` (badge-green / -amber / -red /
    -muted — colour-named only, L33), ``obj.breach_count`` and ``obj.is_active``.

    ``select_related("client__party")`` covers both the ``client.code`` every row prints and a
    ``{{ obj.client }}`` anywhere on the page (``LogisticsClient.__str__`` walks its party) — one join
    for the page instead of one query per row.

    The Recompute-all button is a POST form to ``scm:clientsla_recompute_all`` with
    ``{% csrf_token %}`` in the list header.
    """
    tenant = request.tenant
    qs = ClientSLA.objects.filter(tenant=tenant).select_related("client__party")

    stats = ClientSLA.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        meeting=Count("id", filter=Q(status="meeting")),
        at_risk=Count("id", filter=Q(status="at_risk")),
        breached=Count("id", filter=Q(status="breached")),
        no_data=Count("id", filter=Q(status="no_data")))

    return crud_list(
        request, qs, "scm/3pl/clientsla/list.html",
        search_fields=("number", "name", "client__code", "client__party__name"),
        filters=(
            ("client", "client_id", True),
            ("metric", "metric", False),
            ("status", "status", False),
            ("active", "is_active", False),
        ),
        extra_context={
            "clients": _client_qs(tenant),
            "metric_choices": SLA_METRIC_CHOICES,
            "sla_status_choices": SLA_STATUS_CHOICES,
            "stats": {key: value or 0 for key, value in stats.items()},
            "not_measured_note": NOT_MEASURED_NOTE,
        })


# =================================================================================================
# CRUD
# =================================================================================================
@login_required
def clientsla_create(request):
    """Record a service promise. ``crud_create`` stamps the tenant, audits and refuses a tenant-less
    user; ``_need_tenant`` refuses first so the message names this page rather than the dashboard.

    ``ClientSLAForm`` ALSO stamps the tenant onto the unsaved instance (through ``TenantUniqueMixin``)
    and that is not redundancy: ``crud_create`` assigns ``obj.tenant`` only AFTER ``is_valid()``, so
    without the form-side stamp the tenant-dependent legs of ``ClientSLA.clean()`` — the cross-tenant
    client guard, the cross-client location guard and the NULL-scope duplicate check — would all
    validate an instance whose ``tenant_id`` is ``None``, which is the exact case each of them skips.
    They would be dead code on the create path, and the create path is the one a crafted POST takes.

    Context: ``form``, ``is_edit`` (``False``).
    """
    if _need_tenant(request):
        return redirect("scm:clientsla_list")
    return crud_create(request, form_class=ClientSLAForm,
                       template="scm/3pl/clientsla/form.html",
                       success_url="scm:clientsla_list")


@login_required
def clientsla_edit(request, pk):
    """Change the promise; the evidence is untouched.

    Editable at any measured status, deliberately: a target genuinely gets renegotiated, an at-risk
    band gets widened and a credit percentage gets agreed after the fact, and none of those is a
    derived figure. Nothing an edit can reach is a measurement — all eight evidence columns are
    ``editable=False`` and are not on the form — so an edit cannot restate what was measured.

    An edit CAN change the target, the direction or the window, and the stored ``status`` then refers
    to the OLD rule until somebody recomputes. That is why the detail page prints the measured window
    beside the figure rather than only the figure, and why Recompute sits next to the Edit button.

    Context: ``form``, ``obj``, ``is_edit`` (``True``).
    """
    return crud_edit(request, model=ClientSLA, pk=pk, form_class=ClientSLAForm,
                     template="scm/3pl/clientsla/form.html",
                     success_url="scm:clientsla_list")


@login_required
@require_POST
def clientsla_delete(request, pk):
    """Delete a promise. POST-only — a GET is a 405, never a silent state change.

    Nothing in the application references a ``ClientSLA``, so there is no ``ProtectedError`` to catch
    and no child to count: the row simply goes, and with it the breach history nothing else holds a
    copy of. The message says so and steers to deactivating instead, which is exactly what
    ``is_active`` exists for — a paused promise stops being swept and keeps every window it was
    measured over.

    ``transaction.atomic()`` around ``crud_delete`` so the audit row it writes BEFORE deleting rolls
    back with a delete that then fails.
    """
    obj = get_object_or_404(ClientSLA.objects.select_related("client"), pk=pk, tenant=request.tenant)
    # Counted BEFORE the delete, while the row still exists to be counted.
    breaches = obj.breach_count or 0

    with transaction.atomic():
        response = crud_delete(request, model=ClientSLA, pk=pk,
                               success_url="scm:clientsla_list")

    if breaches:
        messages.info(request, f"{breaches} recorded breach window(s) went with it. To retire a "
                               "promise without losing that history, clear its Active box instead — "
                               "an inactive SLA is skipped by the sweep and keeps everything it has "
                               "measured.")
    return response


@login_required
def clientsla_detail(request, pk):
    """One promise: what was agreed, what the ledger says, and what a breach would suggest.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.ClientSLA`, with ``client__party`` and ``scope_location``
      joined. Safe to ask for ``status_css`` / ``metric_meta`` / ``is_measured`` / ``is_breaching`` /
      ``variance`` — none of them queries.
    * ``metric_meta`` — a dict with EXACTLY ``label``, ``unit``, ``direction``, ``default_target`` and
      ``source``. **``source`` MUST be rendered.** It is the plain-English statement of which
      as-built rows the figure was measured from, and it is the first thing a client asks about a
      number they are being held to. ``default_target`` may be ``None`` for a metric with no registry
      entry — render an em dash.
    * ``status_css`` (str) — a colour-named theme.css badge class (green / amber / red / muted). There
      is no ``badge-success`` / ``badge-danger``; those render UNSTYLED (L33).
    * ``is_measured`` (bool) — ``False`` means ``last_measured_value`` is NULL. Print "Not measured",
      **never 0**, and print ``not_measured_note`` beside it.
    * ``variance`` (Decimal or **``None``**) — signed ``measured − target``. ``None`` when nothing has
      been measured. It is NOT re-signed for a ``lower_is_better`` metric; render it beside the
      direction so a reader can check it against the two numbers either side.
    * ``is_breaching`` (bool).
    * ``window_label`` (str) — the human window, e.g. ``"01 Jul 2026 – 31 Jul 2026 (last full calendar
      month)"``. On a never-measured SLA it describes the window a recompute WOULD use and says
      "not yet measured".
    * ``suggested_credit`` (Decimal) — ``0`` unless the SLA is currently breached.
    * ``credit_basis`` (Decimal) — the fee figure the percentage was applied to.
    * ``credit_basis_run`` (``ClientBillingRun`` or **``None``**) — where that figure came from.
      **``None`` means there is no billed month to base a credit on, and the page must say so**
      rather than printing 0.00 as though the breach were worth nothing.
    * ``credit_pct`` / ``credit_cap_pct`` (Decimals) — a cap of 0 means NO cap; say that, do not print
      "capped at 0%".
    * ``can_recompute`` (bool) — ``False`` on an inactive SLA, mirroring exactly what
      :func:`clientsla_recompute` refuses. Gate the button on it.
    No prose constant is passed. The credit panel is labelled **SUGGESTED — NOT APPLIED** and the
    unmeasured branch explains that no-data is not a zero, but both are written in the TEMPLATE and
    per branch, because the wording differs by state in a way one constant cannot carry. Nothing on
    this page may imply a credit note was raised.

    QUERIES: one for the SLA (both FKs joined) and one for the last billed run. Nothing per-row.
    """
    obj = get_object_or_404(
        ClientSLA.objects.select_related("client__party", "scope_location"),
        pk=pk, tenant=request.tenant)

    # A metric with no registry entry still has to render five keys, or `metric_meta.source` is a
    # silently blank region on the one page whose job is to say where the number came from.
    meta = dict(obj.metric_meta) or {
        "label": obj.get_metric_display(),
        "unit": obj.unit,
        "direction": obj.direction,
        "default_target": None,
        "source": ("This metric has no entry in the closed registry, so there is no statement of "
                   "which records it is measured from — and nothing measures it."),
    }

    run, fees = _credit_basis(obj)

    return render(request, "scm/3pl/clientsla/detail.html", {
        "obj": obj,
        "metric_meta": meta,
        "status_css": obj.status_css,
        "is_measured": obj.is_measured,
        "variance": obj.variance,
        "is_breaching": obj.is_breaching,
        "window_label": obj.window_label(),
        "suggested_credit": obj.suggested_service_credit(fees),
        "credit_basis": fees,
        "credit_basis_run": run,
        "credit_pct": obj.service_credit_pct,
        "credit_cap_pct": obj.service_credit_cap_pct,
        "can_recompute": obj.is_active,
    })


# =================================================================================================
# The measurement — a BUTTON, never a GET, and never a cron this project does not have
# =================================================================================================
@login_required
@require_POST
def clientsla_recompute(request, pk):
    """Measure ONE promise over its window and write back the evidence.

    POST-only (a GET is a 405) and the row is taken ``FOR UPDATE``, because ``recompute()`` increments
    ``breach_count``: two concurrent POSTs would each read the pre-increment value and both add one.
    The ``is_active`` precheck runs INSIDE the lock — outside it, it answers about the state the
    request started in and the write lands the moment the competing transaction commits (the 4.13
    TOCTOU finding).

    The object is resolved BEFORE the status guard so a cross-tenant pk answers 404 rather than a 302
    that leaks "there is a row there, you just cannot touch it" (the 4.12 finding).

    Its own ``write_audit_log`` — this verb bypasses ``crud_edit``, so nothing else would record it —
    written INSIDE the transaction, so a failure between the commit and the log cannot leave a
    measurement with no trail.
    """
    with transaction.atomic():
        obj = get_object_or_404(ClientSLA.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_active:
            messages.error(
                request,
                f"{obj.number} is not active, so it is not being measured. An inactive SLA is a "
                "promise that is not in force — recording a breach against it would count something "
                "nobody currently owes. Tick Active on the edit form first.")
            return redirect("scm:clientsla_detail", pk=pk)

        result = obj.recompute()
        _audit_recompute(request.user, obj, result)

    _recompute_message(request, obj, result)
    return redirect("scm:clientsla_detail", pk=pk)


@login_required
@require_POST
def clientsla_recompute_all(request):
    """Measure every ACTIVE promise in this workspace, and report what the sweep actually found.

    Bounded to :data:`MAX_SWEEP_ROWS`, and the message SAYS when the cap bit — a capped sweep that
    reported nothing would look like a sweep that found nothing.

    **One transaction per row, not one for the sweep.** A single transaction would hold every row lock
    for the whole pass and roll back the good measurements along with one bad row; per-row atomicity
    makes the sweep resumable by pressing the button again. Each row is re-fetched ``FOR UPDATE`` and
    its ``is_active`` flag re-read inside its own lock, so a promise deactivated while the sweep was
    running is skipped rather than measured on stale state.

    ``measured`` and ``no_data`` are reported SEPARATELY and never added up: how many promises could
    not be measured at all is the more actionable of the two numbers, because it usually means an
    integration or a configuration gap rather than a service failure.
    """
    if _need_tenant(request):
        return redirect("scm:clientsla_list")

    pending = list(ClientSLA.objects
                   .filter(tenant=request.tenant, is_active=True)
                   .order_by("client__code", "metric", "id")
                   .values_list("pk", flat=True)[:MAX_SWEEP_ROWS + 1])
    truncated = len(pending) > MAX_SWEEP_ROWS
    del pending[MAX_SWEEP_ROWS:]

    if not pending:
        messages.info(request, "There are no active SLAs in this workspace to measure. An inactive "
                               "promise is skipped by the sweep on purpose.")
        return redirect("scm:clientsla_list")

    measured = no_data = breached = skipped = 0
    for sla_pk in pending:
        with transaction.atomic():
            obj = (ClientSLA.objects.select_for_update()
                   .filter(pk=sla_pk, tenant=request.tenant).first())
            # Deactivated (or deleted) between building the list and reaching it — re-read under the
            # lock rather than trusted from the snapshot the sweep started from.
            if obj is None or not obj.is_active:
                skipped += 1
                continue
            result = obj.recompute()
            _audit_recompute(request.user, obj, result)

        if result["status"] == "no_data":
            no_data += 1
        else:
            measured += 1
            if result["status"] == "breached":
                breached += 1

    messages.success(request, f"Recompute complete — {measured} measured, {no_data} returned no data.")
    if breached:
        messages.warning(request, f"{breached} of the promises measured are breaching their target.")
    if no_data:
        messages.info(request, f"{no_data} promise(s) could not be measured at all — open each one to "
                               "read why. No Data means there was nothing in the window to count, not "
                               "that the target was missed.")
    if skipped:
        messages.info(request, f"{skipped} promise(s) were deactivated while the sweep was running "
                               "and were skipped.")
    if truncated:
        messages.info(request, f"The sweep measures at most {MAX_SWEEP_ROWS} promises in one pass and "
                               "this workspace has more. Run it again, or recompute the remaining "
                               "ones from their own pages.")
    return redirect("scm:clientsla_list")
