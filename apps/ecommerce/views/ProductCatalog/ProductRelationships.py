from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ProductCatalog.ProductRelationships import ProductRelationshipForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductRelationships import ProductRelationship
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def productrelationship_list(request):
    rels_qs = (
        ecommerce_scope(ProductRelationship.objects.all(), request)
        .select_related("source_product", "target_product")
        .order_by("source_product__name", "sort_order")
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        rels_qs = rels_qs.filter(
            Q(source_product__name__icontains=search_query)
            | Q(target_product__name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(notes__icontains=search_query)
        )

    type_filter = request.GET.get("type", "").strip()
    if type_filter:
        rels_qs = rels_qs.filter(relationship_type=type_filter)

    paginator = Paginator(rels_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "relationships": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "type_filter": type_filter,
        "relationship_type_choices": ProductRelationship.RELATIONSHIP_CHOICES,
    }
    return render(request, "ecommerce/productcatalog/productrelationship/list.html", context)


@login_required
def productrelationship_detail(request, pk):
    relationship = ecommerce_object(
        request,
        ProductRelationship,
        pk=pk,
        select_related=("source_product", "target_product"),
    )
    context = {
        "relationship": relationship,
        "source_product": relationship.source_product,
        "target_product": relationship.target_product,
    }
    return render(request, "ecommerce/productcatalog/productrelationship/detail.html", context)


@login_required
def productrelationship_create(request):
    initial = {}
    source_id = request.GET.get("source")
    if source_id:
        initial["source_product"] = source_id

    if request.method == "POST":
        form = ProductRelationshipForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rel = form.save(commit=False)
            rel.tenant = request.tenant
            rel.save()
            write_audit_log(
                request,
                "create",
                rel,
                f"Created relationship {rel.get_relationship_type_display()} from {rel.source_product.name} to {rel.target_product.name}",
            )
            messages.success(request, "Product relationship created successfully.")
            return redirect("ecommerce:catalogproduct_detail", pk=rel.source_product_id)
    else:
        form = ProductRelationshipForm(initial=initial, tenant=request.tenant)

    products_list = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "form": form,
        "relationship": None,
        "is_edit": False,
        "products_list": products_list,
        "relationship_type_choices": ProductRelationship.RELATIONSHIP_CHOICES,
    }
    return render(request, "ecommerce/productcatalog/productrelationship/form.html", context)


@login_required
def productrelationship_edit(request, pk):
    rel = ecommerce_object(request, ProductRelationship, pk=pk, select_related=("source_product", "target_product"))
    if request.method == "POST":
        form = ProductRelationshipForm(request.POST, instance=rel, tenant=request.tenant)
        if form.is_valid():
            rel = form.save()
            write_audit_log(
                request,
                "update",
                rel,
                f"Updated relationship {rel.get_relationship_type_display()} from {rel.source_product.name} to {rel.target_product.name}",
            )
            messages.success(request, "Product relationship updated successfully.")
            return redirect("ecommerce:productrelationship_detail", pk=rel.pk)
    else:
        form = ProductRelationshipForm(instance=rel, tenant=request.tenant)

    products_list = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "form": form,
        "relationship": rel,
        "is_edit": True,
        "products_list": products_list,
        "relationship_type_choices": ProductRelationship.RELATIONSHIP_CHOICES,
    }
    return render(request, "ecommerce/productcatalog/productrelationship/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def productrelationship_delete(request, pk):
    rel = ecommerce_object(request, ProductRelationship, pk=pk)
    source_id = rel.source_product_id
    write_audit_log(request, "delete", rel, f"Deleted product relationship {rel.number}")
    rel.delete()
    messages.success(request, "Product relationship deleted successfully.")
    return redirect("ecommerce:catalogproduct_detail", pk=source_id)
