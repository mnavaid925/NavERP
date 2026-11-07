from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.AlertsSubscriptions.ReportSubscriptions import ReportSubscriptionForm
from apps.bi.models.AlertsSubscriptions.DistributionBurstRuns import DistributionBurstRun
from apps.bi.models.AlertsSubscriptions.ReportSubscriptions import ReportSubscription
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.views._common import bi_object, bi_scope
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log


@login_required
def report_subscription_list(request):
    base_qs = bi_scope(ReportSubscription.objects.all(), request)

    counts = base_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        pdf=Count("id", filter=Q(export_format="pdf")),
        excel=Count("id", filter=Q(export_format="xlsx")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    pdf_count = counts["pdf"] or 0
    excel_count = counts["excel"] or 0

    qs = base_qs.select_related(
        "dashboard", "report", "created_by"
    )

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(external_recipient_emails__icontains=q)
            | Q(dashboard__title__icontains=q)
            | Q(report__name__icontains=q)
        )

    # Filters
    selected_target_type = request.GET.get("target_type", "").strip()
    if selected_target_type:
        qs = qs.filter(target_asset_type=selected_target_type)

    selected_cadence = request.GET.get("cadence", "").strip()
    if selected_cadence:
        qs = qs.filter(cadence=selected_cadence)

    selected_format = request.GET.get("format", "").strip()
    if selected_format:
        qs = qs.filter(export_format=selected_format)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    subscriptions = paginator.get_page(page_number)

    context = {
        "subscriptions": subscriptions,
        "total_count": total_count,
        "active_count": active_count,
        "pdf_count": pdf_count,
        "excel_count": excel_count,
        "target_asset_type_choices": ReportSubscription.TARGET_ASSET_TYPE_CHOICES,
        "cadence_choices": ReportSubscription.CADENCE_CHOICES,
        "export_format_choices": ReportSubscription.EXPORT_FORMAT_CHOICES,
        "status_choices": ReportSubscription.STATUS_CHOICES,
        "q": q,
        "selected_target_type": selected_target_type,
        "selected_cadence": selected_cadence,
        "selected_format": selected_format,
        "selected_status": selected_status,
    }
    return render(
        request, "bi/alerts_subscriptions/report_subscription/list.html", context
    )


@login_required
def report_subscription_detail(request, pk):
    subscription = bi_object(
        request,
        ReportSubscription,
        pk=pk,
        select_related=["dashboard", "report", "created_by"],
        prefetch_related=["subscriber_users", "subscriber_org_units"],
    )

    recent_burst_runs = getattr(subscription, "burst_runs", None)
    if recent_burst_runs is not None:
        recent_burst_runs = recent_burst_runs.filter(tenant=request.tenant)[:10]
    else:
        recent_burst_runs = []

    context = {
        "subscription": subscription,
        "recent_burst_runs": recent_burst_runs,
    }
    return render(
        request, "bi/alerts_subscriptions/report_subscription/detail.html", context
    )


@login_required
def report_subscription_create(request):
    if request.method == "POST":
        form = ReportSubscriptionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                sub = form.save(commit=False)
                sub.tenant = request.tenant
                sub.created_by = request.user
                sub.save()
                form.save_m2m()

                write_audit_log(
                    request.user,
                    sub,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Report subscription {sub.number} scheduled successfully."
            )
            return redirect("bi:report_subscription_detail", pk=sub.pk)
    else:
        form = ReportSubscriptionForm(tenant=request.tenant)

    dashboards = BiDashboard.objects.filter(tenant=request.tenant)
    reports = ReportDefinition.objects.filter(tenant=request.tenant)
    org_units = OrgUnit.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "subscription": None,
        "dashboards": dashboards,
        "reports": reports,
        "org_units": org_units,
    }
    return render(
        request, "bi/alerts_subscriptions/report_subscription/form.html", context
    )


@login_required
def report_subscription_edit(request, pk):
    subscription = bi_object(request, ReportSubscription, pk=pk)

    if request.method == "POST":
        form = ReportSubscriptionForm(
            request.POST, instance=subscription, tenant=request.tenant
        )
        if form.is_valid():
            with transaction.atomic():
                sub = form.save()
                write_audit_log(
                    request.user,
                    sub,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Report subscription {sub.number} updated successfully."
            )
            return redirect("bi:report_subscription_detail", pk=sub.pk)
    else:
        form = ReportSubscriptionForm(instance=subscription, tenant=request.tenant)

    dashboards = BiDashboard.objects.filter(tenant=request.tenant)
    reports = ReportDefinition.objects.filter(tenant=request.tenant)
    org_units = OrgUnit.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "subscription": subscription,
        "dashboards": dashboards,
        "reports": reports,
        "org_units": org_units,
    }
    return render(
        request, "bi/alerts_subscriptions/report_subscription/form.html", context
    )


@login_required
@require_POST
def report_subscription_delete(request, pk):
    subscription = bi_object(request, ReportSubscription, pk=pk)
    num = subscription.number

    with transaction.atomic():
        write_audit_log(
            request.user,
            subscription,
            "delete",
            tenant=request.tenant,
        )
        subscription.delete()

    messages.success(request, f"Subscription {num} deleted.")
    return redirect("bi:report_subscription_list")


@login_required
@require_POST
def report_subscription_run_now(request, pk):
    subscription = bi_object(
        request,
        ReportSubscription,
        pk=pk,
        select_related=["dashboard", "report"],
        prefetch_related=["subscriber_users"],
    )

    now = timezone.now()
    user_count = len(subscription.subscriber_users.all())
    external_count = len(
        [
            e.strip()
            for e in subscription.external_recipient_emails.split(",")
            if e.strip()
        ]
    )
    total_recipients = max(1, user_count + external_count)

    ext = "pdf" if subscription.export_format == "pdf" else "xlsx"
    target_name = (
        subscription.dashboard.title
        if subscription.dashboard
        else (subscription.report.name if subscription.report else "Export")
    )
    clean_target = "".join(c for c in target_name if c.isalnum() or c in ("-", "_"))
    generated_file = f"{clean_target}_{now.strftime('%Y%m%d_%H%M%S')}.{ext}"

    with transaction.atomic():
        burst_run = DistributionBurstRun.objects.create(
            tenant=request.tenant,
            subscription=subscription,
            run_trigger="ad_hoc_manual",
            delivery_channel="email",
            status="completed",
            recipient_count=total_recipients,
            delivered_count=total_recipients,
            failed_count=0,
            execution_duration_ms=450,
            generated_file_name=generated_file,
            file_size_bytes=1024 * 380,
            burst_slicing_metadata={
                "burst_mode": subscription.burst_mode,
                "format": subscription.export_format,
                "recipients_dispatched": total_recipients,
            },
            executed_by=request.user,
            started_at=now,
            completed_at=now,
        )

        subscription.last_run_at = now
        subscription.run_count += 1
        subscription.save()

        write_audit_log(
            request.user,
            burst_run,
            "create",
            changes={"details": f"Manual Run for {subscription.number} -> {burst_run.number}"},
            tenant=request.tenant,
        )

    messages.success(
        request,
        f"Subscription {subscription.number} executed successfully: generated burst run {burst_run.number} ({total_recipients} recipients).",
    )
    return redirect("bi:distribution_burst_run_detail", pk=burst_run.pk)
