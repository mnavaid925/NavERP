from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentSecurityAlert(TenantNumbered):
    """User Behavior Analytics (UBA) anomaly detection record and triage incident."""

    NUMBER_PREFIX = "DANM"

    ALERT_TYPE_CHOICES = (
        ("mass_download", "Mass Document Download / Exfiltration"),
        ("off_hours_access", "Unusual Off-Hours Bulk Access"),
        ("rapid_deletion", "Rapid Document Deletion / Purge"),
        ("excessive_denials", "Excessive Permission Denials (Probing)"),
        ("unusual_location", "Anomalous Geolocation / IP Subnet"),
        ("dormant_file_access", "Sudden Access to Dormant Sensitive File"),
        ("permission_escalation", "Suspicious Permission Escalation"),
    )

    SEVERITY_CHOICES = (
        ("low", "Low Severity (Risk 1-39)"),
        ("medium", "Medium Severity (Risk 40-69)"),
        ("high", "High Severity (Risk 70-89)"),
        ("critical", "Critical Threat (Risk 90-100)"),
    )

    STATUS_CHOICES = (
        ("new", "New / Unassigned"),
        ("investigating", "Under Investigation"),
        ("confirmed_threat", "Confirmed Threat"),
        ("false_positive", "False Positive"),
        ("resolved", "Resolved & Mitigated"),
        ("dismissed", "Dismissed"),
    )

    ACTION_TAKEN_CHOICES = (
        ("logged_only", "Logged / Monitoring Only"),
        ("user_warned", "User Warned via Notification"),
        ("downloads_blocked", "Document Downloads Blocked"),
        ("sharing_revoked", "External Shares Revoked"),
        ("session_terminated", "User Session Terminated"),
    )

    ALERT_TYPE_CSS = {
        "mass_download": "badge-red",
        "off_hours_access": "badge-amber",
        "rapid_deletion": "badge-red",
        "excessive_denials": "badge-amber",
        "unusual_location": "badge-info",
        "dormant_file_access": "badge-slate",
        "permission_escalation": "badge-red",
    }

    SEVERITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    STATUS_CSS = {
        "new": "badge-red",
        "investigating": "badge-amber",
        "confirmed_threat": "badge-red",
        "false_positive": "badge-slate",
        "resolved": "badge-green",
        "dismissed": "badge-muted",
    }

    alert_type = models.CharField(
        max_length=40,
        choices=ALERT_TYPE_CHOICES,
        db_index=True,
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="medium",
        db_index=True,
    )
    risk_score = models.PositiveIntegerField(
        default=50,
        db_index=True,
        help_text="Calculated risk score between 1 and 100",
    )
    title = models.CharField(
        max_length=200,
        help_text="Concise summary headline of anomalous behavior detected",
    )
    description = models.TextField(
        help_text="Detailed heuristic trigger evidence and contextual baseline",
    )
    detected_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_security_alerts",
        db_index=True,
        help_text="Suspect user account exhibiting anomalous behavior",
    )
    target_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_alerts",
        help_text="Target document if alert was triggered on a specific file",
    )
    source_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Source IP originating the anomalous activity",
    )
    event_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of correlated anomalous events grouped into this incident",
    )
    evidence_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON payload of raw audit IDs, thresholds, and statistical baselines",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="new",
        db_index=True,
    )
    action_taken = models.CharField(
        max_length=40,
        choices=ACTION_TAKEN_CHOICES,
        default="logged_only",
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_assigned_security_alerts",
        help_text="Security officer or admin triaging this incident",
    )
    triage_notes = models.TextField(
        blank=True,
        help_text="Forensic notes, interview findings, or justification",
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_resolved_security_alerts",
    )

    class Meta:
        ordering = ["-detected_at"]
        verbose_name = "Document Security Alert"
        verbose_name_plural = "Document Security Alerts"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_danm_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="doc_danm_tnt_sts_idx"),
            models.Index(fields=["tenant", "severity"], name="doc_danm_tnt_sev_idx"),
            models.Index(fields=["tenant", "alert_type"], name="doc_danm_tnt_typ_idx"),
            models.Index(fields=["tenant", "risk_score"], name="doc_danm_tnt_rsk_idx"),
            models.Index(fields=["tenant", "action_taken"], name="doc_danm_tnt_act_idx"),
            models.Index(fields=["tenant", "status", "-detected_at"], name="doc_danm_tnt_sts_dt_idx"),
            models.Index(fields=["tenant", "severity", "-detected_at"], name="doc_danm_tnt_sev_dt_idx"),
            models.Index(fields=["tenant", "target_user", "alert_type", "detected_at"], name="doc_danm_usr_typ_dt_idx"),
        ]

    def __str__(self):
        return f"[{self.number}] ({self.get_severity_display()}) {self.title}"

    def get_severity_badge(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def get_alert_type_badge(self):
        return self.ALERT_TYPE_CSS.get(self.alert_type, "badge-slate")
