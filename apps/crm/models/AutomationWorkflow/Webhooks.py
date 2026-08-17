"""CRM 1.10 Automation & Workflow Engine — Webhooks models (split from apps/crm/models.py)."""
from apps.core.crypto import decrypt as decrypt_secret, encrypt as encrypt_secret
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.AutomationWorkflow.WorkflowRules import WorkflowRule


# ---- 1.10 Webhooks — outbound event push (config + signed delivery log) ------------------
class Webhook(TenantNumbered):
    """An outbound webhook endpoint (1.10). A WorkflowRule's ``webhook`` action (or a manual test)
    builds a JSON payload, HMAC-signs it with ``secret``, and records a :class:`WebhookDelivery`.
    The real outbound HTTP POST is **deferred** — see the SSRF ``# WARNING`` on the delivery helper
    in views.py. Reuses ``WorkflowRule``'s entity/event vocab so a rule fires the matching webhooks."""

    NUMBER_PREFIX = "WH"

    name = models.CharField(max_length=255)
    target_url = models.URLField(max_length=500)
    trigger_entity = models.CharField(max_length=20, choices=WorkflowRule.ENTITY_CHOICES, default="opportunity")
    trigger_event = models.CharField(max_length=20, choices=WorkflowRule.EVENT_CHOICES, default="created")
    # WARNING: a signing secret — write-only AND encrypted at rest. Excluded from the bound edit
    # render (PasswordInput, render_value=False) so it's never shipped back to the browser; that
    # alone only stopped disclosure through the edit page, not through a DB dump, a backup or a
    # logged row, so the column now holds Fernet ciphertext (apps/core/crypto.py) and the plaintext
    # exists only in memory at signing time. Read it with get_secret(), never `.secret` directly.
    # It CANNOT be hashed like tenants.EncryptionKey / accounting.IntegrationConfig: HMAC needs the
    # real key bytes back, and a SHA-256 digest is one-way. Widened from 128 to hold the ciphertext.
    secret = models.CharField(max_length=512, blank=True, help_text="HMAC signing key — write-only (never shown after saving), encrypted at rest.")
    is_active = models.BooleanField(default=True)
    headers = models.JSONField(default=dict, blank=True)  # optional custom request headers
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_wh_tnt_active_idx"),
            models.Index(fields=["tenant", "trigger_entity"], name="crm_wh_tnt_entity_idx"),
        ]

    def save(self, *args, **kwargs):
        """Encrypt the signing key at the one write choke-point.

        Doing it here rather than in ``WebhookForm`` covers all three writers with one
        rule: a new secret typed into the form, the form's blank-on-edit path (which
        re-assigns the already-encrypted stored value — left alone, because
        :func:`~apps.core.crypto.encrypt` is a no-op on a marked value), and the data
        migration. Nothing can reach the column without passing through here.
        """
        self.secret = encrypt_secret(self.secret)
        return super().save(*args, **kwargs)

    def get_secret(self):
        """The plaintext signing key, for HMAC at send time. Never render or log this."""
        return decrypt_secret(self.secret)

    def __str__(self):
        return f"{self.number} · {self.name}"

    @property
    def secret_masked(self):
        # Decrypt first — masking the ciphertext would show four characters of base64,
        # which identifies nothing and changes on every re-encryption.
        s = self.get_secret()
        return f"••••{s[-4:]}" if len(s) >= 4 else ("(set)" if s else "(none)")


class WebhookDelivery(models.Model):
    """Immutable append-only delivery record for a :class:`Webhook` (1.10). Captures the signed payload
    + outcome of one fire. Real outbound HTTP is deferred (status starts ``pending``). Accessed
    list+detail only — never edited (an audit-grade log, like :class:`WorkflowLog`)."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("simulated", "Simulated"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    webhook = models.ForeignKey("crm.Webhook", on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=60)
    payload = models.TextField(blank=True)  # the JSON body that would be POSTed
    signature = models.CharField(max_length=128, blank=True)  # HMAC-SHA256 hex of the payload
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error_msg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "webhook"], name="crm_whd_tnt_webhook_idx"),
            models.Index(fields=["tenant", "status"], name="crm_whd_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.webhook_id} · {self.event} · {self.status}"
