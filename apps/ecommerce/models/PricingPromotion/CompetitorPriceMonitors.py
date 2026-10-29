from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CompetitorPriceMonitor(TenantNumbered):
    """
    Competitive intelligence tracking, automated price matching rules, and margin protection floors.
    Monitors competitor product listings, compares against cost price, and calculates suggested match prices.
    """

    NUMBER_PREFIX = "ECPM"

    STRATEGY_CHOICES = [
        ("manual", "Manual Review Only"),
        ("match_exact", "Match Competitor Exact Price"),
        ("beat_by_fixed", "Beat Competitor by Fixed Amount"),
        ("beat_by_percent", "Beat Competitor by Percentage"),
    ]

    STATUS_CHOICES = [
        ("active", "Active Tracking"),
        ("paused", "Paused"),
        ("margin_suppressed", "Suppressed (Margin Risk)"),
        ("out_of_stock", "Competitor Out of Stock"),
    ]

    competitor_name = models.CharField(
        max_length=120,
        help_text="Name of competitor retailer (e.g. Amazon, Walmart, BestBuy)",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="competitor_monitors",
        help_text="Tracked catalog product",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.CASCADE,
        related_name="competitor_monitors",
        help_text="Tracked SKU variant",
    )
    competitor_url = models.URLField(
        max_length=500,
        help_text="Public URL to competitor listing for price scraping and verification",
    )
    competitor_price = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Latest observed competitor retail price",
    )
    competitor_currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Currency code of competitor price",
    )
    is_in_stock = models.BooleanField(
        default=True,
        help_text="Whether competitor currently has available stock to deliver",
    )
    last_scraped_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of latest price scrape check",
    )
    match_strategy = models.CharField(
        max_length=30,
        choices=STRATEGY_CHOICES,
        default="manual",
        help_text="Dynamic repricing rule algorithm",
    )
    beat_by_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Fixed amount or percentage to undercut competitor",
    )
    min_margin_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Minimum gross profit margin threshold (%) above variant unit cost",
    )
    floor_price = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Hard price floor below which selling price can never drop",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Monitoring status",
    )
    notes = models.TextField(blank=True, help_text="Market intelligence notes")

    class Meta:
        ordering = ["-last_scraped_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_cpm_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "variant"], name="ecom_cpm_tnt_stat_var_idx"),
        ]

    def __str__(self):
        return f"{self.competitor_name} · {self.variant.sku} (${self.competitor_price})"

    @property
    def margin_floor_price(self):
        """
        Calculates lowest allowed price to preserve minimum margin above item cost.
        """
        cost = Decimal(self.variant.cost_price or 0)
        margin_pct = Decimal(self.min_margin_pct or 0)
        cost_floor = cost * (Decimal("1.0000") + (margin_pct / Decimal("100.00")))
        if self.floor_price is not None:
            return max(cost_floor, Decimal(self.floor_price))
        return cost_floor

    @property
    def suggested_price(self):
        """
        Calculates suggested match price based on strategy, capped by margin floor.
        """
        comp_price = Decimal(self.competitor_price or 0)
        if comp_price <= Decimal("0.0000") or not self.is_in_stock:
            return None

        floor = self.margin_floor_price
        target = comp_price

        if self.match_strategy == "match_exact":
            target = comp_price
        elif self.match_strategy == "beat_by_fixed":
            target = max(Decimal("0.0000"), comp_price - Decimal(self.beat_by_value or 0))
        elif self.match_strategy == "beat_by_percent":
            pct = Decimal(self.beat_by_value or 0)
            target = max(Decimal("0.0000"), comp_price * (Decimal("1.0000") - (pct / Decimal("100.00"))))
        elif self.match_strategy == "manual":
            return None

        return max(floor, target)

    @property
    def is_margin_risk(self):
        """
        Checks if competitor price is lower than our required margin floor.
        """
        if Decimal(self.competitor_price or 0) <= Decimal("0.0000"):
            return False
        return Decimal(self.competitor_price) < self.margin_floor_price
