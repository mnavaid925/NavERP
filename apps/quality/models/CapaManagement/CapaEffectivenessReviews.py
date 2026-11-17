from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class CapaEffectivenessReview(TenantNumbered):
    NUMBER_PREFIX = "QEFF"

    METHOD_CHOICES = (
        ("statistical_sample", "Statistical Sampling & Quality Inspection"),
        ("trend_analysis", "Trend Analysis (NCR / Complaint Volume)"),
        ("audit_recheck", "Audit Re-check / Follow-up Audit"),
        ("process_capability", "Process Capability Study (Cpk / Ppk)"),
        ("zero_recurrence_window", "Zero Recurrence Window (30/60/90 Days)"),
    )

    OUTCOME_CHOICES = (
        ("pending", "Pending Evaluation"),
        ("effective", "Effective — Actions Successful"),
        ("ineffective", "Ineffective — Recurrence / Defect Persists"),
        ("inconclusive", "Inconclusive — Extended Window Required"),
    )

    STATUS_CHOICES = (
        ("scheduled", "Scheduled"),
        ("in_progress", "Evaluation In Progress"),
        ("completed", "Review Completed"),
        ("cancelled", "Cancelled"),
    )

    METHOD_CSS = {
        "statistical_sample": "badge-info",
        "trend_analysis": "badge-purple",
        "audit_recheck": "badge-amber",
        "process_capability": "badge-info",
        "zero_recurrence_window": "badge-slate",
    }

    OUTCOME_CSS = {
        "pending": "badge-slate",
        "effective": "badge-green",
        "ineffective": "badge-red",
        "inconclusive": "badge-amber",
    }

    STATUS_CSS = {
        "scheduled": "badge-slate",
        "in_progress": "badge-info",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }

    capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.CASCADE,
        related_name="effectiveness_reviews"
    )
    review_criteria = models.TextField(help_text="Pre-established acceptance criteria (e.g., zero defect recurrence in 90 days, Cpk >= 1.33)")
    verification_method = models.CharField(max_length=32, choices=METHOD_CHOICES, default="zero_recurrence_window")
    planned_review_date = models.DateField(help_text="Scheduled post-implementation review date (30/60/90/180 days)")
    actual_review_date = models.DateField(null=True, blank=True)
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evaluated_capa_reviews"
    )
    metrics_evaluated = models.TextField(blank=True, help_text="Observed defect counts, statistical sample results, or process capability figures")
    recurrence_observed = models.BooleanField(default=False, help_text="Whether the failure mode or root cause recurred during evaluation window")
    recurrence_details = models.TextField(blank=True, help_text="Details of any recurrences observed, including event numbers and root causes")
    outcome = models.CharField(max_length=24, choices=OUTCOME_CHOICES, default="pending", db_index=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="scheduled", db_index=True)
    review_notes = models.TextField(blank=True, help_text="Executive summary of effectiveness review finding and recommendations")
    formal_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="effective_review_signatures",
        editable=False,
        help_text="21 CFR Part 11 e-signature manifest"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "CAPA Effectiveness Review"
        verbose_name_plural = "CAPA Effectiveness Reviews"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qeff_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "capa"], name="idx_qeff_ten_capa"),
            models.Index(fields=["tenant", "outcome"], name="idx_qeff_ten_outcome"),
            models.Index(fields=["tenant", "planned_review_date"], name="idx_qeff_ten_plan_dt"),
            models.Index(fields=["tenant", "status"], name="idx_qeff_ten_status"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qeff_ten_created"),
        ]

    def __str__(self):
        return f"{self.number}: {self.get_outcome_display()} ({self.capa.number})"

    @property
    def method_badge(self):
        return self.METHOD_CSS.get(self.verification_method, "badge-slate")

    @property
    def outcome_badge(self):
        return self.OUTCOME_CSS.get(self.outcome, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def is_review_overdue(self):
        return bool(
            self.planned_review_date
            and self.planned_review_date < timezone.now().date()
            and self.status == "scheduled"
        )

    @property
    def is_effective(self):
        return self.outcome == "effective"
