from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
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

    total_products = products_qs.count()
    active_products = products_qs.filter(status="active").count()
    draft_products = products_qs.filter(status="draft").count()
    total_categories = categories_qs.count()
    total_variants = variants_qs.count()
    total_relationships = relationships_qs.count()

    # Zero variant products check
    zero_variant_products = (
        products_qs.annotate(var_count=Count("variants")).filter(var_count=0).count()
    )

    # Average PIM readiness score
    avg_score_res = products_qs.aggregate(avg_score=Avg("pim_completeness"))["avg_score"]
    avg_pim_completeness = round(avg_score_res or 0, 1)

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
