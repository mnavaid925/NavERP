from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetComplianceAudit(TenantNumbered):
    """
    Asset Compliance Audit & Verification Cycle [ACA-].
    Manages compliance audit cycles, verification inspections, checklist execution,
    evidence gathering, and non-conformance severity tracking.
    """

    NUMBER_PREFIX = "ACA"

    AUDIT_TYPE_CHOICES = [
        ("internal", "Internal Periodic Compliance Audit"),
        ("external_regulatory", "External Statutory / Agency Inspection"),
        ("third_party_certification", "Third-Party ISO / Registrar Audit"),
        ("customer_qualification", "Customer / Supplier EHS Qualification"),
    ]

    COMPLIANCE_RATING_CHOICES = [
        ("fully_compliant", "Fully Compliant (No Findings)"),
        ("minor_deficiencies", "Substantially Compliant (Minor Deficiencies)"),
        ("major_non_conformance", "Major Non-Conformance (Action Required)"),
        ("critical_breach", "Critical Breach / Imminent Danger"),
        ("not_rated", "Not Rated / In Progress"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Audit Scheduled"),
        ("in_progress", "Audit Fieldwork In Progress"),
        ("under_review", "Audit Findings Under Review"),
        ("completed", "Audit Completed & Signed Off"),
        ("cancelled", "Audit Cancelled"),
    ]

    STATUS_CSS = {
        "scheduled": "badge-slate",
        "in_progress": "badge-info",
        "under_review": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }

    COMPLIANCE_RATING_CSS = {
        "fully_compliant": "badge-green",
        "minor_deficiencies": "badge-amber",
        "major_non_conformance": "badge-red",
        "critical_breach": "badge-red",
        "not_rated": "badge-slate",
    }

    AUDIT_TYPE_CSS = {
        "internal": "badge-info",
        "external_regulatory": "badge-red",
        "third_party_certification": "badge-green",
        "customer_qualification": "badge-slate",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="asset_compliance_audits",
    )
    title = models.CharField(
        max_length=255,
        help_text="Descriptive title of audit or statutory inspection",
    )
    framework = models.ForeignKey(
        "assets.AssetComplianceFramework",
        on_delete=models.PROTECT,
        related_name="audits",
        help_text="Governing compliance standard evaluated",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_audits",
        help_text="Subject operational plant equipment or facility",
    )
    audit_type = models.CharField(
        max_length=30,
        choices=AUDIT_TYPE_CHOICES,
        default="internal",
    )
    lead_auditor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_compliance_audits",
        help_text="Internal lead auditor or EHS compliance officer",
    )
    auditor_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_asset_audits",
        help_text="External registrar, certified audit firm, or agency inspector",
    )
    audit_date = models.DateField(default=timezone.now)
    scope_description = models.TextField(
        blank=True,
        help_text="Boundaries of audit, operating units, and evaluated physical assets",
    )
    total_checkpoints = models.PositiveIntegerField(
        default=0,
        help_text="Total evaluated checkpoints in compliance checklist",
    )
    passed_checkpoints = models.PositiveIntegerField(
        default=0,
        help_text="Checkpoints found fully conforming",
    )
    minor_findings_count = models.PositiveIntegerField(
        default=0,
        help_text="Minor deficiencies identified",
    )
    major_findings_count = models.PositiveIntegerField(
        default=0,
        help_text="Major non-conformances identified",
    )
    critical_findings_count = models.PositiveIntegerField(
        default=0,
        help_text="Critical safety breaches or imminent hazards identified",
    )
    compliance_rating = models.CharField(
        max_length=24,
        choices=COMPLIANCE_RATING_CHOICES,
        default="not_rated",
    )
    summary_findings = models.TextField(
        blank=True,
        help_text="Executive summary of findings, observations, and required remedial actions",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-audit_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_aca_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_aca_ten_stat"),
            models.Index(fields=["tenant", "audit_type"], name="idx_aca_ten_type"),
            models.Index(fields=["tenant", "compliance_rating"], name="idx_aca_ten_rate"),
            models.Index(fields=["tenant", "audit_date"], name="idx_aca_ten_adate"),
            models.Index(fields=["tenant", "framework"], name="idx_aca_ten_fw"),
        ]

    def __str__(self):
        return f"{self.title} ({self.number})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def compliance_rating_badge_class(self):
        return self.COMPLIANCE_RATING_CSS.get(self.compliance_rating, "badge-slate")

    @property
    def audit_type_badge_class(self):
        return self.AUDIT_TYPE_CSS.get(self.audit_type, "badge-slate")
