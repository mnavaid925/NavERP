from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetCategory(TenantNumbered):
    """Enterprise asset classification taxonomy node, category types, UNSPSC mapping, and policy profiles [ACAT-]."""

    NUMBER_PREFIX = "ACAT"

    CATEGORY_TYPE_CHOICES = [
        ("machinery", "Machinery & Equipment"),
        ("facility", "Facility & Building Component"),
        ("vehicle", "Fleet & Mobile Equipment"),
        ("it_hardware", "IT & Communication Hardware"),
        ("tooling", "Tooling & Test Instruments"),
        ("furniture", "Furniture & Fixtures"),
        ("infrastructure", "Utility & Civil Infrastructure"),
        ("electrical", "Electrical Distribution"),
        ("piping", "Piping & Fluid Systems"),
        ("other", "Other Capital Asset"),
    ]

    DEPRECIATION_METHOD_CHOICES = [
        ("straight_line", "Straight Line"),
        ("declining_balance", "Declining Balance (150%)"),
        ("double_declining", "Double Declining Balance (200%)"),
        ("sum_of_years", "Sum-of-Years Digits"),
        ("none", "No Depreciation (Land/CIP)"),
    ]

    MAINTENANCE_STRATEGY_CHOICES = [
        ("preventive_calendar", "Calendar-Based PM"),
        ("preventive_meter", "Meter/Usage-Based PM"),
        ("condition_based", "Condition-Based Monitoring (CBM)"),
        ("predictive", "Predictive Maintenance (PdM)"),
        ("run_to_failure", "Run to Failure (Corrective Only)"),
    ]

    CRITICALITY_CHOICES = [
        ("critical", "Critical (Class A)"),
        ("high", "High (Class B)"),
        ("medium", "Medium (Class B)"),
        ("low", "Low (Class C)"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "inactive": "badge-muted",
    }

    CRITICALITY_CSS = {
        "critical": "badge-red",
        "high": "badge-amber",
        "medium": "badge-info",
        "low": "badge-slate",
    }

    code = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Short taxonomy code, e.g. HVAC-CHL, PUMP-CENT, FLEET-FORK",
    )
    name = models.CharField(max_length=150, help_text="Full category title")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent classification node in taxonomy hierarchy",
    )
    category_type = models.CharField(
        max_length=24,
        choices=CATEGORY_TYPE_CHOICES,
        default="machinery",
        help_text="Primary engineering domain classification",
    )

    unspsc_code = models.CharField(
        max_length=16,
        blank=True,
        help_text="8-digit UNSPSC commodity code, e.g. 40151503",
    )
    unspsc_title = models.CharField(
        max_length=150,
        blank=True,
        help_text="UNSPSC commodity category title",
    )

    default_depreciation_method = models.CharField(
        max_length=20,
        choices=DEPRECIATION_METHOD_CHOICES,
        default="straight_line",
        help_text="Default book depreciation method for capital assets in this category",
    )
    default_useful_life_months = models.PositiveIntegerField(
        default=60,
        help_text="Standard accounting and operational useful life in months (e.g. 60 = 5 years)",
    )
    default_maintenance_strategy = models.CharField(
        max_length=24,
        choices=MAINTENANCE_STRATEGY_CHOICES,
        default="preventive_calendar",
        help_text="Default reliability maintenance strategy template",
    )
    default_criticality = models.CharField(
        max_length=10,
        choices=CRITICALITY_CHOICES,
        default="medium",
        help_text="Baseline operational criticality classification",
    )

    description = models.TextField(blank=True, help_text="Scope, guidelines, and inclusion criteria")
    display_order = models.PositiveIntegerField(default=10, help_text="Order in taxonomy listings")
    is_active = models.BooleanField(default=True, help_text="Whether this category is selectable for new assets")

    class Meta:
        db_table = "assets_category"
        ordering = ["display_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="assets_acat_ten_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_acat_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category_type"], name="idx_acat_ten_type"),
            models.Index(fields=["tenant", "parent"], name="idx_acat_ten_parent"),
            models.Index(fields=["tenant", "is_active"], name="idx_acat_ten_active"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
        # Circular hierarchy validation
        if self.parent_id:
            if self.pk and self.parent_id == self.pk:
                raise ValidationError({"parent": "A category cannot be its own parent."})
            visited = {self.pk} if self.pk else set()
            curr = self.parent
            depth = 0
            while curr:
                if self.tenant_id and curr.tenant_id != self.tenant_id:
                    raise ValidationError({"parent": "Parent category belongs to another workspace."})
                depth += 1
                if depth > 10:
                    raise ValidationError({"parent": "Maximum category hierarchy depth (10 levels) exceeded."})
                if curr.pk in visited:
                    raise ValidationError({"parent": "Circular category hierarchy detected."})
                visited.add(curr.pk)
                curr = curr.parent

    @property
    def status_css(self):
        return self.STATUS_CSS.get("active" if self.is_active else "inactive", "badge-muted")

    @property
    def criticality_css(self):
        return self.CRITICALITY_CSS.get(self.default_criticality, "badge-slate")

    @property
    def full_path(self):
        """Breadcrumb path from root to this category."""
        nodes = [self.code]
        curr = self.parent
        depth = 0
        while curr and depth < 10:
            nodes.insert(0, curr.code)
            curr = curr.parent
            depth += 1
        return " / ".join(nodes)
