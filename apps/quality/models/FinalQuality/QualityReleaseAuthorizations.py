from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class QualityReleaseAuthorization(TenantNumbered):
    NUMBER_PREFIX = "QREL"

    RELEASE_DISPOSITION_CHOICES = [
        ("pending_review", "Pending Quality Review"),
        ("released_full", "Fully Released for Shipment"),
        ("conditional_release", "Conditional Release (Concession)"),
        ("quarantined_hold", "Quarantined on Quality Hold"),
        ("rejected_shipping_blocked", "Rejected / Shipping Blocked"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active_hold", "Active Hold"),
        ("authorized", "Authorized & Signed"),
        ("cancelled", "Cancelled"),
    ]

    DISPOSITION_CSS = {
        "pending_review": "badge-slate",
        "released_full": "badge-green",
        "conditional_release": "badge-info",
        "quarantined_hold": "badge-red",
        "rejected_shipping_blocked": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "active_hold": "badge-red",
        "authorized": "badge-green",
        "cancelled": "badge-muted",
    }

    RELEASE_DISPOSITION_CSS = DISPOSITION_CSS

    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    release_disposition = models.CharField(
        max_length=30,
        choices=RELEASE_DISPOSITION_CHOICES,
        default="pending_review",
        db_index=True,
    )

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="quality_releases",
    )
    destination_country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Destination country for export compliance check",
    )
    destination_facility = models.CharField(max_length=255, blank=True)

    shipment_number = models.CharField(max_length=64, blank=True)
    shipment = models.ForeignKey(
        "scm.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_releases",
    )
    sales_order_number = models.CharField(max_length=64, blank=True)
    sales_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_releases",
    )
    lot_number = models.CharField(max_length=100, blank=True)
    quantity_authorized = models.PositiveIntegerField(default=1)

    inspection_lot = models.ForeignKey(
        "quality.FinalInspectionLot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_releases",
    )
    certificate_of_conformance = models.ForeignKey(
        "quality.CertificateOfConformance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_releases",
    )
    packaging_verification = models.ForeignKey(
        "quality.PackagingLabelVerification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_releases",
    )

    is_on_hold = models.BooleanField(default=False, db_index=True)
    hold_reason = models.TextField(blank=True)

    final_inspection_passed = models.BooleanField(
        default=True,
        help_text="Final inspection lot passed or accepted with concession",
    )
    no_open_ncrs_or_capas = models.BooleanField(
        default=True,
        help_text="Verified zero open NCRs, deviations, or blocking CAPAs on this batch",
    )
    packaging_label_approved = models.BooleanField(
        default=True,
        help_text="Packaging and barcode verification passed",
    )
    coc_issued_and_signed = models.BooleanField(
        default=True,
        help_text="Certificate of Conformance issued and signed",
    )
    export_compliance_verified = models.BooleanField(
        default=True,
        help_text="Export control, ECCN/ITAR, and restricted party screening cleared",
    )
    certificate_of_origin_attached = models.BooleanField(
        default=False,
        help_text="Certificate of origin attached if required by destination customs",
    )

    shipping_container_security_seal = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bolt seal, cable seal, or container tamper tag number",
    )
    carrier_name = models.CharField(max_length=100, blank=True)
    tracking_reference = models.CharField(max_length=100, blank=True)

    releasing_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments_released",
    )
    release_date = models.DateField(null=True, blank=True)
    concession_rationale = models.TextField(
        blank=True,
        help_text="Required if conditional release granted",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Quality Release Authorization"
        verbose_name_plural = "Quality Release Authorizations"
        indexes = [
            models.Index(fields=["tenant", "status"], name="quality_rel_tnt_stat_idx"),
            models.Index(fields=["tenant", "release_disposition"], name="quality_rel_tnt_disp_idx"),
            models.Index(fields=["tenant", "is_on_hold"], name="quality_rel_tnt_hold_idx"),
            models.Index(fields=["tenant", "customer"], name="quality_rel_tnt_cust_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_release_disposition_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def disposition_css(self):
        return self.DISPOSITION_CSS.get(self.release_disposition, "badge-slate")

    @property
    def is_cleared_to_ship(self):
        return (
            self.status == "authorized"
            and self.release_disposition in ("released_full", "conditional_release")
            and not self.is_on_hold
            and self.final_inspection_passed
            and self.no_open_ncrs_or_capas
            and self.packaging_label_approved
            and self.coc_issued_and_signed
        )
