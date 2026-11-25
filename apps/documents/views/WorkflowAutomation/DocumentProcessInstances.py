import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.documents.forms.WorkflowAutomation.DocumentProcessInstances import (
    DocumentProcessInstanceForm,
    ProcessAdvanceForm,
)
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.models.WorkflowAutomation.DocumentProcessInstances import (
    DocumentProcessInstance,
)
from apps.documents.services.workflow_automation import (
    advance_process_instance,
    cancel_process_instance,
    start_process_instance,
)
from apps.documents.views._common import (
    documents_object,
    documents_scope,
    paginate_queryset,
    parse_int_param,
)


def _is_tenant_admin(user):
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


def _can_advance_instance(user, instance):
    if _is_tenant_admin(user):
        return True
    if instance.current_assignee_id is not None:
        return instance.current_assignee_id == user.id
    return True


def _can_cancel_or_force_complete(user, instance):
    return _is_tenant_admin(user) or instance.initiated_by_id == user.id


@login_required
def process_instance_list(request):
    qs = documents_scope(
        DocumentProcessInstance.objects.select_related(
            "process_definition",
            "document",
            "current_assignee",
        ).defer(
            "step_trace_json",
            "context_variables_json",
            "error_message",
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
            Q(number__icontains=q)
            | Q(current_node_label__icontains=q)
            | Q(document__title__icontains=q)
            | Q(document__number__icontains=q)
            | Q(process_definition__name__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    process_definition_id, proc_int_id = parse_int_param(request.GET.get("process_definition"))
    if proc_int_id is not None:
        qs = qs.filter(process_definition_id=proc_int_id)

    department_id, dept_int_id = parse_int_param(request.GET.get("department"))
    if dept_int_id is not None:
        qs = qs.filter(department_id=dept_int_id)

    sla_breached = request.GET.get("sla_breached", "").strip()
    if sla_breached == "1":
        qs = qs.filter(is_sla_breached=True)
    elif sla_breached == "0":
        qs = qs.filter(is_sla_breached=False)

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count(
            "id",
            filter=Q(status__in=["queued", "running", "waiting_approval", "waiting_timer"]),
        ),
        completed_count=Count("id", filter=Q(status="completed")),
        sla_breached_count=Count("id", filter=Q(is_sla_breached=True)),
    )

    page_obj = paginate_queryset(qs, request, per_page=15)

    process_definitions = (
        DocumentProcessDefinition.objects.filter(tenant=request.tenant)
        .only("id", "code", "version_number", "name", "tenant_id")
        .order_by("code", "-version_number")
    )
    departments = (
        OrgUnit.objects.filter(tenant=request.tenant)
        .only("id", "name", "tenant_id")
        .order_by("name")
    )

    context = {
        "instances": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": stats["total_count"] or 0,
        "active_count": stats["active_count"] or 0,
        "completed_count": stats["completed_count"] or 0,
        "sla_breached_count": stats["sla_breached_count"] or 0,
        "sla_breached_count": sla_breached_count,
        "status_choices": DocumentProcessInstance.STATUS_CHOICES,
        "process_definitions": process_definitions,
        "departments": departments,
        "q": q,
        "status": status,
        "process_definition": process_definition_id,
        "department": department_id,
        "sla_breached": sla_breached,
    }
    return render(request, "documents/workflow_automation/process_instance/list.html", context)


@login_required
def process_instance_detail(request, pk):
    instance = documents_object(
        request,
        DocumentProcessInstance,
        pk,
        select_related=(
            "process_definition",
            "document",
            "version",
            "triggered_by_rule",
            "approval_workflow",
            "department",
            "initiated_by",
            "current_assignee",
        ),
    )
    can_force_complete = _can_cancel_or_force_complete(request.user, instance)
    is_terminal = instance.status in ("completed", "cancelled")
    can_advance = (not is_terminal) and _can_advance_instance(request.user, instance)
    can_cancel = (not is_terminal) and can_force_complete
    advance_form = ProcessAdvanceForm()
    if not can_force_complete:
        advance_form.fields["outcome"].choices = [
            choice for choice in ProcessAdvanceForm.OUTCOME_CHOICES if choice[0] != "completed"
        ]

    step_trace = instance.step_trace_json or []
    completed_node_ids = {
        str(step.get("node_id"))
        for step in step_trace
        if isinstance(step, dict) and step.get("node_id") and step.get("exited_at") is not None
    }
    context = {
        "instance": instance,
        "step_trace": step_trace,
        "blueprint_nodes": instance.process_definition.nodes_json or [],
        "completed_node_ids": completed_node_ids,
        "context_variables": json.dumps(instance.context_variables_json or {}, indent=2),
        "advance_form": advance_form,
        "can_advance": can_advance,
        "can_force_complete": can_force_complete,
        "can_cancel": can_cancel,
    }
    return render(request, "documents/workflow_automation/process_instance/detail.html", context)


@login_required
def process_instance_create(request):
    if request.method == "POST":
        form = DocumentProcessInstanceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cd = form.cleaned_data
            instance = start_process_instance(
                tenant=request.tenant,
                process_definition=cd["process_definition"],
                document=cd["document"],
                actor=request.user,
                version=cd.get("version"),
                department=cd.get("department"),
                assignee=cd.get("current_assignee"),
                context_variables=cd.get("context_variables_json") or {},
                request=request,
            )
            write_audit_log(request.user, instance, "create", tenant=request.tenant)
            messages.success(request, f"Process instance {instance.number} launched.")
            return redirect("documents:process_instance_detail", pk=instance.pk)
    else:
        initial = {}
        _, proc_id = parse_int_param(request.GET.get("process_definition"))
        if proc_id is not None:
            initial["process_definition"] = proc_id
        _, doc_id = parse_int_param(request.GET.get("document"))
        if doc_id is not None:
            initial["document"] = doc_id
        initial["context_variables_json"] = "{}"
        form = DocumentProcessInstanceForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "instance": None,
        "is_edit": False,
    }
    return render(request, "documents/workflow_automation/process_instance/form.html", context)


@login_required
def process_instance_edit(request, pk):
    instance = documents_object(request, DocumentProcessInstance, pk)
    if instance.status in ("completed", "cancelled"):
        messages.warning(request, "Completed or cancelled process instances cannot be edited.")
        return redirect("documents:process_instance_detail", pk=instance.pk)

    if request.method == "POST":
        form = DocumentProcessInstanceForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                updated = form.save()
                write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Process instance {updated.number} updated.")
            return redirect("documents:process_instance_detail", pk=updated.pk)
    else:
        form = DocumentProcessInstanceForm(
            instance=instance,
            tenant=request.tenant,
            initial={"context_variables_json": json.dumps(instance.context_variables_json or {}, indent=2)},
        )

    context = {
        "form": form,
        "instance": instance,
        "is_edit": True,
    }
    return render(request, "documents/workflow_automation/process_instance/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def process_instance_delete(request, pk):
    instance = documents_object(
        request,
        DocumentProcessInstance,
        pk,
        select_related=("tenant", "process_definition"),
    )
    if instance.status not in ("queued", "cancelled", "failed"):
        messages.error(request, "Only queued, cancelled, or failed instances can be deleted.")
        return redirect("documents:process_instance_detail", pk=instance.pk)

    number = instance.number
    proc_def_id = instance.process_definition_id
    with transaction.atomic():
        write_audit_log(request.user, instance, "delete", tenant=request.tenant)
        instance.delete()
        if proc_def_id:
            DocumentProcessDefinition.objects.filter(
                pk=proc_def_id, instance_count__gt=0
            ).update(instance_count=F("instance_count") - 1)
    messages.success(request, f"Process instance {number} deleted.")
    return redirect("documents:process_instance_list")


@login_required
@require_POST
def process_instance_advance(request, pk):
    instance = documents_object(
        request,
        DocumentProcessInstance,
        pk,
        select_related=("tenant", "process_definition", "document", "version", "current_assignee", "initiated_by"),
    )
    if not _can_advance_instance(request.user, instance):
        raise PermissionDenied("Only an administrator or the assigned owner may advance this step.")
    if request.POST.get("outcome") == "completed" and not _can_cancel_or_force_complete(request.user, instance):
        raise PermissionDenied("Only an administrator or the initiator may force-complete this process.")
    if instance.status in ("completed", "cancelled"):
        messages.warning(request, f"Instance {instance.number} is already {instance.get_status_display()}.")
        return redirect("documents:process_instance_detail", pk=instance.pk)

    form = ProcessAdvanceForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            instance = advance_process_instance(
                instance,
                outcome=form.cleaned_data["outcome"],
                actor=request.user,
                notes=form.cleaned_data.get("notes", ""),
                request=request,
            )
            write_audit_log(request.user, instance, "advance", tenant=request.tenant)
        messages.success(request, f"Process instance {instance.number} transitioned ({instance.get_status_display()}).")
    else:
        messages.error(request, "Invalid step transition parameters.")
    return redirect("documents:process_instance_detail", pk=instance.pk)


@login_required
@require_POST
def process_instance_cancel(request, pk):
    instance = documents_object(
        request,
        DocumentProcessInstance,
        pk,
        select_related=("tenant", "process_definition", "initiated_by"),
    )
    if not _can_cancel_or_force_complete(request.user, instance):
        raise PermissionDenied("Only an administrator or the initiator may cancel this process.")
    if instance.status in ("completed", "cancelled"):
        messages.warning(request, "Completed or cancelled process instances cannot be cancelled.")
        return redirect("documents:process_instance_detail", pk=instance.pk)

    with transaction.atomic():
        instance = cancel_process_instance(instance, actor=request.user, request=request)
        write_audit_log(request.user, instance, "cancel", tenant=request.tenant)
    messages.info(request, f"Process instance {instance.number} cancelled.")
    return redirect("documents:process_instance_detail", pk=instance.pk)
