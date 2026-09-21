"""core — 0.11 views (workflow & approval administration).

The registry and the boards are admin-gated config surfaces. `process_monitor` is the one that reads
real data from other apps — it is still admin-gated, because a workspace's approval backlog is
operational information, not member-facing.
"""
import json

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.workflow import (
    APPROVAL_SOURCES,
    NON_QUEUE_SOURCES,
    approval_backlog,
    evaluate_condition,
    monitored_labels,
)
from apps.core.models import (
    ApprovalLimit,
    BusinessRule,
    BusinessRuleLog,
    SlaRule,
    WorkflowDefinition,
    WorkflowStep,
)
from apps.core.forms import (
    ApprovalLimitForm,
    BusinessRuleForm,
    SlaRuleForm,
    WorkflowDefinitionForm,
    WorkflowStepForm,
)


# =============================================================== bullets 1 + 2: the registry
@tenant_admin_required
def workflow_definition_list(request):
    return crud_list(
        request,
        WorkflowDefinition.objects.filter(tenant=request.tenant)
        .select_related("owner_role").annotate(step_count=Count("steps"))
        # An explicit order_by: `annotate()` with an aggregate leaves the queryset unordered for
        # pagination purposes, which raises UnorderedObjectListWarning and can yield inconsistent
        # pages. Meta.ordering alone is not enough here.
        .order_by("module_slug", "name"),
        "core/workflowdefinition/list.html",
        search_fields=["name", "module_slug", "engine_label", "description"],
        filters=[("module", "module_slug", False), ("active", "is_active", False)],
        extra_context={"active_choices": [("True", "Active"), ("False", "Inactive")],
                       "monitored": monitored_labels()},
    )


@tenant_admin_required
def workflow_definition_detail(request, pk):
    obj = get_object_or_404(
        WorkflowDefinition.objects.select_related("owner_role")
        .prefetch_related("steps__approver_role"),
        pk=pk, tenant=request.tenant)
    return render(request, "core/workflowdefinition/detail.html", {
        "obj": obj,
        "steps": obj.steps.all(),
        "is_monitored": obj.is_monitored,
        "sla_rules": SlaRule.objects.filter(tenant=request.tenant, module_slug=obj.module_slug),
        "limits": ApprovalLimit.objects.filter(tenant=request.tenant, module_slug=obj.module_slug)
        .select_related("role"),
    })


@tenant_admin_required
def workflow_definition_create(request):
    return crud_create(request, form_class=WorkflowDefinitionForm,
                       template="core/workflowdefinition/form.html",
                       success_url="core:workflow_definition_list")


@tenant_admin_required
def workflow_definition_edit(request, pk):
    return crud_edit(request, model=WorkflowDefinition, pk=pk, form_class=WorkflowDefinitionForm,
                     template="core/workflowdefinition/form.html",
                     success_url="core:workflow_definition_list")


@require_POST
@tenant_admin_required
def workflow_definition_delete(request, pk):
    return crud_delete(request, model=WorkflowDefinition, pk=pk,
                       success_url="core:workflow_definition_list")


@tenant_admin_required
def workflow_step_create(request, pk):
    """Add a step to a definition. The definition is fixed by the page it is reached from."""
    definition = get_object_or_404(WorkflowDefinition, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = WorkflowStepForm(request.POST, definition=definition, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.definition = definition
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Step added.")
            return redirect("core:workflow_definition_detail", pk=definition.pk)
    else:
        form = WorkflowStepForm(definition=definition, tenant=request.tenant)
    return render(request, "core/workflowstep/form.html", {"form": form, "definition": definition})


@tenant_admin_required
def workflow_step_edit(request, pk):
    return crud_edit(request, model=WorkflowStep, pk=pk, form_class=WorkflowStepForm,
                     template="core/workflowstep/form.html",
                     success_url="core:workflow_definition_list")


@require_POST
@tenant_admin_required
def workflow_step_delete(request, pk):
    obj = get_object_or_404(WorkflowStep, pk=pk, tenant=request.tenant)
    definition_pk = obj.definition_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Step removed.")
    return redirect("core:workflow_definition_detail", pk=definition_pk)


# =============================================================== bullet 2: approval limits
@tenant_admin_required
def approval_limit_list(request):
    return crud_list(
        request,
        ApprovalLimit.objects.filter(tenant=request.tenant).select_related("role"),
        "core/approvallimit/list.html",
        search_fields=["module_slug", "notes", "role__name"],
        filters=[("module", "module_slug", False)],
        extra_context={},
    )


@tenant_admin_required
def approval_limit_create(request):
    return crud_create(request, form_class=ApprovalLimitForm,
                       template="core/approvallimit/form.html",
                       success_url="core:approval_limit_list")


@tenant_admin_required
def approval_limit_edit(request, pk):
    return crud_edit(request, model=ApprovalLimit, pk=pk, form_class=ApprovalLimitForm,
                     template="core/approvallimit/form.html",
                     success_url="core:approval_limit_list")


@require_POST
@tenant_admin_required
def approval_limit_delete(request, pk):
    return crud_delete(request, model=ApprovalLimit, pk=pk, success_url="core:approval_limit_list")


# =============================================================== bullet 3: SLA rules
@tenant_admin_required
def sla_rule_list(request):
    return crud_list(
        request,
        SlaRule.objects.filter(tenant=request.tenant).select_related("escalate_to_role"),
        "core/slarule/list.html",
        search_fields=["name", "module_slug", "engine_label", "notes"],
        filters=[("module", "module_slug", False), ("action", "action", False)],
        extra_context={"action_choices": SlaRule.ACTION_CHOICES},
    )


@tenant_admin_required
def sla_rule_create(request):
    return crud_create(request, form_class=SlaRuleForm, template="core/slarule/form.html",
                       success_url="core:sla_rule_list")


@tenant_admin_required
def sla_rule_edit(request, pk):
    return crud_edit(request, model=SlaRule, pk=pk, form_class=SlaRuleForm,
                     template="core/slarule/form.html", success_url="core:sla_rule_list")


@require_POST
@tenant_admin_required
def sla_rule_delete(request, pk):
    return crud_delete(request, model=SlaRule, pk=pk, success_url="core:sla_rule_list")


# =============================================================== bullet 4: business rules
@tenant_admin_required
def business_rule_list(request):
    return crud_list(
        request,
        BusinessRule.objects.filter(tenant=request.tenant).annotate(log_count=Count("logs"))
        .order_by("priority", "name"),
        "core/businessrule/list.html",
        search_fields=["name", "module_slug", "notes"],
        filters=[("module", "module_slug", False), ("trigger", "trigger", False),
                 ("action", "action", False)],
        extra_context={"trigger_choices": BusinessRule.TRIGGER_CHOICES,
                       "action_choices": BusinessRule.ACTION_CHOICES},
    )


@tenant_admin_required
def business_rule_detail(request, pk):
    obj = get_object_or_404(BusinessRule, pk=pk, tenant=request.tenant)
    return render(request, "core/businessrule/detail.html", {
        "obj": obj,
        "logs": obj.logs.all()[:20],
        "log_count": obj.logs.count(),
    })


@tenant_admin_required
def business_rule_create(request):
    return crud_create(request, form_class=BusinessRuleForm,
                       template="core/businessrule/form.html",
                       success_url="core:business_rule_list")


@tenant_admin_required
def business_rule_edit(request, pk):
    return crud_edit(request, model=BusinessRule, pk=pk, form_class=BusinessRuleForm,
                     template="core/businessrule/form.html",
                     success_url="core:business_rule_list")


@require_POST
@tenant_admin_required
def business_rule_delete(request, pk):
    return crud_delete(request, model=BusinessRule, pk=pk,
                       success_url="core:business_rule_list")


@tenant_admin_required
def business_rule_test(request, pk):
    """Test-run a rule against a pasted context. The evaluation is REAL and it is logged.

    This is what makes the rules engine inspectable rather than aspirational: an operator can see
    exactly which clauses matched and which did not, before trusting the rule. It also demonstrates
    the boundary — the page reports the recommended action and does NOT perform it.
    """
    obj = get_object_or_404(BusinessRule, pk=pk, tenant=request.tenant)
    context_raw = '{\n  "amount": 15000\n}'
    result = None
    error = ""
    if request.method == "POST":
        context_raw = request.POST.get("context", "").strip()
        try:
            context = json.loads(context_raw or "{}")
        except ValueError as exc:
            error = "That is not valid JSON: %s" % exc
            context = None
        if context is not None and not isinstance(context, dict):
            error = "The context must be a JSON object."
            context = None
        if context is not None:
            matched, reasons = evaluate_condition(obj.condition, context)
            BusinessRuleLog.objects.create(
                tenant=request.tenant, rule=obj, module_slug=obj.module_slug, trigger=obj.trigger,
                context=context, matched=matched, evaluated_by=request.user,
                action_taken="" if not matched else "test run — no action performed",
            )
            result = {"matched": matched, "reasons": reasons, "context": context}
    return render(request, "core/businessrule/test.html",
                  {"obj": obj, "context_raw": context_raw, "result": result, "error": error})


@tenant_admin_required
def rule_log_list(request):
    return crud_list(
        request,
        BusinessRuleLog.objects.filter(tenant=request.tenant).select_related("rule", "evaluated_by"),
        "core/businessrulelog/list.html",
        search_fields=["module_slug", "action_taken", "rule__name"],
        filters=[("module", "module_slug", False), ("trigger", "trigger", False),
                 ("matched", "matched", False)],
        extra_context={"matched_choices": [("True", "Matched"), ("False", "No match")],
                       "trigger_choices": BusinessRule.TRIGGER_CHOICES},
    )


# =============================================================== bullet 5: monitoring
@tenant_admin_required
def process_monitor(request):
    """COMPUTED: the approval backlog read from the REAL tables of other apps.

    Nothing is stored. The board reports five genuine queues, three decision logs (which cannot have a
    backlog — see `apps/core/workflow.py`) and the four approval-ish models it deliberately does not
    treat as queues, each with its reason. It also cross-checks the registry: a `WorkflowDefinition`
    whose engine_label is not a monitored table is flagged, because a process nobody monitors is the
    thing this board exists to surface.
    """
    if request.tenant is None:
        messages.info(request, "Process monitoring applies to a tenant workspace.")
        return redirect("dashboard:home")
    backlog = approval_backlog(request.tenant)
    definitions = list(WorkflowDefinition.objects.filter(tenant=request.tenant)
                       .select_related("owner_role"))
    unmonitored = [d for d in definitions if d.is_active and not d.is_monitored]
    covered = sorted({d.engine_label for d in definitions if d.is_monitored})
    context = {
        "backlog": backlog,
        "queues": backlog["queues"],
        "decision_logs": backlog["decision_logs"],
        "skipped": backlog["skipped"],
        "definitions": definitions,
        "unmonitored": unmonitored,
        "covered_engines": covered,
        "monitored_count": len(monitored_labels()),
        "declared_count": len(APPROVAL_SOURCES) + len(NON_QUEUE_SOURCES),
    }
    return render(request, "core/processmonitor.html", context)


@tenant_admin_required
def workflow_overview(request):
    """COMPUTED hub for 0.11 — no table. Reports posture and names what is NOT built."""
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Workflow administration applies to a tenant workspace.")
        return redirect("dashboard:home")
    backlog = approval_backlog(tenant)
    context = {
        "definition_count": WorkflowDefinition.objects.filter(tenant=tenant).count(),
        "step_count": WorkflowStep.objects.filter(tenant=tenant).count(),
        "limit_count": ApprovalLimit.objects.filter(tenant=tenant).count(),
        "sla_count": SlaRule.objects.filter(tenant=tenant, is_active=True).count(),
        "rule_count": BusinessRule.objects.filter(tenant=tenant).count(),
        "rules_on": BusinessRule.objects.filter(tenant=tenant, is_active=True).count(),
        "log_count": BusinessRuleLog.objects.filter(tenant=tenant).count(),
        "matched_count": BusinessRuleLog.objects.filter(tenant=tenant, matched=True).count(),
        "total_open": backlog["total_open"],
        "total_breached": backlog["total_breached"],
        "queue_count": len(backlog["queues"]),
        "engines_in_repo": len(monitored_labels()),
        "recent_rules": BusinessRule.objects.filter(tenant=tenant).order_by("-created_at")[:5],
    }
    return render(request, "core/workflowoverview.html", context)
