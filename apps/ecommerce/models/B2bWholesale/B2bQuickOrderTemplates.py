from django.conf import settings
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class B2bQuickOrderTemplate(TenantNumbered):
    NUMBER_PREFIX = "EBQT"

    SCOPE_CHOICES = [
        ("private", "Private (Author Only)"),
        ("company_shared", "Company-Wide Shared"),
    ]

    CADENCE_CHOICES = [
        ("ad_hoc", "Ad-Hoc / As Needed"),
        ("weekly", "Weekly Replenishment"),
        ("bi_weekly", "Bi-Weekly"),
        ("monthly", "Monthly Replenishment"),
        ("quarterly", "Quarterly"),
    ]

    company = models.ForeignKey(
        "ecommerce.B2bCompanyAccount",
        on_delete=models.CASCADE,
        related_name="quick_order_templates",
        help_text="Wholesale company account owning template",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_quick_order_templates",
        help_text="User who authored this requisition template",
    )
    name = models.CharField(
        max_length=200,
        help_text="Template name (e.g. Weekly Facilities Consumables)",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Instructions or recurring use guidelines",
    )
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default="company_shared",
        help_text="Visibility scope within the organization",
    )
    cadence = models.CharField(
        max_length=20,
        choices=CADENCE_CHOICES,
        default="ad_hoc",
        help_text="Expected replenishment frequency",
    )
    items_data = models.JSONField(
        default=list,
        blank=True,
        help_text="List of items: product_id, sku, name, default_quantity, uom, notes",
    )
    total_items_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of distinct SKU items included in template",
    )
    times_ordered = models.PositiveIntegerField(
        default=0,
        help_text="Number of times orders were generated from this template",
    )
    last_ordered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last date/time an order was executed from this template",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Template active for recurring ordering",
    )

    class Meta:
        ordering = ["company", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_ebqt_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_ebqt_ten_created"),
            models.Index(fields=["tenant", "company", "is_active"], name="idx_ebqt_ten_co_act"),
            models.Index(fields=["tenant", "company"], name="idx_ebqt_ten_co"),
            models.Index(fields=["tenant", "scope"], name="idx_ebqt_ten_scope"),
            models.Index(fields=["tenant", "is_active"], name="idx_ebqt_ten_act"),
        ]

    def __str__(self):
        return f"{self.name} ({self.company.company_name})"

    def update_items_count(self):
        """Update total items count from line items data."""
        self.total_items_count = len(self.items_data or [])
        return self.total_items_count

    def save(self, *args, **kwargs):
        self.update_items_count()
        super().save(*args, **kwargs)
