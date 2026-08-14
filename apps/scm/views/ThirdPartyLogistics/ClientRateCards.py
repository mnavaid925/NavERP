"""SCM 4.17 Third-Party Logistics (3PL) — ``ClientRateCard`` views: the tariff and its rate lines.

**The parent detail page IS the line list.** ``ClientRateCardLine`` has no standalone list page, no
filter bar and no detail page: a rate line is only meaningful beside the other lines of its own
tariff, and a register of every priced charge in the workspace would be a table nobody can read. The
three line routes (add / edit / delete) all return to the card's detail page.

**Nothing here posts a StockMove and nothing here writes to the ledger** (L29). A rate card holds
prices; the money is ``ClientBillingRun``'s, and even that stops at a DRAFT ``accounting.Invoice``.

--------------------------------------------------------------------------------------------------
WHY THE STATUS GUARDS ARE IN THE VIEWS AND NOT ONLY IN THE TEMPLATE
--------------------------------------------------------------------------------------------------
``ClientRateCard.is_editable`` is declared ONCE on the model and read by four places that must not
disagree: :func:`clientratecard_edit`, all three line-write views, and the ``can_edit`` /
``can_add_line`` flags handed to the template. Hiding a button does not stop a direct POST, and a
button whose route refuses it is the 4.10 "two of three shapes" finding. One definition, five
readers.

The two ladder verbs take the row ``FOR UPDATE`` inside ``transaction.atomic()`` and re-read its
status INSIDE the lock. Two concurrent POSTs (a double-click, a retry, a replay) would otherwise
both see ``draft`` and both activate — and on this model the second activation is the one that could
land a second live tariff over the same dates.

--------------------------------------------------------------------------------------------------
CONTEXT-VAR CONTRACT (pinned, L7 — the templates are written by a separate agent)
--------------------------------------------------------------------------------------------------
``scm/3pl/clientratecard/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from ``crud_list``),
plus ``clients`` (queryset for the ``?client=`` dropdown — compare an option with
``{{ c.pk|stringformat:"d" }}``, **never** ``|slugify``), ``status_choices`` (pairs, compared as a
plain string against ``request.GET.status``) and ``stats`` (keys ``total`` / ``draft`` / ``active``
/ ``superseded`` / ``expired``, counted over the WHOLE workspace like every other stats header in
this app). Per row: ``obj.number``, ``obj.name``, ``obj.version``, ``obj.client.code``,
``obj.effective_from``, ``obj.effective_to`` (**``None`` means open-ended — render "Open-ended", not
a blank cell**), ``obj.status`` / ``obj.get_status_display`` / ``obj.status_css``, and
``obj.line_count`` (ANNOTATED on the queryset — do NOT call ``obj.active_line_count`` per row, that
is one COUNT per card).

``scm/3pl/clientratecard/detail.html`` — ``obj``, ``lines``, ``line_count``, ``active_line_count``,
``manual_only_bases``, ``billing_runs``, ``billing_run_count``, ``panel_limit``,
``is_effective_today``, and the five gates ``can_edit`` / ``can_add_line`` / ``can_activate`` /
``can_supersede`` / ``can_delete``. Gate the Delete button on ``can_delete`` — that is exactly the
condition :func:`clientratecard_delete` enforces, and offering a one-click failure is worse than not
offering it. A line is chipped "needs a manual quantity when billed" with
``{% if line.charge_basis in manual_only_bases %}``.

``scm/3pl/clientratecard/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path).

``scm/3pl/clientratecardline/form.html`` — ``form``, ``is_edit``, ``rate_card`` (the PARENT object;
it drives the page title, the breadcrumb and the cancel link back to ``scm:clientratecard_detail``)
and ``obj`` **only** on the edit path.

Badge classes are COLOUR-NAMED (``obj.status_css`` / ``line.category_css``). ``badge-success`` /
``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css and render unstyled (L33).
"""
from django.db.models import ProtectedError
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
# `_changed` is PRIVATE, so the star import skips it — it has to be named. It builds the
# `{field: new_value}` diff (with the sensitive-field redaction list applied) that `crud_edit`
# records automatically; the hand-rolled line-edit path below bypasses that helper and would
# otherwise silently lose the diff.
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant

from apps.scm.forms import ClientRateCardForm, ClientRateCardLineForm
from apps.scm.models import ClientRateCard, ClientRateCardLine, LogisticsClient
# BY NAME, never `import *` — the 4.17 vocabulary module is owned by the `LogisticsClients` entity
# file (``views/ContractCompliance/Reports.py:65`` imports a sub-module ``_choices`` the same way).
# Imported from the MODULE rather than through ``apps.scm.models``'s re-export block so this file
# does not depend on which of those constants the package __init__ happens to name.
from apps.scm.models.ThirdPartyLogistics._choices import (
    MANUAL_ONLY_BASES,
    MAX_RATE_CARD_LINES,
    RATE_CARD_STATUS_CHOICES,
)


#: How many rows the detail page's billing-run panel shows. The cap is a queryset SLICE, so the
#: DATABASE applies it — it bounds what is FETCHED, not what is rendered (L40 §1: a guard that first
#: builds the whole thing is the payload, not a guard).
MAX_PANEL_ROWS = 25


def _client_qs(tenant):
    """This workspace's 3PL clients, ready for a ``<select>``.

    ``LogisticsClient.__str__`` walks ``party``, so the ``select_related`` is what keeps a dropdown
    of N clients from firing N extra queries (§7.6). Returns ``.none()`` for a tenant-less user
    rather than a filter on NULL.

    Local to this module on purpose *for now*: the three 4.17 entity view modules were built in
    parallel and none of them may reach into another's file. Promote it to
    ``views/ThirdPartyLogistics/LogisticsClients.py`` (this sub-package's root entity, the
    ``_monitor_qs`` precedent) in a consolidation pass — not to ``views/_helpers.py``, which is for
    helpers crossing SUB-MODULES.
    """
    if tenant is None:
        return LogisticsClient.objects.none()
    return LogisticsClient.objects.filter(tenant=tenant).select_related("party")


def _detail(pk):
    """The one redirect every refusal and every verb in this module lands on."""
    return redirect("scm:clientratecard_detail", pk=pk)


def _refuse_locked(request, card, what):
    """Flash the standard "this tariff is frozen" refusal and answer True, or answer False.

    ONE sentence, read by the edit view and all three line-write views, so a member cannot learn
    four different reasons for the same rule.
    """
    if card.is_editable:
        return False
    messages.error(
        request,
        f"{card.number} is {card.get_status_display().lower()} and can no longer be changed — "
        f"{what} on a tariff that has priced a bill would restate what a client was already "
        "charged. Create the next version instead.")
    return True


# =================================================================================================
# The register
# =================================================================================================
@login_required
def clientratecard_list(request):
    """Every tariff in the workspace, newest effective date first.

    Filter GET params, **all applied BEFORE pagination** (a filter applied afterwards pages over the
    unfiltered set and quietly shows the wrong rows on page 2): ``q`` over number / name / client
    code / client party name; ``?client=`` through ``crud_list``'s ``is_int`` leg, so
    ``?client=abc``, ``?client=²`` and ``?client=999999999999999999999`` all SKIP the filter rather
    than raising out of ``.filter()`` (L11); ``?status=`` as a plain string.

    ``line_count`` is annotated with ``distinct=True`` because the ``q`` search joins through
    ``client__party``: a many-to-one join cannot fan the count out today, but the ``distinct`` costs
    nothing and makes the figure correct by construction rather than by the join shape staying the
    way it is.

    ``stats`` is counted over the WHOLE workspace in ONE aggregate, not over the filtered page —
    a header chip that changed every time somebody typed in the search box would be measuring the
    search, not the business.
    """
    # The `order_by` is EXPLICIT and it is not redundant with `Meta.ordering`. The `annotate()`
    # below puts a GROUP BY on the query, and `QuerySet.ordered` reports False for a grouped query
    # that carries no explicit ordering of its own — so `Paginator` raised
    # `UnorderedObjectListWarning` and, worse than the warning, page 2 was free to repeat or skip
    # rows page 1 had already shown. It repeats `Meta.ordering` exactly, so the list stays "newest
    # effective date first" and the two never disagree.
    qs = (ClientRateCard.objects.filter(tenant=request.tenant)
          .select_related("client", "client__party", "currency")
          .annotate(line_count=Count("lines", distinct=True))
          .order_by("-effective_from", "-version", "-id"))

    stats = ClientRateCard.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        draft=Count("id", filter=Q(status="draft")),
        active=Count("id", filter=Q(status="active")),
        superseded=Count("id", filter=Q(status="superseded")),
        expired=Count("id", filter=Q(status="expired")),
    )

    return crud_list(
        request, qs, "scm/3pl/clientratecard/list.html",
        search_fields=["number", "name", "client__code", "client__party__name"],
        filters=[("client", "client_id", True), ("status", "status", False)],
        extra_context={
            "clients": _client_qs(request.tenant),
            "status_choices": RATE_CARD_STATUS_CHOICES,
            "stats": stats,
        },
    )


@login_required
def clientratecard_create(request):
    """Draft a new tariff. Lands on the list; the lines are added from the card's detail page."""
    if _need_tenant(request):
        return redirect("scm:clientratecard_list")
    return crud_create(request, form_class=ClientRateCardForm,
                       template="scm/3pl/clientratecard/form.html",
                       success_url="scm:clientratecard_list")


@login_required
def clientratecard_detail(request, pk):
    """The tariff, its priced lines, and what has been billed against it.

    ``lines`` is materialised ONCE and everything derived from it — ``line_count``,
    ``active_line_count`` — is counted in Python off that list rather than with a second and third
    query. ``active_line_count`` deliberately does NOT call the model property here for the same
    reason.

    The billing-run panel is a SLICE at :data:`MAX_PANEL_ROWS`; ``billing_run_count`` is the honest
    total, so the page can say it is showing a window.
    """
    obj = get_object_or_404(
        ClientRateCard.objects.select_related("client", "client__party", "currency"),
        pk=pk, tenant=request.tenant)

    lines = list(obj.lines.select_related(
        "applies_to_location", "applies_to_item_category", "gl_account"))
    billing_runs = list(obj.billing_runs.select_related("client")
                        .order_by("-period_end", "-id")[:MAX_PANEL_ROWS])
    billing_run_count = obj.billing_runs.count()

    return render(request, "scm/3pl/clientratecard/detail.html", {
        "obj": obj,
        "lines": lines,
        "line_count": len(lines),
        "active_line_count": sum(1 for line in lines if line.is_active),
        # The tuple itself, so the page can chip a line with
        # `{% if line.charge_basis in manual_only_bases %}` rather than repeating the list in HTML.
        "manual_only_bases": MANUAL_ONLY_BASES,
        "billing_runs": billing_runs,
        "billing_run_count": billing_run_count,
        "panel_limit": MAX_PANEL_ROWS,
        "is_effective_today": obj.is_effective_on(timezone.localdate()),
        "can_edit": obj.is_editable,
        "can_add_line": obj.is_editable and len(lines) < MAX_RATE_CARD_LINES,
        "can_activate": obj.status == "draft",
        "can_supersede": obj.status == "active",
        # Mirrors `clientratecard_delete` EXACTLY — a tariff that has priced a bill is PROTECTed.
        "can_delete": billing_run_count == 0,
    })


@login_required
def clientratecard_edit(request, pk):
    """Edit the header. **Refused once the card has left ``draft``.**

    ``EDITABLE_RATE_CARD_STATUSES`` is ``("draft",)``: an active tariff is what a bill was computed
    from, so rewriting its dates or its client would restate a charge that has already gone out.
    The refusal is a message plus a redirect to the detail page, not a 403 — the row is legitimately
    visible, it simply cannot be rewritten. Supersede it and draft the next version instead.

    ``status`` IS on the form, so this is also the ordinary draft -> active path; the overlap guard
    in ``ClientRateCard.clean()`` holds on that write exactly as it does on the audited verb.

    ``success_url`` is a RESOLVED path rather than a route name because ``crud_edit`` hands it
    straight to ``redirect()``, which cannot supply the ``pk`` a detail route needs.
    """
    obj = get_object_or_404(ClientRateCard.objects.select_related("client"),
                            pk=pk, tenant=request.tenant)
    if _refuse_locked(request, obj, "editing the header"):
        return _detail(pk)

    return crud_edit(request, model=ClientRateCard, pk=pk, form_class=ClientRateCardForm,
                     template="scm/3pl/clientratecard/form.html",
                     success_url=reverse("scm:clientratecard_detail", args=[pk]))


@login_required
@require_POST
def clientratecard_delete(request, pk):
    """Delete a tariff — refused once anything has been billed against it.

    ``ClientBillingRun.rate_card`` is PROTECT, so the pre-count is checked FIRST for an actionable
    message, and the ``ProtectedError`` is caught anyway: the count and the delete are two separate
    statements, and a concurrent run created in the gap would otherwise turn an ordinary click into
    a 500. Belt AND braces, because only one of the two can give a useful sentence.
    """
    obj = get_object_or_404(ClientRateCard.objects.select_related("client"),
                            pk=pk, tenant=request.tenant)

    billed = obj.billing_runs.count()
    if billed:
        messages.error(
            request,
            f"{obj.number} has priced {billed} billing run(s) and can't be deleted — the tariff is "
            "the evidence of what those clients were charged. Supersede it instead, which retires "
            "it without destroying the record.")
        return _detail(pk)

    try:
        with transaction.atomic():
            return crud_delete(request, model=ClientRateCard, pk=pk,
                               success_url="scm:clientratecard_list")
    except ProtectedError:
        messages.error(
            request,
            f"{obj.number} was billed against while this page was open, so it can no longer be "
            "deleted. Supersede it instead.")
        return _detail(pk)


# =================================================================================================
# The ladder — draft -> active -> superseded
# =================================================================================================
@login_required
@require_POST
def clientratecard_activate(request, pk):
    """draft -> active. **Re-runs the overlap guard inside the row lock.**

    The guard cannot be left to ``clean()`` alone here: this verb does not go through a form, and
    the question it asks — "is another card already live over these dates?" — reads a SIBLING row.
    Evaluated outside the lock that is a plain snapshot read: it answers about the state the request
    started in, and the write then lands the moment a competing activation commits (the 4.13
    cancel/delete TOCTOU fix). Inside the lock, the second of two concurrent activations sees the
    first and is refused.

    Activating an EMPTY tariff is allowed and warned about rather than refused: a card with no lines
    is a legitimate intermediate state (prices agreed, not yet typed), and a run against it produces
    a calculated bill of zero, which is a correct answer to an empty tariff. Silence would not be.
    """
    with transaction.atomic():
        obj = get_object_or_404(ClientRateCard.objects.select_for_update().select_related("client"),
                                pk=pk, tenant=request.tenant)
        if obj.status != "draft":
            messages.error(request, f"{obj.number} cannot be activated — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)

        conflict = obj.overlapping_active_card()
        if conflict is not None:
            span = conflict.effective_to or "open-ended"
            messages.error(
                request,
                f"{conflict.number} is already the active tariff for {obj.client.code} from "
                f"{conflict.effective_from} to {span}, and these ranges overlap. Two active cards "
                "over one day means the billing run has two prices for it — supersede that one "
                "first.")
            return _detail(pk)

        obj.status = "active"
        obj.save(update_fields=["status", "updated_at"])
        # INSIDE the transaction, with the row still locked. Outside it, a failure between the
        # commit and this line leaves a tariff live with nothing recording who put it there.
        write_audit_log(request.user, obj, "update", {
            "action": "activate",
            "status": "active",
            "client": obj.client.code,
            "effective_from": str(obj.effective_from),
            "effective_to": str(obj.effective_to) if obj.effective_to else None,
        })

    messages.success(request, f"{obj.number} is now the active tariff for {obj.client.code}.")
    if not obj.lines.filter(is_active=True).exists():
        messages.warning(
            request,
            f"{obj.number} has no active rate lines, so a billing run against it will calculate to "
            "zero. Add the charges before the first run.")
    return _detail(pk)


@login_required
@require_POST
def clientratecard_supersede(request, pk):
    """active -> superseded, stamping ``effective_to`` so the card stops pricing.

    The stamp is ``max(effective_from, today)`` and is only APPLIED when it would bring the end date
    forward — three separate rules, each of which exists because of a real row:

    * a card that never had an end date gets today's, so retiring it is not silently a no-op;
    * a card already ending BEFORE today keeps its own date, because moving it forward would
      re-price days it never priced;
    * a card whose ``effective_from`` is in the FUTURE (drafted early, activated early) is stamped
      at its own start rather than at today, because ``effective_to < effective_from`` is a range
      the model refuses — and it should, since it prices nothing.

    ``full_clean()`` is deliberately NOT run: the overlap guard would fire against this very card's
    own former self on some ranges, and superseding is the operation that RESOLVES an overlap. The
    two columns written here are computed, not typed.
    """
    with transaction.atomic():
        obj = get_object_or_404(ClientRateCard.objects.select_for_update().select_related("client"),
                                pk=pk, tenant=request.tenant)
        if obj.status != "active":
            messages.error(request, f"{obj.number} cannot be superseded — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)

        today = timezone.localdate()
        end_on = max(obj.effective_from, today) if obj.effective_from else today
        before = obj.effective_to
        fields = ["status", "updated_at"]
        obj.status = "superseded"
        if before is None or before > end_on:
            obj.effective_to = end_on
            fields.append("effective_to")
        obj.save(update_fields=fields)
        write_audit_log(request.user, obj, "update", {
            "action": "supersede",
            "status": "superseded",
            "client": obj.client.code,
            "effective_to": [str(before) if before else None,
                             str(obj.effective_to) if obj.effective_to else None],
        })

    messages.success(
        request,
        f"{obj.number} superseded — it stops pricing after {obj.effective_to}. Draft the next "
        "version and activate it to take over.")
    return _detail(pk)


# =================================================================================================
# The rate lines — the parent's detail page IS their list
# =================================================================================================
@login_required
def clientratecardline_create(request, pk):
    """Add one priced charge to the tariff named by the ROUTE (``pk`` is the RATE CARD).

    Hand-rolled rather than ``crud_create``: that helper cannot pass ``rate_card=`` into the form's
    constructor, and it stamps ``tenant`` on an object that has no such column. Hand-rolled means
    this path owes its own :func:`write_audit_log` — the ``crud_*`` helpers write one for you and
    nothing else does — and that call must pass ``tenant=`` explicitly, because ``write_audit_log``
    reads ``obj.tenant`` and this child has none (without it the row would be filed under the USER's
    workspace by fallback, which for a superuser is no workspace at all).

    The parent is assigned from the route AFTER ``is_valid()`` as well as being stamped by the
    form's ``__init__``. Restating it is deliberate: this view must not depend on a form's
    constructor for the column that decides which tariff owns the row.

    ``is_edit`` is **False**; the template gets ``rate_card`` for its title, breadcrumb and cancel
    link, and no ``obj``.
    """
    if _need_tenant(request):
        return redirect("scm:clientratecard_list")
    rate_card = get_object_or_404(ClientRateCard.objects.select_related("client"),
                                  pk=pk, tenant=request.tenant)
    if _refuse_locked(request, rate_card, "adding a rate line"):
        return _detail(pk)
    # Bounded here as well as in `ClientRateCardLine.clean()`: the model check renders as a form
    # error on a page the user already opened, this one refuses before the page is even built.
    if rate_card.lines.count() >= MAX_RATE_CARD_LINES:
        messages.error(
            request,
            f"{rate_card.number} already carries the maximum of {MAX_RATE_CARD_LINES} rate lines. "
            "A tariff that large is almost certainly two tariffs — start a new version instead.")
        return _detail(pk)

    if request.method == "POST":
        form = ClientRateCardLineForm(request.POST, rate_card=rate_card, tenant=request.tenant)
        if form.is_valid():
            line = form.save(commit=False)
            # From the ROUTE, never from the POST body — a parent pk in a body is how a caller
            # grafts a priced line onto somebody else's tariff.
            line.rate_card = rate_card
            line.save()
            write_audit_log(request.user, line, "create", {
                "rate_card": rate_card.number,
                "charge_category": line.charge_category,
                "charge_basis": line.charge_basis,
                "rate": str(line.rate),
            }, tenant=request.tenant)
            messages.success(request, f"{line.description} added to {rate_card.number}.")
            return _detail(pk)
        # Re-rendered below with the form's own field errors — a banner repeating them is noise.
    else:
        form = ClientRateCardLineForm(rate_card=rate_card, tenant=request.tenant)

    return render(request, "scm/3pl/clientratecardline/form.html", {
        "form": form,
        "is_edit": False,
        # The form has no `rate_card` field, so the breadcrumb, the page title and the cancel link
        # can only get the parent from here.
        "rate_card": rate_card,
    })


@login_required
def clientratecardline_edit(request, pk):
    """Edit one rate line (``pk`` is the LINE). Refused once the parent has left ``draft``.

    ``ClientRateCardLine`` carries **no tenant column** — it is a pure child of one tariff — so it is
    resolved through the PARENT and never on its own pk. A bare pk lookup here would be a
    cross-tenant write, and it is the dangerous kind: nothing about the response would look wrong,
    so no query anybody runs afterwards would ever reveal that it happened.

    BOTH ``rate_card__tenant`` and ``rate_card__client__tenant`` are stated. They cannot disagree
    today — ``ClientRateCard.clean()`` refuses a cross-tenant client — but a child fetched through
    one path alone is exactly the lookup that stops being safe the day somebody adds a second write
    path, and stating both costs nothing. A tenant-less user resolves to ``tenant IS NULL`` against
    a NOT NULL column and gets a 404, which is the right answer rather than a lucky one.
    """
    obj = get_object_or_404(
        ClientRateCardLine.objects.select_related("rate_card", "rate_card__client"),
        pk=pk, rate_card__tenant=request.tenant, rate_card__client__tenant=request.tenant)
    rate_card = obj.rate_card
    if _refuse_locked(request, rate_card, "editing a rate line"):
        return _detail(rate_card.pk)

    if request.method == "POST":
        form = ClientRateCardLineForm(request.POST, instance=obj, rate_card=rate_card,
                                      tenant=request.tenant)
        if form.is_valid():
            line = form.save()
            write_audit_log(request.user, line, "update", {
                "rate_card": rate_card.number,
                **_changed(form),
            }, tenant=request.tenant)
            messages.success(request, f"{line.description} updated on {rate_card.number}.")
            return _detail(rate_card.pk)
    else:
        form = ClientRateCardLineForm(instance=obj, rate_card=rate_card, tenant=request.tenant)

    return render(request, "scm/3pl/clientratecardline/form.html", {
        "form": form,
        "is_edit": True,
        "obj": obj,
        "rate_card": rate_card,
    })


@login_required
@require_POST
def clientratecardline_delete(request, pk):
    """Delete one rate line (``pk`` is the LINE). POST-only; refused once the parent has left draft.

    The audit row is written BEFORE the delete, because it captures ``str(obj)`` and a deleted
    instance's ``rate_card`` walk would be a second query against a row that is on its way out. The
    two are wrapped in one ``transaction.atomic()`` so a trail entry can never outlive a delete that
    rolled back.
    """
    obj = get_object_or_404(
        ClientRateCardLine.objects.select_related("rate_card", "rate_card__client"),
        pk=pk, rate_card__tenant=request.tenant, rate_card__client__tenant=request.tenant)
    rate_card = obj.rate_card
    if _refuse_locked(request, rate_card, "removing a rate line"):
        return _detail(rate_card.pk)

    description = obj.description
    with transaction.atomic():
        write_audit_log(request.user, obj, "delete", {
            "rate_card": rate_card.number,
            "charge_category": obj.charge_category,
            "charge_basis": obj.charge_basis,
            "rate": str(obj.rate),
        }, tenant=request.tenant)
        obj.delete()

    messages.success(request, f"{description} removed from {rate_card.number}.")
    return _detail(rate_card.pk)
