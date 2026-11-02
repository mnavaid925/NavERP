from decimal import Decimal
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class ChargebackDispute(TenantNumbered):
    NUMBER_PREFIX = "ECBD"

    PAYMENT_METHOD_CHOICES = [
        ("credit_card", "Credit Card"),
        ("debit_card", "Debit Card"),
        ("paypal", "PayPal"),
        ("bank_transfer", "Direct Debit / ACH"),
        ("other", "Other"),
    ]

    REASON_CATEGORY_CHOICES = [
        ("fraudulent", "Fraudulent / Unauthorized Transaction"),
        ("unrecognized", "Unrecognized Card Charge"),
        ("product_not_received", "Merchandise / Service Not Received"),
        ("not_as_described", "Significantly Not as Described / Defective"),
        ("credit_not_processed", "Credit / Refund Not Processed"),
        ("duplicate_charge", "Duplicate Processing"),
        ("subscription_canceled", "Subscription Canceled Prior to Charge"),
        ("other", "Other General Dispute"),
    ]

    STAGE_CHOICES = [
        ("inquiry", "Pre-Dispute Inquiry / Retrieval Request"),
        ("needs_response", "Dispute Received - Action Required"),
        ("under_review", "Evidence Collation Under Review"),
        ("representment_submitted", "Representment Evidence Submitted"),
        ("won", "Resolved: Dispute Won"),
        ("lost", "Resolved: Dispute Lost"),
        ("accepted", "Dispute Accepted (Conceded)"),
    ]

    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.PROTECT,
        related_name="chargeback_disputes",
        help_text="Original disputed customer order",
    )
    customer_party = models.ForeignKey(
        "core.Party",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customer_disputes",
        help_text="Customer identity involved in chargeback",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="disputes",
        help_text="Settlement currency of the disputed transaction",
    )
    dispute_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Disputed transaction amount debited by payment network",
    )
    dispute_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("15.00"),
        help_text="Non-refundable dispute administration fee assessed by payment gateway",
    )
    gateway_dispute_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Processor/Gateway external dispute ID, e.g. dp_1N7xyz",
    )
    payment_method_type = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        default="credit_card",
        help_text="Underlying payment instrument type",
    )
    card_brand = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Credit card brand (Visa, Mastercard, Amex, Discover)",
    )
    reason_category = models.CharField(
        max_length=35,
        choices=REASON_CATEGORY_CHOICES,
        default="fraudulent",
        help_text="High-level category of dispute reason",
    )
    reason_code = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Card scheme specific reason code, e.g. 10.4, 4837, UA01",
    )
    stage = models.CharField(
        max_length=30,
        choices=STAGE_CHOICES,
        default="needs_response",
        help_text="Current regulatory status in representment lifecycle",
    )
    evidence_due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Strict deadline by which representment evidence must be submitted",
    )
    evidence_summary = models.TextField(
        blank=True,
        default="",
        help_text="Summary of collated evidence (tracking logs, signature, IP history)",
    )
    representment_notes = models.TextField(
        blank=True,
        default="",
        help_text="Formal rebuttal statement and argument submitted to card network",
    )
    representment_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when representment evidence was formally submitted",
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when dispute outcome was finalized by scheme",
    )
    outcome_notes = models.TextField(
        blank=True,
        default="",
        help_text="Final card scheme verdict explanation and resolution details",
    )

    class Meta:
        db_table = "ecommerce_chargeback_dispute"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_ecbd_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "stage"], name="idx_ecbd_ten_stage"),
            models.Index(fields=["tenant", "reason_category"], name="idx_ecbd_ten_reason"),
            models.Index(fields=["tenant", "order"], name="idx_ecbd_ten_order"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_reason_category_display()} ({self.currency.code} {self.dispute_amount})"
