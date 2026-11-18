from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class SupplierCorrectiveAction(TenantNumbered):
    NUMBER_PREFIX = "QSCA"

    SEVERITY_CHOICES = [
        ("minor", "Minor (Documentation / Non-Critical)"),
        ("major", "Major (Out of Spec / Functional Defect)"),
        ("critical", "Critical (Safety / Regulatory / Stop-Ship)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued to Vendor"),
        ("containment_submitted", "Containment Submitted"),
        ("rca_submitted", "RCA Submitted"),
        ("action_plan_approved", "Action Plan Approved"),
        ("implemented", "Actions Implemented"),
        ("effectiveness_verified", "Effectiveness Verified"),
        ("closed", "Closed / Resolved"),
        ("cancelled", "Cancelled / Voided"),
    ]

    ROOT_CAUSE_CATEGORY_CHOICES = [
        ("raw_material", "Raw Material Quality"),
        ("process_parameter", "Manufacturing Process Parameter"),
        ("tooling_equipment", "Tooling / Machine Wear"),
        ("operator_training", "Operator / Workmanship Error"),
        ("packaging_handling", "Packaging / Transit Damage"),
        ("sub_tier_supplier", "Sub-Tier Supplier Defect"),
        ("other", "Other / External Factor"),
    ]

    SEVERITY_CSS = {
        "minor": "badge-slate",
        "major": "badge-amber",
        "critical": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "issued": "badge-amber",
        "containment_submitted": "badge-info",
        "rca_submitted": "badge-info",
        "action_plan_approved": "badge-info",
        "implemented": "badge-info",
        "effectiveness_verified": "badge-green",
        "closed": "badge-green",
        "cancelled": "badge-muted",
    }

    ROOT_CAUSE_CATEGORY_CSS = {
        "raw_material": "badge-red",
        "process_parameter": "badge-amber",
        "tooling_equipment": "badge-slate",
        "operator_training": "badge-info",
        "packaging_handling": "badge-slate",
        "sub_tier_supplier": "badge-amber",
        "other": "badge-muted",
    }

    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="quality_scars",
        help_text="Supplier issued with corrective action",
    )
    title = models.CharField(max_length=255)
    severity = models.CharField(
        max_length=15,
        choices=SEVERITY_CHOICES,
        default="major",
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    defect_summary = models.TextField(help_text="Detailed description of defect or non-conformance")

    # Stand-in fields for unbuilt Module 5 masters
    affected_item_code = models.CharField(max_length=100, blank=True, help_text="Item SKU or part number")
    affected_item_name = models.CharField(max_length=255, blank=True, help_text="Part name or component title")
    affected_lots = models.CharField(max_length=255, blank=True, help_text="Impacted vendor batch or lot numbers")

    # Verified Cross-Module SCM / Quality Links
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_scars",
    )
    non_conformance = models.ForeignKey(
        "scm.NonConformance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_scars",
    )
    qualification_audit = models.ForeignKey(
        "quality.SupplierQualificationAudit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_scars",
    )
    internal_capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_scars",
    )

    issued_date = models.DateField(null=True, blank=True)
    response_due_date = models.DateField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_scars",
    )

    # 1. Emergency Containment (24-48h)
    containment_action = models.TextField(
        blank=True,
        help_text="Immediate quarantine, sorting, and stop-ship containment actions taken",
    )
    containment_due_date = models.DateField(null=True, blank=True)
    containment_verified_at = models.DateField(null=True, blank=True)

    # 2. Root Cause Analysis (5 Whys / Ishikawa)
    root_cause_summary = models.TextField(blank=True)
    root_cause_category = models.CharField(
        max_length=30,
        choices=ROOT_CAUSE_CATEGORY_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    vendor_investigation_details = models.TextField(
        blank=True,
        help_text="Vendor 5 Whys or Fishbone investigation details",
    )

    # 3. Corrective & Preventive Action Plan
    corrective_action_plan = models.TextField(
        blank=True,
        help_text="Direct action to eliminate root cause and prevent recurrence",
    )
    preventive_action_plan = models.TextField(
        blank=True,
        help_text="Systemic improvements across similar processes/products",
    )
    implementation_due_date = models.DateField(null=True, blank=True)
    implemented_at = models.DateField(null=True, blank=True)

    # 4. Effectiveness Verification
    effectiveness_due_date = models.DateField(null=True, blank=True)
    effectiveness_method = models.CharField(
        max_length=255,
        blank=True,
        help_text="Sampling or audit method used to prove non-recurrence (e.g. Next 3 consecutive zero-defect lots)",
    )
    effectiveness_results = models.TextField(blank=True)
    is_effective = models.BooleanField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_scars",
    )
    closed_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Supplier Corrective Action (SCAR)"
        verbose_name_plural = "Supplier Corrective Actions (SCAR)"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qsca_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qsca_ten_status"),
            models.Index(fields=["tenant", "supplier"], name="idx_qsca_ten_supp"),
            models.Index(fields=["tenant", "severity"], name="idx_qsca_ten_sev"),
            models.Index(fields=["tenant", "root_cause_category"], name="idx_qsca_ten_cat"),
            models.Index(fields=["tenant", "response_due_date"], name="idx_qsca_ten_due"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qsca_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.supplier.name}: {self.title}"

    @property
    def severity_css(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def category_css(self):
        return self.ROOT_CAUSE_CATEGORY_CSS.get(self.root_cause_category, "badge-slate")

    @property
    def is_overdue(self):
        if self.status in ("closed", "cancelled"):
            return False
        if self.response_due_date and self.response_due_date < timezone.now().date():
            return True
        return False
