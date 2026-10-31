from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
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

    total_campaigns = campaigns_qs.count()
    campaign_metrics = campaigns_qs.aggregate(
        total_delivered=Sum("delivered_count"),
        total_revenue=Sum("revenue_attributed"),
    )
    total_delivered = campaign_metrics.get("total_delivered") or 0
    total_revenue_attributed = campaign_metrics.get("total_revenue") or Decimal("0.00")

    total_affiliates = affiliates_qs.count()
    affiliate_revenue = affiliates_qs.aggregate(total_rev=Sum("total_revenue_generated")).get("total_rev") or Decimal("0.00")
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
    products = ecommerce_scope(CatalogProduct.objects.all(), request).filter(
        is_active=True
    ).select_related("category", "primary_brand")[:200]

    items = []
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"

    for p in products:
        item = {
            "id": p.sku or p.number,
            "title": p.name,
            "description": p.description or p.name,
            "availability": "in stock",
            "condition": "new",
            "price": f"{p.base_price or '0.00'} USD",
            "link": f"{scheme}://{host}/products/{p.slug or p.pk}/",
            "brand": p.primary_brand.name if p.primary_brand else "NavStore",
            "google_product_category": p.category.name if p.category else "Apparel & Accessories",
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
