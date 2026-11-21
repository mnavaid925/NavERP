import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ComputerSystemValidation(TenantNumbered):
    NUMBER_PREFIX = "QCSV"

    GAMP_CATEGORY_CHOICES = [
        ("cat_1_infrastructure", "Category 1: Infrastructure Software (OS, DB, Network)"),
        ("cat_3_non_configured", "Category 3: Non-Configured Software (Commercial COTS)"),
        ("cat_4_configured", "Category 4: Configured Software (Standard LIMS/QMS/ERP)"),
        ("cat_5_custom", "Category 5: Custom Built Software / Bespoke Scripts"),
    ]

    GXP_IMPACT_CHOICES = [
        ("direct_gxp", "Direct GxP Impact"),
        ("indirect_gxp", "Indirect GxP Impact"),
        ("non_gxp", "Non-GxP / Business Only"),
    ]

    VALIDATION_APPROACH_CHOICES = [
        ("traditional_csv", "Traditional CSV (Rigorous Scripted Testing)"),
        ("csa_risk_based", "FDA CSA (Risk-Based & Unscripted Testing)"),
    ]

    HOSTING_MODEL_CHOICES = [
        ("cloud_saas", "Cloud SaaS (Multi-Tenant)"),
        ("cloud_dedicated", "Cloud Dedicated / Private Cloud"),
        ("on_premises", "On-Premises Bare Metal / VM"),
        ("hybrid", "Hybrid Architecture"),
        ("embedded_firmware", "Embedded Instrument Firmware"),
    ]

    TRACEABILITY_STATUS_CHOICES = [
        ("not_started", "Traceability Not Started"),
        ("drafting", "Matrix In Progress"),
        ("matrix_verified", "Traceability Matrix Verified (100%)"),
        ("gaps_identified", "Traceability Gaps Flagged"),
    ]

    STATUS_CHOICES = [
        ("inventory_only", "System Inventory Registered"),
        ("planning", "Validation Plan Approved"),
        ("in_qualification", "Qualification Testing Active"),
        ("validated_live", "Validated for Live GxP Use"),
        ("periodic_review_due", "Periodic Review Overdue"),
        ("decommissioned", "Decommissioned / Retired"),
    ]

    GAMP_CSS = {
        "cat_1_infrastructure": "badge-slate",
        "cat_3_non_configured": "badge-info",
        "cat_4_configured": "badge-green",
        "cat_5_custom": "badge-amber",
    }

    STATUS_CSS = {
        "inventory_only": "badge-slate",
        "planning": "badge-info",
        "in_qualification": "badge-amber",
        "validated_live": "badge-green",
        "periodic_review_due": "badge-red",
        "decommissioned": "badge-muted",
    }

    system_name = models.CharField(max_length=200, help_text="Commercial software product or internal application name")
    version_release = models.CharField(max_length=50, help_text="Software build or version identifier (e.g. v3.2.1)")
    vendor_name = models.CharField(max_length=150, help_text="Commercial software vendor or development provider")
    gamp_category = models.CharField(max_length=28, choices=GAMP_CATEGORY_CHOICES, default="cat_4_configured", db_index=True)
    gxp_impact = models.CharField(max_length=20, choices=GXP_IMPACT_CHOICES, default="direct_gxp", db_index=True)
    validation_approach = models.CharField(max_length=25, choices=VALIDATION_APPROACH_CHOICES, default="csa_risk_based")
    hosting_model = models.CharField(max_length=25, choices=HOSTING_MODEL_CHOICES, default="cloud_saas")

    is_part_11_compliant = models.BooleanField(default=True, help_text="21 CFR Part 11 / EU Annex 11 electronic records & e-signatures evaluated")
    requires_audit_trail = models.BooleanField(default=True, help_text="21 CFR § 11.10(e) time-stamped, tamper-evident audit trail mandated")
    has_disaster_recovery_plan = models.BooleanField(default=True, help_text="Business continuity, backup verification, and DR procedures documented")

    traceability_status = models.CharField(max_length=25, choices=TRACEABILITY_STATUS_CHOICES, default="not_started")
    urs_requirements_count = models.PositiveIntegerField(default=0, help_text="Total User Requirements Specifications (URS) verified")
    test_scripts_count = models.PositiveIntegerField(default=0, help_text="Total qualification test scripts executed (IQ/OQ/PQ)")
    deviations_found_count = models.PositiveIntegerField(default=0, help_text="Open software anomalies / bug tickets logged during validation")

    status = models.CharField(max_length=28, choices=STATUS_CHOICES, default="inventory_only", db_index=True)
    validated_date = models.DateField(null=True, blank=True, help_text="Date system was formally released for live GxP production use")
    periodic_review_frequency_months = models.PositiveIntegerField(default=24, help_text="Periodic review interval in months (typically 24-36 months)")
    last_review_date = models.DateField(null=True, blank=True, help_text="Date of last formal periodic software review")
    next_review_due = models.DateField(null=True, blank=True, db_index=True, help_text="Next scheduled periodic review deadline")

    description = models.TextField(blank=True, help_text="System purpose, functional scope, and interfaces")

    system_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_computer_systems",
        help_text="Business system owner / departmental administrator",
    )
    quality_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="qa_computer_systems",
        help_text="Quality Assurance validation lead",
    )
    validation_protocol = models.ForeignKey(
        "quality.ValidationProtocol",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="computer_system_validations",
        help_text="Associated qualification protocol",
    )
    urs_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="csv_urs_docs",
        help_text="Linked User Requirements Specification (URS)",
    )
    vsr_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="csv_vsr_docs",
        help_text="Linked Validation Summary Report (VSR)",
    )
    risk_assessment = models.ForeignKey(
        "quality.RiskAssessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="computer_system_validations",
        help_text="GxP / GAMP 5 software risk assessment",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Computer System Validation"
        verbose_name_plural = "Computer System Validations"
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcsv_ten_status"),
            models.Index(fields=["tenant", "gamp_category"], name="idx_qcsv_ten_gamp"),
            models.Index(fields=["tenant", "next_review_due"], name="idx_qcsv_ten_review_due"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcsv_ten_num_uniq"),
        ]

    def __str__(self):
        return f"{self.number} - {self.system_name} ({self.version_release})"

    @property
    def is_review_overdue(self):
        if self.next_review_due and self.status not in ("decommissioned",):
            return self.next_review_due < datetime.date.today()
        return False

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def gamp_css(self):
        return self.GAMP_CSS.get(self.gamp_category, "badge-slate")
