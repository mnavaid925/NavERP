"""HRM 3.39 Compliance & Legal — Complianceregister views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    ComplianceRegister,
)
from apps.hrm.forms import (
    ComplianceRegisterForm,
)


# ---- Compliance register (statutory / labour-law) ----------------------------------------------
@tenant_admin_required
def complianceregister_list(request):
    qs = ComplianceRegister.objects.filter(tenant=request.tenant).defer("findings", "notes")
    if request.GET.get("overdue", "").strip() == "1":
        qs = qs.filter(due_date__lt=timezone.localdate()).exclude(status__in=("filed", "not_applicable"))
    return crud_list(request, qs, "hrm/compliance/complianceregister/list.html",
                     search_fields=["number", "title", "jurisdiction", "authority", "findings"],
                     filters=[("register_type", "register_type", False), ("status", "status", False)],
                     extra_context={"register_type_choices": ComplianceRegister.REGISTER_TYPE_CHOICES,
                                    "status_choices": ComplianceRegister.STATUS_CHOICES})


@tenant_admin_required
def complianceregister_create(request):
    return crud_create(request, form_class=ComplianceRegisterForm,
                       template="hrm/compliance/complianceregister/form.html",
                       success_url="hrm:complianceregister_list")


@tenant_admin_required
def complianceregister_detail(request, pk):
    return crud_detail(request, model=ComplianceRegister, pk=pk,
                       template="hrm/compliance/complianceregister/detail.html")


@tenant_admin_required
def complianceregister_edit(request, pk):
    return crud_edit(request, model=ComplianceRegister, pk=pk, form_class=ComplianceRegisterForm,
                     template="hrm/compliance/complianceregister/form.html",
                     success_url="hrm:complianceregister_list")


@tenant_admin_required
@require_POST
def complianceregister_delete(request, pk):
    return crud_delete(request, model=ComplianceRegister, pk=pk,
                       success_url="hrm:complianceregister_list")
