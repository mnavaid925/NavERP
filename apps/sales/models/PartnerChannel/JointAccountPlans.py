"""Sales 8.14 — JointAccountPlan model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

PLAN_STATUS_CHOICES = [
    ("draft", "Drafting"),
    ("active", "Active & Executing"),
    ("achieved", "Targets Achieved"),
    ("underperforming", "Underperforming"),
    ("closed", "Closed"),
]

CO_SELL_MOTION_CHOICES = [
    ("partner_led", "Partner Led Co-Sell"),
    ("vendor_led", "Vendor Led Co-Sell"),
    ("joint_pursuit", "Equal Joint Pursuit"),
    ("services_only", "Partner Services Only"),
]


class JointAccountPlan(TenantNumbered):
    NUMBER_PREFIX = "JAP"

    partner = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_partner_joint_plans",
        help_text="Partner co-selling on this account",
    )
    client_account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_client_joint_plans",
        help_text="Target enterprise customer account",
    )
    plan_name = models.CharField(max_length=255)
    plan_year = models.PositiveIntegerField(default=2026)
    period_start = models.DateField(default=timezone.localdate)
    period_end = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=PLAN_STATUS_CHOICES,
        default="draft",
    )
    target_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    actual_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="sales_jap_currencies",
    )
    vendor_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_led_joint_plans",
        help_text="Internal Direct AE leading the co-sell motion",
    )
    partner_lead_name = models.CharField(max_length=150)
    partner_lead_email = models.EmailField(blank=True)
    co_sell_motion = models.CharField(
        max_length=30,
        choices=CO_SELL_MOTION_CHOICES,
        default="joint_pursuit",
    )
    strategic_objectives = models.TextField(blank=True)
    joint_value_proposition = models.TextField(blank=True)
    action_items = models.JSONField(default=list, blank=True)
    collateral_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_jap_collaterals",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-target_revenue"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_jap_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "partner", "client_account"], name="sales_jap_part_client_idx"),
            models.Index(fields=["tenant", "status"], name="sales_jap_status_idx"),
            models.Index(fields=["tenant", "co_sell_motion"], name="sales_jap_motion_idx"),
        ]

    def __str__(self):
        partner_name = getattr(self.partner, "name", "Partner")
        client_name = getattr(self.client_account, "name", "Client")
        return f"{self.number} — {self.plan_name} ({partner_name} + {client_name})"

    def clean(self):
        super().clean()
        if self.partner_id and hasattr(self, "tenant_id"):
            if self.partner.tenant_id != self.tenant_id:
                raise ValidationError({"partner": "The selected partner firm belongs to another workspace."})

        if self.client_account_id and hasattr(self, "tenant_id"):
            if self.client_account.tenant_id != self.tenant_id:
                raise ValidationError({"client_account": "The selected customer account belongs to another workspace."})

        if self.partner_id and self.client_account_id and self.partner_id == self.client_account_id:
            raise ValidationError({"client_account": "Partner cannot establish a joint plan targeting itself as the client."})

        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                raise ValidationError({"period_end": "Period end date cannot be earlier than period start date."})

        if self.collateral_document_id and hasattr(self, "tenant_id"):
            if self.collateral_document.tenant_id != self.tenant_id:
                raise ValidationError({"collateral_document": "The attached collateral document belongs to another workspace."})

    @property
    def status_badge_class(self):
        mapping = {
            "active": "badge-green",
            "achieved": "badge-green",
            "draft": "badge-muted",
            "underperforming": "badge-amber",
            "closed": "badge-slate",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def revenue_attainment_pct(self):
        if self.target_revenue and self.target_revenue > 0:
            return round((self.actual_revenue / self.target_revenue) * Decimal("100"), 1)
        return Decimal("0.0")
