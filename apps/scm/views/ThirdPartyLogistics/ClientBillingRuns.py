"""SCM 4.17 Third-Party Logistics (3PL) Management — ``ClientBillingRun`` views.

Twelve views: the CRUD five, the four-rung verb ladder (``calculate → approve → draft invoice``,
plus ``void``), and three for the manual charge lines.

--------------------------------------------------------------------------------------------------
THREE RULES EVERY VERB IN THIS MODULE OBEYS
--------------------------------------------------------------------------------------------------

**1. Every verb is ``@require_POST``, so a GET to one is a 405 rather than a silent state change.**
A billing run drafts an invoice; a link-prefetcher or a crawler following a GET verb would be
drafting invoices.

**2. Every verb re-checks its own status guard here, in the view.** The templates hide the buttons
too, but hiding a button does not stop a direct POST — and the two moves that matter (``approve``
and ``draft_invoice``) are the two that turn warehouse activity into an accounts-receivable
document. Each model method raises ``ValidationError`` on a bad transition and each view catches it
into ``messages.error``, so a stale tab is a friendly message and never a 500.

**3. Every verb writes its OWN** :func:`write_audit_log`. The ``crud_*`` helpers write one for you;
nothing else does, and a hand-rolled path that forgets it leaves the money trail with a gap exactly
where somebody would look for it.

``approve`` and ``draft_invoice`` are additionally ``@tenant_admin_required`` (L27): they move
money. The detail template must therefore wrap BOTH buttons in
``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` — showing a member a button
they will 403 on is the 4.11 finding.

--------------------------------------------------------------------------------------------------
THE SLA-CREDIT AND UNBILLED-ACTIVITY PANELS ARE INFORMATION, NOT ACCOUNTING
--------------------------------------------------------------------------------------------------
``sla_credits`` is a SUGGESTION computed on read from this run's own total; nothing anywhere raises
a credit note from it, and the template labels it "SUGGESTED — NOT APPLIED". ``unbilled`` names the
receipts / orders / shipments that happened in the period and that this tariff prices NOTHING for —
the single most useful thing a 3PL account manager can be shown, and the reason it is labelled "not
billed" rather than quietly omitted.
"""
import datetime

from django.db.models import DecimalField, Value
from django.db.models.functions import Coalesce
# `crud_edit` does a bare `redirect(success_url)`, so a route that takes a pk has to arrive already
# reversed — a name alone would raise NoReverseMatch on save.
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
# `_changed` is private, so the star import above skips it — named explicitly, exactly as the other
# hand-rolled save paths in this package do.
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant

from apps.scm.models._base import ZERO, q2
from apps.scm.models import (
    ClientBillingRun,
    ClientBillingRunLine,
    ClientSLA,
    LogisticsClient,
)
from apps.scm.models.ThirdPartyLogistics._choices import (
    CHARGE_CATEGORY_CHOICES,
    CHARGE_CATEGORY_CSS,
    EDITABLE_RUN_STATUSES,
    RUN_STATUS_CHOICES,
    SLA_STATUS_CSS,
)
from apps.scm.forms import ClientBillingRunForm, ClientBillingRunLineForm

#: How many child rows a detail panel shows before it stops and links out. Passed to the template as
#: ``panel_limit`` so the page can say "showing the first N of M" in its own words.
PANEL_LIMIT = 20


def _client_qs(tenant):
    """The ``?client=`` dropdown, ordered the way the list page reads."""
    if tenant is None:
        return LogisticsClient.objects.none()
    return LogisticsClient.objects.filter(tenant=tenant).select_related("party").order_by("code", "id")


def _as_date(raw):
    """A ``YYYY-MM-DD`` GET value as a ``date``, or ``None``.

    Junk is SKIPPED, never raised on — the same L11 posture ``as_db_int`` takes for int filters. A
    hand-edited ``?period_from=lastweek`` must narrow nothing rather than 500 on a value anybody can
    type into the address bar. ``crud_list`` would also swallow the resulting ``ValidationError``,
    but parsing here keeps the rule visible instead of relying on a helper's ``except`` clause.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


# ============================================================================ CRUD
@login_required
def clientbillingrun_list(request):
    """Every run in the workspace, newest period first.

    ``select_related`` covers every FK a row touches AND the chain ``__str__`` walks
    (``client.code``): a row renders ``client.code``, ``rate_card.number`` and ``invoice``, and the
    audit/message paths call ``str(run)``.
    """
    qs = (ClientBillingRun.objects.filter(tenant=request.tenant)
          .select_related("client", "client__party", "rate_card", "invoice"))

    # Both date bounds are parsed BEFORE pagination, and both echo back into their inputs from
    # request.GET.period_from / request.GET.period_to in the template.
    period_from = _as_date(request.GET.get("period_from"))
    if period_from:
        qs = qs.filter(period_end__gte=period_from)
    period_to = _as_date(request.GET.get("period_to"))
    if period_to:
        qs = qs.filter(period_start__lte=period_to)

    # Stats are computed over the WHOLE workspace, never over the filtered page — a tile that moved
    # every time somebody typed in the search box would be a different number from the one the
    # dashboard shows. `approved_value` counts approved AND invoiced runs: money that has been
    # signed off does not stop being signed off when it reaches accounting.
    #
    # TWO aggregate() CALLS, and the split is REQUIRED rather than stylistic. `total` is both the
    # template's name for the row COUNT and the model's own money column, and inside a single
    # `aggregate()` Django resolves a column name against the aliases declared in that same call
    # FIRST — so `Sum("total")` next to `total=Count("id")` resolves to the count and raises
    # `FieldError: Cannot compute Sum('total'): 'total' is an aggregate`, a hard 500 on the list
    # page. Renaming the alias was the alternative and was rejected: `stats.total` is the contract
    # the template renders. Two round trips over an indexed tenant filter is the cheaper half of
    # that trade.
    counts = ClientBillingRun.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        draft=Count("id", filter=Q(status="draft")),
        calculated=Count("id", filter=Q(status="calculated")),
        approved=Count("id", filter=Q(status="approved")),
        invoiced=Count("id", filter=Q(status="invoiced")),
        void=Count("id", filter=Q(status="void")),
    )
    # Declared alone, so "total" here can only mean the column.
    value = ClientBillingRun.objects.filter(tenant=request.tenant).aggregate(
        approved_value=Coalesce(
            Sum("total", filter=Q(status__in=("approved", "invoiced"))),
            Value(ZERO), output_field=DecimalField(max_digits=18, decimal_places=2)),
    )
    stats = {**counts, **value}

    return crud_list(
        request, qs, "scm/3pl/clientbillingrun/list.html",
        search_fields=["number", "client__code", "client__party__name"],
        # `client` is int-guarded (is_int=True) so `?client=abc`, `?client=²` and a 21-digit value
        # all SKIP the filter instead of raising out of .filter() (L11).
        filters=[("client", "client_id", True), ("status", "status", False)],
        extra_context={
            "clients": _client_qs(request.tenant),
            "status_choices": RUN_STATUS_CHOICES,
            "stats": stats,
        },
    )


@login_required
def clientbillingrun_create(request):
    if _need_tenant(request):
        return redirect("scm:clientbillingrun_list")
    return crud_create(
        request,
        form_class=ClientBillingRunForm,
        template="scm/3pl/clientbillingrun/form.html",
        success_url="scm:clientbillingrun_list",
    )


@login_required
def clientbillingrun_edit(request, pk):
    """Editable only while the run is ``draft`` or ``calculated``.

    The guard is here rather than only in the template because an approved run's client, tariff or
    period changing under an already-drafted invoice would silently restate what the client was
    billed for.
    """
    obj = get_object_or_404(ClientBillingRun.objects.select_related("client"),
                            pk=pk, tenant=request.tenant)
    if obj.status not in EDITABLE_RUN_STATUSES:
        messages.error(request, f"A {obj.get_status_display().lower()} run can no longer be edited.")
        return redirect("scm:clientbillingrun_detail", pk=pk)
    return crud_edit(
        request,
        model=ClientBillingRun,
        pk=pk,
        form_class=ClientBillingRunForm,
        template="scm/3pl/clientbillingrun/form.html",
        success_url=reverse("scm:clientbillingrun_detail", args=[pk]),
    )


@login_required
@require_POST
def clientbillingrun_delete(request, pk):
    """POST-only. An INVOICED run is never deleted — its invoice would lose its explanation."""
    obj = get_object_or_404(ClientBillingRun.objects.select_related("client", "invoice"),
                            pk=pk, tenant=request.tenant)
    if obj.status == "invoiced":
        number = obj.invoice.number if obj.invoice_id else "an invoice"
        messages.error(request, f"This run has been invoiced as {number} and can't be deleted. "
                                "Void the invoice in Accounting instead.")
        return redirect("scm:clientbillingrun_detail", pk=pk)
    return crud_delete(request, model=ClientBillingRun, pk=pk,
                       success_url="scm:clientbillingrun_list")


@login_required
def clientbillingrun_detail(request, pk):
    """The run, its charges grouped by category, and the three panels that give them context."""
    obj = get_object_or_404(
        ClientBillingRun.objects.select_related(
            "client", "client__party", "client__currency", "rate_card", "rate_card__currency",
            "invoice", "approved_by"),
        pk=pk, tenant=request.tenant)

    # select_related on rate_card_line: the "needs a quantity" chip and the minimum-charge floor
    # both read through it, and 500 lines each firing their own query is the 4.13 asset_list finding.
    lines = list(obj.lines.select_related("rate_card_line").all())

    minimum_applied, minimum_reason = obj.minimum_status()
    sla_credits, sla_credit_total = _sla_credit_panel(obj)

    return render(request, "scm/3pl/clientbillingrun/detail.html", {
        "obj": obj,
        "line_groups": _group_lines(lines),
        "lines": lines,
        "line_count": len(lines),
        "manual_line_count": sum(1 for line in lines if line.is_manual),
        "needs_quantity_count": sum(1 for line in lines if line.needs_manual_quantity),
        "subtotal": obj.subtotal,
        "minimum_adjustment": obj.minimum_adjustment,
        "total": obj.total,
        "minimum_applied": minimum_applied,
        "minimum_reason": minimum_reason,
        "unbilled": _unbilled_panel(obj),
        "sla_credits": sla_credits,
        "sla_credit_total": sla_credit_total,
        "invoice": obj.invoice,
        "panel_limit": PANEL_LIMIT,
        # Every one of these mirrors EXACTLY what the matching view refuses, so a button the page
        # shows is a button that works and a button it hides is one that would have been rejected.
        #
        # `can_approve` / `can_draft_invoice` are the STATUS half only, deliberately. The permission
        # half stays in the template, which wraps both buttons in
        # `{% if request.user.is_superuser or request.user.is_tenant_admin %}` — folding the role in
        # here would leave the page unable to tell "not ready yet" apart from "not yours to press",
        # and those two want different words on the screen.
        "can_edit": obj.status in EDITABLE_RUN_STATUSES,
        "can_add_line": obj.status in EDITABLE_RUN_STATUSES,
        "can_calculate": obj.status in EDITABLE_RUN_STATUSES,
        "can_approve": obj.status == "calculated",
        "can_draft_invoice": obj.status == "approved" and obj.invoice_id is None,
        "can_void": obj.status in ClientBillingRun.VOIDABLE_STATUSES,
        "can_delete": obj.status != "invoiced",
    })


# ============================================================================ detail panels
def _group_lines(lines):
    """The flat line list folded into ``CHARGE_CATEGORY_CHOICES`` order with a subtotal per group.

    Driven by the choices list rather than by whatever categories happen to be present, so the
    groups always read in the same order on every run — storage, then receiving, then outbound, and
    so on down to the minimum. Empty groups are dropped.
    """
    buckets = {}
    for line in lines:
        buckets.setdefault(line.charge_category, []).append(line)

    groups = []
    for value, label in CHARGE_CATEGORY_CHOICES:
        rows = buckets.pop(value, None)
        if not rows:
            continue
        groups.append({
            "category": value,
            "category_label": label,
            # COLOUR-NAMED classes only (badge-green/red/amber/info/muted/slate). A semantic
            # badge-success/-danger renders UNSTYLED against theme.css (L33).
            "category_css": CHARGE_CATEGORY_CSS.get(value, "badge-muted"),
            "lines": rows,
            "subtotal": sum((line.amount or ZERO for line in rows), ZERO),
        })

    # A category the registry grew without a CSS entry still renders — under its raw value, at the
    # end, rather than vanishing off a page somebody is checking an invoice against.
    for value, rows in buckets.items():
        groups.append({
            "category": value,
            "category_label": value.replace("_", " ").title(),
            "category_css": "badge-muted",
            "lines": rows,
            "subtotal": sum((line.amount or ZERO for line in rows), ZERO),
        })
    return groups


def _unbilled_panel(run):
    """Activity in the period that this tariff prices NOTHING for. Labelled "not billed".

    Counted with the same attribution rules the engine bills by, so the two can never disagree about
    what belongs to the client — the counts come straight from the engine's own resolvers rather
    than from a second, drifting copy of the join.
    """
    priced = set(run.rate_card.lines.filter(is_active=True)
                 .values_list("charge_basis", flat=True)) if run.rate_card_id else set()

    rows = []
    # (bases that would price this activity, the engine resolver that counts it, label, note).
    # `per_order` and `per_line` BOTH price an order, so an order-line tariff is not "unbilled
    # orders" — listing it as such would send an account manager chasing a charge that exists.
    checks = (
        (("per_receipt",), "_qty_receipts", "Goods receipts",
         "no per-receipt charge on this tariff"),
        (("per_order", "per_line"), "_qty_orders", "Sales orders",
         "no per-order or per-line charge on this tariff"),
        (("per_shipment",), "_qty_shipments", "Shipments",
         "no per-shipment charge on this tariff"),
    )
    # The three ACTIVITY resolvers take a rate line but read nothing off it — only the STORAGE
    # resolvers narrow on `applies_to_location` / `applies_to_item_category`. Passing None is
    # therefore exactly "the whole client for this period", which is what this panel counts, and it
    # avoids fabricating a throwaway model instance to satisfy a signature.
    for covered, resolver, label, note in checks:
        if priced & set(covered):
            continue
        count, reference, _needs, _note = getattr(run, resolver)(None)
        if count <= 0:
            continue
        rows.append({
            "label": label,
            "count": int(count),
            "note": f"{note} — not billed" + (f" ({reference})" if reference else ""),
        })
    return rows


def _sla_credit_panel(run):
    """``(rows, total)`` of SUGGESTED service credits — computed on read, applied to nothing.

    The basis is THIS run's total, because a service credit is a percentage of the month's fees and
    this run is that month's fees. Nothing here writes a credit note: raising one is
    ``apps/accounting``'s (L29), and the template says so in as many words.
    """
    rows, total = [], ZERO
    if not run.client_id:
        return rows, total

    breaching = (ClientSLA.objects
                 .filter(tenant=run.tenant, client_id=run.client_id, is_active=True,
                         status="breached")
                 .select_related("scope_location")
                 .order_by("metric", "id"))
    basis = run.total or ZERO
    for sla in breaching:
        credit = q2(sla.suggested_service_credit(basis) or ZERO)
        if credit <= ZERO:
            continue
        rows.append({
            "sla": sla,
            "status": sla.status,
            "status_css": SLA_STATUS_CSS.get(sla.status, "badge-muted"),
            "suggested_credit": credit,
            "basis": basis,
        })
        total += credit
    return rows, q2(total)


# ============================================================================ the verb ladder
@login_required
@require_POST
def clientbillingrun_calculate(request, pk):
    """Re-price the period from the tariff. Manual lines survive; derived lines are regenerated."""
    obj = get_object_or_404(ClientBillingRun.objects.select_related("client", "rate_card"),
                            pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            result = obj.calculate(user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:clientbillingrun_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "calculate",
        "lines_written": result["lines_written"],
        "manual_lines": result["manual_lines"],
        "total": str(result["total"]),
    })
    if result["lines_written"] == 0 and result["manual_lines"] == 0:
        # NOT an error. "This tariff prices nothing that happened in this period" is a finding the
        # account manager needs, and the empty state on the detail page is where it is made.
        messages.warning(request, f"{obj.number} calculated — this tariff priced nothing in "
                                  f"{obj.period_start} – {obj.period_end}.")
    else:
        note = " (line cap reached)" if result["truncated"] else ""
        messages.success(request, f"{obj.number} calculated — {result['lines_written']} derived "
                                  f"charges, {obj.total} total{note}.")
    return redirect("scm:clientbillingrun_detail", pk=pk)


@tenant_admin_required
@require_POST
def clientbillingrun_approve(request, pk):
    """``calculated → approved``. Tenant-admin gated (L27) — this is the signature on the numbers."""
    obj = get_object_or_404(ClientBillingRun.objects.select_related("client"),
                            pk=pk, tenant=request.tenant)
    try:
        obj.approve(user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:clientbillingrun_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {"action": "approve", "total": str(obj.total)})
    messages.success(request, f"{obj.number} approved — {obj.total}.")
    return redirect("scm:clientbillingrun_detail", pk=pk)


@tenant_admin_required
@require_POST
def clientbillingrun_draft_invoice(request, pk):
    """Draft an ``accounting.Invoice`` and link it. Tenant-admin gated (L27) — it moves money.

    A DRAFT only: SCM posts no ``JournalEntry`` and keeps no second AR ledger. Everything after this
    — sending, aging, tax, cash application, dunning — is Module 2's.
    """
    obj = get_object_or_404(
        ClientBillingRun.objects.select_related("client", "client__party", "client__currency",
                                                "client__payment_terms",
                                                "client__default_revenue_account",
                                                "rate_card", "rate_card__currency", "invoice"),
        pk=pk, tenant=request.tenant)
    try:
        invoice = obj.draft_invoice(user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:clientbillingrun_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "draft_invoice",
        "invoice": invoice.number,
        "invoice_subtotal": str(invoice.subtotal),
        "run_total": str(obj.total),
    })
    messages.success(request, f"Drafted invoice {invoice.number} for {obj.number} "
                              f"({invoice.total}). Send it from Accounts Receivable.")
    return redirect("scm:clientbillingrun_detail", pk=pk)


@login_required
@require_POST
def clientbillingrun_void(request, pk):
    """``draft`` / ``calculated`` → ``void``. An invoiced run is voided in accounting, not here."""
    obj = get_object_or_404(ClientBillingRun.objects.select_related("client", "invoice"),
                            pk=pk, tenant=request.tenant)
    try:
        obj.void(user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:clientbillingrun_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {"action": "void"})
    messages.warning(request, f"{obj.number} voided.")
    return redirect("scm:clientbillingrun_detail", pk=pk)


# ============================================================================ manual charge lines
def _line_or_404(request, pk):
    """One run line, scoped through its PARENT's tenant — the child carries none of its own."""
    return get_object_or_404(
        ClientBillingRunLine.objects.select_related("run", "run__client", "rate_card_line"),
        pk=pk, run__tenant=request.tenant)


@login_required
def clientbillingrunline_create(request, pk):
    """Add ONE manual charge to the run named by the ROUTE.

    Hand-rolled rather than ``crud_create``: the parent has to come from the URL (a parent pk in a
    POST body is how a caller grafts a charge onto another workspace's invoice), ``is_manual`` has to
    be FORCED rather than posted, and the parent's totals have to be recomputed in the same
    transaction as the insert. Hand-rolled means this path owes its own :func:`write_audit_log`.

    Context: ``form``, ``is_edit`` (always ``False``), ``run`` (the parent, this exact name — it
    drives the title, the breadcrumb and the cancel link).
    """
    if _need_tenant(request):
        return redirect("scm:clientbillingrun_list")
    run = get_object_or_404(ClientBillingRun.objects.select_related("client"),
                            pk=pk, tenant=request.tenant)
    if run.status not in EDITABLE_RUN_STATUSES:
        messages.error(request, f"A {run.get_status_display().lower()} run can no longer take new "
                                "charges.")
        return redirect("scm:clientbillingrun_detail", pk=run.pk)

    if request.method == "POST":
        form = ClientBillingRunLineForm(request.POST, tenant=request.tenant, run=run)
        if form.is_valid():
            with transaction.atomic():
                line = form.save(commit=False)
                # Restated here rather than trusted to the form's constructor: this view must not
                # depend on a form's __init__ for the column that decides which run owns the charge.
                line.run = run
                # FORCED, never posted. A user-settable flag would let somebody mark a DERIVED line
                # manual and freeze a wrong figure past every future recalculation.
                line.is_manual = True
                line.save()
                run.recalc_amounts()
            write_audit_log(request.user, line, "create", {
                "run": run.number,
                "charge_basis": line.charge_basis,
                "quantity": str(line.quantity),
                "rate": str(line.rate),
                "amount": str(line.amount),
            }, tenant=request.tenant)
            messages.success(request, f"Added {line.description} ({line.amount}) to {run.number}.")
            return redirect("scm:clientbillingrun_detail", pk=run.pk)
    else:
        form = ClientBillingRunLineForm(tenant=request.tenant, run=run)

    return render(request, "scm/3pl/clientbillingrunline/form.html",
                  {"form": form, "is_edit": False, "run": run})


@login_required
def clientbillingrunline_edit(request, pk):
    """Edit one charge line. The line's own pk; the tenant comes from its parent.

    A DERIVED line is editable here too, and deliberately: filling in the quantity on a
    ``needs_manual_quantity`` line is the whole reason those lines are written at all. The success
    message says plainly that a recalculation will regenerate a derived line, so nobody types a
    figure into one and expects it to survive.
    """
    line = _line_or_404(request, pk)
    run = line.run
    if run.status not in EDITABLE_RUN_STATUSES:
        messages.error(request, f"A {run.get_status_display().lower()} run's charges can no longer "
                                "be edited.")
        return redirect("scm:clientbillingrun_detail", pk=run.pk)

    if request.method == "POST":
        form = ClientBillingRunLineForm(request.POST, instance=line, tenant=request.tenant, run=run)
        if form.is_valid():
            with transaction.atomic():
                line = form.save()
                run.recalc_amounts()
            write_audit_log(request.user, line, "update", _changed(form), tenant=request.tenant)
            if line.is_manual:
                messages.success(request, f"Updated {line.description} ({line.amount}).")
            else:
                messages.success(request, f"Updated {line.description} ({line.amount}) — this is a "
                                          "derived charge, so recalculating the run will replace it.")
            return redirect("scm:clientbillingrun_detail", pk=run.pk)
    else:
        form = ClientBillingRunLineForm(instance=line, tenant=request.tenant, run=run)

    return render(request, "scm/3pl/clientbillingrunline/form.html",
                  {"form": form, "is_edit": True, "run": run, "obj": line})


@login_required
@require_POST
def clientbillingrunline_delete(request, pk):
    """POST-only. Removing a charge re-totals the run in the same transaction."""
    line = _line_or_404(request, pk)
    run = line.run
    if run.status not in EDITABLE_RUN_STATUSES:
        messages.error(request, f"A {run.get_status_display().lower()} run's charges can no longer "
                                "be deleted.")
        return redirect("scm:clientbillingrun_detail", pk=run.pk)

    description, amount = line.description, line.amount
    write_audit_log(request.user, line, "delete", {
        "run": run.number, "description": description, "amount": str(amount),
    }, tenant=request.tenant)
    with transaction.atomic():
        line.delete()
        run.recalc_amounts()
    messages.success(request, f"Removed {description} ({amount}) from {run.number}.")
    return redirect("scm:clientbillingrun_detail", pk=run.pk)
