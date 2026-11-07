from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.AlertsSubscriptions.BiNotificationItems import (
    BiNotificationItemForm,
)
from apps.bi.models.AlertsSubscriptions.BiAlertRules import BiAlertRule
from apps.bi.models.AlertsSubscriptions.BiNotificationItems import (
    BiNotificationItem,
)
from apps.bi.models.AlertsSubscriptions.DistributionBurstRuns import (
    DistributionBurstRun,
)
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log

User = get_user_model()


@login_required
def bi_notification_item_list(request):
    qs = bi_scope(BiNotificationItem.objects.all(), request).select_related(
        "recipient", "alert_rule", "burst_run", "acknowledged_by", "escalated_to"
    )

    counts = qs.aggregate(
        total=Count("id"),
        unread=Count("id", filter=Q(status="unread")),
        critical=Count("id", filter=Q(severity="critical")),
        escalated=Count("id", filter=Q(status="escalated")),
    )
    total_count = counts["total"] or 0
    unread_count = counts["unread"] or 0
    critical_count = counts["critical"] or 0
    escalated_count = counts["escalated"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(message__icontains=q)
            | Q(recipient__username__icontains=q)
            | Q(workflow_reference__icontains=q)
        )

    # Filters
    selected_severity = request.GET.get("severity", "").strip()
    if selected_severity:
        qs = qs.filter(severity=selected_severity)

    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        qs = qs.filter(category=selected_category)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    notifications = paginator.get_page(page_number)

    context = {
        "notifications": notifications,
        "total_count": total_count,
        "unread_count": unread_count,
        "critical_count": critical_count,
        "escalated_count": escalated_count,
        "severity_choices": BiNotificationItem.SEVERITY_CHOICES,
        "category_choices": BiNotificationItem.CATEGORY_CHOICES,
        "status_choices": BiNotificationItem.STATUS_CHOICES,
        "q": q,
        "selected_severity": selected_severity,
        "selected_category": selected_category,
        "selected_status": selected_status,
    }
    return render(
        request, "bi/alerts_subscriptions/bi_notification_item/list.html", context
    )


@login_required
def notification_center(request):
    """
    Operational In-App Notification Center workspace for the current user and workspace.
    """
    base_qs = bi_scope(
        BiNotificationItem.objects.all(), request
    ).filter(
        Q(recipient=request.user) | Q(recipient__isnull=True)
    ).select_related("alert_rule", "burst_run", "acknowledged_by")

    counts = base_qs.aggregate(
        unread=Count("id", filter=Q(status="unread")),
        acknowledged=Count("id", filter=Q(status="acknowledged")),
        snoozed=Count("id", filter=Q(status="snoozed")),
        escalated=Count("id", filter=Q(status="escalated")),
    )
    unread_count = counts["unread"] or 0
    acknowledged_count = counts["acknowledged"] or 0
    snoozed_count = counts["snoozed"] or 0
    escalated_count = counts["escalated"] or 0

    active_tab = request.GET.get("tab", "all").strip()
    qs = base_qs
    if active_tab == "unread":
        qs = qs.filter(status="unread")
    elif active_tab == "critical":
        qs = qs.filter(severity="critical")
    elif active_tab == "snoozed":
        qs = qs.filter(status="snoozed")
    elif active_tab == "escalated":
        qs = qs.filter(status="escalated")

    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        qs = qs.filter(category=selected_category)

    inbox_items = qs[:50]

    context = {
        "inbox_items": inbox_items,
        "unread_count": unread_count,
        "acknowledged_count": acknowledged_count,
        "snoozed_count": snoozed_count,
        "escalated_count": escalated_count,
        "active_tab": active_tab,
        "selected_category": selected_category,
        "severity_choices": BiNotificationItem.SEVERITY_CHOICES,
        "category_choices": BiNotificationItem.CATEGORY_CHOICES,
    }
    return render(
        request, "bi/alerts_subscriptions/notification_center.html", context
    )


@login_required
def bi_notification_item_detail(request, pk):
    notification = bi_object(
        request,
        BiNotificationItem,
        pk=pk,
        select_related=[
            "recipient",
            "alert_rule",
            "burst_run",
            "acknowledged_by",
            "escalated_to",
        ],
    )

    if notification.status == "unread" and notification.recipient == request.user:
        notification.status = "read"
        notification.read_at = timezone.now()
        notification.save(update_fields=["status", "read_at", "updated_at"])

    context = {
        "notification": notification,
    }
    return render(
        request, "bi/alerts_subscriptions/bi_notification_item/detail.html", context
    )


@login_required
def bi_notification_item_create(request):
    if request.method == "POST":
        form = BiNotificationItemForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                item = form.save(commit=False)
                item.tenant = request.tenant
                item.save()

                write_audit_log(
                    request.user,
                    item,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Notification {item.number} created successfully."
            )
            return redirect("bi:bi_notification_item_detail", pk=item.pk)
    else:
        form = BiNotificationItemForm(tenant=request.tenant)

    rules = BiAlertRule.objects.filter(tenant=request.tenant)
    burst_runs = DistributionBurstRun.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "notification": None,
        "rules": rules,
        "burst_runs": burst_runs,
    }
    return render(
        request, "bi/alerts_subscriptions/bi_notification_item/form.html", context
    )


@login_required
def bi_notification_item_edit(request, pk):
    notification = bi_object(request, BiNotificationItem, pk=pk)

    if request.method == "POST":
        form = BiNotificationItemForm(
            request.POST, instance=notification, tenant=request.tenant
        )
        if form.is_valid():
            with transaction.atomic():
                item = form.save()
                write_audit_log(
                    request.user,
                    item,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Notification {item.number} updated successfully."
            )
            return redirect("bi:bi_notification_item_detail", pk=item.pk)
    else:
        form = BiNotificationItemForm(instance=notification, tenant=request.tenant)

    rules = BiAlertRule.objects.filter(tenant=request.tenant)
    burst_runs = DistributionBurstRun.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "notification": notification,
        "rules": rules,
        "burst_runs": burst_runs,
    }
    return render(
        request, "bi/alerts_subscriptions/bi_notification_item/form.html", context
    )


@login_required
@require_POST
def bi_notification_item_delete(request, pk):
    notification = bi_object(request, BiNotificationItem, pk=pk)
    num = notification.number

    with transaction.atomic():
        write_audit_log(
            request.user,
            notification,
            "delete",
            tenant=request.tenant,
        )
        notification.delete()

    messages.success(request, f"Notification {num} deleted.")
    return redirect("bi:bi_notification_item_list")


@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = bi_object(request, BiNotificationItem, pk=pk)
    now = timezone.now()
    notification.status = "read"
    notification.read_at = now
    notification.save(update_fields=["status", "read_at", "updated_at"])

    messages.success(request, f"Notification {notification.number} marked as read.")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("bi:notification_center")


@login_required
@require_POST
def notification_acknowledge(request, pk):
    notification = bi_object(request, BiNotificationItem, pk=pk)
    now = timezone.now()
    notes = request.POST.get("notes", "").strip()

    notification.status = "acknowledged"
    notification.acknowledged_at = now
    notification.acknowledged_by = request.user
    if notes:
        notification.acknowledgment_notes = notes
    notification.save(
        update_fields=[
            "status",
            "acknowledged_at",
            "acknowledged_by",
            "acknowledgment_notes",
            "updated_at",
        ]
    )

    write_audit_log(
        request.user,
        notification,
        "update",
        changes={"details": f"Acknowledged {notification.number}"},
        tenant=request.tenant,
    )

    messages.success(
        request, f"Notification {notification.number} acknowledged successfully."
    )
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("bi:notification_center")


@login_required
@require_POST
def notification_snooze(request, pk):
    notification = bi_object(request, BiNotificationItem, pk=pk)
    try:
        hours = int(request.POST.get("hours", "4"))
        if hours not in (1, 4, 24, 72):
            hours = 4
    except (ValueError, TypeError, OverflowError):
        hours = 4
    now = timezone.now()

    notification.status = "snoozed"
    notification.snoozed_until = now + timedelta(hours=hours)
    notification.save(update_fields=["status", "snoozed_until", "updated_at"])

    messages.info(
        request, f"Notification {notification.number} snoozed for {hours} hours."
    )
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("bi:notification_center")


@login_required
@require_POST
def notification_escalate(request, pk):
    notification = bi_object(request, BiNotificationItem, pk=pk)
    notification.status = "escalated"
    notification.escalation_level = min(3, notification.escalation_level + 1)
    notification.save(
        update_fields=["status", "escalation_level", "updated_at"]
    )

    write_audit_log(
        request.user,
        notification,
        "update",
        changes={"details": f"Escalated {notification.number} (level {notification.escalation_level})"},
        tenant=request.tenant,
    )

    messages.warning(
        request,
        f"Notification {notification.number} escalated to Level {notification.escalation_level}.",
    )
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("bi:notification_center")
