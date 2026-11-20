from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ManagementReview(TenantNumbered):
    NUMBER_PREFIX = "QMRV"

    CADENCE_CHOICES = [
        ("annual", "Annual Review"),
        ("semi_annual", "Semi-Annual Review"),
        ("quarterly", "Quarterly Review"),
        ("monthly", "Monthly Quality Review"),
        ("event_driven", "Event-Driven / Special Review"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_preparation", "Input Preparation"),
        ("meeting_active", "Meeting In Progress"),
        ("minutes_drafting", "Minutes & Outputs Drafting"),
        ("pending_approval", "Pending Executive Approval"),
        ("approved", "Executive Approved / Closed"),
        ("cancelled", "Cancelled"),
    ]

    SUITABILITY_CHOICES = [
        ("pending", "Evaluation Pending"),
        ("suitable_effective", "Suitable, Adequate & Fully Effective"),
        ("minor_improvements", "Adequate with Minor Opportunities for Improvement"),
        ("systemic_deficiencies", "Inadequate / Systemic Deficiencies Identified"),
    ]

    CADENCE_CSS = {
        "annual": "badge-info",
        "semi_annual": "badge-info",
        "quarterly": "badge-info",
        "monthly": "badge-slate",
        "event_driven": "badge-amber",
    }

    STATUS_CSS = {
        "scheduled": "badge-info",
        "in_preparation": "badge-amber",
        "meeting_active": "badge-amber",
        "minutes_drafting": "badge-info",
        "pending_approval": "badge-amber",
        "approved": "badge-green",
        "cancelled": "badge-slate",
    }

    SUITABILITY_CSS = {
        "pending": "badge-muted",
        "suitable_effective": "badge-green",
        "minor_improvements": "badge-amber",
        "systemic_deficiencies": "badge-red",
    }

    title = models.CharField(max_length=255)
    cadence = models.CharField(max_length=20, choices=CADENCE_CHOICES, default="quarterly", db_index=True)
    period_start = models.DateField()
    period_end = models.DateField()
    scheduled_date = models.DateField(db_index=True)
    actual_meeting_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)

    executive_sponsor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sponsored_management_reviews",
    )
    lead_facilitator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="facilitated_management_reviews",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_reviews",
    )

    attendees_roster = models.TextField(blank=True, help_text="Documented attendee list, titles, and departments")
    quorum_met = models.BooleanField(default=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="scheduled", db_index=True)
    qms_suitability_conclusion = models.CharField(
        max_length=32, choices=SUITABILITY_CHOICES, default="pending", db_index=True
    )

    executive_summary = models.TextField(blank=True)
    minutes_discussion = models.TextField(blank=True)
    resource_decisions = models.TextField(blank=True)

    electronic_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_reviews",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_management_reviews",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-created_at"]
        verbose_name = "Management Review"
        verbose_name_plural = "Management Reviews"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="qmrv_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qmrv_ten_status"),
            models.Index(fields=["tenant", "cadence"], name="idx_qmrv_ten_cad"),
            models.Index(fields=["tenant", "scheduled_date"], name="idx_qmrv_ten_schdate"),
            models.Index(fields=["tenant", "qms_suitability_conclusion"], name="idx_qmrv_ten_suit"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qmrv_ten_created"),
            models.Index(fields=["tenant", "-scheduled_date", "-created_at"], name="idx_qmrv_ten_date_crd"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_cadence_display()})"

    @property
    def total_inputs_count(self):
        return self.inputs.count()

    @property
    def total_actions_count(self):
        return self.actions.count()

    @property
    def open_actions_count(self):
        return self.actions.filter(status__in=["open", "in_progress", "pending_verification"]).count()

    @property
    def is_overdue(self):
        return self.status == "scheduled" and self.scheduled_date < timezone.now().date()

    @property
    def cadence_badge_class(self):
        return self.CADENCE_CSS.get(self.cadence, "badge-info")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def suitability_badge_class(self):
        return self.SUITABILITY_CSS.get(self.qms_suitability_conclusion, "badge-muted")
