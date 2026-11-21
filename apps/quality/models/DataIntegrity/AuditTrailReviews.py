from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class AuditTrailReview(TenantNumbered):
    NUMBER_PREFIX = "QATR"

    REVIEW_TYPE_CHOICES = [
        ("routine_batch", "Routine Batch / Lot Release Review"),
        ("periodic_system", "Scheduled Periodic System Audit Review"),
        ("event_investigation", "Event-Driven / Deviation Investigation"),
        ("regulatory_inspection", "Pre-Inspection Readiness Audit"),
        ("user_access_drift", "User Access & Privilege Drift Review"),
    ]

    AUDIT_SOURCE_CHOICES = [
        ("database_audit_log", "Core Database Audit Trail (AuditLog)"),
        ("application_event_log", "Application Security & Event Log"),
        ("instrument_raw_log", "Analytical Instrument Raw Data Log"),
        ("cloud_infrastructure", "Cloud Infrastructure & Admin Access Log"),
        ("batch_execution_log", "MES / Batch Execution Log"),
    ]

    SEVERITY_CHOICES = [
        ("none", "No Anomalies Detected (Clean)"),
        ("minor", "Minor Procedural Discrepancy (No GxP Risk)"),
        ("major", "Major Exception (Unapproved Change / Retry Alert)"),
        ("critical", "Critical Integrity Breach (Unauthorized Alteration / Data Loss)"),
    ]

    DISPOSITION_CHOICES = [
        ("pending_review", "Under Examination"),
        ("approved_clean", "Approved — Audit Trail Clean"),
        ("approved_remediated", "Approved — Discrepancies Remediated"),
        ("rejected_escalated", "Rejected — Escalated to Deviation / CAPA"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Review Scheduled"),
        ("in_progress", "Examination In Progress"),
        ("completed", "Review Completed"),
        ("closed", "Closed & Archived"),
    ]

    SEVERITY_CSS = {
        "none": "badge-green",
        "minor": "badge-info",
        "major": "badge-amber",
        "critical": "badge-red",
    }

    DISPOSITION_CSS = {
        "pending_review": "badge-slate",
        "approved_clean": "badge-green",
        "approved_remediated": "badge-amber",
        "rejected_escalated": "badge-red",
    }

    STATUS_CSS = {
        "scheduled": "badge-slate",
        "in_progress": "badge-info",
        "completed": "badge-green",
        "closed": "badge-muted",
    }

    title = models.CharField(max_length=255)
    system = models.ForeignKey(
        "quality.ComputerSystemValidation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_trail_reviews",
    )
    review_type = models.CharField(
        max_length=30, choices=REVIEW_TYPE_CHOICES, default="periodic_system", db_index=True
    )
    audit_source = models.CharField(
        max_length=30, choices=AUDIT_SOURCE_CHOICES, default="database_audit_log"
    )
    period_start = models.DateField(help_text="Start date of audit trail range reviewed")
    period_end = models.DateField(help_text="End date of audit trail range reviewed")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_audit_reviews",
    )
    qa_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_audit_reviews",
    )
    review_date = models.DateField(null=True, blank=True)
    records_sampled_count = models.PositiveIntegerField(default=0)
    anomalies_detected_count = models.PositiveIntegerField(default=0)
    anomaly_severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default="none", db_index=True
    )
    findings_summary = models.TextField(
        blank=True, help_text="Observations, exceptions, or unauthorized access attempts"
    )
    disposition = models.CharField(
        max_length=25, choices=DISPOSITION_CHOICES, default="pending_review", db_index=True
    )
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="scheduled", db_index=True
    )
    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_trail_reviews",
    )
    linked_capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_trail_reviews",
    )
    qa_comments = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-review_date", "-created_at"]
        verbose_name = "Audit Trail Review"
        verbose_name_plural = "Audit Trail Reviews"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qatr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "review_type", "disposition"], name="idx_qatr_ten_typ_disp"),
            models.Index(fields=["tenant", "anomaly_severity", "status"], name="idx_qatr_ten_sev_stat"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_clean(self):
        return self.anomalies_detected_count == 0 and self.anomaly_severity == "none"

    @property
    def requires_escalation(self):
        return self.anomaly_severity in ["major", "critical"]
