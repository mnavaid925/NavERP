import csv
from decimal import Decimal

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.InProcessQuality.LayeredProcessAudits import LayeredProcessAuditForm
from apps.quality.models.InProcessQuality.LayeredProcessAudits import LayeredProcessAudit

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def layered_process_audit_list(request):
    qs = LayeredProcessAudit.objects.filter(tenant=request.tenant).select_related(
        "work_center", "org_unit", "auditor", "controlled_document", "non_conformance"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(work_center_code__icontains=search_query)
            | Q(findings_summary__icontains=search_query)
        )

    current_layer = request.GET.get("audit_layer", "").strip()
    if current_layer:
        qs = qs.filter(audit_layer=current_layer)

    current_focus = request.GET.get("focus_area", "").strip()
    if current_focus:
        qs = qs.filter(focus_area=current_focus)

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_work_center = request.GET.get("work_center", "").strip()
    if current_work_center.isdigit():
        qs = qs.filter(work_center_id=int(current_work_center))

    total_audits_count = LayeredProcessAudit.objects.filter(tenant=request.tenant).count()
    completed_count = LayeredProcessAudit.objects.filter(tenant=request.tenant, status="completed").count()
    scheduled_count = LayeredProcessAudit.objects.filter(tenant=request.tenant, status="scheduled").count()
    avg_compliance = LayeredProcessAudit.objects.filter(tenant=request.tenant, status="completed").aggregate(
        avg=Avg("compliance_percentage")
    )["avg"] or Decimal("0.00")
    avg_compliance_rate = round(avg_compliance, 1)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    work_centers = []
    try:
        WorkCenter = apps.get_model("scm", "WorkCenter")
        work_centers = list(WorkCenter.objects.filter(tenant=request.tenant).only("id", "code", "name").order_by("code"))
    except LookupError:
        pass

    context = {
        "page_obj": page_obj,
        "lpas": page_obj,
        "layer_choices": LayeredProcessAudit.AUDIT_LAYER_CHOICES,
        "focus_choices": LayeredProcessAudit.FOCUS_AREA_CHOICES,
        "status_choices": LayeredProcessAudit.STATUS_CHOICES,
        "work_centers": work_centers,
        "total_audits_count": total_audits_count,
        "completed_count": completed_count,
        "scheduled_count": scheduled_count,
        "avg_compliance_rate": avg_compliance_rate,
        "search_query": search_query,
        "current_layer": current_layer,
        "current_focus": current_focus,
        "current_status": current_status,
        "current_work_center": current_work_center,
    }
    return render(
        request,
        "quality/inprocessquality/layered_process_audit/list.html",
        context,
    )


@login_required
def layered_process_audit_detail(request, pk):
    lpa = get_object_or_404(
        LayeredProcessAudit.objects.filter(tenant=request.tenant).select_related(
            "work_center", "org_unit", "auditor", "controlled_document", "non_conformance"
        ),
        pk=pk,
    )
    context = {
        "lpa": lpa,
    }
    return render(
        request,
        "quality/inprocessquality/layered_process_audit/detail.html",
        context,
    )


@login_required
def layered_process_audit_create(request):
    if request.method == "POST":
        form = LayeredProcessAuditForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            lpa = form.save(commit=False)
            lpa.tenant = request.tenant
            if not lpa.auditor:
                lpa.auditor = request.user
            lpa.save()
            form.save_m2m()
            write_audit_log(request.user, lpa, "create", tenant=request.tenant)
            messages.success(request, f"Layered Process Audit {lpa.number} scheduled successfully.")
            return redirect("quality:layered_process_audit_detail", pk=lpa.pk)
    else:
        form = LayeredProcessAuditForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "lpa": None,
        "title": "Schedule Layered Process Audit (LPA)",
    }
    return render(
        request,
        "quality/inprocessquality/layered_process_audit/form.html",
        context,
    )


@login_required
def layered_process_audit_edit(request, pk):
    lpa = get_object_or_404(LayeredProcessAudit, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = LayeredProcessAuditForm(request.POST, instance=lpa, tenant=request.tenant)
        if form.is_valid():
            lpa = form.save()
            write_audit_log(request.user, lpa, "update", tenant=request.tenant)
            messages.success(request, f"Layered Process Audit {lpa.number} updated successfully.")
            return redirect("quality:layered_process_audit_detail", pk=lpa.pk)
    else:
        form = LayeredProcessAuditForm(instance=lpa, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "lpa": lpa,
        "title": f"Edit Layered Process Audit: {lpa.number}",
    }
    return render(
        request,
        "quality/inprocessquality/layered_process_audit/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def layered_process_audit_delete(request, pk):
    lpa = get_object_or_404(LayeredProcessAudit, pk=pk, tenant=request.tenant)
    number = lpa.number
    write_audit_log(request.user, lpa, "delete", tenant=request.tenant)
    lpa.delete()
    messages.success(request, f"Layered Process Audit {number} deleted successfully.")
    return redirect("quality:layered_process_audit_list")


@login_required
def layered_process_audit_export_csv(request):
    qs = LayeredProcessAudit.objects.filter(tenant=request.tenant).select_related("work_center").order_by("-scheduled_date")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="layered_process_audits.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Audit Number",
        "Title",
        "Audit Layer",
        "Focus Area",
        "Status",
        "Scheduled Date",
        "Total Questions",
        "Conforming",
        "Non-Conforming",
        "Compliance %",
        "On-The-Spot Mitigated",
        "Work Center",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_audit_layer_display()),
            _csv_safe(item.get_focus_area_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.scheduled_date),
            _csv_safe(item.total_questions_audited),
            _csv_safe(item.questions_conforming),
            _csv_safe(item.questions_non_conforming),
            _csv_safe(item.compliance_percentage),
            _csv_safe("Yes" if item.on_the_spot_mitigation else "No"),
            _csv_safe(item.work_center.code if item.work_center else item.work_center_code),
        ])

    return response
