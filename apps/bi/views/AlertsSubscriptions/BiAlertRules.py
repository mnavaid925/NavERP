from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.AlertsSubscriptions.BiAlertRules import BiAlertRuleForm
from apps.bi.models.AlertsSubscriptions.BiAlertRules import BiAlertRule
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PredictiveAnalytics.StatisticalAnomalies import StatisticalAnomaly
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def bi_alert_rule_list(request):
    qs = bi_scope(BiAlertRule.objects.all(), request).select_related(
        "kpi_definition", "anomaly_detection", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        tripped=Count("id", filter=Q(status="tripped")),
        critical=Count("id", filter=Q(severity="critical")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    tripped_count = counts["tripped"] or 0
    critical_count = counts["critical"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
            | Q(notification_email_list__icontains=q)
        )

    # Filters
    selected_alert_type = request.GET.get("alert_type", "").strip()
    if selected_alert_type:
        qs = qs.filter(alert_type=selected_alert_type)

    selected_severity = request.GET.get("severity", "").strip()
    if selected_severity:
        qs = qs.filter(severity=selected_severity)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    rules = paginator.get_page(page_number)

    context = {
        "rules": rules,
        "total_count": total_count,
        "active_count": active_count,
        "tripped_count": tripped_count,
        "critical_count": critical_count,
        "alert_type_choices": BiAlertRule.ALERT_TYPE_CHOICES,
        "severity_choices": BiAlertRule.SEVERITY_CHOICES,
        "status_choices": BiAlertRule.STATUS_CHOICES,
        "q": q,
        "selected_alert_type": selected_alert_type,
        "selected_severity": selected_severity,
        "selected_status": selected_status,
    }
    return render(request, "bi/alerts_subscriptions/bi_alert_rule/list.html", context)


@login_required
def bi_alert_rule_detail(request, pk):
    rule = bi_object(
        request,
        BiAlertRule,
        pk=pk,
        select_related=["kpi_definition", "anomaly_detection", "created_by"],
        prefetch_related=["recipient_users"],
    )

    recent_notifications = getattr(rule, "notifications", None)
    if recent_notifications is not None:
        recent_notifications = recent_notifications.filter(
            tenant=request.tenant
        ).select_related("recipient")[:10]
    else:
        recent_notifications = []

    recent_burst_runs = getattr(rule, "burst_runs", None)
    if recent_burst_runs is not None:
        recent_burst_runs = recent_burst_runs.filter(tenant=request.tenant)[:10]
    else:
        recent_burst_runs = []

    context = {
        "rule": rule,
        "recent_notifications": recent_notifications,
        "recent_burst_runs": recent_burst_runs,
    }
    return render(request, "bi/alerts_subscriptions/bi_alert_rule/detail.html", context)


@login_required
def bi_alert_rule_create(request):
    if request.method == "POST":
        form = BiAlertRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                rule = form.save(commit=False)
                rule.tenant = request.tenant
                rule.created_by = request.user
                rule.save()
                form.save_m2m()

                write_audit_log(
                    request,
                    action="create",
                    model_name="BiAlertRule",
                    object_id=rule.pk,
                    object_repr=str(rule),
                )
            messages.success(request, f"Alert rule {rule.number} created successfully.")
            return redirect("bi:bi_alert_rule_detail", pk=rule.pk)
    else:
        form = BiAlertRuleForm(tenant=request.tenant)

    kpi_definitions = KpiDefinition.objects.filter(tenant=request.tenant)
    anomalies = StatisticalAnomaly.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "rule": None,
        "kpi_definitions": kpi_definitions,
        "anomalies": anomalies,
    }
    return render(request, "bi/alerts_subscriptions/bi_alert_rule/form.html", context)


@login_required
def bi_alert_rule_edit(request, pk):
    rule = bi_object(request, BiAlertRule, pk=pk)

    if request.method == "POST":
        form = BiAlertRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                rule = form.save()
                write_audit_log(
                    request,
                    action="update",
                    model_name="BiAlertRule",
                    object_id=rule.pk,
                    object_repr=str(rule),
                )
            messages.success(request, f"Alert rule {rule.number} updated successfully.")
            return redirect("bi:bi_alert_rule_detail", pk=rule.pk)
    else:
        form = BiAlertRuleForm(instance=rule, tenant=request.tenant)

    kpi_definitions = KpiDefinition.objects.filter(tenant=request.tenant)
    anomalies = StatisticalAnomaly.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "rule": rule,
        "kpi_definitions": kpi_definitions,
        "anomalies": anomalies,
    }
    return render(request, "bi/alerts_subscriptions/bi_alert_rule/form.html", context)


@login_required
@require_POST
def bi_alert_rule_delete(request, pk):
    rule = bi_object(request, BiAlertRule, pk=pk)
    num = rule.number

    with transaction.atomic():
        write_audit_log(
            request,
            action="delete",
            model_name="BiAlertRule",
            object_id=rule.pk,
            object_repr=str(rule),
        )
        rule.delete()

    messages.success(request, f"Alert rule {num} deleted.")
    return redirect("bi:bi_alert_rule_list")


@login_required
@require_POST
def bi_alert_rule_test_evaluate(request, pk):
    rule = bi_object(
        request,
        BiAlertRule,
        pk=pk,
        select_related=["kpi_definition", "anomaly_detection"],
    )

    now = timezone.now()
    rule.last_evaluated_at = now

    simulated_value = Decimal("0.0000")
    if rule.kpi_definition and rule.kpi_definition.current_value is not None:
        simulated_value = rule.kpi_definition.current_value
    else:
        simulated_value = rule.threshold_value + Decimal("5.2500")

    tripped = False
    op = rule.condition_operator
    th = rule.threshold_value
    th2 = rule.secondary_threshold_value or Decimal("0.0000")

    if op == "gt" and simulated_value > th:
        tripped = True
    elif op == "gte" and simulated_value >= th:
        tripped = True
    elif op == "lt" and simulated_value < th:
        tripped = True
    elif op == "lte" and simulated_value <= th:
        tripped = True
    elif op == "eq" and simulated_value == th:
        tripped = True
    elif op == "outside_range" and (simulated_value < th or simulated_value > th2):
        tripped = True
    elif op in ("pct_change_gt", "pct_change_lt", "anomaly_flagged"):
        tripped = True

    if tripped:
        rule.status = "tripped"
        rule.last_triggered_at = now
        rule.trigger_count += 1
        rule.last_trigger_value = simulated_value
        messages.warning(
            request,
            f"Alert {rule.number} evaluated: CONDITION TRIPPED with value {simulated_value} (threshold {th}).",
        )
    else:
        if rule.status == "tripped":
            rule.status = "active"
        messages.success(
            request,
            f"Alert {rule.number} evaluated: condition within normal bounds ({simulated_value}).",
        )

    rule.save()

    write_audit_log(
        request,
        action="update",
        model_name="BiAlertRule",
        object_id=rule.pk,
        object_repr=f"Evaluate {rule.number} -> tripped={tripped}",
    )
    return redirect("bi:bi_alert_rule_detail", pk=rule.pk)
