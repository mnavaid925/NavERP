"""CRM 1.11 Customer Success & Retention — OnboardingPlans views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    OnboardingPlan,
    OnboardingStep,
)
from apps.crm.forms import (
    OnboardingPlanForm,
    OnboardingStepForm,
)


# ------------------------------------------------------------ 1.11 Onboarding plans
@login_required
def onboardingplan_list(request):
    return crud_list(
        request,
        OnboardingPlan.objects.filter(tenant=request.tenant).select_related("account", "owner").prefetch_related("steps"),
        "crm/success/onboardingplan/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("account", "account_id", True)],
        extra_context={"status_choices": OnboardingPlan.STATUS_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def onboardingplan_create(request):
    return crud_create(request, form_class=OnboardingPlanForm,
                       template="crm/success/onboardingplan/form.html", success_url="crm:onboardingplan_list")


@login_required
def onboardingplan_detail(request, pk):
    obj = get_object_or_404(OnboardingPlan.objects.select_related("account", "owner"),
                            pk=pk, tenant=request.tenant)
    steps = list(obj.steps.select_related("assignee").all())
    done = sum(1 for s in steps if s.completed_at is not None)
    return render(request, "crm/success/onboardingplan/detail.html", {
        "obj": obj,
        "steps": steps,
        "progress_pct": round(done / len(steps) * 100) if steps else 0,  # from the already-fetched steps
        "step_form": OnboardingStepForm(tenant=request.tenant),
    })


@login_required
def onboardingplan_edit(request, pk):
    return crud_edit(request, model=OnboardingPlan, pk=pk, form_class=OnboardingPlanForm,
                     template="crm/success/onboardingplan/form.html", success_url="crm:onboardingplan_list")


@login_required
@require_POST
def onboardingplan_delete(request, pk):
    return crud_delete(request, model=OnboardingPlan, pk=pk, success_url="crm:onboardingplan_list")


@login_required
@require_POST
def onboardingstep_add(request, pk):
    plan = get_object_or_404(OnboardingPlan, pk=pk, tenant=request.tenant)
    form = OnboardingStepForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        step = form.save(commit=False)
        step.tenant = request.tenant
        step.plan = plan
        step.order = plan.steps.count()  # append after existing steps
        step.save()
        messages.success(request, "Step added.")
    else:
        messages.error(request, "Could not add step — a title is required.")
    return redirect("crm:onboardingplan_detail", pk=plan.pk)


@login_required
@require_POST
def onboardingstep_complete(request, step_pk):
    step = get_object_or_404(OnboardingStep.objects.select_related("plan"),
                             pk=step_pk, tenant=request.tenant)
    step.completed_at = None if step.completed_at else timezone.now()  # toggle
    step.save(update_fields=["completed_at"])
    plan = step.plan
    if not plan.steps.filter(tenant=request.tenant, completed_at__isnull=True).exists():
        plan.status = "completed"
        plan.completed_at = timezone.now()
        plan.save(update_fields=["status", "completed_at", "updated_at"])
    return redirect("crm:onboardingplan_detail", pk=step.plan_id)


@login_required
@require_POST
def onboardingstep_delete(request, step_pk):
    step = get_object_or_404(OnboardingStep, pk=step_pk, tenant=request.tenant)
    plan_id = step.plan_id
    step.delete()
    messages.success(request, "Step removed.")
    return redirect("crm:onboardingplan_detail", pk=plan_id)


@login_required
def onboardingstep_edit(request, step_pk):
    """Edit a plan step's title/description/assignee/due date (the missing CRUD piece)."""
    step = get_object_or_404(OnboardingStep.objects.select_related("plan"), pk=step_pk, tenant=request.tenant)
    if request.method == "POST":
        form = OnboardingStepForm(request.POST, instance=step, tenant=request.tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Step updated.")
            return redirect("crm:onboardingplan_detail", pk=step.plan_id)
    else:
        form = OnboardingStepForm(instance=step, tenant=request.tenant)
    return render(request, "crm/success/onboardingstep/form.html", {"form": form, "step": step})
