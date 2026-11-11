import hashlib
import ipaddress
import secrets
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered

ALLOWED_ENDPOINT_SCHEMES = frozenset(
    {"https", "http", "opc.tcp", "mqtts", "mqtt", "tcps", "sftp", "wss"}
)

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "metadata.google.internal",
        "169.254.169.254",
    }
)

BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost")


def validate_connector_endpoint_url(value):
    """Validate industrial/API connector URIs against scheme whitelist and SSRF rules."""
    raw = (value or "").strip()
    if not raw:
        raise ValidationError("Endpoint URL is required.")
    if any(ch.isspace() for ch in raw):
        raise ValidationError("Endpoint URL cannot contain whitespace characters.")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_ENDPOINT_SCHEMES:
        allowed = ", ".join(sorted(ALLOWED_ENDPOINT_SCHEMES))
        raise ValidationError(
            f"Unsupported URI scheme '{scheme or '(none)'}'. Allowed schemes: {allowed}."
        )

    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValidationError("Endpoint URL contains an invalid port number.") from exc

    hostname = (parsed.hostname or "").rstrip(".").lower()
    if not hostname:
        raise ValidationError("Endpoint URL must include a valid host name or address.")

    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(BLOCKED_HOST_SUFFIXES):
        raise ValidationError(
            "Localhost, link-local, and internal host targets are not permitted."
        )

    try:
        ip_obj = ipaddress.ip_address(hostname)
    except ValueError:
        ip_obj = None

    if ip_obj is not None and (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        raise ValidationError(
            "Private, loopback, link-local, multicast, or reserved IP addresses are not permitted."
        )

    return raw


class AssetIntegrationConnector(TenantNumbered):
    """
    Registered integration connector linking NavERP Asset Management with external
    ERP/procurement suites, IoT/SCADA gateways, CMMS/EAM systems, GL engines, and GIS services.
    """

    NUMBER_PREFIX = "AICN"

    CATEGORY_CHOICES = [
        ("erp_procurement", "ERP & Procurement"),
        ("iot_scada", "IoT & SCADA Systems"),
        ("cmms_eam", "CMMS / EAM Connectivity"),
        ("financial_gl", "Financial Systems & GL"),
        ("gis_spatial", "GIS & Mapping Tools"),
    ]

    PROVIDER_CHOICES = [
        ("sap_s4hana", "SAP S/4HANA"),
        ("oracle_fusion", "Oracle Fusion Cloud"),
        ("netsuite", "Oracle NetSuite"),
        ("microsoft_d365", "Microsoft Dynamics 365"),
        ("maximo_eam", "IBM Maximo EAM"),
        ("infor_eam", "Infor EAM"),
        ("fiix", "Fiix CMMS"),
        ("osisoft_pi", "AVEVA / OSIsoft PI"),
        ("kepware_opcua", "Kepware OPC-UA"),
        ("esri_arcgis", "Esri ArcGIS"),
        ("qgis_postgis", "QGIS / PostGIS"),
        ("custom_webhook", "Custom Webhook / API"),
    ]

    PROTOCOL_CHOICES = [
        ("rest_json", "REST / JSON"),
        ("odata_v4", "OData v4"),
        ("opc_ua", "OPC-UA"),
        ("mqtt_tls", "MQTT over TLS"),
        ("modbus_tcp", "Modbus TCP"),
        ("graphql", "GraphQL"),
        ("sftp_csv", "SFTP / CSV"),
        ("arcgis_feature_svc", "ArcGIS Feature Service"),
    ]

    SYNC_DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]

    ENVIRONMENT_CHOICES = [
        ("production", "Production"),
        ("staging", "Staging"),
        ("sandbox", "Sandbox"),
    ]

    AUTH_METHOD_CHOICES = [
        ("api_key", "API Key"),
        ("oauth2_client", "OAuth 2.0 Client Credentials"),
        ("mtls_cert", "Mutual TLS (mTLS)"),
        ("hmac_sha256", "HMAC-SHA256 Signature"),
        ("basic_vault", "Vault-Backed Basic Auth"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("error", "Error"),
        ("decommissioned", "Decommissioned"),
    ]

    HEALTH_STATUS_CHOICES = [
        ("healthy", "Healthy"),
        ("degraded", "Degraded"),
        ("unreachable", "Unreachable"),
        ("unverified", "Unverified"),
    ]

    STATUS_BADGE_MAP = {
        "draft": "badge-slate",
        "active": "badge-green",
        "paused": "badge-amber",
        "error": "badge-red",
        "decommissioned": "badge-muted",
    }

    HEALTH_BADGE_MAP = {
        "healthy": "badge-green",
        "degraded": "badge-amber",
        "unreachable": "badge-red",
        "unverified": "badge-slate",
    }

    name = models.CharField(max_length=160)
    connector_category = models.CharField(
        max_length=24, choices=CATEGORY_CHOICES, default="erp_procurement"
    )
    provider = models.CharField(
        max_length=32, choices=PROVIDER_CHOICES, default="custom_webhook"
    )
    protocol = models.CharField(
        max_length=24, choices=PROTOCOL_CHOICES, default="rest_json"
    )
    sync_direction = models.CharField(
        max_length=20, choices=SYNC_DIRECTION_CHOICES, default="bidirectional"
    )
    environment = models.CharField(
        max_length=20, choices=ENVIRONMENT_CHOICES, default="sandbox"
    )
    endpoint_url = models.CharField(
        max_length=500,
        help_text="Protocol-aware URI (e.g., https://..., opc.tcp://..., mqtts://..., sftp://...).",
    )
    auth_method = models.CharField(
        max_length=20, choices=AUTH_METHOD_CHOICES, default="api_key"
    )
    api_key_prefix = models.CharField(max_length=12, blank=True, editable=False)
    api_key_hash = models.CharField(max_length=128, blank=True, editable=False)

    rate_limit_rpm = models.PositiveIntegerField(default=120)
    timeout_seconds = models.PositiveIntegerField(default=30)
    retry_policy_max = models.PositiveSmallIntegerField(default=3)
    polling_interval_minutes = models.PositiveIntegerField(default=15)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    health_status = models.CharField(
        max_length=20, choices=HEALTH_STATUS_CHOICES, default="unverified"
    )

    vendor_partner = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_integration_connectors",
    )
    default_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_integration_connectors",
    )
    default_currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_integration_connectors",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_asset_connectors",
    )

    last_heartbeat_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_sync_at = models.DateTimeField(null=True, blank=True, editable=False)
    consecutive_failures = models.PositiveIntegerField(default=0, editable=False)
    last_error_message = models.TextField(blank=True, editable=False)

    webhook_verify_tls = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Asset Integration Connector"
        verbose_name_plural = "Asset Integration Connectors"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_aicn_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "connector_category"],
                name="idx_aicn_ten_cat",
            ),
            models.Index(
                fields=["tenant", "status"],
                name="idx_aicn_ten_stat",
            ),
            models.Index(
                fields=["tenant", "health_status"],
                name="idx_aicn_ten_hlth",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    @property
    def status_badge_class(self):
        return self.STATUS_BADGE_MAP.get(self.status, "badge-slate")

    @property
    def health_badge_class(self):
        return self.HEALTH_BADGE_MAP.get(self.health_status, "badge-slate")

    def issue_new_secret(self):
        """Mint a fresh connector credential, keeping only prefix + SHA-256 digest."""
        plaintext = f"aicn_{secrets.token_urlsafe(24)}"
        self.api_key_prefix = plaintext[:8]
        self.api_key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        return plaintext

    def clean(self):
        super().clean()
        errors = {}
        if self.endpoint_url:
            try:
                self.endpoint_url = validate_connector_endpoint_url(self.endpoint_url)
            except ValidationError as exc:
                errors["endpoint_url"] = exc.messages
        if self.rate_limit_rpm is not None and self.rate_limit_rpm < 1:
            errors["rate_limit_rpm"] = "Rate limit must be at least 1 request per minute."
        if self.timeout_seconds is not None and self.timeout_seconds < 1:
            errors["timeout_seconds"] = "Timeout must be at least 1 second."
        if (
            self.polling_interval_minutes is not None
            and self.polling_interval_minutes < 1
        ):
            errors["polling_interval_minutes"] = (
                "Polling interval must be at least 1 minute."
            )
        if errors:
            raise ValidationError(errors)
