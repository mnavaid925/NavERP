"""HRM 3.16 Tax & Investment — Taxregimeconfig models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TaxRegimeConfig(TenantOwned):
    """Per-(tenant, financial_year, regime) rate master (3.16) — standard deduction, cess, Section 87A
    rebate, and (via child ``TaxSlabBand`` rows) the slab table the computation engine walks. A small
    settings table, not auto-numbered."""

    REGIME_CHOICES = [
        ("old", "Old Regime"),
        ("new", "New Regime"),
    ]

    financial_year = models.CharField(max_length=10, help_text='Indian FY, e.g. "2025-26".')
    regime = models.CharField(max_length=10, choices=REGIME_CHOICES, default="new")
    standard_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("75000.00"),
        help_text="Flat salary deduction (new-regime default ₹75,000; old-regime ₹50,000).")
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("4.00"),
        help_text="Health & Education Cess applied on the computed tax (both regimes).")
    rebate_income_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Section 87A: taxable-income ceiling at/below which the rebate applies.")
    rebate_max_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Section 87A: the maximum tax the rebate can zero out.")
    is_default_regime = models.BooleanField(default=False,
        help_text="The statutory default regime (new, since FY 2023-24) — drives a declaration's default election.")
    tax_law_reference = models.CharField(max_length=255, blank=True,
        help_text="Free-text note (e.g. Finance Act / Income Tax Act 2025 renumbering caveat).")

    class Meta:
        ordering = ["-financial_year", "regime"]
        unique_together = ("tenant", "financial_year", "regime")
        indexes = [
            models.Index(fields=["tenant", "financial_year"], name="hrm_trc_tenant_fy_idx"),
        ]

    def __str__(self):
        return f"{self.financial_year} · {self.get_regime_display()}"
