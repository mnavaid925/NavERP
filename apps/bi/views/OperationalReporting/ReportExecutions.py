import csv
import json
import time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.OperationalReporting.ReportExecutions import ReportExecutionRunForm
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportExecutions import ReportExecution
from apps.bi.views.OperationalReporting.ReportDefinitions import _evaluate_report_data
from apps.bi.views._common import bi_object, bi_scope, csv_safe
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def report_execution_list(request):
    qs = bi_scope(
        ReportExecution.objects.select_related("report", "executed_by").all(),
        request,
        owner_field="executed_by",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(report__name__icontains=q)
            | Q(report__number__icontains=q)
            | Q(executed_by__username__icontains=q)
        )

    execution_status = request.GET.get("execution_status", "").strip()
    if execution_status:
        qs = qs.filter(execution_status=execution_status)

    execution_mode = request.GET.get("execution_mode", "").strip()
    if execution_mode:
        qs = qs.filter(execution_mode=execution_mode)

    output_format = request.GET.get("output_format", "").strip()
    if output_format:
        qs = qs.filter(output_format=output_format)

    report_id = request.GET.get("report", "").strip()
    if report_id and report_id.isdigit():
        qs = qs.filter(report_id=report_id)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    reports = (
        ReportDefinition.objects.filter(tenant=request.tenant)
        .only("id", "name", "number")
        .order_by("name")
    )

    context = {
        "page_obj": page_obj,
        "executions": page_obj,
        "status_choices": ReportExecution.EXECUTION_STATUS_CHOICES,
        "mode_choices": ReportExecution.EXECUTION_MODE_CHOICES,
        "format_choices": ReportExecution.OUTPUT_FORMAT_CHOICES,
        "reports": reports,
        "q": q,
        "execution_status": execution_status,
        "execution_mode": execution_mode,
        "output_format": output_format,
        "report_id": report_id,
    }
    return render(request, "bi/operational_reporting/report_execution/list.html", context)


@login_required
def report_execution_detail(request, pk):
    execution = bi_object(
        request,
        ReportExecution,
        pk,
        select_related=("report", "executed_by", "report__created_by"),
    )
    can_delete = request.user.is_superuser or getattr(request, "is_tenant_admin", False)

    context = {
        "execution": execution,
        "report": execution.report,
        "can_delete": can_delete,
    }
    return render(request, "bi/operational_reporting/report_execution/detail.html", context)


@login_required
def report_execution_run(request, report_pk):
    report = bi_object(request, ReportDefinition, report_pk)
    if request.method == "POST":
        form = ReportExecutionRunForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            mode = form.cleaned_data["execution_mode"]
            fmt = form.cleaned_data["output_format"]

            start = time.time()
            columns, rows = _evaluate_report_data(report, {})
            duration_ms = max(int((time.time() - start) * 1000), 16)

            with transaction.atomic():
                execution = ReportExecution.objects.create(
                    tenant=request.tenant,
                    report=report,
                    executed_by=request.user,
                    execution_mode=mode,
                    execution_status="completed",
                    completed_at=timezone.now(),
                    duration_ms=duration_ms,
                    row_count=len(rows),
                    output_format=fmt,
                    output_file_name=f"{report.slug}_{int(time.time())}.{fmt}",
                    parameter_values_json={},
                )
                write_audit_log(
                    request.user,
                    execution,
                    "create",
                    changes={"report": report.number, "mode": mode, "format": fmt},
                    tenant=request.tenant,
                )

            messages.success(request, f"Execution {execution.number} completed successfully in {duration_ms} ms.")
            return redirect("bi:report_execution_detail", pk=execution.pk)
    else:
        form = ReportExecutionRunForm(
            initial={"execution_mode": "interactive_view", "output_format": "html"},
            tenant=request.tenant,
        )

    context = {
        "form": form,
        "report": report,
    }
    return render(request, "bi/operational_reporting/report_execution/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def report_execution_delete(request, pk):
    execution = bi_object(request, ReportExecution, pk, select_related=("report",))
    num = execution.number
    with transaction.atomic():
        write_audit_log(
            request.user,
            execution,
            "delete",
            changes={"number": num, "report": execution.report.number},
            tenant=request.tenant,
        )
        execution.delete()
    messages.success(request, f"Execution record '{num}' deleted successfully.")
    return redirect("bi:report_execution_list")


@login_required
def report_execution_export(request, pk, export_format):
    execution = bi_object(request, ReportExecution, pk, select_related=("report",))
    report = execution.report

    columns, rows = _evaluate_report_data(report, execution.parameter_values_json or {})

    clean_format = export_format.lower()
    if clean_format in ("csv", "xlsx"):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{report.slug}_{execution.number}.csv"'

        writer = csv.writer(response)
        # Header row
        writer.writerow([csv_safe(col.get("title", col.get("field", ""))) for col in columns])
        # Data rows
        for row in rows:
            writer.writerow([csv_safe(row.get(col.get("field"), "")) for col in columns])
        return response

    elif clean_format == "json":
        data = {
            "report": report.name,
            "number": report.number,
            "execution": execution.number,
            "executed_at": execution.started_at.isoformat(),
            "columns": columns,
            "rows": rows,
        }
        response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{report.slug}_{execution.number}.json"'
        return response

    else:
        # Default redirect to interactive view for other formats
        return redirect("bi:report_definition_viewer", pk=report.pk)
