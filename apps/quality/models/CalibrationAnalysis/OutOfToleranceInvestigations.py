from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class OutOfToleranceInvestigation(TenantNumbered):
    NUMBER_PREFIX = "QOOT"

    RISK_LEVEL_CHOICES = (
        ("critical", "Critical (Safety / Regulatory / Customer Risk)"),
        ("major", "Major (Fit / Form / Function CTQ Impact)"),
        ("minor", "Minor (Negligible Measurement Uncertainty)"),
        ("no_impact", "No Impact Confirmed"),
    )

    DISPOSITION_CHOICES = (
        ("pending_review", "Pending MRB / Quality Review"),
        ("use_as_is", "Use As-Is (Risk Accepted)"),
        ("re_inspect_inventory", "100% Re-Inspect Suspect Lots"),
        ("customer_notification", "Customer Notification & Concession"),
        ("quarantine_scrap", "Quarantine & Scrap Finished Goods"),
        ("product_recall", "Formal Field Safety / Recall Action"),
    )

    STATUS_CHOICES = (
        ("open", "Open / Newly Quarantined"),
        ("investigating", "Reverse-Tracing Investigation"),
        ("mrb_review", "Material Review Board (MRB)"),
        ("actions_pending", "Containment Actions Pending"),
        ("closed", "Closed / Verified Complete"),
    )

    RISK_LEVEL_CSS = {
        "critical": "badge-red",
        "major": "badge-amber",
        "minor": "badge-info",
        "no_impact": "badge-green",
    }

    STATUS_CSS = {
        "open": "badge-red",
        "investigating": "badge-amber",
        "mrb_review": "badge-info",
        "actions_pending": "badge-amber",
        "closed": "badge-green",
    }

    DISPOSITION_CSS = {
        "pending_review": "badge-slate",
        "use_as_is": "badge-info",
        "re_inspect_inventory": "badge-amber",
        "customer_notification": "badge-red",
        "quarantine_scrap": "badge-red",
        "product_recall": "badge-red",
    }

    calibration_record = models.ForeignKey(
        "quality.CalibrationRecord", on_delete=models.CASCADE, related_name="oot_investigations"
    )
    gage = models.ForeignKey(
        "quality.CalibrationGage", on_delete=models.CASCADE, related_name="oot_investigations"
    )
    discovery_date = models.DateField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="open", db_index=True)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default="major", db_index=True)

    title = models.CharField(max_length=180, help_text="Brief summary of out-of-tolerance condition")
    as_found_error_description = models.TextField(
        help_text="Detailed metrology finding: deviation magnitude, affected parameters"
    )

    suspect_window_start = models.DateField(
        help_text="Date of last valid calibration or last confirmed in-spec verification"
    )
    suspect_window_end = models.DateField(
        default=timezone.now, help_text="Date gage was flagged out of tolerance and quarantined"
    )

    suspect_work_center = models.ForeignKey(
        "scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="oot_investigations"
    )
    suspect_production_orders = models.TextField(
        blank=True, help_text="Comma-separated or listed Work Orders/Batches processed during window"
    )
    suspect_lots_count = models.PositiveIntegerField(
        default=0, help_text="Count of identified production batches in suspect window"
    )
    products_affected = models.CharField(
        max_length=200, blank=True, help_text="Product numbers/descriptions measured with this gage"
    )

    consumer_risk_rating = models.PositiveSmallIntegerField(
        default=3, help_text="Consumer Risk rating (1-5, probability of accepting bad parts)"
    )
    producer_risk_rating = models.PositiveSmallIntegerField(
        default=3, help_text="Producer Risk rating (1-5, probability of rejecting good parts)"
    )

    containment_actions_taken = models.TextField(
        blank=True, help_text="Physical quarantine of gage, quarantine of suspect warehouse stock"
    )
    product_disposition = models.CharField(
        max_length=24, choices=DISPOSITION_CHOICES, default="pending_review", db_index=True
    )
    customer_notification_required = models.BooleanField(default=False)
    product_recall_required = models.BooleanField(default=False)

    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="oot_investigations"
    )
    linked_capa = models.ForeignKey(
        "quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="oot_investigations"
    )

    investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="investigated_oots"
    )
    quality_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_oots"
    )
    closure_date = models.DateField(null=True, blank=True)
    conclusion_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-discovery_date", "-created_at"]
        verbose_name = "Out-of-Tolerance (OOT) Investigation"
        verbose_name_plural = "Out-of-Tolerance (OOT) Investigations"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qoot_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "gage"], name="idx_qoot_ten_gage"),
            models.Index(fields=["tenant", "status"], name="idx_qoot_ten_status"),
            models.Index(fields=["tenant", "risk_level"], name="idx_qoot_ten_risk"),
            models.Index(fields=["tenant", "discovery_date"], name="idx_qoot_ten_disc"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qoot_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_risk_level_display()})"

    @property
    def risk_css(self):
        return self.RISK_LEVEL_CSS.get(self.risk_level, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def disposition_css(self):
        return self.DISPOSITION_CSS.get(self.product_disposition, "badge-slate")
