"""HRM 3.37 Compensation & Benefits — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeBenefitEnrollment,
)


def _enrollment_decide(request, pk, new_status, ok_from, message):
    """Shared admin transition for the benefit-enrollment lifecycle (enroll/waive/terminate)."""
    obj = get_object_or_404(EmployeeBenefitEnrollment, pk=pk, tenant=request.tenant)
    if obj.status not in ok_from:
        messages.error(request, f"This enrollment can't be {message} from its current status.")
        return redirect("hrm:employeebenefitenrollment_detail", pk=obj.pk)
    obj.status = new_status
    obj.decided_by = request.user
    fields = ["status", "decided_by", "updated_at"]
    if new_status == "enrolled":
        obj.enrolled_at = timezone.now()
        fields.append("enrolled_at")
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": message})
    messages.success(request, f"Enrollment {obj.number} {message}.")
    return redirect("hrm:employeebenefitenrollment_detail", pk=obj.pk)
