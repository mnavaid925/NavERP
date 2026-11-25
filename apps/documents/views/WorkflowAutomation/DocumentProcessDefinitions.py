import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Role
from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.documents.forms.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinitionForm,
    ProcessDesignerForm,
)
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.services.workflow_automation import simulate_process_path
from apps.documents.views._common import documents_object, documents_scope

DEFAULT_SWIMLANES = [
    {"id": "intake", "name": "Document Intake", "color": "blue"},
    {"id": "review", "name": "Department & Legal Review", "color": "purple"},
]

DEFAULT_NODES = [
    {"id": "start", "type": "start_event", "label": "Trigger Intake", "lane_id": "intake", "sla_hours": 1},
    {"id": "classify", "type": "service_task", "label": "Auto-Classify & Validate", "lane_id": "intake", "sla_hours": 4},
    {"id": "gateway_risk", "type": "exclusive_gateway", "label": "Confidential?", "lane_id": "review", "sla_hours": 1},
    {"id": "legal_approve", "type": "approval_subprocess", "label": "Legal & Compliance Approval", "lane_id": "review", "sla_hours": 24},
    {"id": "end", "type": "end_event", "label": "Released & Published", "lane_id": "review", "sla_hours": 0},
]

DEFAULT_TRANSITIONS = [
    {"id": "t1", "from_node": "start", "to_node": "classify", "label": "Start", "is_default": True},
    {"id": "t2", "from_node": "classify", "to_node": "gateway_risk", "label": "Validated", "is_default": True},
    {
        "id": "t3",
        "from_node": "gateway_risk",
        "to_node": "legal_approve",
        "label": "Confidential / Restricted",
        "is_default": False,
        "condition": {"source": "document", "field": "classification", "op": "in", "value": ["confidential", "restricted"]},
    },
    {"id": "t4", "from_node": "gateway_risk", "to_node": "end", "label": "Standard Bypass", "is_default": True},
    {"id": "t5", "from_node": "legal_approve", "to_node": "end", "label": "Approved", "is_default": True},
]


@login_required
def process_definition_list(request):
    qs = documents_scope(
        DocumentProcessDefinition.objects.select_related(
            "owner", "department", "target_folder", "core_workflow_ref"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(process_category=category)

    trigger_event = request.GET.get("trigger_event", "").strip()
    if trigger_event:
        qs = qs.filter(trigger_event=trigger_event)

    department_id = request.GET.get("department", "").strip()
    if department_id and department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    total_count = qs.count()
    published_count = qs.filter(status="published").count()
    draft_count = qs.filter(status="draft").count()
    active_count = qs.filter(is_active=True).count()

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "process_definitions": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": total_count,
        "published_count": published_count,
        "draft_count": draft_count,
        "active_count": active_count,
        "status_choices": DocumentProcessDefinition.STATUS_CHOICES,
        "category_choices": DocumentProcessDefinition.PROCESS_CATEGORY_CHOICES,
        "trigger_choices": DocumentProcessDefinition.TRIGGER_EVENT_CHOICES,
        "departments": departments,
        "q": q,
        "status": status,
        "category": category,
        "trigger_event": trigger_event,
        "department": department_id,
    }
    return render(request, "documents/workflow_automation/process_definition/list.html", context)


@login_required
def process_definition_detail(request, pk):
    process_def = documents_object(
        request,
        DocumentProcessDefinition,
        pk,
        select_related=("owner", "department", "target_folder", "core_workflow_ref"),
        prefetch_related=("routing_rules", "webhook_triggers"),
    )
    validation_result = process_def.validate_graph()
    simulation_steps = simulate_process_path(process_def, context={"classification": "confidential"})
    routing_rules = process_def.routing_rules.filter(tenant=request.tenant).order_by("priority", "name")
    recent_instances = (
        process_def.instances.filter(tenant=request.tenant)
        .select_related("document", "initiated_by", "current_assignee")
        .order_by("-started_at", "-id")[:10]
    )
    webhooks = process_def.webhook_triggers.filter(tenant=request.tenant).order_by("name")

    context = {
        "process_def": process_def,
        "validation_result": validation_result,
        "simulation_steps": simulation_steps,
        "routing_rules": routing_rules,
        "recent_instances": recent_instances,
        "webhooks": webhooks,
    }
    return render(request, "documents/workflow_automation/process_definition/detail.html", context)


@login_required
def process_definition_create(request):
    if request.method == "POST":
        form = DocumentProcessDefinitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                proc = form.save(commit=False)
                proc.tenant = request.tenant
                proc.owner = request.user
                proc.status = "draft"
                if not proc.nodes_json:
                    proc.swimlanes_json = list(DEFAULT_SWIMLANES)
                    proc.nodes_json = list(DEFAULT_NODES)
                    proc.transitions_json = list(DEFAULT_TRANSITIONS)
                proc.save()
                write_audit_log(request.user, proc, "create", tenant=request.tenant)
            messages.success(request, f"Process definition {proc.number} created.")
            return redirect("documents:process_definition_detail", pk=proc.pk)
    else:
        form = DocumentProcessDefinitionForm(
            tenant=request.tenant,
            initial={
                "swimlanes_json": json.dumps(DEFAULT_SWIMLANES, indent=2),
                "nodes_json": json.dumps(DEFAULT_NODES, indent=2),
                "transitions_json": json.dumps(DEFAULT_TRANSITIONS, indent=2),
            },
        )

    context = {
        "form": form,
        "process_def": None,
        "is_edit": False,
    }
    return render(request, "documents/workflow_automation/process_definition/form.html", context)


def _is_tenant_admin(user):
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


@login_required
def process_definition_edit(request, pk):
    process_def = documents_object(request, DocumentProcessDefinition, pk)
    if process_def.status == "archived":
        messages.warning(request, "Archived process definitions cannot be edited.")
        return redirect("documents:process_definition_detail", pk=process_def.pk)
    if process_def.status == "published" and not _is_tenant_admin(request.user):
        raise PermissionDenied("Tenant administrator access required to edit published process definitions.")

    if request.method == "POST":
        form = DocumentProcessDefinitionForm(request.POST, instance=process_def, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                proc = form.save()
                write_audit_log(request.user, proc, "update", tenant=request.tenant)
            messages.success(request, f"Process definition {proc.number} updated.")
            return redirect("documents:process_definition_detail", pk=proc.pk)
    else:
        form = DocumentProcessDefinitionForm(
            instance=process_def,
            tenant=request.tenant,
            initial={
                "swimlanes_json": json.dumps(process_def.swimlanes_json or [], indent=2),
                "nodes_json": json.dumps(process_def.nodes_json or [], indent=2),
                "transitions_json": json.dumps(process_def.transitions_json or [], indent=2),
            },
        )

    context = {
        "form": form,
        "process_def": process_def,
        "is_edit": True,
    }
    return render(request, "documents/workflow_automation/process_definition/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def process_definition_delete(request, pk):
    process_def = documents_object(request, DocumentProcessDefinition, pk)
    if process_def.status != "draft":
        messages.error(request, "Only draft process definitions can be deleted.")
        return redirect("documents:process_definition_detail", pk=process_def.pk)
    if process_def.instances.exists():
        messages.error(request, "Cannot delete a process definition that has execution instances.")
        return redirect("documents:process_definition_detail", pk=process_def.pk)

    number = process_def.number
    with transaction.atomic():
        write_audit_log(request.user, process_def, "delete", tenant=request.tenant)
        process_def.delete()
    messages.success(request, f"Process definition {number} deleted.")
    return redirect("documents:process_definition_list")


@login_required
def process_definition_designer(request, pk):
    process_def = documents_object(
        request,
        DocumentProcessDefinition,
        pk,
        select_related=("owner", "department", "target_folder"),
    )
    can_edit_designer = process_def.status != "archived" and (
        process_def.status != "published" or _is_tenant_admin(request.user)
    )
    if request.method == "POST":
        if process_def.status == "archived":
            messages.error(request, "Archived process definitions cannot be modified in the designer.")
            return redirect("documents:process_definition_designer", pk=process_def.pk)
        if process_def.status == "published" and not _is_tenant_admin(request.user):
            raise PermissionDenied("Tenant administrator access required to modify published BPMN blueprints.")

        designer_form = ProcessDesignerForm(request.POST)
        if designer_form.is_valid():
            with transaction.atomic():
                process_def.swimlanes_json = designer_form.cleaned_data["swimlanes_json"]
                process_def.nodes_json = designer_form.cleaned_data["nodes_json"]
                process_def.transitions_json = designer_form.cleaned_data["transitions_json"]
                process_def.save(update_fields=["swimlanes_json", "nodes_json", "transitions_json", "updated_at"])
                write_audit_log(request.user, process_def, "design", tenant=request.tenant)
            messages.success(request, f"Visual BPMN blueprint saved for {process_def.number}.")
            return redirect("documents:process_definition_designer", pk=process_def.pk)
    else:
        designer_form = ProcessDesignerForm(
            initial={
                "swimlanes_json": json.dumps(process_def.swimlanes_json or [], indent=2),
                "nodes_json": json.dumps(process_def.nodes_json or [], indent=2),
                "transitions_json": json.dumps(process_def.transitions_json or [], indent=2),
            }
        )

    validation_result = process_def.validate_graph()
    simulation_steps = simulate_process_path(process_def, context={"classification": "confidential"})
    roles = Role.objects.filter(tenant=request.tenant).order_by("name")
    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
    swimlanes = process_def.swimlanes_json or []
    nodes = process_def.nodes_json or []
    lane_ids = {
        str(lane.get("id") or "").strip()
        for lane in swimlanes
        if isinstance(lane, dict) and lane.get("id")
    }
    unassigned_nodes = [
        node
        for node in nodes
        if isinstance(node, dict) and str(node.get("lane_id") or "").strip() not in lane_ids
    ]

    context = {
        "process_def": process_def,
        "designer_form": designer_form,
        "can_edit_designer": can_edit_designer,
        "swimlanes": swimlanes,
        "nodes": nodes,
        "unassigned_nodes": unassigned_nodes,
        "transitions": process_def.transitions_json or [],
        "validation_result": validation_result,
        "simulation_steps": simulation_steps,
        "roles": roles,
        "departments": departments,
    }
    return render(request, "documents/workflow_automation/process_definition/designer.html", context)


@login_required
@require_POST
@tenant_admin_required
def process_definition_publish(request, pk):
    process_def = documents_object(request, DocumentProcessDefinition, pk)
    if process_def.status == "archived":
        messages.error(request, "Archived process definitions cannot be published.")
        return redirect("documents:process_definition_detail", pk=process_def.pk)
    if process_def.status == "published":
        messages.info(request, f"Process definition {process_def.number} is already published.")
        return redirect("documents:process_definition_detail", pk=process_def.pk)

    validation = process_def.validate_graph()
    if not validation["is_valid"]:
        messages.error(request, f"Cannot publish invalid BPMN graph: {'; '.join(validation['errors'])}")
        return redirect("documents:process_definition_detail", pk=process_def.pk)

    with transaction.atomic():
        process_def.status = "published"
        process_def.is_active = True
        process_def.published_at = timezone.now()
        process_def.save(update_fields=["status", "is_active", "published_at", "updated_at"])
        write_audit_log(request.user, process_def, "publish", tenant=request.tenant)
    messages.success(request, f"Process definition {process_def.number} published.")
    return redirect("documents:process_definition_detail", pk=process_def.pk)


@login_required
@require_POST
@tenant_admin_required
def process_definition_deprecate(request, pk):
    process_def = documents_object(request, DocumentProcessDefinition, pk)
    if process_def.status != "published":
        messages.error(request, "Only published process definitions can be deprecated.")
        return redirect("documents:process_definition_detail", pk=process_def.pk)
    with transaction.atomic():
        process_def.status = "deprecated"
        process_def.is_active = False
        process_def.save(update_fields=["status", "is_active", "updated_at"])
        write_audit_log(request.user, process_def, "deprecate", tenant=request.tenant)
    messages.warning(request, f"Process definition {process_def.number} deprecated.")
    return redirect("documents:process_definition_detail", pk=process_def.pk)
