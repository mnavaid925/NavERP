from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class CapaInvestigation(TenantNumbered):
    NUMBER_PREFIX = "QCAP"

    ACTION_TYPE_CHOICES = (
        ("corrective", "Corrective Action (Address Recurrence)"),
        ("preventive", "Preventive Action (Address Potential Occurrence)"),
    )

    SOURCE_TYPE_CHOICES = (
        ("ncr", "Non-Conformance Report (NCR)"),
        ("complaint", "Customer Complaint"),
        ("internal_audit", "Internal Audit Finding"),
        ("external_audit", "External Regulatory Audit"),
        ("deviation", "Process Deviation"),
        ("risk_assessment", "Risk Assessment / FMEA Trigger"),
        ("management_review", "Management Review Action"),
        ("other", "Other Operational Source"),
    )

    RISK_PRIORITY_CHOICES = (
        ("low", "Low Priority"),
        ("medium", "Medium Priority"),
        ("high", "High Priority"),
        ("critical", "Critical - Patient/Product Safety"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft / Triage"),
        ("under_investigation", "Under Investigation"),
        ("rca_in_progress", "RCA in Progress"),
        ("action_plan_dev", "Action Plan Development"),
        ("action_implementation", "Action Implementation"),
        ("effectiveness_review", "Effectiveness Review"),
        ("closed", "Closed / Verified"),
        ("voided", "Voided / Cancelled"),
    )

    ACTION_TYPE_CSS = {
        "corrective": "badge-info",
        "preventive": "badge-slate",
    }

    SOURCE_TYPE_CSS = {
        "ncr": "badge-amber",
        "complaint": "badge-red",
        "internal_audit": "badge-info",
        "external_audit": "badge-red",
        "deviation": "badge-amber",
        "risk_assessment": "badge-slate",
        "management_review": "badge-info",
        "other": "badge-slate",
    }

    RISK_PRIORITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_investigation": "badge-info",
        "rca_in_progress": "badge-amber",
        "action_plan_dev": "badge-amber",
        "action_implementation": "badge-info",
        "effectiveness_review": "badge-info",
        "closed": "badge-green",
        "voided": "badge-muted",
    }

    title = models.CharField(max_length=255)
    issue_summary = models.TextField(help_text="Detailed problem description, defect observations, and initial conditions")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES, default="corrective", db_index=True)
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES, default="ncr", db_index=True)
    source_reference = models.CharField(max_length=100, blank=True, help_text="Originating defect/document reference ID")
    risk_priority = models.CharField(max_length=16, choices=RISK_PRIORITY_CHOICES, default="medium", db_index=True)
    containment_actions = models.TextField(blank=True, help_text="Immediate stop-gap containment or quarantine measures")
    containment_implemented = models.BooleanField(default=False, help_text="Whether immediate containment/quarantine actions have been executed")
    containment_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_containment_capas"
    )
    containment_date = models.DateField(null=True, blank=True)
    affected_item_code = models.CharField(max_length=100, blank=True, help_text="Part number or SKU affected")
    affected_item_name = models.CharField(max_length=255, blank=True, help_text="Item name or product description")
    affected_lot_numbers = models.CharField(max_length=255, blank=True, help_text="Impacted lot, batch, or serial numbers")
    lead_investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="investigated_capas"
    )
    quality_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_capas"
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capa_investigations"
    )
    design_project = models.ForeignKey(
        "quality.DesignProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capa_investigations",
        help_text="Associated product development plan in Design Controls"
    )
    risk_assessment = models.ForeignKey(
        "quality.RiskAssessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capa_investigations",
        help_text="Linked ISO 14971 risk/FMEA assessment"
    )
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="draft", db_index=True)
    target_investigation_date = models.DateField(null=True, blank=True)
    target_closure_date = models.DateField(null=True, blank=True)
    is_escalated = models.BooleanField(default=False, help_text="Escalated to Executive Quality Management Review")
    escalation_reason = models.TextField(blank=True, help_text="Regulatory aging justification or critical patient risk trigger")
    escalated_at = models.DateTimeField(null=True, blank=True)
    closure_summary = models.TextField(blank=True, help_text="Formal justification and summary of completed remediation")
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_closure_capas"
    )
    formal_closure_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_capa_signatures",
        editable=False,
        help_text="21 CFR Part 11 e-signature manifest"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "CAPA Investigation"
        verbose_name_plural = "CAPA Investigations"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcap_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcap_ten_status"),
            models.Index(fields=["tenant", "action_type"], name="idx_qcap_ten_act_type"),
            models.Index(fields=["tenant", "department"], name="idx_qcap_ten_dept"),
            models.Index(fields=["tenant", "source_type"], name="idx_qcap_ten_src_type"),
            models.Index(fields=["tenant", "risk_priority"], name="idx_qcap_ten_risk_pri"),
            models.Index(fields=["tenant", "target_closure_date"], name="idx_qcap_ten_tgt_date"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qcap_ten_created"),
        ]

    def __str__(self):
        return f"{self.number}: {self.title}"

    @property
    def action_type_badge(self):
        return self.ACTION_TYPE_CSS.get(self.action_type, "badge-slate")

    @property
    def source_type_badge(self):
        return self.SOURCE_TYPE_CSS.get(self.source_type, "badge-slate")

    @property
    def risk_priority_badge(self):
        return self.RISK_PRIORITY_CSS.get(self.risk_priority, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def actions_count(self):
        if "actions_count" in self.__dict__:
            return self.__dict__["actions_count"]
        return self.actions.count()

    @property
    def pending_actions_count(self):
        if "pending_actions_count" in self.__dict__:
            return self.__dict__["pending_actions_count"]
        return self.actions.exclude(status__in=["implemented", "verified", "cancelled"]).count()

    @property
    def rca_count(self):
        return self.root_cause_analyses.count()

    @property
    def is_overdue(self):
        return bool(
            self.target_closure_date
            and self.target_closure_date < timezone.now().date()
            and self.status not in ["closed", "voided"]
        )

    @property
    def days_open(self):
        end = self.closed_at.date() if self.closed_at else timezone.now().date()
        return (end - self.created_at.date()).days
