"""Projects 7.1 Project Initiation & Charter — Project [PRJ-].

Realizes NavERP 7.1 bullet **3 Project Charter Authoring**, and is the container every later
`7.M` sub-module FKs into (7.2 WBS & baseline, 7.3 resource management, 7.4 cost, 7.5 risk …).

⚠️ **The three `PRJ-` models — do NOT "fix" this by renaming or merging anything.**

| Model | File | Status |
|---|---|---|
| `accounting.Project` | `apps/accounting/models/ProjectCosting/Projects.py` | pre-spine stand-in, `NUMBER_PREFIX = "PRJ"` |
| `crm.CrmProject` | `apps/crm/models/ProjectDelivery/Projects.py` | pre-spine stand-in, `NUMBER_PREFIX = "PRJ"` |
| `projects.Project` | *this model* | the master, added by 7.1 |

Numbers are unique per ``(tenant, number)`` **within a model**, so the shared prefix is not a key
collision — but it does mean three different "projects" can all read `PRJ-00001`, so page titles
and the sidebar copy must always say which one the user is looking at. Neither stand-in is
renamed, migrated or deprecated from here; that is a spine consolidation, not a sub-module pass.

**Charter stays short.** No money columns — `budget_amount`, commitments and actuals are 7.4
Cost & Budget Management's, and `accounting.Project` already carries them for the costing lens.
No second attachment store: the signed charter is `charter_document` → `core.Document`.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class Project(TenantNumbered):
    NUMBER_PREFIX = "PRJ"

    METHODOLOGY_CHOICES = [
        ("waterfall", "Waterfall"),
        ("agile", "Agile"),
        ("hybrid", "Hybrid"),
    ]
    CHARTER_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        # RESERVED, not dead: 7.1 ships submit + approve only, so no verb SETS `rejected` yet —
        # a charter an approver disagrees with is simply not approved. It stays in the choices
        # (and `prj_submit_charter` accepts it as a source, so a rejected charter can be
        # resubmitted) because the reject-charter verb belongs with 7.x's approval workflow;
        # dropping it would cost a migration and have to be added straight back.
        ("rejected", "Rejected"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("chartered", "Chartered"),
        ("kickoff", "Kickoff"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    #: Provenance — set by the convert verb ONLY, never by a form.
    request = models.ForeignKey(
        "projects.ProjectRequest", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="projects")
    #: The reusable template LIBRARY behind this is 7.19 Master Data & Configuration's.
    methodology = models.CharField(max_length=12, choices=METHODOLOGY_CHOICES, default="hybrid")

    in_scope = models.TextField(blank=True)
    out_of_scope = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    success_criteria = models.TextField(blank=True, help_text="Measurable — PM².")
    assumptions = models.TextField(blank=True)
    constraints = models.TextField(blank=True)
    risk_summary = models.TextField(
        blank=True, help_text="Charter-level summary; the risk register is 7.5's.")

    executive_sponsor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sponsored_projects")
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="managed_projects")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    client = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="delivery_projects")

    start_date = models.DateField(
        null=True, blank=True, help_text="Charter target; the frozen baseline is 7.2's.")
    end_date = models.DateField(null=True, blank=True)

    charter_status = models.CharField(
        max_length=12, choices=CHARTER_STATUS_CHOICES, default="draft")
    charter_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    charter_approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: Reuse of the core attachment store — no second document table (the 6.19 ruling).
    charter_document = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_charters")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prj_tnt_status_idx"),
            models.Index(fields=["tenant", "charter_status"], name="prj_tnt_charter_idx"),
            models.Index(fields=["tenant", "client"], name="prj_tnt_client_idx"),
            models.Index(fields=["tenant", "org_unit"], name="prj_tnt_ou_idx"),
            # Serves `Meta.ordering` itself: every register page — including the unfiltered
            # default, the most-requested URL — sorted with `Using filesort` over the tenant's
            # whole row set before LIMIT 15, so page cost was O(tenant rows), not O(15). The
            # in-pattern add: ["tenant", "created_at"] already ships on 20+ models app-wide.
            models.Index(fields=["tenant", "-created_at"], name="prj_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def is_overdue(self):
        """Past its charter end date and not in a terminal state.

        `completed` and `cancelled` are excluded on purpose: a finished project whose end date has
        passed is not overdue, and an "Overdue" badge on a closed project is the kind of thing
        that makes people stop trusting the badge.
        """
        if not self.end_date:
            return False
        if self.status in ("completed", "cancelled"):
            return False
        return self.end_date < timezone.localdate()
