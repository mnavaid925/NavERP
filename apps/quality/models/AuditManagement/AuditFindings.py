from datetime import date

from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class AuditFinding(TenantNumbered):
    NUMBER_PREFIX = "QFND"

    SEVERITY_CHOICES = (
        ("critical", "Critical Non-Conformance (Immediate Regulatory / Safety Risk)"),
        ("major", "Major Non-Conformance (Systemic Process Failure)"),
        ("minor", "Minor Non-Conformance (Isolated Procedural Lapse)"),
        ("observation_ofi", "Opportunity for Improvement (OFI)"),
        ("commendation", "Commendation / Best Practice"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft Finding"),
        ("issued", "Issued to Auditee"),
        ("response_submitted", "Remediation Response Submitted"),
        ("response_accepted", "Response Accepted by Auditor"),
        ("capa_in_progress", "CAPA Investigation In Progress"),
        ("verification_pending", "Closure Verification Pending"),
        ("closed", "Closed / Verified Effective"),
        ("escalated", "Escalated / Past Due"),
    )

    SEVERITY_CSS = {
        "critical": "badge-red",
        "major": "badge-red",
        "minor": "badge-amber",
        "observation_ofi": "badge-info",
        "commendation": "badge-green",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "issued": "badge-amber",
        "response_submitted": "badge-info",
        "response_accepted": "badge-info",
        "capa_in_progress": "badge-amber",
        "verification_pending": "badge-amber",
        "closed": "badge-green",
        "escalated": "badge-red",
    }

    audit = models.ForeignKey(
        "quality.QualityAudit",
        on_delete=models.CASCADE,
        related_name="findings",
    )
    finding_number_in_audit = models.PositiveSmallIntegerField(
        default=1,
        help_text="Sequential number within this audit e.g. 1, 2, 3",
    )
    title = models.CharField(max_length=255, help_text="Finding headline / observation summary")
    severity = models.CharField(max_length=24, choices=SEVERITY_CHOICES, default="minor", db_index=True)
    standard_clause = models.CharField(max_length=128, help_text="Standard & clause cited e.g. ISO 13485:2016 §8.2.4, 21 CFR 820.22")

    requirement_statement = models.TextField(help_text="Specified requirement, procedure, or regulation text")
    condition_evidence = models.TextField(help_text="Objective evidence observed proving non-conformance")

    audited_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unit_audit_findings",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_audit_findings",
        help_text="Auditee owner responsible for remediation",
    )
    response_due_date = models.DateField(db_index=True, help_text="Enforced turnaround SLA for auditee response")
    response_received_date = models.DateField(null=True, blank=True)

    containment_action = models.TextField(blank=True, help_text="Immediate correction taken to contain non-conformance")
    root_cause_summary = models.TextField(blank=True, help_text="Root cause analysis submitted by auditee")
    corrective_action_plan = models.TextField(blank=True, help_text="Proposed corrective action plan")

    linked_capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_audit_findings",
        help_text="Closed-loop CAPA investigation",
    )
    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_audit_findings",
        help_text="Immediate Non-Conformance Report",
    )

    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="issued", db_index=True)

    closure_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_audit_findings",
    )
    closed_date = models.DateField(null=True, blank=True)
    closure_notes = models.TextField(blank=True, help_text="Lead auditor verification rationale and objective evidence of closure")

    class Meta:
        ordering = ["-created_at", "finding_number_in_audit"]
        verbose_name = "Audit Finding"
        verbose_name_plural = "Audit Findings"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qfnd_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qfnd_ten_status"),
            models.Index(fields=["tenant", "severity"], name="idx_qfnd_ten_sev"),
            models.Index(fields=["tenant", "audit"], name="idx_qfnd_ten_audit"),
            models.Index(fields=["tenant", "assignee"], name="idx_qfnd_ten_assignee"),
            models.Index(fields=["tenant", "response_due_date"], name="idx_qfnd_ten_due"),
            models.Index(fields=["tenant", "linked_capa"], name="idx_qfnd_ten_capa"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qfnd_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_severity_display()}) - {self.title}"

    @property
    def is_overdue(self):
        if self.status not in ("draft", "issued", "escalated"):
            return False
        return date.today() > self.response_due_date

    @property
    def requires_capa(self):
        return self.severity in ("critical", "major") and not self.linked_capa_id

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if hasattr(self, "audit") and self.audit_id:
            self.audit.sync_findings_counts()

    def delete(self, *args, **kwargs):
        audit = self.audit if (hasattr(self, "audit") and self.audit_id) else None
        res = super().delete(*args, **kwargs)
        if audit:
            audit.sync_findings_counts()
        return res
