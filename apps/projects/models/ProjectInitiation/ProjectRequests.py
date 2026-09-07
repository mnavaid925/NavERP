"""Projects 7.1 Project Initiation & Charter — ProjectRequest [PRQ-].

Realizes NavERP 7.1 bullets **1 Project Request & Intake** and **2 Business Case &
Feasibility**: the single demand-intake register a request travels through from "someone asked
for something" to a go/no-go decision, and — for a Go — the one verb that turns it into a
`Project`.

Two deliberate model caps, both reversible:

* **No `BusinessCase` table.** Bullet 2's economics (`estimated_cost`, `estimated_benefit`,
  `currency`, `risk_rating`, `strategic_alignment`, `alternatives_considered`) are a field set on
  this row. A charter-level business case with its own approver and version history would want its
  own table; the field names here are already grouped for that split if it is ever wanted.
* **No `promoted_to` self-FK.** ServiceNow/JPD model idea→demand promotion inside the one
  register; `request_type="idea"` carries the lighter-weight case without a promote verb.

Status and decision are **verb-driven, never on the form** — a row cannot be edited into
"approved", it must be approved through the action that stamps who/when (the scm requisition
rule).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import Decimal, models, transaction


class ProjectRequest(TenantNumbered):
    NUMBER_PREFIX = "PRQ"

    REQUEST_TYPE_CHOICES = [
        ("new_project", "New Project"),
        ("enhancement", "Enhancement"),
        ("change_request", "Change Request"),
        ("defect", "Defect Repair"),
        ("idea", "Idea"),
    ]
    SOURCE_CHOICES = [
        ("portal", "Portal"),
        ("internal", "Internal"),
        ("idea", "Idea"),
        ("opportunity", "Opportunity"),
        ("email", "Email"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    RISK_RATING_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    FEASIBILITY_CHOICES = [
        ("not_assessed", "Not Assessed"),
        ("feasible", "Feasible"),
        ("feasible_with_constraints", "Feasible with Constraints"),
        ("not_feasible", "Not Feasible"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("screening", "Screening"),
        ("assessment", "Assessment"),
        ("needs_information", "Needs Information"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("deferred", "Deferred"),
        ("converted", "Converted"),
    ]
    DECISION_CHOICES = [
        ("go", "Go"),
        ("no_go", "No-Go"),
        ("hold", "Hold"),
        ("deferred", "Deferred"),
    ]

    #: The documented flat factor behind "risk-adjusted return": a `high` risk rating discounts
    #: the stated benefit to 70%. Deliberately NOT Monte Carlo — the probabilistic simulation is
    #: 7.5 Risk & Issue Management's, and shipping a fake one here would be worse than none.
    RISK_DISCOUNT = {
        "low": Decimal("1.00"),
        "medium": Decimal("0.85"),
        "high": Decimal("0.70"),
        "critical": Decimal("0.50"),
    }

    #: The statuses a request must be in for the Go decision to be taken.
    DECISION_STATUSES = ("submitted", "screening", "assessment")

    title = models.CharField(max_length=200)
    description = models.TextField()

    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default="new_project")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prq_filed")
    #: An EXTERNAL submitter (a customer or partner organisation). Internal staff are `requested_by`.
    requester_party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_requests")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_requests")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="internal")
    source_opportunity = models.ForeignKey(
        "crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_requests")

    assigned_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prq_to_review")
    assigned_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="prq_to_approve")

    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    #: 0-5 scoring (ServiceNow / Planview). 0 means "not scored", not "no alignment" — the form
    #: renders it as a neutral "Not scored" option.
    strategic_alignment = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(5)])

    # MinValueValidator(0) on both: a negative cost or benefit is not a business case, and it
    # reaches `roi_pct` / `risk_adjusted_roi_pct`, where q2() clamps it to a fabricated
    # -9999999999.99% that the ready-to-convert queue then ranks on. (NaN/Infinity and huge
    # magnitudes are already rejected by Django's DecimalField + DecimalValidator(14, 2).)
    estimated_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(ZERO)])
    estimated_benefit = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(ZERO)])
    #: accounting.Currency is GLOBAL — it has no `tenant` column (L29). Never compare its tenant.
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_requests")
    risk_rating = models.CharField(max_length=10, choices=RISK_RATING_CHOICES, default="low")

    # 32, not 24: "feasible_with_constraints" is 25 characters (fields.E009 caught this in check).
    feasibility = models.CharField(
        max_length=32, choices=FEASIBILITY_CHOICES, default="not_assessed")
    feasibility_notes = models.TextField(blank=True)
    alternatives_considered = models.TextField(blank=True)
    required_resources = models.TextField(
        blank=True, help_text="Free text — real resourcing is 7.3 Resource Management's.")

    target_start_date = models.DateField(null=True, blank=True)
    target_end_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES, default="", blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    information_requested = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)

    #: Set by the convert verb — the project this request became.
    converted_project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="source_requests")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prq_tnt_status_idx"),
            models.Index(fields=["tenant", "request_type"], name="prq_tnt_type_idx"),
            models.Index(fields=["tenant", "org_unit"], name="prq_tnt_ou_idx"),
            # Serves `Meta.ordering` itself: every register page — including the unfiltered
            # default, the most-requested URL — sorted with `Using filesort` over the tenant's
            # whole row set before LIMIT 15, so page cost was O(tenant rows), not O(15). The
            # in-pattern add: ["tenant", "created_at"] already ships on 20+ models app-wide.
            models.Index(fields=["tenant", "-created_at"], name="prq_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived economics (properties, NEVER columns) ------------------------------------------

    @property
    def roi_pct(self):
        """(benefit - cost) / cost * 100, or ``None`` when there is no cost to divide by.

        ``None`` rather than a ZeroDivisionError and rather than a fake 0/infinity: a request with
        no cost estimate has no ROI, and the template says so instead of printing a number.
        """
        cost = self.estimated_cost or Decimal("0")
        if cost == 0:
            return None
        return q2((self.estimated_benefit - cost) / cost * 100)

    @property
    def risk_adjusted_benefit(self):
        return q2(self.estimated_benefit * self.RISK_DISCOUNT.get(self.risk_rating, Decimal("1.00")))

    @property
    def risk_adjusted_roi_pct(self):
        cost = self.estimated_cost or Decimal("0")
        if cost == 0:
            return None
        return q2((self.risk_adjusted_benefit - cost) / cost * 100)

    # -- the convert verb ------------------------------------------------------------------------

    def convert_to_project(self, user=None):
        """Turn an approved request into a `Project`, linking both directions.

        One ``transaction.atomic()``: the project and the back-pointer must land together or not
        at all — a half-converted request is exactly the state that produces two projects for
        one demand.

        The idempotency guard is a LOCKING RE-READ, not a check on this instance: two concurrent
        POSTs each hold their own in-memory ``ProjectRequest``, so an ``if self.converted_project_id``
        on a stale copy lets both through and mints two projects for one demand. The
        ``select_for_update()`` below re-reads the row under an exclusive lock *inside* the
        transaction and filters on ``converted_project__isnull=True`` in the same statement — a
        compare-and-swap: the loser blocks until the winner commits, then reads the latest row,
        matches nothing, and returns None. (The cheap ``self.converted_project_id`` check stays as
        a fast path that avoids taking a lock in the common case.)
        """
        from apps.projects.models import Project

        if self.converted_project_id:
            return None
        with transaction.atomic():
            unconverted = (type(self).objects
                           .select_for_update()
                           .filter(pk=self.pk, converted_project__isnull=True)
                           .exists())
            if not unconverted:
                return None
            project = Project(
                tenant=self.tenant,
                name=self.title,
                description=self.description,
                request=self,
                org_unit=self.org_unit,
                client=self.requester_party,
                executive_sponsor=self.assigned_approver,
                start_date=self.target_start_date,
                end_date=self.target_end_date,
                created_by=user,
            )
            project.save()
            self.converted_project = project
            self.status = "converted"
            self.save(update_fields=["converted_project", "status", "updated_at"])
        return project
