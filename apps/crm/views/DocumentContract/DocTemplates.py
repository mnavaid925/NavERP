"""CRM 1.9 Document & Contract Management — DocTemplates views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ContractDocument,
    DocTemplate,
)
from apps.crm.forms import (
    DocTemplateForm,
)


# ------------------------------------------------------------ 1.9 Document templates
@login_required
def doctemplate_list(request):
    return crud_list(
        request,
        DocTemplate.objects.filter(tenant=request.tenant).select_related("owner").defer("body"),
        "crm/documents/doctemplate/list.html",
        search_fields=["number", "name"],
        filters=[("template_type", "template_type", False), ("is_active", "is_active", False)],
        extra_context={"type_choices": DocTemplate.TYPE_CHOICES},
    )


@tenant_admin_required  # authoring a server-rendered template body is privileged (security-review)
def doctemplate_create(request):
    return crud_create(request, form_class=DocTemplateForm, template="crm/documents/doctemplate/form.html",
                       success_url="crm:doctemplate_list")


@login_required
def doctemplate_detail(request, pk):
    obj = get_object_or_404(DocTemplate.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/documents/doctemplate/detail.html", {
        "obj": obj,
        "contract_count": ContractDocument.objects.filter(tenant=request.tenant, template=obj).count(),
    })


@tenant_admin_required  # authoring a server-rendered template body is privileged (security-review)
def doctemplate_edit(request, pk):
    return crud_edit(request, model=DocTemplate, pk=pk, form_class=DocTemplateForm,
                     template="crm/documents/doctemplate/form.html", success_url="crm:doctemplate_list")


@tenant_admin_required  # symmetric with create/edit — template authoring is admin-only (security-review)
@require_POST
def doctemplate_delete(request, pk):
    return crud_delete(request, model=DocTemplate, pk=pk, success_url="crm:doctemplate_list")
