import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.ecommerce.models.AnalyticsBi.AttributionTouchpoints import AttributionTouchpoint
from apps.ecommerce.models.AnalyticsBi.DailySalesSnapshots import DailySalesSnapshot
from apps.ecommerce.models.AnalyticsBi.ProductMerchandisingMetrics import ProductMerchandisingMetric
from apps.ecommerce.models.CartCheckout.Carts import Cart
from apps.ecommerce.models.CartCheckout.CheckoutSessions import CheckoutSession
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder


@login_required
def analytics_cockpit(request):
    tenant = request.tenant
    today = timezone.now().date()

    # 1. Today's live sales KPIs
    today_orders = EcommerceOrder.objects.filter(
        tenant=tenant,
        created_at__date=today,
    ).exclude(status="cancelled")

    order_stats = today_orders.aggregate(
        rev=Sum("total_amount"),
        cnt=Count("id"),
    )
    today_revenue = order_stats["rev"] or Decimal("0.00")
    today_orders_count = order_stats["cnt"] or 0
    today_aov = Decimal("0.00")
    if today_orders_count > 0:
        today_aov = (today_revenue / Decimal(str(today_orders_count))).quantize(Decimal("0.01"))

    # 2. Cart telemetry & recovery
    active_carts_count = Cart.objects.filter(tenant=tenant, status="active").count()
    abandoned_carts_count = Cart.objects.filter(tenant=tenant, status="abandoned").count()
    recovered_carts_count = Cart.objects.filter(tenant=tenant, status="recovered").count()
    total_abandon_pool = abandoned_carts_count + recovered_carts_count
    cart_recovery_rate_pct = Decimal("0.00")
    if total_abandon_pool > 0:
        cart_recovery_rate_pct = (
            (Decimal(str(recovered_carts_count)) / Decimal(str(total_abandon_pool))) * Decimal("100.00")
        ).quantize(Decimal("0.01"))

    # 3. Checkout Funnel Stages
    total_carts = Cart.objects.filter(tenant=tenant).count() or 1
    total_checkouts = CheckoutSession.objects.filter(tenant=tenant).count()
    shipping_sessions = CheckoutSession.objects.filter(
        tenant=tenant,
        current_step__in=["shipping_method", "payment_method", "review", "completed"],
    ).count()
    payment_sessions = CheckoutSession.objects.filter(
        tenant=tenant,
        current_step__in=["payment_method", "review", "completed"],
    ).count()
    completed_orders = EcommerceOrder.objects.filter(tenant=tenant).exclude(status="cancelled").count()

    funnel_stages = [
        {
            "stage": "Cart Created",
            "count": total_carts,
            "pct": 100.0,
            "color": "blue",
        },
        {
            "stage": "Checkout Started",
            "count": total_checkouts,
            "pct": round((total_checkouts / total_carts) * 100.0, 1),
            "color": "purple",
        },
        {
            "stage": "Shipping Selected",
            "count": shipping_sessions,
            "pct": round((shipping_sessions / total_carts) * 100.0, 1),
            "color": "orange",
        },
        {
            "stage": "Payment Step",
            "count": payment_sessions,
            "pct": round((payment_sessions / total_carts) * 100.0, 1),
            "color": "amber",
        },
        {
            "stage": "Order Placed",
            "count": completed_orders,
            "pct": round((completed_orders / total_carts) * 100.0, 1),
            "color": "green",
        },
    ]

    # 4. Recent snapshots & chart trends
    recent_snapshots = list(
        DailySalesSnapshot.objects.filter(tenant=tenant).order_by("-snapshot_date")[:14]
    )
    # reverse for chronological chart
    chronological = list(reversed(recent_snapshots))
    trend_labels = [s.snapshot_date.strftime("%b %d") for s in chronological]
    trend_revenues = [float(s.net_sales) for s in chronological]

    # 5. Top Best Seller products
    top_best_sellers = ProductMerchandisingMetric.objects.filter(
        tenant=tenant,
        velocity_tier="best_seller",
    ).select_related("product", "variant").order_by("-units_sold")[:5]

    # 6. Channel attribution summary
    touchpoint_aggs = (
        AttributionTouchpoint.objects.filter(tenant=tenant)
        .values("channel_type")
        .annotate(
            total_rev=Sum("attributed_revenue"),
            tp_count=Count("id"),
        )
        .order_by("-total_rev")[:6]
    )
    channel_attribution_summary = []
    for agg in touchpoint_aggs:
        channel_attribution_summary.append({
            "channel": dict(AttributionTouchpoint.CHANNEL_CHOICES).get(agg["channel_type"], agg["channel_type"]),
            "revenue": agg["total_rev"] or Decimal("0.00"),
            "count": agg["tp_count"],
        })

    return render(
        request,
        "ecommerce/analytics_bi/cockpit/cockpit.html",
        {
            "today_revenue": today_revenue,
            "today_orders_count": today_orders_count,
            "today_aov": today_aov,
            "active_carts_count": active_carts_count,
            "abandoned_carts_count": abandoned_carts_count,
            "cart_recovery_rate_pct": cart_recovery_rate_pct,
            "funnel_stages": funnel_stages,
            "recent_snapshots": recent_snapshots[:7],
            "top_best_sellers": top_best_sellers,
            "channel_attribution_summary": channel_attribution_summary,
            "trend_labels_json": json.dumps(trend_labels),
            "trend_revenue_json": json.dumps(trend_revenues),
        },
    )
