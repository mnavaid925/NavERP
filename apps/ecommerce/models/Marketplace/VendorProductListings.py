from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class VendorProductListing(TenantNumbered):
    NUMBER_PREFIX = "EVPL"

    CONDITION_CHOICES = [
        ("new", "Brand New"),
        ("refurbished", "Certified Refurbished"),
        ("used_like_new", "Used - Like New"),
        ("used_good", "Used - Good"),
        ("used_fair", "Used - Fair"),
    ]

    MODERATION_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_review", "Pending Moderation Review"),
        ("approved", "Approved & Live"),
        ("rejected", "Rejected"),
        ("changes_requested", "Changes Requested"),
    ]

    COMPLIANCE_STATUS_CHOICES = [
        ("pending", "Compliance Pending"),
        ("compliant", "Policy Compliant"),
        ("flagged_prohibited", "Prohibited Item Flag"),
        ("counterfeit_suspect", "Counterfeit Suspect"),
        ("ip_infringement", "Trademark / IP Violation"),
    ]

    vendor = models.ForeignKey(
        "ecommerce.MarketplaceVendor",
        on_delete=models.CASCADE,
        related_name="product_listings",
        help_text="Marketplace vendor offering this item",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="vendor_listings",
        help_text="Canonical catalog product master",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_listings",
        help_text="Specific product variant or SKU",
    )
    seller_sku = models.CharField(
        max_length=80,
        help_text="Vendor internal SKU code",
    )
    barcode = models.CharField(
        max_length=60,
        blank=True,
        help_text="UPC, EAN, or ISBN barcode",
    )
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default="new",
        help_text="Item physical cosmetic and functional condition",
    )
    condition_notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Details on packaging, open-box state, or cosmetic blemishes",
    )
    asking_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Seller listing price offered to consumers",
    )
    compare_at_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original MSRP or reference comparison price",
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Vendor wholesale cost basis (for vendor internal margin calculation)",
    )
    available_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Real-time stock units available for immediate dispatch",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Alert threshold for low vendor inventory",
    )
    lead_time_days = models.PositiveIntegerField(
        default=2,
        help_text="Custom dispatch lead time in business days for this item",
    )
    moderation_status = models.CharField(
        max_length=25,
        choices=MODERATION_STATUS_CHOICES,
        default="pending_review",
        db_index=True,
        help_text="Administrative catalog moderation state",
    )
    compliance_status = models.CharField(
        max_length=25,
        choices=COMPLIANCE_STATUS_CHOICES,
        default="pending",
        db_index=True,
        help_text="Legal and counterfeit policy compliance status",
    )
    moderator_notes = models.TextField(
        blank=True,
        help_text="Internal review notes visible to merchant and operator staff",
    )
    rejection_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason code if listing was rejected",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_listings",
        help_text="Operator staff who reviewed this listing",
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when vendor submitted listing for moderation",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when moderation decision was recorded",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this listing is published and purchasable",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_evpl_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "vendor", "seller_sku"],
                name="ecommerce_evpl_ven_sku_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "moderation_status", "is_active"],
                name="idx_evpl_ten_mod_act",
            ),
            models.Index(
                fields=["tenant", "product", "asking_price"],
                name="idx_evpl_ten_prd_price",
            ),
        ]

    def clean(self):
        super().clean()
        if self.asking_price < Decimal("0.00"):
            raise ValidationError({"asking_price": "Asking price cannot be negative."})
        if self.compare_at_price is not None and self.compare_at_price < Decimal("0.00"):
            raise ValidationError({"compare_at_price": "Compare-at price cannot be negative."})
        if self.cost_price is not None and self.cost_price < Decimal("0.00"):
            raise ValidationError({"cost_price": "Cost price cannot be negative."})

        # Tenant boundary check
        if self.vendor_id and hasattr(self, "tenant_id") and self.vendor.tenant_id != self.tenant_id:
            raise ValidationError({"vendor": "Vendor belongs to another workspace."})
        if self.product_id and hasattr(self, "tenant_id") and self.product.tenant_id != self.tenant_id:
            raise ValidationError({"product": "Catalog product belongs to another workspace."})
        if self.variant_id and hasattr(self, "tenant_id") and self.variant.tenant_id != self.tenant_id:
            raise ValidationError({"variant": "Product variant belongs to another workspace."})

    def __str__(self):
        return f"{self.product.name} [{self.seller_sku}] — {self.vendor.store_name} ({self.number})"
