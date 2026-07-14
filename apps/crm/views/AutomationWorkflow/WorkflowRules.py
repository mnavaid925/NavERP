"""CRM 1.10 Automation & Workflow Engine — WorkflowRules views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    WorkflowLog,
    WorkflowRule,
)
from apps.crm.forms import (
    WorkflowRuleForm,
)
from ._engine import _run_rule


# ------------------------------------------------------------ 1.10 Workflow rules
@login_required
def workflowrule_list(request):
    return crud_list(
        request,
        WorkflowRule.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/workflow/workflowrule/list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False), ("trigger_entity", "trigger_entity", False)],
        extra_context={"entity_choices": WorkflowRule.ENTITY_CHOICES,
                       "event_choices": WorkflowRule.EVENT_CHOICES},
    )


@tenant_admin_required  # rule authoring = executable automation config; match the run gate (security-review)
def workflowrule_create(request):
    return crud_create(request, form_class=WorkflowRuleForm, template="crm/workflow/workflowrule/form.html",
                       success_url="crm:workflowrule_list")


@login_required
def workflowrule_detail(request, pk):
    obj = get_object_or_404(WorkflowRule.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/workflowrule/detail.html", {
        "obj": obj,
        "logs": WorkflowLog.objects.filter(tenant=request.tenant, rule=obj).order_by("-fired_at")[:10],
    })


@tenant_admin_required  # automation config (security-review)
def workflowrule_edit(request, pk):
    return crud_edit(request, model=WorkflowRule, pk=pk, form_class=WorkflowRuleForm,
                     template="crm/workflow/workflowrule/form.html", success_url="crm:workflowrule_list")


@tenant_admin_required  # automation config (security-review)
@require_POST
def workflowrule_delete(request, pk):
    return crud_delete(request, model=WorkflowRule, pk=pk, success_url="crm:workflowrule_list")


@tenant_admin_required
@require_POST
def workflowrule_run(request, pk):
    """1.10 — manually run a rule now (evaluate conditions + fire actions over recent records, bounded)."""
    rule = get_object_or_404(WorkflowRule, pk=pk, tenant=request.tenant)
    if not rule.is_active:
        messages.error(request, "Activate the rule before running it.")
        return redirect("crm:workflowrule_detail", pk=pk)
    s = _run_rule(rule, request.user)
    write_audit_log(request.user, rule, "update", {"action": "run", **s})
    messages.success(request, f"Ran {rule.number}: {s['matched']}/{s['evaluated']} matched, "
                              f"{s['actions']} action(s) fired.")
    return redirect("crm:workflowrule_detail", pk=pk)
