from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class PackagingLabelVerification(TenantNumbered):
    NUMBER_PREFIX = "QPKG"

    BARCODE_SYMBOLOGY_CHOICES = [
        ("code_128_1d", "Code 128 (1D Linear)"),
        ("datamatrix_gs1_2d", "GS1 DataMatrix (2D)"),
        ("qr_code_2d", "QR Code (2D)"),
        ("gs1_128_sscc", "GS1-128 / SSCC Carton Code"),
        ("upc_ean_retail", "UPC-A / EAN-13 Retail Code"),
        ("other", "Other Symbology"),
    ]

    ISO_IEC_GRADE_CHOICES = [
        ("grade_a_4_0", "Grade A (3.5 - 4.0) Excellent"),
        ("grade_b_3_0", "Grade B (2.5 - 3.4) Good"),
        ("grade_c_2_0", "Grade C (1.5 - 2.4) Acceptable"),
        ("grade_d_1_0", "Grade D (0.5 - 1.4) Marginal"),
        ("grade_f_fail", "Grade F (0.0 - 0.4) Unacceptable / Fail"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / Staged"),
        ("verified", "Verified / Completed"),
        ("failed", "Failed Verification"),
        ("cancelled", "Cancelled"),
    ]

    DISPOSITION_CHOICES = [
        ("pending", "Pending Verification"),
        ("pass_released", "Pass / Released to Pack"),
        ("relabel_required", "Relabeling Required"),
        ("repack_required", "Repackaging Required"),
        ("reject_quarantine", "Reject / Quarantine"),
    ]

    BARCODE_CSS = {
        "code_128_1d": "badge-slate",
        "datamatrix_gs1_2d": "badge-info",
        "qr_code_2d": "badge-info",
        "gs1_128_sscc": "badge-amber",
        "upc_ean_retail": "badge-slate",
        "other": "badge-muted",
    }

    ISO_IEC_GRADE_CSS = {
        "grade_a_4_0": "badge-green",
        "grade_b_3_0": "badge-green",
        "grade_c_2_0": "badge-amber",
        "grade_d_1_0": "badge-amber",
        "grade_f_fail": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "verified": "badge-green",
        "failed": "badge-red",
        "cancelled": "badge-muted",
    }

    DISPOSITION_CSS = {
        "pending": "badge-slate",
        "pass_released": "badge-green",
        "relabel_required": "badge-amber",
        "repack_required": "badge-amber",
        "reject_quarantine": "badge-red",
    }

    GRADE_CSS = ISO_IEC_GRADE_CSS

    title = models.CharField(max_length=255)
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

    item_code = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    lot_number = models.CharField(max_length=100, blank=True)
    carton_count_inspected = models.PositiveIntegerField(default=1)

    label_part_number = models.CharField(max_length=100, blank=True)
    label_artwork_revision = models.CharField(max_length=32, blank=True, default="Rev 1")
    artwork_master = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="packaging_verifications",
        help_text="Released artwork master specification",
    )

    barcode_symbology = models.CharField(
        max_length=30,
        choices=BARCODE_SYMBOLOGY_CHOICES,
        default="datamatrix_gs1_2d",
    )
    scanned_barcode_data = models.CharField(
        max_length=255,
        blank=True,
        help_text="Decoded text string from barcode scanner",
    )
    iso_iec_print_grade = models.CharField(
        max_length=20,
        choices=ISO_IEC_GRADE_CHOICES,
        default="grade_a_4_0",
    )

    label_content_accurate = models.BooleanField(
        default=True,
        help_text="Part number, description, quantity, batch/lot, and manufacturing date match perfectly",
    )
    regulatory_symbols_present = models.BooleanField(
        default=True,
        help_text="CE, UL, RoHS, WEEE, FDA, country-of-origin symbols present and legible",
    )
    serialization_verified = models.BooleanField(
        default=True,
        help_text="Serial numbers adhere to scheme and contain zero duplicates",
    )
    carton_integrity_intact = models.BooleanField(
        default=True,
        help_text="Outer shipping cartons free of tears, moisture, crushing, or structural damage",
    )
    tamper_evident_seal_intact = models.BooleanField(
        default=True,
        help_text="Tamper-evident tape, security seals, or shrink wrap intact",
    )
    cushioning_dunnage_adequate = models.BooleanField(
        default=True,
        help_text="Internal cushioning and ESD/moisture barrier protection verified",
    )
    pallet_stacking_compliant = models.BooleanField(
        default=True,
        help_text="Pallet pattern, strapping, corner boards, and stretch wrap verified",
    )

    inspection_lot = models.ForeignKey(
        "quality.FinalInspectionLot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="packaging_verifications",
    )
    shipment = models.ForeignKey(
        "scm.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="packaging_verifications",
    )
    verifier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="packaging_verifications_performed",
    )
    verified_date = models.DateField(null=True, blank=True)
    discrepancy_details = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Packaging & Label Verification"
        verbose_name_plural = "Packaging & Label Verifications"
        indexes = [
            models.Index(fields=["tenant", "status"], name="quality_pkg_tnt_stat_idx"),
            models.Index(fields=["tenant", "disposition"], name="quality_pkg_tnt_disp_idx"),
            models.Index(fields=["tenant", "iso_iec_print_grade"], name="quality_pkg_tnt_grd_idx"),
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
    def grade_css(self):
        return self.ISO_IEC_GRADE_CSS.get(self.iso_iec_print_grade, "badge-slate")

    @property
    def barcode_css(self):
        return self.BARCODE_CSS.get(self.barcode_symbology, "badge-slate")

    @property
    def is_passed(self):
        return (
            self.disposition == "pass_released"
            and self.iso_iec_print_grade in ("grade_a_4_0", "grade_b_3_0", "grade_c_2_0")
            and self.label_content_accurate
            and self.carton_integrity_intact
        )
