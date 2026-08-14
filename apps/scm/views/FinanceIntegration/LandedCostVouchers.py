"""SCM 4.18 Finance & Accounting Integration — ``LandedCostVoucher`` views.

Twelve views: the CRUD five, the four-rung verb ladder (``allocate → accrue → draft bill``, plus
``cancel``), and three for the cost charges.

--------------------------------------------------------------------------------------------------
THREE RULES EVERY VERB IN THIS MODULE OBEYS
--------------------------------------------------------------------------------------------------

**1. Every verb is ``@require_POST``, so a GET to one is a 405 rather than a silent state change.**
``allocate`` rewrites what inventory is valued at and ``draft_bill`` raises an accounts-payable
document; a link-prefetcher or a crawler following a GET verb would be doing both.

**2. Every verb re-checks its own status guard HERE, in the view — via the model method it calls.**
The templates hide the buttons too, but hiding a button does not stop a direct POST. Each model
method raises ``ValidationError`` on a bad transition and each view catches it into
``messages.error``, so a stale tab is a friendly message and never a 500.

**3. Every verb writes its OWN** :func:`write_audit_log`. The ``crud_*`` helpers write one for you;
nothing else does, and a hand-rolled path that forgets it leaves the money trail with a gap exactly
where somebody would look for it.

All four verbs are ``@tenant_admin_required`` (L27) — every one of them moves money, either into
inventory valuation or into accounts payable. The detail template must therefore wrap all four
buttons in ``{% if request.user.is_superuser or request.user.is_tenant_admin %}``; showing a member a
button they will 403 on is the 4.11 finding. The ``can_*`` context keys below are the STATUS half
only, deliberately — folding the role in here would leave the page unable to tell "not ready yet"
apart from "not yours to press", and those two want different words on the screen.

The CHARGE views stay at ``@login_required``: adding a freight quote to a draft voucher is ordinary
clerical work, and a draft voucher's charges have not landed on anything yet.
"""
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

from apps.scm.models._base import ZERO, q2, q4
from apps.scm.models import LandedCostCharge, LandedCostVoucher

from apps.scm.forms import LandedCostChargeForm, LandedCostVoucherForm

#: The money column shape every Coalesce default on this page declares. Django needs an explicit
#: `output_field` when a `Value(Decimal)` is mixed with a `Sum` over a DecimalField.
_MONEY = DecimalField(max_digits=18, decimal_places=2)


def _party_qs(tenant):
    """The ``?party=`` dropdown — only parties that actually appear on a voucher.

    Narrowed to payees IN USE rather than the whole party book: a filter offering 400 customers, of
    whom three have ever been a landed-cost payee, is a filter nobody uses. `_carrier_parties` is the
    right set for the FORM (who you MAY choose); this is the right set for the FILTER (who you HAVE
    chosen).
    """
    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, scm_landed_cost_vouchers__tenant=tenant)
            .distinct().order_by("name", "id"))


# ============================================================================ CRUD
@login_required
def landedcostvoucher_list(request):
    """Every landed cost voucher in the workspace, newest cost date first.

    ``select_related`` covers every FK a row touches AND the chain ``__str__`` walks (``party.name``):
    a row renders the receipt number, the payee, the shipment, the currency and the linked bill, and
    the audit/message paths call ``str(voucher)``.
    """
    qs = (LandedCostVoucher.objects.filter(tenant=request.tenant)
          .select_related("goods_receipt", "party", "shipment", "currency", "bill"))

    # ONE aggregate() call, deliberately — this model is NOT the 4.17 `ClientBillingRun` case.
    # That model has to split its counts from its money because it carries a money column literally
    # named `total`, which the `total=Count("id")` alias shadows: inside a single `aggregate()`
    # Django resolves a name against the aliases declared in that same call first, so a
    # `Sum("total")` next to it computes over the COUNT and raises `FieldError`.
    # `LandedCostVoucher` has NO field named `total`, `draft`, `allocated`, `accrued`, `reconciled`
    # or `cancelled` — its money columns are `estimated_total` / `actual_total` / `allocated_total` /
    # `variance_amount` / `variance_pct` — and the two money aliases (`sum_actual`, `sum_variance`)
    # shadow nothing either, so no alias here can collide and the split bought only a second round
    # trip on every list page load. They are remapped onto the frozen `stats.actual_total` /
    # `stats.variance_total` template keys below.
    #
    # Stats are computed over the WHOLE workspace, never over the filtered page — a tile that moved
    # every time somebody typed in the search box would be a different number from the dashboard's.
    counts = LandedCostVoucher.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        draft=Count("id", filter=Q(status="draft")),
        allocated=Count("id", filter=Q(status="allocated")),
        accrued=Count("id", filter=Q(status="accrued")),
        reconciled=Count("id", filter=Q(status="reconciled")),
        cancelled=Count("id", filter=Q(status="cancelled")),
        sum_actual=Coalesce(Sum("actual_total"), Value(ZERO), output_field=_MONEY),
        sum_variance=Coalesce(Sum("variance_amount"), Value(ZERO), output_field=_MONEY),
    )
    stats = {**counts,
             "actual_total": counts["sum_actual"],
             "variance_total": counts["sum_variance"]}

    return crud_list(
        request, qs, "scm/finance/landedcostvoucher/list.html",
        search_fields=["number", "goods_receipt__number", "party__name", "notes"],
        # `party` is int-guarded (is_int=True) so `?party=abc`, `?party=²` and a 21-digit value all
        # SKIP the filter instead of raising out of .filter() (L11).
        filters=[("status", "status", False),
                 ("basis", "allocation_basis", False),
                 ("party", "party_id", True)],
        extra_context={
            "status_choices": LandedCostVoucher.STATUS_CHOICES,
            "basis_choices": LandedCostVoucher.ALLOCATION_BASIS_CHOICES,
            "charge_type_choices": LandedCostCharge.CHARGE_TYPE_CHOICES,
            "parties": _party_qs(request.tenant),
            "stats": stats,
        },
    )


@login_required
def landedcostvoucher_create(request):
    if _need_tenant(request):
        return redirect("scm:landedcostvoucher_list")
    return crud_create(
        request,
        form_class=LandedCostVoucherForm,
        template="scm/finance/landedcostvoucher/form.html",
        success_url="scm:landedcostvoucher_list",
    )


@login_required
def landedcostvoucher_detail(request, pk):
    """The voucher, its charges, its allocation, and the receipt moves it allocated over.

    Hand-rolled rather than ``crud_detail``: the page carries five panels and six gates, and every
    one of them has to be computed from the same objects the totals were computed from.
    """
    obj = get_object_or_404(
        LandedCostVoucher.objects.select_related(
            "goods_receipt", "goods_receipt__purchase_order", "party", "shipment",
            "trade_document", "currency", "bill", "bill__party"),
        pk=pk, tenant=request.tenant)

    # Every FK a charge row renders, in one query rather than four per row (the 4.13 asset_list
    # finding). `party` and `tax_code` are additionally read by `split_charges()` and the bill
    # preview below, so fetching them here pays for itself twice.
    charges = list(obj.charges.select_related("party", "freight_invoice", "gl_account",
                                              "tax_code").all())
    billable, excluded = obj.split_charges(charges)

    # NOT capped, deliberately: an allocation set is bounded by (receipt moves × capitalising
    # charges), i.e. by the size of the receipt itself, and `allocation_groups` needs the actual rows
    # to build its per-item `rows` list. Cap this the day a receipt with hundreds of lines meets a
    # voucher with a dozen charges — and cap the GROUPS with a DB aggregate when you do, not the rows.
    allocations = list(obj.allocations
                       .select_related("item", "stock_move", "stock_move__location", "charge")
                       .all())

    # The allocation BASE, re-read rather than inferred from the allocations: a voucher that has
    # never been allocated still has to show what it WOULD allocate over, and a voucher whose receipt
    # has posted nothing has to show the empty state that explains why the button will refuse.
    receipt_moves = list(obj.receipt_moves().select_related("item", "location"))

    return render(request, "scm/finance/landedcostvoucher/detail.html", {
        "obj": obj,
        "charges": charges,
        "charge_count": len(charges),
        "allocations": allocations,
        "allocation_groups": _allocation_groups(allocations),
        "allocation_count": len(allocations),
        "receipt_moves": receipt_moves,
        "receipt_move_count": len(receipt_moves),
        "billable_charges": billable,
        "billable_total": q2(sum((c.allocatable_amount for c in billable), ZERO)),
        "excluded_charges": excluded,
        "excluded_total": q2(sum((c.allocatable_amount for c in excluded), ZERO)),
        "bill": obj.bill,
        "grn": obj.goods_receipt,
        # Each gate mirrors EXACTLY what its view (via its model method) refuses, so a button the
        # page shows is a button that works and a button it hides is one that would have been
        # rejected. STATUS half only — see the module docstring on the permission half.
        "can_edit": obj.is_editable,
        "can_delete": obj.is_editable,
        "can_add_charge": obj.is_editable,
        "can_allocate": obj.status in ("draft", "allocated", "accrued") and obj.bill_id is None,
        "can_accrue": obj.status == "allocated",
        # Mirrors the relaxed `draft_bill()` guard: a DRAFT voucher on which nothing capitalises can
        # be billed without being allocated first, because `allocate()` refuses exactly that voucher
        # and the pair would otherwise be a dead end for a purely-recoverable (import VAT) or
        # purely-expensed voucher. It still needs something to bill to this payee — `billable` is
        # empty when every charge names a different vendor, which `draft_bill()` also refuses.
        # Computed off the already-fetched `charges` list, so the extra rung costs no query.
        "can_draft_bill": obj.bill_id is None and (
            obj.status in ("allocated", "accrued")
            or (obj.status == "draft" and bool(billable)
                and not any(charge.capitalises and charge.allocatable_amount > ZERO
                            for charge in charges))),
        "can_cancel": obj.status != "cancelled" and obj.bill_id is None,
    })


def _allocation_groups(allocations):
    """The flat allocation rows folded per ITEM — what the page is actually read for.

    A voucher with six charges over twelve receipt lines writes seventy-two rows; nobody reads those.
    What a stock controller needs is "this SKU picked up 3.41 per unit", which is this. The uplift is
    RE-DERIVED from the group's summed amount and quantity rather than summed from the rows' own
    per-row uplifts: summing already-rounded 4dp figures across six charges drifts from the honest
    ratio, and the honest ratio is the number that has to agree with ``Item.average_cost``.

    ``basis_used`` is the group's basis where every row agrees and ``"mixed"`` where they do not —
    two charges on one voucher may legitimately have allocated on different bases (one by weight, one
    that fell back to quantity), and averaging that away would hide the fallback the row exists to
    disclose.
    """
    groups, seen_moves = {}, {}
    for row in allocations:
        group = groups.get(row.item_id)
        if group is None:
            group = groups[row.item_id] = {
                "item": row.item,
                "quantity": ZERO,
                "allocated_amount": ZERO,
                "unit_cost_uplift": ZERO,
                "basis_used": row.basis_used,
                "rows": [],
            }
            seen_moves[row.item_id] = set()
        # Quantity is the MOVE's quantity, repeated once per charge on the same move — counted once
        # per (item, stock move) pair, or a six-charge voucher would report six times the units. A
        # SET rather than a scan over `rows`: that scan is O(charges) per row and therefore
        # O(charges²) per item, on a page whose whole job is to be cheap to open.
        if row.stock_move_id not in seen_moves[row.item_id]:
            seen_moves[row.item_id].add(row.stock_move_id)
            group["quantity"] += row.quantity or ZERO
        group["allocated_amount"] += row.allocated_amount or ZERO
        if group["basis_used"] != row.basis_used:
            group["basis_used"] = "mixed"
        group["rows"].append(row)

    ordered = []
    for group in groups.values():
        quantity = group["quantity"]
        group["quantity"] = q4(quantity)
        group["allocated_amount"] = q2(group["allocated_amount"])
        # `None`, NOT `ZERO`, when there is no quantity to divide by: "this group was not allocated
        # per unit" and "this group picked up nothing per unit" are different facts, and the detail
        # page tests `{% if group.unit_cost_uplift is not None %}` on both the badge and the column.
        # With `ZERO` its `{% else %}—{% endif %}` branch was dead code and a zero-quantity group
        # rendered the misleading badge "+0.0000 per unit". Matches the identical `uplift_per_unit`
        # treatment in `views/FinanceIntegration/Reports.py`.
        group["unit_cost_uplift"] = (q4(group["allocated_amount"] / quantity)
                                     if quantity else None)
        ordered.append(group)
    # By SKU, so the panel reads in the same order as the item list and the receipt.
    ordered.sort(key=lambda group: (group["item"].sku if group["item"] else "", group["item"].pk
                                    if group["item"] else 0))
    return ordered


@login_required
def landedcostvoucher_edit(request, pk):
    """Editable only while the voucher is a DRAFT with no bill behind it.

    The guard is here rather than only in the template because changing the receipt, the payee or the
    basis under an already-allocated voucher would silently restate what inventory is carrying,
    without reversing the roll that put it there.
    """
    obj = get_object_or_404(LandedCostVoucher.objects.select_related("party", "bill"),
                            pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        if obj.bill_id is not None:
            messages.error(request, "This voucher has been billed and can no longer be edited — "
                                    "void the bill in Accounting first.")
        else:
            messages.error(request, f"A {obj.get_status_display().lower()} voucher can no longer be "
                                    "edited. Cancel it to reverse the allocation.")
        return redirect("scm:landedcostvoucher_detail", pk=pk)
    return crud_edit(
        request,
        model=LandedCostVoucher,
        pk=pk,
        form_class=LandedCostVoucherForm,
        template="scm/finance/landedcostvoucher/form.html",
        success_url=reverse("scm:landedcostvoucher_detail", args=[pk]),
    )


@login_required
@require_POST
def landedcostvoucher_delete(request, pk):
    """POST-only, and only a DRAFT voucher with no bill.

    Anything past draft has rolled cost into ``Item.average_cost``; deleting it would cascade the
    allocation rows away and leave that uplift in every affected item with nothing left to explain
    it. ``cancel`` is the route out of an allocated voucher, because cancel REVERSES first.
    """
    obj = get_object_or_404(LandedCostVoucher.objects.select_related("bill"),
                            pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        if obj.bill_id is not None:
            messages.error(request, "This voucher has been billed and can't be deleted — void the "
                                    "bill in Accounting instead.")
        else:
            messages.error(request, f"A {obj.get_status_display().lower()} voucher has landed cost "
                                    "on stock and can't be deleted. Cancel it instead — that "
                                    "reverses the allocation before it closes the voucher.")
        return redirect("scm:landedcostvoucher_detail", pk=pk)
    return crud_delete(request, model=LandedCostVoucher, pk=pk,
                       success_url="scm:landedcostvoucher_list")


# ============================================================================ the verb ladder
@tenant_admin_required
@require_POST
def landedcostvoucher_allocate(request, pk):
    """Push the capitalising charges onto the receipt's units. Tenant-admin gated (L27).

    Safe to press twice: ``allocate()`` reverses its own previous roll first, inside the same
    transaction. The success message names the row count, the amount and any basis fallback that
    fired — a voucher asked to allocate by weight that silently allocated by quantity because no item
    carries a weight is the one outcome here that looks right and is not what was asked for.
    """
    obj = get_object_or_404(
        LandedCostVoucher.objects.select_related("goods_receipt", "party", "bill"),
        pk=pk, tenant=request.tenant)
    try:
        result = obj.allocate()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:landedcostvoucher_detail", pk=pk)

    fallback = ", ".join(result["fallbacks"])
    write_audit_log(request.user, obj, "update", {
        "action": "allocate",
        "rows": result["rows"],
        "amount": str(result["amount"]),
        "charges": result["charges"],
        "basis_fallback": fallback,
    })
    note = f" Basis fell back: {fallback}." if fallback else ""
    messages.success(request, f"{obj.number} allocated — {result['amount']} across "
                              f"{result['rows']} lines from {result['charges']} charges.{note}")
    return redirect("scm:landedcostvoucher_detail", pk=pk)


@tenant_admin_required
@require_POST
def landedcostvoucher_accrue(request, pk):
    """``allocated → accrued``. Records cost in stock that is not yet in accounts payable.

    Posts NO ``JournalEntry`` — the accrual journal is Module 2's (L29). What this stamps is the fact
    the payables report reads to show a landed cost voucher with no bill behind it.
    """
    obj = get_object_or_404(LandedCostVoucher.objects.select_related("party"),
                            pk=pk, tenant=request.tenant)
    try:
        obj.accrue()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:landedcostvoucher_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "accrue", "amount": str(obj.actual_total)})
    messages.success(request, f"{obj.number} accrued — {obj.actual_total} is in stock and awaiting "
                              "the vendor bill.")
    return redirect("scm:landedcostvoucher_detail", pk=pk)


@tenant_admin_required
@require_POST
def landedcostvoucher_draft_bill(request, pk):
    """Draft an ``accounting.Bill`` for the payee and link it. Tenant-admin gated (L27).

    A DRAFT only: SCM posts no ``JournalEntry`` and opens no second AP ledger. Approving, paying and
    posting are Module 2's. Idempotent — pressing the button twice reports the existing bill rather
    than raising a duplicate vendor bill, which is the expensive mistake on this page.
    """
    obj = get_object_or_404(
        LandedCostVoucher.objects.select_related("goods_receipt", "party", "currency", "bill"),
        pk=pk, tenant=request.tenant)

    if obj.bill_id is not None:
        # Early return BEFORE calling the model, so nothing is written and no audit row claims a
        # draft that did not happen.
        messages.info(request, f"{obj.number} is already billed as {obj.bill.number}. Open it in "
                               "Accounts Payable to approve or pay it.")
        return redirect("scm:landedcostvoucher_detail", pk=pk)

    # Read the split BEFORE drafting: the charges do not change, and the count has to be reportable
    # whether the draft succeeds or is refused.
    _billable, excluded = obj.split_charges()
    try:
        bill = obj.draft_bill()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:landedcostvoucher_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "draft_bill",
        "bill": bill.number,
        "bill_subtotal": str(bill.subtotal),
        "excluded_charges": len(excluded),
    })
    note = (f" {len(excluded)} charge(s) naming a different vendor were excluded."
            if excluded else "")
    messages.success(request, f"Drafted bill {bill.number} for {obj.number} ({bill.total}). "
                              f"Approve it in Accounts Payable.{note}")
    return redirect("scm:landedcostvoucher_detail", pk=pk)


@tenant_admin_required
@require_POST
def landedcostvoucher_cancel(request, pk):
    """Reverse the allocation and close the voucher. Refused once a bill exists.

    Tenant-admin gated with the rest of the ladder (L27): this UNWINDS an inventory valuation, which
    is the same money moving in the other direction.
    """
    obj = get_object_or_404(LandedCostVoucher.objects.select_related("party", "bill"),
                            pk=pk, tenant=request.tenant)
    reversed_amount = obj.allocated_total
    try:
        obj.cancel()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:landedcostvoucher_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "cancel", "reversed_amount": str(reversed_amount)})
    if reversed_amount:
        messages.warning(request, f"{obj.number} cancelled — {reversed_amount} of landed cost was "
                                  "rolled back out of the affected items.")
    else:
        messages.warning(request, f"{obj.number} cancelled.")
    return redirect("scm:landedcostvoucher_detail", pk=pk)


# ============================================================================ cost charges
def _charge_or_404(request, pk):
    """One cost charge, scoped through its PARENT's tenant — the child carries none of its own."""
    return get_object_or_404(
        LandedCostCharge.objects.select_related("voucher", "voucher__party", "party",
                                                "freight_invoice", "gl_account", "tax_code"),
        pk=pk, voucher__tenant=request.tenant)


@login_required
def landedcostcharge_create(request, pk):
    """Add ONE cost charge to the voucher named by the ROUTE.

    Hand-rolled rather than ``crud_create``: the parent has to come from the URL (a parent pk in a
    POST body is how a caller grafts a charge onto another workspace's voucher), and the parent's
    totals have to be recomputed in the same transaction as the insert. Hand-rolled means this path
    owes its own :func:`write_audit_log`.

    Context: ``form``, ``is_edit`` (always ``False``), ``voucher`` (the parent, this exact name — it
    drives the title, the breadcrumb and the cancel link).
    """
    if _need_tenant(request):
        return redirect("scm:landedcostvoucher_list")
    voucher = get_object_or_404(
        LandedCostVoucher.objects.select_related("party", "goods_receipt", "bill"),
        pk=pk, tenant=request.tenant)
    if not voucher.is_editable:
        messages.error(request, f"A {voucher.get_status_display().lower()} voucher can no longer "
                                "take new charges — its costs are already in stock.")
        return redirect("scm:landedcostvoucher_detail", pk=voucher.pk)

    if request.method == "POST":
        form = LandedCostChargeForm(request.POST, tenant=request.tenant, voucher=voucher)
        if form.is_valid():
            with transaction.atomic():
                charge = form.save(commit=False)
                # Restated here rather than trusted to the form's constructor: this view must not
                # depend on a form's __init__ for the column that decides which voucher owns it.
                charge.voucher = voucher
                charge.save()
                voucher.recalc_totals()
            write_audit_log(request.user, charge, "create", {
                "voucher": voucher.number,
                "charge_type": charge.charge_type,
                "estimated_amount": str(charge.estimated_amount),
                "actual_amount": str(charge.actual_amount),
                "capitalises": charge.capitalises,
            }, tenant=request.tenant)
            messages.success(request, f"Added {charge.get_charge_type_display()} "
                                      f"({charge.allocatable_amount}) to {voucher.number}.")
            return redirect("scm:landedcostvoucher_detail", pk=voucher.pk)
    else:
        form = LandedCostChargeForm(tenant=request.tenant, voucher=voucher)

    return render(request, "scm/finance/landedcostcharge/form.html",
                  {"form": form, "is_edit": False, "voucher": voucher})


@login_required
def landedcostcharge_edit(request, pk):
    """Edit one cost charge. The charge's own pk; the tenant comes from its parent voucher."""
    charge = _charge_or_404(request, pk)
    voucher = charge.voucher
    if not voucher.is_editable:
        messages.error(request, f"A {voucher.get_status_display().lower()} voucher's charges can no "
                                "longer be edited — its costs are already in stock.")
        return redirect("scm:landedcostvoucher_detail", pk=voucher.pk)

    if request.method == "POST":
        form = LandedCostChargeForm(request.POST, instance=charge, tenant=request.tenant,
                                    voucher=voucher)
        if form.is_valid():
            with transaction.atomic():
                charge = form.save()
                voucher.recalc_totals()
            write_audit_log(request.user, charge, "update", _changed(form), tenant=request.tenant)
            messages.success(request, f"Updated {charge.get_charge_type_display()} "
                                      f"({charge.allocatable_amount}).")
            return redirect("scm:landedcostvoucher_detail", pk=voucher.pk)
    else:
        form = LandedCostChargeForm(instance=charge, tenant=request.tenant, voucher=voucher)

    return render(request, "scm/finance/landedcostcharge/form.html",
                  {"form": form, "is_edit": True, "voucher": voucher, "obj": charge})


@login_required
@require_POST
def landedcostcharge_delete(request, pk):
    """POST-only. Removing a charge re-totals the voucher in the same transaction."""
    charge = _charge_or_404(request, pk)
    voucher = charge.voucher
    if not voucher.is_editable:
        messages.error(request, f"A {voucher.get_status_display().lower()} voucher's charges can no "
                                "longer be deleted — its costs are already in stock.")
        return redirect("scm:landedcostvoucher_detail", pk=voucher.pk)

    # The audit row is written INSIDE the atomic block, like its sibling `clientbillingrunline_delete`.
    # Written before the `with`, a failure in `charge.delete()` or `recalc_totals()` would roll the
    # delete back and leave an immutable AuditLog row claiming a cost line was removed — a false
    # entry in the money trail, which is worse than a missing one. It still precedes the delete
    # itself so it can read the charge's own fields without re-querying a row on its way out.
    label, amount = charge.get_charge_type_display(), charge.allocatable_amount
    with transaction.atomic():
        write_audit_log(request.user, charge, "delete", {
            "voucher": voucher.number, "charge_type": charge.charge_type, "amount": str(amount),
        }, tenant=request.tenant)
        charge.delete()
        voucher.recalc_totals()
    messages.success(request, f"Removed {label} ({amount}) from {voucher.number}.")
    return redirect("scm:landedcostvoucher_detail", pk=voucher.pk)
