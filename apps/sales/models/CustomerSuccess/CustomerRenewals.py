"""Sales 8.11 — Customer Renewal model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

STAGE_CHOICES = [
    ("upcoming", "Upcoming (90+ Days)"),
    ("engagement", "Active Engagement"),
    ("proposal_sent", "Renewal Proposal Sent"),
    ("negotiation", "Contract Negotiation"),
    ("renewed", "Renewed (Closed-Won)"),
    ("expanded", "Renewed & Expanded"),
    ("churned", "Churned (Closed-Lost)"),
    ("contracted_down", "Contracted Down"),
]

CHURN_RISK_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]


class CustomerRenewal(TenantNumbered):
    NUMBER_PREFIX = "CRN"

    account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_customer_renewals",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_owned_renewals",
        help_text="Assigned CSM or Account Director responsible for renewal",
    )
    original_order = models.ForeignKey(
        "scm.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_renewal_records",
        help_text="Original executed sales order / contract anchor",
    )
    renewal_name = models.CharField(
        max_length=160,
        help_text="e.g. Acme Corp Enterprise Platform 2026-2027 Renewal",
    )
    contract_reference = models.CharField(
        max_length=80,
        blank=True,
        help_text="External contract or MSA reference number",
    )
    current_arr = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Current Annual Recurring Revenue expiring at renewal date",
    )
    projected_renewal_arr = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Projected ARR renewal value factoring in CPI or discounts",
    )
    expansion_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Additional net expansion / upsell value attached to renewal",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="sales_customer_renewals",
    )
    renewal_date = models.DateField(
        help_text="Contract expiration date and required renewal start date",
    )
    target_close_date = models.DateField(
        help_text="Target contract signature date (typically 30-60 days prior)",
    )
    stage = models.CharField(
        max_length=25,
        choices=STAGE_CHOICES,
        default="upcoming",
    )
    churn_risk_flag = models.CharField(
        max_length=15,
        choices=CHURN_RISK_CHOICES,
        default="low",
    )
    renewal_probability_pct = models.PositiveSmallIntegerField(
        default=80,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Estimated probability of renewal success (0-100%)",
    )
    auto_renewal = models.BooleanField(
        default=False,
        help_text="Contract contains evergreen auto-renewal clause",
    )
    notice_period_days = models.PositiveIntegerField(
        default=60,
        help_text="Advance notice window required for cancellation (in days)",
    )
    expansion_opportunity = models.ForeignKey(
        "crm.Opportunity",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_renewal_expansions",
        help_text="Linked CRM opportunity for tracked upsell or cross-sell deals",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["renewal_date", "-current_arr"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_crn_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "account", "stage"], name="sales_crn_acct_stage_idx"),
            models.Index(fields=["tenant", "stage"], name="sales_crn_ten_stage_idx"),
            models.Index(fields=["tenant", "renewal_date"], name="sales_crn_date_idx"),
            models.Index(fields=["tenant", "churn_risk_flag"], name="sales_crn_risk_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'CRN'} - {self.renewal_name} ({self.get_stage_display()})"

    def clean(self):
        super().clean()
        if self.account_id and self.tenant_id:
            if self.account.tenant_id != self.tenant_id:
                raise ValidationError({"account": "The selected customer account belongs to another workspace."})

        if self.owner_id and self.tenant_id:
            if getattr(self.owner, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"owner": "The renewal owner must belong to this workspace."})

        if self.original_order_id and self.tenant_id:
            if self.original_order.tenant_id != self.tenant_id:
                raise ValidationError({"original_order": "The linked order belongs to another workspace."})

        if self.expansion_opportunity_id and self.tenant_id:
            if self.expansion_opportunity.tenant_id != self.tenant_id:
                raise ValidationError({"expansion_opportunity": "The linked opportunity belongs to another workspace."})

        if self.stage == "expanded" and self.expansion_amount <= Decimal("0.00"):
            raise ValidationError({"expansion_amount": "Renewals marked as Expanded must have an expansion amount greater than 0.00."})

    @property
    def stage_badge_class(self):
        mapping = {
            "upcoming": "badge-info",
            "engagement": "badge-amber",
            "proposal_sent": "badge-amber",
            "negotiation": "badge-amber",
            "renewed": "badge-green",
            "expanded": "badge-green",
            "churned": "badge-red",
            "contracted_down": "badge-slate",
        }
        return mapping.get(self.stage, "badge-slate")

    @property
    def risk_badge_class(self):
        mapping = {
            "low": "badge-green",
            "medium": "badge-amber",
            "high": "badge-red",
            "critical": "badge-red",
        }
        return mapping.get(self.churn_risk_flag, "badge-slate")

    @property
    def total_potential_arr(self):
        return (self.projected_renewal_arr or Decimal("0.00")) + (self.expansion_amount or Decimal("0.00"))
