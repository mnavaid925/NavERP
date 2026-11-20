from datetime import date

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class QualityAudit(TenantNumbered):
    NUMBER_PREFIX = "QAUD"

    AUDIT_TYPE_CHOICES = (
        ("internal_system", "Internal Quality System Audit"),
        ("internal_process", "Manufacturing / Process Audit"),
        ("internal_product", "Product Quality Audit"),
        ("supplier_qualification", "Supplier Quality Audit"),
        ("regulatory_fda", "FDA Regulatory Inspection"),
        ("certification_notified_body", "ISO / Notified Body Audit"),
        ("customer_audit", "Customer / Client Quality Audit"),
        ("special_for_cause", "Special / For-Cause Investigation Audit"),
    )

    AUDIT_METHOD_CHOICES = (
        ("on_site", "On-Site Audit"),
        ("remote_virtual", "Remote / Virtual Audit"),
        ("hybrid", "Hybrid Audit"),
        ("desk_audit", "Desk / Off-Site Document Review"),
    )

    STANDARD_FRAMEWORK_CHOICES = (
        ("iso_9001_2015", "ISO 9001:2015"),
        ("iso_13485_2016", "ISO 13485:2016 (Medical Devices)"),
        ("iatf_16949", "IATF 16949 (Automotive)"),
        ("fda_21cfr820_qmsr", "FDA 21 CFR 820 / QMSR"),
        ("eu_mdr_2017_745", "EU MDR 2017/745"),
        ("gmp_21cfr211", "cGMP 21 CFR 211 (Pharma)"),
        ("as9100d", "AS9100D (Aerospace)"),
        ("multiple_frameworks", "Multiple Frameworks / Comprehensive"),
        ("internal_sop", "Internal Quality SOPs"),
    )

    STATUS_CHOICES = (
        ("scheduled", "Scheduled"),
        ("in_preparation", "In Preparation"),
        ("in_progress", "In Progress / Fieldwork"),
        ("reporting", "Reporting & Evaluation"),
        ("capa_pending", "CAPA Follow-Up Pending"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    )

    OUTCOME_CHOICES = (
        ("pending", "Assessment Pending"),
        ("conforming", "Conforming (No Deficiencies)"),
        ("minor_findings", "Minor Deficiencies Only"),
        ("major_findings", "Major Deficiencies Identified"),
        ("critical_non_conformance", "Critical Non-Conformance"),
        ("passed", "Passed / Satisfactory"),
        ("conditional_pass", "Conditional Approval"),
        ("failed", "Failed / Unsatisfactory"),
    )

    AUDIT_TYPE_CSS = {
        "internal_system": "badge-info",
        "internal_process": "badge-info",
        "internal_product": "badge-info",
        "supplier_qualification": "badge-slate",
        "regulatory_fda": "badge-red",
        "certification_notified_body": "badge-amber",
        "customer_audit": "badge-slate",
        "special_for_cause": "badge-red",
    }

    AUDIT_METHOD_CSS = {
        "on_site": "badge-info",
        "remote_virtual": "badge-slate",
        "hybrid": "badge-amber",
        "desk_audit": "badge-muted",
    }

    STATUS_CSS = {
        "scheduled": "badge-slate",
        "in_preparation": "badge-info",
        "in_progress": "badge-amber",
        "reporting": "badge-info",
        "capa_pending": "badge-amber",
        "closed": "badge-green",
        "cancelled": "badge-red",
    }

    OUTCOME_CSS = {
        "pending": "badge-muted",
        "conforming": "badge-green",
        "minor_findings": "badge-amber",
        "major_findings": "badge-red",
        "critical_non_conformance": "badge-red",
        "passed": "badge-green",
        "conditional_pass": "badge-amber",
        "failed": "badge-red",
    }

    program = models.ForeignKey(
        "quality.AuditProgram",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audits",
        help_text="Parent audit program (nullable for ad-hoc / unannounced audits)",
    )
    title = models.CharField(max_length=255, help_text="Audit title e.g. ISO 13485 Internal Audit - Design & Document Control")
    audit_type = models.CharField(max_length=40, choices=AUDIT_TYPE_CHOICES, default="internal_system", db_index=True)
    audit_method = models.CharField(max_length=24, choices=AUDIT_METHOD_CHOICES, default="on_site", db_index=True)
    standard_framework = models.CharField(max_length=32, choices=STANDARD_FRAMEWORK_CHOICES, default="iso_13485_2016", db_index=True)

    target_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audited_org_units",
        help_text="Audited internal plant, department, or business unit",
    )
    external_entity = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_quality_audits",
        help_text="External supplier, registrar, or regulatory agency audited/auditing",
    )

    lead_auditor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="led_quality_audits",
    )
    auditee_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_quality_audits",
    )
    audit_checklist_sop = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referenced_in_audits",
        help_text="Governing audit protocol, SOP, or checklist document",
    )

    planned_start_date = models.DateField(db_index=True)
    planned_end_date = models.DateField()
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)

    scope_objectives = models.TextField(help_text="Detailed scope, processes evaluated, and criteria")
    product_scope = models.CharField(max_length=255, blank=True, help_text="Product family or device name evaluated (Module 5 unbuilt item stand-in)")
    lot_number_sampled = models.CharField(max_length=100, blank=True, help_text="Sampled production lot / batch number (Module 5 unbuilt lot stand-in)")

    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="scheduled", db_index=True)
    outcome = models.CharField(max_length=36, choices=OUTCOME_CHOICES, default="pending", db_index=True)

    executive_summary = models.TextField(blank=True, help_text="Summary of observations, strengths, and leadership conclusion")
    report_published_date = models.DateField(null=True, blank=True)

    total_findings_count = models.PositiveIntegerField(default=0)
    critical_findings_count = models.PositiveIntegerField(default=0)
    major_findings_count = models.PositiveIntegerField(default=0)
    minor_findings_count = models.PositiveIntegerField(default=0)
    ofi_findings_count = models.PositiveIntegerField(default=0)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-planned_start_date", "-created_at"]
        verbose_name = "Quality Audit"
        verbose_name_plural = "Quality Audits"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qaud_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qaud_ten_status"),
            models.Index(fields=["tenant", "audit_type"], name="idx_qaud_ten_type"),
            models.Index(fields=["tenant", "outcome"], name="idx_qaud_ten_outcome"),
            models.Index(fields=["tenant", "planned_start_date"], name="idx_qaud_ten_pstart"),
            models.Index(fields=["tenant", "program"], name="idx_qaud_ten_prog"),
            models.Index(fields=["tenant", "target_org_unit"], name="idx_qaud_ten_unit"),
            models.Index(fields=["tenant", "lead_auditor"], name="idx_qaud_ten_auditor"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qaud_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def is_overdue(self):
        if self.status in ("closed", "cancelled"):
            return False
        return date.today() > self.planned_end_date

    @property
    def days_open(self):
        start = self.actual_start_date or self.planned_start_date
        end = self.actual_end_date or date.today()
        if start and end >= start:
            return (end - start).days
        return 0

    @property
    def open_findings_count(self):
        if hasattr(self, "annotated_open_findings"):
            return self.annotated_open_findings
        return self.findings.exclude(status="closed").count()

    def sync_findings_counts(self):
        aggs = self.findings.aggregate(
            total=models.Count("id"),
            critical=models.Count("id", filter=models.Q(severity="critical")),
            major=models.Count("id", filter=models.Q(severity="major")),
            minor=models.Count("id", filter=models.Q(severity="minor")),
            ofi=models.Count("id", filter=models.Q(severity="observation_ofi")),
        )
        self.total_findings_count = aggs["total"]
        self.critical_findings_count = aggs["critical"]
        self.major_findings_count = aggs["major"]
        self.minor_findings_count = aggs["minor"]
        self.ofi_findings_count = aggs["ofi"]
        self.save(update_fields=[
            "total_findings_count",
            "critical_findings_count",
            "major_findings_count",
            "minor_findings_count",
            "ofi_findings_count",
            "updated_at",
        ])
