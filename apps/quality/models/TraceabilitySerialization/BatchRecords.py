from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class BatchRecord(TenantNumbered):
    NUMBER_PREFIX = "QBMR"

    STATUS_CHOICES = [
        ("draft", "Draft / Staged"),
        ("in_production", "In Production"),
        ("production_complete", "Production Complete"),
        ("qa_review", "Under QA Review"),
        ("released", "Batch Released"),
        ("rejected", "Batch Rejected"),
        ("quarantined", "Quarantined Hold"),
    ]

    RELEASE_STATUS_CHOICES = [
        ("pending", "Pending Disposition"),
        ("approved_full", "Full Release Approved"),
        ("approved_concession", "Release with Concession"),
        ("rejected", "Disposition Rejected"),
        ("on_hold", "Quality Hold Active"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_production": "badge-info",
        "production_complete": "badge-info",
        "qa_review": "badge-amber",
        "released": "badge-green",
        "rejected": "badge-red",
        "quarantined": "badge-amber",
    }

    RELEASE_STATUS_CSS = {
        "pending": "badge-slate",
        "approved_full": "badge-green",
        "approved_concession": "badge-amber",
        "rejected": "badge-red",
        "on_hold": "badge-red",
    }

    title = models.CharField(max_length=255)
    batch_number = models.CharField(max_length=100, db_index=True)
    product_code = models.CharField(max_length=100, db_index=True)
    product_name = models.CharField(max_length=255)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)
    release_status = models.CharField(max_length=25, choices=RELEASE_STATUS_CHOICES, default="pending", db_index=True)
    production_order_number = models.CharField(max_length=64, blank=True)
    work_order = models.ForeignKey(
        "scm.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_batch_records",
    )
    master_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_batch_records",
    )
    planned_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    actual_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unit_of_measure = models.CharField(max_length=25, default="EA")
    yield_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    manufacturing_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    retest_date = models.DateField(null=True, blank=True)
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervised_batch_records",
    )
    qa_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_batch_records",
    )
    qa_decision_at = models.DateTimeField(null=True, blank=True)
    electronic_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_record_signatures",
    )
    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_records",
    )
    linked_deviation = models.ForeignKey(
        "quality.ProcessDeviation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_records",
    )
    linked_fqc = models.ForeignKey(
        "quality.FinalInspectionLot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_records",
    )
    component_genealogy = models.JSONField(default=list, blank=True)
    checklist_passed = models.BooleanField(default=False)
    is_quarantined = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "batch_number"]
        verbose_name = "Batch Manufacturing Record"
        verbose_name_plural = "Batch Manufacturing Records"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qbmr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "batch_number"], name="idx_qbmr_ten_batch"),
            models.Index(fields=["tenant", "status"], name="idx_qbmr_ten_status"),
            models.Index(fields=["tenant", "release_status"], name="idx_qbmr_ten_release"),
        ]

    def __str__(self):
        return f"{self.number} - {self.batch_number} ({self.product_name})"

    def save(self, *args, **kwargs):
        if self.planned_quantity and self.planned_quantity > Decimal("0.00"):
            self.yield_percentage = (
                (self.actual_quantity / self.planned_quantity) * Decimal("100.00")
            ).quantize(Decimal("0.01"))
        else:
            self.yield_percentage = Decimal("0.00")
        super().save(*args, **kwargs)

    @property
    def can_release(self):
        return (
            self.checklist_passed
            and not self.is_quarantined
            and (self.linked_ncr is None or getattr(self.linked_ncr, "status", "") == "closed")
        )
