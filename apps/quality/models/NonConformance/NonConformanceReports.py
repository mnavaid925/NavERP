from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class NonConformanceReport(TenantNumbered):
    NUMBER_PREFIX = "QNCR"

    SOURCE_TYPE_CHOICES = (
        ("incoming", "Incoming Inspection"),
        ("in_process", "In-Process Production"),
        ("final_inspection", "Final Product Inspection"),
        ("customer_return", "Customer Return / RMA"),
        ("internal_audit", "Internal Quality Audit"),
        ("supplier", "Supplier Facility Issue"),
    )

    CATEGORY_CHOICES = (
        ("material", "Raw Material / Component Defect"),
        ("process", "Manufacturing Process Deviation"),
        ("product", "Finished Product Out-of-Spec"),
        ("supplier", "Supplier Quality Issue"),
        ("facility", "Facility / Environmental Excursion"),
        ("documentation", "Documentation / Labeling Error"),
    )

    SEVERITY_CHOICES = (
        ("minor", "Minor (Low Risk)"),
        ("major", "Major (Quality Impact)"),
        ("critical", "Critical (Safety / Regulatory)"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft / Triage"),
        ("containment_active", "Containment Active"),
        ("under_investigation", "Under Investigation"),
        ("mrb_review", "MRB Review"),
        ("disposition_approved", "Disposition Approved"),
        ("rework_in_progress", "Rework in Progress"),
        ("closed", "Closed / Verified"),
        ("voided", "Voided / Cancelled"),
    )

    SOURCE_TYPE_CSS = {
        "incoming": "badge-info",
        "in_process": "badge-amber",
        "final_inspection": "badge-info",
        "customer_return": "badge-red",
        "internal_audit": "badge-slate",
        "supplier": "badge-amber",
    }

    CATEGORY_CSS = {
        "material": "badge-amber",
        "process": "badge-info",
        "product": "badge-red",
        "supplier": "badge-amber",
        "facility": "badge-slate",
        "documentation": "badge-info",
    }

    SEVERITY_CSS = {
        "minor": "badge-slate",
        "major": "badge-amber",
        "critical": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "containment_active": "badge-red",
        "under_investigation": "badge-amber",
        "mrb_review": "badge-info",
        "disposition_approved": "badge-info",
        "rework_in_progress": "badge-amber",
        "closed": "badge-green",
        "voided": "badge-muted",
    }

    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Detailed description of the defect or non-conformance event")
    source_type = models.CharField(max_length=24, choices=SOURCE_TYPE_CHOICES, default="in_process", db_index=True)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default="material", db_index=True)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="major", db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="draft", db_index=True)
    defect_code = models.CharField(max_length=64, blank=True, help_text="Defect code (e.g., DIM-OOS, CONTAM, PKG-FAIL)")
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="non_conformance_reports",
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_ncrs",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_ncrs",
    )
    supplier_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_ncrs",
        help_text="Vendor or external supplier",
    )
    affected_item_code = models.CharField(max_length=100, blank=True, help_text="SKU or part number affected")
    affected_item_name = models.CharField(max_length=255, blank=True, help_text="Item name or description")
    lot_serial_numbers = models.CharField(max_length=255, blank=True, help_text="Batch, lot, or serial numbers")
    quantity_inspected = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    quantity_nonconforming = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unit_of_measure = models.CharField(max_length=32, default="EA", blank=True)
    estimated_financial_loss = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    immediate_containment_required = models.BooleanField(
        default=True,
        help_text="Immediate physical quarantine or stop-shipment required",
    )
    capa_required = models.BooleanField(
        default=False,
        help_text="Critical or recurring defect requiring CAPA investigation",
    )
    capa_investigation = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originating_ncrs",
        help_text="Linked CAPA record",
    )
    target_resolution_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_ncrs",
    )
    closure_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Non-Conformance Report"
        verbose_name_plural = "Non-Conformance Reports"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qncr_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qncr_ten_status"),
            models.Index(fields=["tenant", "severity"], name="idx_qncr_ten_severity"),
            models.Index(fields=["tenant", "source_type"], name="idx_qncr_ten_src_type"),
            models.Index(fields=["tenant", "category"], name="idx_qncr_ten_category"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qncr_ten_created"),
        ]

    def __str__(self):
        return f"{self.number or 'Draft'} - {self.title}"

    @property
    def source_type_badge(self):
        return self.SOURCE_TYPE_CSS.get(self.source_type, "badge-slate")

    @property
    def category_badge(self):
        return self.CATEGORY_CSS.get(self.category, "badge-slate")

    @property
    def severity_badge(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def is_closed(self):
        return self.status in ("closed", "voided")

    @property
    def is_overdue(self):
        if self.target_resolution_date and not self.is_closed:
            return self.target_resolution_date < timezone.now().date()
        return False

    @property
    def containments_count(self):
        return self.containment_records.count()

    @property
    def active_containments_count(self):
        return self.containment_records.filter(status="active").count()

    @property
    def mrb_dispositions_count(self):
        return self.mrb_dispositions.count()

    @property
    def deviations_count(self):
        return self.process_deviations.count()
