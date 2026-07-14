"""CRM 1.11 Customer Success & Retention — OnboardingTemplates views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    OnboardingPlan,
    OnboardingStep,
    OnboardingTemplate,
    OnboardingTemplateStep,
)
from apps.crm.forms import (
    OnboardingTemplateForm,
    OnboardingTemplateStepForm,
)


# ------------------------------------------------------------ 1.11 Onboarding templates (reusable blueprints)
@login_required
def onboardingtemplate_list(request):
    return crud_list(
        request,
        OnboardingTemplate.objects.filter(tenant=request.tenant).annotate(n_steps=Count("steps")).order_by("-created_at"),
        "crm/success/onboardingtemplate/list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False)],
    )


@tenant_admin_required  # template authoring = the shared org blueprint library (security-review)
def onboardingtemplate_create(request):
    return crud_create(request, form_class=OnboardingTemplateForm,
                       template="crm/success/onboardingtemplate/form.html", success_url="crm:onboardingtemplate_list")


@login_required
def onboardingtemplate_detail(request, pk):
    obj = get_object_or_404(OnboardingTemplate, pk=pk, tenant=request.tenant)
    return render(request, "crm/success/onboardingtemplate/detail.html", {
        "obj": obj,
        "steps": list(obj.steps.all()),
        "step_form": OnboardingTemplateStepForm(tenant=request.tenant),
        "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name"),
    })


@tenant_admin_required  # shared blueprint library (security-review)
def onboardingtemplate_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplate, pk=pk, form_class=OnboardingTemplateForm,
                     template="crm/success/onboardingtemplate/form.html", success_url="crm:onboardingtemplate_list")


@tenant_admin_required  # shared blueprint library (security-review)
@require_POST
def onboardingtemplate_delete(request, pk):
    return crud_delete(request, model=OnboardingTemplate, pk=pk, success_url="crm:onboardingtemplate_list")


@tenant_admin_required  # shared blueprint library (security-review)
@require_POST
def onboardingtemplatestep_add(request, pk):
    template = get_object_or_404(OnboardingTemplate, pk=pk, tenant=request.tenant)
    form = OnboardingTemplateStepForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        step = form.save(commit=False)
        step.tenant = request.tenant
        step.template = template
        step.order = template.steps.count()  # append after existing steps
        step.save()
        messages.success(request, "Template step added.")
    else:
        messages.error(request, "Could not add step — a title is required.")
    return redirect("crm:onboardingtemplate_detail", pk=template.pk)


@tenant_admin_required  # shared blueprint library (security-review)
def onboardingtemplatestep_edit(request, step_pk):
    step = get_object_or_404(OnboardingTemplateStep.objects.select_related("template"),
                             pk=step_pk, tenant=request.tenant)
    if request.method == "POST":
        form = OnboardingTemplateStepForm(request.POST, instance=step, tenant=request.tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Template step updated.")
            return redirect("crm:onboardingtemplate_detail", pk=step.template_id)
    else:
        form = OnboardingTemplateStepForm(instance=step, tenant=request.tenant)
    return render(request, "crm/success/onboardingtemplatestep/form.html", {"form": form, "step": step})


@tenant_admin_required  # shared blueprint library (security-review)
@require_POST
def onboardingtemplatestep_delete(request, step_pk):
    step = get_object_or_404(OnboardingTemplateStep, pk=step_pk, tenant=request.tenant)
    template_id = step.template_id
    step.delete()
    messages.success(request, "Template step removed.")
    return redirect("crm:onboardingtemplate_detail", pk=template_id)


@login_required
@require_POST
def onboardingtemplate_apply(request, pk):
    """Clone an active template's steps into a brand-new OnboardingPlan for a chosen tenant account."""
    template = get_object_or_404(OnboardingTemplate, pk=pk, tenant=request.tenant)
    if not template.is_active:
        messages.error(request, "This template is inactive — activate it before applying.")
        return redirect("crm:onboardingtemplate_detail", pk=template.pk)
    account_id = (request.POST.get("account") or "").strip()
    if not account_id.isdigit():
        messages.error(request, "Choose an account to apply the template to.")
        return redirect("crm:onboardingtemplate_detail", pk=template.pk)
    account = get_object_or_404(Party, pk=int(account_id), tenant=request.tenant)  # tenant-scoped → cross-tenant 404
    template_steps = list(template.steps.all())
    if not template_steps:
        messages.error(request, "This template has no steps to apply.")
        return redirect("crm:onboardingtemplate_detail", pk=template.pk)
    today = timezone.now().date()
    with transaction.atomic():
        plan = OnboardingPlan.objects.create(
            tenant=request.tenant, account=account, owner=request.user, name=template.name,
            status="active", description=f"Created from template {template.number}.")
        OnboardingStep.objects.bulk_create([
            OnboardingStep(tenant=request.tenant, plan=plan, order=ts.order, title=ts.title,
                           description=ts.description, due_date=today + timedelta(days=ts.offset_days))
            for ts in template_steps
        ])
        write_audit_log(request.user, plan, "create")
    messages.success(request, f"Onboarding plan {plan.number} created from template ({len(template_steps)} steps).")
    return redirect("crm:onboardingplan_detail", pk=plan.pk)
