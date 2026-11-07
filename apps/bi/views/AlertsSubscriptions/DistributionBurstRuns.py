from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.AlertsSubscriptions.DistributionBurstRuns import (
    DistributionBurstRunForm,
)
from apps.bi.models.AlertsSubscriptions.BiAlertRules import BiAlertRule
from apps.bi.models.AlertsSubscriptions.DistributionBurstRuns import (
    DistributionBurstRun,
)
from apps.bi.models.AlertsSubscriptions.ReportSubscriptions import ReportSubscription
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def distribution_burst_run_list(request):
    qs = bi_scope(DistributionBurstRun.objects.all(), request).select_related(
        "subscription", "alert_rule", "executed_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status="completed")),
        failed=Count("id", filter=Q(status__in=["failed", "partial_failure"])),
        delivered_sum=Sum("delivered_count"),
    )
    total_runs = counts["total"] or 0
    completed_runs = counts["completed"] or 0
    failed_runs = counts["failed"] or 0
    total_delivered_recipients = counts["delivered_sum"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(generated_file_name__icontains=q)
            | Q(error_summary__icontains=q)
            | Q(subscription__name__icontains=q)
            | Q(alert_rule__name__icontains=q)
        )

    # Filters
    selected_trigger = request.GET.get("trigger", "").strip()
    if selected_trigger:
        qs = qs.filter(run_trigger=selected_trigger)

    selected_channel = request.GET.get("channel", "").strip()
    if selected_channel:
        qs = qs.filter(delivery_channel=selected_channel)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    burst_runs = paginator.get_page(page_number)

    context = {
        "burst_runs": burst_runs,
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "total_delivered_recipients": total_delivered_recipients,
        "run_trigger_choices": DistributionBurstRun.RUN_TRIGGER_CHOICES,
        "delivery_channel_choices": DistributionBurstRun.DELIVERY_CHANNEL_CHOICES,
        "status_choices": DistributionBurstRun.STATUS_CHOICES,
        "q": q,
        "selected_trigger": selected_trigger,
        "selected_channel": selected_channel,
        "selected_status": selected_status,
    }
    return render(
        request, "bi/alerts_subscriptions/distribution_burst_run/list.html", context
    )


@login_required
def distribution_burst_run_detail(request, pk):
    burst_run = bi_object(
        request,
        DistributionBurstRun,
        pk=pk,
        select_related=["subscription", "alert_rule", "executed_by"],
    )

    notifications = getattr(burst_run, "notifications", None)
    if notifications is not None:
        notifications = notifications.filter(tenant=request.tenant).select_related(
            "recipient"
        )[:10]
    else:
        notifications = []

    context = {
        "burst_run": burst_run,
        "notifications": notifications,
    }
    return render(
        request, "bi/alerts_subscriptions/distribution_burst_run/detail.html", context
    )


@login_required
def distribution_burst_run_create(request):
    if request.method == "POST":
        form = DistributionBurstRunForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                run = form.save(commit=False)
                run.tenant = request.tenant
                run.executed_by = request.user
                run.delivered_count = run.recipient_count
                run.started_at = timezone.now()
                run.completed_at = timezone.now()
                run.save()

                write_audit_log(
                    request.user,
                    run,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Distribution burst run {run.number} logged successfully."
            )
            return redirect("bi:distribution_burst_run_detail", pk=run.pk)
    else:
        form = DistributionBurstRunForm(tenant=request.tenant)

    subscriptions = ReportSubscription.objects.filter(tenant=request.tenant)
    rules = BiAlertRule.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "burst_run": None,
        "subscriptions": subscriptions,
        "rules": rules,
    }
    return render(
        request, "bi/alerts_subscriptions/distribution_burst_run/form.html", context
    )


@login_required
def distribution_burst_run_edit(request, pk):
    burst_run = bi_object(request, DistributionBurstRun, pk=pk)

    if request.method == "POST":
        form = DistributionBurstRunForm(
            request.POST, instance=burst_run, tenant=request.tenant
        )
        if form.is_valid():
            with transaction.atomic():
                run = form.save()
                write_audit_log(
                    request.user,
                    run,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Distribution burst run {run.number} updated successfully."
            )
            return redirect("bi:distribution_burst_run_detail", pk=run.pk)
    else:
        form = DistributionBurstRunForm(instance=burst_run, tenant=request.tenant)

    subscriptions = ReportSubscription.objects.filter(tenant=request.tenant)
    rules = BiAlertRule.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "burst_run": burst_run,
        "subscriptions": subscriptions,
        "rules": rules,
    }
    return render(
        request, "bi/alerts_subscriptions/distribution_burst_run/form.html", context
    )


@login_required
@require_POST
def distribution_burst_run_delete(request, pk):
    burst_run = bi_object(request, DistributionBurstRun, pk=pk)
    num = burst_run.number

    with transaction.atomic():
        write_audit_log(
            request.user,
            burst_run,
            "delete",
            tenant=request.tenant,
        )
        burst_run.delete()

    messages.success(request, f"Burst run {num} deleted.")
    return redirect("bi:distribution_burst_run_list")
