import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrderLine
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.models.Personalization.PersonalizedExperiences import PersonalizedExperience
from apps.ecommerce.models.Personalization.RecommendationStrategies import RecommendationStrategy
from apps.ecommerce.models.Personalization.ShopperBehaviorEvents import ShopperBehaviorEvent
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.views._common import ecommerce_scope


def compute_recommendations(tenant, anchor_product=None, strategy=None, max_items=6):
    """
    Computes algorithmic recommendations for a given anchor product and strategy.
    Supports related_products, frequently_bought_together, collaborative, and trending_popular.
    """
    recommended_products = []
    base_qs = (
        CatalogProduct.objects.filter(tenant=tenant)
        .exclude(status="archived")
        .select_related("primary_category")
    )

    if anchor_product:
        base_qs = base_qs.exclude(pk=anchor_product.pk)

    algorithm = strategy.algorithm if strategy else "related_products"
    target_category = strategy.target_category if strategy else None
    min_rating = strategy.min_rating if strategy else 0
    same_brand_only = strategy.same_brand_only if strategy else False

    if target_category:
        base_qs = base_qs.filter(
            Q(primary_category=target_category) | Q(categories=target_category)
        ).distinct()

    if same_brand_only and anchor_product and anchor_product.brand:
        base_qs = base_qs.filter(brand__iexact=anchor_product.brand)

    # 1. Frequently Bought Together (Co-occurrence in order lines)
    if algorithm == "frequently_bought_together" and anchor_product:
        co_order_ids = list(
            EcommerceOrderLine.objects.filter(
                product=anchor_product, order__tenant=tenant
            ).values_list("order_id", flat=True)[:50]
        )

        if co_order_ids:
            co_product_ids = list(
                EcommerceOrderLine.objects.filter(order_id__in=co_order_ids)
                .exclude(product=anchor_product)
                .values("product")
                .annotate(freq=Count("product"))
                .order_by("-freq")
                .values_list("product_id", flat=True)[:max_items]
            )
            recommended_products = list(base_qs.filter(id__in=co_product_ids))

    # 2. Collaborative / Shoppers Also Viewed (Co-viewed in same session)
    elif algorithm == "collaborative_filtering" and anchor_product:
        co_sessions = list(
            ShopperBehaviorEvent.objects.filter(
                tenant=tenant, product=anchor_product
            ).values_list("session_key", flat=True)[:100]
        )

        if co_sessions:
            co_viewed_ids = list(
                ShopperBehaviorEvent.objects.filter(
                    tenant=tenant, session_key__in=co_sessions
                )
                .exclude(product=anchor_product)
                .exclude(product__isnull=True)
                .values("product")
                .annotate(views=Count("product"))
                .order_by("-views")
                .values_list("product_id", flat=True)[:max_items]
            )
            recommended_products = list(base_qs.filter(id__in=co_viewed_ids))

    # 3. Related Products (Same category, similar price bracket)
    elif algorithm == "related_products" and anchor_product and anchor_product.primary_category:
        recommended_products = list(
            base_qs.filter(
                Q(primary_category=anchor_product.primary_category)
                | Q(categories=anchor_product.primary_category)
            )
            .distinct()
            .order_by("-created_at")[:max_items]
        )

    # 4. Trending & Popular (Most clickstream events or recent created)
    elif algorithm == "trending_popular":
        popular_ids = list(
            ShopperBehaviorEvent.objects.filter(tenant=tenant)
            .exclude(product__isnull=True)
            .values("product")
            .annotate(cnt=Count("product"))
            .order_by("-cnt")
            .values_list("product_id", flat=True)[:max_items]
        )
        recommended_products = list(base_qs.filter(id__in=popular_ids))

    # Fallback to general active products if empty or insufficient
    if len(recommended_products) < max_items:
        existing_ids = [p.id for p in recommended_products]
        if anchor_product:
            existing_ids.append(anchor_product.id)
        fillers = list(
            base_qs.exclude(id__in=existing_ids).order_by("-created_at")[: max_items - len(recommended_products)]
        )
        recommended_products.extend(fillers)

    return recommended_products[:max_items]


@login_required
def personalization_console(request):
    tenant = request.tenant

    segments = ecommerce_scope(AudienceSegment.objects.all(), request)
    strategies = ecommerce_scope(RecommendationStrategy.objects.all(), request)
    experiences = ecommerce_scope(PersonalizedExperience.objects.all(), request)
    recent_events = ecommerce_scope(ShopperBehaviorEvent.objects.all(), request).select_related(
        "product", "customer_profile"
    )[:10]

    # Metrics
    vip_segments_count = segments.filter(lifecycle_stage="high_value_vip", is_active=True).count()
    at_risk_count = segments.filter(lifecycle_stage="at_risk", is_active=True).count()
    cart_triggers_count = experiences.filter(
        experience_type="cart_abandonment", is_active=True
    ).count()

    cutoff_24h = timezone.now() - datetime.timedelta(hours=24)
    events_24h_count = ShopperBehaviorEvent.objects.filter(
        tenant=tenant, created_at__gte=cutoff_24h
    ).count()

    # Products for simulation dropdown
    products = CatalogProduct.objects.filter(tenant=tenant).exclude(status="archived").order_by("name")[:30]

    selected_product_id = request.GET.get("product_id")
    selected_strategy_id = request.GET.get("strategy_id")
    selected_segment_id = request.GET.get("segment_id")

    anchor_product = None
    if selected_product_id:
        anchor_product = CatalogProduct.objects.filter(tenant=tenant, pk=selected_product_id).first()
    if not anchor_product and products.exists():
        anchor_product = products.first()
        selected_product_id = str(anchor_product.id) if anchor_product else ""

    selected_strategy = None
    if selected_strategy_id:
        selected_strategy = strategies.filter(pk=selected_strategy_id).first()
    if not selected_strategy and strategies.exists():
        selected_strategy = strategies.first()

    simulated_recommendations = compute_recommendations(
        tenant=tenant,
        anchor_product=anchor_product,
        strategy=selected_strategy,
        max_items=selected_strategy.max_items if selected_strategy else 6,
    )

    simulated_experience = None
    if selected_segment_id:
        simulated_experience = (
            experiences.filter(target_segment_id=selected_segment_id, is_active=True)
            .order_by("-priority")
            .first()
        )
    elif experiences.filter(is_active=True).exists():
        simulated_experience = experiences.filter(is_active=True).order_by("-priority").first()

    context = {
        "segments": segments,
        "strategies": strategies,
        "experiences": experiences,
        "recent_events": recent_events,
        "vip_segments_count": vip_segments_count,
        "at_risk_count": at_risk_count,
        "cart_triggers_count": cart_triggers_count,
        "events_24h_count": events_24h_count,
        "products": products,
        "selected_product_id": selected_product_id,
        "selected_strategy_id": selected_strategy_id,
        "selected_segment_id": selected_segment_id,
        "anchor_product": anchor_product,
        "selected_strategy": selected_strategy,
        "simulated_recommendations": simulated_recommendations,
        "simulated_experience": simulated_experience,
    }
    return render(request, "ecommerce/personalization/console/workbench.html", context)


@login_required
def recommendation_simulate(request):
    tenant = request.tenant
    product_id = request.GET.get("product_id")
    strategy_id = request.GET.get("strategy_id")

    anchor_product = None
    if product_id:
        anchor_product = CatalogProduct.objects.filter(tenant=tenant, pk=product_id).first()

    strategy = None
    if strategy_id:
        strategy = RecommendationStrategy.objects.filter(tenant=tenant, pk=strategy_id).first()

    recommendations = compute_recommendations(
        tenant=tenant,
        anchor_product=anchor_product,
        strategy=strategy,
        max_items=strategy.max_items if strategy else 6,
    )

    context = {
        "anchor_product": anchor_product,
        "strategy": strategy,
        "simulated_recommendations": recommendations,
    }
    return render(
        request,
        "ecommerce/personalization/console/partials/recommendations_preview.html",
        context,
    )
