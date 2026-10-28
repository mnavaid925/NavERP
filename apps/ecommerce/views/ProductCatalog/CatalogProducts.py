from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ProductCatalog.CatalogProducts import CatalogProductForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope
from apps.scm.models.InventoryManagement.Items import Item


@login_required
def catalogproduct_list(request):
    products_qs = (
        ecommerce_scope(CatalogProduct.objects.all(), request)
        .select_related("primary_category", "item")
        .prefetch_related("variants")
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        products_qs = products_qs.filter(
            Q(name__icontains=search_query)
            | Q(slug__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(brand__icontains=search_query)
            | Q(variants__sku__icontains=search_query)
        ).distinct()

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        products_qs = products_qs.filter(status=status_filter)

    visibility_filter = request.GET.get("visibility", "").strip()
    if visibility_filter:
        products_qs = products_qs.filter(visibility=visibility_filter)

    category_filter = request.GET.get("category", "").strip()
    if category_filter and category_filter.isdigit():
        products_qs = products_qs.filter(
            Q(primary_category_id=category_filter) | Q(categories__id=category_filter)
        ).distinct()

    brand_filter = request.GET.get("brand", "").strip()
    if brand_filter:
        products_qs = products_qs.filter(brand=brand_filter)

    paginator = Paginator(products_qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories_list = StoreCategory.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    brands_list = (
        CatalogProduct.objects.filter(tenant=request.tenant)
        .exclude(brand="")
        .values_list("brand", flat=True)
        .distinct()
        .order_by("brand")
    )

    context = {
        "products": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "status_filter": status_filter,
        "visibility_filter": visibility_filter,
        "category_filter": category_filter,
        "brand_filter": brand_filter,
        "status_choices": CatalogProduct.STATUS_CHOICES,
        "visibility_choices": CatalogProduct.VISIBILITY_CHOICES,
        "categories_list": categories_list,
        "brands_list": brands_list,
    }
    return render(request, "ecommerce/productcatalog/catalogproduct/list.html", context)


@login_required
def catalogproduct_detail(request, pk):
    product = ecommerce_object(
        request,
        CatalogProduct,
        pk=pk,
        select_related=("primary_category", "item"),
        prefetch_related=("categories", "variants__item"),
    )

    variants = (
        product.variants.filter(tenant=request.tenant)
        .select_related("item")
        .order_by("sort_order", "sku")
    )

    rels = (
        product.relationships_from.filter(tenant=request.tenant, is_active=True)
        .select_related("target_product__primary_category")
        .order_by("sort_order")
    )

    cross_sells = [r for r in rels if r.relationship_type == "cross_sell"]
    up_sells = [r for r in rels if r.relationship_type == "up_sell"]
    accessories = [r for r in rels if r.relationship_type == "accessory"]
    bundles = [r for r in rels if r.relationship_type == "bundle_kit"]
    bought_together = [r for r in rels if r.relationship_type == "bought_together"]

    context = {
        "product": product,
        "variants": variants,
        "relationships": rels,
        "cross_sells": cross_sells,
        "up_sells": up_sells,
        "accessories": accessories,
        "bundles": bundles,
        "bought_together": bought_together,
    }
    return render(request, "ecommerce/productcatalog/catalogproduct/detail.html", context)


@login_required
def catalogproduct_create(request):
    if request.method == "POST":
        form = CatalogProductForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            product = form.save(commit=False)
            product.tenant = request.tenant
            product.save()
            form.save_m2m()
            write_audit_log(
                request.user,
                product,
                "create",
                {"name": product.name, "number": product.number},
            )
            messages.success(request, f"Product '{product.name}' created successfully.")
            return redirect("ecommerce:catalogproduct_detail", pk=product.pk)
    else:
        form = CatalogProductForm(tenant=request.tenant)

    primary_categories = StoreCategory.objects.filter(tenant=request.tenant, is_active=True)
    items_list = Item.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "product": None,
        "is_edit": False,
        "primary_categories": primary_categories,
        "items_list": items_list,
        "status_choices": CatalogProduct.STATUS_CHOICES,
        "visibility_choices": CatalogProduct.VISIBILITY_CHOICES,
    }
    return render(request, "ecommerce/productcatalog/catalogproduct/form.html", context)


@login_required
def catalogproduct_edit(request, pk):
    product = ecommerce_object(request, CatalogProduct, pk=pk)
    if request.method == "POST":
        form = CatalogProductForm(request.POST, instance=product, tenant=request.tenant)
        if form.is_valid():
            product = form.save()
            write_audit_log(
                request.user,
                product,
                "update",
                {"name": product.name, "number": product.number},
            )
            messages.success(request, f"Product '{product.name}' updated successfully.")
            return redirect("ecommerce:catalogproduct_detail", pk=product.pk)
    else:
        form = CatalogProductForm(instance=product, tenant=request.tenant)

    primary_categories = StoreCategory.objects.filter(tenant=request.tenant, is_active=True)
    items_list = Item.objects.filter(tenant=request.tenant)

    context = {
        "form": form,
        "product": product,
        "is_edit": True,
        "primary_categories": primary_categories,
        "items_list": items_list,
        "status_choices": CatalogProduct.STATUS_CHOICES,
        "visibility_choices": CatalogProduct.VISIBILITY_CHOICES,
    }
    return render(request, "ecommerce/productcatalog/catalogproduct/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def catalogproduct_delete(request, pk):
    product = ecommerce_object(request, CatalogProduct, pk=pk)
    name = product.name
    write_audit_log(
        request.user,
        product,
        "delete",
        {"name": name, "number": product.number},
    )
    product.delete()
    messages.success(request, f"Product '{name}' deleted successfully.")
    return redirect("ecommerce:catalogproduct_list")


@login_required
@require_POST
def catalogproduct_publish(request, pk):
    product = ecommerce_object(request, CatalogProduct, pk=pk)
    if product.status == "active":
        product.status = "draft"
        action_msg = "moved to draft"
    else:
        product.status = "active"
        if not product.published_at:
            product.published_at = timezone.now()
        action_msg = "published live"

    product.save()
    write_audit_log(
        request.user,
        product,
        "update",
        {"action": action_msg, "status": product.status},
    )
    messages.success(request, f"Product '{product.name}' {action_msg}.")
    return redirect("ecommerce:catalogproduct_detail", pk=product.pk)
