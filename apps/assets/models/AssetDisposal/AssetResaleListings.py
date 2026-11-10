from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetResaleListing(TenantNumbered):
    """
    Asset Resale & Auction Listing [ARSL-].
    Governs equipment remarketing, secondary market auction cataloging,
    buyer negotiation, sales proceeds settlement, and bill of sale compliance.
    """

    NUMBER_PREFIX = "ARSL"

    LISTING_CHANNEL_CHOICES = [
        ("public_auction", "Industrial Auction (Public / Online)"),
        ("private_treaty", "Private Treaty / Direct Negotiation"),
        ("online_marketplace", "B2B Equipment Marketplace"),
        ("employee_sale", "Internal Employee Purchase Program"),
        ("dealer_wholesale", "Dealer Wholesale Liquidation"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Listing"),
        ("listed", "Active on Market"),
        ("bid_received", "Bid / Offer Received"),
        ("negotiation", "Under Negotiation"),
        ("sold", "Awarded / Sold"),
        ("payment_received", "Payment Received & Reconciled"),
        ("delivered", "Delivered / Asset Released"),
        ("unsold_withdrawn", "Unsold / Listing Withdrawn"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending Invoicing / Escrow"),
        ("partial", "Partial Deposit In Hand"),
        ("paid", "Paid in Full"),
        ("waived", "Waived / Written Off"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "listed": "badge-info",
        "bid_received": "badge-amber",
        "negotiation": "badge-amber",
        "sold": "badge-green",
        "payment_received": "badge-green",
        "delivered": "badge-green",
        "unsold_withdrawn": "badge-muted",
        "cancelled": "badge-red",
    }

    LISTING_CHANNEL_CSS = {
        "public_auction": "badge-info",
        "private_treaty": "badge-slate",
        "online_marketplace": "badge-info",
        "employee_sale": "badge-green",
        "dealer_wholesale": "badge-slate",
    }

    PAYMENT_STATUS_CSS = {
        "pending": "badge-amber",
        "partial": "badge-amber",
        "paid": "badge-green",
        "waived": "badge-muted",
    }

    disposal_request = models.ForeignKey(
        "assets.AssetDisposalRequest",
        on_delete=models.CASCADE,
        related_name="resale_listings",
        help_text="Parent disposal authorization request",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.CASCADE,
        related_name="resale_listings",
        help_text="Fixed asset offered for resale",
    )
    buyer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchased_asset_listings",
        help_text="Winning buyer party record",
    )
    broker_auctioneer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="brokered_asset_listings",
        help_text="Remarketing broker or industrial auction house",
    )
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_resale_listings",
        help_text="Internal asset remarketing manager",
    )
    bill_of_sale_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resale_bills_of_sale",
        help_text="Executed Bill of Sale or auction settlement statement",
    )

    listing_channel = models.CharField(
        max_length=24,
        choices=LISTING_CHANNEL_CHOICES,
        default="public_auction",
    )
    listing_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="External auction catalog lot number or portal listing ID",
    )
    listing_date = models.DateField(
        default=timezone.now,
        help_text="Date listing was published or auction cataloged",
    )
    closing_date = models.DateField(
        null=True,
        blank=True,
        help_text="Auction close or bidding deadline date",
    )

    reserve_price = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Confidential minimum reserve amount",
    )
    asking_price = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Public asking or target buy-it-now price",
    )
    highest_bid_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Top standing offer or winning auction bid",
    )

    buyer_contact_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Name of buyer representative",
    )
    buyer_contact_email = models.CharField(
        max_length=254,
        blank=True,
        help_text="Buyer contact email",
    )
    buyer_contact_phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Buyer contact telephone",
    )

    gross_sale_proceeds = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross contract sale price agreed",
    )
    commission_rate_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Auctioneer or broker commission percentage",
    )
    commission_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total commission deducted",
    )
    tax_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Sales or transfer tax collected",
    )
    net_sale_proceeds = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net proceeds received by seller (gross - commission)",
    )

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date buyer remittance cleared",
    )
    pickup_delivery_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date buyer collected equipment",
    )
    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Special conditions of sale, warranty disclaimers, or pickup deadlines",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_arsl_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_arsl_ten_stat"),
            models.Index(fields=["tenant", "listing_channel"], name="idx_arsl_ten_chan"),
            models.Index(fields=["tenant", "listing_date"], name="idx_arsl_ten_ldate"),
        ]

    def __str__(self):
        return f"{self.number} — {self.fixed_asset.name} ({self.get_listing_channel_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def listing_channel_css(self):
        return self.LISTING_CHANNEL_CSS.get(self.listing_channel, "badge-slate")

    @property
    def payment_status_css(self):
        return self.PAYMENT_STATUS_CSS.get(self.payment_status, "badge-slate")

    def calculate_settlement(self):
        """Calculates commission amount and net proceeds."""
        if self.gross_sale_proceeds and self.commission_rate_percent:
            self.commission_amount = (
                self.gross_sale_proceeds * (self.commission_rate_percent / Decimal("100.00"))
            )
        else:
            self.commission_amount = self.commission_amount or Decimal("0.00")

        self.net_sale_proceeds = (self.gross_sale_proceeds or Decimal("0.00")) - self.commission_amount
        return self.net_sale_proceeds
