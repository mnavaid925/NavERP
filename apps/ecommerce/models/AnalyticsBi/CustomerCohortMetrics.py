from decimal import Decimal

from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class CustomerCohortMetric(TenantNumbered):
    NUMBER_PREFIX = "ECCM"

    cohort_month = models.DateField(db_index=True, help_text="First day of acquisition month")
    period_offset_months = models.PositiveSmallIntegerField(
        default=0,
        help_text="Months since acquisition (0=acquisition month, 1, 2...)",
    )
    initial_cohort_size = models.PositiveIntegerField(
        default=0,
        help_text="Total distinct customers acquired in cohort month",
    )
    active_customers = models.PositiveIntegerField(
        default=0,
        help_text="Customers from cohort making an order in offset month",
    )
    retention_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    cohort_orders_count = models.PositiveIntegerField(default=0)
    cumulative_gross_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    cumulative_net_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    cumulative_margin = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    cumulative_ltv_per_customer = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    churn_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    acquisition_channel_tag = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Optional segment or channel tag",
    )

    class Meta:
        db_table = "ecommerce_customer_cohort_metric"
        ordering = ["-cohort_month", "period_offset_months"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_eccm_tenant_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "cohort_month", "period_offset_months", "acquisition_channel_tag"],
                name="ecommerce_eccm_ten_coh_off_tag_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "cohort_month"], name="idx_eccm_ten_month"),
        ]

    def __str__(self):
        tag = f" [{self.acquisition_channel_tag}]" if self.acquisition_channel_tag else ""
        return f"{self.number} ({self.cohort_month} +M{self.period_offset_months}{tag} - Retention: {self.retention_rate_pct}%)"

    def recalculate_rates(self):
        """Calculates retention %, churn %, and LTV based on current customer counts and revenue."""
        if self.initial_cohort_size > 0:
            retention = (
                (Decimal(str(self.active_customers)) / Decimal(str(self.initial_cohort_size)))
                * Decimal("100.00")
            )
            self.retention_rate_pct = min(Decimal("100.00"), max(Decimal("0.00"), retention)).quantize(Decimal("0.01"))
            self.churn_rate_pct = max(Decimal("0.00"), (Decimal("100.00") - self.retention_rate_pct)).quantize(Decimal("0.01"))

            ltv = (self.cumulative_net_revenue / Decimal(str(self.initial_cohort_size))).quantize(
                Decimal("0.01")
            )
            self.cumulative_ltv_per_customer = ltv
        else:
            self.retention_rate_pct = Decimal("0.00")
            self.churn_rate_pct = Decimal("0.00")
            self.cumulative_ltv_per_customer = Decimal("0.00")
