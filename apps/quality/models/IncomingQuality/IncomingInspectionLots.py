import math
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.quality.models._base import TenantNumbered


class IncomingInspectionLot(TenantNumbered):
    NUMBER_PREFIX = "QIIL"

    STAGE_CHOICES = [
        ("pending_receipt", "Pending Dock Receipt"),
        ("in_inspection", "In Inspection"),
        ("sampling_complete", "Sampling Completed"),
        ("under_mrb", "Under MRB / Disposition Review"),
        ("completed", "Completed / Closed"),
        ("cancelled", "Cancelled"),
    ]

    USAGE_DECISION_CHOICES = [
        ("pending", "Pending Decision"),
        ("accepted", "Accepted (Full Release)"),
        ("accepted_with_deviation", "Accepted with Concession / Deviation"),
        ("quarantined", "Quarantined for Containment"),
        ("rejected", "Rejected / Return to Vendor"),
        ("skip_lot_passed", "Skip-Lot Auto Released"),
    ]

    STAGE_CSS = {
        "pending_receipt": "badge-slate",
        "in_inspection": "badge-info",
        "sampling_complete": "badge-amber",
        "under_mrb": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }

    USAGE_DECISION_CSS = {
        "pending": "badge-slate",
        "accepted": "badge-green",
        "accepted_with_deviation": "badge-amber",
        "quarantined": "badge-red",
        "rejected": "badge-red",
        "skip_lot_passed": "badge-info",
    }

    inspection_plan = models.ForeignKey(
        "quality.IncomingInspectionPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspection_lots",
    )
    item_code = models.CharField(max_length=50, db_index=True)
    item_name = models.CharField(max_length=150)
    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="incoming_inspection_lots",
    )
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_inspection_lots",
    )
    goods_receipt_note = models.ForeignKey(
        "scm.GoodsReceiptNote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_inspection_lots",
    )
    lot_number = models.CharField(max_length=50, db_index=True)
    heat_or_batch = models.CharField(max_length=50, blank=True)
    receipt_date = models.DateField(null=True, blank=True)
    inspection_date = models.DateField(null=True, blank=True)
    lot_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    sample_size = models.PositiveIntegerField(
        default=0,
        help_text="Sample size computed from ANSI/ASQ Z1.4",
    )
    inspected_quantity = models.PositiveIntegerField(default=0)
    accepted_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    rejected_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    quarantine_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))

    critical_defects = models.PositiveIntegerField(default=0)
    major_defects = models.PositiveIntegerField(default=0)
    minor_defects = models.PositiveIntegerField(default=0)

    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="pending_receipt",
        db_index=True,
    )
    usage_decision = models.CharField(
        max_length=25,
        choices=USAGE_DECISION_CHOICES,
        default="pending",
        db_index=True,
    )
    usage_decision_notes = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_inspection_lots",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspected_inspection_lots",
    )

    measurements_data = models.JSONField(
        default=list,
        blank=True,
        help_text="Raw CTQ measurements: [{characteristic, sample_no, value, is_pass}]",
    )
    spc_mean = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    spc_std_dev = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    spc_cp = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    spc_cpk = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    spc_out_of_control = models.BooleanField(default=False)

    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originating_inspection_lots",
    )
    linked_deviation = models.ForeignKey(
        "quality.ProcessDeviation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_inspection_lots",
    )
    linked_containment = models.ForeignKey(
        "quality.QuarantineContainment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_inspection_lots",
    )
    linked_scar = models.ForeignKey(
        "quality.SupplierCorrectiveAction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_inspection_lots",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Incoming Inspection Lot"
        verbose_name_plural = "Incoming Inspection Lots"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qiil_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "stage"], name="idx_qiil_ten_stage"),
            models.Index(fields=["tenant", "usage_decision"], name="idx_qiil_ten_decision"),
            models.Index(fields=["tenant", "supplier"], name="idx_qiil_ten_supp"),
            models.Index(fields=["tenant", "item_code"], name="idx_qiil_ten_item"),
            models.Index(fields=["tenant", "lot_number"], name="idx_qiil_ten_lot"),
        ]

    def __str__(self):
        return f"{self.number} - Lot {self.lot_number} ({self.item_code})"

    def get_absolute_url(self):
        return reverse("quality:incoming_inspection_lot_detail", kwargs={"pk": self.pk})

    @property
    def stage_css(self):
        return self.STAGE_CSS.get(self.stage, "badge-slate")

    @property
    def usage_decision_css(self):
        return self.USAGE_DECISION_CSS.get(self.usage_decision, "badge-slate")

    def recalculate_spc(self, characteristic_name=None, lsl=None, usl=None):
        if not self.measurements_data:
            return

        if (lsl is None or usl is None) and self.inspection_plan and self.inspection_plan.characteristics_matrix:
            matrix = self.inspection_plan.characteristics_matrix
            if isinstance(matrix, list):
                target_char = None
                for spec in matrix:
                    if not isinstance(spec, dict):
                        continue
                    spec_name = spec.get("name") or spec.get("characteristic") or ""
                    if characteristic_name and spec_name.strip().lower() == characteristic_name.strip().lower():
                        target_char = spec
                        break
                if target_char is None and len(matrix) == 1 and isinstance(matrix[0], dict):
                    target_char = matrix[0]
                if target_char:
                    if lsl is None and target_char.get("lsl") is not None:
                        try:
                            lsl = float(target_char["lsl"])
                        except (ValueError, TypeError):
                            pass
                    if usl is None and target_char.get("usl") is not None:
                        try:
                            usl = float(target_char["usl"])
                        except (ValueError, TypeError):
                            pass

        values = []
        for m in self.measurements_data:
            if not isinstance(m, dict):
                continue
            if characteristic_name and m.get("characteristic") != characteristic_name:
                continue
            val = m.get("value")
            if val is not None:
                try:
                    fval = float(val)
                    if math.isfinite(fval):
                        values.append(fval)
                except (ValueError, TypeError):
                    continue

        if len(values) < 2:
            return

        n = len(values)
        mean_val = sum(values) / n
        variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
        std_val = math.sqrt(variance)

        if not math.isfinite(mean_val) or not math.isfinite(std_val):
            return

        self.spc_mean = Decimal(f"{mean_val:.4f}")
        self.spc_std_dev = Decimal(f"{std_val:.4f}")

        if lsl is not None and usl is not None and std_val > 0:
            usl_f = float(usl)
            lsl_f = float(lsl)
            cp_val = (usl_f - lsl_f) / (6 * std_val)
            cpu_val = (usl_f - mean_val) / (3 * std_val)
            cpl_val = (mean_val - lsl_f) / (3 * std_val)
            cpk_val = min(cpu_val, cpl_val)

            self.spc_cp = Decimal(f"{cp_val:.3f}")
            self.spc_cpk = Decimal(f"{cpk_val:.3f}")
            self.spc_out_of_control = cpk_val < 1.33
        else:
            self.spc_out_of_control = False
