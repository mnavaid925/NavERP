from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class EcommerceConnector(TenantNumbered):
    NUMBER_PREFIX = "ECON"

    CATEGORY_CHOICES = [
        ("erp", "ERP & Back-Office Sync"),
        ("payment", "Payment Gateway Connector"),
        ("shipping", "Shipping & Logistics API"),
        ("marketing", "Marketing & Analytics Tool"),
        ("custom", "Custom Webhook / REST Connector"),
    ]

    PROVIDER_CHOICES = [
        ("netsuite", "Oracle NetSuite ERP"),
        ("sap_s4hana", "SAP S/4HANA ERP"),
        ("ms_dynamics", "Microsoft Dynamics 365"),
        ("odoo", "Odoo ERP"),
        ("stripe", "Stripe Payments"),
        ("adyen", "Adyen Payments"),
        ("paypal", "PayPal Gateway"),
        ("square", "Square Commerce"),
        ("fedex", "FedEx Logistics"),
        ("ups", "UPS Shipping"),
        ("dhl", "DHL Express"),
        ("usps", "USPS Postal Service"),
        ("klaviyo", "Klaviyo Marketing Automation"),
        ("mailchimp", "Mailchimp Newsletter"),
        ("segment", "Twilio Segment CDP"),
        ("braze", "Braze Customer Engagement"),
        ("google_analytics", "Google Analytics 4 / Tag Manager"),
        ("generic_rest", "Generic REST / Webhook API"),
        ("other", "Other Integration Provider"),
    ]

    AUTH_TYPE_CHOICES = [
        ("api_key", "API Key / Secret Token"),
        ("bearer_token", "Bearer Auth Token"),
        ("oauth2", "OAuth 2.0 Credentials"),
        ("basic_auth", "HTTP Basic Authentication"),
        ("hmac_secret", "HMAC Shared Secret"),
        ("none", "No Authentication / Public"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Operational"),
        ("inactive", "Inactive / Paused"),
        ("testing", "Sandbox / Testing"),
        ("error", "Connection Error"),
        ("maintenance", "Scheduled Maintenance"),
    ]

    name = models.CharField(
        max_length=255,
        help_text="Human-readable connector name e.g. NetSuite ERP Production",
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="erp",
        help_text="Category of external system integration",
    )
    provider = models.CharField(
        max_length=40,
        choices=PROVIDER_CHOICES,
        default="generic_rest",
        help_text="Underlying technology provider or standard adapter",
    )
    auth_type = models.CharField(
        max_length=30,
        choices=AUTH_TYPE_CHOICES,
        default="api_key",
        help_text="Authentication protocol and credential mechanism",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Operational status of connector",
    )
    base_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Base API endpoint URL e.g. https://api.stripe.com/v1",
    )
    api_version = models.CharField(
        max_length=50,
        blank=True,
        default="v1",
        help_text="Target API version tag",
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Stored API key or client identifier",
    )
    api_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Sensitive API secret or auth credential",
    )
    account_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="External merchant / account / organization ID",
    )
    is_sandbox = models.BooleanField(
        default=False,
        help_text="Whether connector targets test / sandbox environment",
    )
    timeout_seconds = models.IntegerField(
        default=30,
        help_text="HTTP request timeout in seconds",
    )
    rate_limit_per_minute = models.IntegerField(
        default=120,
        help_text="Throttling rate limit per minute",
    )
    health_status = models.CharField(
        max_length=30,
        default="healthy",
        help_text="Health status: healthy, degraded, down, unknown",
    )
    last_health_check_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last health verification",
    )
    last_error_message = models.TextField(
        blank=True,
        default="",
        help_text="Last diagnostic or error trace returned by endpoint",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Administrative description of connector usage and data flows",
    )

    class Meta:
        db_table = "ecommerce_connector"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_econ_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_econ_ten_status"),
            models.Index(fields=["tenant", "category"], name="idx_econ_ten_cat"),
            models.Index(fields=["tenant", "provider"], name="idx_econ_ten_prov"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_provider_display()})"
