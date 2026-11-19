import uuid

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class CertificateOfConformance(TenantNumbered):
    NUMBER_PREFIX = "QCOC"

    CERTIFICATE_TYPE_CHOICES = [
        ("standard_commercial", "Standard Commercial (ISO 9001)"),
        ("aerospace_as9100_as9102", "Aerospace (AS9100 / AS9102)"),
        ("medical_device_iso13485", "Medical Device (ISO 13485 / FDA)"),
        ("automotive_iatf_16949", "Automotive (IATF 16949)"),
        ("custom_customer_format", "Customer Specific Format"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("approved_signed", "Approved & Digitally Signed"),
        ("revoked", "Revoked / Superseded"),
    ]

    TYPE_CSS = {
        "standard_commercial": "badge-slate",
        "aerospace_as9100_as9102": "badge-info",
        "medical_device_iso13485": "badge-green",
        "automotive_iatf_16949": "badge-amber",
        "custom_customer_format": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_review": "badge-amber",
        "approved_signed": "badge-green",
        "revoked": "badge-red",
    }

    CERTIFICATE_TYPE_CSS = TYPE_CSS

    title = models.CharField(max_length=255)
    certificate_type = models.CharField(
        max_length=30,
        choices=CERTIFICATE_TYPE_CHOICES,
        default="standard_commercial",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="certificates_of_conformance",
    )
    customer_po_number = models.CharField(max_length=64, blank=True)
    sales_order_number = models.CharField(max_length=64, blank=True)
    sales_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_certificates_of_conformance",
    )
    shipment_number = models.CharField(max_length=64, blank=True)
    shipment = models.ForeignKey(
        "scm.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_certificates_of_conformance",
    )

    item_code = models.CharField(max_length=100, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    revision = models.CharField(max_length=32, blank=True, default="Rev A")
    lot_number = models.CharField(max_length=100, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    serial_numbers_text = models.TextField(
        blank=True,
        help_text="Comma-separated or newline-separated serial numbers covered by this certificate",
    )
    certified_quantity = models.PositiveIntegerField(default=1)

    inspection_lot = models.ForeignKey(
        "quality.FinalInspectionLot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates_of_conformance",
    )

    applicable_specifications = models.TextField(
        blank=True,
        help_text="Industry, military, or engineering specifications complied with (e.g. ASTM A240, Mil-Spec, ISO 9001)",
    )
    test_results_summary = models.TextField(
        blank=True,
        help_text="Summary of dimensional, tensile, hardness, electrical, or functional test outcomes",
    )
    conformance_statement = models.TextField(
        blank=True,
        help_text="Legal declaration certifying goods conform in all respects to drawing, contract, and specs",
    )

    authorized_signatory = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cocs_authorized",
    )
    signatory_title = models.CharField(
        max_length=100,
        blank=True,
        default="Director of Quality Assurance",
    )
    signed_date = models.DateField(null=True, blank=True)
    digital_signature_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="Cryptographic SHA-256 hash stamp of sign-off",
    )
    qr_verification_code = models.CharField(
        max_length=64,
        blank=True,
        unique=True,
        help_text="Unique tamper-evident token for public or customer verification",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Certificate of Conformance"
        verbose_name_plural = "Certificates of Conformance"
        indexes = [
            models.Index(fields=["tenant", "status"], name="quality_coc_tnt_stat_idx"),
            models.Index(fields=["tenant", "certificate_type"], name="quality_coc_tnt_type_idx"),
            models.Index(fields=["tenant", "customer"], name="quality_coc_tnt_cust_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.customer.name})"

    def save(self, *args, **kwargs):
        if not self.qr_verification_code:
            self.qr_verification_code = f"COC-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def type_css(self):
        return self.TYPE_CSS.get(self.certificate_type, "badge-slate")

    @property
    def is_signed(self):
        return self.status == "approved_signed" and bool(self.digital_signature_hash)
