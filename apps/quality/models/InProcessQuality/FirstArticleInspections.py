from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class FirstArticleInspection(TenantNumbered):
    NUMBER_PREFIX = "QFAI"

    FAI_TYPE_CHOICES = [
        ("full_fai", "Full First Article Inspection (AS9102)"),
        ("delta_partial_fai", "Delta / Partial FAI (Change Only)"),
    ]

    SETUP_REASON_CHOICES = [
        ("new_product_intro", "New Product Introduction (NPI)"),
        ("machine_setup_change", "Machine / Tooling Setup Change"),
        ("tooling_die_change", "Tooling / Die Replacement"),
        ("process_revision", "Process / Routing Revision"),
        ("material_lot_change", "Raw Material Source / Lot Change"),
        ("drawing_revision", "Engineering Drawing / Revision Change"),
        ("periodic_recertification", "Periodic Recertification / Dormancy"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / Scheduled"),
        ("in_inspection", "In Inspection / Measurement"),
        ("approved_run_released", "Approved (Production Released)"),
        ("conditional_approval", "Conditional Approval (Pilot Run)"),
        ("rejected_setup_hold", "Rejected (Setup Hold)"),
        ("cancelled", "Cancelled"),
    ]

    RELEASE_VERDICT_CHOICES = [
        ("pending", "Pending Verdict"),
        ("released", "Full Production Run Released"),
        ("conditional_pilot_release", "Conditional Pilot Release"),
        ("rejected_retool", "Rejected / Retool & Re-inspect"),
    ]

    FAI_TYPE_CSS = {
        "full_fai": "badge-info",
        "delta_partial_fai": "badge-slate",
    }

    SETUP_REASON_CSS = {
        "new_product_intro": "badge-info",
        "machine_setup_change": "badge-slate",
        "tooling_die_change": "badge-slate",
        "process_revision": "badge-amber",
        "material_lot_change": "badge-slate",
        "drawing_revision": "badge-amber",
        "periodic_recertification": "badge-info",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_inspection": "badge-amber",
        "approved_run_released": "badge-green",
        "conditional_approval": "badge-info",
        "rejected_setup_hold": "badge-red",
        "cancelled": "badge-muted",
    }

    RELEASE_VERDICT_CSS = {
        "pending": "badge-slate",
        "released": "badge-green",
        "conditional_pilot_release": "badge-info",
        "rejected_retool": "badge-red",
    }

    title = models.CharField(max_length=255)
    fai_type = models.CharField(
        max_length=25,
        choices=FAI_TYPE_CHOICES,
        default="full_fai",
        db_index=True,
    )
    setup_reason = models.CharField(
        max_length=35,
        choices=SETUP_REASON_CHOICES,
        default="machine_setup_change",
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    production_order_number = models.CharField(max_length=64, blank=True)
    work_order = models.ForeignKey(
        "scm.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_fais",
    )
    work_center_code = models.CharField(max_length=64, blank=True)
    work_center = models.ForeignKey(
        "scm.WorkCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_fais",
    )
    machine_tooling_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Machine, CNC asset, or stamping die identifier",
    )

    item_code = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    drawing_number = models.CharField(max_length=100, blank=True)
    drawing_revision = models.CharField(max_length=32, blank=True)
    first_piece_lot_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)

    total_characteristics_inspected = models.PositiveIntegerField(default=0)
    characteristics_conforming = models.PositiveIntegerField(default=0)
    characteristics_out_of_spec = models.PositiveIntegerField(default=0)
    max_deviation_found = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. +0.003 mm on Bore Dia",
    )

    as9102_form1_complete = models.BooleanField(
        default=False,
        help_text="Part Number Accountability & Verification",
    )
    as9102_form2_complete = models.BooleanField(
        default=False,
        help_text="Product Process Accountability & Routing Sign-off",
    )
    as9102_form3_complete = models.BooleanField(
        default=False,
        help_text="Characteristic Accountability & Verification (Ballooned Drawing)",
    )
    gage_serial_numbers = models.CharField(
        max_length=255,
        blank=True,
        help_text="Calibrated instruments used (micrometer, CMM, height gauge)",
    )

    release_verdict = models.CharField(
        max_length=30,
        choices=RELEASE_VERDICT_CHOICES,
        default="pending",
        db_index=True,
    )
    conditional_release_notes = models.TextField(blank=True)

    non_conformance = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fais",
        help_text="Linked NCR if setup or first piece was rejected",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspected_fais",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_fais",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "First Article Inspection"
        verbose_name_plural = "First Article Inspections"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qfai_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qfai_ten_status"),
            models.Index(fields=["tenant", "release_verdict"], name="idx_qfai_ten_verd"),
            models.Index(fields=["tenant", "fai_type"], name="idx_qfai_ten_type"),
            models.Index(fields=["tenant", "setup_reason"], name="idx_qfai_ten_reason"),
            models.Index(fields=["tenant", "work_center"], name="idx_qfai_ten_wc"),
            models.Index(fields=["tenant", "work_order"], name="idx_qfai_ten_wo"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qfai_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_release_verdict_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def verdict_css(self):
        return self.RELEASE_VERDICT_CSS.get(self.release_verdict, "badge-slate")

    @property
    def type_css(self):
        return self.FAI_TYPE_CSS.get(self.fai_type, "badge-slate")

    @property
    def reason_css(self):
        return self.SETUP_REASON_CSS.get(self.setup_reason, "badge-slate")

    @property
    def conformance_rate(self):
        if not self.total_characteristics_inspected:
            return 0.0
        return round((self.characteristics_conforming / self.total_characteristics_inspected) * 100, 1)

    @property
    def is_approved(self):
        return self.status == "approved_run_released" or self.release_verdict == "released"

    @property
    def as9102_completed_all(self):
        return bool(self.as9102_form1_complete and self.as9102_form2_complete and self.as9102_form3_complete)
