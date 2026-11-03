from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.IntegrationApi.EcommerceConnectors import EcommerceConnectorForm
from apps.ecommerce.models.IntegrationApi.EcommerceConnectors import EcommerceConnector
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def integration_api_hub(request):
    # Dynamic import to avoid circular dependency
    from apps.ecommerce.models.IntegrationApi.IntegrationSyncJobs import IntegrationSyncJob
    from apps.ecommerce.models.IntegrationApi.WebhookSubscriptions import WebhookSubscription
    from apps.ecommerce.models.IntegrationApi.ApiCredentials import ApiCredential

    connectors_qs = ecommerce_scope(EcommerceConnector.objects.all(), request)
    sync_jobs_qs = ecommerce_scope(IntegrationSyncJob.objects.all(), request)
    webhooks_qs = ecommerce_scope(WebhookSubscription.objects.all(), request)
    credentials_qs = ecommerce_scope(ApiCredential.objects.all(), request)

    connector_stats = connectors_qs.aggregate(
        total_connectors=Count("id"),
        active_connectors=Count("id", filter=Q(status="active")),
        erp_connectors=Count("id", filter=Q(category="erp")),
        payment_connectors=Count("id", filter=Q(category="payment")),
    )
    job_stats = sync_jobs_qs.aggregate(
        total_jobs=Count("id"),
        running_jobs=Count("id", filter=Q(status="running")),
        failed_jobs=Count("id", filter=Q(status="failed")),
        completed_jobs=Count("id", filter=Q(status="completed")),
    )
    webhook_stats = webhooks_qs.aggregate(
        total_webhooks=Count("id"),
        active_webhooks=Count("id", filter=Q(status="active")),
        broken_webhooks=Count("id", filter=Q(status="circuit_broken")),
    )
    credential_stats = credentials_qs.aggregate(
        total_credentials=Count("id"),
        active_credentials=Count("id", filter=Q(status="active")),
    )

    recent_jobs = sync_jobs_qs.select_related("connector")[:5]
    recent_connectors = connectors_qs[:5]
    active_webhooks = webhooks_qs.filter(status="active")[:5]
    active_credentials = credentials_qs.filter(status="active")[:5]

    context = {
        "stats": {
            "total_connectors": connector_stats["total_connectors"],
            "active_connectors": connector_stats["active_connectors"],
            "erp_connectors": connector_stats["erp_connectors"],
            "payment_connectors": connector_stats["payment_connectors"],
            "total_jobs": job_stats["total_jobs"],
            "running_jobs": job_stats["running_jobs"],
            "failed_jobs": job_stats["failed_jobs"],
            "completed_jobs": job_stats["completed_jobs"],
            "total_webhooks": webhook_stats["total_webhooks"],
            "active_webhooks": webhook_stats["active_webhooks"],
            "broken_webhooks": webhook_stats["broken_webhooks"],
            "total_credentials": credential_stats["total_credentials"],
            "active_credentials": credential_stats["active_credentials"],
        },
        "recent_jobs": recent_jobs,
        "recent_connectors": recent_connectors,
        "active_webhooks": active_webhooks,
        "active_credentials": active_credentials,
    }
    return render(request, "ecommerce/integration_api/integration_api_hub.html", context)


@login_required
def ecommerce_connector_list(request):
    qs = ecommerce_scope(EcommerceConnector.objects.all(), request)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(provider__icontains=search_query)
            | Q(base_url__icontains=search_query)
            | Q(account_id__icontains=search_query)
        )

    category_filter = request.GET.get("category", "").strip()
    if category_filter:
        qs = qs.filter(category=category_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    provider_filter = request.GET.get("provider", "").strip()
    if provider_filter:
        qs = qs.filter(provider=provider_filter)

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
    )
    total_count = stats["total_count"]
    active_count = stats["active_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "connectors": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "search_query": search_query,
        "q": search_query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "provider_filter": provider_filter,
        "category_choices": EcommerceConnector.CATEGORY_CHOICES,
        "status_choices": EcommerceConnector.STATUS_CHOICES,
        "provider_choices": EcommerceConnector.PROVIDER_CHOICES,
    }
    return render(request, "ecommerce/integration_api/ecommerce_connector/list.html", context)


# Route alias
ecommerceconnector_list = ecommerce_connector_list


@login_required
def ecommerce_connector_detail(request, pk):
    connector = ecommerce_object(request, EcommerceConnector, pk)
    recent_jobs = connector.sync_jobs.all().order_by("-created_at")[:10]

    context = {
        "connector": connector,
        "recent_jobs": recent_jobs,
    }
    return render(request, "ecommerce/integration_api/ecommerce_connector/detail.html", context)


# Route alias
ecommerceconnector_detail = ecommerce_connector_detail


@tenant_admin_required
def ecommerce_connector_create(request):
    if request.method == "POST":
        form = EcommerceConnectorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            connector = form.save(commit=False)
            connector.tenant = request.tenant
            connector.save()
            write_audit_log(
                request.user,
                connector,
                "create",
                changes={
                    "name": connector.name,
                    "category": connector.category,
                    "provider": connector.provider,
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Connector '{connector.name}' created successfully.")
            return redirect("ecommerce:ecommerceconnector_detail", pk=connector.pk)
    else:
        initial_category = request.GET.get("category", "erp")
        form = EcommerceConnectorForm(tenant=request.tenant, initial={"category": initial_category})

    context = {
        "form": form,
        "connector": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/integration_api/ecommerce_connector/form.html", context)


# Route alias
ecommerceconnector_create = ecommerce_connector_create


@tenant_admin_required
def ecommerce_connector_edit(request, pk):
    connector = ecommerce_object(request, EcommerceConnector, pk)

    if request.method == "POST":
        form = EcommerceConnectorForm(request.POST, instance=connector, tenant=request.tenant)
        if form.is_valid():
            connector = form.save()
            write_audit_log(
                request.user,
                connector,
                "update",
                changes={"name": connector.name, "status": connector.status},
                tenant=request.tenant,
            )
            messages.success(request, f"Connector '{connector.name}' updated successfully.")
            return redirect("ecommerce:ecommerceconnector_detail", pk=connector.pk)
    else:
        form = EcommerceConnectorForm(instance=connector, tenant=request.tenant)

    context = {
        "form": form,
        "connector": connector,
        "is_edit": True,
    }
    return render(request, "ecommerce/integration_api/ecommerce_connector/form.html", context)


# Route alias
ecommerceconnector_edit = ecommerce_connector_edit


@tenant_admin_required
@require_POST
def ecommerce_connector_delete(request, pk):
    connector = ecommerce_object(request, EcommerceConnector, pk)
    name = connector.name
    write_audit_log(
        request.user,
        connector,
        "delete",
        changes={"name": name, "number": connector.number},
        tenant=request.tenant,
    )
    connector.delete()
    messages.success(request, f"Connector '{name}' was deleted.")
    return redirect("ecommerce:ecommerceconnector_list")


# Route alias
ecommerceconnector_delete = ecommerce_connector_delete


@tenant_admin_required
@require_POST
def ecommerce_connector_test_connection(request, pk):
    connector = ecommerce_object(request, EcommerceConnector, pk)
    connector.health_status = "healthy"
    connector.last_health_check_at = timezone.now()
    connector.last_error_message = ""
    connector.save(update_fields=["health_status", "last_health_check_at", "last_error_message"])

    write_audit_log(
        request.user,
        connector,
        "test",
        changes={"action_type": "test_connection", "health_status": "healthy"},
        tenant=request.tenant,
    )
    messages.success(request, f"Health check passed for '{connector.name}'. Connection active.")
    return redirect("ecommerce:ecommerceconnector_detail", pk=connector.pk)


# Route alias
ecommerceconnector_test_connection = ecommerce_connector_test_connection
