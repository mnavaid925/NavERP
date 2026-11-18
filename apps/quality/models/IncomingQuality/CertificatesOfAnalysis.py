import math

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.quality.models._base import TenantNumbered


class CertificateOfAnalysis(TenantNumbered):
    NUMBER_PREFIX = "QCOA"

    STATUS_CHOICES = [
        ("received", "Received / Unverified"),
        ("verified_compliant", "Verified Compliant"),
        ("exception_detected", "Specification Exception Detected"),
        ("rejected", "Rejected / Invalid CoA"),
    ]

    STATUS_CSS = {
        "received": "badge-slate",
        "verified_compliant": "badge-green",
        "exception_detected": "badge-amber",
        "rejected": "badge-red",
    }

    certificate_number = models.CharField(
        max_length=100,
        help_text="Supplier's original CoA/Test Report number",
    )
    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="certificates_of_analysis",
    )
    item_code = models.CharField(max_length=50, db_index=True)
    item_name = models.CharField(max_length=150)
    lot_number = models.CharField(max_length=50, db_index=True)
    inspection_lot = models.ForeignKey(
        "quality.IncomingInspectionLot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates_of_analysis",
    )
    inspection_plan = models.ForeignKey(
        "quality.IncomingInspectionPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates_of_analysis",
    )
    manufacturer_name = models.CharField(max_length=150, blank=True)
    date_of_manufacture = models.DateField(null=True, blank=True)
    expiry_or_retest_date = models.DateField(null=True, blank=True)
    lab_accreditation = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. ISO/IEC 17025 accredited laboratory",
    )
    parameters_payload = models.JSONField(
        default=list,
        blank=True,
        help_text="Analytical parameters: [{parameter, method, lsl, target, usl, actual_value, unit, is_pass}]",
    )
    variance_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of parameters failing tolerance limits",
    )
    is_within_spec = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="received",
        db_index=True,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_coas",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    supporting_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_coas",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Certificate of Analysis"
        verbose_name_plural = "Certificates of Analysis"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qcoa_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcoa_ten_status"),
            models.Index(fields=["tenant", "supplier"], name="idx_qcoa_ten_supp"),
            models.Index(fields=["tenant", "item_code"], name="idx_qcoa_ten_item"),
            models.Index(fields=["tenant", "lot_number"], name="idx_qcoa_ten_lot"),
            models.Index(fields=["tenant", "is_within_spec"], name="idx_qcoa_ten_within_spec"),
        ]

    def __str__(self):
        return f"{self.number} - CoA {self.certificate_number} (Lot {self.lot_number})"

    def get_absolute_url(self):
        return reverse("quality:certificate_of_analysis_detail", kwargs={"pk": self.pk})

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def verify_specifications(self):
        if not self.parameters_payload:
            self.is_within_spec = True
            self.variance_count = 0
            if self.status == "received":
                self.status = "verified_compliant"
            return

        variances = 0
        updated_payload = []

        for p in self.parameters_payload:
            if not isinstance(p, dict):
                continue
            item = dict(p)
            actual = item.get("actual_value")
            lsl = item.get("lsl")
            usl = item.get("usl")

            is_pass = True
            if actual is not None:
                try:
                    act_f = float(actual)
                    if not math.isfinite(act_f):
                        is_pass = False
                    else:
                        if lsl is not None and act_f < float(lsl):
                            is_pass = False
                        if usl is not None and act_f > float(usl):
                            is_pass = False
                except (ValueError, TypeError):
                    if item.get("expected") and str(actual).strip() != str(item.get("expected")).strip():
                        is_pass = False

            item["is_pass"] = is_pass
            if not is_pass:
                variances += 1
            updated_payload.append(item)

        self.parameters_payload = updated_payload
        self.variance_count = variances
        self.is_within_spec = variances == 0
        if self.status != "rejected":
            self.status = "verified_compliant" if variances == 0 else "exception_detected"
