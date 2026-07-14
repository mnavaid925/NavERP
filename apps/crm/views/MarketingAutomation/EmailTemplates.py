"""CRM 1.3 Marketing Automation — EmailTemplates views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    EmailTemplate,
)
from apps.crm.forms import (
    EmailTemplateForm,
)


# ------------------------------------------------------------ Email templates (1.3)
@login_required
def emailtemplate_list(request):
    return crud_list(
        request,
        # defer the large HTML body — it's never shown on the list.
        EmailTemplate.objects.filter(tenant=request.tenant).select_related("owner").defer("body"),
        "crm/marketing/emailtemplate/list.html",
        search_fields=["number", "name", "subject"],
        filters=[("category", "category", False), ("is_active", "is_active", False)],
        extra_context={"category_choices": EmailTemplate.CATEGORY_CHOICES},
    )


@login_required
def emailtemplate_create(request):
    return crud_create(request, form_class=EmailTemplateForm,
                       template="crm/marketing/emailtemplate/form.html",
                       success_url="crm:emailtemplate_list")


@login_required
def emailtemplate_detail(request, pk):
    obj = get_object_or_404(EmailTemplate.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/emailtemplate/detail.html", {"obj": obj})


@login_required
def emailtemplate_edit(request, pk):
    return crud_edit(request, model=EmailTemplate, pk=pk, form_class=EmailTemplateForm,
                     template="crm/marketing/emailtemplate/form.html",
                     success_url="crm:emailtemplate_list")


@login_required
@require_POST
def emailtemplate_delete(request, pk):
    return crud_delete(request, model=EmailTemplate, pk=pk, success_url="crm:emailtemplate_list")
