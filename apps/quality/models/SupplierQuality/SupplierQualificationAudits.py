from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class SupplierQualificationAudit(TenantNumbered):
    NUMBER_PREFIX = "QSQA"

    ASSESSMENT_TYPE_CHOICES = [
        ("initial_qualification", "Initial Qualification"),
        ("periodic_reaudit", "Periodic Re-Audit"),
        ("for_cause", "For-Cause Audit"),
        ("certification_review", "Certification Review"),
        ("quality_agreement_review", "Quality Agreement Review"),
    ]

    CRITICALITY_TIER_CHOICES = [
        ("critical", "Critical (Direct Product Contact / High Risk)"),
        ("major", "Major (Key Component / Service)"),
        ("minor", "Minor (Standard Catalog / Low Risk)"),
        ("indirect", "Indirect / Non-Product Services"),
    ]

    AUDIT_METHOD_CHOICES = [
        ("on_site", "On-Site Facility Audit"),
        ("desktop_survey", "Desktop / Questionnaire Survey"),
        ("third_party_iso", "Third-Party ISO / Registrar Audit"),
        ("virtual", "Virtual / Remote Audit"),
    ]

    QUALIFICATION_STATUS_CHOICES = [
        ("under_evaluation", "Under Evaluation"),
        ("approved", "Approved (Active AVL)"),
        ("conditional", "Conditionally Approved"),
        ("suspended", "Suspended Hold"),
        ("disqualified", "Disqualified"),
    ]

    AUDIT_RESULT_CHOICES = [
        ("pending", "Pending Assessment"),
        ("passed", "Passed / Fully Qualified"),
        ("passed_with_capa", "Passed with Corrective Actions"),
        ("failed", "Failed / Unacceptable"),
        ("exempt", "Audit Exempt"),
    ]

    STATUS_CSS = {
        "under_evaluation": "badge-amber",
        "approved": "badge-green",
        "conditional": "badge-info",
        "suspended": "badge-red",
        "disqualified": "badge-muted",
    }

    TIER_CSS = {
        "critical": "badge-red",
        "major": "badge-amber",
        "minor": "badge-slate",
        "indirect": "badge-muted",
    }

    RESULT_CSS = {
        "pending": "badge-slate",
        "passed": "badge-green",
        "passed_with_capa": "badge-amber",
        "failed": "badge-red",
        "exempt": "badge-muted",
    }

    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="quality_qualifications",
        help_text="Supplier or vendor party record",
    )
    assessment_type = models.CharField(
        max_length=35,
        choices=ASSESSMENT_TYPE_CHOICES,
        default="initial_qualification",
        db_index=True,
    )
    criticality_tier = models.CharField(
        max_length=20,
        choices=CRITICALITY_TIER_CHOICES,
        default="major",
        db_index=True,
    )
    audit_method = models.CharField(
        max_length=25,
        choices=AUDIT_METHOD_CHOICES,
        default="on_site",
        db_index=True,
    )
    qualification_status = models.CharField(
        max_length=25,
        choices=QUALIFICATION_STATUS_CHOICES,
        default="under_evaluation",
        db_index=True,
    )
    scope_commodities = models.TextField(
        blank=True,
        help_text="Approved materials, services, or part categories",
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Audit compliance score 0-100%",
    )
    audit_result = models.CharField(
        max_length=25,
        choices=AUDIT_RESULT_CHOICES,
        default="pending",
        db_index=True,
    )
    critical_findings = models.PositiveIntegerField(default=0)
    major_findings = models.PositiveIntegerField(default=0)
    minor_findings = models.PositiveIntegerField(default=0)
    lead_auditor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_supplier_audits",
    )
    audit_date = models.DateField(null=True, blank=True)
    qualified_date = models.DateField(null=True, blank=True)
    next_audit_due_date = models.DateField(null=True, blank=True)
    certificate_expiry_date = models.DateField(null=True, blank=True)
    dock_to_stock_eligible = models.BooleanField(
        default=False,
        help_text="Certified supplier authorized to bypass receiving inspection",
    )
    skip_lot_approved = models.BooleanField(
        default=False,
        help_text="Approved for reduced inspection frequency",
    )
    requires_coa = models.BooleanField(
        default=True,
        help_text="Certificate of Analysis mandatory on shipments",
    )
    quality_agreement = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_qualifications",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Supplier Qualification & Audit"
        verbose_name_plural = "Supplier Qualification & Audits"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qsqa_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "qualification_status"], name="idx_qsqa_ten_status"),
            models.Index(fields=["tenant", "supplier"], name="idx_qsqa_ten_supp"),
            models.Index(fields=["tenant", "criticality_tier"], name="idx_qsqa_ten_crit"),
            models.Index(fields=["tenant", "audit_result"], name="idx_qsqa_ten_res"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qsqa_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.supplier.name} ({self.get_qualification_status_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.qualification_status, "badge-slate")

    @property
    def tier_css(self):
        return self.TIER_CSS.get(self.criticality_tier, "badge-slate")

    @property
    def result_css(self):
        return self.RESULT_CSS.get(self.audit_result, "badge-slate")

    @property
    def total_findings(self):
        return (self.critical_findings or 0) + (self.major_findings or 0) + (self.minor_findings or 0)

    @property
    def is_expired(self):
        if self.certificate_expiry_date and self.certificate_expiry_date < timezone.now().date():
            return True
        return False

    @property
    def is_audit_overdue(self):
        if self.next_audit_due_date and self.next_audit_due_date < timezone.now().date():
            return True
        return False
