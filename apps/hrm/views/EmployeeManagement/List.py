"""HRM 3.1 Employee Management — List views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
)


# ============================================================ Employee Profiles (3.1)
@login_required
def employee_list(request):
    return crud_list(
        request,
        EmployeeProfile.objects.filter(tenant=request.tenant)
        .select_related("party", "employment", "employment__org_unit", "designation"),
        "hrm/employee/list.html",
        search_fields=["number", "party__name", "personal_email", "mobile"],
        filters=[("employee_type", "employee_type", False),
                 ("designation", "designation_id", True),
                 ("status", "employment__status", False)],
        extra_context={"employee_type_choices": EmployeeProfile.EMPLOYEE_TYPE_CHOICES,
                       "designations": Designation.objects.filter(tenant=request.tenant).order_by("name"),
                       "status_choices": Employment.STATUS_CHOICES},
    )
