"""HRM 3.35 Travel Management — Travelrequest views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    ExpenseClaim,
    TravelBooking,
    TravelRequest,
)
from apps.hrm.forms import (
    TravelBookingForm,
    TravelRequestForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_child_create, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit, _is_own_hr_request


@login_required
def travelrequest_list(request):
    is_admin = _is_admin(request.user)
    # list.html only renders employee.party.name (+ scalar fields); trim to match — no bookings/policy/
    # currency/approver/settlement_claim on this page, so drop the dead prefetch + unused joins.
    qs = _ss_scope(request, TravelRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    return crud_list(request, qs, "hrm/travel/travelrequest/list.html",
                     search_fields=["number", "title", "origin", "destination"],
                     filters=[("status", "status", False), ("trip_type", "trip_type", False),
                              ("employee", "employee_id", is_admin)],
                     extra_context={"status_choices": TravelRequest.STATUS_CHOICES,
                                    "trip_type_choices": TravelRequest.TRIP_TYPE_CHOICES, "is_admin": is_admin,
                                    "employees": _ss_employees(request) if is_admin else None})


@login_required
def travelrequest_create(request):
    return _ss_child_create(request, TravelRequestForm, "hrm/travel/travelrequest/form.html",
                            "hrm:travelrequest_list")


@login_required
def travelrequest_detail(request, pk):
    obj = get_object_or_404(
        TravelRequest.objects.select_related("employee__party", "policy", "currency", "approver",
                                             "settlement_claim")
        .prefetch_related("bookings", "settlement_claim__lines"),
        pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This trip belongs to another employee.")
    return render(request, "hrm/travel/travelrequest/detail.html", {
        "obj": obj, "bookings": obj.bookings.all(), "is_admin": _is_admin(request.user),
        "is_own": _is_own_hr_request(request, obj), "net_settlement": obj.net_settlement,
        "booking_form": TravelBookingForm(tenant=request.tenant) if obj.status in TravelRequest.OPEN_STATUSES else None,
        "booking_type_choices": TravelBooking.BOOKING_TYPE_CHOICES})


@login_required
def travelrequest_edit(request, pk):
    return _hr_request_edit(request, TravelRequest, pk, TravelRequestForm,
                            "hrm/travel/travelrequest/form.html", "hrm:travelrequest_detail")


@login_required
@require_POST
def travelrequest_delete(request, pk):
    return _hr_request_delete(request, TravelRequest, pk, "hrm:travelrequest_list")


@login_required
@require_POST
def travelrequest_submit(request, pk):
    return _hr_request_submit(request, TravelRequest, pk, "hrm:travelrequest_detail")


@login_required
@require_POST
def travelrequest_cancel(request, pk):
    return _hr_request_cancel(request, TravelRequest, pk, "hrm:travelrequest_detail")


@tenant_admin_required
@require_POST
def travelrequest_approve(request, pk):
    return _hr_request_approve(request, TravelRequest, pk, "hrm:travelrequest_detail")


@tenant_admin_required
@require_POST
def travelrequest_reject(request, pk):
    return _hr_request_reject(request, TravelRequest, pk, "hrm:travelrequest_detail")


@tenant_admin_required
@require_POST
def travelrequest_approve_advance(request, pk):
    obj = get_object_or_404(TravelRequest, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You can't approve your own travel advance — another admin must review it.")
        return redirect("hrm:travelrequest_detail", pk=obj.pk)
    if obj.status != "approved":
        messages.error(request, "The trip must be approved before its advance can be authorized.")
        return redirect("hrm:travelrequest_detail", pk=obj.pk)
    raw = (request.POST.get("advance_approved") or "").strip()
    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, "Enter a valid advance amount.")
        return redirect("hrm:travelrequest_detail", pk=obj.pk)
    # Decimal("NaN")/"Infinity" parse fine; ordering comparisons on NaN raise InvalidOperation (500).
    if not amount.is_finite():
        messages.error(request, "Enter a valid advance amount.")
        return redirect("hrm:travelrequest_detail", pk=obj.pk)
    if amount < 0:
        messages.error(request, "Amount must be zero or greater.")
    elif amount >= Decimal("10000000000"):
        messages.error(request, "Amount is too large.")
    elif obj.advance_requested is None:
        messages.error(request, "No advance was requested for this trip, so none can be approved.")
    elif amount > obj.advance_requested:
        messages.error(request, f"Cannot approve more than the requested advance of {obj.advance_requested}.")
    elif (obj.policy_id and obj.policy.advance_percent_limit is not None and obj.estimated_cost is not None
          and amount > (obj.policy.advance_percent_limit / Decimal("100")) * obj.estimated_cost):
        cap = ((obj.policy.advance_percent_limit / Decimal("100")) * obj.estimated_cost).quantize(Decimal("0.01"))
        messages.error(request, f"Cannot exceed the policy cap of {cap} "
                                f"({obj.policy.advance_percent_limit}% of the estimated cost).")
    else:
        obj.advance_approved = amount
        obj.save(update_fields=["advance_approved", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve_advance"})
        messages.success(request, "Travel advance approved.")
    return redirect("hrm:travelrequest_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def travelrequest_mark_advance_paid(request, pk):
    obj = get_object_or_404(TravelRequest, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You can't disburse your own travel advance.")
    elif obj.advance_approved is None or obj.advance_approved <= 0:
        messages.error(request, "No approved advance to disburse.")
    elif obj.advance_paid_at:
        messages.error(request, "The advance has already been marked as paid.")
    else:
        obj.advance_paid_at = timezone.now()
        obj.advance_reference = (request.POST.get("advance_reference") or "").strip()[:100]
        obj.save(update_fields=["advance_paid_at", "advance_reference", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_advance_paid"})
        messages.success(request, "Advance marked as paid.")
    return redirect("hrm:travelrequest_detail", pk=obj.pk)


@login_required
@require_POST
def travelrequest_generate_settlement(request, pk):
    obj = get_object_or_404(TravelRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("You can only generate a settlement for your own trip.")
    if obj.status not in ("approved", "completed"):
        messages.error(request, "Generate a settlement only after the trip is approved.")
        return redirect("hrm:travelrequest_detail", pk=obj.pk)
    if obj.settlement_claim_id:
        messages.error(request, "A settlement has already been generated for this trip.")
        return redirect("hrm:travelrequest_detail", pk=obj.pk)
    with transaction.atomic():
        claim = ExpenseClaim.objects.create(
            tenant=request.tenant, employee=obj.employee,
            title=f"Travel settlement - {obj.destination}", purpose=obj.purpose,
            period_start=obj.start_date, period_end=obj.end_date, currency=obj.currency, status="draft")
        obj.settlement_claim = claim
        obj.save(update_fields=["settlement_claim", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "generate_settlement", "claim": claim.number})
    messages.success(request, f"Settlement {claim.number} created. Add expense lines and submit it for approval.")
    return redirect("hrm:expenseclaim_detail", pk=claim.pk)


@login_required
@require_POST
def travelrequest_complete(request, pk):
    obj = get_object_or_404(TravelRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This trip belongs to another employee.")
    if obj.status != "approved":
        messages.error(request, "Only an approved trip can be marked completed.")
    else:
        obj.status = "completed"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, "Trip marked completed.")
    return redirect("hrm:travelrequest_detail", pk=obj.pk)
