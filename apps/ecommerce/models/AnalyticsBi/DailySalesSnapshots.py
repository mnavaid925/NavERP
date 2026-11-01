from decimal import Decimal

from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class DailySalesSnapshot(TenantNumbered):
    NUMBER_PREFIX = "EDSS"

    snapshot_date = models.DateField(db_index=True, help_text="Date of sales aggregation")
    currency = models.CharField(max_length=3, default="USD", help_text="Currency ISO code")
    gross_sales = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discounts_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    refunds_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    net_sales = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    shipping_collected = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    taxes_collected = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    cost_of_goods_sold = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    orders_count = models.PositiveIntegerField(default=0)
    units_sold = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    carts_created = models.PositiveIntegerField(default=0)
    carts_abandoned = models.PositiveIntegerField(default=0)
    conversion_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    is_finalized = models.BooleanField(default=False, help_text="True if closed day snapshot")
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "ecommerce_daily_sales_snapshot"
        ordering = ["-snapshot_date", "currency"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_edss_tenant_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "snapshot_date", "currency"],
                name="ecommerce_edss_tenant_date_curr_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "snapshot_date"], name="idx_edss_ten_date"),
            models.Index(fields=["tenant", "is_finalized"], name="idx_edss_ten_fin"),
        ]

    def __str__(self):
        return f"{self.number} ({self.snapshot_date} - {self.currency} {self.net_sales})"

    @classmethod
    def aggregate_for_tenant_date(cls, tenant, date, currency="USD"):
        """Computes and updates or creates a snapshot from actual tenant orders & carts."""
        from apps.ecommerce.models.CartCheckout.Carts import Cart
        from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder

        order_filter = {
            "tenant": tenant,
            "created_at__date": date,
        }
        if isinstance(currency, str):
            order_filter["currency__code"] = currency
            currency_code = currency
        else:
            order_filter["currency"] = currency
            currency_code = getattr(currency, "code", "USD")

        orders = EcommerceOrder.objects.filter(**order_filter).exclude(status="cancelled")

        order_stats = orders.aggregate(
            total_orders=Count("id"),
            sum_subtotal=Sum("subtotal_amount"),
            sum_discount=Sum("discount_amount"),
            sum_shipping=Sum("shipping_amount"),
            sum_tax=Sum("tax_amount"),
            sum_grand=Sum("total_amount"),
        )

        orders_count = order_stats["total_orders"] or 0
        gross_sales = order_stats["sum_subtotal"] or Decimal("0.00")
        discounts_total = order_stats["sum_discount"] or Decimal("0.00")
        shipping_collected = order_stats["sum_shipping"] or Decimal("0.00")
        taxes_collected = order_stats["sum_tax"] or Decimal("0.00")
        net_sales = order_stats["sum_grand"] or Decimal("0.00")

        # Carts created and abandoned on that date
        carts = Cart.objects.filter(tenant=tenant, created_at__date=date)
        carts_created = carts.count()
        carts_abandoned = carts.filter(status="abandoned").count()

        aov = Decimal("0.00")
        if orders_count > 0:
            aov = (net_sales / Decimal(str(orders_count))).quantize(Decimal("0.01"))

        conversion_rate = Decimal("0.00")
        if carts_created > 0:
            conversion_rate = (
                (Decimal(str(orders_count)) / Decimal(str(carts_created))) * Decimal("100.00")
            ).quantize(Decimal("0.01"))

        snapshot, _ = cls.objects.get_or_create(
            tenant=tenant,
            snapshot_date=date,
            currency=currency_code,
            defaults={
                "gross_sales": gross_sales,
                "discounts_total": discounts_total,
                "net_sales": net_sales,
                "shipping_collected": shipping_collected,
                "taxes_collected": taxes_collected,
                "orders_count": orders_count,
                "average_order_value": aov,
                "carts_created": carts_created,
                "carts_abandoned": carts_abandoned,
                "conversion_rate_pct": conversion_rate,
            },
        )
        if not snapshot.is_finalized:
            snapshot.gross_sales = gross_sales
            snapshot.discounts_total = discounts_total
            snapshot.net_sales = net_sales
            snapshot.shipping_collected = shipping_collected
            snapshot.taxes_collected = taxes_collected
            snapshot.orders_count = orders_count
            snapshot.average_order_value = aov
            snapshot.carts_created = carts_created
            snapshot.carts_abandoned = carts_abandoned
            snapshot.conversion_rate_pct = conversion_rate
            snapshot.save()

        return snapshot
