"""HRM 3.5 Job Requisition — Jobrequisition models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.JobRequisition.EMPLOYMENT_TYPE_CHOICESs import EMPLOYMENT_TYPE_CHOICES
from apps.hrm.models.JobRequisition.JR_STATUS_CHOICESs import JR_STATUS_CHOICES
from apps.hrm.models.JobRequisition.POSTING_TYPE_CHOICESs import POSTING_TYPE_CHOICES
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES
from apps.hrm.models.JobRequisition.REASON_FOR_HIRE_CHOICESs import REASON_FOR_HIRE_CHOICES
from apps.hrm.models.JobRequisition.REQ_TYPE_CHOICESs import REQ_TYPE_CHOICES
from apps.hrm.models.JobRequisition.EMPLOYMENT_TYPE_CHOICESs import EMPLOYMENT_TYPE_CHOICES
from apps.hrm.models.JobRequisition.JR_STATUS_CHOICESs import JR_STATUS_CHOICES
from apps.hrm.models.JobRequisition.POSTING_TYPE_CHOICESs import POSTING_TYPE_CHOICES
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES
from apps.hrm.models.JobRequisition.REASON_FOR_HIRE_CHOICESs import REASON_FOR_HIRE_CHOICES
from apps.hrm.models.JobRequisition.REQ_TYPE_CHOICESs import REQ_TYPE_CHOICES


class JobRequisition(TenantNumbered):
    """The hub "authorization to hire" record (3.5). One per opening event; drives the
    draft → pending_approval → approved → posted → filled lifecycle (+ on_hold / rejected /
    cancelled). The JD body fields are an opening-specific *copy* (distinct from the evergreen
    ``Designation.description``). Workflow-owned fields (status + the ``*_at`` stamps) are
    ``editable=False`` and set only by the audited POST actions — never on the form."""

    NUMBER_PREFIX = "JR"

    # Identity
    title = models.CharField(max_length=255)
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="requisitions")
    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="requisitions")
    template = models.ForeignKey("hrm.JobDescriptionTemplate", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="requisitions")

    # Organization
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="hrm_requisitions",
                                   limit_choices_to={"kind": "department"})
    cost_center = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="hrm_requisitions_cc",
                                    limit_choices_to={"kind": "cost_center"})
    location = models.CharField(max_length=255, blank=True)

    # Headcount & type
    headcount = models.PositiveSmallIntegerField(default=1)
    req_type = models.CharField(max_length=20, choices=REQ_TYPE_CHOICES, default="standard")
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES,
                                       default="full_time")
    reason_for_hire = models.CharField(max_length=30, choices=REASON_FOR_HIRE_CHOICES,
                                       default="new_headcount")
    is_replacement_for = models.CharField(max_length=255, blank=True,
                                          help_text="Name of the departing employee (free text; "
                                                    "FK upgrade deferred to 3.6).")
    posting_type = models.CharField(max_length=10, choices=POSTING_TYPE_CHOICES, default="external")

    # Hiring team — per HRM convention, FK to EmployeeProfile (never core.Party directly).
    hiring_manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="managed_requisitions")
    recruiter = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name="assigned_requisitions")

    # Timeline
    target_start_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")

    # Budget
    salary_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default="USD")
    estimated_annual_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                help_text="Loaded annual cost (salary + benefits).")
    hiring_cost_budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                             help_text="One-time recruitment spend (agency/job-board).")

    # Job description (opening-specific copy)
    jd_summary = models.TextField(blank=True)
    jd_responsibilities = models.TextField(blank=True)
    jd_requirements = models.TextField(blank=True)
    jd_nice_to_have = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Workflow-owned — set only by the POST actions, never the form.
    status = models.CharField(max_length=20, choices=JR_STATUS_CHOICES, default="draft",
                              editable=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    posted_at = models.DateTimeField(null=True, blank=True, editable=False)
    filled_at = models.DateTimeField(null=True, blank=True, editable=False)

    # 3.6 Candidate Management — public career-portal bearer credential. Set (once) when the req is
    # posted; an unguessable token resolves the public application page (mirrors crm.Case/LandingPage:
    # unique + null when unposted so the empty values don't collide on the unique constraint).
    public_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text="URL-safe token minted when the req is posted; powers the public careers portal.")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_jr_tenant_status_idx"),
            models.Index(fields=["tenant", "designation"], name="hrm_jr_tenant_desig_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_jr_tenant_dept_idx"),
            models.Index(fields=["tenant", "hiring_manager"], name="hrm_jr_tenant_hm_idx"),
            models.Index(fields=["tenant", "priority", "status"], name="hrm_jr_tenant_prio_stat_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.salary_min is not None and self.salary_max is not None
                and self.salary_min > self.salary_max):
            raise ValidationError({"salary_max": "Salary minimum cannot exceed maximum."})
        if self.headcount is not None and self.headcount < 1:
            raise ValidationError({"headcount": "Headcount must be at least 1."})

    @property
    def is_overdue(self):
        """True when the target start date has passed and the req isn't yet filled/closed —
        drives the red 'Overdue' indicator."""
        return (self.target_start_date is not None
                and self.target_start_date < date.today()
                and self.status not in ("filled", "cancelled", "rejected"))

    @property
    def approval_progress(self):
        """``(approved_count, total_count)`` over the approval chain — feeds the detail-hub
        progress text. Computed from the prefetched ``approvals`` when available.

        PERF: fires a SELECT unless ``approvals`` is prefetched. Over a *collection* of
        requisitions, compute from an already-fetched list instead (see ``jobrequisition_detail``)."""
        steps = self.approvals.all()
        total = len(steps)
        approved = sum(1 for s in steps if s.status == "approved")
        return approved, total

    @property
    def current_approval_step(self):
        """The lowest-ordered still-pending approval step (the one awaiting a decision), or
        ``None`` when the chain is fully decided.

        PERF: fires a SELECT per call. Don't call in a list loop — the detail view derives the
        current step from its already-fetched ``approvals`` list instead."""
        return (self.approvals.filter(status="pending").order_by("step_order").first())

    def __str__(self):
        return f"{self.number} · {self.title}"
