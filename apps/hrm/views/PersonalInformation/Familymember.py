"""HRM 3.25 Personal Information — Familymember views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_delete, _ss_child_detail, _ss_child_edit, _ss_employees, _ss_scope
from apps.hrm.models import (
    FamilyMember,
)
from apps.hrm.forms import (
    FamilyMemberForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_delete, _ss_child_detail, _ss_child_edit, _ss_employees, _ss_scope


# ---------------------------------------------------------------- Family Members (admin-gated writes)
@login_required
def familymember_list(request):
    qs = _ss_scope(request, FamilyMember.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin, "relationship_choices": FamilyMember.RELATIONSHIP_CHOICES}
    filters = [("relationship", "relationship", False), ("is_dependent", "is_dependent", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/familymember/list.html",
                     search_fields=("name", "occupation", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def familymember_detail(request, pk):
    return _ss_child_detail(request, FamilyMember, pk,
                            "hrm/selfservice/familymember/detail.html", select_related=("employee__party",))


@tenant_admin_required
def familymember_create(request):
    return _ss_child_create(request, FamilyMemberForm,
                            "hrm/selfservice/familymember/form.html", "hrm:familymember_list")


@tenant_admin_required
def familymember_edit(request, pk):
    return _ss_child_edit(request, FamilyMember, pk, FamilyMemberForm,
                          "hrm/selfservice/familymember/form.html", "hrm:familymember_detail")


@tenant_admin_required
@require_POST
def familymember_delete(request, pk):
    return _ss_child_delete(request, FamilyMember, pk, "hrm:familymember_list")
