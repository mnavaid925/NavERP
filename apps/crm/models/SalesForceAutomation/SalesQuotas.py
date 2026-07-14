"""CRM 1.2 Sales Force Automation — SalesQuotas models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class SalesQuota(TenantNumbered):
    """A per-rep (and optional per-territory) sales target for a period (1.2 Forecasting).
    The forecast dashboard rolls weighted pipeline + closed-won against this target."""

    NUMBER_PREFIX = "QTA"

    PERIOD_CHOICES = [
        ("month", "Monthly"),
        ("quarter", "Quarterly"),
        ("year", "Annual"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_sales_quotas")
    territory = models.ForeignKey("Territory", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_quotas")
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="quarter")
    period_year = models.PositiveSmallIntegerField(default=2026)
    period_number = models.PositiveSmallIntegerField(default=1)  # month 1-12 / quarter 1-4 / year=0
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-period_year", "period_number"]
        unique_together = [
            ("tenant", "number"),
            # Territory is part of the key so a rep can hold one quota per territory per period
            # (a null-territory "overall" quota is also enforced friendly-side in the form).
            ("tenant", "owner", "territory", "period_type", "period_year", "period_number"),
        ]
        indexes = [
            models.Index(fields=["tenant", "period_year"], name="crm_qta_tnt_year_idx"),
            models.Index(fields=["tenant", "territory"], name="crm_qta_tnt_terr_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_period_type_display()} {self.period_year}"
