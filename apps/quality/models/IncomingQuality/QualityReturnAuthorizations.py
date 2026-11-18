from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.quality.models._base import TenantNumbered


class QualityReturnAuthorization(TenantNumbered):
    NUMBER_PREFIX = "QRMA"

    RETURN_REASON_CHOICES = [
        ("dimensional_oos", "Dimensional Out-of-Specification"),
        ("functional_failure", "Functional / Electrical Failure"),
        ("coa_non_compliance", "Certificate of Analysis Non-Compliance"),
        ("cosmetic_visual", "Cosmetic / Visual Defect"),
        ("wrong_material", "Wrong Material / Incorrect Grade"),
        ("packaging_damage", "Packaging Damage / Transit Breach"),
        ("contamination", "Foreign Matter / Bioburden Contamination"),
        ("expired_shelf_life", "Expired or Past Retest Shelf-Life"),
    ]

    DISPOSITION_TYPE_CHOICES = [
        ("return_for_credit", "Return for Credit / Debit Memo"),
        ("return_for_replacement", "Return for Replacement"),
        ("return_for_rework", "Return for Supplier Rework"),
        ("scrap_on_site", "Scrap on Site (Supplier Credit)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Initiation"),
        ("rma_requested", "RMA Requested from Vendor"),
        ("rma_approved", "RMA Approved by Vendor"),
        ("shipped_to_vendor", "Goods Shipped to Vendor"),
        ("received_by_vendor", "Received by Vendor"),
        ("settled_closed", "Settled & Closed"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "rma_requested": "badge-amber",
        "rma_approved": "badge-info",
        "shipped_to_vendor": "badge-info",
        "received_by_vendor": "badge-amber",
        "settled_closed": "badge-green",
        "cancelled": "badge-muted",
    }

    DISPOSITION_CSS = {
        "return_for_credit": "badge-green",
        "return_for_replacement": "badge-info",
        "return_for_rework": "badge-amber",
        "scrap_on_site": "badge-red",
    }

    inspection_lot = models.ForeignKey(
        "quality.IncomingInspectionLot",
        on_delete=models.CASCADE,
        related_name="return_authorizations",
    )
    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="quality_return_authorizations",
    )
    vendor_rma_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Vendor-issued return authorization reference",
    )
    return_reason = models.CharField(
        max_length=30,
        choices=RETURN_REASON_CHOICES,
        default="dimensional_oos",
        db_index=True,
    )
    disposition_type = models.CharField(
        max_length=25,
        choices=DISPOSITION_TYPE_CHOICES,
        default="return_for_credit",
        db_index=True,
    )
    return_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
    )
    unit_of_measure = models.CharField(max_length=20, default="EA")
    estimated_credit_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    bill_of_lading = models.CharField(max_length=100, blank=True)
    shipped_date = models.DateField(null=True, blank=True)
    vendor_receipt_date = models.DateField(null=True, blank=True)
    debit_memo_number = models.CharField(max_length=50, blank=True)
    settled_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    settlement_date = models.DateField(null=True, blank=True)
    assigned_coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coordinated_rmas",
    )
    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_authorizations",
    )
    linked_scar = models.ForeignKey(
        "quality.SupplierCorrectiveAction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_authorizations",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Quality Return Authorization"
        verbose_name_plural = "Quality Return Authorizations"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qrma_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qrma_ten_status"),
            models.Index(fields=["tenant", "supplier"], name="idx_qrma_ten_supp"),
            models.Index(fields=["tenant", "disposition_type"], name="idx_qrma_ten_disp"),
            models.Index(fields=["tenant", "return_reason"], name="idx_qrma_ten_reason"),
        ]

    def __str__(self):
        return f"{self.number} - Lot {self.inspection_lot_id}"

    def get_absolute_url(self):
        return reverse("quality:quality_return_authorization_detail", kwargs={"pk": self.pk})

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def disposition_css(self):
        return self.DISPOSITION_CSS.get(self.disposition_type, "badge-slate")
