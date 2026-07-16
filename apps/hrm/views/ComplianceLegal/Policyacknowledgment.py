"""HRM 3.39 Compliance & Legal — Policyacknowledgment views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    HRPolicy,
    PolicyAcknowledgment,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_employees, _ss_scope


# ---- Policy acknowledgments (employee self-service) --------------------------------------------
@login_required
def policyacknowledgment_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, PolicyAcknowledgment.objects.filter(tenant=request.tenant)
                   .select_related("policy", "employee__party"))
    extra = {"is_admin": is_admin, "status_choices": PolicyAcknowledgment.STATUS_CHOICES,
             "policies": HRPolicy.objects.filter(tenant=request.tenant, status="published")
             .order_by("title")}
    filters = [("status", "status", False), ("policy", "policy_id", True)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/compliance/policyacknowledgment/list.html",
                     search_fields=["policy__title", "employee__party__name"],
                     filters=filters, extra_context=extra)


@login_required
@require_POST
def policyacknowledgment_acknowledge(request, pk):
    """The employee acknowledges their OWN pending policy row (an admin can't acknowledge for them)."""
    obj = get_object_or_404(PolicyAcknowledgment.objects.select_related("policy"),
                            pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (profile is not None and obj.employee_id == profile.pk):
        messages.error(request, "You can only acknowledge your own policy assignments.")
        return redirect("hrm:policyacknowledgment_list")
    if obj.status == "acknowledged":
        messages.error(request, "You have already acknowledged this policy.")
        return redirect("hrm:policyacknowledgment_list")
    obj.status = "acknowledged"
    obj.acknowledged_at = timezone.now()
    obj.save(update_fields=["status", "acknowledged_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
    messages.success(request, f"Acknowledged '{obj.policy.title}'.")
    return redirect("hrm:policyacknowledgment_list")
