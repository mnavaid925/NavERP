"""Accounting 2.6 Fixed Assets — FixedAssetsRegister models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ============================================================== 2.6 Fixed Assets
class FixedAsset(TenantNumbered):
    """A capitalised asset with a depreciation method. ``accumulated_depreciation`` is advanced by
    the ``depreciation_run`` action (which posts Dr Depreciation Expense / Cr Accumulated Deprec.)."""

    NUMBER_PREFIX = "FA"

    METHOD_CHOICES = [
        ("straight_line", "Straight Line"),
        ("declining_balance", "Declining Balance (200%)"),
        ("units_of_production", "Units of Production"),
    ]
    STATUS_CHOICES = [
        ("cip", "Construction in Progress"),
        ("active", "In Service"),
        ("disposed", "Disposed"),
    ]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True)
    acquisition_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    salvage_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    useful_life_months = models.PositiveIntegerField(default=60)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="straight_line")
    in_service_date = models.DateField(null=True, blank=True)
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    last_depreciation_date = models.DateField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    asset_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="fixed_assets_cost")
    accumulated_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="fixed_assets_accum")
    expense_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="fixed_assets_expense")
    custodian = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="custodian_assets")
    location = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="located_assets")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_fa_tenant_status_idx")]

    @property
    def depreciable_base(self):
        return (self.acquisition_cost or ZERO) - (self.salvage_value or ZERO)

    def book_value(self):
        return (self.acquisition_cost or ZERO) - (self.accumulated_depreciation or ZERO)

    def remaining_depreciable(self):
        return max(self.depreciable_base - (self.accumulated_depreciation or ZERO), ZERO)

    def period_depreciation(self):
        """One period's depreciation, capped so accumulated never exceeds the depreciable base."""
        base = self.depreciable_base
        life = self.useful_life_months or 1
        if self.method == "declining_balance":
            rate = Decimal(2) / Decimal(life)
            amount = (self.book_value() * rate).quantize(Decimal("0.01"))
        else:  # straight_line and units_of_production (fallback)
            amount = (base / Decimal(life)).quantize(Decimal("0.01"))
        return min(amount, self.remaining_depreciable())

    def __str__(self):
        return f"{self.number} · {self.name}"
