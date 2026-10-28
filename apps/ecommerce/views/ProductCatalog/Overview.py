from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render

from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductRelationships import ProductRelationship
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


@login_required
def catalog_overview(request):
    tenant = request.tenant

    products_qs = CatalogProduct.objects.filter(tenant=tenant)
    categories_qs = StoreCategory.objects.filter(tenant=tenant)
    variants_qs = ProductVariant.objects.filter(tenant=tenant)
    relationships_qs = ProductRelationship.objects.filter(tenant=tenant)

    product_stats = products_qs.aggregate(
        total_products=Count("id"),
        active_products=Count("id", filter=Q(status="active")),
        draft_products=Count("id", filter=Q(status="draft")),
        avg_score=Avg("pim_completeness"),
    )
    total_products = product_stats["total_products"]
    active_products = product_stats["active_products"]
    draft_products = product_stats["draft_products"]
    avg_pim_completeness = round(product_stats["avg_score"] or 0, 1)

    total_categories = categories_qs.count()
    total_variants = variants_qs.count()
    total_relationships = relationships_qs.count()

    # Zero variant products check
    zero_variant_products = (
        products_qs.annotate(var_count=Count("variants")).filter(var_count=0).count()
    )

    recent_products = (
        products_qs.select_related("primary_category")
        .prefetch_related("variants")
        .order_by("-created_at")[:6]
    )
    recent_categories = (
        categories_qs.select_related("parent")
        .order_by("display_order", "name")[:8]
    )

    context = {
        "total_products": total_products,
        "active_products": active_products,
        "draft_products": draft_products,
        "total_categories": total_categories,
        "total_variants": total_variants,
        "total_relationships": total_relationships,
        "zero_variant_products": zero_variant_products,
        "avg_pim_completeness": avg_pim_completeness,
        "recent_products": recent_products,
        "recent_categories": recent_categories,
    }
    return render(request, "ecommerce/productcatalog/overview.html", context)
