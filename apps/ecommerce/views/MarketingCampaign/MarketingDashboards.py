from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render

from apps.ecommerce.models.MarketingCampaign.AffiliatePartners import AffiliatePartner
from apps.ecommerce.models.MarketingCampaign.AffiliateReferralConversions import AffiliateReferralConversion
from apps.ecommerce.models.MarketingCampaign.MarketingCampaigns import MarketingCampaign
from apps.ecommerce.models.MarketingCampaign.SeoMetadataRules import SeoMetadataRule
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.views._common import ecommerce_scope


@login_required
def marketing_dashboard(request):
    tenant = request.tenant

    campaigns_qs = ecommerce_scope(MarketingCampaign.objects.all(), request)
    affiliates_qs = ecommerce_scope(AffiliatePartner.objects.all(), request)
    conversions_qs = ecommerce_scope(AffiliateReferralConversion.objects.all(), request)
    seo_qs = ecommerce_scope(SeoMetadataRule.objects.all(), request)

    campaign_metrics = campaigns_qs.aggregate(
        total_count=Count("id"),
        total_delivered=Sum("delivered_count"),
        total_revenue=Sum("revenue_attributed"),
    )
    total_campaigns = campaign_metrics.get("total_count") or 0
    total_delivered = campaign_metrics.get("total_delivered") or 0
    total_revenue_attributed = campaign_metrics.get("total_revenue") or Decimal("0.00")

    affiliate_metrics = affiliates_qs.aggregate(
        total_count=Count("id"),
        total_revenue=Sum("total_revenue_generated"),
    )
    total_affiliates = affiliate_metrics.get("total_count") or 0
    affiliate_revenue = affiliate_metrics.get("total_revenue") or Decimal("0.00")
    active_seo_rules = seo_qs.filter(is_active=True).count()

    kpis = {
        "total_campaigns": total_campaigns,
        "total_delivered": total_delivered,
        "total_revenue_attributed": total_revenue_attributed,
        "total_affiliates": total_affiliates,
        "total_affiliate_revenue": affiliate_revenue,
        "active_seo_rules": active_seo_rules,
    }

    recent_campaigns = campaigns_qs.order_by("-created_at")[:6]
    top_affiliates = affiliates_qs.filter(status="active").order_by("-total_revenue_generated")[:5]
    recent_conversions = conversions_qs.select_related("affiliate", "order").order_by("-created_at")[:8]
    seo_rules = seo_qs.filter(is_active=True).order_by("-created_at")[:6]

    active_tab = request.GET.get("tab", "overview").strip().lower()

    context = {
        "kpis": kpis,
        "recent_campaigns": recent_campaigns,
        "top_affiliates": top_affiliates,
        "recent_conversions": recent_conversions,
        "seo_rules": seo_rules,
        "active_tab": active_tab,
    }
    return render(request, "ecommerce/marketing_campaign/dashboard/dashboard.html", context)


@login_required
def social_commerce_feed(request):
    """
    Syndicated Social Commerce Catalog Feed for Meta (Instagram/Facebook) & TikTok Shops.
    Returns JSON structured catalog item feed per tenant.
    """
    products = (
        ecommerce_scope(CatalogProduct.objects.all(), request)
        .filter(status="active")
        .select_related("primary_category")
        .prefetch_related("variants")
        .only(
            "id",
            "tenant",
            "number",
            "name",
            "short_description",
            "description",
            "slug",
            "brand",
            "primary_category__id",
            "primary_category__name",
        )[:200]
    )

    items = []
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"

    for p in products:
        variants = list(p.variants.all())
        first_variant = variants[0] if variants else None
        price_val = str(first_variant.price) if first_variant and first_variant.price else "0.00"
        item = {
            "id": (first_variant.sku if first_variant and first_variant.sku else p.number),
            "title": p.name,
            "description": p.short_description or p.description or p.name,
            "availability": "in stock",
            "condition": "new",
            "price": f"{price_val} USD",
            "link": f"{scheme}://{host}/products/{p.slug or p.pk}/",
            "brand": p.brand or "NavStore",
            "google_product_category": p.primary_category.name if p.primary_category else "Apparel & Accessories",
            "item_group_id": p.number,
        }
        items.append(item)

    data = {
        "channel": "NavERP Social Commerce Product Feed",
        "tenant_id": request.tenant.pk,
        "product_count": len(items),
        "items": items,
    }
    return JsonResponse(data, json_dumps_params={"indent": 2})
