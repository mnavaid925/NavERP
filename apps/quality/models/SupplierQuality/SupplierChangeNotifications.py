from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class SupplierChangeNotification(TenantNumbered):
    NUMBER_PREFIX = "QSCN"

    CHANGE_CATEGORY_CHOICES = [
        ("raw_material", "Raw Material / Component Change"),
        ("manufacturing_process", "Manufacturing Process / Line Relocation"),
        ("facility_location", "Facility / Manufacturing Site Change"),
        ("tooling_equipment", "Tooling / Mold / Machine Replacement"),
        ("packaging_labeling", "Packaging / Labeling Specification"),
        ("specification_testing", "Testing Method / Specification Change"),
        ("sub_tier_supplier", "Sub-Tier Supplier / Source Change"),
        ("other", "Other Operational Change"),
    ]

    RISK_LEVEL_CHOICES = [
        ("level_1_minor", "Level 1: Minor (Low Risk / Notification Only)"),
        ("level_2_moderate", "Level 2: Moderate (Technical Review Required)"),
        ("level_3_major", "Level 3: Major (Re-qualification / Validation Mandatory)"),
    ]

    STATUS_CHOICES = [
        ("received", "Received / Logged"),
        ("under_assessment", "Under Assessment"),
        ("technical_evaluation", "Technical Evaluation"),
        ("samples_pending", "Samples / Test Pending"),
        ("approved", "Approved"),
        ("conditional_approval", "Conditionally Approved"),
        ("rejected", "Rejected"),
        ("implemented", "Implemented / Live"),
    ]

    DISPOSITION_CHOICES = [
        ("pending", "Pending Disposition"),
        ("approved", "Approved (Proceed)"),
        ("conditional_approval", "Conditional Approval (With Caveats)"),
        ("rejected", "Rejected (Change Disallowed)"),
    ]

    CHANGE_CATEGORY_CSS = {
        "raw_material": "badge-red",
        "manufacturing_process": "badge-amber",
        "facility_location": "badge-info",
        "tooling_equipment": "badge-slate",
        "packaging_labeling": "badge-slate",
        "specification_testing": "badge-amber",
        "sub_tier_supplier": "badge-amber",
        "other": "badge-muted",
    }

    RISK_LEVEL_CSS = {
        "level_1_minor": "badge-slate",
        "level_2_moderate": "badge-amber",
        "level_3_major": "badge-red",
    }

    STATUS_CSS = {
        "received": "badge-slate",
        "under_assessment": "badge-amber",
        "technical_evaluation": "badge-info",
        "samples_pending": "badge-info",
        "approved": "badge-green",
        "conditional_approval": "badge-amber",
        "rejected": "badge-red",
        "implemented": "badge-green",
    }

    DISPOSITION_CSS = {
        "pending": "badge-slate",
        "approved": "badge-green",
        "conditional_approval": "badge-amber",
        "rejected": "badge-red",
    }

    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="quality_scns",
        help_text="Supplier notifying the change",
    )
    title = models.CharField(max_length=255)
    supplier_scn_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Supplier internal change request / PCN number",
    )
    change_category = models.CharField(
        max_length=30,
        choices=CHANGE_CATEGORY_CHOICES,
        default="raw_material",
        db_index=True,
    )
    risk_level = models.CharField(
        max_length=25,
        choices=RISK_LEVEL_CHOICES,
        default="level_2_moderate",
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="received",
        db_index=True,
    )
    description = models.TextField(help_text="Detailed description of proposed process or material change")
    proposed_effective_date = models.DateField(null=True, blank=True)
    first_affected_lot = models.CharField(max_length=100, blank=True)

    # Stand-in fields for unbuilt Module 5 masters
    affected_item_code = models.CharField(max_length=100, blank=True)
    affected_item_name = models.CharField(max_length=255, blank=True)

    # Form-Fit-Function (FFF) & Impact Evaluation Checklist
    affects_form_fit_function = models.BooleanField(
        default=False,
        help_text="Change impacts physical form, fit, or functional interchangeability",
    )
    requires_requalification = models.BooleanField(
        default=False,
        help_text="Mandates facility audit or formal vendor re-qualification",
    )
    requires_design_change = models.BooleanField(
        default=False,
        help_text="Triggers medical device design history file (DHF) change order",
    )
    requires_regulatory_filing = models.BooleanField(
        default=False,
        help_text="Mandates regulatory notification or submission amendment",
    )
    requires_customer_notification = models.BooleanField(
        default=False,
        help_text="Commercial agreements require customer prior notice or consent",
    )
    samples_required = models.BooleanField(
        default=False,
        help_text="Pre-production validation samples requested from supplier",
    )
    impact_assessment_notes = models.TextField(blank=True)

    # Verified Sibling FKs
    design_project = models.ForeignKey(
        "quality.DesignProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_scns",
    )
    requalification_audit = models.ForeignKey(
        "quality.SupplierQualificationAudit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_notifications",
    )

    # Disposition & Governance
    disposition = models.CharField(
        max_length=30,
        choices=DISPOSITION_CHOICES,
        default="pending",
        db_index=True,
    )
    disposition_notes = models.TextField(blank=True)
    disposition_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_scns",
    )
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_scns",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Supplier Change Notification (SCN)"
        verbose_name_plural = "Supplier Change Notifications (SCN)"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qscn_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qscn_ten_status"),
            models.Index(fields=["tenant", "supplier"], name="idx_qscn_ten_supp"),
            models.Index(fields=["tenant", "risk_level"], name="idx_qscn_ten_risk"),
            models.Index(fields=["tenant", "change_category"], name="idx_qscn_ten_cat"),
            models.Index(fields=["tenant", "disposition"], name="idx_qscn_ten_disp"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qscn_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.supplier.name}: {self.title}"

    @property
    def category_css(self):
        return self.CHANGE_CATEGORY_CSS.get(self.change_category, "badge-slate")

    @property
    def risk_css(self):
        return self.RISK_LEVEL_CSS.get(self.risk_level, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def disposition_css(self):
        return self.DISPOSITION_CSS.get(self.disposition, "badge-slate")

    @property
    def has_critical_impact(self):
        return (
            self.affects_form_fit_function
            or self.requires_requalification
            or self.requires_regulatory_filing
        )
