"""CPQQuote model representing enterprise multi-revision sales proposals."""
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from apps.sales.models._base import TenantNumbered


class CPQQuote(TenantNumbered):
    """Master sales proposal header supporting multi-versioning, approval workflows, and order conversion."""

    NUMBER_PREFIX = "CPQ"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_review", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("presented", "Presented"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("converted", "Converted to Order"),
        ("superseded", "Superseded"),
        ("expired", "Expired"),
    ]

    APPROVAL_STATUS_CHOICES = [
        ("not_required", "Not Required"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    name = models.CharField(max_length=255)
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quotes",
    )
    account = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quotes",
        help_text="Customer company / party",
    )
    contact = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_contact_quotes",
        help_text="Primary purchasing contact",
    )
    price_book = models.ForeignKey(
        "crm.PriceBook",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quotes",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="cpq_quotes",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default="not_required")
    approval_rule = models.ForeignKey(
        "sales.QuoteApprovalRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotes",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_cpq_quotes",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_note = models.TextField(blank=True)
    valid_until = models.DateField(null=True, blank=True)

    quote_group_id = models.CharField(max_length=50, db_index=True, blank=True)
    revision_number = models.PositiveIntegerField(default=1)
    revision_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Designates this quote as the primary quote syncing with Opportunity amount",
    )

    header_discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Global quote-level discount applied across all non-optional lines",
    )

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    cost_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    margin_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    margin_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), editable=False)

    proposal_template = models.ForeignKey(
        "crm.DocTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quotes",
    )
    proposal_rendered_content = models.TextField(blank=True, help_text="Rendered HTML snapshot")
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Public e-signature portal attributes
    signing_token = models.CharField(max_length=64, unique=True, db_index=True, blank=True, editable=False)
    signer_name = models.CharField(max_length=255, blank=True)
    signer_title = models.CharField(max_length=120, blank=True)
    signer_email = models.EmailField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signature_data = models.TextField(blank=True, help_text="Typed signature or SVG data")
    # SECURITY — read this before "improving" it. Populated from request.META["REMOTE_ADDR"]
    # and from NOTHING ELSE. X-Forwarded-For (and X-Real-IP, and every other forwarding header)
    # is supplied by the caller: any client can send `X-Forwarded-For: 8.8.8.8`, and with no
    # trusted-proxy list in this repo there is no way to tell a genuine hop from a lie. Trusting
    # the header would write an ATTACKER-CHOSEN string into the evidentiary record of a
    # legally-binding acceptance — the one record whose entire job is to be believable in a
    # dispute. REMOTE_ADDR is set by the WSGI server from the socket, so behind a reverse proxy
    # it records the proxy rather than the signer; a deliberately less precise value that is
    # TRUE beats a precise one that is forgeable. If a trusted-proxy chain is ever configured,
    # THAT is the change to make — not a header read here.
    signer_ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)

    # Order conversion handoff
    converted_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originating_cpq_quotes",
    )
    crm_quote = models.ForeignKey(
        "crm.Quote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quotes",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_owned_quotes",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "number"], name="sales_cpq_tnt_num_idx"),
            models.Index(fields=["tenant", "approval_status"], name="sales_cpq_tnt_appr_idx"),
            models.Index(fields=["tenant", "status"], name="sales_cpq_tnt_status_idx"),
            models.Index(fields=["tenant", "quote_group_id"], name="sales_cpq_tnt_group_idx"),
            models.Index(fields=["tenant", "opportunity"], name="sales_cpq_tnt_opp_idx"),
            models.Index(fields=["tenant", "is_primary"], name="sales_cpq_tnt_prim_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name} (Rev {self.revision_number})"

    def save(self, *args, **kwargs):
        if not self.signing_token:
            self.signing_token = uuid.uuid4().hex
        super().save(*args, **kwargs)
        if not self.quote_group_id:
            self.quote_group_id = self.number
            super().save(update_fields=["quote_group_id"])

    @property
    def is_editable(self):
        return self.status in ["draft", "rejected"]

    @property
    def is_approved(self):
        return self.approval_status in ["approved", "not_required"]

    @property
    def is_expired(self):
        return bool(
            self.valid_until and
            self.status in ["draft", "in_review", "approved", "presented"] and
            self.valid_until < timezone.localdate()
        )

    @property
    def can_convert(self):
        return self.status in ["approved", "presented", "accepted"] and not self.converted_order_id
