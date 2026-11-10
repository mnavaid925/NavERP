from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetComplianceIncident(TenantNumbered):
    """
    Asset Compliance Incident, Citation & Violation [ACI-].
    Captures environmental exceedances, safety infractions, Notices of Violation (NOV),
    penalty fine settlements, root-cause investigations, and CAPA remediation workflows.
    """

    NUMBER_PREFIX = "ACI"

    INCIDENT_TYPE_CHOICES = [
        ("notice_of_violation", "Formal Notice of Violation (NOV)"),
        ("regulatory_citation", "Statutory Agency Citation"),
        ("emissions_exceedance", "Air / Water Discharge Exceedance"),
        ("unpermitted_discharge", "Unpermitted Chemical / Fluid Spill"),
        ("safety_infraction", "OSHA Safety Violation / Guarding Issue"),
        ("failed_inspection", "Failed Regulatory Inspection"),
        ("internal_audit_breach", "Internal Compliance Audit Failure"),
    ]

    SEVERITY_CHOICES = [
        ("de_minimis", "De Minimis (Administrative / Advisory)"),
        ("other_than_serious", "Other-Than-Serious (Low Direct Impact)"),
        ("serious", "Serious (Substantial Probability of Harm)"),
        ("repeat", "Repeat Infraction"),
        ("willful", "Willful / Intentional Non-Compliance"),
        ("imminent_danger", "Imminent Danger / Stop-Work Order"),
    ]

    ROOT_CAUSE_CHOICES = [
        ("mechanical_failure", "Equipment / Mechanical Component Failure"),
        ("human_error", "Operator Error / Procedural Drift"),
        ("inadequate_procedure", "Inadequate SOP / Training Deficiency"),
        ("lack_of_maintenance", "Deferred Maintenance / Missed Inspection"),
        ("measurement_error", "Instrumentation / Sensor Calibration Error"),
        ("external_factor", "Extreme Weather / External Contractor Factor"),
    ]

    STATUS_CHOICES = [
        ("open", "Open (Reported)"),
        ("under_investigation", "Under Root Cause Investigation"),
        ("capa_in_progress", "CAPA Remediation In Progress"),
        ("under_agency_review", "CAPA Submitted for Agency Review"),
        ("appealed", "Formal Administrative Appeal Filed"),
        ("resolved", "Resolved (CAPA Verified)"),
        ("closed", "Closed & Settled"),
    ]

    STATUS_CSS = {
        "open": "badge-red",
        "under_investigation": "badge-amber",
        "capa_in_progress": "badge-info",
        "under_agency_review": "badge-amber",
        "appealed": "badge-slate",
        "resolved": "badge-green",
        "closed": "badge-muted",
    }

    SEVERITY_CSS = {
        "de_minimis": "badge-slate",
        "other_than_serious": "badge-info",
        "serious": "badge-amber",
        "repeat": "badge-red",
        "willful": "badge-red",
        "imminent_danger": "badge-red",
    }

    INCIDENT_TYPE_CSS = {
        "notice_of_violation": "badge-red",
        "regulatory_citation": "badge-red",
        "emissions_exceedance": "badge-amber",
        "unpermitted_discharge": "badge-red",
        "safety_infraction": "badge-amber",
        "failed_inspection": "badge-info",
        "internal_audit_breach": "badge-slate",
    }

    ROOT_CAUSE_CSS = {
        "mechanical_failure": "badge-amber",
        "human_error": "badge-slate",
        "inadequate_procedure": "badge-info",
        "lack_of_maintenance": "badge-red",
        "measurement_error": "badge-slate",
        "external_factor": "badge-muted",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="compliance_incidents",
    )
    title = models.CharField(
        max_length=255,
        help_text="Brief summary of violation or non-compliance event",
    )
    incident_date = models.DateTimeField(
        default=timezone.now,
        help_text="Date and time violation occurred",
    )
    discovery_date = models.DateField(
        default=timezone.now,
        help_text="Date cited or internally discovered",
    )
    incident_type = models.CharField(
        max_length=30,
        choices=INCIDENT_TYPE_CHOICES,
        default="safety_infraction",
    )
    severity = models.CharField(
        max_length=24,
        choices=SEVERITY_CHOICES,
        default="serious",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_incidents",
        help_text="Cited operational equipment or plant asset",
    )
    permit = models.ForeignKey(
        "assets.AssetPermitLicense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
        help_text="Violated permit or operating certificate",
    )
    audit = models.ForeignKey(
        "assets.AssetComplianceAudit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
        help_text="Source audit that identified non-compliance",
    )
    enforcement_agency = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cited_compliance_incidents",
        help_text="Issuing regulatory enforcement authority",
    )
    citation_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Statutory docket, citation, or ticket number",
    )
    fine_assessed = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Monetary fine or penalty assessed by regulator",
    )
    fine_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Penalty amount paid to date",
    )
    fine_payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Settlement payment confirmation date",
    )
    root_cause = models.CharField(
        max_length=30,
        choices=ROOT_CAUSE_CHOICES,
        default="mechanical_failure",
    )
    root_cause_analysis = models.TextField(
        blank=True,
        help_text="Detailed root cause investigation analysis",
    )
    corrective_action_plan = models.TextField(
        blank=True,
        help_text="Mandated CAPA remediation and prevention plan",
    )
    assigned_investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investigated_compliance_incidents",
        help_text="Lead investigator or remediation manager",
    )
    target_resolution_date = models.DateField(null=True, blank=True)
    actual_resolution_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="open",
    )

    class Meta:
        ordering = ["-incident_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_aci_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_aci_ten_stat"),
            models.Index(fields=["tenant", "severity"], name="idx_aci_ten_sev"),
            models.Index(fields=["tenant", "incident_type"], name="idx_aci_ten_type"),
            models.Index(fields=["tenant", "incident_date"], name="idx_aci_ten_idate"),
            models.Index(fields=["tenant", "asset"], name="idx_aci_ten_ast"),
        ]

    def __str__(self):
        return f"{self.title} ({self.number})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def severity_badge_class(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def incident_type_badge_class(self):
        return self.INCIDENT_TYPE_CSS.get(self.incident_type, "badge-slate")

    @property
    def root_cause_badge_class(self):
        return self.ROOT_CAUSE_CSS.get(self.root_cause, "badge-slate")

    @property
    def outstanding_fine(self):
        return max(Decimal("0.00"), self.fine_assessed - self.fine_paid)

    @property
    def outstanding_penalty(self):
        return self.outstanding_fine

    @property
    def has_outstanding_fine(self):
        return self.outstanding_fine > Decimal("0.00")

    @property
    def is_resolved(self):
        return self.status in ["resolved", "closed"]

