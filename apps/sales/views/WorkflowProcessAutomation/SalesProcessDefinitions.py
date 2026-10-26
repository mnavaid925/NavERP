"""Sales 8.17 — SalesProcessDefinition views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Case, Lead, Opportunity
from apps.sales.forms.WorkflowProcessAutomation.SalesProcessDefinitions import (
    SalesProcessDefinitionForm,
)
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.WorkflowProcessAutomation.SalesAlertTriggers import SalesAlertTrigger
from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import (
    TARGET_ENTITY_CHOICES,
    SalesProcessDefinition,
)
from apps.sales.views.WorkflowProcessAutomation.SalesAlertTriggers import fire_alert_trigger
from apps.scm.models import SalesOrder

SPD_TARGET_MODELS = {
    "lead": Lead,
    "opportunity": Opportunity,
    "quote": CPQQuote,
    "order": SalesOrder,
    "case": Case,
    "contract": CustomerContract,
    "subscription": CustomerSubscription,
}
MAX_RUN_RECORDS = 100


def _evaluate_condition(record, condition):
    field = condition.get("field")
    operator = condition.get("operator")
    value = condition.get("value")
    actual = getattr(record, field, None)
    try:
        if operator == "eq":
            return actual == value
        if operator == "ne":
            return actual != value
        if operator == "in":
            return actual in (value or [])
        if operator == "not_in":
            return actual not in (value or [])
        if operator == "contains":
            return value in str(actual or "")
        if operator == "icontains":
            return str(value or "").lower() in str(actual or "").lower()
        if operator == "gt":
            return actual is not None and actual > value
        if operator == "gte":
            return actual is not None and actual >= value
        if operator == "lt":
            return actual is not None and actual < value
        if operator == "lte":
            return actual is not None and actual <= value
        if operator == "is_set":
            return bool(actual) is bool(value)
        if operator == "is_empty":
            return (actual in (None, "", [], {})) is bool(value)
    except TypeError:
        return False
    return False


@login_required
def sales_process_definition_list(request):
    tenant = request.tenant
    qs = SalesProcessDefinition.objects.filter(tenant=tenant).select_related("owner")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(number__icontains=q))

    status = request.GET.get("status", "").strip()
    if status in {value for value, _ in SalesProcessDefinition.STATUS_CHOICES}:
        qs = qs.filter(status=status)

    target_entity = request.GET.get("target_entity", "").strip()
    if target_entity in {value for value, _ in TARGET_ENTITY_CHOICES}:
        qs = qs.filter(target_entity=target_entity)

    trigger_event = request.GET.get("trigger_event", "").strip()
    if trigger_event in {value for value, _ in SalesProcessDefinition.TRIGGER_EVENT_CHOICES}:
        qs = qs.filter(trigger_event=trigger_event)

    page_obj = paginate(request, qs, 15)
    context = {
        "process_definitions": page_obj.object_list,
        "page_obj": page_obj,
        "status_choices": SalesProcessDefinition.STATUS_CHOICES,
        "target_entity_choices": TARGET_ENTITY_CHOICES,
        "trigger_event_choices": SalesProcessDefinition.TRIGGER_EVENT_CHOICES,
    }
    return render(request, "sales/workflowprocessautomation/salesprocessdefinition/list.html", context)


@login_required
def sales_process_definition_detail(request, pk):
    process_definition = get_object_or_404(
        SalesProcessDefinition.objects.filter(tenant=request.tenant).select_related(
            "owner", "job_definition"
        ),
        pk=pk,
    )
    context = {"process_definition": process_definition}
    return render(request, "sales/workflowprocessautomation/salesprocessdefinition/detail.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_process_definition_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = SalesProcessDefinitionForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.owner = request.user
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=tenant)
            messages.success(request, f"Process definition '{obj.name}' created.")
            return redirect("sales:sales_process_definition_detail", pk=obj.pk)
    else:
        form = SalesProcessDefinitionForm(tenant=tenant)

    context = {
        "form": form,
        "process_definition": None,
        "is_edit": False,
    }
    return render(request, "sales/workflowprocessautomation/salesprocessdefinition/form.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_process_definition_edit(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesProcessDefinition.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = SalesProcessDefinitionForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if "status" in form.changed_data:
                obj.version += 1
            obj.save()
            write_audit_log(request.user, obj, "update", tenant=tenant)
            messages.success(request, f"Process definition '{obj.name}' updated.")
            return redirect("sales:sales_process_definition_detail", pk=obj.pk)
    else:
        form = SalesProcessDefinitionForm(instance=obj, tenant=tenant)

    context = {
        "form": form,
        "process_definition": obj,
        "is_edit": True,
    }
    return render(request, "sales/workflowprocessautomation/salesprocessdefinition/form.html", context)


@login_required
@require_POST
@tenant_admin_required
@transaction.atomic
def sales_process_definition_delete(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesProcessDefinition.objects.filter(tenant=tenant), pk=pk)
    name = obj.name
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Process definition '{name}' deleted.")
    return redirect("sales:sales_process_definition_list")


@login_required
@require_POST
@tenant_admin_required
@transaction.atomic
def sales_process_definition_run(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesProcessDefinition.objects.filter(tenant=tenant), pk=pk)
    if obj.status != "active":
        messages.error(request, "Only an active process definition can run.")
        return redirect("sales:sales_process_definition_detail", pk=obj.pk)

    records = list(
        SPD_TARGET_MODELS[obj.target_entity].objects.filter(tenant=tenant).order_by("pk")[:MAX_RUN_RECORDS]
    )
    evaluated = len(records)
    matched = sum(
        1 for record in records if all(_evaluate_condition(record, c) for c in obj.conditions)
    )

    for node in obj.nodes:
        if node.get("type") != "notify":
            continue
        params = node.get("params") or {}
        # str() first: params arrive from JSON, so alert_trigger_id may legitimately be an
        # int; as_db_int() guards STRING input (L11) and must not be handed a bare int.
        trigger_id = as_db_int(str(params.get("alert_trigger_id")))
        if trigger_id is None:
            continue
        trigger = SalesAlertTrigger.objects.filter(tenant=tenant, pk=trigger_id).first()
        if trigger:
            fire_alert_trigger(trigger, user=request.user)

    write_audit_log(
        request.user,
        obj,
        "update",
        changes={
            "action": "process_run",
            "evaluated": str(evaluated),
            "matched": str(matched),
            "nodes": str(len(obj.nodes)),
        },
        tenant=tenant,
    )
    messages.success(request, f"Process '{obj.name}' evaluated {evaluated} record(s); {matched} matched.")
    return redirect("sales:sales_process_definition_detail", pk=obj.pk)
