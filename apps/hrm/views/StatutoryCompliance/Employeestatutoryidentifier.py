"""HRM 3.15 Statutory Compliance — Employeestatutoryidentifier views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeStatutoryIdentifier,
    INDIAN_STATE_CHOICES,
)
from apps.hrm.forms import (
    EmployeeStatutoryIdentifierForm,
)


# ---------------------------------------- EmployeeStatutoryIdentifier (UAN/PF/ESI)
@login_required
def employeestatutoryidentifier_list(request):
    return crud_list(
        request,
        EmployeeStatutoryIdentifier.objects.filter(tenant=request.tenant).select_related("employee__party"),
        "hrm/statutory/employeestatutoryidentifier/list.html",
        search_fields=["employee__party__name", "uan_number", "pf_number", "esi_number"],
        filters=[("pt_state", "pt_state", False), ("is_pf_applicable", "is_pf_applicable", False),
                 ("is_esi_applicable", "is_esi_applicable", False)],
        extra_context={"state_choices": INDIAN_STATE_CHOICES},
    )


@login_required
def employeestatutoryidentifier_create(request):
    return crud_create(request, form_class=EmployeeStatutoryIdentifierForm,
                       template="hrm/statutory/employeestatutoryidentifier/form.html",
                       success_url="hrm:employeestatutoryidentifier_list")


@login_required
def employeestatutoryidentifier_detail(request, pk):
    return crud_detail(request, model=EmployeeStatutoryIdentifier, pk=pk,
                       template="hrm/statutory/employeestatutoryidentifier/detail.html",
                       select_related=("employee__party",))


@login_required
def employeestatutoryidentifier_edit(request, pk):
    return crud_edit(request, model=EmployeeStatutoryIdentifier, pk=pk,
                     form_class=EmployeeStatutoryIdentifierForm,
                     template="hrm/statutory/employeestatutoryidentifier/form.html",
                     success_url="hrm:employeestatutoryidentifier_list")


@login_required
@require_POST
def employeestatutoryidentifier_delete(request, pk):
    return crud_delete(request, model=EmployeeStatutoryIdentifier, pk=pk,
                       success_url="hrm:employeestatutoryidentifier_list")
