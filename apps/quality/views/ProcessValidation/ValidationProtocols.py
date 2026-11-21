import csv
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.quality.forms.ProcessValidation.ValidationProtocols import ValidationProtocolForm
from apps.quality.models.ProcessValidation.ValidationProtocols import ValidationProtocol
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def validation_protocol_list(request):
    qs = quality_scope(ValidationProtocol.objects.all(), request).select_related(
        "lead_author", "qa_reviewer", "final_approver", "department"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(equipment_tag__icontains=q)
            | Q(process_name__icontains=q)
            | Q(item_code__icontains=q)
        )

    stage_filter = request.GET.get("stage", "").strip()
    if stage_filter:
        qs = qs.filter(protocol_stage=stage_filter)

    target_type_filter = request.GET.get("target_type", "").strip()
    if target_type_filter:
        qs = qs.filter(target_type=target_type_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    trigger_filter = request.GET.get("revalidation_trigger", "").strip()
    if trigger_filter:
        qs = qs.filter(revalidation_trigger=trigger_filter)

    dept_filter = request.GET.get("department", "").strip()
    if dept_filter and dept_filter.isdigit():
        qs = qs.filter(department_id=int(dept_filter))

    base_tenant_qs = ValidationProtocol.objects.filter(tenant=request.tenant)
    today = datetime.date.today()
    stats = base_tenant_qs.aggregate(
        active_count=Count("id", filter=Q(status__in=["in_review", "approved_for_execution", "in_execution"])),
        completed_count=Count("id", filter=Q(status__in=["execution_completed", "final_approved"])),
        overdue_count=Count("id", filter=Q(target_completion_date__lt=today) & ~Q(status__in=["final_approved", "rejected", "superseded"])),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    total_count = paginator.count
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        query_params.pop("page")

    context = {
        "page_obj": page_obj,
        "validation_protocols": page_obj,
        "total_count": total_count,
        "active_count": stats["active_count"],
        "completed_count": stats["completed_count"],
        "overdue_count": stats["overdue_count"],
        "stage_choices": ValidationProtocol.STAGE_CHOICES,
        "target_type_choices": ValidationProtocol.TARGET_TYPE_CHOICES,
        "status_choices": ValidationProtocol.STATUS_CHOICES,
        "revalidation_trigger_choices": ValidationProtocol.REVALIDATION_TRIGGER_CHOICES,
        "departments": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "search_query": q,
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/processvalidation/validation_protocol/list.html", context)


@login_required
def validation_protocol_detail(request, pk):
    validation_protocol = quality_object(
        request,
        ValidationProtocol,
        pk,
        select_related=(
            "lead_author",
            "qa_reviewer",
            "final_approver",
            "department",
            "governing_document",
            "triggering_change",
            "calibration_gage",
        ),
    )
    context = {
        "validation_protocol": validation_protocol,
        "is_detail": True,
    }
    return render(request, "quality/processvalidation/validation_protocol/detail.html", context)


@login_required
def validation_protocol_create(request):
    if request.method == "POST":
        form = ValidationProtocolForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Validation Protocol {obj.number} created successfully.")
            return redirect("quality:validation_protocol_detail", pk=obj.pk)
    else:
        form = ValidationProtocolForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "validation_protocol": None,
    }
    return render(request, "quality/processvalidation/validation_protocol/form.html", context)


@login_required
def validation_protocol_edit(request, pk):
    validation_protocol = quality_object(request, ValidationProtocol, pk)
    if request.method == "POST":
        form = ValidationProtocolForm(request.POST, instance=validation_protocol, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Validation Protocol {obj.number} updated successfully.")
            return redirect("quality:validation_protocol_detail", pk=obj.pk)
    else:
        form = ValidationProtocolForm(instance=validation_protocol, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "validation_protocol": validation_protocol,
    }
    return render(request, "quality/processvalidation/validation_protocol/form.html", context)


@login_required
@require_POST
def validation_protocol_delete(request, pk):
    validation_protocol = quality_object(request, ValidationProtocol, pk)
    num = validation_protocol.number
    write_audit_log(request.user, validation_protocol, "delete", tenant=request.tenant)
    validation_protocol.delete()
    messages.success(request, f"Validation Protocol {num} deleted successfully.")
    return redirect("quality:validation_protocol_list")


@login_required
def validation_protocol_export(request):
    qs = quality_scope(ValidationProtocol.objects.all(), request).select_related(
        "lead_author", "qa_reviewer", "final_approver", "department"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="validation_protocols.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "Title",
        "Stage",
        "Target Type",
        "Status",
        "Trigger",
        "Equipment Tag",
        "Process Name",
        "Target Completion",
        "Actual Completion",
        "Revalidation Due",
        "Runs Planned",
        "Runs Completed",
        "Deviations",
        "Lead Author",
        "QA Reviewer",
    ])

    for p in qs:
        writer.writerow([
            _csv_safe(p.number),
            _csv_safe(p.title),
            _csv_safe(p.get_protocol_stage_display()),
            _csv_safe(p.get_target_type_display()),
            _csv_safe(p.get_status_display()),
            _csv_safe(p.get_revalidation_trigger_display()),
            _csv_safe(p.equipment_tag),
            _csv_safe(p.process_name),
            _csv_safe(p.target_completion_date),
            _csv_safe(p.actual_completion_date),
            _csv_safe(p.revalidation_due_date),
            p.test_runs_planned,
            p.test_runs_completed,
            p.deviations_encountered,
            _csv_safe(p.lead_author.get_full_name() if p.lead_author else ""),
            _csv_safe(p.qa_reviewer.get_full_name() if p.qa_reviewer else ""),
        ])

    return response
