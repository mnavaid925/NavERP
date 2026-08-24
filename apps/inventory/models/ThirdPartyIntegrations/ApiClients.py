"""Inventory 5.19 Third-Party Integrations & API — ApiClient model (NavERP bullet 4, inbound half).

Keys WE issue to third parties calling OUR REST/GraphQL surface (the MuleSoft/Jitterbit
client-management half of API Management). crm/scm webhooks are OUTBOUND push; nobody else owns
inbound access control. The token plaintext is NEVER persisted — only a prefix + SHA-256 hash
(L20/L25); it is revealed exactly once on issue/rotate (accounting.IntegrationConfig mechanics
copied VERBATIM, renamed for tokens — peer apps don't import each other's internals).
"""
import hashlib
import secrets

from apps.inventory.models._base import *  # noqa: F401,F403
from apps.inventory.models.ThirdPartyIntegrations._choices import (
    API_PROTOCOL_CHOICES,
    API_STATUS_CHOICES,
)


class ApiClient(TenantNumbered):
    """A third-party caller registered against our own API surface [API-]."""

    NUMBER_PREFIX = "API"

    #: EMPTY ON PURPOSE, and its emptiness is a decision rather than an omission (WebhookSubscription
    #: precedent): this entity has **no foreign key beyond the inherited ``tenant``** — it points at
    #: no partner, no party, no item and no location. There is consequently no cross-tenant FK to
    #: reject, no ``clean()`` override on this class, and no ``_reject_foreign`` call in its form.
    #: The constant stays declared so the absence reads as "checked, nothing to check" rather than
    #: "forgotten".
    TENANT_SCOPED_FKS = ()

    # --- identity ---------------------------------------------------------------------------------
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    scopes = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            'Comma-separated scope list, e.g. "stock:read,moves:read" — RECORDED intent only; '
            "no enforcement middleware exists in this pass."
        ),
    )
    protocol = models.CharField(max_length=8, choices=API_PROTOCOL_CHOICES, default="rest")

    # --- credential -------------------------------------------------------------------------------
    api_token_prefix = models.CharField(max_length=12, blank=True, editable=False)
    api_token_hash = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
        help_text="Prefix + SHA-256 marker; plaintext NEVER persisted, shown exactly once on issue/rotate.",
    )

    # --- lifecycle --------------------------------------------------------------------------------
    status = models.CharField(
        max_length=8,
        choices=API_STATUS_CHOICES,
        default="active",
        help_text="Moves ONLY via the revoke POST verb — never a form field.",
    )
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    allowed_ips = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "Comma-separated allow-list, e.g. 203.0.113.7,198.51.100.0/24 — RECORDED intent, "
            "NOT enforced by any gateway in this pass."
        ),
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Home for the future gateway pass to stamp; NOTHING in this build writes it.",
    )
    rate_limit_note = models.CharField(
        max_length=120,
        blank=True,
        help_text='Our budget promise to the consumer, e.g. "60 req/min sustained" — prose, never a throttle.',
    )

    class Meta:
        ordering = ["name", "id"]
        unique_together = (("tenant", "number"), ("tenant", "name"))
        indexes = [
            Index(fields=["tenant", "status"], name="inv_apc_tnt_status_idx"),
        ]

    @staticmethod
    def hash_secret(secret):
        """SHA-256 hex digest of the token plaintext — the only thing we ever persist."""
        return hashlib.sha256(secret.encode()).hexdigest()

    def set_api_token(self, secret):
        """Store only prefix + hash — never the plaintext (L20/L25)."""
        self.api_token_prefix = secret[:6]
        self.api_token_hash = self.hash_secret(secret)

    @staticmethod
    def generate_api_token():
        return secrets.token_urlsafe(24)

    @property
    def masked(self):
        if not self.api_token_hash:
            return ""
        return f"{self.api_token_prefix}{'•' * 8}"

    def revoke(self):
        """Revoke this client. No-op-safe: only an ``active`` client transitions, so double-revoking
        neither errors nor re-stamps ``revoked_at``."""
        if self.status == "active":
            self.status = "revoked"
            self.revoked_at = timezone.now()
            self.save(update_fields=["status", "revoked_at", "updated_at"])

    def __str__(self):
        return f"{self.number} — {self.name}"
