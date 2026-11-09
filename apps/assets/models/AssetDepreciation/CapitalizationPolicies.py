from decimal import Decimal, InvalidOperation

from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class CapitalizationPolicy(TenantNumbered):
    """Capital vs Expense determination thresholds, de minimis safe harbor, and accounting rules [ACTH-]."""

    NUMBER_PREFIX = "ACTH"

    POLICY_SCOPE_CHOICES = [
        ("global_default", "Global Tenant Default"),
        ("category_override", "Category-Specific Override"),
        ("tax_book_safe_harbor", "Tax Book De Minimis Safe Harbor"),
        ("project_capex", "Major Capital Project Threshold"),
    ]

    CLASSIFICATION_CHOICES = [
        ("capitalize", "Capitalize into Fixed Assets Register (CapEx)"),
        ("expense_immediately", "Immediate Period Expense (OpEx)"),
        ("manual_review", "Flag for Controller Manual Review"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "draft": "badge-slate",
        "archived": "badge-muted",
    }

    SCOPE_CSS = {
        "global_default": "badge-blue",
        "category_override": "badge-purple",
        "tax_book_safe_harbor": "badge-amber",
        "project_capex": "badge-slate",
    }

    # Policy Scope & Category
    name = models.CharField(
        max_length=150,
        help_text="Policy title, e.g. IRS De Minimis Safe Harbor, Plant Machinery CapEx Rule",
    )
    policy_scope = models.CharField(
        max_length=30, choices=POLICY_SCOPE_CHOICES, default="global_default"
    )
    category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capitalization_policies",
        help_text="Category targeted if category override",
    )

    # Threshold Criteria
    minimum_cost_threshold = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("2500.00"),
        help_text="Minimum cost amount required to capitalize (e.g. $2,500.00 or $5,000.00)",
    )
    minimum_useful_life_months = models.PositiveIntegerField(
        default=12,
        help_text="Minimum economic useful life required for capitalization (standard: >= 12 months)",
    )
    default_classification = models.CharField(
        max_length=24, choices=CLASSIFICATION_CHOICES, default="capitalize"
    )

    # Accounting Standards
    de_minimis_safe_harbor = models.BooleanField(
        default=True,
        help_text="Whether this complies with IRS Reg. 1.263(a)-1(f) de minimis safe harbor",
    )
    applicable_gaap_standard = models.CharField(
        max_length=60,
        default="US GAAP / IFRS IAS 16",
        help_text="Governing accounting framework reference",
    )

    # Default GL Routing
    default_cip_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="policy_cip_accounts",
        help_text="Default CIP clearing account",
    )
    default_expense_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="policy_expense_accounts",
        help_text="Default immediate OpEx expense account if below threshold",
    )

    # Lifecycle & Audit
    policy_notes = models.TextField(
        blank=True,
        help_text="Detailed accounting policy memo, threshold justification, and audit notes",
    )
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "assets_capitalization_policy"
        ordering = ["-is_active", "policy_scope", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_acth_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "policy_scope"], name="idx_acth_ten_scope"),
            models.Index(fields=["tenant", "category"], name="idx_acth_ten_cat"),
            models.Index(fields=["tenant", "is_active"], name="idx_acth_ten_active"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} (${self.minimum_cost_threshold:,.2f})"

    @property
    def status_css(self):
        if self.is_active:
            return self.STATUS_CSS.get("active", "badge-green")
        return self.STATUS_CSS.get("archived", "badge-muted")

    @property
    def scope_css(self):
        return self.SCOPE_CSS.get(self.policy_scope, "badge-slate")

    def evaluate_asset(self, cost, useful_life_months):
        try:
            cost_val = Decimal(str(cost or 0))
            if not cost_val.is_finite() or cost_val < Decimal("0.00") or cost_val >= Decimal("1000000000000"):
                raise ValueError("Invalid cost value")
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Invalid cost value")

        try:
            life_val = int(useful_life_months or 0)
            if life_val < 0 or life_val > 1200:
                raise ValueError("Invalid useful life")
        except (TypeError, ValueError):
            raise ValueError("Invalid useful life")

        meets_cost = cost_val >= self.minimum_cost_threshold
        meets_life = life_val >= self.minimum_useful_life_months

        if meets_cost and meets_life:
            return (
                "capitalize",
                f"Meets capitalization threshold (${self.minimum_cost_threshold:,.2f}) and useful life ({self.minimum_useful_life_months} mos) requirement.",
            )
        elif not meets_cost:
            return (
                self.default_classification,
                f"Cost (${cost_val:,.2f}) is below minimum capitalization threshold (${self.minimum_cost_threshold:,.2f}).",
            )
        else:
            return (
                self.default_classification,
                f"Useful life ({life_val} mos) is below required minimum ({self.minimum_useful_life_months} mos).",
            )
