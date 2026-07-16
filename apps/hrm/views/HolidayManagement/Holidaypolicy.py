"""HRM 3.12 Holiday Management — Holidaypolicy views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
    HolidayPolicy,
)
from apps.hrm.forms import (
    HolidayPolicyForm,
)


# ============================================================ Holiday Policies (3.12)
@login_required
def holidaypolicy_list(request):
    return crud_list(
        request,
        HolidayPolicy.objects.filter(tenant=request.tenant).select_related("org_unit", "designation"),
        "hrm/holiday/holidaypolicy/list.html",
        search_fields=["name", "location"],
        filters=[("is_active", "is_active", False), ("employee_type", "employee_type", False),
                 ("org_unit", "org_unit_id", True), ("designation", "designation_id", True)],
        extra_context={
            "employee_type_choices": EmployeeProfile.EMPLOYEE_TYPE_CHOICES,
            "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
            "designations": Designation.objects.filter(tenant=request.tenant).order_by("name"),
        },
    )


@login_required
def holidaypolicy_create(request):
    return crud_create(request, form_class=HolidayPolicyForm,
                       template="hrm/holiday/holidaypolicy/form.html", success_url="hrm:holidaypolicy_list")


@login_required
def holidaypolicy_detail(request, pk):
    obj = get_object_or_404(
        HolidayPolicy.objects.select_related("org_unit", "designation").prefetch_related("holidays"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/holiday/holidaypolicy/detail.html", {
        "obj": obj,
        # .all() (not .order_by) serves from the prefetch_related cache above; PublicHoliday.Meta
        # already orders by date, so this stays date-sorted with zero extra queries.
        "policy_holidays": obj.holidays.all(),
        "recent_elections": (obj.elections.select_related("employee__party", "holiday")
                             .all()[:10]),
    })


@login_required
def holidaypolicy_edit(request, pk):
    return crud_edit(request, model=HolidayPolicy, pk=pk, form_class=HolidayPolicyForm,
                     template="hrm/holiday/holidaypolicy/form.html", success_url="hrm:holidaypolicy_list")


@login_required
@require_POST
def holidaypolicy_delete(request, pk):
    return crud_delete(request, model=HolidayPolicy, pk=pk, success_url="hrm:holidaypolicy_list")
