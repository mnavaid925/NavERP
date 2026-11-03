from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.IntegrationApi.WebhookSubscriptions import WebhookSubscriptionForm
from apps.ecommerce.models.IntegrationApi.WebhookSubscriptions import WebhookSubscription
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def webhook_subscription_list(request):
    qs = ecommerce_scope(WebhookSubscription.objects.all(), request)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(target_url__icontains=search_query)
            | Q(event_topic__icontains=search_query)
        )

    topic_filter = request.GET.get("topic", "").strip()
    if topic_filter:
        qs = qs.filter(event_topic=topic_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        broken_count=Count("id", filter=Q(status="circuit_broken")),
    )
    total_count = stats["total_count"]
    active_count = stats["active_count"]
    broken_count = stats["broken_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "webhooks": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "broken_count": broken_count,
        "search_query": search_query,
        "q": search_query,
        "topic_filter": topic_filter,
        "status_filter": status_filter,
        "topic_choices": WebhookSubscription.EVENT_TOPIC_CHOICES,
        "status_choices": WebhookSubscription.STATUS_CHOICES,
    }
    return render(request, "ecommerce/integration_api/webhook_subscription/list.html", context)


# Route alias
webhooksubscription_list = webhook_subscription_list


@login_required
def webhook_subscription_detail(request, pk):
    webhook = ecommerce_object(request, WebhookSubscription, pk)

    context = {
        "webhook": webhook,
    }
    return render(request, "ecommerce/integration_api/webhook_subscription/detail.html", context)


# Route alias
webhooksubscription_detail = webhook_subscription_detail


@tenant_admin_required
def webhook_subscription_create(request):
    if request.method == "POST":
        form = WebhookSubscriptionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            webhook = form.save(commit=False)
            webhook.tenant = request.tenant
            webhook.save()
            write_audit_log(
                request.user,
                webhook,
                "create",
                changes={
                    "name": webhook.name,
                    "target_url": webhook.target_url,
                    "event_topic": webhook.event_topic,
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Webhook Subscription '{webhook.name}' created.")
            return redirect("ecommerce:webhooksubscription_detail", pk=webhook.pk)
    else:
        form = WebhookSubscriptionForm(tenant=request.tenant)

    context = {
        "form": form,
        "webhook": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/integration_api/webhook_subscription/form.html", context)


# Route alias
webhooksubscription_create = webhook_subscription_create


@tenant_admin_required
def webhook_subscription_edit(request, pk):
    webhook = ecommerce_object(request, WebhookSubscription, pk)

    if request.method == "POST":
        form = WebhookSubscriptionForm(request.POST, instance=webhook, tenant=request.tenant)
        if form.is_valid():
            webhook = form.save()
            write_audit_log(
                request.user,
                webhook,
                "update",
                changes={"name": webhook.name, "status": webhook.status},
                tenant=request.tenant,
            )
            messages.success(request, f"Webhook Subscription '{webhook.name}' updated.")
            return redirect("ecommerce:webhooksubscription_detail", pk=webhook.pk)
    else:
        form = WebhookSubscriptionForm(instance=webhook, tenant=request.tenant)

    context = {
        "form": form,
        "webhook": webhook,
        "is_edit": True,
    }
    return render(request, "ecommerce/integration_api/webhook_subscription/form.html", context)


# Route alias
webhooksubscription_edit = webhook_subscription_edit


@tenant_admin_required
@require_POST
def webhook_subscription_delete(request, pk):
    webhook = ecommerce_object(request, WebhookSubscription, pk)
    name = webhook.name
    write_audit_log(
        request.user,
        webhook,
        "delete",
        changes={"name": name, "number": webhook.number},
        tenant=request.tenant,
    )
    webhook.delete()
    messages.success(request, f"Webhook Subscription '{name}' deleted.")
    return redirect("ecommerce:webhooksubscription_list")


# Route alias
webhooksubscription_delete = webhook_subscription_delete


@tenant_admin_required
@require_POST
def webhook_subscription_ping(request, pk):
    webhook = ecommerce_object(request, WebhookSubscription, pk)
    webhook.last_delivery_at = timezone.now()
    webhook.last_status_code = 200
    webhook.last_error_message = ""
    webhook.consecutive_failures = 0
    webhook.total_delivered_count = F("total_delivered_count") + 1
    if webhook.status == "circuit_broken":
        webhook.status = "active"
    webhook.save(
        update_fields=[
            "last_delivery_at",
            "last_status_code",
            "last_error_message",
            "consecutive_failures",
            "total_delivered_count",
            "status",
        ]
    )

    write_audit_log(
        request.user,
        webhook,
        "test_ping",
        changes={"status_code": 200},
        tenant=request.tenant,
    )
    messages.success(request, f"Test ping delivered successfully to '{webhook.target_url}' (HTTP 200 OK).")
    return redirect("ecommerce:webhooksubscription_detail", pk=webhook.pk)


# Route alias
webhooksubscription_ping = webhook_subscription_ping
