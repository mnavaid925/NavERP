"""HRM 3.37 Compensation & Benefits — Equitygrant views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EquityGrant,
)
from apps.hrm.forms import (
    EquityGrantForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_employees, _ss_scope


# ---- Equity grants (admin-issued, own-vs-admin visibility) ------------------------------------
@login_required
def equitygrant_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, EquityGrant.objects.filter(tenant=request.tenant)
                   .select_related("employee__party", "currency"))
    extra = {"status_choices": EquityGrant.STATUS_CHOICES, "grant_type_choices": EquityGrant.GRANT_TYPE_CHOICES,
             "is_admin": is_admin}
    filters = [("status", "status", False), ("grant_type", "grant_type", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/compensation/equitygrant/list.html",
                     search_fields=["number", "employee__party__name"],
                     filters=filters, extra_context=extra)


@tenant_admin_required
def equitygrant_create(request):
    return crud_create(request, form_class=EquityGrantForm,
                       template="hrm/compensation/equitygrant/form.html", success_url="hrm:equitygrant_list")


@login_required
def equitygrant_detail(request, pk):
    obj = get_object_or_404(EquityGrant.objects.select_related("employee__party", "currency"),
                            pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This grant belongs to another employee.")
    return render(request, "hrm/compensation/equitygrant/detail.html", {
        "obj": obj, "is_admin": _is_admin(request.user)})


@tenant_admin_required
def equitygrant_edit(request, pk):
    return crud_edit(request, model=EquityGrant, pk=pk, form_class=EquityGrantForm,
                     template="hrm/compensation/equitygrant/form.html", success_url="hrm:equitygrant_list")


@tenant_admin_required
@require_POST
def equitygrant_delete(request, pk):
    return crud_delete(request, model=EquityGrant, pk=pk, success_url="hrm:equitygrant_list")


@tenant_admin_required
@require_POST
def equitygrant_record_exercise(request, pk):
    """Record an exercise/release of vested shares (admin). Guards against exercising more than the
    currently exercisable (vested − already-exercised) amount."""
    obj = get_object_or_404(EquityGrant, pk=pk, tenant=request.tenant)
    if obj.status in ("cancelled", "expired"):
        messages.error(request, "A cancelled or expired grant can't be exercised.")
        return redirect("hrm:equitygrant_detail", pk=obj.pk)
    raw = (request.POST.get("shares") or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        messages.error(request, "Enter a positive number of shares to exercise.")
        return redirect("hrm:equitygrant_detail", pk=obj.pk)
    shares = int(raw)
    if shares > obj.exercisable_shares:
        messages.error(request, f"Only {obj.exercisable_shares} vested share(s) are currently exercisable.")
        return redirect("hrm:equitygrant_detail", pk=obj.pk)
    obj.exercised_shares += shares
    obj.last_exercised_at = timezone.now()
    if obj.exercised_shares >= obj.shares_granted:
        obj.status = "exercised"
    obj.save(update_fields=["exercised_shares", "last_exercised_at", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "record_exercise", "shares": shares})
    messages.success(request, f"Recorded exercise of {shares} share(s) on {obj.number}.")
    return redirect("hrm:equitygrant_detail", pk=obj.pk)
