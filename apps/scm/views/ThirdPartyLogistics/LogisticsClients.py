"""SCM 4.17 Third-Party Logistics (3PL) — ``LogisticsClient`` views: the DEPOSITOR MASTER.

This is the sub-module's root screen and the target of the **Client Integration** sidebar bullet. One
row per company whose goods we hold: their billing convention, their space commitment, their contract
and how their orders reach us. Everything else in 4.17 hangs off it — a tariff (``ClientRateCard``),
a period calculation (``ClientBillingRun``), a promise (``ClientSLA``) — and so do the two additive
``owner_client`` columns 4.17 puts on 4.3's ``Item`` and ``Location``, which are what make client
inventory segregation a QUERY rather than a second stock table.

--------------------------------------------------------------------------------------------------
THE PERFORMANCE RULE THIS MODULE IS WRITTEN AROUND
--------------------------------------------------------------------------------------------------
``LogisticsClient`` exposes ``on_hand_quantity()``, ``on_hand_value()``, ``sku_count()``,
``dedicated_location_count()``, ``open_sla_breaches()`` and ``last_billing_run()``. All six are
correct, all six fire their own query, and all six are meant for a SINGLE row on the detail page.
**None of them may be called from the list view or from ``list.html``** — 15 rows a page x six
methods is 90 extra queries for one screen, which is exactly the 4.13 ``asset_list`` finding, and the
fact that the ORM makes them read nicely in a template is what makes it easy to ship. The contracted
per-row reads for ``list.html`` are the plain columns and the ``get_*_display`` labels; the two report
pages compute the same facts for many clients at once with grouped aggregates instead.

--------------------------------------------------------------------------------------------------
DELETE IS THE DANGEROUS VERB HERE, AND IT IS GUARDED FROM TWO SIDES
--------------------------------------------------------------------------------------------------
``ClientRateCard.client`` and ``ClientBillingRun.client`` are both ``PROTECT`` — a tariff and a
billed period are commercial evidence and must not vanish under one click — while ``ClientSLA.client``
is ``CASCADE``, so a delete that gets through takes the client's whole SLA record with it.
:func:`logisticsclient_delete` therefore pre-counts the two protected relations for a sentence
somebody can act on, ALSO catches ``ProtectedError`` in case a row is filed between the check and the
delete (the 4.10 ``currency_delete`` finding), and steers to ``status="suspended"`` /
``"terminated"`` — which is the move that actually solves the problem, because it stops the
commercial relationship without destroying a single row of evidence.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/3pl/logisticsclient/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``). Filter context: ``status_choices`` / ``billing_cycle_choices`` /
  ``space_model_choices`` / ``integration_mode_choices`` (lists of ``(value, label)`` pairs; compare
  against ``request.GET.<param>`` directly — these are strings, so **no** ``|stringformat:"d"`` and
  never ``|slugify``). Header chips: ``stats``, a dict with keys ``total`` / ``active`` /
  ``onboarding`` / ``prospect`` / ``suspended`` / ``breaching``. Per-row reads: ``obj.code``,
  ``obj.party``, ``obj.status`` + ``obj.get_status_display``, ``obj.get_billing_cycle_display``,
  ``obj.get_space_model_display``, ``obj.get_integration_mode_display``, ``obj.number``.
  **``obj.notes`` is deferred** — it is the one TextField no list column renders, and reading it in
  the template costs a query per row.
* ``scm/3pl/logisticsclient/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path, from
  ``crud_edit``).
* ``scm/3pl/logisticsclient/detail.html`` — see :func:`logisticsclient_detail`'s docstring for the
  full key list; it is long enough to belong beside the code that builds it.

Badge classes come from ``_choices.py``'s ``CLIENT_STATUS_CSS``. Only the six colour-named classes
exist in ``theme.css``: ``badge-green`` / ``badge-red`` / ``badge-amber`` / ``badge-info`` /
``badge-muted`` / ``badge-slate``. ``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT
EXIST and render as completely unstyled text (L33).
"""
# ProtectedError is a db-layer exception, not a model, so it is imported from django directly rather
# than through `_common`'s star (the `AssetManagement/Assets.py` precedent).
from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant

from apps.core.models import PartyRole
from apps.scm.forms import LogisticsClientForm
from apps.scm.models import (BILLING_CYCLE_CHOICES, CLIENT_STATUS_CHOICES,
                             INTEGRATION_MODE_CHOICES, LogisticsClient, SPACE_MODEL_CHOICES)

#: How many rows each panel on the detail page shows. A queryset SLICE, so the DATABASE applies it —
#: it bounds what is FETCHED, not merely what is rendered (L40 §1: a guard that first builds the whole
#: thing is the payload, not a guard). Billing runs in particular accumulate one row per period
#: forever, so an unbounded panel is a page that gets slower every month it is left alone.
MAX_PANEL_ROWS = 20


# ================================================================================== small helpers
def _detail(pk):
    """The one redirect target every refusal in this module answers with."""
    return redirect("scm:logisticsclient_detail", pk=pk)


def _panel(queryset):
    """``(rows, truncated)`` — fetch ``MAX_PANEL_ROWS + 1`` and report whether the cap bit.

    The ``+ 1`` is what makes the count free in the common case: when the slice did NOT truncate, the
    list length IS the total and a round trip to learn what we already hold is a query for nothing.
    ``portaldocumentshare_detail`` established the shape; this is it, named.
    """
    rows = list(queryset[:MAX_PANEL_ROWS + 1])
    truncated = len(rows) > MAX_PANEL_ROWS
    del rows[MAX_PANEL_ROWS:]
    return rows, truncated


# ======================================================================================= the list
@login_required
def logisticsclient_list(request):
    """The depositor register: search, four filters, six header chips.

    EVERY filter is applied BEFORE ``crud_list`` paginates. A filter applied afterwards would page
    over the unfiltered set and quietly show the wrong rows on page 2.

    All four filters are plain string columns, so none of them needs the ``is_int`` L11 guard — and a
    junk value simply matches nothing rather than raising, because ``crud_list`` hands the string
    straight to a ``CharField`` lookup. (``crud_list`` still catches ``ValueError`` /
    ``ValidationError`` out of ``.filter()`` for the cases where a column would reject the value.)

    ``.defer("notes")`` drops the one ``TextField`` no list row renders — only the detail page and
    the form read it. ``defer`` touches the SELECT list ONLY, so every filter below is unaffected.

    ``stats`` is counted over the WHOLE workspace rather than the filtered page, on purpose: "3
    clients breaching an SLA" is a fact somebody has to act on, and recomputing it per filter would
    make the number change as you browse.

    ``stats["breaching"]`` is a DISTINCT count of clients carrying at least one active, breached SLA,
    and it is written through the reverse relation name rather than by importing ``ClientSLA`` — the
    sibling entity, whose own module imports this one's model. ``.distinct()`` is load-bearing: a
    client with three breached SLAs is ONE breaching client, and the join would otherwise count it
    three times.
    """
    queryset = (LogisticsClient.objects.filter(tenant=request.tenant)
                # `party` is read by every row AND by the model's own __str__.
                .select_related("party")
                .defer("notes")
                # STATED, not inherited. It is Meta.ordering, which is already a total order
                # (`code` + `id`), so page 2 is deterministic rather than depending on row order.
                .order_by("code", "id"))

    base = LogisticsClient.objects.filter(tenant=request.tenant)
    stats = base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        onboarding=Count("id", filter=Q(status="onboarding")),
        prospect=Count("id", filter=Q(status="prospect")),
        suspended=Count("id", filter=Q(status="suspended")),
    )
    stats["breaching"] = (base.filter(slas__is_active=True, slas__status="breached")
                          .distinct().count())

    return crud_list(
        request, queryset, "scm/3pl/logisticsclient/list.html",
        # `notes` is deliberately NOT searched: the search box on this page is for finding a client,
        # and matching an internal note would return a row whose visible columns contain nothing the
        # user typed, which reads as a bug.
        search_fields=["code", "party__name", "client_system", "number"],
        filters=[("status", "status", False),
                 ("billing_cycle", "billing_cycle", False),
                 ("space_model", "space_model", False),
                 ("integration_mode", "integration_mode", False)],
        extra_context={
            # The same lists the form renders from, named directly rather than read back off
            # `_meta.get_field(...).choices` — that is what keeps "the filter offers exactly what the
            # column accepts" a fact rather than a coincidence.
            "status_choices": CLIENT_STATUS_CHOICES,
            "billing_cycle_choices": BILLING_CYCLE_CHOICES,
            "space_model_choices": SPACE_MODEL_CHOICES,
            "integration_mode_choices": INTEGRATION_MODE_CHOICES,
            "stats": stats,
        },
    )


# ======================================================================================= the CRUD
@login_required
def logisticsclient_create(request):
    """Onboard one client. This row IS the agreement's configuration — there is no lifecycle verb.

    ``crud_create`` stamps the tenant, audits and refuses a tenant-less user; ``_need_tenant`` is
    still called first so the refusal lands back on this module's list rather than the dashboard.

    ``LogisticsClientForm`` ALSO stamps the tenant onto the unsaved instance
    (``TenantUniqueMixin``), and that is not redundancy: ``crud_create`` assigns ``obj.tenant`` only
    AFTER ``is_valid()``, so without the form-side stamp both ``LogisticsClient.clean()``'s
    cross-tenant guards and the ``("tenant", "code")`` / ``("tenant", "party")`` uniqueness checks
    would validate an instance whose ``tenant_id`` is None — and the uniqueness ones are the rules a
    user breaks by hand, which without the mixin pass ``is_valid()`` and then raise an uncaught
    ``IntegrityError`` on ``save()``.

    Success returns to the LIST rather than the new detail page, matching every other scm create.
    """
    if _need_tenant(request):
        return redirect("scm:logisticsclient_list")
    return crud_create(request, form_class=LogisticsClientForm,
                       template="scm/3pl/logisticsclient/form.html",
                       success_url="scm:logisticsclient_list")


@login_required
def logisticsclient_edit(request, pk):
    """Change a client's configuration. Every field on the form is editable, always.

    There is no status ladder and no frozen state here: the row is configuration rather than a
    document, so there is no history for an edit to rewrite. The two columns an edit genuinely cannot
    reach are ``onboarded_on`` (stamped once by ``LogisticsClient.save()`` the first time the client
    is active, and never restamped, so a suspend/reactivate cycle cannot rewrite the go-live date)
    and ``last_synced_at``. Both are ``editable=False``, which keeps them off the form automatically
    rather than relying on the field list staying correct (L22).

    **An edit here does NOT rewrite a billed period.** ``ClientBillingRunLine`` snapshots the
    category, basis and rate it was calculated at, so changing a client's tax rate or minimum today
    leaves every already-calculated run reading exactly as it did when it was approved.
    """
    return crud_edit(request, model=LogisticsClient, pk=pk, form_class=LogisticsClientForm,
                     template="scm/3pl/logisticsclient/form.html",
                     success_url="scm:logisticsclient_list")


@login_required
def logisticsclient_detail(request, pk):
    """The 360°: the agreement, the tariff, the billing history, the promises and the stock held.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.LogisticsClient`, with ``party``, ``parent_client``
      (and **``parent_client__party``**, because ``LogisticsClient.__str__`` walks it), ``currency``,
      ``payment_terms``, ``default_revenue_account``, ``contract_document`` and ``account_manager``
      joined.
    * ``rate_cards`` — a LIST of :class:`ClientRateCard`, newest ``effective_from`` first, capped at
      ``panel_limit``; ``rate_card_count`` (int, every card ever written for this client);
      ``active_rate_card`` (a ``ClientRateCard`` or **``None``** — the one that is ``active`` AND
      effective today; ``None`` means this client currently has no tariff and **a billing run for
      them would price nothing**, which the page should say rather than leave blank).
    * ``billing_runs`` — a LIST of :class:`ClientBillingRun`, newest ``period_end`` first, capped;
      ``billing_run_count`` (int).
    * ``slas`` — a LIST of :class:`ClientSLA`, **active ones first**, capped; ``sla_count`` (int);
      ``open_breach_count`` (int — active SLAs currently sitting at ``breached``). Render an SLA's
      ``last_measured_value`` of ``None`` as "Not measured", never as 0 and never as a blank cell.
    * ``child_clients`` — a LIST of the divisions/brands parented to this client (empty is the normal
      case for a standalone client).
    * **The stock position, all four DERIVED and none of them stored (L37):**
      ``on_hand_quantity`` (Decimal), ``on_hand_value`` (Decimal), ``sku_count`` (int — item masters
      ASSIGNED to this client, which is deliberately not "items currently holding stock": a client
      with forty SKUs and an empty warehouse still has forty SKUs) and ``dedicated_location_count``
      (int).
    * ``has_customer_role`` (bool) — whether the party carries a ``customer`` ``PartyRole``.
      **False renders an informational chip, never an error**: nothing in this module refuses a
      client whose party lacks the tag, and the remedy is one edit on the party record.
    * ``panel_limit`` (int) — the row cap the panels were sliced at, so the page can say it is
      showing a window rather than a total.
    * ``can_delete`` (bool) — False when ``rate_card_count`` or ``billing_run_count`` is non-zero,
      mirroring EXACTLY what :func:`logisticsclient_delete` refuses. Offering a button the view will
      refuse is the 4.11 finding.

    QUERIES: one for the client, one for the party role, four panels (+ a COUNT each only where the
    cap actually bit), one grouped aggregate for the stock value, one for the quantity, one for the
    SKU count, one for the dedicated locations, one for the open breaches. Flat — not one of them per
    row.
    """
    obj = get_object_or_404(
        LogisticsClient.objects.select_related(
            "party", "parent_client", "parent_client__party", "currency", "payment_terms",
            "default_revenue_account", "contract_document", "account_manager"),
        pk=pk, tenant=request.tenant)

    today = timezone.localdate()

    # --- the tariff -------------------------------------------------------------------------------
    # Every panel states `tenant=` even though it is reached through an object already proved to be
    # this workspace's. It narrows nothing and it is the house idiom: it holds the module-wide scoping
    # rule mechanically, and each child model's index leads with `tenant`, which a query through the
    # related manager alone cannot open.
    rate_cards, rate_cards_truncated = _panel(
        obj.rate_cards.filter(tenant=request.tenant)
        .select_related("client", "currency")
        .order_by("-effective_from", "-version", "-id"))
    rate_card_count = (obj.rate_cards.filter(tenant=request.tenant).count()
                       if rate_cards_truncated else len(rate_cards))

    # The card that is BOTH active and in force today. `effective_to=None` is open-ended, i.e. +∞ —
    # the same reading `ClientRateCard.is_effective_on()` uses, so the chip on this page and the card
    # a billing run picks up cannot come to different conclusions.
    active_rate_card = (obj.rate_cards
                        .filter(tenant=request.tenant, status="active",
                                effective_from__lte=today)
                        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
                        .select_related("currency")
                        .order_by("-effective_from", "-version", "-id").first())

    # --- the billing history -----------------------------------------------------------------------
    # Ordered by `period_end`, not by creation: runs are routinely raised out of order (a late
    # correction for March raised in May), and "the newest row" is not "the latest period".
    billing_runs, runs_truncated = _panel(
        obj.billing_runs.filter(tenant=request.tenant)
        .select_related("client", "rate_card", "invoice")
        .order_by("-period_end", "-id"))
    billing_run_count = (obj.billing_runs.filter(tenant=request.tenant).count()
                         if runs_truncated else len(billing_runs))

    # --- the promises --------------------------------------------------------------------------------
    # Active first, then worst-status first, so a breach is never the thing that falls off the cap.
    slas, slas_truncated = _panel(
        obj.slas.filter(tenant=request.tenant)
        .select_related("client", "scope_location")
        .order_by("-is_active", "metric", "id"))
    sla_count = (obj.slas.filter(tenant=request.tenant).count()
                 if slas_truncated else len(slas))

    # --- the group -----------------------------------------------------------------------------------
    child_clients, children_truncated = _panel(
        LogisticsClient.objects.filter(tenant=request.tenant, parent_client=obj)
        .select_related("party").order_by("code", "id"))

    return render(request, "scm/3pl/logisticsclient/detail.html", {
        "obj": obj,

        "rate_cards": rate_cards,
        "rate_cards_truncated": rate_cards_truncated,
        "rate_card_count": rate_card_count,
        "active_rate_card": active_rate_card,

        "billing_runs": billing_runs,
        "billing_runs_truncated": runs_truncated,
        "billing_run_count": billing_run_count,

        "slas": slas,
        "slas_truncated": slas_truncated,
        "sla_count": sla_count,
        "open_breach_count": obj.open_sla_breaches(),

        "child_clients": child_clients,
        "child_clients_truncated": children_truncated,

        # The model's own derived methods, on ONE row — which is exactly what they are for. The list
        # page must not do this (see the module docstring), and the two report pages compute the same
        # facts for many clients with grouped aggregates instead.
        "on_hand_quantity": obj.on_hand_quantity(),
        "on_hand_value": obj.on_hand_value(),
        "sku_count": obj.sku_count(),
        "dedicated_location_count": obj.dedicated_location_count(),

        # Informational, never a blocker. `LogisticsClient` deliberately does not validate this — an
        # operations team onboarding a client before finance tags the party is an ordinary Tuesday.
        "has_customer_role": PartyRole.objects.filter(
            tenant=request.tenant, party_id=obj.party_id, role="customer").exists(),

        "panel_limit": MAX_PANEL_ROWS,

        # The exact condition logisticsclient_delete enforces — one statement of the rule, read by
        # the button and by the route behind it, so the two cannot disagree (the 4.10 finding).
        "can_delete": not (rate_card_count or billing_run_count),
    })


@login_required
@require_POST
def logisticsclient_delete(request, pk):
    """Delete a client — refused while a tariff or a billed period references it, and loud about it.

    **Read the consequence before the code.** ``ClientRateCard.client`` and
    ``ClientBillingRun.client`` are ``PROTECT``, so the database will refuse those; but
    ``ClientSLA.client`` is ``CASCADE``, which means a delete that gets through destroys the client's
    entire SLA record — every target, every measurement window, every breach count — and nothing
    reconstructs it. The two ``owner_client`` columns on ``Item`` and ``Location`` are ``SET_NULL``,
    so a successful delete also silently un-assigns every SKU and every dedicated bin, which is the
    quiet half of the damage and the reason the message below counts them.

    **The right move is almost always ``status="suspended"`` or ``"terminated"``**, and the refusal
    says so. It is not a soft-delete dressed up: it is the actual commercial fact (this client has
    stopped, or has paused), it keeps every tariff and invoice readable, and it leaves the stock
    assignment intact so the goods on the floor still have an owner.

    **Two guards for one hazard, on purpose.** The pre-count produces the sentence a user can act on
    ("3 rate cards and 11 billing runs reference this client"); the ``ProtectedError`` catch is what
    stops a row filed between the check and the delete from becoming an uncaught 500 on a mainline
    delete path (the 4.10 ``currency_delete`` finding, priced in advance rather than after). The
    catch is generic rather than an enumeration of models, because an enumeration goes stale silently
    — as a 500.

    ``transaction.atomic()`` wraps the delegated delete so the audit row ``crud_delete`` writes
    BEFORE deleting rolls back with a delete that then fails, rather than recording a deletion that
    did not happen.
    """
    obj = get_object_or_404(LogisticsClient.objects.select_related("party"),
                            pk=pk, tenant=request.tenant)

    cards = obj.rate_cards.filter(tenant=request.tenant).count()
    runs = obj.billing_runs.filter(tenant=request.tenant).count()
    if cards or runs:
        messages.error(
            request,
            f"{obj.number} is referenced by {cards} rate card(s) and {runs} billing run(s) and "
            "cannot be deleted — a tariff and a billed period are what an invoice was calculated "
            "from, and they must keep the client they were raised against. Set this client's status "
            "to Suspended or Terminated instead: that ends the commercial relationship without "
            "destroying any of the record.")
        return _detail(pk)

    # Counted BEFORE the delete, while the rows still exist to be counted.
    slas = obj.slas.filter(tenant=request.tenant).count()
    items = obj.owned_items.filter(tenant=request.tenant).count()
    locations = obj.dedicated_locations.filter(tenant=request.tenant).count()
    label = f"{obj.number} · {obj.party}"

    try:
        with transaction.atomic():
            response = crud_delete(request, model=LogisticsClient, pk=pk,
                                   success_url="scm:logisticsclient_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"{obj.number} is still referenced by {', '.join(blockers)} and cannot be deleted — set "
            "its status to Suspended or Terminated instead, which ends the relationship without "
            "destroying the record.")
        return _detail(pk)

    # No second success banner: `crud_delete` already flashed one, and two green bars for one action
    # is the 4.13 double-message finding. The info line below is the one that actually has something
    # to say — what ELSE just changed, which the green bar cannot express.
    if slas or items or locations:
        messages.info(
            request,
            f"Removed with {label}: {slas} SLA(s), and {items} item(s) and {locations} location(s) "
            "are now unassigned. The SLA record cannot be reconstructed; the items and locations "
            "still exist and still hold stock — they simply no longer name an owner, so they will "
            "appear as unassigned on the client inventory report until they are re-assigned.")
    return response
