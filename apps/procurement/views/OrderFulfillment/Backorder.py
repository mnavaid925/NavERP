"""Procurement 6.11 Order Fulfillment & Tracking — Backorder views.

**Backorder Management** bullet: a register of outstanding shortfalls that can actually be WORKED —
filtered by how much trouble each one is in, rescheduled with a stated reason, closed out, and
escalated into the 6.1 alert inbox.

Two rules shape this file:

* **The risk buckets are ORM date arithmetic, applied BEFORE ``crud_list``.** Computing "past due"
  in Python over ``page_obj.object_list`` would filter the page rather than the queryset, and every
  count, every page number and the paginator itself would then be lying about a different set of
  rows than the one on screen.
* **Every status guard is re-checked in the model verb, not only here.** These views refuse early
  so the user gets a message instead of a silent no-op, but hiding a button (or failing a check in
  a view) is not what stops a direct POST — the verb's own guard is.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import as_db_int
from apps.procurement.forms import BackorderCloseForm, BackorderForm, BackorderRescheduleForm
from apps.procurement.models import AdvancedShipmentNotice, Backorder
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseOrder, PurchaseOrderLine


def _risk_conditions(today):
    """The four risk buckets as ORM ``Q()`` objects — ONE definition, used by the ``?risk=``
    filter AND by the stat cards, so a card can never disagree with the list it links to.

    ``Backorder.risk_bucket`` mirrors these clause for clause on the Python side (that is what puts
    the right badge on each row); keeping both in step is why they are written out here rather than
    inlined at three call sites.
    """
    horizon = today + timedelta(days=Backorder.AT_RISK_DAYS)
    live = Q(status__in=Backorder.OPEN_STATUSES)
    return {
        "past_due": live & (Q(revised_promise_date__lt=today)
                            | Q(revised_promise_date__isnull=True,
                                original_promise_date__lt=today)),
        "at_risk": live & Q(revised_promise_date__gte=today,
                            revised_promise_date__lte=horizon),
        "no_commitment": live & Q(revised_promise_date__isnull=True,
                                  original_promise_date__isnull=True),
        "on_track": live & Q(revised_promise_date__gt=horizon),
    }


@login_required
def backorder_list(request):
    """The shortfall register. ``?risk=`` narrows the QUERYSET (never the page); an unknown value is
    ignored so a hand-edited ``?risk=zzz`` still renders a 200 rather than an empty-looking lie."""
    base = (Backorder.objects.filter(tenant=request.tenant)
            # Exactly what a row (and a row's __str__, which walks po_line -> item_description)
            # touches, plus the chained hop to the order the PO column and the search both use.
            # `delivery_schedule`, `asn` and `alert` are deliberately NOT here: the register
            # renders none of them, so each would only add a LEFT JOIN that drags an unused
            # TextField into every row. backorder_detail keeps its wider select_related — that
            # page does show all three.
            .select_related("po_line", "po_line__purchase_order"))

    conditions = _risk_conditions(timezone.localdate())
    qs = base
    risk = request.GET.get("risk", "").strip()
    if risk in conditions:
        qs = qs.filter(conditions[risk])

    stats = base.aggregate(
        open=Count("id", filter=Q(status__in=Backorder.OPEN_STATUSES)),
        past_due=Count("id", filter=conditions["past_due"]),
        at_risk=Count("id", filter=conditions["at_risk"]),
        no_commitment=Count("id", filter=conditions["no_commitment"]),
    )

    return crud_list(
        request, qs, "procurement/orderfulfillment/backorder/list.html",
        search_fields=["number", "reason_note", "po_line__item_description",
                       "po_line__purchase_order__number"],
        filters=[
            ("status", "status", False),
            ("reason", "reason", False),
            ("po", "po_line__purchase_order_id", True),
        ],
        extra_context={
            "status_choices": Backorder.STATUS_CHOICES,
            "reason_choices": Backorder.REASON_CHOICES,
            "risk_choices": Backorder.RISK_CHOICES,
            "purchase_orders": (PurchaseOrder.objects.filter(tenant=request.tenant)
                                .order_by("-order_date", "-id")[:200]),
            "stats": stats,
        },
    )


@login_required
def backorder_detail(request, pk):
    obj = get_object_or_404(
        Backorder.objects.select_related(
            "po_line", "po_line__purchase_order", "po_line__purchase_order__vendor",
            "delivery_schedule", "asn", "alert", "created_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "procurement/orderfulfillment/backorder/detail.html", {
        "obj": obj,
        "po_line": obj.po_line,
        "order": obj.po_line.purchase_order,
        "reschedule_form": BackorderRescheduleForm(),
        "close_form": BackorderCloseForm(),
        "alert": obj.alert,
        # The Actions sidebar gates on THESE booleans, never on raw status strings — one place to
        # read what a user may do with this row, and it matches the verbs' own guards.
        "can_edit": obj.is_open,
        "can_reschedule": obj.is_open,
        "can_fulfil": obj.is_open,
        "can_cancel": obj.is_open,
        "can_raise_alert": obj.is_open,
        # Mirrors @tenant_admin_required on backorder_delete exactly — a button a non-admin can see
        # but not use is a lie, and one that is merely hidden is not a control.
        "can_delete": bool(request.user.is_superuser
                           or getattr(request.user, "is_tenant_admin", False)),
    })


@login_required
def backorder_create(request):
    """Record a shortfall. Hand-rolled rather than ``crud_create`` for two reasons the generic
    helper cannot cover: stamping ``created_by``, and the ASN hand-off prefill.

    The prefill (``?po_line=&asn=&quantity=`` from the shortfall row on an ASN's detail page) is
    CONVENIENCE ONLY. Every referenced row is re-checked against this tenant and dropped if it does
    not belong — a query string is never an authorization path, and the form's own querysets plus
    ``Backorder.clean()`` refuse a foreign pk again on POST.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before recording backorders.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = BackorderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create",
                            {"po_line": str(obj.po_line)[:120],
                             "quantity": str(obj.quantity_backordered)})
            messages.success(request, f"Backorder {obj.number} recorded.")
            return redirect("procurement:backorder_detail", pk=obj.pk)
    else:
        form = BackorderForm(tenant=request.tenant, initial=_create_initial(request))

    return render(request, "procurement/orderfulfillment/backorder/form.html",
                  {"form": form, "is_edit": False, "obj": None})


def _create_initial(request):
    """Tenant-checked ``?po_line=&asn=&quantity=`` prefill for the create form.

    A ModelChoiceField preselects by PK — handing it an instance silently matches nothing — so the
    validated pks go in as integers. Anything that is not this workspace's row is simply left out.
    """
    initial = {}

    line_pk = as_db_int(request.GET.get("po_line"))
    if line_pk is not None and PurchaseOrderLine.objects.filter(
            pk=line_pk, purchase_order__tenant=request.tenant).exists():
        initial["po_line"] = line_pk

    asn_pk = as_db_int(request.GET.get("asn"))
    if asn_pk is not None and AdvancedShipmentNotice.objects.filter(
            pk=asn_pk, tenant=request.tenant).exists():
        initial["asn"] = asn_pk

    raw_quantity = (request.GET.get("quantity") or "").strip()
    if raw_quantity:
        try:
            quantity = Decimal(raw_quantity)
            # L11, decimal edition: "nan" and "Infinity" both PARSE cleanly, and it is the
            # COMPARISON that then raises (NaN) or the save that dies (Infinity). is_finite()
            # covers both, and the whole thing sits inside the try because `> 0` is itself the
            # operation that throws — a hand-typed ?quantity=nan must not 500 the add page.
            if quantity.is_finite() and quantity > 0:
                # A zero/negative shortfall is not a backorder — leave the field blank rather
                # than prefilling a value the model validator will immediately reject.
                initial["quantity_backordered"] = quantity
        except (InvalidOperation, ValueError, ArithmeticError):
            pass

    return initial


@login_required
def backorder_edit(request, pk):
    """Amend a live shortfall. A closed row is frozen: its quantity and dates are the record of
    what happened, and re-opening is a new backorder, not an edit of the old one."""
    obj = get_object_or_404(Backorder, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request,
                       f"Backorder {obj.number} is {obj.get_status_display().lower()} — a closed "
                       f"shortfall is a record of what happened and cannot be edited.")
        return redirect("procurement:backorder_detail", pk=obj.pk)
    return crud_edit(
        request, model=Backorder, pk=pk, form_class=BackorderForm,
        template="procurement/orderfulfillment/backorder/form.html",
        success_url=reverse("procurement:backorder_detail", args=[obj.pk]),
    )


@login_required
@tenant_admin_required
@require_POST
def backorder_delete(request, pk):
    """Admin-gated: deleting a backorder erases the evidence that a supplier missed a commitment.
    Closing it out (Fulfil / Cancel) is the ordinary way to finish one."""
    return crud_delete(request, model=Backorder, pk=pk,
                       success_url="procurement:backorder_list")


@login_required
@require_POST
def backorder_reschedule(request, pk):
    """The supplier has moved the date. Locked so two simultaneous reschedules cannot both read the
    same ``reschedule_count`` and each write it as +1, losing a slip from the record."""
    form = BackorderRescheduleForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Give both the new promised date and the reason it moved.")
        return redirect("procurement:backorder_detail", pk=pk)

    with transaction.atomic():
        obj = get_object_or_404(Backorder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        moved = obj.reschedule(request.user,
                               form.cleaned_data["revised_promise_date"],
                               form.cleaned_data["reason_note"])
    if not moved:
        messages.info(request, "This backorder is already closed — its dates are final.")
        return redirect("procurement:backorder_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "reschedule",
        "revised_promise_date": str(obj.revised_promise_date),
        "reschedule_count": obj.reschedule_count,
    })
    messages.success(request,
                     f"Backorder {obj.number} rescheduled to "
                     f"{obj.revised_promise_date:%Y-%m-%d} (slip #{obj.reschedule_count}).")
    return redirect("procurement:backorder_detail", pk=pk)


@login_required
@require_POST
def backorder_fulfil(request, pk):
    """The outstanding quantity arrived. (Booking the RECEIPT itself is 6.12's job — this only
    closes the chase.)"""
    form = BackorderCloseForm(request.POST)
    note = form.cleaned_data.get("closure_note", "") if form.is_valid() else ""

    with transaction.atomic():
        obj = get_object_or_404(Backorder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        closed = obj.fulfil(request.user, note=note)
    if not closed:
        messages.info(request, "This backorder has already been closed.")
        return redirect("procurement:backorder_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {"action": "fulfil", "note": note[:200]})
    messages.success(request, f"Backorder {obj.number} marked fulfilled.")
    return redirect("procurement:backorder_detail", pk=pk)


@login_required
@require_POST
def backorder_cancel(request, pk):
    """The shortfall will never be delivered — sourced elsewhere, or the order shrank. Closing the
    backorder does NOT touch the purchase order: 6.11 is read-only against the spine (L36), and
    changing what was ordered is a 6.10 change order."""
    form = BackorderCloseForm(request.POST)
    note = form.cleaned_data.get("closure_note", "") if form.is_valid() else ""

    with transaction.atomic():
        obj = get_object_or_404(Backorder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        closed = obj.cancel(request.user, note=note)
    if not closed:
        messages.info(request, "This backorder has already been closed.")
        return redirect("procurement:backorder_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {"action": "cancel", "note": note[:200]})
    messages.success(request, f"Backorder {obj.number} cancelled.")
    return redirect("procurement:backorder_detail", pk=pk)


@login_required
@require_POST
def backorder_raise_alert(request, pk):
    """Escalate into the 6.1 Task & Alert Center. ``raise_alert()`` is idempotent, so this reports
    an existing open alert with ``messages.info`` rather than failing or raising a duplicate."""
    with transaction.atomic():
        obj = get_object_or_404(
            Backorder.objects.select_for_update().select_related(
                "po_line", "po_line__purchase_order", "alert"),
            pk=pk, tenant=request.tenant)
        if not obj.is_open:
            messages.error(request, "A closed backorder needs no escalation.")
            return redirect("procurement:backorder_detail", pk=pk)
        previous_alert_id = obj.alert_id
        alert = obj.raise_alert(request.user)
        # A NEW alert has a different pk from whatever was linked before; the idempotent path hands
        # back the row that was already there.
        raised = alert.pk != previous_alert_id

    write_audit_log(request.user, obj, "update",
                    {"action": "raise_alert", "alert": alert.pk, "raised": raised})
    if raised:
        messages.success(request,
                         f"Alert raised for backorder {obj.number} — it is now in the Task & "
                         f"Alert Center.")
    else:
        messages.info(request, f"Backorder {obj.number} already has an open alert.")
    return redirect("procurement:backorder_detail", pk=pk)
