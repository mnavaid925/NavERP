"""Sales 8.6 — the order hold workbench: 5 CRUD views + 7 POST actions.

This turns SCM 4.5's two hold columns into a queue of records a person can work: what is
held, why, against which order, who owns it, and — the whole point — the **frozen**
evaluation snapshot that proves why the machine said no on the day it said it.

Ownership (L36/L37) is the constraint everything else follows from. ``scm.SalesOrder``
belongs to SCM 4.5. This file:

* reads the order through an FK and never declares, constructs or duplicates it;
* writes back ONLY ``credit_hold`` and ``hold_reason`` — both ``editable=False`` on 4.5's
  side, and never ``status``. 4.5's own status machine stays 4.5's;
* **delegates** the submit to 4.5's ``salesorder_submit`` rather than re-implementing it, so
  the credit/fraud evaluation is re-run by the code that owns it (a blind ``status`` write
  here would skip the unmapped-line guard and silently re-open a hole 4.5 closed);
* leaves ``salesorder_release_hold`` as the release verb for 4.5's OWN credit/fraud hold.

Four rules govern every view here:

* **Tenant scope, always.** ``filter(tenant=request.tenant)``, never ``.objects.all()``. The
  tenantless superuser therefore sees empty lists BY DESIGN, and every action verb 404s on
  another workspace's hold.
* **Junk in, ignored out (L11).** ``?hold_type=nonsense`` narrows nothing rather than
  raising, and ``?sales_order=`` / a bulk id list go through ``as_db_int`` so a 40-digit
  value is skipped instead of overflowing the driver.
* **No GET may mutate.** Every action verb is ``@require_POST`` + CSRF.
* **Audit on every mutation.** ``write_audit_log`` is POSITIONAL —
  ``(user, obj, action, changes, tenant)`` — and the instance is the SECOND argument.

The **checkout** is the concurrency control and is treated as exclusive throughout: a hold
checked out by somebody else cannot be cleared or re-checked-out, and only the holder or a
tenant admin may release a checkout (an override, recorded in ``clear_note``).
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.OrderManagement.OrderHolds import OrderHoldActionForm, OrderHoldForm
from apps.sales.models.OrderManagement.OrderHolds import OrderHold, build_evaluation_snapshot
from apps.sales.models.OrderManagement.OrderValidationRules import OrderValidationRule
from apps.sales.views._common import *  # noqa: F401,F403  (login_required, get_object_or_404, ...)


LIST_TEMPLATE = "sales/ordermanagement/orderhold/list.html"
DETAIL_TEMPLATE = "sales/ordermanagement/orderhold/detail.html"
FORM_TEMPLATE = "sales/ordermanagement/orderhold/form.html"

#: Rows per page. Matches the shared pagination partial's expectation of ``page_obj``.
PAGE_SIZE = 15

#: The ``?checked_out=`` chip. Any value outside this set is ignored (L11) rather than
#: treated as "no", which would silently hide every checked-out hold in the register.
CHECKED_OUT_CHOICES = [("", "All"), ("yes", "Checked Out"), ("no", "Not Checked Out")]

#: A rule whose type is a credit gate raises a CREDIT hold; every other rule is a plain
#: validation failure. Kept as data so the mapping is one line to read, not a chain of
#: ``if`` inside the raise loop.
RULE_HOLD_TYPES = {"credit_limit": "credit"}


def _is_tenant_admin(user):
    """The same predicate ``@tenant_admin_required`` enforces, for the override checks.

    The decorator is the access control; this is the honesty of an in-template guard and the
    override case of the release verb, which must ask "may this user take somebody else's
    checkout?" rather than assume nobody ever does.
    """
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def _hold_queryset(request):
    """The tenant-scoped hold register. One place, so no view can forget the filter."""
    return (
        OrderHold.objects.filter(tenant=request.tenant)
        .select_related("sales_order", "rule", "party", "raised_by", "checked_out_by", "cleared_by")
    )


def _form_context(form, is_edit, obj=None):
    """The form view's context. ``obj`` is pinned on BOTH create and edit — ``None`` on
    create — so the shared form template never has to branch on which one it got."""
    return {"form": form, "obj": obj, "is_edit": is_edit}


def _other_open_holds_page(request, hold):
    """The other OPEN holds on the same order, as a Page of 15.

    An order can carry several holds at once (a credit gate AND a fraud review). Clearing
    one of them must not look like the order is free to ship, so the detail page shows the
    rest — which is also why the release verbs re-check for a remaining open hold rather
    than trusting this count.
    """
    queryset = (
        OrderHold.objects.filter(
            tenant=request.tenant,
            sales_order_id=hold.sales_order_id,
            status=OrderHold.OPEN_STATUS,
        )
        .exclude(pk=hold.pk)
        .select_related("rule", "checked_out_by")
    )
    return paginate(request, queryset, PAGE_SIZE)


def _tenant_sales_orders(request):
    """The order dropdown for the filters and the form. Read-only over SCM 4.5's table."""
    from apps.scm.models import SalesOrder

    return SalesOrder.objects.filter(tenant=request.tenant).select_related("customer").order_by(
        "-order_date", "-id"
    )


def _write_back_hold(order, reason):
    """Mark the ORDER held. The only two fields 8.6 ever writes on ``scm.SalesOrder``.

    ``status`` is deliberately NOT written: 4.5 owns that machine, and an order whose
    ``credit_hold`` is set while it sits in ``draft`` is exactly the state 4.5's own submit
    re-evaluates. ``updated_at`` rides along because it is ``auto_now`` and a partial save
    that omits it leaves a row that claims to be fresher than it is.
    """
    order.credit_hold = True
    order.hold_reason = reason
    order.save(update_fields=["credit_hold", "hold_reason", "updated_at"])


def _release_order_hold_flags(order):
    """Clear the order's hold flags — called ONLY when no open hold remains.

    A blind release here would be the bug this whole module is written to avoid: clearing
    one of three holds must not tell the order it is free to ship.
    """
    if not order.credit_hold and not order.hold_reason:
        return False
    order.credit_hold = False
    order.hold_reason = ""
    order.save(update_fields=["credit_hold", "hold_reason", "updated_at"])
    return True


def _open_holds_remaining(hold):
    """How many OTHER open holds this order still carries."""
    return (
        OrderHold.objects.filter(
            tenant=hold.tenant,
            sales_order_id=hold.sales_order_id,
            status=OrderHold.OPEN_STATUS,
        )
        .exclude(pk=hold.pk)
        .count()
    )


def _has_unmapped_lines(order):
    """True when a line still has no stock item — 4.5's own submit guard, restated.

    Mirrors ``scm.views.salesorder_submit``: allocation, picking and every on-hand check key
    off the item, so a quote-converted line with no item is an order nobody can fulfil. The
    clear-and-submit verb checks it BEFORE delegating, so the user gets 8.6's message rather
    than a round trip through 4.5.
    """
    return any(line.item_id is None for line in order.lines.all())



def _evaluate_order(request, order):
    """Run every ACTIVE, in-force rule against ``order`` → ``(created, warnings)``.

    One hold per non-``warn`` finding; ``warn`` findings produce a message and no row,
    because a rule that says "watch this" must not block an order or pad the board.

    Each hold carries a FROZEN snapshot built from the finding it came from, and its
    ``severity`` is COPIED from the rule — so a rule re-tuned next month cannot rewrite the
    record of why this order was held today.

    An order that already carries an OPEN hold from the same rule is reported and skipped
    rather than stacked: re-running the raise must not bury the real, still-open hold under
    a duplicate of itself, and the existing hold is the one whose snapshot is still true.
    """
    created, warnings, skipped = [], [], []
    rules = OrderValidationRule.objects.filter(tenant=request.tenant, is_active=True)
    already_open = set(
        OrderHold.objects.filter(
            tenant=request.tenant,
            sales_order=order,
            status=OrderHold.OPEN_STATUS,
        ).exclude(rule__isnull=True).values_list("rule_id", flat=True)
    )
    for rule in rules:
        if not rule.runs_on("submit"):
            continue
        findings, _blocks = rule.evaluate(order)
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            message = str(finding.get("message") or rule.name or "Validation rule fired.")
            if finding.get("severity") == "warn":
                warnings.append(f"{rule.number or rule.name}: {message}")
                continue
            if rule.pk in already_open:
                skipped.append(f"{rule.number or rule.name} already holds this order.")
                continue
            hold = OrderHold(
                tenant=request.tenant,
                sales_order=order,
                rule=rule,
                party=order.customer,
                hold_type=RULE_HOLD_TYPES.get(rule.rule_type, "validation"),
                reason=message,
                # COPIED, not referenced: what this hold was, on the day it was raised.
                severity=finding.get("severity") or rule.severity,
                evaluation_snapshot=build_evaluation_snapshot(
                    rule,
                    [finding],
                    order=order,
                    hold_type=RULE_HOLD_TYPES.get(rule.rule_type, "validation"),
                    actor=request.user,
                ),
                raised_at=timezone.now(),
                raised_by=request.user,
            )
            hold.save()
            created.append(hold)
            write_audit_log(
                request.user,
                hold,
                "create",
                {
                    "action": "raise_order_hold",
                    "number": hold.number,
                    "sales_order": order.number,
                    "rule": rule.number,
                    "hold_type": hold.hold_type,
                    "severity": hold.severity,
                },
                tenant=request.tenant,
            )
    return created, warnings, skipped


def _apply_holds_to_order(request, order, created):
    """Write ``credit_hold`` / ``hold_reason`` back on the order once holds exist.

    One write, listing every reason raised, rather than one write per hold — the order has
    a single pair of columns, so N holds must produce one coherent reason, not whichever
    happened to be saved last.
    """
    if not created:
        return
    reason = " · ".join(hold.reason for hold in created)
    _write_back_hold(order, reason)
    write_audit_log(
        request.user,
        order,
        "update",
        {"action": "hold_applied", "order": order.number, "holds": [h.number for h in created]},
        tenant=request.tenant,
    )


def _posted_ids(request, field):
    """A POSTed list of pks as ints — ``field=a&field=b`` or ``field=1,2,3``.

    Every value goes through ``as_db_int`` (L11), so ``order_ids=abc``, ``order_ids=²`` and a
    40-digit value are skipped rather than raised on. A bulk verb that 500s on a crafted
    form is a bulk verb nobody can use.
    """
    raw = list(request.POST.getlist(field))
    single = request.POST.get(field)
    if single:
        raw.extend(part for part in single.split(","))
    seen, ids = set(), []
    for value in raw:
        number = as_db_int(value)
        if number and number not in seen:
            seen.add(number)
            ids.append(number)
    return ids



@login_required
@tenant_admin_required
def order_hold_list(request):
    base_queryset = OrderHold.objects.filter(tenant=request.tenant)
    queryset = _hold_queryset(request)

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(reason__icontains=q)
            | Q(sales_order__number__icontains=q)
        )

    hold_type = request.GET.get("hold_type", "").strip()
    if hold_type in dict(OrderHold.HOLD_TYPE_CHOICES):
        queryset = queryset.filter(hold_type=hold_type)
    else:
        hold_type = ""

    status = request.GET.get("status", "").strip()
    if status in dict(OrderHold.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""

    severity = request.GET.get("severity", "").strip()
    if severity in dict(OrderHold.SEVERITY_CHOICES):
        queryset = queryset.filter(severity=severity)
    else:
        severity = ""

    # A FK filter is trusted only after as_db_int: ``?sales_order=abc`` and a 40-digit value
    # are skipped rather than raised on. Zero is skipped too — it is not a pk, and filtering
    # on it returns an empty page that reads as "this workspace has no holds", which is a lie.
    sales_order_filter = request.GET.get("sales_order", "").strip()
    sales_order_pk = as_db_int(sales_order_filter)
    if sales_order_pk:
        queryset = queryset.filter(sales_order_id=sales_order_pk)
    else:
        sales_order_filter = ""

    party_filter = request.GET.get("party", "").strip()
    party_pk = as_db_int(party_filter)
    if party_pk:
        queryset = queryset.filter(party_id=party_pk)
    else:
        party_filter = ""

    # The checkout chip is SCOPED TO OPEN HOLDS. A cleared hold keeps its checkout stamps as
    # history, and counting those would report a full board of work that is already done.
    checked_out = request.GET.get("checked_out", "").strip().lower()
    if checked_out in ("yes", "no"):
        queryset = queryset.filter(status=OrderHold.OPEN_STATUS)
        if checked_out == "yes":
            queryset = queryset.exclude(checked_out_by__isnull=True)
        else:
            queryset = queryset.filter(checked_out_by__isnull=True)
    else:
        checked_out = ""

    # Filters are read BEFORE pagination, so the page count reflects what is on screen.
    page_obj = paginate(request, queryset, PAGE_SIZE)

    # Stats describe the WHOLE tenant register, not the filtered page — a stats strip that
    # changes when you search is a stats strip nobody trusts. Counts, one grouped query.
    stats = base_queryset.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=OrderHold.OPEN_STATUS)),
        checked_out=Count(
            "id",
            filter=Q(status=OrderHold.OPEN_STATUS, checked_out_by__isnull=False),
        ),
        cleared=Count("id", filter=Q(status="cleared")),
    )

    return render(request, LIST_TEMPLATE, {
        "holds": page_obj,
        # The shared pagination partial reads ``page_obj``; it is an ALIAS of the very same
        # Page, never a second paginator run over the same queryset.
        "page_obj": page_obj,
        "q": q,
        "hold_type": hold_type,
        "status": status,
        "severity": severity,
        "sales_order": sales_order_filter,
        "party": party_filter,
        "checked_out": checked_out,
        "hold_type_choices": OrderHold.HOLD_TYPE_CHOICES,
        "status_choices": OrderHold.STATUS_CHOICES,
        "severity_choices": OrderHold.SEVERITY_CHOICES,
        "checked_out_choices": CHECKED_OUT_CHOICES,
        "sales_orders": _tenant_sales_orders(request),
        "parties": Party.objects.filter(tenant=request.tenant).order_by("name"),
        "stats": stats,
    })



@login_required
@tenant_admin_required
def order_hold_create(request):
    """Place a hold BY HAND.

    A hand-placed hold still gets a server-generated snapshot — of the order, the placer and
    the moment — with no rule and no findings. That is what keeps the board honest: a manual
    hold is visibly manual, rather than indistinguishable from an automatic one.
    """
    if request.method == "POST":
        form = OrderHoldForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            hold = form.save(commit=False)
            hold.tenant = request.tenant
            order = hold.sales_order
            hold.raised_at = timezone.now()
            hold.raised_by = request.user
            hold.severity = "hold"
            hold.status = OrderHold.OPEN_STATUS
            hold.evaluation_snapshot = build_evaluation_snapshot(
                None, [], order=order, hold_type=hold.hold_type, actor=request.user,
            )
            # A hold placed by hand without naming a customer follows the order's own.
            if hold.party_id is None and order is not None:
                hold.party = order.customer
            hold.save()
            _write_back_hold(order, hold.reason)
            write_audit_log(
                request.user,
                hold,
                "create",
                {
                    "action": "create_order_hold",
                    "number": hold.number,
                    "sales_order": order.number if order else "",
                    "hold_type": hold.hold_type,
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Hold {hold.number} placed on order {order.number}.")
            return redirect("sales:order_hold_detail", pk=hold.pk)
    else:
        form = OrderHoldForm(tenant=request.tenant)
    return render(request, FORM_TEMPLATE, _form_context(form, False, None))


@login_required
@tenant_admin_required
def order_hold_detail(request, pk):
    hold = get_object_or_404(_hold_queryset(request), pk=pk)
    page_obj = _other_open_holds_page(request, hold)
    return render(request, DETAIL_TEMPLATE, {
        "hold": hold,
        # The PARSED dict, never the raw column: a malformed blob degrades to an empty panel
        # via parsed_snapshot rather than rendering a JSON string into the page (or 500ing
        # the one page whose whole job is to explain a decision).
        "evaluation": hold.parsed_snapshot,
        "order": hold.sales_order,
        "open_holds": page_obj,
        # ALIAS of the other-open-holds Page for the shared pagination partial. On this page
        # that is the only paginated collection, so the two cannot drift apart.
        "page_obj": page_obj,
    })


@login_required
@tenant_admin_required
def order_hold_edit(request, pk):
    """Edit the two things a person may change: the reason, and the justification note.

    The lifecycle is NOT editable here. ``status``, ``severity``, the snapshot and every
    action stamp are workflow-governed, and an edit form that could flip a cleared hold back
    to open would make the audit trail a suggestion.
    """
    hold = get_object_or_404(_hold_queryset(request), pk=pk)
    if request.method == "POST":
        form = OrderHoldForm(request.POST, instance=hold, tenant=request.tenant)
        if form.is_valid():
            hold = form.save()
            write_audit_log(
                request.user,
                hold,
                "update",
                {
                    "action": "update_order_hold",
                    "number": hold.number,
                    "hold_type": hold.hold_type,
                    "changed": sorted(form.changed_data),
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Hold {hold.number} updated.")
            return redirect("sales:order_hold_detail", pk=hold.pk)
    else:
        form = OrderHoldForm(instance=hold, tenant=request.tenant)
    return render(request, FORM_TEMPLATE, _form_context(form, True, hold))


@require_POST
@login_required
@tenant_admin_required
def order_hold_delete(request, pk):
    """Delete a hold outright — refused while it is still holding an order.

    Deleting an OPEN hold would quietly release the order behind everyone's back, which is
    precisely the un-audited release this model exists to prevent. Clear it, with a reason,
    and the record of it survives.
    """
    hold = get_object_or_404(_hold_queryset(request), pk=pk)
    if hold.is_open:
        messages.error(
            request,
            f"Hold {hold.number} is still holding order {hold.sales_order.number}. "
            "Clear it with a reason instead — a hold cannot be deleted out from under an order.",
        )
        return redirect("sales:order_hold_detail", pk=hold.pk)
    number = hold.number
    # The number is captured BEFORE the row goes, because after ``delete()`` there is no pk
    # left to stamp the audit row with.
    write_audit_log(
        request.user,
        hold,
        "delete",
        {
            "action": "delete_order_hold",
            "number": number,
            "sales_order": hold.sales_order.number if hold.sales_order_id else "",
        },
        tenant=request.tenant,
    )
    hold.delete()
    messages.success(request, f"Hold {number} deleted.")
    return redirect("sales:order_hold_list")



@require_POST
@login_required
@tenant_admin_required
def order_hold_checkout(request, pk):
    """Claim the hold. EXCLUSIVE: one user at a time.

    Two clerks working the same hold is how a customer gets told "it was released" by two
    people with two different stories. Re-checking-out a hold you already hold is a no-op
    rather than an error, so a double click is harmless; checking out one somebody else
    holds is refused outright.
    """
    hold = get_object_or_404(_hold_queryset(request), pk=pk)
    if not hold.is_open:
        messages.info(request, f"Hold {hold.number} is {hold.get_status_display().lower()} — there is nothing to check out.")
        return redirect("sales:order_hold_detail", pk=hold.pk)
    if hold.is_checked_out and hold.checked_out_by_id != request.user.pk:
        messages.error(
            request,
            f"{hold.checked_out_by} already has hold {hold.number} checked out. "
            "Ask them to release it, or release it as a tenant administrator.",
        )
        return redirect("sales:order_hold_detail", pk=hold.pk)
    if hold.checked_out_by_id == request.user.pk:
        messages.info(request, f"Hold {hold.number} is already checked out to you.")
        return redirect("sales:order_hold_detail", pk=hold.pk)
    hold.checked_out_by = request.user
    hold.checked_out_at = timezone.now()
    hold.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
    write_audit_log(
        request.user,
        hold,
        "update",
        {"action": "checkout_order_hold", "number": hold.number},
        tenant=request.tenant,
    )
    messages.success(request, f"Hold {hold.number} checked out to you.")
    return redirect("sales:order_hold_detail", pk=hold.pk)


@require_POST
@login_required
@tenant_admin_required
def order_hold_release_checkout(request, pk):
    """Release the checkout. Holder or tenant admin only — the override is recorded.

    Taking a colleague's checkout is sometimes the right call (they went home mid-hold), so
    it is allowed for a tenant admin rather than forbidden outright. But it demands a written
    reason and is stamped into ``clear_note``: an override that leaves no trace is how a hold
    workbench becomes untrustworthy.
    """
    hold = get_object_or_404(_hold_queryset(request), pk=pk)
    if not hold.is_checked_out:
        messages.info(request, f"Hold {hold.number} has no checkout to release.")
        return redirect("sales:order_hold_detail", pk=hold.pk)
    is_holder = hold.checked_out_by_id == request.user.pk
    if not is_holder and not _is_tenant_admin(request.user):
        messages.error(
            request,
            f"{hold.checked_out_by} has hold {hold.number} checked out. Only they, or a tenant "
            "administrator, can release it.",
        )
        return redirect("sales:order_hold_detail", pk=hold.pk)

    form = OrderHoldActionForm(request.POST, tenant=request.tenant)
    override_note = ""
    if not is_holder:
        # The override is the only case that demands prose. In the ordinary case the release
        # is self-evident and asking for a reason only teaches people to type noise.
        if not form.is_valid():
            messages.error(
                request,
                "Say why you are overriding the checkout before taking it from "
                f"{hold.checked_out_by}.",
            )
            return redirect("sales:order_hold_detail", pk=hold.pk)
        override_note = (form.cleaned_data.get("release_note") or "").strip()

    previous_holder = hold.checked_out_by
    hold.checked_out_by = None
    hold.checked_out_at = None
    if override_note:
        hold.clear_note = (
            f"{hold.clear_note}\nOverride: released by {request.user} (held by {previous_holder}): "
            f"{override_note}"
        ).strip()
    hold.save(update_fields=["checked_out_by", "checked_out_at", "clear_note", "updated_at"])
    write_audit_log(
        request.user,
        hold,
        "update",
        {
            "action": "release_checkout",
            "number": hold.number,
            "override": bool(override_note),
            "previous_holder": str(previous_holder),
        },
        tenant=request.tenant,
    )
    if override_note:
        messages.warning(request, f"Checkout of hold {hold.number} taken from {previous_holder}.")
    else:
        messages.success(request, f"Checkout of hold {hold.number} released.")
    return redirect("sales:order_hold_detail", pk=hold.pk)



def _clear_hold(request, hold, note, released_checkout=False):
    """Clear one hold and, only if it was the last one, release the ORDER's hold flags.

    Returns the number of other open holds that remain on the order. The caller reports it;
    this function never decides what the user should be told.
    """
    remaining = _open_holds_remaining(hold)
    hold.status = "cleared"
    hold.cleared_by = request.user
    hold.cleared_at = timezone.now()
    hold.clear_note = note
    if released_checkout:
        hold.checked_out_by = None
        hold.checked_out_at = None
    hold.save(update_fields=[
        "status", "cleared_by", "cleared_at", "clear_note",
        "checked_out_by", "checked_out_at", "updated_at",
    ])
    write_audit_log(
        request.user,
        hold,
        "update",
        {
            "action": "clear_order_hold",
            "number": hold.number,
            "clear_note": note,
            "other_open_holds": remaining,
        },
        tenant=request.tenant,
    )
    # THE rule that makes clearing safe: one hold of three going away does not tell the
    # order it is free to ship.
    if remaining == 0:
        _release_order_hold_flags(hold.sales_order)
    return remaining



@require_POST
@login_required
@tenant_admin_required
def order_hold_clear(request, pk):
    """Clear a hold — with a written reason, and only when nobody else owns the checkout."""
    hold = get_object_or_404(_hold_queryset(request), pk=pk)
    if not hold.is_open:
        messages.info(request, f"Hold {hold.number} is already {hold.get_status_display().lower()}.")
        return redirect("sales:order_hold_detail", pk=hold.pk)
    # The checkout is exclusive, so clearing through it would defeat the point of taking it.
    if hold.is_checked_out and hold.checked_out_by_id != request.user.pk:
        messages.error(
            request,
            f"{hold.checked_out_by} has hold {hold.number} checked out. Release the checkout "
            "first — clearing a colleague's hold from under them is how two people end up "
            "releasing the same order.",
        )
        return redirect("sales:order_hold_detail", pk=hold.pk)

    form = OrderHoldActionForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        for error in form.errors.get("clear_note", []):
            messages.error(request, error)
        return redirect("sales:order_hold_detail", pk=hold.pk)
    note = (form.cleaned_data.get("clear_note") or "").strip()

    with transaction.atomic():
        remaining = _clear_hold(request, hold, note, released_checkout=hold.is_checked_out)
    if remaining:
        messages.warning(
            request,
            f"Hold {hold.number} cleared. {remaining} other open hold(s) still apply to order "
            f"{hold.sales_order.number}, which stays held.",
        )
    else:
        messages.success(
            request,
            f"Hold {hold.number} cleared — order {hold.sales_order.number} is no longer held.",
        )
    return redirect("sales:order_hold_detail", pk=hold.pk)



@require_POST
@login_required
@tenant_admin_required
def order_hold_clear_and_submit(request, pk):
    """Clear the hold, then let **4.5** submit the order.

    The submit is DELEGATED, never re-implemented: ``salesorder_submit`` re-runs the
    credit/fraud evaluation, refuses unmapped lines, stamps ``confirmation_sent_at`` only on
    the path that actually reaches ``submitted``, and owns the status machine. A blind
    ``order.status = "submitted"`` here would skip all of that and hand 8.6 a second,
    weaker, silently divergent submit path (L36/L37).

    The guards below therefore MIRROR 4.5's, so the refusal names its cause here instead of
    bouncing; where 4.5 refuses anyway, its refusal wins — that is the whole point.
    """
    hold = get_object_or_404(_hold_queryset(request), pk=pk)
    order = hold.sales_order
    if not hold.is_open:
        messages.info(request, f"Hold {hold.number} is already {hold.get_status_display().lower()}.")
        return redirect("scm:salesorder_detail", pk=order.pk)
    if hold.is_checked_out and hold.checked_out_by_id != request.user.pk:
        messages.error(
            request,
            f"{hold.checked_out_by} has hold {hold.number} checked out. Release the checkout first.",
        )
        return redirect("sales:order_hold_detail", pk=hold.pk)

    form = OrderHoldActionForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        for error in form.errors.get("clear_note", []):
            messages.error(request, error)
        return redirect("sales:order_hold_detail", pk=hold.pk)
    note = (form.cleaned_data.get("clear_note") or "").strip()

    with transaction.atomic():
        remaining = _clear_hold(request, hold, note, released_checkout=hold.is_checked_out)
    if remaining:
        messages.error(
            request,
            f"{remaining} other open hold(s) still apply to order {order.number}. Clear those "
            "first — the order cannot be submitted while any hold is open.",
        )
        return redirect("scm:salesorder_detail", pk=order.pk)


    # 4.5's own guards, restated so the refusal names the cause instead of bouncing.
    if order.status != "draft":
        messages.error(
            request,
            f"Order {order.number} is {order.get_status_display().lower()}, not a draft — SCM "
            "owns its workflow from here. Clear the hold, then submit it from the order itself.",
        )
        return redirect("scm:salesorder_detail", pk=order.pk)
    if not order.lines.exists():
        messages.error(request, f"Order {order.number} has no lines to submit.")
        return redirect("scm:salesorder_detail", pk=order.pk)
    if _has_unmapped_lines(order):
        messages.error(
            request,
            f"Order {order.number} still has line(s) with no stock item picked. Map them on the "
            "order before submitting.",
        )
        return redirect("scm:salesorder_detail", pk=order.pk)

    # DELEGATE. 4.5 re-evaluates and writes the status; this view never does.
    from apps.scm.views.OrderManagement.SalesOrders import salesorder_submit

    return salesorder_submit(request, order.pk)


@require_POST
@login_required
@tenant_admin_required
def order_hold_raise(request, order_id):
    """Evaluate every active rule against one order and raise the holds they find.

    This is the automatic half of the workbench: the counterpart of 4.5's fixed credit/fraud
    check, but driven by the workspace's own rule set. ``warn`` findings produce a message
    and no row — a rule that says "watch this" must not block an order or pad the board.
    """
    from apps.scm.models import SalesOrder

    order = get_object_or_404(
        SalesOrder.objects.filter(tenant=request.tenant).select_related("customer"),
        pk=order_id,
    )
    with transaction.atomic():
        created, warnings, skipped = _evaluate_order(request, order)
        _apply_holds_to_order(request, order, created)

    if created:
        messages.success(
            request,
            f"{len(created)} hold(s) raised on order {order.number}: "
            f"{', '.join(hold.number for hold in created)}.",
        )
    else:
        messages.info(request, f"No active validation rule holds order {order.number}.")
    for warning in warnings:
        messages.warning(request, warning)
    for note in skipped:
        messages.info(request, note)
    return redirect("sales:order_hold_list")



@require_POST
@login_required
@tenant_admin_required
def order_hold_bulk_raise(request):
    """Raise across a set of order ids, reporting every outcome individually.

    Per-record reporting, not a single summary: a batch that silently drops three of ten
    orders is worse than no batch at all, because the summary still reads "done". Every id
    that is not a real order in this workspace is named, not silently skipped.
    """
    from apps.scm.models import SalesOrder

    ids = _posted_ids(request, "order_ids")
    if not ids:
        messages.error(request, "Select at least one order to evaluate.")
        return redirect("sales:order_hold_list")

    orders = {
        order.pk: order
        for order in SalesOrder.objects.filter(tenant=request.tenant, pk__in=ids).select_related("customer")
    }
    raised, failed = 0, []
    for pk in ids:
        order = orders.get(pk)
        if order is None:
            failed.append(f"Order {pk}: not found in this workspace.")
            continue
        try:
            with transaction.atomic():
                created, _warnings, _skipped = _evaluate_order(request, order)
                _apply_holds_to_order(request, order, created)
        except Exception as exc:  # noqa: BLE001 - one bad order must not sink the batch
            failed.append(f"{order.number}: {exc}")
            continue
        if created:
            raised += 1
        else:
            failed.append(f"{order.number}: no active rule holds it.")
    if raised:
        messages.success(request, f"{raised} order(s) now carry at least one hold.")
    if failed:
        messages.warning(request, f"{len(failed)} order(s) raised nothing: " + "; ".join(failed[:8]))
    return redirect("sales:order_hold_list")


@require_POST
@login_required
@tenant_admin_required
def order_hold_bulk_clear(request):
    """Clear a set of holds, re-checking checkout ownership for EACH one.

    The checkout is re-evaluated per record rather than once for the batch, so a batch that
    contains one hold checked out by a colleague clears the other nine and says exactly which
    one it would not touch.
    """
    ids = _posted_ids(request, "hold_ids")
    if not ids:
        messages.error(request, "Select at least one hold to clear.")
        return redirect("sales:order_hold_list")

    form = OrderHoldActionForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        for error in form.errors.get("clear_note", []):
            messages.error(request, error)
        return redirect("sales:order_hold_list")
    note = (form.cleaned_data.get("clear_note") or "").strip()

    holds = {hold.pk: hold for hold in _hold_queryset(request).filter(pk__in=ids)}
    cleared, failed, still_held_orders = 0, [], set()
    for pk in ids:
        hold = holds.get(pk)
        if hold is None:
            failed.append(f"Hold {pk}: not found in this workspace.")
            continue
        if not hold.is_open:
            failed.append(f"{hold.number}: already {hold.get_status_display().lower()}.")
            continue
        if hold.is_checked_out and hold.checked_out_by_id != request.user.pk:
            failed.append(f"{hold.number}: checked out by {hold.checked_out_by}.")
            continue
        with transaction.atomic():
            remaining = _clear_hold(request, hold, note, released_checkout=hold.is_checked_out)
        cleared += 1
        if remaining:
            still_held_orders.add(hold.sales_order.number)

    if cleared:
        messages.success(request, f"{cleared} hold(s) cleared.")
    if still_held_orders:
        messages.warning(
            request,
            "These orders are still held by another open hold: " + ", ".join(sorted(still_held_orders)),
        )
    if failed:
        messages.warning(
            request,
            f"{len(failed)} hold(s) were not cleared: " + "; ".join(failed[:8]),
        )
    return redirect("sales:order_hold_list")

