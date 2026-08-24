"""Inventory 5.19 Third-Party Integrations & API — IntegrationChannel [INT-].

The connection register (Celigo/Patchworks compression; serves NavERP.md bullets 1-3:
E-commerce / ERP / Accounting Software integration). A row RECORDS that a connection to an
external platform exists — its identity, auth intent, environment and human-maintained
health marker — and owns the prefix+SHA-256 credential mechanics; it transports nothing.

**Boundaries (research §4):** NO outbound HTTP exists in this build (``base_url`` carries a
``# WARNING SSRF`` comment for any future transport pass); QuickBooks/Xero/Sage rows are
EXTERNAL connector registrations only (no accounting model is touched — inventory 5.18 owns
internal JE automation); no OAuth token storage (``auth_method`` records intent);
``scm.Item`` / ``scm.Location`` are pointed at, never re-declared (L36).
"""
import hashlib
import secrets

from apps.inventory.models._base import *  # noqa: F401,F403
from apps.inventory.models.ThirdPartyIntegrations._choices import (
    CHANNEL_AUTH_METHOD_CHOICES,
    CHANNEL_KIND_CHOICES,
    CHANNEL_PLATFORM_CHOICES,
    CHANNEL_STATUS_CHOICES,
    CHANNEL_SYNC_DIRECTION_CHOICES,
    CHANNEL_TRIGGER_CHOICES,
    ENVIRONMENT_CHOICES,
)


class IntegrationChannel(TenantNumbered):
    """An external-system connection registration [INT-] — bullets 1-3 of 5.19."""

    NUMBER_PREFIX = "INT"

    name = models.CharField(max_length=120)
    kind = models.CharField(
        max_length=12,
        choices=CHANNEL_KIND_CHOICES,
        default="custom",
        help_text="Which family of external system this connection points at",
    )
    platform = models.CharField(
        max_length=20,
        choices=CHANNEL_PLATFORM_CHOICES,
        blank=True,
        default="custom",
        help_text="Named commercial platform the connector targets",
    )
    direction = models.CharField(
        max_length=14,
        choices=CHANNEL_SYNC_DIRECTION_CHOICES,
        default="bidirectional",
        help_text="Which way stock data flows across this connection (intent)",
    )
    auth_method = models.CharField(
        max_length=10,
        choices=CHANNEL_AUTH_METHOD_CHOICES,
        default="api_key",
        help_text="Auth intent only — OAuth2 records intent and stores nothing",
    )
    # WARNING SSRF: tenant-editable URL the server WOULD dial; no transport exists in this build.
    # Any future pass needs allow-list + private-IP block + DNS-rebinding re-resolve FIRST.
    # Deliberately a CharField, not URLField (non-HTTP schemes stay legal — scm
    # IntegrationEndpoint.endpoint_url rationale).
    base_url = models.CharField(max_length=500, blank=True)
    external_account_ref = models.CharField(
        max_length=120,
        blank=True,
        help_text="Shop domain / seller id / realm / company id at the platform",
    )
    api_key_prefix = models.CharField(max_length=12, blank=True, editable=False)
    api_key_hash = models.CharField(max_length=64, blank=True, editable=False)
    environment = models.CharField(max_length=10, choices=ENVIRONMENT_CHOICES, default="sandbox")
    status = models.CharField(
        max_length=14,
        choices=CHANNEL_STATUS_CHOICES,
        default="disconnected",
        help_text=(
            "ON the form deliberately — a human-maintained marker; no transport observes anything"
            " (scm endpoint.status ruling)"
        ),
    )
    trigger_mode = models.CharField(
        max_length=10,
        choices=CHANNEL_TRIGGER_CHOICES,
        default="manual",
        help_text="Sync-firing intent only — no scheduler exists in this build",
    )
    schedule_note = models.CharField(max_length=200, blank=True)
    rate_limit_note = models.CharField(
        max_length=120,
        blank=True,
        help_text='Prose humans read, never enforced — e.g. "QBO: 429 w/ Retry-After, ~10 concurrent"',
    )
    default_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="WHICH stocking location backs this channel's availability",
    )
    last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Home for the future transport pass — NOTHING in this build writes it",
    )
    last_run_status = models.CharField(
        max_length=14,
        blank=True,
        editable=False,
        help_text="Written ONLY by the sync verb — honestly reflects the latest recorded run",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        unique_together = (("tenant", "number"), ("tenant", "name"))
        indexes = [
            models.Index(fields=["tenant", "kind"], name="inv_int_tnt_kind_idx"),
            models.Index(fields=["tenant", "status"], name="inv_int_tnt_status_idx"),
            models.Index(fields=["tenant", "is_active"], name="inv_int_tnt_active_idx"),
        ]

    #: Read by BOTH the form's ``_reject_foreign`` and this model's own ``clean()`` loop
    #: (scm idiom: one table, two readers). A new tenant-scoped FK inherits both checks by
    #: being added here.
    TENANT_SCOPED_FKS = ("default_location",)

    def __str__(self):
        return f"{self.number} — {self.name}"

    def clean(self):
        super().clean()
        if self.tenant_id is None:
            return
        errors = {}
        for name in self.TENANT_SCOPED_FKS:
            if getattr(self, f"{name}_id", None) is None:
                continue
            related = getattr(self, name, None)
            if related is not None and getattr(related, "tenant_id", None) != self.tenant_id:
                errors[name] = "That record belongs to another workspace."
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ credentials
    @staticmethod
    def hash_secret(secret):
        return hashlib.sha256(secret.encode()).hexdigest()

    def set_api_key(self, secret):
        """Store only prefix + hash — never the plaintext."""
        self.api_key_prefix = secret[:6]
        self.api_key_hash = self.hash_secret(secret)

    @staticmethod
    def generate_api_key():
        return secrets.token_urlsafe(24)

    @property
    def masked(self):
        """Templates render THIS — never the raw columns."""
        if not self.api_key_hash:
            return ""
        return f"{self.api_key_prefix}{'•' * 8}"
