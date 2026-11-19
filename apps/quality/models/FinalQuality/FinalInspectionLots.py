from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class FinalInspectionLot(TenantNumbered):
    NUMBER_PREFIX = "QFQC"

    INSPECTION_STAGE_CHOICES = [
        ("finished_goods_dock", "Finished Goods Receiving / Dock"),
        ("pre_packaging_fqc", "Pre-Packaging Final Inspection"),
        ("post_packaging_oqc", "Post-Packaging Outgoing Inspection"),
        ("functional_end_of_line", "Functional End-of-Line Test"),
        ("pre_shipment_audit", "Pre-Shipment Customer Audit"),
    ]

    SAMPLING_STANDARD_CHOICES = [
        ("ansi_asq_z1_4_normal", "ANSI/ASQ Z1.4 (ISO 2859-1) Normal II"),
        ("ansi_asq_z1_4_tightened", "ANSI/ASQ Z1.4 Tightened III"),
        ("ansi_asq_z1_4_reduced", "ANSI/ASQ Z1.4 Reduced I"),
        ("c_zero_sampling", "Squeglia C=0 Zero Acceptance Plan"),
        ("hundred_percent_screening", "100% 1-to-1 Screening Inspection"),
        ("custom_protocol", "Custom Customer Protocol"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    USAGE_DECISION_CHOICES = [
        ("pending", "Pending Decision"),
        ("accepted", "Accepted / Conforming"),
        ("accepted_with_concession", "Accepted with Concession"),
        ("quarantined_hold", "Quarantined on Hold"),
        ("rejected_mrb", "Rejected to MRB"),
    ]

    STAGE_CSS = {
        "finished_goods_dock": "badge-slate",
        "pre_packaging_fqc": "badge-info",
        "post_packaging_oqc": "badge-slate",
        "functional_end_of_line": "badge-amber",
        "pre_shipment_audit": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_progress": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }

    USAGE_DECISION_CSS = {
        "pending": "badge-slate",
        "accepted": "badge-green",
        "accepted_with_concession": "badge-info",
        "quarantined_hold": "badge-red",
        "rejected_mrb": "badge-red",
    }

    DECISION_CSS = USAGE_DECISION_CSS
    INSPECTION_STAGE_CSS = STAGE_CSS

    title = models.CharField(max_length=255)
    inspection_stage = models.CharField(
        max_length=30,
        choices=INSPECTION_STAGE_CHOICES,
        default="post_packaging_oqc",
        db_index=True,
    )
    sampling_standard = models.CharField(
        max_length=30,
        choices=SAMPLING_STANDARD_CHOICES,
        default="ansi_asq_z1_4_normal",
    )
    aql_critical = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.00"))
    aql_major = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))
    aql_minor = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("4.00"))

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    usage_decision = models.CharField(
        max_length=30,
        choices=USAGE_DECISION_CHOICES,
        default="pending",
        db_index=True,
    )
    decision_rationale = models.TextField(blank=True)

    item_code = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    lot_number = models.CharField(max_length=100, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    serial_number_range = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. SN-1000 through SN-1250",
    )

    lot_quantity = models.PositiveIntegerField(default=1)
    sample_size_inspected = models.PositiveIntegerField(default=1)
    critical_defects_count = models.PositiveIntegerField(default=0)
    major_defects_count = models.PositiveIntegerField(default=0)
    minor_defects_count = models.PositiveIntegerField(default=0)
    units_passed = models.PositiveIntegerField(default=0)
    units_rejected = models.PositiveIntegerField(default=0)

    visual_inspection_passed = models.BooleanField(default=True)
    dimensional_inspection_passed = models.BooleanField(default=True)
    functional_test_passed = models.BooleanField(default=True)
    packaging_inspection_passed = models.BooleanField(default=True)

    is_on_hold = models.BooleanField(default=False, db_index=True)
    hold_reason = models.TextField(blank=True)

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_inspection_lots",
    )
    sales_order_number = models.CharField(max_length=64, blank=True)
    sales_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_inspection_lots",
    )
    work_order_number = models.CharField(max_length=64, blank=True)
    work_order = models.ForeignKey(
        "scm.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_inspection_lots",
    )
    inspection_plan = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_inspection_lots",
    )
    non_conformance = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_inspection_lots",
    )
    process_deviation = models.ForeignKey(
        "quality.ProcessDeviation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_inspection_lots",
    )

    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fqc_inspections_conducted",
    )
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fqc_usage_decisions",
    )
    inspection_date = models.DateField(null=True, blank=True)
    decision_date = models.DateField(null=True, blank=True)
    inspection_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Final Inspection Lot"
        verbose_name_plural = "Final Inspection Lots"
        indexes = [
            models.Index(fields=["tenant", "status"], name="quality_fqc_tnt_stat_idx"),
            models.Index(fields=["tenant", "usage_decision"], name="quality_fqc_tnt_dec_idx"),
            models.Index(fields=["tenant", "lot_number"], name="quality_fqc_tnt_lot_idx"),
            models.Index(fields=["tenant", "is_on_hold"], name="quality_fqc_tnt_hold_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_usage_decision_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def stage_css(self):
        return self.STAGE_CSS.get(self.inspection_stage, "badge-slate")

    @property
    def decision_css(self):
        return self.USAGE_DECISION_CSS.get(self.usage_decision, "badge-slate")

    @property
    def pass_rate_percentage(self):
        if not self.sample_size_inspected:
            return 0.0
        return round((self.units_passed / self.sample_size_inspected) * 100, 1)

    @property
    def is_rejected(self):
        return self.usage_decision in ("quarantined_hold", "rejected_mrb") or self.units_rejected > 0 or self.is_on_hold
