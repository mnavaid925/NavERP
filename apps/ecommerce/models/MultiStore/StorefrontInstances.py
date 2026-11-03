from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class StorefrontInstance(TenantNumbered):
    NUMBER_PREFIX = "ESTR"

    STORE_TYPE_CHOICES = [
        ("retail_b2c", "Retail B2C"),
        ("wholesale_b2b", "Wholesale B2B"),
        ("hybrid", "Hybrid B2B/B2C"),
        ("brand_boutique", "Brand Boutique"),
        ("outlet_clearance", "Outlet / Clearance"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / In Design"),
        ("active", "Active / Online"),
        ("maintenance", "Maintenance Mode"),
        ("suspended", "Suspended"),
        ("archived", "Archived"),
    ]

    CHECKOUT_MODE_CHOICES = [
        ("standard_multistep", "Standard Multi-Step"),
        ("one_page_express", "One-Page Express"),
        ("headless_api", "Headless API Hand-off"),
    ]

    SSL_STATUS_CHOICES = [
        ("active_provisioned", "Active / Auto-Renewing"),
        ("pending_dns", "Pending DNS Verification"),
        ("custom_cert", "Custom Certificate Uploaded"),
        ("expired", "Expired / Error"),
    ]

    name = models.CharField(max_length=255, help_text="Storefront channel display name")
    code = models.CharField(max_length=50, blank=True, help_text="Unique storefront code/slug")
    store_type = models.CharField(max_length=30, choices=STORE_TYPE_CHOICES, default="retail_b2c")
    brand_name = models.CharField(max_length=150, blank=True, help_text="Brand portfolio name")
    primary_domain = models.CharField(max_length=255, help_text="Canonical domain e.g. shop.acme.com")
    custom_domains = models.TextField(blank=True, help_text="Secondary domains or regional subdomains")
    default_currency = models.ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="storefront_defaults")
    supported_currencies = models.CharField(max_length=255, default="USD,EUR,GBP")
    default_locale = models.CharField(max_length=10, default="en-US")
    supported_locales = models.CharField(max_length=255, default="en-US,es-ES,de-DE,fr-FR")
    root_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storefront_roots",
    )
    default_fulfillment_center = models.ForeignKey(
        "ecommerce.FulfillmentCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storefront_assignments",
    )
    theme_identifier = models.CharField(max_length=100, default="default-slate")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_default = models.BooleanField(default=False, help_text="Primary default store for this tenant")
    checkout_mode = models.CharField(max_length=25, choices=CHECKOUT_MODE_CHOICES, default="standard_multistep")
    ssl_certificate_status = models.CharField(max_length=25, choices=SSL_STATUS_CHOICES, default="active_provisioned")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_default", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_estr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "store_type"], name="idx_estr_ten_stat_type"),
            models.Index(fields=["tenant", "primary_domain"], name="idx_estr_ten_domain"),
            models.Index(fields=["tenant", "-is_default", "name"], name="idx_estr_ten_def_name"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"
