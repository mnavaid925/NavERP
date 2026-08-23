"""Inventory 5.10 Returns Management — ReturnInspection [RMI-] and ReturnInspectionChecklist.

**OWNERSHIP (L36/L29):**
SCM 4.10 owns the primary RMA document (``scm.ReturnAuthorization``) and the accounting/ledger
posting disposition record (``scm.ReturnDisposition``).
Module 5 adds the warehouse floor operations layer: physical inspection tracking, component
completeness verification, functional/cosmetic grading, and restock fee recommendations.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.inventory.models._base import *  # noqa: F401,F403


class ReturnInspection(TenantNumbered):
    """Warehouse receiving inspection for returned merchandise [RMI-]."""

    NUMBER_PREFIX = "RMI"

    PACKAGING_CHOICES = [
        ("intact", "Original & Intact"),
        ("opened", "Opened / Minor Wear"),
        ("damaged", "Heavily Damaged"),
        ("missing", "Missing / No Packaging"),
    ]

    COMPLETENESS_CHOICES = [
        ("complete", "Complete (All Parts/Accessories)"),
        ("missing_accessories", "Missing Cables/Accessories"),
        ("missing_parts", "Missing Major Components"),
        ("missing_manual", "Missing Manual/Docs Only"),
    ]

    FUNCTIONAL_CHOICES = [
        ("pass", "Fully Functional"),
        ("partial", "Partially Functional / Minor Defect"),
        ("fail", "Non-Functional / Defective"),
        ("untested", "Untested / Not Applicable"),
    ]

    COSMETIC_CHOICES = [
        ("new", "Like New / Pristine"),
        ("minor_wear", "Minor Scratches / Light Wear"),
        ("heavy_wear", "Heavy Wear / Dents"),
        ("broken", "Broken / Cracked"),
    ]

    GRADE_CHOICES = [
        ("a", "Grade A — Like New"),
        ("b", "Grade B — Minor Wear / Refurbishable"),
        ("c", "Grade C — Heavy Wear / Secondary"),
        ("d", "Grade D — Defective / Unsellable"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Inspection"),
        ("in_progress", "In Progress"),
        ("passed", "Passed Inspection"),
        ("failed", "Failed Inspection"),
        ("quarantined", "Quarantined"),
    ]

    return_authorization = models.ForeignKey(
        "scm.ReturnAuthorization",
        on_delete=models.CASCADE,
        related_name="inventory_inspections",
        help_text="The parent Return Authorization (RMA) ticket",
    )
    return_line = models.ForeignKey(
        "scm.ReturnLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_inspections",
        help_text="Specific return line on the RMA (optional)",
    )
    return_disposition = models.ForeignKey(
        "scm.ReturnDisposition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_inspections",
        help_text="Receiving bench disposition row (optional)",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.PROTECT,
        related_name="inventory_return_inspections",
        help_text="The item SKU inspected",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Quantity of units inspected",
    )
    lot_serial = models.ForeignKey(
        "scm.LotSerial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Specific lot or serial number inspected",
    )
    inspected_by = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_inspections_conducted",
        help_text="Staff/Inspector party who performed the inspection",
    )
    inspected_at = models.DateTimeField(
        default=timezone.now,
        help_text="Date and time the inspection took place",
    )
    packaging_condition = models.CharField(
        max_length=20,
        choices=PACKAGING_CHOICES,
        default="opened",
        help_text="Condition of packaging upon warehouse receipt",
    )
    completeness = models.CharField(
        max_length=20,
        choices=COMPLETENESS_CHOICES,
        default="complete",
        help_text="Completeness of product accessories, manuals, and parts",
    )
    functional_status = models.CharField(
        max_length=20,
        choices=FUNCTIONAL_CHOICES,
        default="pass",
        help_text="Operational testing verdict",
    )
    cosmetic_condition = models.CharField(
        max_length=20,
        choices=COSMETIC_CHOICES,
        default="new",
        help_text="Visual cosmetic evaluation",
    )
    condition_grade = models.CharField(
        max_length=1,
        choices=GRADE_CHOICES,
        default="a",
        help_text="Assigned condition grade: Grade A (new) to Grade D (defective)",
    )
    serial_verified = models.BooleanField(
        default=True,
        help_text="Whether serial number matches the RMA authorization record",
    )
    is_restock_eligible = models.BooleanField(
        default=True,
        help_text="Whether goods are fit to be restocked into sellable inventory",
    )
    suggested_restock_fee_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100.00"))],
        help_text="Recommended restocking fee percentage based on condition findings",
    )
    findings = models.TextField(
        blank=True,
        help_text="Detailed defect notes, missing parts, or inspector comments",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="passed",
        help_text="Overall status of this warehouse inspection",
    )

    class Meta:
        ordering = ["-inspected_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_rmi_tnt_stat_idx"),
            models.Index(fields=["tenant", "inspected_at"], name="inv_rmi_tnt_insp_idx"),
            models.Index(fields=["tenant", "condition_grade"], name="inv_rmi_tnt_grd_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.item.sku} × {self.quantity})"

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return

        # Cross-tenant guards. NOTE: ``scm.ReturnLine`` is deliberately TENANT-LESS on the spine
        # (reached only through its authorisation), so its guard goes through the parent RMA.
        if self.return_authorization_id and getattr(self.return_authorization, "tenant_id", None) != tenant_id:
            raise ValidationError({"return_authorization": "Return authorization belongs to another workspace."})
        if self.return_line_id and getattr(
            self.return_line.return_authorization, "tenant_id", None
        ) != tenant_id:
            raise ValidationError({"return_line": "Return line belongs to another workspace."})
        if self.return_disposition_id and getattr(self.return_disposition, "tenant_id", None) != tenant_id:
            raise ValidationError({"return_disposition": "Return disposition belongs to another workspace."})
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            raise ValidationError({"item": "Item belongs to another workspace."})
        if self.lot_serial_id and getattr(self.lot_serial, "tenant_id", None) != tenant_id:
            raise ValidationError({"lot_serial": "Lot/Serial belongs to another workspace."})
        if self.inspected_by_id and getattr(self.inspected_by, "tenant_id", None) != tenant_id:
            raise ValidationError({"inspected_by": "Inspector party belongs to another workspace."})


class ReturnInspectionChecklist(TenantOwned):
    """Checklist checkpoint evaluated during a return inspection."""

    RESULT_CHOICES = [
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("na", "N/A"),
    ]

    inspection = models.ForeignKey(
        ReturnInspection,
        on_delete=models.CASCADE,
        related_name="checklist_items",
        help_text="The parent inspection record",
    )
    checkpoint = models.CharField(
        max_length=120,
        help_text="Checkpoint label (e.g. 'Power-on test', 'Packaging integrity', 'Factory reset')",
    )
    result = models.CharField(
        max_length=10,
        choices=RESULT_CHOICES,
        default="pass",
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Specific note on this checkpoint",
    )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["tenant", "inspection"], name="inv_rmick_tnt_insp_idx"),
        ]

    def __str__(self):
        return f"{self.checkpoint}: {self.get_result_display()}"

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return
        if self.inspection_id and getattr(self.inspection, "tenant_id", None) != tenant_id:
            raise ValidationError({"inspection": "Inspection record belongs to another workspace."})
