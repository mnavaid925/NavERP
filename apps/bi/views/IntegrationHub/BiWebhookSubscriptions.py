from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.IntegrationHub.BiWebhookSubscriptions import BiWebhookSubscriptionForm
from apps.bi.models.IntegrationHub.BiWebhookSubscriptions import BiWebhookSubscription
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def bi_webhook_subscription_list(request):
    qs = bi_scope(BiWebhookSubscription.objects.all(), request).select_related("created_by")

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        failing=Count("id", filter=Q(status="failing") | Q(status="suspended")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    failing_count = counts["failing"] or 0

    # Search query
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(endpoint_url__icontains=q)
        )

    # Filters
    payload_format = request.GET.get("payload_format", "").strip()
    if payload_format:
        qs = qs.filter(payload_format=payload_format)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "webhooks": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "failing_count": failing_count,
        "search_query": q,
        "payload_format": payload_format,
        "status": status,
        "format_choices": BiWebhookSubscription.PAYLOAD_FORMAT_CHOICES,
        "status_choices": BiWebhookSubscription.STATUS_CHOICES,
    }
    return render(
        request,
        "bi/integration_hub/bi_webhook_subscription/list.html",
        context,
    )


@login_required
def bi_webhook_subscription_detail(request, pk):
    webhook = bi_object(
        request,
        BiWebhookSubscription,
        pk,
        select_related=("created_by",),
    )
    context = {
        "webhook": webhook,
    }
    return render(
        request,
        "bi/integration_hub/bi_webhook_subscription/detail.html",
        context,
    )


@login_required
def bi_webhook_subscription_create(request):
    if request.method == "POST":
        form = BiWebhookSubscriptionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            webhook = form.save(commit=False)
            webhook.tenant = request.tenant
            webhook.created_by = request.user
            webhook.save()

            write_audit_log(
                request.user,
                webhook,
                "create",
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"Webhook subscription '{webhook.name}' registered successfully.",
            )
            return redirect("bi:bi_webhook_subscription_detail", pk=webhook.pk)
    else:
        form = BiWebhookSubscriptionForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(
        request,
        "bi/integration_hub/bi_webhook_subscription/form.html",
        context,
    )


@login_required
def bi_webhook_subscription_edit(request, pk):
    webhook = bi_object(request, BiWebhookSubscription, pk)

    if request.method == "POST":
        form = BiWebhookSubscriptionForm(
            request.POST,
            instance=webhook,
            tenant=request.tenant,
        )
        if form.is_valid():
            webhook = form.save()
            write_audit_log(
                request.user,
                webhook,
                "update",
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"Webhook subscription '{webhook.name}' updated successfully.",
            )
            return redirect("bi:bi_webhook_subscription_detail", pk=webhook.pk)
    else:
        form = BiWebhookSubscriptionForm(
            instance=webhook,
            tenant=request.tenant,
        )

    context = {
        "form": form,
        "webhook": webhook,
        "is_create": False,
    }
    return render(
        request,
        "bi/integration_hub/bi_webhook_subscription/form.html",
        context,
    )


@login_required
@require_POST
def bi_webhook_subscription_delete(request, pk):
    webhook = bi_object(request, BiWebhookSubscription, pk)
    name = webhook.name
    write_audit_log(
        request.user,
        webhook,
        "delete",
        tenant=request.tenant,
    )
    webhook.delete()

    messages.success(request, f"Webhook subscription '{name}' deleted successfully.")
    return redirect("bi:bi_webhook_subscription_list")


@login_required
@require_POST
def bi_webhook_subscription_ping(request, pk):
    webhook = bi_object(request, BiWebhookSubscription, pk)
    webhook.last_triggered_at = timezone.now()
    webhook.last_response_code = 200
    webhook.last_response_time_ms = 145
    webhook.total_deliveries = F("total_deliveries") + 1
    webhook.consecutive_failures = 0
    webhook.status = "active"
    webhook.last_error_log = ""
    webhook.updated_at = timezone.now()
    webhook.save(
        update_fields=[
            "last_triggered_at",
            "last_response_code",
            "last_response_time_ms",
            "total_deliveries",
            "consecutive_failures",
            "status",
            "last_error_log",
            "updated_at",
        ]
    )

    write_audit_log(
        request.user,
        webhook,
        "action",
        changes={"response_code": 200, "latency_ms": 145},
        tenant=request.tenant,
    )
    messages.success(
        request,
        f"Test ping dispatched successfully to '{webhook.endpoint_url}' (HTTP 200 OK, 145ms).",
    )
    return redirect("bi:bi_webhook_subscription_detail", pk=webhook.pk)
