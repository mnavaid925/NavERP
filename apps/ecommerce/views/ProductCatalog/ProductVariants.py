from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ProductCatalog.ProductVariants import ProductVariantForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope
from apps.scm.models.InventoryManagement.Items import Item


@login_required
def productvariant_list(request):
    variants_qs = (
        ecommerce_scope(ProductVariant.objects.all(), request)
        .select_related("product", "item")
        .order_by("product__name", "sort_order", "sku")
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        variants_qs = variants_qs.filter(
            Q(sku__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(barcode__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(product__name__icontains=search_query)
        )

    product_filter = request.GET.get("product", "").strip()
    if product_filter and product_filter.isdigit():
        variants_qs = variants_qs.filter(product_id=product_filter)

    is_active_filter = request.GET.get("is_active", "").strip()
    if is_active_filter == "true":
        variants_qs = variants_qs.filter(is_active=True)
    elif is_active_filter == "false":
        variants_qs = variants_qs.filter(is_active=False)

    paginator = Paginator(variants_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    products_list = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "variants": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "product_filter": product_filter,
        "is_active_filter": is_active_filter,
        "products_list": products_list,
    }
    return render(request, "ecommerce/productcatalog/productvariant/list.html", context)


@login_required
def productvariant_detail(request, pk):
    variant = ecommerce_object(request, ProductVariant, pk=pk, select_related=("product", "item"))
    context = {
        "variant": variant,
        "product": variant.product,
        "item": variant.item,
    }
    return render(request, "ecommerce/productcatalog/productvariant/detail.html", context)


@login_required
def productvariant_create(request):
    initial = {}
    product_id = request.GET.get("product")
    if product_id:
        initial["product"] = product_id

    if request.method == "POST":
        form = ProductVariantForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.tenant = request.tenant
            variant.save()
            write_audit_log(
                request.user,
                variant,
                "create",
                {"sku": variant.sku, "product": variant.product.name},
            )
            messages.success(request, f"Variant '{variant.sku}' created successfully.")
            return redirect("ecommerce:catalogproduct_detail", pk=variant.product_id)
    else:
        form = ProductVariantForm(initial=initial, tenant=request.tenant)

    products_list = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")
    items_list = Item.objects.filter(tenant=request.tenant).order_by("sku")

    context = {
        "form": form,
        "variant": None,
        "is_edit": False,
        "products_list": products_list,
        "items_list": items_list,
    }
    return render(request, "ecommerce/productcatalog/productvariant/form.html", context)


@login_required
def productvariant_edit(request, pk):
    variant = ecommerce_object(request, ProductVariant, pk=pk, select_related=("product", "item"))
    if request.method == "POST":
        form = ProductVariantForm(request.POST, instance=variant, tenant=request.tenant)
        if form.is_valid():
            variant = form.save()
            write_audit_log(
                request.user,
                variant,
                "update",
                {"sku": variant.sku, "product": variant.product.name},
            )
            messages.success(request, f"Variant '{variant.sku}' updated successfully.")
            return redirect("ecommerce:productvariant_detail", pk=variant.pk)
    else:
        form = ProductVariantForm(instance=variant, tenant=request.tenant)

    products_list = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")
    items_list = Item.objects.filter(tenant=request.tenant).order_by("sku")

    context = {
        "form": form,
        "variant": variant,
        "is_edit": True,
        "products_list": products_list,
        "items_list": items_list,
    }
    return render(request, "ecommerce/productcatalog/productvariant/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def productvariant_delete(request, pk):
    variant = ecommerce_object(request, ProductVariant, pk=pk)
    product_pk = variant.product_id
    sku = variant.sku
    write_audit_log(
        request.user,
        variant,
        "delete",
        {"sku": sku},
    )
    variant.delete()
    messages.success(request, f"Variant '{sku}' deleted successfully.")
    return redirect("ecommerce:catalogproduct_detail", pk=product_pk)
