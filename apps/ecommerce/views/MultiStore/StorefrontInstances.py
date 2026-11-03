from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MultiStore.StorefrontInstances import StorefrontInstanceForm
from apps.ecommerce.models.MultiStore.StorefrontInstances import StorefrontInstance
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def storefront_instance_list(request):
    queryset = ecommerce_scope(
        StorefrontInstance.objects.select_related("default_currency", "root_category", "default_fulfillment_center"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(brand_name__icontains=search_query)
            | Q(primary_domain__icontains=search_query)
            | Q(number__icontains=search_query)
        )

    store_type_filter = request.GET.get("store_type", "").strip()
    if store_type_filter:
        queryset = queryset.filter(store_type=store_type_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "storefront_instances": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "store_type_filter": store_type_filter,
        "status_filter": status_filter,
        "store_type_choices": StorefrontInstance.STORE_TYPE_CHOICES,
        "status_choices": StorefrontInstance.STATUS_CHOICES,
    }
    return render(request, "ecommerce/multi_store/storefront_instance/list.html", context)


@login_required
def storefront_instance_detail(request, pk):
    storefront = ecommerce_object(
        request,
        StorefrontInstance,
        pk=pk,
        select_related=("default_currency", "root_category", "default_fulfillment_center"),
    )
    catalog_assignments = storefront.catalog_assignments.select_related("product", "custom_currency")[:10]
    environments = storefront.environments.all()[:10]
    recent_deployments = []
    if environments.exists():
        from apps.ecommerce.models.MultiStore.DeploymentPipelines import DeploymentPipeline
        recent_deployments = ecommerce_scope(
            DeploymentPipeline.objects.filter(environment__in=environments).select_related("environment", "promoted_by"),
            request,
        ).order_by("-created_at")[:5]

    context = {
        "storefront": storefront,
        "catalog_assignments": catalog_assignments,
        "environments": environments,
        "recent_deployments": recent_deployments,
    }
    return render(request, "ecommerce/multi_store/storefront_instance/detail.html", context)


@login_required
def storefront_instance_create(request):
    if request.method == "POST":
        form = StorefrontInstanceForm(request.POST)
        form.tenant = request.tenant
        if form.is_valid():
            storefront = form.save(commit=False)
            storefront.tenant = request.tenant
            if storefront.is_default:
                StorefrontInstance.objects.filter(tenant=request.tenant, is_default=True).update(is_default=False)
            storefront.save()
            write_audit_log(
                request.user,
                "CREATE",
                storefront,
                f"Created storefront channel '{storefront.name}' ({storefront.number})"
            )
            messages.success(request, f"Storefront '{storefront.name}' created successfully.")
            return redirect("ecommerce:storefront_instance_detail", pk=storefront.pk)
    else:
        form = StorefrontInstanceForm()
        form.tenant = request.tenant

    context = {
        "form": form,
        "storefront": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/multi_store/storefront_instance/form.html", context)


@login_required
def storefront_instance_edit(request, pk):
    storefront = ecommerce_object(request, StorefrontInstance, pk=pk)
    if request.method == "POST":
        form = StorefrontInstanceForm(request.POST, instance=storefront)
        form.tenant = request.tenant
        if form.is_valid():
            storefront = form.save(commit=False)
            if storefront.is_default:
                StorefrontInstance.objects.filter(tenant=request.tenant, is_default=True).exclude(pk=storefront.pk).update(is_default=False)
            storefront.save()
            write_audit_log(
                request.user,
                "UPDATE",
                storefront,
                f"Updated storefront channel '{storefront.name}' ({storefront.number})"
            )
            messages.success(request, f"Storefront '{storefront.name}' updated successfully.")
            return redirect("ecommerce:storefront_instance_detail", pk=storefront.pk)
    else:
        form = StorefrontInstanceForm(instance=storefront)
        form.tenant = request.tenant

    context = {
        "form": form,
        "storefront": storefront,
        "is_edit": True,
    }
    return render(request, "ecommerce/multi_store/storefront_instance/form.html", context)


@login_required
@require_POST
def storefront_instance_delete(request, pk):
    storefront = ecommerce_object(request, StorefrontInstance, pk=pk)
    name = storefront.name
    num = storefront.number
    storefront.delete()
    write_audit_log(
        request.user,
        "DELETE",
        None,
        f"Deleted storefront channel '{name}' ({num})"
    )
    messages.success(request, f"Storefront '{name}' was deleted.")
    return redirect("ecommerce:storefront_instance_list")


@login_required
@require_POST
def storefront_toggle_status(request, pk):
    storefront = ecommerce_object(request, StorefrontInstance, pk=pk)
    if storefront.status == "active":
        storefront.status = "maintenance"
    elif storefront.status == "maintenance":
        storefront.status = "active"
    storefront.save()
    write_audit_log(
        request.user,
        "UPDATE",
        storefront,
        f"Toggled status of storefront '{storefront.name}' to '{storefront.get_status_display()}'"
    )
    messages.success(request, f"Storefront status updated to {storefront.get_status_display()}.")
    return redirect("ecommerce:storefront_instance_detail", pk=storefront.pk)
