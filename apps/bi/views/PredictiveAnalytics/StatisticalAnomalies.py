from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.PredictiveAnalytics.StatisticalAnomalies import StatisticalAnomalyForm
from apps.bi.models.PredictiveAnalytics.StatisticalAnomalies import StatisticalAnomaly
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def statistical_anomaly_list(request):
    qs = bi_scope(StatisticalAnomaly.objects.all(), request, owner_field="assigned_to").select_related(
        "model", "semantic_model", "kpi_definition", "assigned_to"
    )

    counts = qs.aggregate(
        total=Count("id"),
        open_anomalies=Count("id", filter=Q(triage_status="open")),
        critical=Count("id", filter=Q(severity="critical")),
    )
    total_count = counts["total"] or 0
    open_count = counts["open_anomalies"] or 0
    critical_count = counts["critical"] or 0

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(metric_name__icontains=q)
            | Q(resolution_notes__icontains=q)
        )

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    triage_status = request.GET.get("triage_status", "").strip()
    if triage_status:
        qs = qs.filter(triage_status=triage_status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "bi/predictive_analytics/statistical_anomaly/list.html",
        {
            "statistical_anomalies": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "open_count": open_count,
            "critical_count": critical_count,
            "severity_choices": StatisticalAnomaly.SEVERITY_CHOICES,
            "triage_choices": StatisticalAnomaly.TRIAGE_CHOICES,
        },
    )


@login_required
def statistical_anomaly_detail(request, pk):
    anomaly = bi_object(
        request,
        StatisticalAnomaly,
        pk,
        select_related=["model", "semantic_model", "kpi_definition", "assigned_to"],
    )

    return render(
        request,
        "bi/predictive_analytics/statistical_anomaly/detail.html",
        {
            "anomaly_obj": anomaly,
        },
    )


@login_required
def statistical_anomaly_create(request):
    if request.method == "POST":
        form = StatisticalAnomalyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            anomaly = form.save(commit=False)
            anomaly.tenant = request.tenant
            anomaly.save()
            write_audit_log(request.user, anomaly, "create", changes={"title": anomaly.title, "number": anomaly.number}, tenant=request.tenant)
            messages.success(request, f"Statistical anomaly '{anomaly.title}' ({anomaly.number}) logged successfully.")
            return redirect("bi:statistical_anomaly_detail", pk=anomaly.pk)
    else:
        form = StatisticalAnomalyForm(tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/statistical_anomaly/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def statistical_anomaly_edit(request, pk):
    anomaly = bi_object(request, StatisticalAnomaly, pk)
    if request.method == "POST":
        form = StatisticalAnomalyForm(request.POST, instance=anomaly, tenant=request.tenant)
        if form.is_valid():
            anomaly = form.save()
            write_audit_log(request.user, anomaly, "update", changes={"title": anomaly.title, "number": anomaly.number}, tenant=request.tenant)
            messages.success(request, f"Statistical anomaly '{anomaly.title}' updated successfully.")
            return redirect("bi:statistical_anomaly_detail", pk=anomaly.pk)
    else:
        form = StatisticalAnomalyForm(instance=anomaly, tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/statistical_anomaly/form.html",
        {
            "form": form,
            "anomaly_obj": anomaly,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def statistical_anomaly_delete(request, pk):
    anomaly = bi_object(request, StatisticalAnomaly, pk)
    title = anomaly.title
    number = anomaly.number
    anomaly.delete()
    write_audit_log(request.user, anomaly, "delete", changes={"title": title, "number": number}, tenant=request.tenant)
    messages.success(request, f"Anomaly '{title}' ({number}) deleted successfully.")
    return redirect("bi:statistical_anomaly_list")


@login_required
@require_POST
def statistical_anomaly_triage(request, pk):
    anomaly = bi_object(request, StatisticalAnomaly, pk)
    new_status = request.POST.get("triage_status", "").strip()
    notes = request.POST.get("resolution_notes", "").strip()
    valid_statuses = dict(StatisticalAnomaly.TRIAGE_CHOICES).keys()
    if new_status in valid_statuses:
        anomaly.mark_triage(new_status, notes=notes, user=request.user)
        write_audit_log(request.user, anomaly, "triage", changes={"triage_status": new_status, "notes": notes}, tenant=request.tenant)
        messages.success(request, f"Anomaly triage updated to '{anomaly.get_triage_status_display()}'.")
    else:
        messages.error(request, "Invalid triage status provided.")
    return redirect("bi:statistical_anomaly_detail", pk=anomaly.pk)
