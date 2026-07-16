"""HRM 3.1 Employee Management — Lifecycle views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeManagement._helpers import _employee_child_create
from apps.hrm.models import (
    EmployeeLifecycleEvent,
    EmployeeProfile,
    LIFECYCLE_EVENT_TYPE_CHOICES,
)
from apps.hrm.forms import (
    EmployeeLifecycleEventForm,
)
from apps.hrm.views.EmployeeManagement._helpers import _employee_child_create


# ---------------------------------------------------------- Employee Lifecycle Events (3.1)
@login_required
def employee_lifecycle_list(request):
    return crud_list(
        request,
        EmployeeLifecycleEvent.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "from_designation", "to_designation"),
        "hrm/employee/lifecycle/list.html",
        search_fields=["number", "employee__party__name", "reason", "notes"],
        filters=[("event_type", "event_type", False), ("employee", "employee_id", True)],
        extra_context={"event_type_choices": LIFECYCLE_EVENT_TYPE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@tenant_admin_required  # lifecycle events are authoritative HR records (promotion/salary/separation)
def employee_lifecycle_create(request):
    return _employee_child_create(request, EmployeeLifecycleEventForm,
                                  "hrm/employee/lifecycle/form.html", stamp_initiated_by=True)


@login_required
def employee_lifecycle_detail(request, pk):
    obj = get_object_or_404(
        EmployeeLifecycleEvent.objects.select_related(
            "employee__party", "from_designation", "to_designation", "from_department",
            "to_department", "from_manager__party", "to_manager__party", "initiated_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/employee/lifecycle/detail.html", {"obj": obj})


@tenant_admin_required
def employee_lifecycle_edit(request, pk):
    return crud_edit(request, model=EmployeeLifecycleEvent, pk=pk,
                     form_class=EmployeeLifecycleEventForm,
                     template="hrm/employee/lifecycle/form.html",
                     success_url="hrm:employee_lifecycle_list")


@tenant_admin_required
@require_POST
def employee_lifecycle_delete(request, pk):
    return crud_delete(request, model=EmployeeLifecycleEvent, pk=pk,
                       success_url="hrm:employee_lifecycle_list")
