from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ProductCatalog.StoreCategories import StoreCategoryForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def storecategory_list(request):
    categories_qs = ecommerce_scope(StoreCategory.objects.select_related("parent"), request)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        categories_qs = categories_qs.filter(
            Q(name__icontains=search_query)
            | Q(slug__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(number__icontains=search_query)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter == "active":
        categories_qs = categories_qs.filter(is_active=True)
    elif status_filter == "inactive":
        categories_qs = categories_qs.filter(is_active=False)

    paginator = Paginator(categories_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "categories": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "status_filter": status_filter,
    }
    return render(request, "ecommerce/productcatalog/storecategory/list.html", context)


@login_required
def storecategory_detail(request, pk):
    category = ecommerce_object(request, StoreCategory, pk=pk, select_related=("parent",))
    children = StoreCategory.objects.filter(tenant=request.tenant, parent=category).order_by("display_order", "name")
    products_qs = (
        CatalogProduct.objects.filter(tenant=request.tenant)
        .filter(Q(primary_category=category) | Q(categories=category))
        .distinct()
        .order_by("name")
    )

    context = {
        "category": category,
        "children": children,
        "products": products_qs,
    }
    return render(request, "ecommerce/productcatalog/storecategory/detail.html", context)


@login_required
def storecategory_create(request):
    if request.method == "POST":
        form = StoreCategoryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            category = form.save(commit=False)
            category.tenant = request.tenant
            category.save()
            write_audit_log(
                request.user,
                category,
                "create",
                {"name": category.name},
            )
            messages.success(request, f"Store category '{category.name}' created successfully.")
            return redirect("ecommerce:storecategory_detail", pk=category.pk)
    else:
        form = StoreCategoryForm(tenant=request.tenant)

    parent_categories = StoreCategory.objects.filter(tenant=request.tenant, is_active=True)
    context = {
        "form": form,
        "category": None,
        "is_edit": False,
        "parent_categories": parent_categories,
    }
    return render(request, "ecommerce/productcatalog/storecategory/form.html", context)


@login_required
def storecategory_edit(request, pk):
    category = ecommerce_object(request, StoreCategory, pk=pk)
    if request.method == "POST":
        form = StoreCategoryForm(request.POST, instance=category, tenant=request.tenant)
        if form.is_valid():
            category = form.save()
            write_audit_log(
                request.user,
                category,
                "update",
                {"name": category.name},
            )
            messages.success(request, f"Store category '{category.name}' updated successfully.")
            return redirect("ecommerce:storecategory_detail", pk=category.pk)
    else:
        form = StoreCategoryForm(instance=category, tenant=request.tenant)

    parent_categories = StoreCategory.objects.filter(tenant=request.tenant, is_active=True).exclude(pk=category.pk)
    context = {
        "form": form,
        "category": category,
        "is_edit": True,
        "parent_categories": parent_categories,
    }
    return render(request, "ecommerce/productcatalog/storecategory/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def storecategory_delete(request, pk):
    category = ecommerce_object(request, StoreCategory, pk=pk)
    name = category.name
    write_audit_log(
        request.user,
        category,
        "delete",
        {"name": name},
    )
    category.delete()
    messages.success(request, f"Store category '{name}' deleted successfully.")
    return redirect("ecommerce:storecategory_list")
