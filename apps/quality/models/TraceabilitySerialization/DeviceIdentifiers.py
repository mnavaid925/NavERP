from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class DeviceIdentifier(TenantNumbered):
    NUMBER_PREFIX = "QUDI"

    ISSUING_AGENCY_CHOICES = [
        ("gs1", "GS1"),
        ("hibcc", "HIBCC"),
        ("iccbba", "ICCBBA"),
        ("other", "Other Recognized Agency"),
    ]

    DEVICE_CLASS_CHOICES = [
        ("class_i", "Class I (Low Risk)"),
        ("class_iia", "Class IIa / Class II (Moderate)"),
        ("class_iib", "Class IIb (Moderate-High)"),
        ("class_iii", "Class III (High Risk)"),
        ("unclassified", "Unclassified / General"),
    ]

    REGULATORY_STATUS_CHOICES = [
        ("draft", "Draft / In Preparation"),
        ("ready_to_submit", "Ready for Submission"),
        ("submitted", "Submitted to Agency"),
        ("published", "Published / Active"),
        ("rejected", "Submission Rejected"),
    ]

    DISTRIBUTION_STATUS_CHOICES = [
        ("in_commercial_distribution", "In Commercial Distribution"),
        ("off_market", "Off Market / Discontinued"),
        ("not_yet_distributed", "Not Yet in Commercial Distribution"),
    ]

    BARCODE_FORMAT_CHOICES = [
        ("gs1_datamatrix", "GS1 DataMatrix (2D)"),
        ("gs1_128", "GS1-128 (1D Linear)"),
        ("hibc_2d", "HIBC 2D Barcode"),
        ("qr_code", "QR Code"),
    ]

    MRI_STATUS_CHOICES = [
        ("mr_safe", "MR Safe"),
        ("mr_conditional", "MR Conditional"),
        ("mr_unsafe", "MR Unsafe"),
        ("not_evaluated", "Not Evaluated"),
    ]

    REGULATORY_STATUS_CSS = {
        "draft": "badge-slate",
        "ready_to_submit": "badge-info",
        "submitted": "badge-amber",
        "published": "badge-green",
        "rejected": "badge-red",
    }

    DEVICE_CLASS_CSS = {
        "class_i": "badge-slate",
        "class_iia": "badge-info",
        "class_iib": "badge-amber",
        "class_iii": "badge-red",
        "unclassified": "badge-muted",
    }

    device_name = models.CharField(max_length=255)
    model_number = models.CharField(max_length=100, blank=True)
    primary_di = models.CharField(max_length=64, db_index=True)
    issuing_agency = models.CharField(max_length=20, choices=ISSUING_AGENCY_CHOICES, default="gs1", db_index=True)
    device_class = models.CharField(max_length=20, choices=DEVICE_CLASS_CHOICES, default="class_iia", db_index=True)
    basic_udi_di = models.CharField(max_length=64, blank=True, db_index=True, help_text="EUDAMED Basic UDI-DI identifier")
    gudid_status = models.CharField(max_length=25, choices=REGULATORY_STATUS_CHOICES, default="draft", db_index=True)
    eudamed_status = models.CharField(max_length=25, choices=REGULATORY_STATUS_CHOICES, default="draft", db_index=True)
    brand_name = models.CharField(max_length=255, blank=True)
    commercial_distribution_status = models.CharField(
        max_length=35,
        choices=DISTRIBUTION_STATUS_CHOICES,
        default="in_commercial_distribution",
        db_index=True,
    )
    catalog_number = models.CharField(max_length=100, blank=True)
    barcode_format = models.CharField(max_length=25, choices=BARCODE_FORMAT_CHOICES, default="gs1_datamatrix", db_index=True)
    is_sterile = models.BooleanField(default=False)
    contains_latex = models.BooleanField(default=False)
    is_single_use = models.BooleanField(default=True)
    mri_safety_status = models.CharField(max_length=20, choices=MRI_STATUS_CHOICES, default="mr_safe", db_index=True)
    storage_handling_instructions = models.TextField(blank=True)
    fda_listing_number = models.CharField(max_length=64, blank=True)
    submission_date = models.DateField(null=True, blank=True)
    approval_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_identifiers",
    )
    regulatory_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_device_identifiers",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["device_name", "primary_di"]
        verbose_name = "Device Identifier (UDI)"
        verbose_name_plural = "Device Identifiers (UDI)"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qudi_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "primary_di"], name="idx_qudi_ten_pdi"),
            models.Index(fields=["tenant", "gudid_status"], name="idx_qudi_ten_gudid"),
            models.Index(fields=["tenant", "eudamed_status"], name="idx_qudi_ten_euda"),
        ]

    def __str__(self):
        return f"{self.number} - {self.primary_di} ({self.device_name})"
