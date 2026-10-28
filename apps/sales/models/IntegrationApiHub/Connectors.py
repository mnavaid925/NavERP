"""Sales 8.18 — SalesIntegrationConnector model.

L55 Coexistence Ruling:
This is the 5th integration register across NavERP:
- SCM 4.19 IntegrationEndpoint [CNX-] (supply-chain transport-less)
- Inventory 5.19 IntegrationChannel [INT-] (commerce-stock)
- Accounting 2.15 IntegrationConfig (financial ledger integrations)
- Projects 7.18 ProjectIntegrationConnector [IXC-] (project-scoped workspace sync)
- Sales 8.18 SalesIntegrationConnector [SIC-] (revenue operations, order-to-cash, lead sync, sales alerts, BI warehouse, e-sign)
These registers answer separate domain questions and deliberately coexist.
Sales 8.18 performs ZERO outbound HTTP and writes NO accounting rows directly.
"""
from django.db import models
from django.utils import timezone

from apps.core.crypto import decrypt, encrypt, is_encrypted
from apps.sales.models._base import TenantNumbered

CATEGORY_CHOICES = [
    ("erp", "ERP & Financial"),
    ("marketing", "Marketing Automation"),
    ("communication", "Communication & Telephony"),
    ("bi_warehouse", "BI & Data Warehouse"),
    ("esignature", "E-Signature & CLM"),
    ("custom", "Custom / Other"),
]

PROVIDER_CHOICES = [
    ("sap", "SAP ERP"),
    ("oracle", "Oracle Fusion/EBS"),
    ("netsuite", "Oracle NetSuite"),
    ("dynamics_finance", "Microsoft Dynamics 365 Finance"),
    ("hubspot", "HubSpot CRM/Marketing"),
    ("marketo", "Adobe Marketo Engage"),
    ("pardot", "Salesforce Marketing Cloud Account Engagement (Pardot)"),
    ("eloqua", "Oracle Eloqua"),
    ("slack", "Slack"),
    ("teams", "Microsoft Teams"),
    ("zoom", "Zoom Phone"),
    ("telephony", "Telephony / PBX System"),
    ("tableau", "Tableau"),
    ("powerbi", "Microsoft Power BI"),
    ("looker", "Looker (Google Cloud)"),
    ("snowflake", "Snowflake Data Warehouse"),
    ("docusign", "DocuSign eSignature"),
    ("adobesign", "Adobe Sign"),
    ("pandadoc", "PandaDoc"),
    ("clm", "Contract Lifecycle Management (CLM)"),
    ("custom", "Custom REST/GraphQL Endpoint"),
]

ENVIRONMENT_CHOICES = [
    ("production", "Production"),
    ("sandbox", "Sandbox / Staging"),
    ("development", "Development / Test"),
]

AUTH_METHOD_CHOICES = [
    ("api_key", "API Key / Token"),
    ("oauth2", "OAuth 2.0 (Bearer Token)"),
    ("basic_auth", "HTTP Basic Auth"),
    ("webhook_secret", "HMAC Webhook Secret"),
    ("none", "None / Public"),
]

HEALTH_STATUS_CHOICES = [
    ("connected", "Connected & Healthy"),
    ("degraded", "Degraded Performance"),
    ("error", "Connection Error"),
    ("offline", "Offline / Paused"),
    ("untested", "Untested / Draft"),
]


class SalesIntegrationConnector(TenantNumbered):
    NUMBER_PREFIX = "SIC"

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="erp")
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default="sap")
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default="production")
    base_url = models.URLField(max_length=255, blank=True, default="")
    auth_method = models.CharField(max_length=20, choices=AUTH_METHOD_CHOICES, default="api_key")
    credential_encrypted = models.TextField(blank=True, default="")
    remote_scope_ref = models.CharField(max_length=255, blank=True, default="", help_text="Remote tenant, instance ID, or workspace slug")
    health_status = models.CharField(max_length=20, choices=HEALTH_STATUS_CHOICES, default="untested")
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_sic_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category", "is_active"], name="sales_sic_cat_act_idx"),
            models.Index(fields=["tenant", "provider"], name="sales_sic_provider_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.get_provider_display()})"

    def set_credential(self, raw_secret):
        if raw_secret:
            self.credential_encrypted = encrypt(raw_secret.strip())
        else:
            self.credential_encrypted = ""

    def get_credential(self):
        if not self.credential_encrypted:
            return ""
        return decrypt(self.credential_encrypted)

    @property
    def masked_credential(self):
        if self.credential_encrypted:
            return "••••••••"
        return "None"
