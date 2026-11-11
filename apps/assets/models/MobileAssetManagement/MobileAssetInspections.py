from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class MobileAssetInspection(TenantNumbered):
    """
    Mobile digital inspection checklists, safety walkarounds, photographic proof,
    condition ratings, and voice-to-text notes from field personnel [MINS-].
    """

    NUMBER_PREFIX = "MINS"

    INSPECTION_TYPE_CHOICES = [
        ("safety_audit", "Safety & Statutory Walkaround"),
        ("pre_trip", "Pre-Trip / Pre-Shift Checklist"),
        ("condition_assessment", "Condition & Wear Assessment"),
        ("routine_pm", "Routine PM Inspection"),
        ("breakdown_triage", "Emergency Breakdown Triage"),
    ]

    OVERALL_RESULT_CHOICES = [
        ("pass", "Pass (Satisfactory)"),
        ("conditional_pass", "Conditional Pass (Action Item Open)"),
        ("fail", "Fail (Needs Repair)"),
        ("critical_hazard", "Critical Hazard / Out of Service"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Incomplete)"),
        ("submitted", "Submitted from Field"),
        ("under_review", "Under Supervisory Review"),
        ("approved", "Approved & Closed"),
        ("rejected", "Rejected (Re-inspection Required)"),
    ]

    CONDITION_RATING_CHOICES = [
        (5, "5 - Excellent (Like New)"),
        (4, "4 - Good (Normal Operational)"),
        (3, "3 - Fair (Minor Wear / Servicing Due)"),
        (2, "2 - Poor (Degraded / Urgent Repair)"),
        (1, "1 - Critical / Scrap Hazard"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-info",
        "under_review": "badge-amber",
        "approved": "badge-green",
        "rejected": "badge-red",
    }

    OVERALL_RESULT_CSS = {
        "pass": "badge-green",
        "conditional_pass": "badge-amber",
        "fail": "badge-red",
        "critical_hazard": "badge-red",
    }

    INSPECTION_TYPE_CSS = {
        "safety_audit": "badge-amber",
        "pre_trip": "badge-info",
        "condition_assessment": "badge-slate",
        "routine_pm": "badge-green",
        "breakdown_triage": "badge-red",
    }

    title = models.CharField(max_length=200, help_text="Short descriptive title of the mobile inspection")
    inspection_type = models.CharField(max_length=32, choices=INSPECTION_TYPE_CHOICES, default="routine_pm")
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="mobile_inspections",
        help_text="Subject operational asset inspected",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mobile_inspections",
        help_text="Financial asset record (if linked)",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mobile_inspections",
        help_text="Field technician / inspector who completed the audit",
    )
    inspection_date = models.DateTimeField(default=timezone.now, help_text="Timestamp when inspection was completed")
    scheduled_date = models.DateField(null=True, blank=True, help_text="Target scheduled date for routine inspection")
    overall_result = models.CharField(max_length=24, choices=OVERALL_RESULT_CHOICES, default="pass")
    condition_rating = models.PositiveSmallIntegerField(default=5, choices=CONDITION_RATING_CHOICES)
    meter_reading = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Odometer or runtime hours captured on-site",
    )
    checklist_summary = models.TextField(
        blank=True,
        help_text="Checklist questions evaluated and itemized pass/fail results",
    )
    photo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL or document path to primary inspection photograph",
    )
    photo_caption = models.CharField(max_length=200, blank=True, help_text="Photo evidence description / defect caption")
    voice_notes_transcription = models.TextField(
        blank=True,
        help_text="Speech-to-text transcription of inspector voice memos",
    )
    corrective_action_required = models.BooleanField(
        default=False,
        help_text="Whether follow-up maintenance or work order is needed",
    )
    findings_summary = models.TextField(
        blank=True,
        help_text="Executive summary of defects, leaks, wear, or abnormal vibrations",
    )
    gps_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_accuracy_m = models.FloatField(null=True, blank=True, help_text="GPS fix accuracy in meters")
    client_sync_id = models.CharField(max_length=64, blank=True, help_text="Client-side UUID for offline reconciliation")
    is_offline_captured = models.BooleanField(
        default=False,
        help_text="Captured without internet and synced on reconnect",
    )
    synced_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of server synchronization")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")

    class Meta:
        ordering = ["-inspection_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_mins_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_mins_ten_stat"),
            models.Index(fields=["tenant", "overall_result"], name="idx_mins_ten_res"),
            models.Index(fields=["tenant", "inspection_type"], name="idx_mins_ten_type"),
            models.Index(fields=["tenant", "inspection_date"], name="idx_mins_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_overall_result_display()})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def result_badge_class(self):
        return self.OVERALL_RESULT_CSS.get(self.overall_result, "badge-slate")

    @property
    def type_badge_class(self):
        return self.INSPECTION_TYPE_CSS.get(self.inspection_type, "badge-slate")
