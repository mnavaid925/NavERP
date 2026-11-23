from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DlpIncident(TenantNumbered):
    """
    Telemetry log recording sensitive data policy violations, redacted evidence snippets,
    automated security enforcement actions, and officer triage workflow.
    """

    NUMBER_PREFIX = "DINC"

    SEVERITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    ACTION_TAKEN_CHOICES = (
        ("logged", "Logged Only"),
        ("warned", "Author Warned"),
        ("blocked", "Save Blocked"),
        ("quarantined", "Document Quarantined"),
        ("watermarked", "Watermark Enforced"),
    )

    RESOLUTION_CHOICES = (
        ("open", "Open / Pending Review"),
        ("under_investigation", "Under Investigation"),
        ("resolved_justified", "Resolved (Legitimate Business Need)"),
        ("false_positive", "False Positive"),
        ("dismissed", "Dismissed"),
    )

    SEVERITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    ACTION_CSS = {
        "logged": "badge-slate",
        "warned": "badge-info",
        "blocked": "badge-red",
        "quarantined": "badge-amber",
        "watermarked": "badge-slate",
    }

    RESOLUTION_CSS = {
        "open": "badge-red",
        "under_investigation": "badge-amber",
        "resolved_justified": "badge-green",
        "false_positive": "badge-slate",
        "dismissed": "badge-muted",
    }

    policy = models.ForeignKey(
        "documents.DlpPolicy",
        on_delete=models.CASCADE,
        related_name="incidents",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="dlp_incidents",
    )
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dlp_incidents",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="triggered_dlp_incidents",
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="high",
    )
    action_taken = models.CharField(
        max_length=20,
        choices=ACTION_TAKEN_CHOICES,
        default="logged",
    )
    matches_detected_count = models.PositiveIntegerField(default=1)
    snippet_redacted = models.TextField(blank=True)

    # Resolution Triage
    resolution_status = models.CharField(
        max_length=25,
        choices=RESOLUTION_CHOICES,
        default="open",
        db_index=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_dlp_incidents",
    )
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DLP Incident"
        verbose_name_plural = "DLP Incidents"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dinc_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "created_at"], name="doc_dinc_tnt_crt_idx"),
            models.Index(fields=["tenant", "policy", "resolution_status"], name="doc_dinc_tnt_pol_res_idx"),
            models.Index(fields=["tenant", "document", "created_at"], name="doc_dinc_tnt_doc_crt_idx"),
            models.Index(fields=["tenant", "severity", "resolution_status"], name="doc_dinc_tnt_sev_res_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.policy.name} ({self.get_severity_display()})"

    @property
    def severity_badge(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def action_badge(self):
        return self.ACTION_CSS.get(self.action_taken, "badge-slate")

    @property
    def resolution_badge(self):
        return self.RESOLUTION_CSS.get(self.resolution_status, "badge-slate")
