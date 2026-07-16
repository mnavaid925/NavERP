"""HRM 3.25 Personal Information — Emergencycontact views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_delete, _ss_child_detail, _ss_child_edit, _ss_employees, _ss_scope
from apps.hrm.models import (
    EmergencyContact,
)
from apps.hrm.forms import (
    EmergencyContactForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_delete, _ss_child_detail, _ss_child_edit, _ss_employees, _ss_scope


# ---------------------------------------------------------------- Emergency Contacts (direct self-edit)
@login_required
def emergencycontact_list(request):
    qs = _ss_scope(request, EmergencyContact.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin}
    filters = [("is_primary", "is_primary", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/emergencycontact/list.html",
                     search_fields=("name", "relationship", "phone", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def emergencycontact_create(request):
    return _ss_child_create(request, EmergencyContactForm,
                            "hrm/selfservice/emergencycontact/form.html", "hrm:emergencycontact_list")


@login_required
def emergencycontact_detail(request, pk):
    return _ss_child_detail(request, EmergencyContact, pk,
                            "hrm/selfservice/emergencycontact/detail.html", select_related=("employee__party",))


@login_required
def emergencycontact_edit(request, pk):
    return _ss_child_edit(request, EmergencyContact, pk, EmergencyContactForm,
                          "hrm/selfservice/emergencycontact/form.html", "hrm:emergencycontact_detail")


@login_required
@require_POST
def emergencycontact_delete(request, pk):
    return _ss_child_delete(request, EmergencyContact, pk, "hrm:emergencycontact_list")
