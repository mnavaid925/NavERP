import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.WorkflowAutomation.DocumentRoutingRules import (
    DocumentRoutingRuleForm,
    RoutingRuleSimulatorForm,
)
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.models.WorkflowAutomation.DocumentRoutingRules import DocumentRoutingRule
from apps.documents.services.workflow_automation import evaluate_routing_rules
from apps.documents.views._common import (
    documents_object,
    documents_scope,
    paginate_queryset,
    parse_int_param,
)


@login_required
def routing_rule_list(request):
    qs = documents_scope(
        DocumentRoutingRule.objects.select_related(
            "process_definition",
            "destination_folder",
            "route_to_org_unit",
            "route_to_role",
            "route_to_user",
        ).defer(
            "conditions_json",
            "else_action_json",
            "validation_rules_json",
            "auto_populate_json",
            "description",
            "process_definition__swimlanes_json",
            "process_definition__nodes_json",
            "process_definition__transitions_json",
            "process_definition__description",
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    rule_type = request.GET.get("rule_type", "").strip()
    if rule_type:
        qs = qs.filter(rule_type=rule_type)

    trigger_event = request.GET.get("trigger_event", "").strip()
    if trigger_event:
        qs = qs.filter(trigger_event=trigger_event)

    route_action = request.GET.get("route_action", "").strip()
    if route_action:
        qs = qs.filter(route_action=route_action)

    status = request.GET.get("status", "").strip()
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    process_definition_id, proc_int_id = parse_int_param(request.GET.get("process_definition"))
    if proc_int_id is not None:
        qs = qs.filter(process_definition_id=proc_int_id)

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(is_active=True)),
        total_matches=Sum("match_count"),
    )

    page_obj = paginate_queryset(qs, request, per_page=15)

    process_definitions = (
        DocumentProcessDefinition.objects.filter(tenant=request.tenant)
        .only("id", "code", "version_number", "name", "tenant_id")
        .order_by("code", "-version_number")
    )

    context = {
        "routing_rules": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": stats["total_count"] or 0,
        "active_count": stats["active_count"] or 0,
        "total_matches": stats["total_matches"] or 0,
        "rule_type_choices": DocumentRoutingRule.RULE_TYPE_CHOICES,
        "trigger_choices": DocumentRoutingRule.TRIGGER_EVENT_CHOICES,
        "route_action_choices": DocumentRoutingRule.ROUTE_ACTION_CHOICES,
        "process_definitions": process_definitions,
        "q": q,
        "rule_type": rule_type,
        "trigger_event": trigger_event,
        "route_action": route_action,
        "status": status,
        "process_definition": process_definition_id,
    }
    return render(request, "documents/workflow_automation/routing_rule/list.html", context)


@login_required
def routing_rule_detail(request, pk):
    rule = documents_object(
        request,
        DocumentRoutingRule,
        pk,
        select_related=(
            "process_definition",
            "core_rule_ref",
            "source_folder",
            "destination_folder",
            "route_to_org_unit",
            "route_to_role",
            "route_to_user",
            "owner",
        ),
    )
    context = {
        "rule": rule,
        "conditions": rule.conditions_json or [],
        "validation_rules": rule.validation_rules_json or [],
        "auto_populate": rule.auto_populate_json or {},
        "else_action": rule.else_action_json or {},
    }
    return render(request, "documents/workflow_automation/routing_rule/detail.html", context)


@login_required
@tenant_admin_required
def routing_rule_create(request):
    if request.method == "POST":
        form = DocumentRoutingRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                rule = form.save(commit=False)
                rule.tenant = request.tenant
                rule.owner = request.user
                rule.save()
                write_audit_log(request.user, rule, "create", tenant=request.tenant)
            messages.success(request, f"Routing rule {rule.number} created.")
            return redirect("documents:routing_rule_detail", pk=rule.pk)
    else:
        initial = {}
        _, proc_id = parse_int_param(request.GET.get("process_definition"))
        if proc_id is not None:
            initial["process_definition"] = proc_id
        initial["conditions_json"] = json.dumps(
            [{"source": "document", "field": "classification", "op": "eq", "value": "confidential"}],
            indent=2,
        )
        initial["auto_populate_json"] = json.dumps({"document_fields": {}, "metadata_fields": {}}, indent=2)
        initial["validation_rules_json"] = "[]"
        initial["else_action_json"] = "{}"
        form = DocumentRoutingRuleForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "rule": None,
        "is_edit": False,
    }
    return render(request, "documents/workflow_automation/routing_rule/form.html", context)


@login_required
@tenant_admin_required
def routing_rule_edit(request, pk):
    rule = documents_object(request, DocumentRoutingRule, pk)
    if request.method == "POST":
        form = DocumentRoutingRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                updated = form.save()
                write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Routing rule {updated.number} updated.")
            return redirect("documents:routing_rule_detail", pk=updated.pk)
    else:
        form = DocumentRoutingRuleForm(
            instance=rule,
            tenant=request.tenant,
            initial={
                "conditions_json": json.dumps(rule.conditions_json or [], indent=2),
                "else_action_json": json.dumps(rule.else_action_json or {}, indent=2),
                "validation_rules_json": json.dumps(rule.validation_rules_json or [], indent=2),
                "auto_populate_json": json.dumps(rule.auto_populate_json or {}, indent=2),
            },
        )

    context = {
        "form": form,
        "rule": rule,
        "is_edit": True,
    }
    return render(request, "documents/workflow_automation/routing_rule/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def routing_rule_delete(request, pk):
    rule = documents_object(request, DocumentRoutingRule, pk)
    number = rule.number
    with transaction.atomic():
        write_audit_log(request.user, rule, "delete", tenant=request.tenant)
        rule.delete()
    messages.success(request, f"Routing rule {number} deleted.")
    return redirect("documents:routing_rule_list")


@login_required
@require_POST
@tenant_admin_required
def routing_rule_toggle(request, pk):
    rule = documents_object(request, DocumentRoutingRule, pk)
    with transaction.atomic():
        rule.is_active = not rule.is_active
        rule.save(update_fields=["is_active", "updated_at"])
        write_audit_log(request.user, rule, "toggle", tenant=request.tenant)
    state_label = "activated" if rule.is_active else "paused"
    messages.success(request, f"Routing rule {rule.number} {state_label}.")
    return redirect("documents:routing_rule_detail", pk=rule.pk)


@login_required
def routing_rule_simulator(request):
    selected_document = None
    evaluation_results = []
    applied_summary = []

    if request.method == "POST":
        form = RoutingRuleSimulatorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            selected_document = form.cleaned_data["document"]
            selected_rule = form.cleaned_data.get("rule")
            trigger_event = form.cleaned_data.get("trigger_event") or None
            apply_mutations = bool(form.cleaned_data.get("apply_mutations"))
            if apply_mutations and not (
                request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
            ):
                messages.error(request, "Tenant administrator privileges are required to apply live rule mutations.")
                apply_mutations = False

            rules_arg = [selected_rule] if selected_rule else None
            evaluation_results = evaluate_routing_rules(
                tenant=request.tenant,
                document=selected_document,
                rules=rules_arg,
                trigger_event=trigger_event,
                apply_mutations=apply_mutations,
                actor=request.user,
                request=request,
            )
            for item in evaluation_results:
                if item["applied_actions"]:
                    applied_summary.append(
                        f"{item['rule'].number}: {', '.join(item['applied_actions'])}"
                    )
            blocked_rules = [
                item["rule"].number for item in evaluation_results if item["validation_errors"]
            ]
            if apply_mutations:
                write_audit_log(request.user, selected_document, "eval", tenant=request.tenant)
                if blocked_rules:
                    messages.warning(
                        request,
                        f"Evaluated {selected_document.number}, but validation gates blocked: {', '.join(blocked_rules)}.",
                    )
                else:
                    messages.success(
                        request,
                        f"Evaluated and applied routing rules against {selected_document.number}.",
                    )
            elif blocked_rules:
                messages.warning(
                    request,
                    f"Dry-run validation gates flagged blockers for {selected_document.number}: {', '.join(blocked_rules)}.",
                )
    else:
        initial = {}
        _, rule_id = parse_int_param(request.GET.get("rule"))
        if rule_id is not None:
            initial["rule"] = rule_id
        _, doc_id = parse_int_param(request.GET.get("document"))
        if doc_id is not None:
            initial["document"] = doc_id
        form = RoutingRuleSimulatorForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "selected_document": selected_document,
        "evaluation_results": evaluation_results,
        "applied_summary": applied_summary,
    }
    return render(request, "documents/workflow_automation/routing_rule/simulator.html", context)
