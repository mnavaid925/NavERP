"""HRM 3.41 Employee Engagement & Wellbeing — Flexibleworkarrangement views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    FlexibleWorkArrangement,
)
from apps.hrm.forms import (
    FlexibleWorkArrangementForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_child_create, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit, _is_own_hr_request


# ---- Flexible work arrangements (a TravelRequest-shaped self-service request) -------------------
@login_required
def flexibleworkarrangement_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, FlexibleWorkArrangement.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    return crud_list(request, qs, "hrm/engagement/flexibleworkarrangement/list.html",
                     search_fields=["number", "reason"],
                     filters=[("status", "status", False),
                              ("arrangement_type", "arrangement_type", False),
                              ("employee", "employee_id", is_admin)],
                     extra_context={"status_choices": FlexibleWorkArrangement.STATUS_CHOICES,
                                    "arrangement_type_choices": FlexibleWorkArrangement.ARRANGEMENT_TYPE_CHOICES,
                                    "is_admin": is_admin,
                                    "employees": _ss_employees(request) if is_admin else None})


@login_required
def flexibleworkarrangement_create(request):
    return _ss_child_create(request, FlexibleWorkArrangementForm,
                            "hrm/engagement/flexibleworkarrangement/form.html",
                            "hrm:flexibleworkarrangement_list")


@login_required
def flexibleworkarrangement_detail(request, pk):
    obj = get_object_or_404(
        FlexibleWorkArrangement.objects.select_related("employee__party", "approver"),
        pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This request belongs to another employee.")
    return render(request, "hrm/engagement/flexibleworkarrangement/detail.html", {
        "obj": obj, "is_admin": _is_admin(request.user), "is_own": _is_own_hr_request(request, obj)})


@login_required
def flexibleworkarrangement_edit(request, pk):
    return _hr_request_edit(request, FlexibleWorkArrangement, pk, FlexibleWorkArrangementForm,
                            "hrm/engagement/flexibleworkarrangement/form.html",
                            "hrm:flexibleworkarrangement_detail")


@login_required
@require_POST
def flexibleworkarrangement_delete(request, pk):
    return _hr_request_delete(request, FlexibleWorkArrangement, pk, "hrm:flexibleworkarrangement_list")


@login_required
@require_POST
def flexibleworkarrangement_submit(request, pk):
    return _hr_request_submit(request, FlexibleWorkArrangement, pk, "hrm:flexibleworkarrangement_detail")


@login_required
@require_POST
def flexibleworkarrangement_cancel(request, pk):
    return _hr_request_cancel(request, FlexibleWorkArrangement, pk, "hrm:flexibleworkarrangement_detail")


@tenant_admin_required
@require_POST
def flexibleworkarrangement_approve(request, pk):
    return _hr_request_approve(request, FlexibleWorkArrangement, pk, "hrm:flexibleworkarrangement_detail")


@tenant_admin_required
@require_POST
def flexibleworkarrangement_reject(request, pk):
    return _hr_request_reject(request, FlexibleWorkArrangement, pk, "hrm:flexibleworkarrangement_detail")
