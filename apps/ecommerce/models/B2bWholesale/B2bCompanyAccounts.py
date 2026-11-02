from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class B2bCompanyAccount(TenantNumbered):
    NUMBER_PREFIX = "EBCA"

    PAYMENT_TERMS_CHOICES = [
        ("prepaid", "Prepaid / Advance Payment"),
        ("due_on_receipt", "Due on Receipt"),
        ("net_15", "Net 15 Days"),
        ("net_30", "Net 30 Days"),
        ("net_45", "Net 45 Days"),
        ("net_60", "Net 60 Days"),
        ("net_90", "Net 90 Days"),
    ]

    CREDIT_STATUS_CHOICES = [
        ("good_standing", "Good Standing"),
        ("warning", "Credit Warning"),
        ("exceeded_limit", "Exceeded Limit"),
        ("suspended", "Suspended"),
        ("revoked", "Revoked"),
    ]

    PUNCHOUT_PROTOCOL_CHOICES = [
        ("none", "No Punchout Configured"),
        ("cxml", "cXML (Ariba / Coupa / Jaggaer)"),
        ("oci", "OCI (SAP / Open Catalog Interface)"),
    ]

    STATUS_CHOICES = [
        ("pending_review", "Pending Review"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("suspended", "Suspended"),
        ("closed", "Closed"),
    ]

    company_party = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="b2b_company_accounts",
        help_text="Corporate organization party record in core spine",
    )
    primary_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_b2b_companies",
        help_text="Primary business contact / account executive",
    )
    preferred_currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="b2b_companies",
        help_text="Default billing currency for trade orders and credit limits",
    )
    company_name = models.CharField(
        max_length=255,
        help_text="Corporate entity commercial trading name",
    )
    company_tax_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Federal Tax ID, EIN, or VAT registration number",
    )
    business_registration_number = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="State or national registrar business number",
    )
    website = models.URLField(
        blank=True,
        default="",
        help_text="Official corporate website URL",
    )
    industry = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Sector or industry classification (e.g. Manufacturing, Healthcare)",
    )
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Approved commercial credit line limit",
    )
    available_credit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Current remaining available credit balance",
    )
    payment_terms = models.CharField(
        max_length=25,
        choices=PAYMENT_TERMS_CHOICES,
        default="due_on_receipt",
        help_text="Contractual invoice settlement terms",
    )
    credit_status = models.CharField(
        max_length=25,
        choices=CREDIT_STATUS_CHOICES,
        default="good_standing",
        help_text="Trade credit status",
    )
    requires_po_number = models.BooleanField(
        default=True,
        help_text="Enforce customer Purchase Order (PO) number entry on checkout",
    )
    requires_order_approval = models.BooleanField(
        default=False,
        help_text="Require supervisor sign-off on orders exceeding threshold",
    )
    approval_threshold_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Orders exceeding this sum trigger mandatory approval",
    )
    default_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approver_b2b_companies",
        help_text="Default corporate supervisor who approves high-value orders",
    )
    punchout_enabled = models.BooleanField(
        default=False,
        help_text="Enable e-procurement PunchOut catalog integration",
    )
    punchout_protocol = models.CharField(
        max_length=20,
        choices=PUNCHOUT_PROTOCOL_CHOICES,
        default="none",
        help_text="Integration protocol for e-procurement (cXML or OCI)",
    )
    punchout_identity = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="cXML Buyer Identity / Network ID (e.g. DUNS or Network ID)",
    )
    punchout_shared_secret = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Shared authentication credential token",
    )
    punchout_return_url = models.URLField(
        blank=True,
        default="",
        help_text="Procurement system return URL for punchback cart payload",
    )
    wholesale_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Default wholesale catalog discount percentage",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="pending_review",
        help_text="Corporate account status",
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Internal notes regarding credit assessment and wholesale terms",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_ebca_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_ebca_ten_stat"),
            models.Index(fields=["tenant", "credit_status"], name="idx_ebca_ten_cred"),
            models.Index(fields=["tenant", "company_party"], name="idx_ebca_ten_party"),
        ]

    def __str__(self):
        return f"{self.company_name} ({self.number})"

    def save(self, *args, **kwargs):
        # On initial creation, default available credit to credit limit if not manually set
        if not self.pk and self.available_credit == Decimal("0.00") and self.credit_limit > Decimal("0.00"):
            self.available_credit = self.credit_limit
        super().save(*args, **kwargs)

    def has_available_credit(self, amount):
        """Check whether company has sufficient remaining trade credit."""
        return self.available_credit >= Decimal(str(amount))

    def calculate_discounted_price(self, base_price):
        """Calculate unit price after applying wholesale discount."""
        if not self.wholesale_discount_percent or self.wholesale_discount_percent <= Decimal("0.00"):
            return Decimal(str(base_price))
        factor = Decimal("1.00") - (self.wholesale_discount_percent / Decimal("100.00"))
        return (Decimal(str(base_price)) * factor).quantize(Decimal("0.01"))
