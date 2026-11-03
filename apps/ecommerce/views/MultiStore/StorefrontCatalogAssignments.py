from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MultiStore.StorefrontCatalogAssignments import StorefrontCatalogAssignmentForm
from apps.ecommerce.models.MultiStore.StorefrontCatalogAssignments import StorefrontCatalogAssignment
from apps.ecommerce.models.MultiStore.StorefrontInstances import StorefrontInstance
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def storefront_catalog_assignment_list(request):
    queryset = ecommerce_scope(
        StorefrontCatalogAssignment.objects.select_related("storefront", "product", "custom_currency"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(product__name__icontains=search_query)
            | Q(product__sku__icontains=search_query)
            | Q(custom_title__icontains=search_query)
            | Q(storefront_badge__icontains=search_query)
            | Q(number__icontains=search_query)
        )

    storefront_filter = request.GET.get("storefront", "").strip()
    if storefront_filter:
        queryset = queryset.filter(storefront_id=storefront_filter)

    publish_status_filter = request.GET.get("publish_status", "").strip()
    if publish_status_filter:
        queryset = queryset.filter(publish_status=publish_status_filter)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    storefronts = ecommerce_scope(StorefrontInstance.objects.all(), request)

    context = {
        "catalog_assignments": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "storefront_filter": storefront_filter,
        "publish_status_filter": publish_status_filter,
        "publish_status_choices": StorefrontCatalogAssignment.PUBLISH_STATUS_CHOICES,
        "storefronts": storefronts,
    }
    return render(request, "ecommerce/multi_store/storefront_catalog_assignment/list.html", context)


@login_required
def storefront_catalog_assignment_detail(request, pk):
    assignment = ecommerce_object(
        request,
        StorefrontCatalogAssignment,
        pk=pk,
        select_related=("storefront", "product", "custom_currency"),
    )
    context = {
        "assignment": assignment,
    }
    return render(request, "ecommerce/multi_store/storefront_catalog_assignment/detail.html", context)


@login_required
def storefront_catalog_assignment_create(request):
    initial = {}
    storefront_id = request.GET.get("storefront")
    if storefront_id:
        initial["storefront"] = storefront_id

    if request.method == "POST":
        form = StorefrontCatalogAssignmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.tenant = request.tenant
            assignment.save()
            write_audit_log(
                request.user,
                "CREATE",
                assignment,
                f"Assigned product '{assignment.product.name}' to storefront '{assignment.storefront.name}' ({assignment.number})"
            )
            messages.success(request, f"Product assigned to storefront successfully.")
            return redirect("ecommerce:storefront_catalog_assignment_detail", pk=assignment.pk)
    else:
        form = StorefrontCatalogAssignmentForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "assignment": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/multi_store/storefront_catalog_assignment/form.html", context)


@login_required
def storefront_catalog_assignment_edit(request, pk):
    assignment = ecommerce_object(request, StorefrontCatalogAssignment, pk=pk)
    if request.method == "POST":
        form = StorefrontCatalogAssignmentForm(request.POST, instance=assignment, tenant=request.tenant)
        if form.is_valid():
            assignment = form.save()
            write_audit_log(
                request.user,
                "UPDATE",
                assignment,
                f"Updated catalog assignment for '{assignment.product.name}' on storefront '{assignment.storefront.name}' ({assignment.number})"
            )
            messages.success(request, "Catalog assignment updated successfully.")
            return redirect("ecommerce:storefront_catalog_assignment_detail", pk=assignment.pk)
    else:
        form = StorefrontCatalogAssignmentForm(instance=assignment, tenant=request.tenant)

    context = {
        "form": form,
        "assignment": assignment,
        "is_edit": True,
    }
    return render(request, "ecommerce/multi_store/storefront_catalog_assignment/form.html", context)


@login_required
@require_POST
def storefront_catalog_assignment_delete(request, pk):
    assignment = ecommerce_object(request, StorefrontCatalogAssignment, pk=pk)
    store_name = assignment.storefront.name
    prod_name = assignment.product.name
    num = assignment.number
    assignment.delete()
    write_audit_log(
        request.user,
        "DELETE",
        None,
        f"Removed product '{prod_name}' from storefront '{store_name}' ({num})"
    )
    messages.success(request, f"Product assignment removed.")
    return redirect("ecommerce:storefront_catalog_assignment_list")
