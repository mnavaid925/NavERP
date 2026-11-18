from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class InProcessInspection(TenantNumbered):
    NUMBER_PREFIX = "QIPQ"

    INSPECTION_TYPE_CHOICES = [
        ("visual_surface", "Visual / Surface Finish Inspection"),
        ("dimensional_gauging", "Dimensional / Gauging Verification"),
        ("functional_test", "In-Line Functional / Electrical Test"),
        ("automated_vision", "Automated Vision / Optical Inspection"),
        ("in_line_stage_gate", "Stage-Gate Completion Inspection"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    DISPOSITION_CHOICES = [
        ("pending", "Pending Disposition"),
        ("pass", "Pass / Conforming"),
        ("conditional_pass", "Conditional Pass (Deviation)"),
        ("rework_required", "Rework Required"),
        ("reject_scrap", "Reject / Scrap"),
        ("quarantine_hold", "Quarantine Hold"),
    ]

    DEFECT_CATEGORY_CHOICES = [
        ("", "None / Conforming"),
        ("dimensional", "Dimensional Out-of-Tolerance"),
        ("surface_cosmetic", "Surface / Cosmetic Defect"),
        ("functional_electrical", "Functional / Electrical Failure"),
        ("material_flaw", "Raw Material Flaw / Void"),
        ("assembly_error", "Assembly / Orientation Error"),
        ("contamination", "Foreign Object / Contamination"),
        ("other", "Other Defect Category"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_progress": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }

    DISPOSITION_CSS = {
        "pending": "badge-slate",
        "pass": "badge-green",
        "conditional_pass": "badge-info",
        "rework_required": "badge-amber",
        "reject_scrap": "badge-red",
        "quarantine_hold": "badge-red",
    }

    TYPE_CSS = {
        "visual_surface": "badge-slate",
        "dimensional_gauging": "badge-info",
        "functional_test": "badge-amber",
        "automated_vision": "badge-info",
        "in_line_stage_gate": "badge-slate",
    }

    DEFECT_CSS = {
        "": "badge-muted",
        "dimensional": "badge-amber",
        "surface_cosmetic": "badge-info",
        "functional_electrical": "badge-red",
        "material_flaw": "badge-red",
        "assembly_error": "badge-amber",
        "contamination": "badge-red",
        "other": "badge-slate",
    }

    INSPECTION_TYPE_CSS = TYPE_CSS
    DEFECT_CATEGORY_CSS = DEFECT_CSS

    title = models.CharField(max_length=255)
    inspection_type = models.CharField(
        max_length=30,
        choices=INSPECTION_TYPE_CHOICES,
        default="visual_surface",
        db_index=True,
    )
    stage_gate = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manufacturing stage-gate (e.g. Primary Machining, Sub-Assembly, Final In-Line)",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    disposition = models.CharField(
        max_length=25,
        choices=DISPOSITION_CHOICES,
        default="pending",
        db_index=True,
    )

    production_order_number = models.CharField(max_length=64, blank=True)
    work_order = models.ForeignKey(
        "scm.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_in_process_inspections",
    )
    work_center_code = models.CharField(max_length=64, blank=True)
    work_center = models.ForeignKey(
        "scm.WorkCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_in_process_inspections",
    )
    operation_step = models.CharField(max_length=64, blank=True, help_text="e.g. Op 020 - Turning")
    item_code = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    lot_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)

    batch_quantity = models.PositiveIntegerField(default=1)
    sample_size_inspected = models.PositiveIntegerField(default=1)
    quantity_passed = models.PositiveIntegerField(default=0)
    quantity_rejected = models.PositiveIntegerField(default=0)
    quantity_reworked = models.PositiveIntegerField(default=0)

    defect_category = models.CharField(
        max_length=30,
        choices=DEFECT_CATEGORY_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    defect_description = models.TextField(blank=True)

    controlled_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="in_process_inspections",
        help_text="Linked SOP or Digital Work Instruction",
    )
    work_instruction_step = models.CharField(max_length=100, blank=True)
    operator_sign_off = models.BooleanField(default=False)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator_in_process_inspections",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_in_process_inspections",
    )
    inspection_date = models.DateField(null=True, blank=True)
    non_conformance = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="in_process_inspections",
        help_text="Escalated NCR on inspection failure",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "In-Process Inspection"
        verbose_name_plural = "In-Process Inspections"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qipq_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qipq_ten_status"),
            models.Index(fields=["tenant", "disposition"], name="idx_qipq_ten_disp"),
            models.Index(fields=["tenant", "inspection_type"], name="idx_qipq_ten_type"),
            models.Index(fields=["tenant", "work_center"], name="idx_qipq_ten_wc"),
            models.Index(fields=["tenant", "work_order"], name="idx_qipq_ten_wo"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qipq_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_disposition_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def disposition_css(self):
        return self.DISPOSITION_CSS.get(self.disposition, "badge-slate")

    @property
    def type_css(self):
        return self.TYPE_CSS.get(self.inspection_type, "badge-slate")

    @property
    def defect_css(self):
        return self.DEFECT_CSS.get(self.defect_category, "badge-muted")

    @property
    def pass_rate_percentage(self):
        if not self.sample_size_inspected:
            return 0.0
        return round((self.quantity_passed / self.sample_size_inspected) * 100, 1)

    @property
    def is_failed(self):
        return self.disposition in ("reject_scrap", "quarantine_hold", "rework_required") or self.quantity_rejected > 0
