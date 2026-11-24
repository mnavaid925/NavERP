import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
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
    start_process_instance,
)
from apps.documents.views._common import documents_object, documents_scope


@login_required
def process_instance_list(request):
    qs = documents_scope(
        DocumentProcessInstance.objects.select_related(
            "process_definition",
            "document",
            "department",
            "initiated_by",
            "current_assignee",
            "approval_workflow",
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

    process_definition_id = request.GET.get("process_definition", "").strip()
    if process_definition_id and process_definition_id.isdigit():
        qs = qs.filter(process_definition_id=int(process_definition_id))

    department_id = request.GET.get("department", "").strip()
    if department_id and department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    sla_breached = request.GET.get("sla_breached", "").strip()
    if sla_breached == "1":
        qs = qs.filter(is_sla_breached=True)
    elif sla_breached == "0":
        qs = qs.filter(is_sla_breached=False)

    total_count = qs.count()
    active_count = qs.filter(status__in=["queued", "running", "waiting_approval", "waiting_timer"]).count()
    completed_count = qs.filter(status="completed").count()
    sla_breached_count = qs.filter(is_sla_breached=True).count()

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    process_definitions = DocumentProcessDefinition.objects.filter(
        tenant=request.tenant
    ).order_by("code", "-version_number")
    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "instances": page_obj.object_list,
        "page_obj": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "completed_count": completed_count,
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
    context = {
        "instance": instance,
        "step_trace": instance.step_trace_json or [],
        "blueprint_nodes": instance.process_definition.nodes_json or [],
        "advance_form": ProcessAdvanceForm(),
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
        proc_id = request.GET.get("process_definition", "").strip()
        if proc_id and proc_id.isdigit():
            initial["process_definition"] = int(proc_id)
        doc_id = request.GET.get("document", "").strip()
        if doc_id and doc_id.isdigit():
            initial["document"] = int(doc_id)
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
    instance = documents_object(request, DocumentProcessInstance, pk)
    if instance.status not in ("queued", "cancelled", "failed"):
        messages.error(request, "Only queued, cancelled, or failed instances can be deleted.")
        return redirect("documents:process_instance_detail", pk=instance.pk)

    number = instance.number
    with transaction.atomic():
        write_audit_log(request.user, instance, "delete", tenant=request.tenant)
        instance.delete()
    messages.success(request, f"Process instance {number} deleted.")
    return redirect("documents:process_instance_list")


@login_required
@require_POST
def process_instance_advance(request, pk):
    instance = documents_object(
        request,
        DocumentProcessInstance,
        pk,
        select_related=("process_definition", "document", "version"),
    )
    if instance.status in ("completed", "cancelled"):
        messages.warning(request, f"Instance {instance.number} is already {instance.get_status_display()}.")
        return redirect("documents:process_instance_detail", pk=instance.pk)

    form = ProcessAdvanceForm(request.POST)
    if form.is_valid():
        advance_process_instance(
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
    instance = documents_object(request, DocumentProcessInstance, pk)
    if instance.status in ("completed", "cancelled"):
        messages.warning(request, "Completed or cancelled process instances cannot be cancelled.")
        return redirect("documents:process_instance_detail", pk=instance.pk)

    with transaction.atomic():
        instance.status = "cancelled"
        instance.completed_at = timezone.now()
        instance.save(update_fields=["status", "completed_at", "updated_at"])
        write_audit_log(request.user, instance, "cancel", tenant=request.tenant)
    messages.info(request, f"Process instance {instance.number} cancelled.")
    return redirect("documents:process_instance_detail", pk=instance.pk)
