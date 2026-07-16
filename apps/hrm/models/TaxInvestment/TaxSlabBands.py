"""HRM 3.16 Tax & Investment — TaxSlabBands models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TaxSlabBand(TenantOwned):
    """One income bracket of a ``TaxRegimeConfig``'s slab table (3.16) — walked bracket-by-bracket by
    ``TaxComputation``. Managed inline on the config detail (like ``SalaryStructureLine``)."""

    config = models.ForeignKey("hrm.TaxRegimeConfig", on_delete=models.CASCADE, related_name="slab_bands")
    income_from = models.DecimalField(max_digits=12, decimal_places=2)
    income_to = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Leave blank for the top (unbounded) band.")
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["config", "sequence", "income_from"]
        indexes = [
            models.Index(fields=["tenant", "config"], name="hrm_tsb_tenant_config_idx"),
        ]

    def clean(self):
        super().clean()
        if self.income_to is not None and self.income_from is not None and self.income_to < self.income_from:
            raise ValidationError({"income_to": "Income-to cannot be below income-from."})

    def __str__(self):
        return f"{self.config} · {self.income_from}–{self.income_to or '∞'} @ {self.rate_percent}%"
