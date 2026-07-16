"""HRM 3.3 Employee Onboarding — Templatetask views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingTemplate,
    OnboardingTemplateTask,
    PHASE_CHOICES,
    TASK_CATEGORY_CHOICES,
)
from apps.hrm.forms import (
    OnboardingTemplateTaskForm,
)


# ============================================================ Onboarding Template Tasks (3.3)
@login_required
def onboardingtemplatetask_list(request):
    return crud_list(
        request,
        OnboardingTemplateTask.objects.filter(tenant=request.tenant).select_related("template"),
        "hrm/onboarding/templatetask/list.html",
        search_fields=["title", "description", "template__name"],
        filters=[("template", "template_id", True), ("phase", "phase", False),
                 ("task_category", "task_category", False)],
        extra_context={"templates": OnboardingTemplate.objects.filter(tenant=request.tenant).order_by("name"),
                       "phase_choices": PHASE_CHOICES,
                       "category_choices": TASK_CATEGORY_CHOICES},
    )


@login_required
def onboardingtemplatetask_create(request):
    return crud_create(request, form_class=OnboardingTemplateTaskForm,
                       template="hrm/onboarding/templatetask/form.html",
                       success_url="hrm:onboardingtemplatetask_list")


@login_required
def onboardingtemplatetask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplateTask.objects.select_related("template"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/templatetask/detail.html", {"obj": obj})


@login_required
def onboardingtemplatetask_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplateTask, pk=pk,
                     form_class=OnboardingTemplateTaskForm,
                     template="hrm/onboarding/templatetask/form.html",
                     success_url="hrm:onboardingtemplatetask_list")


@login_required
@require_POST
def onboardingtemplatetask_delete(request, pk):
    return crud_delete(request, model=OnboardingTemplateTask, pk=pk,
                       success_url="hrm:onboardingtemplatetask_list")
