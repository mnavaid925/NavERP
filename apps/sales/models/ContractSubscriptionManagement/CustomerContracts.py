"""Sales 8.15 — CustomerContract model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

CONTRACT_TYPE_CHOICES = [
    ("subscription_agreement", "Software Subscription Agreement"),
    ("msa", "Master Services Agreement (MSA)"),
    ("sow", "Statement of Work (SOW)"),
    ("sla", "Service Level Agreement (SLA)"),
    ("nda", "Non-Disclosure Agreement (NDA)"),
    ("custom", "Custom Commercial Agreement"),
]

CONTRACT_STATUS_CHOICES = [
    ("draft", "Draft Authoring"),
    ("internal_review", "Internal Legal Review"),
    ("negotiating", "Redlining & Negotiation"),
    ("active", "Active / Executed"),
    ("amended", "Amended"),
    ("terminated", "Terminated"),
    ("expired", "Expired"),
]


class CustomerContract(TenantNumbered):
    NUMBER_PREFIX = "CCT"

    account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="customer_contracts",
    )
    title = models.CharField(max_length=255)
    contract_type = models.CharField(
        max_length=40,
        choices=CONTRACT_TYPE_CHOICES,
        default="subscription_agreement",
    )
    status = models.CharField(
        max_length=30,
        choices=CONTRACT_STATUS_CHOICES,
        default="draft",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_customer_contracts",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="+",
    )
    total_contract_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    annual_contract_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    renewal_term_months = models.PositiveIntegerField(default=12)
    notice_period_days = models.PositiveIntegerField(default=30)
    price_uplift_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    governing_law = models.CharField(max_length=120, blank=True)
    originating_quote = models.ForeignKey(
        "sales.CPQQuote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originated_contracts",
    )
    originating_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originated_contracts",
    )
    template = models.ForeignKey(
        "crm.DocTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_contracts",
    )
    document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_contracts",
    )
    special_terms = models.TextField(blank=True)
    redline_notes = models.TextField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signoff_contact = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_cct_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_cct_ten_status_idx"),
            models.Index(fields=["tenant", "account"], name="sales_cct_ten_acc_idx"),
            models.Index(fields=["tenant", "end_date"], name="sales_cct_ten_end_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be prior to start date."})

        if self.account_id and self.tenant_id and self.account.tenant_id != self.tenant_id:
            raise ValidationError({"account": "Account must belong to this workspace."})

        if self.owner_id and self.tenant_id and getattr(self.owner, "tenant_id", None) != self.tenant_id:
            raise ValidationError({"owner": "Owner must belong to this workspace."})

        if self.originating_quote_id and self.tenant_id and self.originating_quote.tenant_id != self.tenant_id:
            raise ValidationError({"originating_quote": "Originating quote must belong to this workspace."})

        if self.originating_order_id and self.tenant_id and self.originating_order.tenant_id != self.tenant_id:
            raise ValidationError({"originating_order": "Originating order must belong to this workspace."})

        if self.template_id and self.tenant_id and self.template.tenant_id != self.tenant_id:
            raise ValidationError({"template": "Template must belong to this workspace."})

        if self.document_id and self.tenant_id and self.document.tenant_id != self.tenant_id:
            raise ValidationError({"document": "Document must belong to this workspace."})
