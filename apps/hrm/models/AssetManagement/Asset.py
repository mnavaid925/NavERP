"""HRM 3.33 Asset Management — Asset models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeOnboarding.Assetallocation import AssetAllocation
from apps.hrm.models.EmployeeOnboarding.Assetallocation import AssetAllocation


# ---------------------------------------------------------------------------
# 3.33 Asset Management — Asset (central register) + AssetMaintenance
#
# The HR-facing asset register the existing AssetAllocation (3.3) issuance rows point at (via the new
# AssetAllocation.asset FK). Depreciation is COMPUTED (properties), not a stored ledger. Coordinates
# with the eventual Module 11 enterprise ``assets.Asset`` (deferred). NUMBER_PREFIX avoids the AST-
# collision with AssetAllocation.
# ---------------------------------------------------------------------------
class Asset(TenantNumbered):
    """A registered company asset (3.33) — ``ASSET-#####``. The central register that AssetAllocation
    issuance rows link to. status/current_holder are kept in sync by AssetAllocation._sync_linked_asset()
    on issue/return; depreciation (accumulated / book value) is computed live, never stored."""

    NUMBER_PREFIX = "ASSET"

    STATUS_CHOICES = [
        ("in_stock", "In Stock"), ("assigned", "Assigned"), ("in_repair", "In Repair"),
        ("retired", "Retired"), ("disposed", "Disposed"),
    ]
    CONDITION_CHOICES = [
        ("new", "New"), ("good", "Good"), ("fair", "Fair"), ("poor", "Poor"), ("damaged", "Damaged"),
    ]
    DEPRECIATION_METHOD_CHOICES = [
        ("none", "No Depreciation"), ("straight_line", "Straight Line"),
        ("declining_balance", "Declining Balance (20%/yr)"),
    ]

    asset_tag = models.CharField(max_length=100, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    # Reuses AssetAllocation.ASSET_CATEGORY_CHOICES verbatim — the taxonomy AssetRequest already follows.
    category = models.CharField(max_length=30, choices=AssetAllocation.ASSET_CATEGORY_CHOICES, default="other")
    manufacturer = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_stock")
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default="good")
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_assets")
    warranty_expiry = models.DateField(null=True, blank=True)
    location = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_assets")
    # Denormalized convenience pointer — kept in sync by AssetAllocation._sync_linked_asset(), never
    # hand-edited by a user (excluded from AssetForm).
    current_holder = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="assets_held")
    depreciation_method = models.CharField(max_length=20, choices=DEPRECIATION_METHOD_CHOICES, default="none")
    useful_life_months = models.PositiveIntegerField(null=True, blank=True)
    salvage_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        default=Decimal("0"))
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_asset_tnt_status_idx"),
            models.Index(fields=["tenant", "category"], name="hrm_asset_tnt_category_idx"),
            models.Index(fields=["tenant", "current_holder"], name="hrm_asset_tnt_holder_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}" if self.number else self.name

    # ---- Depreciation (computed, NEVER stored — Depreciation bullet) ----
    @property
    def months_in_service(self):
        """Whole months from purchase_date to today. 0 if no purchase_date or it is in the future."""
        if not self.purchase_date:
            return 0
        today = timezone.localdate()
        if today <= self.purchase_date:
            return 0
        months = (today.year - self.purchase_date.year) * 12 + (today.month - self.purchase_date.month)
        if today.day < self.purchase_date.day:
            months -= 1
        return max(0, months)

    @property
    def accumulated_depreciation(self):
        """Straight-line: (cost - salvage) * min(months_in_service, useful_life) / useful_life.
        Declining-balance: a documented simplification — fixed 20%/yr reducing-balance, compounded
        monthly (cost * (1 - rate)**months), floored at salvage. Both div-by-zero guarded (no cost,
        method="none", or useful_life None/0 -> Decimal("0"))."""
        if not self.purchase_cost or self.depreciation_method == "none" or not self.useful_life_months:
            return Decimal("0")
        cost = self.purchase_cost
        salvage = self.salvage_value or Decimal("0")
        depreciable = max(Decimal("0"), cost - salvage)
        months = min(self.months_in_service, self.useful_life_months)
        if self.depreciation_method == "straight_line":
            monthly = depreciable / Decimal(self.useful_life_months)
            return (monthly * months).quantize(Decimal("0.01"))
        if self.depreciation_method == "declining_balance":
            rate = Decimal("0.20") / Decimal("12")
            book = cost * ((Decimal("1") - rate) ** months)
            book = max(book, salvage)
            return (cost - book).quantize(Decimal("0.01"))
        return Decimal("0")

    @property
    def current_book_value(self):
        """cost - accumulated_depreciation, floored at salvage_value (never below salvage)."""
        if not self.purchase_cost:
            return Decimal("0")
        salvage = self.salvage_value or Decimal("0")
        value = self.purchase_cost - self.accumulated_depreciation
        return max(value, salvage).quantize(Decimal("0.01"))

    @property
    def is_under_warranty(self):
        return bool(self.warranty_expiry and self.warranty_expiry >= timezone.localdate())
