"""SCM 4.9 Quality Management — QualityAudit, the audit programme [QA-].

Realizes the "Audit Management" bullet entirely: schedule an audit, run it against a checklist,
raise findings, conclude, close.

**Zero coupling to the stock spine.** Nothing here points at ``Item``, ``LotSerial``, ``StockMove``,
a goods receipt, a shipment or a work order — an audit is about a process or a counterparty, not a
batch. That is what makes this the lowest-risk of 4.9's five models: no code path in this file can
destabilise the ledger.

**Findings ARE NonConformance rows.** ``NonConformance(source="audit", audit=…)`` — there is no
``QualityAuditFinding`` table. One finding register fed by inspections, receipts, production,
suppliers and audits alike is the whole point: a "major finding" and a "major non-conformance" are
the same object, get the same disposition workflow, and feed the same CAPA. Evidence attaches as a
``core.Document`` through its generic FK.

**``findings_major`` / ``findings_minor`` are NOT columns and must never become columns.** They are
properties here and ``Count(..., filter=Q(...))`` annotations on the list. Storing a derived count
is the pattern 4.7 shipped, regretted and fixed — the number goes stale the moment a finding's
severity is edited, and nothing recomputes it.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class QualityAudit(TenantNumbered):
    """One planned or executed audit of a process, a supplier or a customer requirement [QA-]."""

    NUMBER_PREFIX = "QA"

    AUDIT_TYPE_CHOICES = [
        ("internal", "Internal — our own process"),
        ("supplier", "Supplier — a counterparty we buy from"),
        ("customer", "Customer — an audit of us by a customer"),
        ("certification", "Certification — an external body"),
    ]
    RISK_LEVEL_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("reported", "Reported"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    #: Audit types whose auditee is an external party rather than one of our own org units.
    EXTERNAL_TYPES = ("supplier", "customer")
    #: Finding severities that count as "major" on the roll-ups (Intelex grading).
    MAJOR_SEVERITIES = ("critical", "major")
    #: Finding statuses that still need work before the audit can be closed.
    OPEN_FINDING_STATUSES = ("open", "investigating", "dispositioned")

    audit_type = models.CharField(max_length=14, choices=AUDIT_TYPE_CHOICES, default="internal")
    title = models.CharField(max_length=255)
    standard = models.CharField(
        max_length=120, blank=True,
        help_text="Free text, e.g. ISO 9001:2015 — a standards master is deferred")
    scope = models.TextField(blank=True)

    auditee_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="scm_quality_audits",
                                      help_text="The supplier or customer being audited")
    auditee_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="scm_quality_audits",
                                         help_text="The department being audited internally")
    checklist_plan = models.ForeignKey(
        "scm.InspectionPlan", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audits",
        help_text="An audit-checklist inspection plan — its characteristics are the questions")
    lead_auditor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="scm_led_audits",
                                     help_text="An employee party — 4.9 adds no person table")

    planned_date = models.DateField()
    risk_level = models.CharField(max_length=8, choices=RISK_LEVEL_CHOICES, default="medium",
                                  help_text="Drives how often this auditee comes round again")
    # Stamped by the start/complete actions ONLY — never typed, never the admin.
    actual_start = models.DateField(null=True, blank=True, editable=False)
    actual_end = models.DateField(null=True, blank=True, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned",
                              editable=False)
    conclusion = models.TextField(
        blank=True, help_text="The auditor's narrative — required before the audit can be reported")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-planned_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_qa_tnt_status_idx"),
            models.Index(fields=["tenant", "audit_type", "status"],
                         name="scm_qa_tnt_type_status_idx"),
            models.Index(fields=["tenant", "planned_date"], name="scm_qa_tnt_date_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'QA'} · {self.title}"

    def clean(self):
        super().clean()
        if self.actual_start and self.actual_end and self.actual_end < self.actual_start:
            raise ValidationError({"actual_end": "The audit cannot end before it starts."})
        if self.audit_type in self.EXTERNAL_TYPES and self.auditee_party_id is None:
            raise ValidationError({"auditee_party": "A supplier or customer audit must name the "
                                                    "party being audited."})
        if self.audit_type == "internal" and self.auditee_org_unit_id is None:
            raise ValidationError({"auditee_org_unit": "An internal audit must name the department "
                                                       "being audited."})
        if (self.checklist_plan_id
                and self.checklist_plan.plan_type != "audit_checklist"):
            raise ValidationError({"checklist_plan": f"{self.checklist_plan.code} is a "
                                                     f"{self.checklist_plan.get_plan_type_display()} "
                                                     "plan, not an audit checklist."})

    # --- derived (nothing below is stored — see the module docstring) ----------------------------
    #: Statuses whose header the auditor may still edit. `in_progress` is included deliberately:
    #: `qualityaudit_complete` refuses a blank `conclusion`, and the conclusion is written AFTER
    #: the audit has been run — locking the header at `start` made the normal path unreachable and
    #: left Cancel as the only remaining action.
    EDITABLE_STATUSES = ("planned", "in_progress")

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def finding_count(self):
        return self.findings.count()

    @property
    def major_count(self):
        return self.findings.filter(severity__in=self.MAJOR_SEVERITIES).count()

    @property
    def minor_count(self):
        return self.findings.exclude(severity__in=self.MAJOR_SEVERITIES).count()

    @property
    def open_finding_count(self):
        return self.findings.filter(status__in=self.OPEN_FINDING_STATUSES).count()

    @property
    def duration_days(self):
        """Calendar days the audit ran, inclusive. ``None`` while it has not finished."""
        if not self.actual_start or not self.actual_end:
            return None
        return (self.actual_end - self.actual_start).days + 1
