"""HRM 3.6 Candidate Management — Emailtemplate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    CandidateEmailTemplate,
    EMAIL_TEMPLATE_TYPE_CHOICES,
)
from apps.hrm.forms import (
    CandidateEmailTemplateForm,
)


# --------------------------------------------------------------- Candidate Email Templates (3.6)
@login_required
def emailtemplate_list(request):
    return crud_list(
        request, CandidateEmailTemplate.objects.filter(tenant=request.tenant),
        "hrm/candidates/emailtemplate/list.html",
        search_fields=["name", "subject", "number"],
        filters=[("type", "template_type", False), ("active", "is_active", False)],
        extra_context={"type_choices": EMAIL_TEMPLATE_TYPE_CHOICES})


@tenant_admin_required  # templates auto-fire to external candidate emails — admin-authored only
def emailtemplate_create(request):
    return crud_create(request, form_class=CandidateEmailTemplateForm,
                       template="hrm/candidates/emailtemplate/form.html",
                       success_url="hrm:emailtemplate_list")


@login_required
def emailtemplate_detail(request, pk):
    return crud_detail(request, model=CandidateEmailTemplate, pk=pk,
                       template="hrm/candidates/emailtemplate/detail.html")


@tenant_admin_required  # templates auto-fire to external candidate emails — admin-authored only
def emailtemplate_edit(request, pk):
    return crud_edit(request, model=CandidateEmailTemplate, pk=pk, form_class=CandidateEmailTemplateForm,
                     template="hrm/candidates/emailtemplate/form.html",
                     success_url="hrm:emailtemplate_list")


@tenant_admin_required
@require_POST
def emailtemplate_delete(request, pk):
    return crud_delete(request, model=CandidateEmailTemplate, pk=pk, success_url="hrm:emailtemplate_list")
