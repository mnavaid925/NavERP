"""SCM 4.9 Quality Management — CapaAction + CapaTask, the corrective/preventive plan [CAPA-].

Realizes the "Corrective and Preventive Action (CAPA)" bullet entirely, and closes 4.2's parked
SCAR hook without touching 4.2's schema: a supplier corrective-action request is a CAPA with
``source="supplier"`` and the ``supplier`` FK set.

**Corrective vs preventive is an ATTRIBUTE, not two tables** (ISO 9001 §10.2, and how Odoo models
it) — the workflow, the tasks, the root-cause analysis and the effectiveness check are identical.

**A stand-alone CAPA is first-class** (TrackWise's term). ``nonconformance`` and ``audit`` are both
nullable: a trend spotted across inspections, or a management-review improvement, is a legitimate
CAPA with no parent document.

**DEFERRED and named here so nobody looks for it:** rules-based routing, configurable approval
matrices and electronic-signature ladders (MasterControl / ETQ / Veeva). NavERP has no workflow
engine, so this pass is a FIXED status ladder — open → investigating → in_progress →
pending_verification → closed, with ``not_effective`` re-opening at investigating (QT9's re-open).
Structured 8D step records and fishbone branches are deferred too: this pass stores the METHOD and
the CONCLUSION, which is what a report actually reads.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class CapaAction(TenantNumbered):
    """One corrective or preventive action — problem, root cause, plan, tasks, verification [CAPA-]."""

    NUMBER_PREFIX = "CAPA"

    ACTION_TYPE_CHOICES = [
        ("corrective", "Corrective — stop it recurring"),
        ("preventive", "Preventive — stop it happening"),
    ]
    SOURCE_CHOICES = [
        ("nonconformance", "Non-conformance"),
        ("audit_finding", "Audit finding"),
        ("inspection_trend", "Inspection trend"),
        ("supplier", "Supplier (SCAR)"),
        ("complaint", "Customer complaint"),
        ("internal_improvement", "Internal improvement"),
    ]
    ROOT_CAUSE_METHOD_CHOICES = [
        ("five_why", "5 Why"),
        ("fishbone", "Fishbone / Ishikawa"),
        ("fault_tree", "Fault tree"),
        ("eight_d", "8D"),
        ("pareto", "Pareto"),
        ("other", "Other"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("investigating", "Investigating"),
        ("in_progress", "In Progress"),
        ("pending_verification", "Pending Verification"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    EFFECTIVENESS_CHOICES = [
        ("pending", "Pending"),
        ("effective", "Effective"),
        ("not_effective", "Not Effective"),
    ]
    #: Statuses whose header/tasks the owner may still edit.
    EDITABLE_STATUSES = ("open", "investigating", "in_progress")

    action_type = models.CharField(max_length=10, choices=ACTION_TYPE_CHOICES,
                                   default="corrective")
    title = models.CharField(max_length=255)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES,
                              default="internal_improvement")
    nonconformance = models.ForeignKey("scm.NonConformance", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="capa_actions")
    audit = models.ForeignKey("scm.QualityAudit", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="capa_actions")
    # SET_NULL, deliberately NOT PROTECT: a CAPA is a process improvement and the item is context.
    # A fourth PROTECT FK onto Item would mean a fourth delete guard for no traceability gain.
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="capa_actions")
    supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_capa_actions",
                                 help_text="Set to make this a supplier corrective-action request")

    problem_statement = models.TextField()
    containment_action = models.TextField(
        blank=True, help_text="The immediate correction — distinct from the CAPA itself")
    root_cause_method = models.CharField(max_length=12, choices=ROOT_CAUSE_METHOD_CHOICES,
                                         blank=True)
    root_cause = models.TextField(blank=True,
                                  help_text="Required before the action can be marked implemented")
    action_plan = models.TextField(blank=True)

    owner = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="scm_capa_actions_owned")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="normal")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open",
                              editable=False)

    # --- effectiveness block ---------------------------------------------------------------------
    # `effectiveness_due_date` is EDITABLE and the form is its only writer. The implement action
    # deliberately REFUSES while it is blank rather than defaulting it — filling it there would
    # make the action a second writer of a date the owner is accountable for.
    implemented_on = models.DateField(null=True, blank=True, editable=False)
    effectiveness_due_date = models.DateField(
        null=True, blank=True,
        help_text="When the fix gets checked for effectiveness — set it before implementing")
    effectiveness_result = models.CharField(max_length=14, choices=EFFECTIVENESS_CHOICES,
                                            default="pending", editable=False)
    verified_by = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                    editable=False, related_name="scm_capa_verifications")
    verified_on = models.DateField(null=True, blank=True, editable=False)
    verification_notes = models.TextField(blank=True, editable=False)
    closed_on = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_capa_tnt_status_idx"),
            models.Index(fields=["tenant", "priority", "status"], name="scm_capa_tnt_prio_idx"),
            models.Index(fields=["tenant", "due_date"], name="scm_capa_tnt_due_idx"),
            models.Index(fields=["tenant", "source"], name="scm_capa_tnt_source_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'CAPA'} · {self.title}"

    def clean(self):
        super().clean()
        if (self.effectiveness_due_date and self.due_date
                and self.effectiveness_due_date < self.due_date):
            raise ValidationError({"effectiveness_due_date": "Effectiveness is checked after the "
                                                             "action is due, not before."})
        if self.source == "nonconformance" and self.nonconformance_id is None:
            raise ValidationError({"nonconformance": "Name the non-conformance this CAPA answers."})
        if self.source == "audit_finding" and self.audit_id is None:
            raise ValidationError({"audit": "Name the audit this CAPA came out of."})
        if self.source == "supplier" and self.supplier_id is None:
            raise ValidationError({"supplier": "A supplier corrective-action request must name the "
                                               "supplier."})

    # --- derived (nothing below is stored) -------------------------------------------------------
    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_overdue(self):
        if not self.due_date or self.status in ("closed", "cancelled"):
            return False
        return self.due_date < timezone.localdate()

    @property
    def verification_overdue(self):
        """The effectiveness check itself is late — the failure mode a CAPA register exists to catch."""
        return bool(self.effectiveness_due_date
                    and self.status == "pending_verification"
                    and self.effectiveness_result == "pending"
                    and self.effectiveness_due_date < timezone.localdate())

    @property
    def open_task_count(self):
        """Tasks still to do. ANNOTATED on the list page — this property is the detail-page reader."""
        return self.tasks.filter(status__in=("open", "in_progress")).count()


class CapaTask(models.Model):
    """One step of a CAPA's action plan. Tenant-less — reached only through its parent CAPA."""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]

    capa = models.ForeignKey("scm.CapaAction", on_delete=models.CASCADE, related_name="tasks")
    sequence = models.PositiveIntegerField(default=10)
    description = models.CharField(max_length=255)
    # The dropdown must still be narrowed to employee parties by hand: TenantModelForm scopes a
    # child's FK by tenant, but "an employee" is a PartyRole question it knows nothing about.
    owner = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="+")
    due_date = models.DateField(null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open")

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return self.description

    @property
    def is_overdue(self):
        if not self.due_date or self.status in ("done", "cancelled"):
            return False
        return self.due_date < timezone.localdate()
