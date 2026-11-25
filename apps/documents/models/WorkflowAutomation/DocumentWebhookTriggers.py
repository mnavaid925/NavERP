import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from apps.core.crypto import decrypt, encrypt
from apps.documents.models._base import TenantNumbered
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.services.workflow_automation import (
    validate_dms_webhook_url,
    validate_flat_headers,
)


class DocumentWebhookTrigger(TenantNumbered):
    """DMS-scoped inbound/outbound event trigger and webhook subscription with encrypted HMAC signing."""

    NUMBER_PREFIX = "DWHK"

    DIRECTION_CHOICES = (
        ("outbound_webhook", "Outbound Webhook"),
        ("inbound_webhook", "Inbound Webhook"),
        ("middleware_callback", "Middleware Callback"),
    )

    TRIGGER_EVENT_CHOICES = (
        ("document.uploaded", "document.uploaded"),
        ("document.status_changed", "document.status_changed"),
        ("version.published", "version.published"),
        ("metadata.updated", "metadata.updated"),
        ("ocr.completed", "ocr.completed"),
        ("routing.matched", "routing.matched"),
        ("process.started", "process.started"),
        ("process.completed", "process.completed"),
        ("process.sla_breached", "process.sla_breached"),
        ("approval.decided", "approval.decided"),
        ("inbound.trigger", "inbound.trigger"),
    )

    HTTP_METHOD_CHOICES = (
        ("post", "POST"),
        ("put", "PUT"),
        ("patch", "PATCH"),
    )

    PAYLOAD_FORMAT_CHOICES = (
        ("json", "NavERP Standard JSON"),
        ("cloudevents_json", "CloudEvents 1.0 JSON"),
    )

    LAST_STATUS_CHOICES = (
        ("never_fired", "Never Fired"),
        ("simulated", "Simulated (Local)"),
        ("queued", "Queued"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
    )

    FILTER_DOC_TYPE_CHOICES = [("", "All Document Types")] + list(Document.DOCUMENT_TYPE_CHOICES)

    LAST_STATUS_CSS = {
        "never_fired": "badge-slate",
        "simulated": "badge-info",
        "queued": "badge-amber",
        "delivered": "badge-green",
        "failed": "badge-red",
    }

    DIRECTION_CSS = {
        "outbound_webhook": "badge-info",
        "inbound_webhook": "badge-amber",
        "middleware_callback": "badge-slate",
    }

    IS_ACTIVE_CSS = {
        True: "badge-green",
        False: "badge-slate",
    }

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    direction = models.CharField(
        max_length=30,
        choices=DIRECTION_CHOICES,
        default="outbound_webhook",
        db_index=True,
    )
    trigger_event = models.CharField(
        max_length=40,
        choices=TRIGGER_EVENT_CHOICES,
        default="document.uploaded",
        db_index=True,
    )
    process_definition = models.ForeignKey(
        "documents.DocumentProcessDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_triggers",
    )
    connector_ref = models.ForeignKey(
        "core.ConnectorDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_webhook_triggers",
    )
    target_url = models.URLField(max_length=500, blank=True)
    http_method = models.CharField(
        max_length=15,
        choices=HTTP_METHOD_CHOICES,
        default="post",
    )
    payload_format = models.CharField(
        max_length=30,
        choices=PAYLOAD_FORMAT_CHOICES,
        default="json",
    )
    custom_headers = models.JSONField(default=dict, blank=True)
    payload_template_json = models.JSONField(default=dict, blank=True)
    filter_document_type = models.CharField(
        max_length=40,
        choices=FILTER_DOC_TYPE_CHOICES,
        blank=True,
    )
    retry_policy_max = models.PositiveSmallIntegerField(default=5)
    signing_secret = models.CharField(max_length=512, blank=True, editable=False)
    signing_secret_prefix = models.CharField(max_length=16, blank=True, editable=False)
    is_active = models.BooleanField(default=True, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_dms_webhook_triggers",
    )
    last_status = models.CharField(
        max_length=25,
        choices=LAST_STATUS_CHOICES,
        default="never_fired",
        editable=False,
        db_index=True,
    )
    last_fired_at = models.DateTimeField(null=True, blank=True, editable=False)
    fire_count = models.PositiveIntegerField(default=0, editable=False)
    failure_count = models.PositiveIntegerField(default=0, editable=False)
    delivery_history_json = models.JSONField(default=list, blank=True, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "Document Webhook Trigger"
        verbose_name_plural = "Document Webhook Triggers"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dwhk_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "trigger_event"], name="doc_dwhk_tnt_evt_idx"),
            models.Index(fields=["tenant", "direction"], name="doc_dwhk_tnt_dir_idx"),
            models.Index(fields=["tenant", "is_active"], name="doc_dwhk_tnt_act_idx"),
            models.Index(fields=["tenant", "last_status"], name="doc_dwhk_tnt_sts_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.trigger_event})"

    def clean(self):
        super().clean()
        if self.target_url:
            validate_dms_webhook_url(self.target_url)
        elif self.direction in ("outbound_webhook", "middleware_callback"):
            raise ValidationError(
                {"target_url": "Target URL is required for outbound webhooks and middleware callbacks."}
            )
        self.custom_headers = validate_flat_headers(self.custom_headers)

    def set_signing_secret(self, raw_secret):
        if raw_secret:
            self.signing_secret = encrypt(raw_secret)
            self.signing_secret_prefix = raw_secret[:8]
        else:
            self.signing_secret = ""
            self.signing_secret_prefix = ""

    def get_signing_secret(self):
        if not self.signing_secret:
            return ""
        return decrypt(self.signing_secret)

    def generate_signing_secret(self):
        raw = secrets.token_hex(32)
        self.set_signing_secret(raw)
        return raw

    def compute_signature(self, payload_bytes):
        sec = self.get_signing_secret()
        if not sec:
            return ""
        if isinstance(payload_bytes, str):
            payload_bytes = payload_bytes.encode("utf-8")
        return hmac.new(sec.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    def verify_signature(self, payload_bytes, signature):
        expected = self.compute_signature(payload_bytes)
        if not expected or not signature:
            return False
        return hmac.compare_digest(expected, str(signature))

    def record_simulated_delivery(self, event_name, payload_dict, signature=""):
        now = timezone.now()
        entry = {
            "timestamp": now.isoformat(),
            "event": event_name,
            "status": "simulated",
            "signature_header": f"sha256={signature[:16]}..." if signature else "",
            "target_url": self.target_url,
            "payload": payload_dict,
        }
        with transaction.atomic():
            locked = DocumentWebhookTrigger.objects.select_for_update().get(pk=self.pk)
            history = list(locked.delivery_history_json or [])
            history.append(entry)
            history = history[-25:]
            locked.last_status = "simulated"
            locked.last_fired_at = now
            locked.delivery_history_json = history
            locked.fire_count = (locked.fire_count or 0) + 1
            locked.save(
                update_fields=[
                    "last_status",
                    "last_fired_at",
                    "delivery_history_json",
                    "fire_count",
                    "updated_at",
                ]
            )
            self.last_status = locked.last_status
            self.last_fired_at = locked.last_fired_at
            self.delivery_history_json = locked.delivery_history_json
            self.fire_count = locked.fire_count
        return entry

    @property
    def last_status_badge(self):
        return self.LAST_STATUS_CSS.get(self.last_status, "badge-slate")

    @property
    def direction_badge(self):
        return self.DIRECTION_CSS.get(self.direction, "badge-slate")

    @property
    def active_badge(self):
        return self.IS_ACTIVE_CSS.get(self.is_active, "badge-slate")

    @property
    def masked_secret(self):
        if self.signing_secret_prefix:
            return f"{self.signing_secret_prefix}••••••••••••••••"
        return "Not configured"
