"""HRM 3.39 Compliance & Legal — Employmentcontract views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmploymentContract,
)
from apps.hrm.forms import (
    EmploymentContractForm,
)
from apps.hrm.views.PersonalInformation._helpers import _ss_employees


# ---- Employment contracts (admin-managed) -----------------------------------------------------
@tenant_admin_required
def employmentcontract_list(request):
    qs = (EmploymentContract.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "designation")
          .defer("notes"))  # not rendered in the list
    if request.GET.get("expiring", "").strip() == "1":
        # Active contracts whose end date falls inside the expiring-soon window (computed in ORM).
        today = timezone.localdate()
        horizon = today + timedelta(days=EmploymentContract.EXPIRING_SOON_DAYS)
        qs = qs.filter(status="active", end_date__gte=today, end_date__lte=horizon)
    return crud_list(request, qs, "hrm/compliance/employmentcontract/list.html",
                     search_fields=["number", "employee__party__name", "notes"],
                     filters=[("status", "status", False), ("contract_type", "contract_type", False),
                              ("employee", "employee_id", True)],
                     extra_context={"status_choices": EmploymentContract.STATUS_CHOICES,
                                    "contract_type_choices": EmploymentContract.CONTRACT_TYPE_CHOICES,
                                    "employees": _ss_employees(request)})


@tenant_admin_required
def employmentcontract_create(request):
    return crud_create(request, form_class=EmploymentContractForm,
                       template="hrm/compliance/employmentcontract/form.html",
                       success_url="hrm:employmentcontract_list")


@tenant_admin_required
def employmentcontract_detail(request, pk):
    return crud_detail(request, model=EmploymentContract, pk=pk,
                       template="hrm/compliance/employmentcontract/detail.html",
                       select_related=("employee__party", "designation", "salary_structure", "renewed_from"))


@tenant_admin_required
def employmentcontract_edit(request, pk):
    return crud_edit(request, model=EmploymentContract, pk=pk, form_class=EmploymentContractForm,
                     template="hrm/compliance/employmentcontract/form.html",
                     success_url="hrm:employmentcontract_list")


@tenant_admin_required
@require_POST
def employmentcontract_delete(request, pk):
    return crud_delete(request, model=EmploymentContract, pk=pk, success_url="hrm:employmentcontract_list")
