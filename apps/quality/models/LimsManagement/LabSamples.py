from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class LabSample(TenantNumbered):
    NUMBER_PREFIX = "QSMP"

    SAMPLE_TYPE_CHOICES = [
        ("raw_material", "Raw Material"),
        ("in_process", "In-Process Intermediate"),
        ("finished_product", "Finished Product"),
        ("stability", "Stability Study Sample"),
        ("environmental", "Environmental Monitoring"),
        ("water_purified", "Purified Water / Utility"),
        ("retained_sample", "Retained Archive Sample"),
        ("blind_qc", "Blind QC / Proficiency"),
    ]

    STATUS_CHOICES = [
        ("registered", "Registered / Logged"),
        ("received", "Received in Lab"),
        ("in_testing", "Testing in Progress"),
        ("testing_completed", "Testing Completed"),
        ("approved", "Approved / Conforms"),
        ("rejected", "Rejected / OOS"),
        ("disposed", "Sample Disposed"),
        ("retained", "Retained in Vault"),
    ]

    STORAGE_CONDITION_CHOICES = [
        ("ambient", "Ambient (15-25°C)"),
        ("refrigerated_2_8c", "Refrigerated (2-8°C)"),
        ("frozen_minus_20c", "Frozen (-20°C)"),
        ("ultra_low_minus_80c", "Ultra-Low (-80°C)"),
        ("desiccated", "Desiccated / Dry"),
        ("light_protected", "Light-Protected / Amber"),
    ]

    STATUS_CSS = {
        "registered": "badge-slate",
        "received": "badge-info",
        "in_testing": "badge-amber",
        "testing_completed": "badge-info",
        "approved": "badge-green",
        "rejected": "badge-red",
        "disposed": "badge-muted",
        "retained": "badge-slate",
    }

    SAMPLE_TYPE_CSS = {
        "raw_material": "badge-info",
        "in_process": "badge-amber",
        "finished_product": "badge-green",
        "stability": "badge-slate",
        "environmental": "badge-info",
        "water_purified": "badge-info",
        "retained_sample": "badge-slate",
        "blind_qc": "badge-amber",
    }

    sample_name = models.CharField(max_length=255)
    sample_type = models.CharField(
        max_length=35,
        choices=SAMPLE_TYPE_CHOICES,
        default="raw_material",
        db_index=True,
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="registered",
        db_index=True,
    )
    matrix_description = models.CharField(max_length=255, blank=True)
    source_batch_number = models.CharField(max_length=100, blank=True, db_index=True)
    item_code = models.CharField(max_length=100, blank=True, db_index=True)
    item_name = models.CharField(max_length=255, blank=True)
    sampling_point = models.CharField(max_length=150, blank=True)
    sampled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collected_lab_samples",
    )
    sampled_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_lab_samples",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    current_custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_lab_samples",
    )
    storage_location = models.CharField(
        max_length=150,
        blank=True,
        help_text="e.g. Cold Room 02, Freezer -80C Rack 4, Shelf B",
    )
    storage_condition = models.CharField(
        max_length=30,
        choices=STORAGE_CONDITION_CHOICES,
        default="ambient",
    )
    quantity_collected = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("1.0000"),
    )
    unit_of_measure = models.CharField(max_length=25, default="g")
    retest_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    barcode_identifier = models.CharField(max_length=120, blank=True, db_index=True)
    chain_of_custody_log = models.TextField(
        blank=True,
        help_text="Timestamped audit entries of custodian handoffs",
    )
    work_order = models.ForeignKey(
        "scm.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_samples",
    )
    batch_record = models.ForeignKey(
        "quality.BatchRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_samples",
    )
    facility = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_samples",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "sample_name"]
        verbose_name = "Lab Sample"
        verbose_name_plural = "Lab Samples"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qsmp_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "sample_type"], name="idx_qsmp_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_qsmp_ten_status"),
            models.Index(fields=["tenant", "item_code"], name="idx_qsmp_ten_item"),
            models.Index(fields=["tenant", "source_batch_number"], name="idx_qsmp_ten_batch"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qsmp_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.sample_name} ({self.get_sample_type_display()})"

    @property
    def is_received(self):
        return self.status in ["received", "in_testing", "testing_completed", "approved", "rejected"]

    @property
    def can_test(self):
        return self.status in ["received", "in_testing"]

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def get_sample_type_badge(self):
        return self.SAMPLE_TYPE_CSS.get(self.sample_type, "badge-info")
