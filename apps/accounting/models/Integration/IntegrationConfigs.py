"""Accounting 2.15 Integration & API — IntegrationConfigs models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ================================================================= 2.15 Integration & API
class IntegrationConfig(TenantOwned):
    """An external-service connector configuration. The API secret is NEVER stored — only a prefix
    + SHA-256 hash (lessons L20/L25); the plaintext is revealed exactly once on rotate. Live sync
    against the provider is deferred."""

    PROVIDER_CHOICES = [
        ("plaid", "Plaid"), ("stripe", "Stripe"), ("paypal", "PayPal"), ("square", "Square"),
        ("avalara", "Avalara"), ("vertex", "Vertex"), ("shopify", "Shopify"), ("woocommerce", "WooCommerce"),
        ("salesforce", "Salesforce"), ("hubspot", "HubSpot"), ("quickbooks", "QuickBooks"),
        ("netsuite", "NetSuite"), ("workday", "Workday"), ("custom", "Custom API"),
    ]
    CATEGORY_CHOICES = [
        ("banking", "Banking"), ("payments", "Payments"), ("tax", "Tax"), ("ecommerce", "E-commerce"),
        ("crm", "CRM"), ("erp", "ERP"), ("hris", "HRIS"), ("storage", "Document Storage"), ("other", "Other"),
    ]
    STATUS_CHOICES = [("disconnected", "Disconnected"), ("connected", "Connected"), ("error", "Error")]

    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES, default="custom")
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default="other")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="disconnected")
    api_key_prefix = models.CharField(max_length=12, blank=True, editable=False)
    api_key_hash = models.CharField(max_length=64, blank=True, editable=False)
    last_sync = models.DateTimeField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    @staticmethod
    def hash_secret(secret):
        return hashlib.sha256(secret.encode()).hexdigest()

    def set_secret(self, secret):
        """Store only prefix + hash — never the plaintext (L20/L25)."""
        self.api_key_prefix = secret[:6]
        self.api_key_hash = self.hash_secret(secret)

    @property
    def masked(self):
        if not self.api_key_hash:
            return ""
        return f"{self.api_key_prefix}{'•' * 8}"

    @staticmethod
    def generate_secret():
        return secrets.token_urlsafe(24)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"
