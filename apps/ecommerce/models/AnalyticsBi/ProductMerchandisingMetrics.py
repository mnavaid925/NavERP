from decimal import Decimal

from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class ProductMerchandisingMetric(TenantNumbered):
    NUMBER_PREFIX = "EPMM"

    VELOCITY_TIER_CHOICES = [
        ("best_seller", "Best Seller (Top Velocity)"),
        ("core_performer", "Core Performer"),
        ("slow_mover", "Slow Mover"),
        ("dead_stock", "Dead Stock / Dormant"),
    ]

    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="merchandising_metrics",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="merchandising_metrics",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    velocity_tier = models.CharField(
        max_length=20,
        choices=VELOCITY_TIER_CHOICES,
        default="core_performer",
    )
    units_sold = models.PositiveIntegerField(default=0)
    gross_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    cost_of_goods = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gross_margin_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    refunds_count = models.PositiveIntegerField(default=0)
    return_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    page_views_count = models.PositiveIntegerField(default=0)
    add_to_cart_count = models.PositiveIntegerField(default=0)
    conversion_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    inventory_turnover_ratio = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "ecommerce_product_merchandising_metric"
        ordering = ["-period_end", "-gross_revenue"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_epmm_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "velocity_tier"], name="idx_epmm_ten_tier"),
            models.Index(fields=["tenant", "product", "period_end"], name="idx_epmm_ten_prd_end"),
        ]

    def __str__(self):
        prod_name = getattr(self.product, "name", "Product")
        return f"{self.number} ({prod_name} - {self.get_velocity_tier_display()})"

    def recalculate_metrics(self):
        """Computes margin %, return rate %, conversion rate %, and assigns velocity tier."""
        if self.gross_revenue > 0:
            margin = (
                ((self.gross_revenue - self.cost_of_goods) / self.gross_revenue) * Decimal("100.00")
            )
            self.gross_margin_pct = max(Decimal("0.00"), margin.quantize(Decimal("0.01")))
        else:
            self.gross_margin_pct = Decimal("0.00")

        if self.units_sold > 0:
            ret_rate = (
                (Decimal(str(self.refunds_count)) / Decimal(str(self.units_sold))) * Decimal("100.00")
            )
            self.return_rate_pct = ret_rate.quantize(Decimal("0.01"))
        else:
            self.return_rate_pct = Decimal("0.00")

        if self.page_views_count > 0:
            conv_rate = (
                (Decimal(str(self.units_sold)) / Decimal(str(self.page_views_count))) * Decimal("100.00")
            )
            self.conversion_rate_pct = conv_rate.quantize(Decimal("0.01"))
        else:
            self.conversion_rate_pct = Decimal("0.00")

        # Velocity tier classification
        if self.units_sold >= 100:
            self.velocity_tier = "best_seller"
        elif self.units_sold >= 20:
            self.velocity_tier = "core_performer"
        elif self.units_sold > 0:
            self.velocity_tier = "slow_mover"
        else:
            self.velocity_tier = "dead_stock"
