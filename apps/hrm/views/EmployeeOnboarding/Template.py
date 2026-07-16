"""HRM 3.3 Employee Onboarding — Template views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    OnboardingProgram,
    OnboardingTemplate,
)
from apps.hrm.forms import (
    OnboardingTemplateForm,
)


# ============================================================ Onboarding Templates (3.3)
@login_required
def onboardingtemplate_list(request):
    return crud_list(
        request,
        OnboardingTemplate.objects.filter(tenant=request.tenant).select_related("designation")
        .annotate(task_count=Count("template_tasks")).order_by("name"),
        "hrm/onboarding/template/list.html",
        search_fields=["number", "name", "designation__name"],
        filters=[("is_active", "is_active", False), ("designation", "designation_id", True)],
        extra_context={"designations": Designation.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def onboardingtemplate_create(request):
    return crud_create(request, form_class=OnboardingTemplateForm,
                       template="hrm/onboarding/template/form.html",
                       success_url="hrm:onboardingtemplate_list")


@login_required
def onboardingtemplate_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplate.objects.select_related("designation"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/template/detail.html", {
        "obj": obj,
        "tasks": obj.template_tasks.order_by("phase", "order", "title"),
        "program_count": OnboardingProgram.objects.filter(tenant=request.tenant, template=obj).count(),
    })


@login_required
def onboardingtemplate_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplate, pk=pk, form_class=OnboardingTemplateForm,
                     template="hrm/onboarding/template/form.html",
                     success_url="hrm:onboardingtemplate_list")


@login_required
@require_POST
def onboardingtemplate_delete(request, pk):
    obj = get_object_or_404(OnboardingTemplate, pk=pk, tenant=request.tenant)
    # Guard: a template still referenced by programs is kept (SET_NULL would orphan the link).
    if OnboardingProgram.objects.filter(tenant=request.tenant, template=obj).exists():
        messages.error(request, "Cannot delete a template that has onboarding programs. "
                                "Deactivate it instead.")
        return redirect("hrm:onboardingtemplate_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Onboarding template deleted.")
    return redirect("hrm:onboardingtemplate_list")
