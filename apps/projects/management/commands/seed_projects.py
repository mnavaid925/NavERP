"""Seed Project Management (Module 7) demo data — 7.1 Initiation & 7.2 Planning & Scheduling.

Per tenant it builds one honest end-to-end chain:

* **9 ProjectRequests**, one per status, so every status badge and every filter facet has a real
  row. Two of them matter more than the rest: the `approved` row that is **converted through the
  real ``convert_to_project()`` path** (so ``converted_project`` and ``Project.request`` are
  honest rather than hand-stamped) and a second `approved` row left **unconverted** so the Convert
  verb is still exercisable on a freshly seeded workspace.
* **3 Projects** — the converted one, one standalone draft, and one walked all the way to
  ``charter_status="approved"`` / ``status="active"``.
* **6 ProjectStakeholders** on the converted project: every RACI value, every
  influence×interest quadrant, mixed comms preferences, three flagged as attending the kickoff.
* **2 ProjectKickoffs** — one completed with its baseline acknowledged, one merely scheduled.
* **4 core.Activity rows** GFK'd to the active project: the kickoff meeting plus three onboarding
  tasks. No second checklist table — the activities ARE the onboarding checklist.
* **7.2 Planning & Scheduling** (``_planning``, its own guard): a WBS of deliverables + work
  packages per project, a dependency network whose longest FS chain is the critical path, phase
  gates and milestones, and baselines — sized to each project's lifecycle stage (the active
  project carries the full plan incl. its achieved discovery gate and the frozen baseline the
  completed kickoff acknowledged; the chartered project is mid-planning; the draft has sketch
  rows and no commitments).
* **7.3 Resource Management** (``_resourcing``, its own guard): a resource pool of internal
  staff (one per existing EmployeeProfile, varied capacities incl. a 24h part-timer) plus a
  windowed contractor, ten allocations exercising every booking status and all three magnitude
  units (named, placeholder, request-linked, and a released→successor substitution chain), and
  sixteen time entries across three ISO weeks covering all four statuses — the approval queue
  and the actuals-to-plan comparison ship with real rows.
* **7.4 Cost & Budget Management** (``_cost``, its own guard): an approved-and-activated
  revision 0 per planned project (it IS the cost baseline) plus a draft sketch revision and a
  pending-approval scope change (+50,000.00 ``amount_delta``), budget lines across all seven
  categories anchored to the WBS work packages, one control account per active-project
  deliverable tuned so all three CPI health bands render, and expenses covering every entry
  type and status — posted commitments with PO strings, actuals, accruals, one void row and one
  draft.
* **7.5 Risk & Issue Management** (``_risk``, its own guard): 17 risks per tenant (12 on the
  active project, 5 on the chartered one) covering all nine categories, both threat/opportunity
  values, all four severity bands and all six statuses — one realized risk carrying the issue the
  realize verb would have minted, one closed with a lesson, three with a past review date — plus
  response actions on the top risks (one completed, one overdue), seven issues across all four
  severities with two resolved and one escalated to level 2 with a two-step escalation path.
* **7.8 Task & Work Management** (``_taskwork``, its own guard): the execution layer ON 7.2's
  tasks — no new task table — spreading assignees, every priority, all four MoSCoW values, all
  four Eisenhower quadrants and honest percent_complete over the work packages, with
  actual_start/actual_end stamped on the started/finished rows the way the verbs would; plus a
  checklist per lead task (mixed ticks so the progress rollup is non-trivial) and the block
  evidence trail (one active blocker, one closed with its full unblock trail).
* **7.9 Collaboration & Communication** (``_collab``, its own guard): the conversation layer ON
  the existing projects — three channels (discussion, announcement, and one ARCHIVED) carrying 17
  messages across a two-reply thread, a one-reply thread, a bare root and an edited root with two
  mentions; four shared documents covering every access level and both active states (one
  claimed); four meetings, one per status, the completed one with full minutes, a covered agenda
  and a mixed action list; six agenda and six action items (one overdue, one unassigned, one
  linked to a real 7.2 work package); and 18 notifications covering every kind, both read states
  and every optional source FK. It reuses the workspace's existing projects, work packages and a
  ``core.Document`` — it never invents a project, a task or a second attachment store.
* **7.10 Document & Knowledge Management** (``_docmgt``, its own guard): the record layer ON the
  existing projects — a 12-folder tree across two projects (including an ARCHIVED branch), 22
  controlled documents spanning every doc type and every status (one ``expected`` placeholder, one
  checked-out row, one under legal hold, two archived, one superseded, two whose retention window
  has closed), 23 revisions whose numbers, checksums and extracted text are produced by the same
  helpers the upload verb uses (two superseded pairs, four rows left pending approval), 16
  standards covering every category with both publish states, and 17 knowledge entries covering
  every kind and every status with three on the featured shelf. It reuses the workspace's existing
  projects, work packages and milestones; the only files it writes are the revision and standard
  payloads, and only for rows this run created.

Every block is idempotent on its own guard, so a second run is a no-op without ``--flush``.
Nothing here invents a parallel customer or department: the chain reuses the workspace's existing
``core.Party`` / ``core.OrgUnit`` / users, and skips with a message when those are missing.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Activity, Document, OrgUnit, Party, PartyRole, Tenant
from apps.core.utils import write_audit_log
from apps.projects.models import (
    BudgetRevision,
    Channel,
    ChannelMessage,
    ClientApprovalRequest,
    ClientPortalAccess,
    CostControlAccount,

    DeliverableInspection,
    DocumentShare,
    DocumentTemplate,
    IssueEscalation,
    KnowledgeEntry,
    Meeting,
    MeetingActionItem,
    MeetingAgendaItem,
    OvertimeRule,
    Portfolio,
    PortfolioInvestment,
    Program,
    ProgramDependency,
    Project,
    ProjectBudgetLine,
    ProjectClientInvoice,
    ProjectDocument,
    ProjectDocumentRevision,
    ProjectEpic,
    ProjectExpense,
    ProjectFolder,
    ProjectIssue,
    ProjectKickoff,
    ProjectMilestone,
    ProjectNotification,
    ProjectRelease,
    ProjectRequest,
    ProjectRisk,
    ProjectStakeholder,
    ProjectTask,
    QualityDefect,
    QualityPlan,
    QualityReview,
    Requirement,
    ResourceAllocation,
    ResourceProfile,
    ResourceTimeEntry,
    RiskResponseAction,
    ScheduleBaseline,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
    SOWAmendment,
    Sprint,
    SprintImpediment,
    SprintRetrospective,
    StatementOfWork,
    TaskBlock,
    TaskChecklistItem,
    TaskDependency,
    TimeActivityCode,
    ProjectOvertimeRecord,
    VendorHandoff,
)


# -- 7.2 WBS specs -----------------------------------------------------------------------------
#
# Date offsets are days relative to today (negative = past). Deliverables carry no dates of
# their own — the tree view rolls their children up. Work-package names double as the keys the
# dependency/milestone specs reference, so a rename must move through all three specs.

#: The active project — the full plan. The FS chain workshops -> SSO spike -> order API ->
#: cart UI -> checkout -> refund hooks is the longest chain, i.e. the critical path.
ACTIVE_WBS = [
    dict(name="Discovery & design", node_type="deliverable", sequence=1),
    dict(name="Requirements workshops", parent="Discovery & design", node_type="work_package",
         start=-60, end=-52, effort="48.00", method="bottom_up", confidence="high",
         status="done", sequence=1),
    dict(name="UX design: ordering", parent="Discovery & design", node_type="work_package",
         start=-51, end=-35, effort="80.00", method="analogous", confidence="high",
         status="done", sequence=2),
    dict(name="Technical spike: SSO", parent="Discovery & design", node_type="work_package",
         start=-50, end=-40, effort="40.00", method="parametric", confidence="medium",
         status="done", sequence=3),
    # A CANCELLED leaf: 7.8's board/priority/register lenses all need a terminal-but-not-done
    # row to prove they exclude it (review M5 — the seed had no cancelled task). It carries
    # planned dates (it WAS planned) but no actuals, exactly like a real cancellation.
    dict(name="Legacy migration spike", parent="Discovery & design", node_type="work_package",
         start=-48, end=-30, effort="24.00", method="analogous", confidence="low",
         status="cancelled", sequence=4),
    dict(name="Self-service ordering", node_type="deliverable", sequence=2),
    dict(name="Order API", parent="Self-service ordering", node_type="work_package",
         start=-38, end=-18, effort="120.00", method="bottom_up", confidence="high",
         status="in_progress", sequence=1),
    dict(name="Cart UI", parent="Self-service ordering", node_type="work_package",
         start=-38, end=-8, effort="96.00", method="top_down", confidence="medium",
         status="in_progress", sequence=2),
    dict(name="Checkout integration", parent="Self-service ordering", node_type="work_package",
         start=-5, end=25, effort="140.00", method="bottom_up", confidence="low",
         status="planned", sequence=3),
    dict(name="Returns module", node_type="deliverable", sequence=3),
    dict(name="Returns portal UI", parent="Returns module", node_type="work_package",
         start=20, end=55, effort="88.00", method="analogous", confidence="medium",
         status="planned", sequence=1),
    dict(name="Refund service hooks", parent="Returns module", node_type="work_package",
         start=55, end=75, effort="56.00", method="parametric", confidence="low",
         status="planned", sequence=2),
]

#: Deliverable 1's pairs plus the cross-deliverable chain; one SS link, one lag, one lead.
ACTIVE_DEPS = [
    ("Requirements workshops", "UX design: ordering", "finish_to_start", 0),
    ("Requirements workshops", "Technical spike: SSO", "finish_to_start", 2),
    ("Technical spike: SSO", "Order API", "finish_to_start", 0),
    ("Order API", "Cart UI", "start_to_start", 0),
    ("Cart UI", "Checkout integration", "finish_to_start", 3),
    ("Checkout integration", "Refund service hooks", "finish_to_start", -1),
    ("UX design: ordering", "Returns portal UI", "finish_to_start", 0),
]

ACTIVE_MILESTONES = [
    dict(name="Discovery gate passed", gate=True, target=-20, actual=-19, status="achieved",
         entry="Workshops held, UX signed off, SSO spike concluded.",
         exit="Client product owner accepts scope for release 3."),
    dict(name="Beta ordering live", target=35, status="in_review",
         anchor="Checkout integration",
         description="Ordering open to a beta cohort of customers."),
    dict(name="Go/no-go: returns module", gate=True, target=70, status="planned",
         entry="Returns UI demoable end to end on staging.",
         exit="Refund service integration signed off by finance."),
]

#: The chartered project — mid-planning, a smaller tree and a two-link chain.
CHARTERED_WBS = [
    dict(name="Scorecard framework", node_type="deliverable", sequence=1),
    dict(name="Metric definitions", parent="Scorecard framework", node_type="work_package",
         start=5, end=25, effort="60.00", method="bottom_up", confidence="medium",
         status="planned", sequence=1),
    dict(name="Data collection pipeline", parent="Scorecard framework",
         node_type="work_package", start=20, end=60, effort="110.00", method="top_down",
         confidence="low", status="planned", sequence=2),
    dict(name="Quarterly publication", node_type="deliverable", sequence=2),
    dict(name="Publishing workflow", parent="Quarterly publication", node_type="work_package",
         start=45, end=90, effort="70.00", method="analogous", confidence="medium",
         status="planned", sequence=1),
]

CHARTERED_DEPS = [
    ("Metric definitions", "Data collection pipeline", "finish_to_start", 0),
    ("Data collection pipeline", "Publishing workflow", "finish_to_start", 5),
]

CHARTERED_MILESTONES = [
    dict(name="Gate: metrics agreed", gate=True, target=25, status="in_review",
         entry="Draft metric pack circulated to tier-1 suppliers.",
         exit="Procurement council signs the metric definitions."),
    dict(name="First scorecard published", target=95, status="planned"),
    dict(name="Supplier comms pack ready", target=40, status="planned"),
]

#: The draft project — sketch rows only: no dependencies, no baselines, nothing achieved.
DRAFT_WBS = [
    dict(name="Fleet programme setup", node_type="deliverable", sequence=1),
    dict(name="Vehicle lifecycle audit", parent="Fleet programme setup",
         node_type="work_package", start=30, end=60, effort="40.00", method="top_down",
         confidence="low", status="planned", sequence=1),
    dict(name="Leasing market scan", parent="Fleet programme setup", node_type="work_package",
         start=45, end=90, effort="24.00", method="analogous", confidence="low",
         status="planned", sequence=2),
]

DRAFT_MILESTONES = [
    dict(name="Fleet programme kickoff", target=95, status="planned"),
    dict(name="Replacement strategy chosen", target=150, status="planned"),
    dict(name="Board review", gate=True, target=180, status="planned",
         entry="Lifecycle audit and market scan concluded.",
         exit="Board approves the five-year replacement plan."),
]


class Command(BaseCommand):
    help = ("Seed Module 7 Project Management demo data (7.1 Initiation, 7.2 Planning, "
            "7.3 Resourcing, 7.4 Cost & Budget, 7.5 Risk & Issue Management, "
            "7.6 Quality Management, 7.7 Scope & Requirements Management, "
            "7.8 Task & Work Management, 7.9 Collaboration & Communication, "
            "7.10 Document & Knowledge Management).")
    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help=("Delete ALL projects rows for ALL tenants before seeding "
                  "(knowledge entries, standards, document revisions, documents, folders, "
                  "notifications, action items, agenda items, document shares, messages, "
                  "meetings, channels, checklist items, task blocks, scope verifications, "
                  "scope change requests, scope items, requirements, quality defects, "
                  "deliverable inspections, quality reviews, quality plans, escalations, issues, "
                  "response actions, risks, expenses, budget lines, control accounts, budget "
                  "revisions, time entries, allocations, resource profiles, baselines, "
                  "milestones, dependencies, tasks, kickoffs, stakeholders, projects, requests) "
                  "- not just seeder-created ones."))

    @staticmethod
    def _purge_docmgt_files():
        """Remove 7.10's two MEDIA_ROOT subtrees and return how many files went.

        `--flush` clears the rows; this clears the BYTES. It runs inside the flush only, so a plain
        re-seed (which is guarded per tenant and writes no new file for an existing row) never
        touches the store.
        """
        import os
        import shutil

        from django.conf import settings

        removed = 0
        for prefix in ("projects/documents", "projects/templates"):
            path = os.path.join(settings.MEDIA_ROOT, *prefix.split("/"))
            if not os.path.isdir(path):
                continue
            removed += sum(len(files) for _root, _dirs, files in os.walk(path))
            shutil.rmtree(path, ignore_errors=True)
        return removed

    def handle(self, *args, **options):
        if options["flush"]:
            # Children first: dependencies and milestones hang off tasks, tasks and baselines
            # hang off projects, requests own the converted_project link (SET_NULL). 7.3's rows
            # hang off all of the above, so they go before everything else. 7.4's hang off
            # projects/tasks/revisions/accounts: expenses first, then lines, then the accounts
            # and revisions they point at. 7.5's hang off projects/tasks/risks/issues: the
            # escalation is the deepest child, then the issues (which point at risks), then the
            # response actions, then the risks. 7.6's hang off projects/tasks/plans/inspections/
            # issues: the defect is the deepest child, then the inspections and the reviews (both
            # of which point at plans), then the plans. 7.8's checklist items and blocks hang off
            # tasks, so they go before ProjectTask as well. 7.9's notifications hang off the
            # channel, the message, the task and the meeting — all four — so they go first of
            # everything; then the meeting's two children, then the shares (which hang off the
            # channel and the project), then the messages, then the meetings and channels.
            #
            # 7.10's rows are ordered by their PROTECT edge as much as by their FK depth: a
            # revision hangs off its document, a document is PROTECTed by its folder, and a
            # folder nests inside its parent — so revisions go first, then the documents, then
            # the folders. `ProjectFolder.parent` is a CASCADE self-FK, so one folder delete
            # would already take the subtree; the documents are deleted EXPLICITLY rather than
            # left to the PROTECT edge to refuse the folder delete.
            ProjectNotification.objects.all().delete()
            MeetingActionItem.objects.all().delete()
            MeetingAgendaItem.objects.all().delete()
            DocumentShare.objects.all().delete()
            ChannelMessage.objects.all().delete()
            Meeting.objects.all().delete()
            Channel.objects.all().delete()
            KnowledgeEntry.objects.all().delete()
            DocumentTemplate.objects.all().delete()
            ProjectDocumentRevision.objects.all().delete()
            ProjectDocument.objects.all().delete()
            ProjectFolder.objects.all().delete()
            # 7.10 stores real BYTES under MEDIA_ROOT (`projects/documents/` for revisions,
            # `projects/templates/` for standards) and no row delete removes them — Django never
            # unlinks a FileField. A flush that cleared the tables but left the payloads behind
            # would keep the previous corpus downloadable at its old URLs for ever, which for a
            # module whose point is confidential and legally-held documents is a retention
            # failure rather than a tidy-up detail. These are the only two `upload_to` prefixes in
            # apps/projects, so nothing outside 7.10 lives in either subtree.
            purged = self._purge_docmgt_files()
            self.stdout.write(f"  removed {purged} stored 7.10 file(s) from MEDIA_ROOT")
            ProjectClientInvoice.objects.all().delete()
            VendorHandoff.objects.all().delete()
            SOWAmendment.objects.all().delete()
            StatementOfWork.objects.all().delete()
            ClientApprovalRequest.objects.all().delete()
            ClientPortalAccess.objects.all().delete()
            TaskChecklistItem.objects.all().delete()

            TaskBlock.objects.all().delete()
            QualityDefect.objects.all().delete()
            DeliverableInspection.objects.all().delete()
            QualityReview.objects.all().delete()
            QualityPlan.objects.all().delete()
            ProjectExpense.objects.all().delete()
            ProjectBudgetLine.objects.all().delete()
            CostControlAccount.objects.all().delete()
            BudgetRevision.objects.all().delete()
            ScopeVerification.objects.all().delete()
            ScopeChangeRequest.objects.all().delete()
            ScopeItem.objects.all().delete()
            Requirement.objects.all().delete()
            IssueEscalation.objects.all().delete()
            ProjectIssue.objects.all().delete()
            RiskResponseAction.objects.all().delete()
            ProjectRisk.objects.all().delete()
            ResourceTimeEntry.objects.all().delete()
            ResourceAllocation.objects.all().delete()
            ResourceProfile.objects.all().delete()
            ScheduleBaseline.objects.all().delete()
            TaskDependency.objects.all().delete()
            ProjectMilestone.objects.all().delete()
            ProjectTask.objects.all().delete()
            ProjectKickoff.objects.all().delete()
            ProjectStakeholder.objects.all().delete()
            Project.objects.all().delete()
            ProjectRequest.objects.all().delete()

        now = timezone.now()
        for tenant in Tenant.objects.all():
            self._seed_tenant(tenant, now)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Projects demo data seeded."))
        self._print_logins()

    # -- per-tenant -----------------------------------------------------------------------------

    def _seed_tenant(self, tenant, now):
        org_unit = OrgUnit.objects.filter(tenant=tenant).order_by("id").first()
        party = self._client(tenant)
        users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
        if not org_unit or not party or not users:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: missing OrgUnit/Party/users - run seed_core and "
                f"seed_accounts first. Skipping."))
            return

        if ProjectRequest.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: project requests already exist. "
                              f"Use --flush to re-seed.")
        else:
            currency = self._currency()
            requester, approver = users[0], users[-1]
            sponsor = users[1] if len(users) > 1 else approver
            manager = users[2] if len(users) > 2 else approver
            with transaction.atomic():
                requests = self._requests(tenant, now, org_unit, party, currency,
                                          requester, approver)
                converted = self._convert(tenant, requests, now)
                projects = self._projects(tenant, now, org_unit, party, sponsor, manager,
                                          converted)
                # Select by identity, never by list position: _projects() returns TWO rows
                # instead of three whenever _convert() yields None, which silently shifts every
                # index — the stakeholders would land on the standalone draft and _activities
                # would IndexError. (_kickoffs picks its two rows by status, same pattern.)
                chartered = next((p for p in projects if p.request_id is not None), None)
                active = next((p for p in projects if p.status == "active"), None)
                self._stakeholders(tenant, chartered, party, users, manager)
                self._kickoffs(tenant, now, projects)
                self._activities(tenant, now, active, manager)
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: {len(requests)} requests, {len(projects)} projects, "
                f"{ProjectStakeholder.objects.filter(tenant=tenant).count()} stakeholders, "
                f"{ProjectKickoff.objects.filter(tenant=tenant).count()} kickoffs."))

        # 7.2 has its OWN guard so an already-seeded workspace (7.1's guard above) still gets
        # its planning rows on this run's first execution.
        self._planning(tenant, now)
        # 7.3 has its OWN guard too, same reasoning as 7.2's.
        self._resourcing(tenant, now)
        # 7.4 has its OWN guard, same reasoning again.
        self._cost(tenant, now)
        # 7.5 has its OWN guard too — the risk register, its response actions, the issue log and
        # the recorded escalation path.
        self._risk(tenant, now)
        # 7.6 has its OWN guard as well — the quality plans, the review register, the inspections
        # and the punch list. The plans/reviews/inspections are seeded BEFORE the defects: the
        # defect rows FK the other three, so they are the children here.
        self._quality(tenant, now)
        # 7.7 has its OWN guard too — the requirement register with its traceability links, the
        # boundary/assumption/constraint registry, the CCB change register and the acceptance log.
        self._scope(tenant, now)
        # 7.8 has its OWN guard as well — the execution layer extends 7.2's tasks IN PLACE
        # (assignee/priority/MoSCoW/Eisenhower/percent_complete + the actual stamps) plus the
        # checklist and block registers. Nothing here creates a task.
        self._taskwork(tenant, now)
        # 7.9 has its OWN guard too — the collaboration layer: channels and their threads, the
        # shared-document register, meetings with their agendas/minutes/actions, and the
        # notification inbox. Nothing here creates a project or a task; it reuses both.
        self._collab(tenant, now)
        # 7.10 has its OWN guard as well — the document repository: the folder tree, the
        # controlled documents with their approved-revision chains, the tenant-wide standards
        # library and the knowledge register. It reuses the projects, tasks, milestones and
        # users every block above already created; nothing here invents a project.
        self._docmgt(tenant, now)
        # 7.11 has its OWN guard as well — the time & attendance tracking layer: standard
        # activity codes, overtime calculation policies, project overtime records, and
        # activity/billable updates on time entries.
        self._time_attendance(tenant, now)
        # 7.12 Portfolio & Program Management: investment portfolios, delivery programs,
        # weighted multi-criteria investment scoring, and cross-project program dependencies.
        self._portfolio_management(tenant, now)
        # 7.13 Agile & Scrum Management: sprints, epics, release trains, impediments,
        # retrospectives, and in-place story point assignments.
        self._agile_scrum(tenant, now)
        # 7.14 Client & External Collaboration: client portal access, approval requests,
        # SOWs & amendments, vendor handoffs, and client billing schedules.
        self._client_collaboration(tenant, now)



    # -- 7.2 planning ---------------------------------------------------------------------------

    def _planning(self, tenant, now):
        """WBS + dependencies + milestones + baselines, sized to each project's stage.

        Guarded per tenant. The ACTIVE project carries the full plan: an 11-node WBS, the
        dependency network (one long FS chain that is the critical path, one SS link, one lagged
        and one led link), an achieved discovery gate plus two live milestones, and the frozen
        baseline the completed kickoff acknowledged. The chartered project is mid-planning (a
        smaller WBS, a two-link chain, a gate in review, a what-if). The draft has sketch nodes
        and a planned milestone — no dependencies, no baselines: you don't freeze a plan for a
        project whose charter isn't approved.
        """
        if ProjectTask.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: planning rows already exist. "
                              f"Use --flush to re-seed.")
            return
        projects = list(Project.objects.filter(tenant=tenant))
        active = next((p for p in projects if p.status == "active"), None)
        chartered = next((p for p in projects if p.status == "chartered"), None)
        draft = next((p for p in projects if p.status == "draft"), None)
        # Any project's manager — only used as the WBS node owner; None is a valid owner.
        manager = next((p.project_manager for p in projects if p.project_manager_id), None)
        today = timezone.localdate()

        with transaction.atomic():
            if active is not None:
                tasks = self._wbs(tenant, active, manager, today, ACTIVE_WBS)
                self._deps(tenant, tasks, ACTIVE_DEPS)
                self._milestones(tenant, active, tasks, today, ACTIVE_MILESTONES)
                self._baseline(tenant, active, "Release 3 baseline v1", "baseline",
                               is_active=True, frozen_offset=58)
                self._baseline(tenant, active, "Compression experiment: crash checkout",
                               "what_if", strategy_note="Crash the checkout integration by "
                               "adding a second engineer (4 weeks -> 3).")
            if chartered is not None:
                tasks = self._wbs(tenant, chartered, manager, today, CHARTERED_WBS)
                self._deps(tenant, tasks, CHARTERED_DEPS)
                self._milestones(tenant, chartered, tasks, today, CHARTERED_MILESTONES)
                self._baseline(tenant, chartered, "Scorecard rollout: publish-only scenario",
                               "what_if", strategy_note="Fast-track the data-collection "
                               "package by starting it before design sign-off.")
            if draft is not None:
                self._wbs(tenant, draft, manager, today, DRAFT_WBS)
                self._milestones(tenant, draft, {}, today, DRAFT_MILESTONES)

        if ProjectTask.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: {ProjectTask.objects.filter(tenant=tenant).count()} WBS "
                f"nodes, {TaskDependency.objects.filter(tenant=tenant).count()} dependencies, "
                f"{ProjectMilestone.objects.filter(tenant=tenant).count()} milestones, "
                f"{ScheduleBaseline.objects.filter(tenant=tenant).count()} baselines."))

    # -- 7.3 resourcing -------------------------------------------------------------------------

    def _resourcing(self, tenant, now):
        """Resource pool + bookings + time entries, guarded per tenant.

        The pool reuses the workspace's existing EmployeeProfiles (one pool row each, varied
        capacities incl. a 24h part-timer) and the first Party as a windowed contractor — never
        a second person master. The allocations exercise every booking status, all three
        magnitude units, both placeholder kinds (project-linked and request-linked) and a
        released→successor substitution chain. The time entries cover all four statuses across
        three ISO weeks; the submitted trio IS the approval queue and the approved past rows are
        what the actuals-to-plan section compares. A workspace without an active project or an
        unconverted approved request still gets its pool — only the rows that would have used
        the missing anchor are skipped, never a crash.
        """
        from apps.hrm.models import EmployeeProfile

        users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
        parties = list(Party.objects.filter(tenant=tenant).order_by("id"))
        if not users or not parties:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: missing users/Party - run seed_core and seed_accounts "
                f"first. Skipping resourcing."))
            return
        if ResourceProfile.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: resource rows already exist. "
                              f"Use --flush to re-seed.")
            return

        org_unit = OrgUnit.objects.filter(tenant=tenant).order_by("id").first()
        employees = list(EmployeeProfile.objects.filter(tenant=tenant).order_by("id"))
        today = timezone.localdate()
        active = Project.objects.filter(tenant=tenant, status="active").first()
        pipeline_request = ProjectRequest.objects.filter(
            tenant=tenant, status="approved", converted_project__isnull=True).first()
        manager = (active.project_manager if active and active.project_manager_id
                   else users[0])

        with transaction.atomic():
            profiles = self._pool(tenant, org_unit, employees, parties, today)
            if active is not None:
                self._allocations(tenant, active, profiles, manager, today)
                if pipeline_request is not None:
                    self._request_demand(tenant, pipeline_request, manager, today)
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  {tenant.name}: no unconverted approved request - skipping the "
                        f"request-linked demand row."))
                self._time_entries(tenant, active, profiles, manager, today, now)
            else:
                self.stdout.write(self.style.WARNING(
                    f"  {tenant.name}: no active project - skipping the allocation and time "
                    f"entry rows."))

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {ResourceProfile.objects.filter(tenant=tenant).count()} "
            f"resources, {ResourceAllocation.objects.filter(tenant=tenant).count()} "
            f"allocations, {ResourceTimeEntry.objects.filter(tenant=tenant).count()} "
            f"time entries."))

    def _pool(self, tenant, org_unit, employees, parties, today):
        """Five pool rows: four internal (one per EmployeeProfile, capacities 40/40/32/24) and
        one windowed contractor. A workspace with fewer employees than four falls back to
        party-keyed internal rows — the exactly-one-of clean() allows party-keyed internals."""
        roles = ["Backend developer", "Frontend developer", "Data engineer", "QA analyst"]
        capacities = [Decimal("40.00"), Decimal("40.00"), Decimal("32.00"), Decimal("24.00")]
        targets = [80, 80, 80, 50]
        skills = ["Python, Django, Airflow", "React, TypeScript", "Python, dbt, SQL",
                  "Playwright, pytest"]
        profiles = []
        for i in range(4):
            kw = dict(
                tenant=tenant, resource_type="internal", default_role=roles[i],
                org_unit=org_unit, skill_summary=skills[i],
                weekly_capacity_hours=capacities[i], utilization_target_pct=targets[i])
            if i < len(employees):
                kw["employee"] = employees[i]
            else:
                kw["party"] = parties[i % len(parties)]
            profile = ResourceProfile(**kw)
            profile.save()
            profiles.append(profile)
        contractor = ResourceProfile(
            tenant=tenant, party=parties[0], resource_type="contractor",
            default_role="Site reliability engineer", org_unit=org_unit,
            skill_summary="Terraform, AWS, Go", weekly_capacity_hours=Decimal("40.00"),
            available_from=today - timedelta(days=30),
            available_to=today + timedelta(days=90))
        contractor.save()
        profiles.append(contractor)
        return profiles

    def _allocations(self, tenant, active, profiles, manager, today):
        """Nine project-linked bookings on the active project: every status, all three units,
        two placeholders, and the released→successor substitution chain (rows 8 and 9)."""
        first_task = ProjectTask.objects.filter(
            tenant=tenant, project=active, node_type="work_package"
        ).order_by("sequence", "id").first()

        def ral(**kw):
            obj = ResourceAllocation(tenant=tenant, requested_by=manager, **kw)
            obj.save()
            return obj

        ral(project=active, resource=profiles[0], role_name="Backend developer",
            skill_requirements="Python, Django", allocation_unit="hours_per_week",
            # 48h/wk against RSP-00001's 40h capacity — one seeded cell deliberately exceeds
            # capacity so the board's over-allocation alert state is reachable from seed data.
            hours_per_week=Decimal("48.00"),
            start_date=today - timedelta(days=14), end_date=today + timedelta(days=28),
            booking_status="firm")
        ral(project=active, resource=profiles[1], role_name="Frontend developer",
            skill_requirements="React", allocation_unit="hours_per_week",
            hours_per_week=Decimal("12.00"), project_task=first_task,
            start_date=today - timedelta(days=7), end_date=today + timedelta(days=35),
            booking_status="firm")
        ral(project=active, resource=profiles[3], role_name="QA analyst",
            skill_requirements="Playwright", allocation_unit="pct_capacity", pct_capacity=50,
            start_date=today - timedelta(days=7), end_date=today + timedelta(days=35),
            booking_status="soft")
        ral(project=active, resource=None, role_name="Data engineer",
            skill_requirements="Python, Airflow", allocation_unit="hours_per_week",
            hours_per_week=Decimal("20.00"),
            start_date=today + timedelta(days=7), end_date=today + timedelta(days=49),
            booking_status="requested")
        ral(project=active, resource=None, role_name="QA analyst",
            allocation_unit="hours_per_week", hours_per_week=Decimal("10.00"),
            start_date=today - timedelta(days=21), end_date=today + timedelta(days=21),
            booking_status="soft")
        ral(project=active, resource=profiles[0], role_name="Backend developer",
            allocation_unit="hours_per_week", hours_per_week=Decimal("16.00"),
            start_date=today - timedelta(days=90), end_date=today - timedelta(days=30),
            booking_status="completed")
        released = ral(project=active, resource=profiles[1], role_name="Frontend developer",
                       allocation_unit="hours_per_week", hours_per_week=Decimal("12.00"),
                       start_date=today - timedelta(days=28), end_date=today + timedelta(days=28),
                       booking_status="released")
        ral(project=active, resource=profiles[2], role_name="Frontend developer",
            allocation_unit="hours_per_week", hours_per_week=Decimal("12.00"),
            start_date=today - timedelta(days=28), end_date=today + timedelta(days=28),
            booking_status="firm", substitute_of=released)
        ral(project=active, resource=profiles[4], role_name="Site reliability engineer",
            skill_requirements="Terraform", allocation_unit="total_hours",
            total_hours=Decimal("40.00"),
            start_date=today + timedelta(days=7), end_date=today + timedelta(days=21),
            booking_status="soft")

    def _request_demand(self, tenant, request_row, manager, today):
        """The pipeline-demand placeholder: an unconverted approved request still needing a
        role — the coverage-gap flag on the demand board."""
        ResourceAllocation(
            tenant=tenant, project_request=request_row, resource=None,
            role_name="Backend developer", skill_requirements="Django",
            allocation_unit="hours_per_week", hours_per_week=Decimal("20.00"),
            start_date=today + timedelta(days=14), end_date=today + timedelta(days=70),
            booking_status="requested", requested_by=manager).save()

    def _time_entries(self, tenant, active, profiles, manager, today, now):
        """Sixteen entries across resources #1-#3 and three ISO weeks: nine approved past
        (6h each, on the active project, incl. the remainder row), three submitted this week
        (the approval queue), two drafts, one rejected with its decision note, and one approved
        non-project row."""
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        prev_monday = this_monday - timedelta(days=14)

        def rte(resource, day, hours, status="approved", project=active, description="",
                decision_note=""):
            row = ResourceTimeEntry(
                tenant=tenant, resource=resource, project=project, entry_date=day,
                hours=hours, status=status, task_description=description,
                decision_note=decision_note)
            if status == "submitted":
                row.submitted_at = now
            if status in ("approved", "rejected"):
                row.approved_by = manager
                row.approved_at = now
            row.save()

        r1, r2, r3 = profiles[0], profiles[1], profiles[2]
        six = Decimal("6.00")
        rte(r1, prev_monday, six, description="Order API work")
        rte(r2, prev_monday + timedelta(days=1), six, description="Checkout UI")
        rte(r3, prev_monday + timedelta(days=2), six, description="Data model")
        rte(r1, prev_monday + timedelta(days=3), six, description="Order API tests")
        rte(r2, last_monday, six, description="Checkout UI polish")
        rte(r3, last_monday + timedelta(days=1), six, description="ETL pipeline")
        rte(r1, last_monday + timedelta(days=2), six, description="Refund hooks")
        rte(r2, last_monday + timedelta(days=3), six, description="Spike cleanup")
        rte(r3, last_monday + timedelta(days=4), six, description="Warehouse backfill")
        rte(r1, this_monday, six, status="submitted", description="Cart integration")
        rte(r1, this_monday + timedelta(days=1), six, status="submitted",
            description="Cart integration (cont.)")
        rte(r2, this_monday + timedelta(days=2), six, status="submitted",
            description="Checkout regression fixes")
        rte(r3, this_monday + timedelta(days=1), Decimal("5.00"), status="draft",
            description="dbt model review")
        rte(r3, this_monday + timedelta(days=2), Decimal("4.00"), status="draft",
            description="Dashboard mocks")
        rte(r2, this_monday, six, status="rejected",
            description="Support escalation",
            decision_note="Client call overran - re-log the extra hour under support.")
        rte(r1, this_monday + timedelta(days=3), Decimal("2.00"), project=None,
            description="Internal training")

    # -- 7.4 cost & budget --------------------------------------------------------------------------

    def _cost(self, tenant, now):
        """Budget revisions + control accounts + budget lines + expenses, guarded per tenant.

        Revision 0 of the active and chartered projects is approved AND activated — it IS the
        cost baseline the EVM panel measures; the draft project's revision 0 stays draft. One
        control account per deliverable of the active project, with progress + posted spend
        tuned so all three CPI health bands appear: CA-1 over (spend past earned, available
        negative), CA-2 watch (CPI between 0.95 and 1.00), CA-3 under (nothing posted yet). A
        pending-approval revision 1 on the active project is the change request an approver
        weighs (amount_delta +50,000.00). Expenses cover every entry type and status: posted
        commitments whose ``source_number`` is a PO STRING (soft reference — 4.x/6.x own the PO
        engine), posted actuals and accruals, one void row (visible, not counting) and one
        draft (burns nothing). CA-3 deliberately receives no posted actual/accrual: its
        "under" band is the no-actuals CPI-None case.
        """
        if BudgetRevision.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: cost rows already exist. "
                              f"Use --flush to re-seed.")
            return
        projects = list(Project.objects.filter(tenant=tenant))
        active = next((p for p in projects if p.status == "active"), None)
        chartered = next((p for p in projects if p.status == "chartered"), None)
        draft = next((p for p in projects if p.status == "draft"), None)
        currency = self._currency()
        vendor = Party.objects.filter(tenant=tenant).order_by("id").first()
        manager = next((p.project_manager for p in projects if p.project_manager_id), None)
        today = timezone.localdate()

        def revision(project, no, title, status, reason, activate=False):
            obj = BudgetRevision(
                tenant=tenant, project=project, revision_no=no, title=title,
                currency=currency, status=status, reason=reason, requested_by=manager,
                requested_at=now if status != "draft" else None,
                decided_by=manager if status in ("approved", "rejected") else None,
                decided_at=now if status in ("approved", "rejected") else None,
                activated_at=now if activate else None)
            obj.save()
            return obj

        def line(rev, category, amount, wbs=None, account=None, note=""):
            obj = ProjectBudgetLine(
                tenant=tenant, budget_revision=rev, project=rev.project,
                category=category, amount=Decimal(amount), wbs_node=wbs,
                control_account=account, note=note)
            obj.save()
            return obj

        def account(project, code, name, wbs, contingency, pct, status="active"):
            obj = CostControlAccount(
                tenant=tenant, project=project, code=code, name=name, wbs_node=wbs,
                contingency=Decimal(contingency), percent_complete=Decimal(pct),
                status=status,
                note="Progress attested at the weekly cost review; task-level execution "
                     "supersedes it.")
            obj.save()
            return obj

        def expense(proj, acct, entry_type, amount, day_offset, status="posted",
                    source_kind="manual", source_number="", vendor_row=None,
                    description=""):
            obj = ProjectExpense(
                tenant=tenant, project=proj, control_account=acct, entry_type=entry_type,
                source_kind=source_kind, source_number=source_number,
                vendor=vendor_row, amount=Decimal(amount), currency=currency,
                entry_date=today + timedelta(days=day_offset), status=status,
                description=description)
            obj.save()
            return obj

        with transaction.atomic():
            if active is not None:
                tasks = {t.name: t for t in ProjectTask.objects.filter(tenant=tenant,
                                                                       project=active)}
                base = revision(active, 0, "Original budget — release 3", "approved",
                                "Bottom-up estimate from the WBS work packages, approved at "
                                "the discovery gate.", activate=True)
                ca1 = account(active, "CA-1.0", "Discovery & design",
                              tasks.get("Discovery & design"), "10000.00", "95.00")
                ca2 = account(active, "CA-2.0", "Self-service ordering",
                              tasks.get("Self-service ordering"), "20000.00", "50.00")
                ca3 = account(active, "CA-3.0", "Returns module",
                              tasks.get("Returns module"), "15000.00", "0.00")
                line(base, "labor", "60000.00", tasks.get("Requirements workshops"), ca1)
                line(base, "labor", "80000.00", tasks.get("UX design: ordering"), ca1)
                line(base, "material", "15000.00", tasks.get("Technical spike: SSO"), ca1)
                line(base, "labor", "150000.00", tasks.get("Order API"), ca2)
                line(base, "labor", "120000.00", tasks.get("Cart UI"), ca2)
                line(base, "subcontract", "90000.00", tasks.get("Checkout integration"), ca2)
                line(base, "equipment", "40000.00", tasks.get("Returns portal UI"), ca3)
                line(base, "labor", "60000.00", tasks.get("Refund service hooks"), ca3)
                line(base, "overhead", "18000.00",
                     note="Workspace, tooling and licences — not charged to a control account.")
                line(base, "contingency", "25000.00",
                     note="Management-held reserve outside the control accounts.")
                line(base, "other", "5000.00",
                     note="Sundry costs — bank charges, printing and couriers.")

                # The change request under approval: a full replacement budget (a revision
                # carries the whole line set, so amount_delta reads total-vs-total) that adds
                # security and monitoring scope and raises the Cart UI line by 10,000.
                change = revision(active, 1, "Scope change: security & monitoring", "pending_approval",
                                  "Client security review asked for hardening and observability "
                                  "before beta.")
                for src in base.lines.all():
                    line(change, src.category, src.amount, src.wbs_node, src.control_account,
                         note=src.note)
                line(change, "labor", "25000.00", account=ca2, note="NEW: security hardening "
                                                                     "of the order API.")
                line(change, "equipment", "15000.00", account=ca2, note="NEW: monitoring "
                                                                        "tooling.")
                cl = change.lines.filter(category="labor",
                                         wbs_node=tasks.get("Cart UI")).first()
                if cl is not None:
                    cl.amount = Decimal("130000.00")
                    cl.save()

                # CPI bands: CA-1 over (160,000 posted vs 147,250 earned), CA-2 watch
                # (185,000 posted vs 180,000 earned -> CPI 0.97), CA-3 under (nothing posted).
                expense(active, ca1, "actual", "95000.00", -50, source_kind="purchase_order",
                        source_number="PO-00021", vendor_row=vendor,
                        description="Discovery subcontract")
                expense(active, ca1, "actual", "40000.00", -45,
                        source_kind="supplier_invoice", source_number="SIV-00102",
                        vendor_row=vendor, description="Research incentives")
                expense(active, ca1, "accrual", "25000.00", -35, source_kind="accrual",
                        description="Design contractor accrual")
                expense(active, ca1, "actual", "8000.00", -15,
                        source_kind="supplier_invoice", source_number="SIV-00131",
                        vendor_row=vendor, status="void",
                        description="Duplicate invoice — voided, does not count")
                expense(active, ca2, "actual", "105000.00", -30, source_kind="purchase_order",
                        source_number="PO-00031", vendor_row=vendor,
                        description="Order API build sprint")
                expense(active, ca2, "actual", "70000.00", -20,
                        source_kind="supplier_invoice", source_number="SIV-00119",
                        vendor_row=vendor, description="Cart UI contractor")
                expense(active, ca2, "commitment", "45000.00", -5,
                        source_kind="purchase_order", source_number="PO-00044",
                        vendor_row=vendor, description="Checkout integration subcontract")
                expense(active, ca2, "commitment", "12000.00", 10,
                        source_kind="purchase_order", source_number="PO-00058",
                        vendor_row=vendor, description="Load-testing rig")
                expense(active, ca2, "accrual", "7000.00", -2, source_kind="accrual",
                        description="Cloud spend accrual")
                expense(active, ca2, "accrual", "3000.00", -1, source_kind="accrual",
                        description="Monitoring licences accrual")
                expense(active, ca3, "commitment", "20000.00", 3,
                        source_kind="purchase_order", source_number="PO-00051",
                        vendor_row=vendor, description="Returns kiosk hardware")
                expense(active, ca2, "actual", "5000.00", 1, status="draft",
                        description="Draft: awaiting the vendor's final invoice")
            if chartered is not None:
                tasks = {t.name: t for t in ProjectTask.objects.filter(tenant=tenant,
                                                                       project=chartered)}
                base = revision(chartered, 0, "Original budget — scorecard rollout",
                                "approved",
                                "Planning-stage estimate; approved alongside the charter.",
                                activate=True)
                line(base, "labor", "60000.00", tasks.get("Metric definitions"))
                line(base, "equipment", "45000.00", tasks.get("Data collection pipeline"))
                line(base, "labor", "55000.00", tasks.get("Publishing workflow"))
                line(base, "subcontract", "30000.00",
                     note="Data migration partner — booking pending.")
                line(base, "overhead", "12000.00")
                line(base, "contingency", "15000.00")
            if draft is not None:
                tasks = {t.name: t for t in ProjectTask.objects.filter(tenant=tenant,
                                                                       project=draft)}
                sketch = revision(draft, 0, "Draft budget — fleet programme", "draft",
                                  "First sketch to size the programme — not yet submitted.")
                line(sketch, "labor", "30000.00", tasks.get("Vehicle lifecycle audit"))
                line(sketch, "material", "8000.00", tasks.get("Leasing market scan"))
                line(sketch, "contingency", "10000.00")

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {BudgetRevision.objects.filter(tenant=tenant).count()} budget "
            f"revisions, {ProjectBudgetLine.objects.filter(tenant=tenant).count()} budget "
            f"lines, {CostControlAccount.objects.filter(tenant=tenant).count()} control "
            f"accounts, {ProjectExpense.objects.filter(tenant=tenant).count()} expenses."))

    def _risk(self, tenant, now):
        """Risks + response actions + issues + escalations, guarded per tenant.

        The register is sized so the analysis and monitoring pages have something real to compute
        over: 17 rows per tenant (12 on the active project, 5 on the chartered one) so the
        register paginates, every one of the nine categories and both ``risk_type`` values appear,
        and the probability × impact pairs land rows in **all four severity bands** (low 1–3,
        medium 4–7, high 8–14, critical 15–25). All six statuses are represented, one row is
        ``realized`` and carries the ``ProjectIssue`` the realize verb would have minted, and one
        is ``closed`` with a lesson so the monitoring page's lessons lens is non-empty.

        ``identified_date`` values are spread over ~4 months on purpose: the burn-down aggregates
        by month, and a register seeded entirely inside one period would render a one-row chart
        and prove nothing. Three live rows carry a past ``review_date`` so the review queue and the
        ``?review_due=1`` lens have hits.

        Response actions implement bullet 3 on the top risks (one completed, one overdue, the rest
        planned/in-progress). Issues cover all four severities with two resolved (stamps written)
        and one escalated to level 2 with a two-step ``IssueEscalation`` path — the escalation
        register is otherwise empty on a fresh workspace.
        """
        if ProjectRisk.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: risk rows already exist. "
                              f"Use --flush to re-seed.")
            return
        projects = list(Project.objects.filter(tenant=tenant))
        active = next((p for p in projects if p.status == "active"), None)
        chartered = next((p for p in projects if p.status == "chartered"), None)
        users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
        manager = next((p.project_manager for p in projects if p.project_manager_id), None)
        owner = users[1] if len(users) > 1 else manager
        today = timezone.localdate()

        def risk(project, title, category, risk_type, probability, impact, cost_impact,
                 status="identified", wbs=None, strategy="mitigate", day_offset=0,
                 review_offset=None, description="", trigger="", contingency_plan="",
                 residual=None, lessons=""):
            obj = ProjectRisk(
                tenant=tenant, project=project, wbs_node=wbs, title=title,
                description=description or f"{title}. Identified during the project's risk review.",
                cause="", effect="", category=category, risk_type=risk_type,
                probability=probability, impact=impact, cost_impact=Decimal(cost_impact),
                response_strategy=strategy, response_note="", trigger=trigger,
                contingency_plan=contingency_plan, status=status, owner=owner,
                identified_by=owner, identified_date=today - timedelta(days=day_offset),
                review_date=(today + timedelta(days=review_offset)
                             if review_offset is not None else None),
                residual_probability=residual[0] if residual else None,
                residual_impact=residual[1] if residual else None,
                lessons_learned=lessons,
                closed_at=now if status == "closed" else None)
            obj.save()
            return obj

        def action(risk_row, title, strategy, offset, cost, status="planned", trigger=""):
            obj = RiskResponseAction(
                tenant=tenant, risk=risk_row, title=title,
                description=f"{title} — the action that implements the risk's response strategy.",
                strategy=strategy, owner=owner,
                due_date=today + timedelta(days=offset), cost=Decimal(cost),
                trigger=trigger or "Activated when the risk's trigger condition is observed.",
                status=status,
                completed_at=now if status == "completed" else None)
            obj.save()
            return obj

        def issue(project, title, severity, status, wbs=None, risk_row=None, offset=0,
                  due_offset=None, description="", escalated_to=None, level=0,
                  resolved=False, lessons=""):
            obj = ProjectIssue(
                tenant=tenant, project=project, wbs_node=wbs, risk=risk_row, title=title,
                description=description or f"{title}. Raised from the weekly project review.",
                issue_type="issue", severity=severity, status=status, owner=owner,
                raised_by=owner, identified_date=today - timedelta(days=offset),
                due_date=(today + timedelta(days=due_offset) if due_offset is not None else None),
                escalation_level=level,
                escalated_to=escalated_to if level else None,
                escalated_at=now if level else None,
                root_cause=("Root cause established during the post-incident review."
                            if resolved else ""),
                resolution_note=("Resolved — the corrective action was verified at the "
                                 "following review." if resolved else ""),
                resolved_by=owner if resolved else None,
                resolved_at=now if resolved else None,
                lessons_learned=lessons)
            obj.save()
            return obj

        def escalation(issue_row, level, target_role, reason, outcome="", resolved=False):
            obj = IssueEscalation(
                tenant=tenant, issue=issue_row, level=level, target_role=target_role,
                target_user=owner, reason=reason, escalated_by=owner,
                outcome=outcome, resolved_at=now if resolved else None)
            obj.save()
            return obj

        with transaction.atomic():
            if active is not None:
                tasks = {t.name: t for t in ProjectTask.objects.filter(tenant=tenant,
                                                                       project=active)}
                r1 = risk(active, "Single sign-on dependency slips",
                          "technical", "threat", 5, 5, "250000.00", "response_planned",
                          tasks.get("Technical spike: SSO"), "mitigate", 118,
                          review_offset=14, residual=(3, 4),
                          trigger="The identity provider misses the integration milestone.",
                          contingency_plan="Fall back to the in-house credential store for "
                                           "release 3 and re-plan SSO for the next increment.")
                r2 = risk(active, "Checkout integration partner delays the interface",
                          "external", "threat", 3, 5, "180000.00", "assessing",
                          tasks.get("Checkout integration"), "transfer", 96, review_offset=-6,
                          trigger="The partner's sandbox does not pass certification on schedule.")
                r3 = risk(active, "Order API throughput below the target profile",
                          "technical", "threat", 4, 3, "120000.00", "monitoring",
                          tasks.get("Order API"), "mitigate", 74, review_offset=-11,
                          residual=(2, 3),
                          trigger="Load test shows p95 latency above the agreed budget.")
                r4 = risk(active, "Cart UI usability rework after first user testing",
                          "quality", "threat", 3, 3, "90000.00", "identified",
                          tasks.get("Cart UI"), "mitigate", 61)
                r5 = risk(active, "Returns module scope growth",
                          "organizational", "threat", 2, 5, "150000.00", "response_planned",
                          tasks.get("Returns module"), "avoid", 47, residual=(2, 3),
                          trigger="A stakeholder requests a returns capability outside the "
                                  "charter's in-scope list.")
                r6 = risk(active, "Refund service compliance review findings",
                          "compliance", "threat", 2, 3, "40000.00", "monitoring",
                          tasks.get("Refund service hooks"), "mitigate", 35, review_offset=-3)
                r7 = risk(active, "UX designer availability across two workstreams",
                          "resource", "threat", 3, 2, "30000.00", "identified",
                          tasks.get("UX design: ordering"), "mitigate", 28)
                r8 = risk(active, "Requirements workshop attendance below quorum",
                          "resource", "threat", 4, 1, "20000.00", "closed",
                          tasks.get("Requirements workshops"), "accept", 24,
                          lessons="Book the workshop two weeks out with named attendees. The "
                                  "one session that slipped cost a week of rework on the "
                                  "ordering journey.")
                r9 = risk(active, "Design system version drift across screens",
                          "technical", "threat", 1, 3, "15000.00", "identified",
                          tasks.get("UX design: ordering"), "accept", 18)
                r10 = risk(active, "Release documentation lags the build",
                           "other", "threat", 1, 2, "8000.00", "assessing", None, "accept", 11)
                r11 = risk(active, "Reusable SSO component for later projects",
                           "technical", "opportunity", 3, 3, "75000.00", "monitoring",
                           tasks.get("Technical spike: SSO"), "exploit", 9,
                           trigger="The spike produces a component the platform team can adopt.")
                r12 = risk(active, "Vendor invoice processing delay",
                           "cost", "threat", 4, 3, "60000.00", "realized", None, "mitigate", 5,
                           trigger="An invoice is not matched within the payment terms window.")

                action(r1, "Run the SSO spike as a time-boxed proof", "mitigate", 21, "12000.00",
                       "completed", "Spike kicks off when the partner confirms the interface.")
                action(r1, "Agree a written fallback with the platform team", "avoid", -4,
                       "4000.00", "in_progress",
                       "Activated if the partner misses the certification date.")
                action(r1, "Escalate the dependency to the steering group", "escalate", 30,
                       "0.00", "planned")
                action(r2, "Certify the partner sandbox early", "mitigate", -9, "6000.00",
                       "planned", "Starts as soon as the sandbox credentials arrive.")
                action(r2, "Add a contractual interface SLA to the partner agreement",
                       "transfer", 45, "2500.00", "planned")
                action(r3, "Tune the query plan and re-run the load test", "mitigate", 14,
                       "9000.00", "in_progress")
                action(r3, "Cache the product catalogue read path", "mitigate", 40, "15000.00",
                       "planned")

                issue(active, "Vendor invoice for the SSO spike is unmatched", "medium",
                      "in_progress", None, r12, 4, due_offset=6,
                      description="The realized vendor-invoice risk materialized: the "
                                  "invoice has no matching purchase order.")
                issue(active, "Load test fails the p95 latency target", "critical", "open",
                      tasks.get("Order API"), r3, 12, due_offset=3)
                esc_issue = issue(active, "Partner sandbox certification blocked on credentials",
                                  "high", "blocked", tasks.get("Checkout integration"), r2, 20,
                                  due_offset=-2, escalated_to=owner, level=2)
                issue(active, "Returns portal design review outstanding", "medium", "open",
                      tasks.get("Returns portal UI"), None, 8, due_offset=9)
                issue(active, "Workshop quorum missed for the ordering journey", "medium",
                      "resolved", tasks.get("Requirements workshops"), r8, 24, resolved=True,
                      lessons="Name the attendees and confirm them in writing — an open invite "
                              "does not produce a quorum.")
                issue(active, "Stale design-system tokens in the cart screens", "low", "resolved",
                      tasks.get("Cart UI"), None, 30, resolved=True,
                      lessons="Pin the design-system version in the build, not in a wiki page.")
                issue(active, "Refund service review notes outstanding", "low", "closed", None,
                      r6, 40)

                escalation(esc_issue, 1, "Project Manager",
                           "The partner's certification owner is unresponsive and the "
                           "interface date is at risk.", "Project manager took the "
                           "escalation and chased the partner directly.", resolved=True)
                escalation(esc_issue, 2, "Program Manager",
                           "Certification is still blocked after a week and the interface "
                           "date cannot absorb further delay.")

            if chartered is not None:
                tasks = {t.name: t for t in ProjectTask.objects.filter(tenant=tenant,
                                                                       project=chartered)}
                risk(chartered, "Metric definitions churn between stakeholders",
                     "organizational", "threat", 4, 2, "45000.00", "monitoring",
                     tasks.get("Metric definitions"), "mitigate", 33, review_offset=10)
                risk(chartered, "Data pipeline capacity for the quarterly volume",
                     "technical", "threat", 2, 3, "25000.00", "assessing",
                     tasks.get("Data collection pipeline"), "mitigate", 26)
                risk(chartered, "Publishing workflow ownership undecided",
                     "resource", "threat", 3, 2, "18000.00", "identified",
                     tasks.get("Publishing workflow"), "mitigate", 19)
                risk(chartered, "Quarterly publication cadence slips",
                     "schedule", "threat", 1, 2, "6000.00", "identified",
                     tasks.get("Quarterly publication"), "accept", 12)
                risk(chartered, "Benchmark data licensing opportunity",
                     "external", "opportunity", 2, 4, "50000.00", "monitoring", None, "exploit",
                     7, trigger="A benchmark provider offers a discounted multi-year licence.")

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {ProjectRisk.objects.filter(tenant=tenant).count()} risks, "
            f"{RiskResponseAction.objects.filter(tenant=tenant).count()} response actions, "
            f"{ProjectIssue.objects.filter(tenant=tenant).count()} issues, "
            f"{IssueEscalation.objects.filter(tenant=tenant).count()} escalations."))

    def _quality(self, tenant, now):
        """Quality plans + reviews + inspections + defects, guarded per tenant.

        Sized so the computed pages have something real to compute over: 4 plans (two
        deliverable-anchored and active, a superseded one and a draft so the frozen-row guards
        and the board's plan statuses render), 6 reviews covering every ``review_type`` with one
        improvement action overdue (the ``?overdue=1`` lens) and maturity scores on the assessed
        rows (the improvement page's computed score), 6 inspections covering all five types with
        one accepted (stamps written), one failed-and-pending, one still in the acceptance queue
        and planned rows ahead, and 6 defects across the severities and punch-list dispositions —
        two resolved/closed with stamps, one carrying the issue the ``qdf_raise_issue`` bridge
        would have minted, and the rest open so the acceptance board's punch-list counts are
        non-zero.

        ``identified_date`` values are spread over ~2 months so the improvement page's defect
        trend renders more than one period. ``inspected_date``/``resolved_at`` stamps follow the
        same spread.
        """
        if QualityPlan.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: quality rows already exist. "
                              f"Use --flush to re-seed.")
            return
        projects = list(Project.objects.filter(tenant=tenant))
        active = next((p for p in projects if p.status == "active"), None)
        chartered = next((p for p in projects if p.status == "chartered"), None)
        users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
        if not active or not users:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no active project or users - skipping quality."))
            return
        manager = next((p.project_manager for p in projects if p.project_manager_id), None)
        owner = users[1] if len(users) > 1 else manager
        inspector = users[-1] if len(users) > 2 else owner
        party = self._client(tenant)
        today = timezone.localdate()
        deliverables = {t.name: t for t in ProjectTask.objects.filter(
            tenant=tenant, project=active, node_type="deliverable")}
        gates = {m.name: m for m in ProjectMilestone.objects.filter(tenant=tenant,
                                                                    project=active)}
        discovery = deliverables.get("Discovery & design")
        ordering = deliverables.get("Self-service ordering")
        gate_milestone = gates.get("Discovery gate passed")
        chartered_deliverable = ProjectTask.objects.filter(
            tenant=tenant, project=chartered, node_type="deliverable").first()

        def plan(project, title, wbs=None, status="active", method="inspection",
                 standard="", review_offset=None, approved=False):
            obj = QualityPlan(
                tenant=tenant, project=project, wbs_node=wbs, title=title,
                description=f"{title}. The acceptance criteria this deliverable must satisfy.",
                acceptance_criteria=("- Functional criteria exercised end to end.\n"
                                     "- Documentation complete and reviewed.\n"
                                     "- Compliance mapping signed off."),
                verification_method=method, standard_reference=standard,
                regulatory_requirement="", owner=owner, status=status,
                planned_review_date=(today + timedelta(days=review_offset)
                                     if review_offset is not None else None),
                approved_by=owner if approved else None,
                approved_at=now if approved else None)
            obj.save()
            return obj

        def review(project, title, rtype, status="reported", wbs=None, plan_row=None,
                   offset=0, score=None, imp_status="n_a", imp_due=None, imp_action="",
                   checklist="", findings=""):
            obj = QualityReview(
                tenant=tenant, project=project, wbs_node=wbs, quality_plan=plan_row,
                title=title, scope=f"{title} — what was reviewed and against which baseline.",
                review_type=rtype,
                checklist=checklist or "- Process followed.\n- Artifacts produced.\n"
                                       "- Actions closed.",
                findings=findings or f"{title} concluded with observations recorded below.",
                reviewer=owner, review_date=today - timedelta(days=offset), status=status,
                maturity_score=score,
                improvement_action=imp_action,
                improvement_owner=owner if imp_status in ("planned", "in_progress") else None,
                improvement_due_date=(today + timedelta(days=imp_due)
                                      if imp_due is not None else None),
                improvement_status=imp_status,
                closed_at=now if status == "closed" else None)
            obj.save()
            return obj

        def inspection(project, title, itype, wbs=None, plan_row=None, milestone_row=None,
                       result="pending", decision="pending", status="planned",
                       planned_offset=0, inspected_offset=None, findings="",
                       accepted=False, acceptance_note="", party_row=None):
            obj = DeliverableInspection(
                tenant=tenant, project=project, wbs_node=wbs, quality_plan=plan_row,
                milestone=milestone_row, title=title,
                description=f"{title}. The protocol this inspection follows.",
                inspection_type=itype,
                planned_date=today + timedelta(days=planned_offset),
                inspected_date=(today - timedelta(days=inspected_offset)
                                if inspected_offset is not None else None),
                inspector=inspector, result=result, usage_decision=decision,
                findings=findings or f"{title} execution notes.",
                accepted_by=owner if accepted else None,
                accepted_by_party=party_row if accepted else None,
                accepted_at=now if accepted else None,
                acceptance_note=acceptance_note, status=status)
            obj.save()
            return obj

        def defect(project, title, severity, category, disposition, status, wbs=None,
                   plan_row=None, insp_row=None, issue_row=None, offset=0, due_offset=None,
                   resolved=False, lessons=""):
            obj = QualityDefect(
                tenant=tenant, project=project, wbs_node=wbs, quality_plan=plan_row,
                inspection=insp_row, project_issue=issue_row, title=title,
                description=f"{title}. Found while inspecting the deliverable.",
                defect_category=category, severity=severity, disposition=disposition,
                status=status, owner=owner,
                identified_date=today - timedelta(days=offset),
                due_date=(today + timedelta(days=due_offset)
                          if due_offset is not None else None),
                root_cause=("Root cause established during the punch-list review."
                            if resolved else ""),
                resolution_note=("Dispositioned — the fix was verified at re-inspection."
                                 if resolved else ""),
                resolved_by=owner if resolved else None,
                resolved_at=now if resolved else None,
                lessons_learned=lessons)
            obj.save()
            return obj

        with transaction.atomic():
            # One seeded defect carries the issue the ``qdf_raise_issue`` bridge would have
            # minted — the register's ``→ ISS-`` link and the bridge panel render it.
            bridged_issue = (ProjectIssue.objects.filter(tenant=tenant, project=active)
                             .order_by("id").first())

            # -- bullet 1: the plans -------------------------------------------------------------
            plan_discovery = plan(active, "Discovery & design acceptance plan", discovery,
                                  "active", "review", "ISO 9001:2015", review_offset=-3,
                                  approved=True)
            plan_ordering = plan(active, "Self-service ordering acceptance plan", ordering,
                                 "active", "testing", "WCAG 2.2 AA", review_offset=9)
            plan(active, "Superseded discovery criteria draft", discovery, "superseded",
                 "inspection", "", approved=True)
            if chartered is not None:
                plan(chartered, "Scorecard framework acceptance plan", chartered_deliverable,
                     "draft", "analysis", "", review_offset=21)

            # -- bullets 2 + 4: the reviews ------------------------------------------------------
            review(active, "Methodology adherence review — release 3 kickoff",
                   "methodology_review", "closed", discovery, plan_discovery, offset=30,
                   score=3, checklist="- Charters signed.\n- WBS baselined.",
                   findings="Process followed for the kickoff; the baseline change log lags.")
            review(active, "Compliance check — data protection requirements",
                   "compliance_check", "reported", discovery, plan_discovery, offset=18,
                   score=4)
            review(active, "Gate review — discovery gate", "gate_review", "closed", discovery,
                   plan_discovery, offset=22, score=4,
                   findings="Exit criteria met; the client product owner accepted the scope.")
            review(active, "Kaizen event — defect intake", "kaizen_event", "reported", None,
                   None, offset=12, imp_status="in_progress", imp_due=-4,
                   imp_action="Move defect intake onto the punch list with a named owner.")
            review(active, "Retrospective — ordering increment", "retrospective", "reported",
                   ordering, plan_ordering, offset=7, imp_status="planned", imp_due=10,
                   imp_action="Adopt pairwise review for integration branches.")
            if chartered is not None:
                review(chartered, "Maturity assessment — scorecard programme",
                       "maturity_assessment", "in_progress", None, None, offset=2, score=2)

            # -- bullets 3 + 5: the inspections ---------------------------------------------------
            insp_discovery = inspection(active, "Discovery deliverable acceptance",
                                        "acceptance", discovery, plan_discovery,
                                        gate_milestone, "conditional", "accept_with_deviation",
                                        "passed", planned_offset=-21, inspected_offset=-20,
                                        accepted=True, party_row=party,
                                        acceptance_note="Accepted with deviations: the UX "
                                                        "annotation pack ships late.")
            insp_api = inspection(active, "Order API integration testing", "testing", ordering,
                                  plan_ordering, None, "fail", "pending", "in_progress",
                                  planned_offset=-9, inspected_offset=-8)
            inspection(active, "Checkout walkthrough", "walkthrough", ordering, plan_ordering,
                       None, "pending", "pending", "planned", planned_offset=4)
            inspection(active, "Ordering demo for the client", "demonstration", ordering,
                       plan_ordering, None, "pass", "pending", "in_progress",
                       planned_offset=-2, inspected_offset=-1)
            inspection(active, "Returns portal design review", "review", None, None, None,
                       "pending", "pending", "planned", planned_offset=14)
            if chartered is not None:
                inspection(chartered, "Metric definitions acceptance", "acceptance",
                           chartered_deliverable, None, None, "pending", "pending", "planned",
                           planned_offset=-1)

            # -- bullets 3 + 5: the punch list ----------------------------------------------------
            defect(active, "Checkout total rounds to whole currency units", "critical",
                   "functional", "rework", "in_progress", ordering, plan_ordering, insp_api,
                   offset=3, due_offset=6)
            defect(active, "Order API omits the idempotency key", "major", "functional",
                   "resubmit", "open", ordering, plan_ordering, insp_api,
                   issue_row=bridged_issue, offset=8, due_offset=2)
            defect(active, "Annotation pack illustrations unfinished", "minor", "workmanship",
                   "accept_as_is", "closed", discovery, plan_discovery, insp_discovery,
                   offset=26, resolved=True,
                   lessons="Accept the annotated deliverable late rather than hold the gate — "
                           "record the dependency in the plan.")
            defect(active, "Compliance mapping misses clause 7.1.6", "major", "compliance",
                   "repair", "resolved", discovery, plan_discovery, insp_discovery, offset=24,
                   resolved=True)
            defect(active, "UX spec references the retired design system", "minor",
                   "documentation", "rework", "open", discovery, plan_discovery,
                   insp_discovery, offset=40)
            if chartered is not None:
                defect(chartered, "Metric pack lacks the source-data glossary", "observation",
                       "documentation", "deferred", "open", None, None, None, offset=55)

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {QualityPlan.objects.filter(tenant=tenant).count()} plans, "
            f"{QualityReview.objects.filter(tenant=tenant).count()} reviews, "
            f"{DeliverableInspection.objects.filter(tenant=tenant).count()} inspections, "
            f"{QualityDefect.objects.filter(tenant=tenant).count()} defects."))

    def _scope(self, tenant, now):
        """Requirements + boundary registry + CCB changes + acceptance log, guarded per tenant.

        Sized so the traceability matrix and the creep board have something real to compute over:
        15 requirements per tenant (12 on the active project, 3 on the chartered one) covering every
        ``requirement_type``, every elicitation technique, all four MoSCoW priorities and all seven
        statuses — with three rows deliberately left **untraced** (no work package) so the coverage
        gap list is non-empty, and three approved/implemented rows so the "never verified" gap is too.

        The change register covers all six statuses, with approved rows carrying a cost impact, a
        schedule impact and a quality impact each (so all three creep dimensions are non-zero) and
        one material change whose cost crosses ``HIGH_COST``. ``decided_at`` is stamped on every
        approved/rejected/implemented row because the creep board aggregates by the decision month.

        The acceptance log covers all three results and all four acceptance statuses, including a
        waived gate and a rejected deliverable with its mandatory written reason.
        """
        if Requirement.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: requirement rows already exist. "
                              f"Use --flush to re-seed.")
            return
        projects = list(Project.objects.filter(tenant=tenant))
        active = next((p for p in projects if p.status == "active"), None)
        chartered = next((p for p in projects if p.status == "chartered"), None)
        users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
        if not users:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no users - run seed_accounts first. Skipping scope."))
            return
        manager = next((p.project_manager for p in projects if p.project_manager_id), None)
        owner = users[1] if len(users) > 1 else manager
        requester = users[0]
        parties = list(Party.objects.filter(tenant=tenant).order_by("id"))
        party = parties[0] if parties else None
        today = timezone.localdate()

        def req(project, title, rtype, method, priority, status, wbs=None, **kw):
            obj = Requirement(
                tenant=tenant, project=project, wbs_node=wbs, title=title,
                description=kw.get("description") or f"{title}. Captured during the project's "
                                                     f"requirements workstream.",
                requirement_type=rtype, elicitation_method=method, priority=priority,
                status=status, source_party=party, owner=owner, requested_by=requester,
                acceptance_criteria=kw.get("acceptance_criteria", ""),
                elicitation_note=kw.get("elicitation_note", ""),
                version=kw.get("version", "1.0"),
                verification_method=kw.get("verification_method", "test"),
                rejection_reason=kw.get("rejection_reason", ""),
                approved_by=owner if status in ("approved", "implemented", "verified") else None,
                approved_at=now if status in ("approved", "implemented", "verified") else None,
                verified_by=owner if status == "verified" else None,
                verified_at=now if status == "verified" else None,
                verification_note=kw.get("verification_note", ""),
                created_by=requester)
            # Fail loudly at seed time rather than at the DB CHECK: a bad choice value or a bad
            # magnitude must name the offending row, not abort the whole atomic block.
            obj.full_clean(exclude=["number"])
            obj.save()
            return obj

        def item(project, statement, item_type, impact, status, requirement=None, **kw):
            obj = ScopeItem(
                tenant=tenant, project=project, requirement=requirement, statement=statement,
                description=kw.get("description", ""), item_type=item_type, impact_area=impact,
                status=status, owner=owner,
                identified_date=today - timedelta(days=kw.get("age", 40)),
                review_date=(today + timedelta(days=kw["review_offset"])
                             if kw.get("review_offset") is not None else None),
                outcome=kw.get("outcome", ""),
                closed_at=now if status in ("realized", "retired") else None,
                created_by=requester)
            obj.full_clean(exclude=["number"])
            obj.save()
            return obj

        def change(project, title, source, priority, cost, days, quality, status, **kw):
            decided = status in ("approved", "rejected", "implemented")
            obj = ScopeChangeRequest(
                tenant=tenant, project=project, requirement=kw.get("requirement"),
                risk=kw.get("risk"), title=title,
                description=kw.get("description") or f"{title}. Raised through the project's "
                                                    f"change control process.",
                justification=kw.get("justification", ""), source=source, priority=priority,
                schedule_impact_days=days, cost_impact=Decimal(cost), quality_impact=quality,
                quality_note=kw.get("quality_note", ""), status=status,
                decision_note=kw.get("decision_note", ""), requested_by=requester,
                decided_by=owner if decided else None,
                decided_at=now - timedelta(days=kw.get("decided_age", 10)) if decided else None,
                implemented_at=now - timedelta(days=kw["impl_age"])
                if status == "implemented" else None,
                created_by=requester)
            obj.full_clean(exclude=["number"])
            obj.save()
            return obj

        def verification(project, deliverable, method, result, acceptance, **kw):
            decided = acceptance != "pending"
            obj = ScopeVerification(
                tenant=tenant, project=project, wbs_node=kw.get("wbs"),
                requirement=kw.get("requirement"), deliverable=deliverable, method=method,
                result=result, acceptance_status=acceptance, inspected_by=owner,
                inspection_date=today - timedelta(days=kw.get("age", 12)),
                findings=kw.get("findings", ""), decision_note=kw.get("decision_note", ""),
                accepted_by=owner if decided else None,
                accepted_at=now if decided else None, created_by=requester)
            obj.full_clean(exclude=["number"])
            obj.save()
            return obj

        with transaction.atomic():
            if active is not None:
                tasks = {t.name: t for t in ProjectTask.objects.filter(tenant=tenant,
                                                                       project=active)}
                risks = {r.title: r for r in ProjectRisk.objects.filter(tenant=tenant,
                                                                        project=active)}

                r_sso = req(active, "Single sign-on for the customer portal", "functional",
                            "interview", "must", "verified", tasks.get("Technical spike: SSO"),
                            acceptance_criteria="A user can sign in through the corporate identity "
                                                "provider and is returned to the page they asked for.",
                            elicitation_note="Walked through the sign-in journey with the platform "
                                             "team; the redirect contract was the sticking point.",
                            verification_method="demonstration", version="1.1",
                            verification_note="Demonstrated in the sandbox on the agreed redirect "
                                              "contract.")
                r_perf = req(active, "Order API responds within 300 ms at p95", "non_functional",
                             "workshop", "must", "implemented", tasks.get("Order API"),
                             acceptance_criteria="The agreed load profile shows p95 latency at or "
                                                 "below 300 ms.",
                             verification_method="test")
                r_saved = req(active, "Checkout supports saved payment methods", "functional",
                              "user_story", "should", "approved",
                              tasks.get("Checkout integration"),
                              acceptance_criteria="A returning customer can pay with a stored "
                                                  "method in one step.")
                r_returns = req(active, "Returns can be raised without contacting support",
                                "business", "survey", "must", "submitted",
                                tasks.get("Returns portal UI"),
                                acceptance_criteria="A customer completes a standard return "
                                                    "unaided in under three minutes.")
                r_refund = req(active, "Refund service complies with the payment scheme rules",
                               "regulatory", "document_analysis", "must", "verified",
                               tasks.get("Refund service hooks"),
                               acceptance_criteria="The scheme's refund timing and evidence rules "
                                                   "are satisfied for every refund path.",
                               verification_method="analysis",
                               verification_note="Evidence pack reviewed against the scheme's "
                                                 "published rules.")
                r_wcag = req(active, "Cart screens meet WCAG 2.2 AA", "non_functional",
                             "prototype", "should", "approved", tasks.get("Cart UI"),
                             acceptance_criteria="An automated audit plus a manual keyboard pass "
                                                 "find no level-AA failures.",
                             verification_method="inspection")
                req(active, "Order confirmation email is localised", "functional", "brainstorm",
                    "could", "draft",
                    acceptance_criteria="The confirmation renders in the customer's locale.")
                req(active, "Supplier catalogue CSV dialect is accepted on import", "interface",
                    "document_analysis", "could", "deferred",
                    acceptance_criteria="A supplier file in the documented dialect imports without "
                                        "manual edits.")
                req(active, "Guest checkout in the first release", "business", "workshop", "wont",
                    "rejected", rejection_reason="Rejected by the sponsor: guest checkout is "
                                                 "deferred until the identity work lands.")
                r_history = req(active, "Order history is searchable by order number", "functional",
                                "observation", "should", "implemented", tasks.get("Order API"),
                                acceptance_criteria="A search on an exact order number returns that "
                                                    "order in under two seconds.")
                r_session = req(active, "Session timeout follows the security policy", "technical",
                                "interview", "must", "verified", tasks.get("Order API"),
                                acceptance_criteria="Idle sessions expire on the policy's schedule "
                                                    "and warn before they do.",
                                verification_method="analysis",
                                verification_note="Configuration reviewed against the security "
                                                  "policy's session section.")
                req(active, "Payment provider sandbox mirrors production behaviour", "technical",
                    "workshop", "should", "draft",
                    acceptance_criteria="The sandbox returns the same error shapes as production.")

                item(active, "Release 3 covers the self-service ordering journey end to end",
                     "in_scope", "scope", "validated",
                     description="From catalogue browse to order confirmation, without a support "
                                 "intervention.")
                item(active, "Marketplace seller onboarding is not in release 3", "out_of_scope",
                     "scope", "validated",
                     description="Deferred to the marketplace programme; no release-3 work.")
                item(active, "Multi-currency pricing is deferred to release 4", "out_of_scope",
                     "cost", "open", review_offset=21)
                item(active, "The identity provider sandbox is available throughout the build",
                     "assumption", "schedule", "realized",
                     outcome="The sandbox slipped by two weeks, which pushed the SSO spike and "
                             "consumed the schedule float on the critical path.")
                item(active, "Load-test infrastructure is provisioned by the platform team",
                     "assumption", "resource", "open", review_offset=-6)
                item(active, "Go-live is fixed by the retail peak freeze", "constraint",
                     "schedule", "validated",
                     description="No production change after the peak freeze window opens.")
                item(active, "PCI DSS scope excludes card data at rest", "constraint",
                     "compliance", "validated",
                     description="The provider tokenises; no card number reaches our storage.")
                item(active, "The checkout interface is delivered by the partner's sandbox",
                     "dependency", "schedule", "realized",
                     outcome="Certification completed three weeks late; the interface landed with "
                             "the fallback plan already agreed.")
                item(active, "Returns self-service is in release 3 for standard orders", "in_scope",
                     "scope", "open", review_offset=14)
                item(active, "The design-system version is pinned in the build", "assumption",
                     "quality", "retired",
                     outcome="Superseded — the design system is now pinned in the build pipeline "
                             "itself, so the assumption no longer needs tracking.")

                change(active, "Add saved payment methods to checkout", "client", "high", "48000.00",
                       15, "medium", "approved", requirement=r_saved,
                       justification="Repeat customers abandon at the payment step; the client's "
                                     "usability study puts the recovery at 4% of orders.",
                       quality_note="The stored-method selector needs a full design review.",
                       decided_age=34)
                change(active, "Extend the returns window from 14 to 30 days", "client", "medium",
                       "12000.00", 5, "low", "implemented", requirement=r_returns,
                       justification="Competitor parity — the client's policy is now 30 days.",
                       decided_age=52, impl_age=30)
                change(active, "Add multi-currency pricing to release 3", "internal", "critical",
                       "180000.00", 40, "high", "rejected",
                       justification="Would open three additional markets this year.",
                       decision_note="Rejected: the cost and the forty-day schedule impact cannot "
                                     "be absorbed before the peak freeze. Revisit for release 4.",
                       quality_note="Pricing rules would need a second approval path.",
                       decided_age=26)
                change(active, "Reduce the accessibility target on the checkout screens",
                       "regulatory", "medium", "0.00", 10, "high", "rejected",
                       justification="Buy ten days by shipping checkout at a lower conformance "
                                     "level.",
                       decision_note="Rejected: the accessibility target is a regulatory "
                                     "commitment, not a schedule lever.",
                       decided_age=45)
                change(active, "Add a loyalty points display to the cart", "internal", "low",
                       "22000.00", 8, "none", "submitted",
                       justification="Small, visible win for the loyalty programme.")
                change(active, "Move the returns module to release 4", "internal", "high", "0.00",
                       30, "none", "under_review",
                       justification="Frees the QA team for the checkout work.",
                       description="De-scope the returns module to protect the checkout date.")
                change(active, "Replace the legacy order export with the API", "technical",
                       "medium", "9000.00", 3, "none", "draft",
                       justification="Retires the last consumer of the legacy export job.")
                change(active, "Add audit logging to the refund service", "regulatory", "high",
                       "15000.00", 6, "medium", "approved",
                       requirement=r_refund, decided_age=18,
                       justification="The scheme's evidence rules require a retained audit trail "
                                     "for every refund decision.",
                       quality_note="Log retention length must match the scheme's minimum.",
                       risk=risks.get("Refund service compliance review findings"))

                verification(active, "Order API load-test report", "test", "pass", "accepted",
                             wbs=tasks.get("Order API"), requirement=r_perf, age=20,
                             findings="p95 held at 240 ms across the agreed profile; no error-rate "
                                      "regression.")
                verification(active, "Single sign-on integration demonstration", "demonstration",
                             "pass", "accepted", wbs=tasks.get("Technical spike: SSO"),
                             requirement=r_sso, age=16,
                             findings="Redirect contract honoured on all three entry points.")
                verification(active, "Refund service compliance evidence pack", "analysis", "pass",
                             "accepted", wbs=tasks.get("Refund service hooks"),
                             requirement=r_refund, age=14,
                             findings="Every refund path evidenced against the scheme's timing and "
                                      "retention rules.")
                verification(active, "Order history search walkthrough", "demonstration",
                             "conditional", "accepted", wbs=tasks.get("Order API"),
                             requirement=r_history, age=9,
                             findings="Exact-number search meets the target; partial matches are "
                                      "slower than the stated target.",
                             decision_note="Accepted on the condition that partial-match latency "
                                           "is tracked as a follow-up.")
                verification(active, "Session timeout configuration review", "review", "pass",
                             "accepted", wbs=tasks.get("Order API"), requirement=r_session,
                             age=7, findings="Idle expiry and the pre-expiry warning both match the "
                                             "policy.")
                verification(active, "Cart accessibility audit", "inspection", "conditional",
                             "pending", wbs=tasks.get("Cart UI"), requirement=r_wcag, age=4,
                             findings="Two level-AA contrast failures remain in the cart summary.")
                verification(active, "Saved payment method demonstration", "demonstration", "pass",
                             "pending", wbs=tasks.get("Checkout integration"), requirement=r_saved,
                             age=2, findings="One-step stored-method payment works end to end.")
                verification(active, "Returns portal design review", "review", "fail", "rejected",
                             wbs=tasks.get("Returns portal UI"), requirement=r_returns, age=5,
                             findings="The unaided-completion path needs a support contact.",
                             decision_note="Rejected: the requirement is specifically that a "
                                           "customer can complete a return unaided.")
                verification(active, "Supplier catalogue import dry run", "test", "conditional",
                             "waived", age=11,
                             findings="The supplier's dialect differs in two columns; a mapping "
                                      "sheet resolves it.",
                             decision_note="Waived by the sponsor: the supplier will be asked to "
                                           "use the documented dialect instead.")

            if chartered is not None:
                tasks = {t.name: t for t in ProjectTask.objects.filter(tenant=tenant,
                                                                       project=chartered)}
                req(chartered, "Scorecard publishes on the agreed quarterly cadence", "business",
                    "interview", "must", "approved", tasks.get("Quarterly publication"),
                    acceptance_criteria="Four published cycles with no missed quarter.",
                    version="1.2")
                req(chartered, "Data collection pipeline ingests partner files", "interface",
                    "document_analysis", "should", "submitted",
                    tasks.get("Data collection pipeline"),
                    acceptance_criteria="A partner file in the agreed schema lands in the "
                                        "warehouse within one hour.")
                req(chartered, "Metric definitions are signed off by the finance owner", "business",
                    "workshop", "must", "draft",
                    acceptance_criteria="Every published metric names its owner and its formula.")

                item(chartered, "Partner data files arrive in the agreed schema", "assumption",
                     "quality", "open", review_offset=10)
                item(chartered, "The scorecard uses the group's published metric definitions",
                     "constraint", "compliance", "validated")

                change(chartered, "Bring the scorecard forward by one quarter", "internal", "high",
                       "65000.00", 22, "medium", "under_review",
                       justification="The board wants the scorecard in the next reporting cycle.")

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {Requirement.objects.filter(tenant=tenant).count()} requirements, "
            f"{ScopeItem.objects.filter(tenant=tenant).count()} scope items, "
            f"{ScopeChangeRequest.objects.filter(tenant=tenant).count()} change requests, "
            f"{ScopeVerification.objects.filter(tenant=tenant).count()} inspections."))

    def _wbs(self, tenant, project, manager, today, spec):
        """Build the WBS from a spec; return a name -> task map for the dependency specs.

        Rows are constructed and ``.save()``d individually — never ``bulk_create``: it bypasses
        ``TenantNumbered.save()`` and would ship every row with an empty number.
        """
        by_name = {}
        for entry in spec:
            parent = by_name.get(entry["parent"]) if entry.get("parent") else None
            task = ProjectTask(
                tenant=tenant, project=project, parent=parent,
                node_type=entry["node_type"], name=entry["name"],
                description=entry.get("description", ""),
                owner=manager if entry["node_type"] == "work_package" else None,
                status=entry.get("status", "planned"),
                # Deliverables carry no planned dates — the tree view rolls their children up.
                planned_start=today + timedelta(days=entry["start"])
                if entry.get("start") is not None else None,
                planned_end=today + timedelta(days=entry["end"])
                if entry.get("end") is not None else None,
                effort_hours=Decimal(entry["effort"]) if entry.get("effort") else None,
                estimation_method=entry.get("method", "bottom_up"),
                confidence=entry.get("confidence", "medium"),
                sequence=entry.get("sequence", 0))
            task.save()
            by_name[entry["name"]] = task
        return by_name

    def _deps(self, tenant, tasks, spec):
        for predecessor, successor, link_type, lag in spec:
            a, b = tasks.get(predecessor), tasks.get(successor)
            if a is None or b is None:
                continue
            TaskDependency(tenant=tenant, predecessor=a, successor=b,
                           link_type=link_type, lag_days=lag).save()

    def _milestones(self, tenant, project, tasks, today, spec):
        for entry in spec:
            anchor = tasks.get(entry["anchor"]) if entry.get("anchor") else None
            ProjectMilestone(
                tenant=tenant, project=project, anchor_task=anchor,
                name=entry["name"], description=entry.get("description", ""),
                target_date=today + timedelta(days=entry["target"]),
                is_phase_gate=entry.get("gate", False),
                entry_criteria=entry.get("entry", ""),
                exit_criteria=entry.get("exit", ""),
                status=entry["status"],
                actual_date=today + timedelta(days=entry["actual"])
                if entry.get("actual") is not None else None).save()

    def _baseline(self, tenant, project, name, baseline_type, is_active=False,
                  frozen_offset=None, strategy_note=""):
        baseline = ScheduleBaseline(
            tenant=tenant, project=project, name=name, baseline_type=baseline_type,
            is_active=is_active, strategy_note=strategy_note)
        if baseline_type == "baseline":
            # Snapshot the plan as it stands, then backdate the freeze to the kickoff's
            # acknowledgement — the row attests to the schedule the ceremony accepted.
            baseline.freeze_snapshot()
            if frozen_offset:
                baseline.frozen_on = timezone.localdate() - timedelta(days=frozen_offset)
        baseline.save()

    # -- 7.1 blocks -------------------------------------------------------------------------------

    def _requests(self, tenant, now, org_unit, party, currency, requester, approver):
        """Nine rows, one per status. Guarded as a block — see the module docstring."""
        rows = [
            dict(title="Warehouse automation feasibility study", status="draft",
                 request_type="new_project", description="Assess a conveyor upgrade for bay 2.",
                 estimated_cost=Decimal("45000.00"), estimated_benefit=Decimal("120000.00")),
            dict(title="Customer portal self-service returns", status="submitted",
                 request_type="enhancement", priority="high",
                 description="Let customers raise a return without emailing support.",
                 estimated_cost=Decimal("80000.00"), estimated_benefit=Decimal("210000.00"),
                 strategic_alignment=4),
            dict(title="Replace legacy nightly batch export", status="screening",
                 request_type="change_request", priority="medium",
                 description="The nightly export still runs on a 2016 job server.",
                 estimated_cost=Decimal("30000.00"), estimated_benefit=Decimal("45000.00")),
            dict(title="ERP mobile approvals for managers", status="assessment",
                 request_type="new_project", priority="high", risk_rating="high",
                 feasibility="feasible_with_constraints", strategic_alignment=4,
                 description="Approve POs and leave from a phone.",
                 estimated_cost=Decimal("120000.00"), estimated_benefit=Decimal("260000.00"),
                 feasibility_notes="Feasible once the SSO rollout lands in Q3.",
                 alternatives_considered="1) Buy an off-the-shelf approvals app. "
                                         "2) Email-based approval (rejected: no audit trail)."),
            dict(title="Consolidate two regional warehouses", status="needs_information",
                 request_type="new_project", priority="critical",
                 description="One site instead of two — needs the lease numbers.",
                 estimated_cost=Decimal("640000.00"), estimated_benefit=Decimal("900000.00"),
                 information_requested="Lease break costs for both sites, and the redundancy "
                                       "estimate for the affected staff."),
            dict(title="Supplier scorecard rollout", status="approved",
                 request_type="new_project", priority="medium", strategic_alignment=5,
                 description="Publish a quarterly scorecard to every tier-1 supplier.",
                 estimated_cost=Decimal("55000.00"), estimated_benefit=Decimal("175000.00"),
                 feasibility="feasible", decision="go"),
            dict(title="Second shift at the northern plant", status="approved",
                 request_type="new_project", priority="high", strategic_alignment=3,
                 description="Add a second shift to clear the order backlog.",
                 estimated_cost=Decimal("210000.00"), estimated_benefit=Decimal("390000.00"),
                 feasibility="feasible", decision="go"),
            dict(title="In-house fleet telematics build", status="rejected",
                 request_type="new_project", priority="low", feasibility="not_feasible",
                 decision="no_go", description="Build our own vehicle tracking stack.",
                 estimated_cost=Decimal("320000.00"), estimated_benefit=Decimal("140000.00"),
                 rejection_reason="Negative ROI and three mature vendors already do this better."),
            dict(title="Blockchain provenance pilot", status="deferred",
                 request_type="idea", priority="low",
                 description="Interesting, but nobody has asked for it yet.",
                 estimated_cost=Decimal("90000.00"), estimated_benefit=Decimal("0.00")),
        ]
        created = []
        for i, row in enumerate(rows, start=1):
            status = row.pop("status")
            decided = bool(row.get("decision"))
            # Stamped in the CONSTRUCTOR, not by two follow-up saves: three saves per row was 25
            # UPDATEs against 18 INSERTs across two tenants. NOT bulk_create — TenantNumbered
            # .save() allocates `number` through next_number() and bulk_create bypasses save()
            # entirely, which would ship every row with an empty number.
            obj = ProjectRequest(
                tenant=tenant, requested_by=requester, requester_party=party,
                org_unit=org_unit, currency=currency, assigned_approver=approver,
                created_by=requester, status=status,
                submitted_at=None if status == "draft" else timezone.now() - timedelta(days=i),
                decided_by=approver if decided else None,
                decided_at=timezone.now() - timedelta(days=1) if decided else None,
                **row)
            obj.save()
            created.append(obj)
            if decided:
                write_audit_log(None, obj, "approve",
                                changes={"verb": "approve", "from": "submitted", "to": obj.status})
        return created

    def _convert(self, tenant, requests, now):
        """Run the REAL convert path on request #6 — not a hand-stamped ``converted_project``."""
        target = next((r for r in requests if r.title == "Supplier scorecard rollout"), None)
        if target is None:
            return None
        project = target.convert_to_project(user=target.created_by)
        if project is None:
            return None
        write_audit_log(None, target, "convert",
                        changes={"verb": "convert", "from": target.number, "to": project.number})
        return project

    def _projects(self, tenant, now, org_unit, party, sponsor, manager, converted):
        """The converted project plus two more: a bare draft and one walked to active."""
        out = []
        if converted is not None:
            converted.status = "chartered"
            converted.charter_status = "submitted"
            converted.project_manager = manager
            converted.executive_sponsor = sponsor
            converted.in_scope = "Tier-1 supplier scorecard, quarterly publication cycle."
            converted.out_of_scope = "Tier-2 and below; supplier-facing portal (7.14)."
            converted.objectives = "Publish a defensible scorecard every quarter."
            converted.success_criteria = "Scorecards out for 100% of tier-1 suppliers within 2 quarters."
            converted.save()
            out.append(converted)

        draft = Project.objects.filter(tenant=tenant, name="Fleet replacement programme").first()
        if draft is None:
            draft = Project(
                tenant=tenant, name="Fleet replacement programme", code="FLT-2027",
                description="Replace 40 vans on a five-year cycle.",
                methodology="waterfall", org_unit=org_unit, client=party,
                project_manager=manager, executive_sponsor=sponsor,
                start_date=(now + timedelta(days=30)).date(),
                end_date=(now + timedelta(days=300)).date(),
                created_by=manager)
            draft.save()
        out.append(draft)

        active = Project.objects.filter(tenant=tenant, name="Customer portal release 3").first()
        if active is None:
            active = Project(
                tenant=tenant, name="Customer portal release 3", code="PORTAL-3",
                description="Self-service ordering, invoicing and returns.",
                methodology="agile", org_unit=org_unit, client=party,
                project_manager=manager, executive_sponsor=sponsor,
                start_date=(now - timedelta(days=60)).date(),
                end_date=(now + timedelta(days=90)).date(),
                in_scope="Ordering, invoicing, returns.",
                out_of_scope="Marketplace integrations.",
                objectives="Cut inbound support tickets by a third.",
                success_criteria="Ticket volume down 30% within one quarter of go-live.",
                assumptions="The existing auth stack carries the new surface.",
                constraints="No changes to the billing engine this release.",
                risk_summary="Single sign-on rollout is on the critical path.",
                status="active", charter_status="approved",
                charter_approved_by=sponsor, charter_approved_at=now - timedelta(days=62),
                created_by=manager)
            active.save()
            write_audit_log(None, active, "approve",
                            changes={"verb": "approve_charter", "from": "submitted",
                                     "to": "approved"})
        out.append(active)
        return out

    def _stakeholders(self, tenant, project, party, users, manager):
        """Six rows: every RACI value, every influence×interest quadrant, 3 attending."""
        if project is None or project.stakeholders.count() >= 6:
            return
        rows = [
            ("sponsor", "a", "charter approval", "high", "high", True),
            ("approver", "r", "charter approval", "high", "low", True),
            ("subject_matter_expert", "c", "scorecard metrics", "medium", "high", False),
            ("affected", "i", "supplier communications", "low", "high", False),
            ("team_member", "r", "data collection", "medium", "low", True),
            ("resource_provider", "c", "tooling", "low", "low", False),
        ]
        for i, (stype, raci, scope, infl, intr, attending) in enumerate(rows):
            ProjectStakeholder.objects.create(
                tenant=tenant, project=project,
                party=party if i % 2 == 0 else None,
                user=users[i % len(users)] if i % 2 else None,
                stakeholder_type=stype, raci_role=raci, raci_scope=scope,
                influence=infl, interest=intr, attending_kickoff=attending,
                notes="Seeded stakeholder row." if i == 0 else "",
                created_by=manager)

    def _kickoffs(self, tenant, now, projects):
        """Two rows: one completed with its baseline acknowledged, one merely scheduled."""
        if ProjectKickoff.objects.filter(tenant=tenant).exists():
            return
        active = next((p for p in projects if p.status == "active"), None)
        chartered = next((p for p in projects if p.status == "chartered"), None)
        if active is not None:
            ProjectKickoff.objects.create(
                tenant=tenant, project=active,
                meeting_date=now - timedelta(days=58),
                location_or_link="https://meet.example.com/portal-3-kickoff",
                agenda_template="agile", status="completed",
                agenda="1. Vision 2. Scope 3. Baseline 4. Ways of working",
                attendee_summary="Two client-side product owners joined.",
                onboarding_notes="Access provisioned, tooling set up, intro to sponsor.",
                completed_at=now - timedelta(days=57),
                baseline_acknowledged_at=now - timedelta(days=57),
                baseline_acknowledged_by=active.executive_sponsor,
                created_by=active.project_manager)
        if chartered is not None:
            ProjectKickoff.objects.create(
                tenant=tenant, project=chartered,
                meeting_date=now + timedelta(days=7),
                location_or_link="Boardroom 2",
                agenda_template="client_facing", status="scheduled",
                agenda="1. Objectives 2. RACI 3. Next steps",
                created_by=chartered.project_manager)

    def _activities(self, tenant, now, project, manager):
        """The kickoff meeting plus three onboarding tasks — the checklist, on the spine."""
        if project is None or Activity.objects.filter(
                tenant=tenant,
                content_type=ContentType.objects.get_for_model(Project),
                object_id=project.pk).exists():
            return
        ct = ContentType.objects.get_for_model(Project)
        rows = [
            ("meeting", "Kickoff meeting", "done", now - timedelta(days=58)),
            ("task", "Provision repository access", "done", now - timedelta(days=56)),
            ("task", "Set up the build pipeline", "in_progress", now + timedelta(days=3)),
            ("task", "Intro to the executive sponsor", "open", now + timedelta(days=10)),
        ]
        for kind, subject, status, due in rows:
            Activity.objects.create(
                tenant=tenant, owner=manager, kind=kind, subject=subject,
                content_type=ct, object_id=project.pk, status=status, due_at=due)

    # -- shared lookups ---------------------------------------------------------------------------

    # -- 7.8 task & work management --------------------------------------------------------------

    def _taskwork(self, tenant, now):
        """Execution layer on the 7.2 tasks + the checklist and block registers, guarded.

        Nothing here creates a task: the WBS rows are 7.2's and this block only extends them
        IN PLACE (the documented 7.2 hand-off) with the execution fields the board / gantt /
        priority pages compute over, and seeds the two 7.8 registers against them.

        Execution coverage per tenant: every priority, all four MoSCoW values PLUS an
        unclassified row (the first work package of each project), all four Eisenhower
        quadrants, percent_complete honest to the row's status (done rows at 100, in_progress
        mid-flight, planned at 0), actual_start/actual_end written the way tsk_start/tsk_complete
        would (the seeder stamps evidence directly, 7.5 precedent), one overdue row (planned_end
        in the past, still in_progress) and every unassigned shape. A cancelled work package
        (7.2's ``ACTIVE_WBS``) gives the terminal-but-not-done lens something to exclude.
        Checklists land on every third work package with mixed ticks so the progress rollup is
        non-trivial and the register runs to page 2; the un-checklisted rows are the documented
        empty state. The block trail is one active blocker and one closed with its full evidence
        (blocked_by/at, unblocked_by/at, resolution note).
        """
        if TaskChecklistItem.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: task execution rows already exist. "
                              f"Use --flush to re-seed.")
            return
        tasks = list(ProjectTask.objects.filter(tenant=tenant, node_type="work_package")
                     .select_related("project").order_by("project_id", "id"))
        users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
        if not tasks or not users:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no work packages or users - skipping task execution."))
            return
        today = timezone.localdate()
        priorities = ["low", "medium", "high", "critical"]
        moscow = ["must_have", "should_have", "could_have", "wont_have"]
        quadrants = [(False, False), (True, False), (True, True), (False, True)]

        with transaction.atomic():
            seen_projects = set()
            for i, task in enumerate(tasks):
                task.assignee = users[i % len(users)]
                task.priority = priorities[i % 4]
                # The FIRST work package of each project stays UNCLASSIFIED (moscow=None) so the
                # board's "Unclassified" bucket and the priority page's unclassified group are
                # both non-empty (review M5 — every row used to carry a MoSCoW value).
                if task.project_id in seen_projects:
                    task.moscow = moscow[i % 4]
                else:
                    task.moscow = None
                    seen_projects.add(task.project_id)
                task.is_urgent, task.is_important = quadrants[i % 4]
                if task.status == "done":
                    task.percent_complete = Decimal("100.00")
                    task.actual_start = task.planned_start or (today - timedelta(days=10))
                    task.actual_end = today - timedelta(days=2)
                elif task.status == "in_progress":
                    task.percent_complete = Decimal("50.00") if i % 2 == 0 \
                        else Decimal("25.00")
                    task.actual_start = task.planned_start or (today - timedelta(days=5))
                else:
                    # planned/cancelled rows carry no actuals — the verbs have not touched them.
                    task.percent_complete = Decimal("0.00")
                task.full_clean(exclude=["number"])
                task.save(update_fields=[
                    "assignee", "priority", "moscow", "is_urgent", "is_important",
                    "percent_complete", "actual_start", "actual_end", "updated_at"])

                if i % 3 == 0:
                    # Every third work package carries a checklist, one item short of complete —
                    # the rollup must never read as trivially 0 or trivially 100. The spacing
                    # also pushes the register past its 15-row page so page 2 is reachable, and
                    # leaves the un-checklisted rows as the documented EMPTY-checklist state
                    # (review M5).
                    total = 4
                    for seq, label in enumerate([
                            "Confirm the work package's inputs with the owner",
                            "Draft the deliverable outline",
                            "Internal review pass",
                            "Hand-off sign-off"]):
                        done = seq < total - 1
                        item = TaskChecklistItem(
                            tenant=tenant, task=task, label=label, sequence=seq,
                            is_done=done,
                            done_by=users[0] if done else None,
                            done_at=now - timedelta(days=total - seq) if done else None,
                            created_by=users[0])
                        item.full_clean(exclude=["number"])
                        item.save()

            # The block evidence trail: one ACTIVE blocker (the board/priority blocked lenses
            # and the over-WIP badges read it) and one CLOSED with its full unblock evidence.
            active_task = next((t for t in tasks if t.status == "in_progress"), tasks[0])
            active = TaskBlock(tenant=tenant, task=active_task,
                               reason="Waiting on the vendor sandbox credentials before the "
                                      "integration work can continue.",
                               unblock_criteria="Sandbox tenant provisioned and the credentials "
                                                "received from the vendor contact.",
                               blocked_by=users[-1], blocked_at=now - timedelta(days=3),
                               created_by=users[0])
            active.full_clean(exclude=["number"])
            active.save()
            closed_task = next((t for t in tasks
                                if t.id != active_task.id and t.status != "done"), None) \
                or tasks[-1]
            closed = TaskBlock(tenant=tenant, task=closed_task,
                               reason="Design decision pending — two competing approaches "
                                      "for the sync window.",
                               unblock_criteria="Architecture review minutes published "
                                                "with the chosen approach.",
                               resolution_note="Architecture review chose the nightly batch "
                                               "window; decision recorded in the minutes.",
                               blocked_by=users[-1], blocked_at=now - timedelta(days=9),
                               unblocked_by=users[0], unblocked_at=now - timedelta(days=6),
                               created_by=users[0])
            closed.full_clean(exclude=["number"])
            closed.save()

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {ProjectTask.objects.filter(tenant=tenant).count()} tasks "
            f"extended for execution, "
            f"{TaskChecklistItem.objects.filter(tenant=tenant).count()} checklist items, "
            f"{TaskBlock.objects.filter(tenant=tenant).count()} block rows "
            f"(1 active, 1 closed)."))

    def _collab(self, tenant, now):
        """7.9 collaboration: channels + threads, shared documents, meetings, notifications.

        Guarded per tenant. Nothing here invents a project, a task or a document store: the
        channels hang off the workspace's existing projects, the action items point at 7.2's
        existing work packages, and the shares reuse a ``core.Document`` row (the repository
        belongs to 7.10 — this block creates at most two attachments so the register is not
        empty, and never a parallel store).

        Coverage per tenant: three channels (discussion / announcement / ARCHIVED, so the
        archive facet and both badge states have rows); 18 messages — two roots carrying two and
        three replies, two bare roots, an EDITED root carrying two mentions, five announcement
        roots and three on the archived channel — which clears the register's 15-row page so the
        paginator has a genuine page 2; four meetings, one per status, with the completed one
        carrying full minutes, a covered agenda and a mixed action list; six agenda items and six
        action items (one overdue, one unassigned, one linked to a real work package, one closed);
        and 18 notifications covering every kind, both read states, every optional source FK and
        three recipients.
        """
        if Channel.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: collaboration rows already exist. "
                              f"Use --flush to re-seed.")
            return
        projects = list(Project.objects.filter(tenant=tenant).order_by("id"))
        users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
        if not projects or not users:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no projects or users - skipping collaboration."))
            return
        active = next((p for p in projects if p.status == "active"), projects[0])
        other = next((p for p in projects if p.pk != active.pk), active)
        tasks = list(ProjectTask.objects.filter(
            tenant=tenant, project=active, node_type="work_package").order_by("id"))
        today = timezone.localdate()

        def channel(project, name, kind, topic, archived=False):
            row = Channel(tenant=tenant, project=project, name=name, kind=kind, topic=topic,
                          created_by=users[0])
            if archived:
                row.is_archived = True
                row.archived_by = users[-1]
                row.archived_at = now - timedelta(days=21)
            row.full_clean(exclude=["number"])
            row.save()
            return row

        def message(chan, body, author, parent=None, mentions=(), edited=False):
            row = ChannelMessage(tenant=tenant, channel=chan, parent=parent, body=body,
                                 created_by=author)
            if edited:
                row.edited_by = users[-1]
                row.edited_at = now - timedelta(hours=3)
            row.full_clean(exclude=["number"])
            row.save()
            if mentions:
                row.mentions.set(mentions)
            return row

        def meeting(project, title, kind, status, day_offset, recurrence="none",
                    location="", minutes="", covered=0, agenda=(), actions=()):
            row = Meeting(tenant=tenant, project=project, title=title, kind=kind,
                          scheduled_start=now + timedelta(days=day_offset),
                          scheduled_end=now + timedelta(days=day_offset, hours=1),
                          location=location, recurrence=recurrence, status=status,
                          created_by=users[0])
            if status == "in_progress":
                row.actual_start = now + timedelta(days=day_offset)
            elif status == "completed":
                row.actual_start = now + timedelta(days=day_offset)
                row.actual_end = now + timedelta(days=day_offset, hours=1)
            if minutes:
                row.minutes = minutes
                row.minutes_by = users[0]
                row.minutes_at = now + timedelta(days=day_offset, hours=1)
            row.full_clean(exclude=["number"])
            row.save()
            for seq, (title_text, presenter, duration, is_covered) in enumerate(agenda):
                item = MeetingAgendaItem(
                    tenant=tenant, meeting=row, title=title_text,
                    presenter=users[presenter % len(users)] if presenter is not None else None,
                    duration_minutes=duration, sequence=seq, is_covered=is_covered,
                    created_by=users[0])
                if is_covered:
                    item.covered_by = users[0]
                    item.covered_at = now + timedelta(days=day_offset, hours=1)
                item.full_clean(exclude=["number"])
                item.save()
            for index, (description, assignee, due_offset, is_done, task_index) in enumerate(
                    actions):
                item = MeetingActionItem(
                    tenant=tenant, meeting=row, description=description,
                    assignee=users[assignee % len(users)] if assignee is not None else None,
                    due_date=today + timedelta(days=due_offset) if due_offset is not None else None,
                    task=tasks[task_index] if task_index is not None and tasks else None,
                    is_done=is_done, created_by=users[0])
                if is_done:
                    item.done_by = users[assignee % len(users)] if assignee is not None else users[0]
                    item.done_at = now - timedelta(days=1)
                item.full_clean(exclude=["number"])
                item.save()
            return row

        def notify(project, recipient, kind, title, body="", chan=None, msg=None, task=None,
                   mtg=None, read=False, trigger=None):
            row = ProjectNotification(
                tenant=tenant, project=project, recipient=recipient, kind=kind, title=title,
                body=body, channel=chan, message=msg, task=task, meeting=mtg,
                triggered_by=trigger if trigger is not None else users[-1], is_read=read,
                read_at=(now - timedelta(hours=5)) if read else None, created_by=users[0])
            row.full_clean(exclude=["number"])
            row.save()
            return row

        with transaction.atomic():
            # -- channels and their threads --------------------------------------------------
            standup = channel(active, "Delivery Standup", "discussion",
                              "Daily delivery coordination - blockers, hand-offs and owners.")
            announce = channel(active, "Project Announcements", "announcement",
                               "One-way updates for the whole delivery team.")
            closed = channel(other, "Discovery (closed)", "discussion",
                             "Archived once the discovery phase signed off.", archived=True)

            root = message(standup, "Kicking off this week - we are behind on the integration "
                                    "work package. Blockers here please.", users[0])
            message(standup, "Sandbox credentials are still pending with the vendor; I have "
                             "chased them again this morning.", users[1], parent=root)
            message(standup, "Understood - I will keep the integration work package parked "
                             "until they land.", users[2], parent=root)
            second = message(standup, "Reminder: the steering pack is due before Thursday's "
                                      "review. Numbers come off the cost register.",
                             users[1])
            message(standup, "I will pull the variance figures this afternoon.", users[0],
                    parent=second)
            message(standup, "Anyone able to pick up the acceptance checklist? It is the last "
                             "open item on the quality plan.", users[2])
            edited = message(standup, "Heads up: the delivery date moved. The revised plan is "
                                      "on the shared document.", users[0],
                             mentions=[users[1], users[2]], edited=True)
            message(announce, "Charter approved - the project is now formally active.",
                    users[0])
            message(announce, "Baseline frozen at revision 0. Changes go through the CCB from "
                              "here.", users[0])
            message(announce, "New work packages published on the plan; owners have been "
                              "notified.", users[1])
            message(announce, "Monthly status pack is out - variance is inside tolerance.",
                    users[2])
            message(closed, "Discovery signed off - thank you all for the turnaround.",
                    users[0])
            message(closed, "Notes and the decision log are filed against the kickoff record.",
                    users[1])
            # Four more so the register genuinely exceeds its 15-row page and the paginator has
            # a real page 2 to serve (a 13-row register silently renders page 1 for every ?page=).
            message(standup, "Variance commentary added to the pack; the two red lines are both "
                             "integration-side.", users[0], parent=second)
            message(standup, "Thanks - I will re-run the forecast against the new dates.",
                    users[1], parent=second)
            message(standup, "Risk review moved to Tuesday; the register has three new entries.",
                    users[2])
            message(announce, "Change freeze begins the 28th and lifts after the go-live "
                              "checkpoint.", users[0])
            message(closed, "Retro actions are all closed; nothing carried into delivery.",
                    users[2])

            # -- shared documents ------------------------------------------------------------
            # The artifact store is core.Document (7.10 owns the repository); these two rows exist
            # so the share register is not empty, and no second attachment table is created.
            pack, _ = Document.objects.get_or_create(
                tenant=tenant, name="Project status pack",
                defaults={"classification": "internal", "version": "2.0"})
            plan, _ = Document.objects.get_or_create(
                tenant=tenant, name="Integrated delivery plan",
                defaults={"classification": "confidential", "version": "1.4"})
            claimed = DocumentShare(
                tenant=tenant, project=active, channel=standup, document=pack,
                access_level="edit", shared_with=users[1],
                note="Owner copy - update the variance table before each steering review.",
                claimed_by=users[1], claimed_at=now - timedelta(hours=2), created_by=users[0])
            claimed.full_clean(exclude=["number"])
            claimed.save()
            free = DocumentShare(
                tenant=tenant, project=active, channel=standup, document=plan,
                access_level="edit", note="Team copy - co-edit before the next review.",
                created_by=users[0])
            free.full_clean(exclude=["number"])
            free.save()
            DocumentShare(tenant=tenant, project=active, document=pack, access_level="comment",
                          shared_with=users[2],
                          note="Comments welcome on the narrative section.", created_by=users[0]
                          ).save()
            revoked = DocumentShare(
                tenant=tenant, project=other, document=plan, access_level="view",
                note="Superseded by the frozen baseline.", is_active=False, revoked_by=users[-1],
                revoked_at=now - timedelta(days=14), created_by=users[0])
            revoked.full_clean(exclude=["number"])
            revoked.save()

            # -- meetings: one per status ----------------------------------------------------
            steering = meeting(
                active, "Weekly steering committee", "steering", "completed", -3,
                location="Boardroom 2",
                minutes=("Agreed: the integration work package stays parked until the vendor "
                         "sandbox lands. Variance is inside tolerance at 4%. The acceptance "
                         "checklist is the last open quality item and is now owned."),
                agenda=[("Variance review", 1, 20, True),
                        ("Integration blocker", 2, 15, True),
                        ("Acceptance checklist", None, 15, True)],
                actions=[("Chase the vendor sandbox credentials", 1, -1, False, 0),
                         ("Publish the revised steering pack", 0, 3, False, None),
                         ("Close the acceptance checklist", 2, 7, False, None),
                         ("File the discovery decision log", 1, -6, True, None)])
            meeting(
                active, "Delivery standup", "standup", "in_progress", 0, recurrence="daily",
                agenda=[("Blockers", 0, 10, False),
                        ("Hand-offs", 1, 10, False),
                        ("Plan for the day", None, 10, False)])
            meeting(
                active, "Design review - reporting lens", "review", "scheduled", 5,
                recurrence="biweekly", location="Teams",
                agenda=[("Walk the report builder", 2, 30, False),
                        ("Agree the KPI set", 0, 20, False)])
            meeting(
                other, "Discovery close-out", "workshop", "cancelled", -21,
                location="Boardroom 1",
                actions=[("Archive the discovery notes", 0, -18, True, None)])

            # -- action items on the completed meeting's work packages ------------------------
            # A sixth action, linked to a real 7.2 work package, so the task join has a row.
            linked = MeetingActionItem(
                tenant=tenant, meeting=steering, description="Re-baseline the integration work "
                                                             "package once the blocker clears.",
                assignee=users[0], due_date=today - timedelta(days=2),
                task=tasks[0] if tasks else None, created_by=users[0])
            linked.full_clean(exclude=["number"])
            linked.save()
            unassigned = MeetingActionItem(
                tenant=tenant, meeting=steering,
                description="Confirm who owns the acceptance checklist before the next review.",
                due_date=today + timedelta(days=10), created_by=users[0])
            unassigned.full_clean(exclude=["number"])
            unassigned.save()

            # -- notifications: every kind, both states, every optional source ---------------
            notify(active, users[1], "mention", "Mentioned in CHN-00001 - Delivery Standup",
                   body="Heads up: the delivery date moved.", chan=standup, msg=edited)
            notify(active, users[2], "mention", "Mentioned in CHN-00001 - Delivery Standup",
                   body="Heads up: the delivery date moved.", chan=standup, msg=edited, read=True)
            notify(active, users[0], "assignment", "You own the integration work package",
                   task=tasks[0] if tasks else None)
            notify(active, users[1], "assignment", "You own the acceptance checklist",
                   task=tasks[1] if len(tasks) > 1 else None, read=True)
            notify(active, users[2], "due_date", "Action item due in 7 days",
                   body="Close the acceptance checklist.", mtg=steering)
            notify(active, users[0], "due_date", "Action item overdue by 2 days",
                   body="Re-baseline the integration work package.", mtg=steering)
            notify(active, users[1], "status_change",
                   "MTG-00001 moved to Completed", mtg=steering)
            notify(active, users[2], "status_change", "Project status moved to Active")
            notify(active, users[0], "system", "Baseline frozen at revision 0",
                   body="Changes now go through the change control board.", read=True)
            notify(active, users[1], "system", "Quality plan activated")
            notify(other, users[0], "system", "Discovery phase closed", chan=closed, read=True)
            notify(other, users[1], "mention", "Mentioned in Discovery (closed)",
                   body="Notes and the decision log are filed against the kickoff record.",
                   chan=closed)
            notify(active, users[2], "mention", "Mentioned on the shared status pack",
                   body="Owner copy - update the variance table before each steering review.")
            notify(active, users[0], "assignment", "Document share DSH-00001 is yours to edit")
            notify(active, users[1], "due_date", "Steering pack due before Thursday",
                   mtg=steering, read=True)
            notify(active, users[2], "status_change", "Work package moved to In Progress",
                   task=tasks[0] if tasks else None)
            notify(active, users[0], "system", "New message in Project Announcements",
                   chan=announce)
            notify(active, users[1], "system", "New message in Project Announcements",
                   chan=announce, read=True)

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {Channel.objects.filter(tenant=tenant).count()} channels, "
            f"{ChannelMessage.objects.filter(tenant=tenant).count()} messages, "
            f"{DocumentShare.objects.filter(tenant=tenant).count()} document shares, "
            f"{Meeting.objects.filter(tenant=tenant).count()} meetings, "
            f"{MeetingAgendaItem.objects.filter(tenant=tenant).count()} agenda items, "
            f"{MeetingActionItem.objects.filter(tenant=tenant).count()} action items, "
            f"{ProjectNotification.objects.filter(tenant=tenant).count()} notifications."))

    # -- 7.10 document & knowledge management -----------------------------------------------------

    def _docmgt(self, tenant, now):
        """7.10 document & knowledge management: the folder tree, the controlled documents with
        their approved-revision chains, the tenant-wide standards library and the knowledge
        register.

        Guarded per tenant on the FOLDER tree, because that is this block's entry point: every
        document needs a folder (``ProjectDocument.folder`` is PROTECT and required), every
        revision hangs off a document, and the standards and knowledge registers stand alone.
        Nothing here invents a project, a task, a milestone or a user — it reuses 7.1's projects
        and 7.2's plan, exactly as 7.9 does.

        **The two revision writers are modelled on their views, never hand-stamped.** The number
        comes from ``next_revision_no``, the checksum from ``file_sha256`` over the payload BEFORE
        the storage layer consumes it, and the text from ``extract_text`` AFTER the row exists —
        there is nothing on disk to read until then. ``approve`` moves the parent's integer pointer
        and copies the revision's text up into the parent's denormalized search copy, which is what
        makes the register's four-character full-text sweep demonstrably work on a fresh workspace.
        The payloads are ``.txt`` on purpose: ``.txt`` is in ``PLAIN_TEXT_EXTENSIONS``, so the
        extractor genuinely reads them without committing a binary fixture to the repository.

        **WARNING: this WRITES FILES under MEDIA_ROOT** (revisions and standards). Every
        ``ContentFile`` is minted only for a row this run just created, inside the guard's ``else``
        branch, so a second run writes none — Django's storage layer RENAMES on collision rather
        than overwriting, so a block that re-ran would quietly pile up duplicate files nobody ever
        looks at.

        Coverage per tenant: a 12-folder tree across two projects, including an ARCHIVED branch so
        the archive lens and both badge states have rows; 22 documents spanning every doc type and
        every status — one ``expected`` placeholder, one checked-out row, one under legal hold, two
        archived, one superseded, and two whose retention window has already closed; 23 revisions,
        two of them superseded pairs (v1 and v2 both approved, the pointer on v2) and four left
        pending approval; 16 standards covering every category with both publish states; and 17
        knowledge entries covering every kind and every status, three of them on the featured
        shelf. The document and knowledge registers both clear their 15-row page, so the paginator
        has a genuine page 2, and the retention board's four headline figures are all non-zero.
        """
        from django.core.files.base import ContentFile

        # Deep imports into the entity modules, never through the package re-export: `normalize_tags`
        # has a rival definition in a sibling app's repository and `next_revision_no` / `file_sha256`
        # are names several modules use, so they are reached by the module that owns them.
        from apps.projects.models.DocumentKnowledgeManagement.Revisions import (
            EXTRACT_MAX_CHARS, extract_text, file_sha256, next_revision_no)

        if ProjectFolder.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: document repository rows already exist. "
                              f"Use --flush to re-seed.")
            return

        projects = list(Project.objects.filter(tenant=tenant).order_by("id"))
        users = list(get_user_model().objects.filter(tenant=tenant, is_active=True).order_by("id"))
        if not projects or not users:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no projects or users - skipping document & knowledge "
                f"management."))
            return

        active = next((p for p in projects if p.status == "active"), projects[0])
        other = next((p for p in projects if p.pk != active.pk), None)
        tasks = list(ProjectTask.objects.filter(
            tenant=tenant, project=active, node_type="work_package").order_by("id"))
        milestones = list(ProjectMilestone.objects.filter(
            tenant=tenant, project=active).order_by("id"))
        owner = users[0]
        approver = users[-1]
        holder = users[1] if len(users) > 1 else owner
        today = timezone.localdate()

        def backdate(row, days):
            """Age a seeded row the way a real workspace would be aged.

            ``created_at`` is ``auto_now_add``, so it cannot be passed to the constructor; a
            queryset ``.update()`` bypasses the ``pre_save`` hook and is the only honest way to give
            a seeded row a past. It matters here more than anywhere: ``retain_until`` is
            ``created_at + 30 * retention_months``, so without backdating NO document could ever be
            retention-due on a fresh workspace and the retention board's headline figure would be
            structurally zero.
            """
            stamp = now - timedelta(days=days)
            type(row).objects.filter(pk=row.pk).update(created_at=stamp)
            row.created_at = stamp
            return row

        def folder(project, name, sequence, parent=None, description="", archived=False):
            row = ProjectFolder(tenant=tenant, project=project, parent=parent, name=name,
                                description=description, sequence=sequence, created_by=owner)
            if archived:
                row.is_archived = True
                row.archived_by = approver
                row.archived_at = now - timedelta(days=45)
            row.full_clean(exclude=["number"])
            row.save()
            return row

        def document(folder_row, title, doc_type, status="draft", classification="internal",
                     tags="", description="", retention_months=None, review_on=None,
                     milestone=None, task=None, doc_owner=None, hold="", archived=False,
                     checked_out=False, age_days=0):
            """One controlled document. ``folder_row`` fixes the project — never a second argument.

            The folder is PROTECT and required, so a document always has a project by construction;
            taking it from the folder rather than as a parameter is what makes "the folder belongs
            to another project" unrepresentable in this seeder (the model's ``clean()`` would refuse
            it, but a seeder should not be able to construct the error in the first place).
            """
            row = ProjectDocument(
                tenant=tenant, project=folder_row.project, folder=folder_row, title=title,
                document_type=doc_type, classification=classification, status=status, tags=tags,
                description=description, retention_months=retention_months, review_on=review_on,
                milestone=milestone, task=task, owner=doc_owner or owner, created_by=owner)
            # The hold and the archive are kept mutually exclusive: the model's clean() refuses a
            # held row that is also archived, and the seed must not need that refusal to fire.
            if hold:
                row.is_legal_hold = True
                row.hold_reason = hold
                row.held_by = approver
                row.held_at = now - timedelta(days=12)
            if archived:
                # Mirrors `pdm_archive` exactly: the status the row carried is STAMPED before the
                # verb overwrites it, so un-archiving restores it instead of guessing. `status` is
                # therefore the PRE-archive state on these calls, not "archived".
                row.pre_archive_status = row.status
                row.is_archived = True
                row.archived_by = approver
                row.archived_at = now - timedelta(days=30)
                row.status = "archived"
            if checked_out:
                row.is_checked_out = True
                row.checked_out_by = holder
                row.checked_out_at = now - timedelta(hours=6)
            row.full_clean(exclude=["number"])
            row.save()
            if age_days:
                backdate(row, age_days)
            return row

        def mint(document_row, filename, change_note, body):
            """Create the next revision the way ``pdv_upload`` does — unapproved, pointer unmoved.

            The view allocates under a ``select_for_update()`` on the parent because two uploaders
            can race; a management command is the single writer, so there is nothing to serialize
            against and no lock is taken here.
            """
            payload = ContentFile(body.encode("utf-8"), name=filename)
            digest = file_sha256(payload)
            revision = ProjectDocumentRevision(
                tenant=tenant, document=document_row, revision_no=next_revision_no(document_row),
                file=payload, checksum=digest, change_note=change_note, uploaded_by=owner)
            revision.save()
            text, note = extract_text(revision.file)
            revision.extracted_text = (text or "")[:EXTRACT_MAX_CHARS]
            revision.extraction_note = note
            revision.save(update_fields=["extracted_text", "extraction_note"])
            return revision

        def approve(document_row, revision):
            """Approve one revision the way ``pdv_approve`` does.

            Stamp the revision, move the parent's integer pointer, copy the revision's text up into
            the parent's denormalized SEARCH COPY and lift a still-open document to ``approved``.
            An earlier approved revision is deliberately LEFT approved: it was, and "only the latest
            approved version is current" is expressed by the pointer landing on exactly one row,
            never by un-approving history. That is what gives the chain its superseded pair.
            """
            revision.is_approved = True
            revision.approved_by = approver
            revision.approved_at = now - timedelta(days=1)
            revision.save(update_fields=["is_approved", "approved_by", "approved_at"])
            previous = document_row.current_revision_no
            document_row.current_revision_no = revision.revision_no
            document_row.extracted_text = (revision.extracted_text or "")[:EXTRACT_MAX_CHARS]
            if document_row.status in ("draft", "expected", "in_review"):
                document_row.status = "approved"
            document_row.save(update_fields=["current_revision_no", "extracted_text", "status",
                                             "updated_at"])
            write_audit_log(approver, revision, "update",
                            {"verb": "pdv_approve", "from": previous,
                             "to": revision.revision_no})
            return revision

        def standard(name, category, doc_type, version, is_active=True, locked=False,
                     review_on=None, description="", filename=None, body=""):
            row = DocumentTemplate(
                tenant=tenant, name=name, category=category, document_type=doc_type,
                version=version, description=description, is_active=is_active,
                is_format_locked=locked, owner=owner, review_on=review_on, created_by=owner)
            if filename:
                row.file = ContentFile(body.encode("utf-8"), name=filename)
            row.full_clean(exclude=["number"])
            row.save()
            return row

        def insight(title, kind, summary, body="", status="published", featured=False, used=0,
                    project=None, document_row=None, tags="", category=""):
            row = KnowledgeEntry(
                tenant=tenant, title=title, kind=kind, summary=summary, body=body, category=category,
                tags=tags, source_project=project, document=document_row, owner=owner,
                status=status, is_featured=featured, created_by=owner)
            # `usage_count` is `editable=False`, so `full_clean` skips it and it is assigned here.
            # It is a CLICK COUNTER — a seeded number is a plausible press count, nothing more.
            row.usage_count = used
            row.full_clean(exclude=["number"])
            row.save()
            return row

        # -- the folder tree ---------------------------------------------------------------------
        gov = folder(active, "01 Governance", 1,
                     description="Charter, approvals and the audit trail.")
        charter_folder = folder(active, "Charter & approvals", 1, parent=gov)
        status_folder = folder(active, "Status reports", 2, parent=gov)
        design = folder(active, "02 Design", 2,
                        description="Design packs, drawings and specifications.")
        drawings = folder(active, "Drawings", 1, parent=design)
        specs = folder(active, "Specifications", 2, parent=design)
        delivery = folder(active, "03 Delivery", 3,
                          description="Test evidence, handover packs and statutory certificates.")
        tests = folder(active, "Test results", 1, parent=delivery)
        handover = folder(active, "Handover", 2, parent=delivery)
        legacy = folder(active, "04 Legacy archive", 4, archived=True,
                        description="The 2024-25 programme, retained for audit.")
        other_gov = other_delivery = None
        if other is not None:
            other_gov = folder(other, "01 Governance", 1)
            other_delivery = folder(other, "02 Delivery", 2)

        # -- the controlled documents ------------------------------------------------------------
        d_charter = document(
            charter_folder, "Project charter (signed)", "charter", status="draft",
            classification="confidential", tags="Charter, governance ,signed",
            description="The approved charter, countersigned by the sponsor.",
            retention_months=84, milestone=milestones[0] if milestones else None, age_days=400)
        d_approval = document(
            charter_folder, "Charter approval memo", "other", tags="charter, approval",
            retention_months=60, age_days=395)
        d_status_aug = document(
            status_folder, "Monthly status report - August", "status_update",
            tags="status, monthly", retention_months=24,
            review_on=today + timedelta(days=12), age_days=45)
        d_status_sep = document(
            status_folder, "Monthly status report - September", "status_update",
            status="in_review", tags="status, monthly",
            review_on=today + timedelta(days=20), age_days=10)
        d_schedule = document(
            status_folder, "Baseline schedule v3", "schedule", tags="baseline, schedule",
            # Past its review date: one of the two rows the retention board's review lens shows.
            review_on=today - timedelta(days=10), age_days=120)
        d_reqs = document(
            specs, "Requirements specification (release 3)", "specification",
            classification="confidential", tags="requirements, release-3",
            retention_months=120, task=tasks[0] if tasks else None, age_days=200)
        d_ux = document(
            design, "UX design pack - ordering", "plan", tags="ux, design", age_days=150)
        d_api = document(
            drawings, "Order API interface drawing", "drawing", tags="api, drawing",
            task=tasks[1] if len(tasks) > 1 else None, age_days=100)
        d_api_test = document(
            tests, "Order API test results", "test_result", tags="test, api",
            task=tasks[1] if len(tasks) > 1 else None, age_days=40)
        d_cart_test = document(
            tests, "Cart UI test results", "test_result", status="in_review", tags="test, cart-ui",
            task=tasks[2] if len(tasks) > 2 else None, age_days=8)
        d_checkout = document(
            tests, "Checkout integration test plan", "plan", tags="checkout, test-plan",
            description="Drafted while the integration work package is still open.",
            task=tasks[3] if len(tasks) > 3 else None, checked_out=True, age_days=5)
        d_handover = document(
            handover, "Handover pack - release 3", "handover", tags="handover, release-3",
            retention_months=300, review_on=today - timedelta(days=3), age_days=20)
        d_photo = document(
            drawings, "Site photo log (scanned)", "other", tags="photo, site",
            description="Scanned pages - stored and downloadable, with no text layer to read.",
            age_days=60)
        d_nda = document(
            charter_folder, "Vendor NDA - Northwind", "other", classification="confidential",
            tags="nda, vendor", retention_months=12, age_days=400)
        d_fire = document(
            handover, "Fire safety certificate", "other", classification="public",
            tags="certificate, compliance", retention_months=6, age_days=380)
        d_expected = document(
            handover, "Decommissioning plan (slot)", "plan", status="expected",
            tags="decommissioning",
            description="A named slot created before the file exists.", age_days=2)
        d_hold = document(
            charter_folder, "Litigation bundle 2026", "other", classification="confidential",
            tags="litigation, hold",
            hold="Litigation hold raised 2026-09-01 - do not destroy.", age_days=90)
        d_superseded = document(
            specs, "Integration plan (superseded)", "plan", tags="integration",
            retention_months=36, age_days=300)
        d_arch_a = document(
            legacy, "Legacy migration spike report", "report", status="approved",
            tags="legacy, migration", archived=True, age_days=500)
        d_arch_b = document(
            legacy, "2025 status pack", "status_update", status="approved", tags="status, 2025",
            archived=True, age_days=450)
        d_other_charter = d_other_plan = None
        if other_gov is not None:
            d_other_charter = document(
                other_gov, "Charter - pilot programme", "charter", tags="charter, pilot",
                retention_months=48, age_days=250)
            d_other_plan = document(
                other_delivery, "Pilot delivery plan", "plan", tags="pilot, delivery",
                age_days=180)

        # -- the revision chains -----------------------------------------------------------------
        # The charter carries the superseded PAIR: v1 and v2 are both approved and the pointer sits
        # on v2, so v1 renders the amber "superseded" badge without any history being rewritten.
        approve(d_charter, mint(d_charter, "project-charter.txt", "Charter as first issued.",
                                "Project charter, revision 1.\nApproved scope for release 3.\n"))
        approve(d_charter, mint(d_charter, "project-charter-r2.txt",
                                "Sponsor amendments folded in.",
                                "Project charter, revision 2.\nSponsor amendments: the returns "
                                "module moves behind the checkout release.\n"))
        approve(d_approval, mint(d_approval, "charter-approval-memo.txt", "Initial upload.",
                                 "Charter approval memo.\nCountersigned by the sponsor.\n"))
        approve(d_status_aug, mint(d_status_aug, "status-2026-08.txt", "August report as issued.",
                                   "August status report.\nSchedule variance: 3 days.\n"))
        approve(d_schedule, mint(d_schedule, "baseline-schedule-v3.txt", "Third baseline.",
                                 "Baseline schedule v3.\nCritical path: workshops, SSO spike, "
                                 "order API, cart UI, checkout.\n"))
        approve(d_reqs, mint(d_reqs, "requirements-release-3.txt", "Initial upload.",
                             "Requirements specification, release 3.\nTraceability to the "
                             "requirement register.\n"))
        approve(d_reqs, mint(d_reqs, "requirements-release-3-r2.txt",
                             "Acceptance criteria sharpened after review.",
                             "Requirements specification, release 3, revision 2.\nAcceptance "
                             "criteria rewritten to be testable.\n"))
        approve(d_ux, mint(d_ux, "ux-design-pack.txt", "Initial upload.",
                           "UX design pack - ordering.\nWireframes and the interaction model.\n"))
        approve(d_api, mint(d_api, "order-api-drawing.txt", "Initial upload.",
                            "Order API interface drawing.\nEndpoint shapes and error envelope.\n"))
        approve(d_api_test, mint(d_api_test, "order-api-test-results.txt", "Initial upload.",
                                 "Order API test results.\nAll contract tests passing.\n"))
        approve(d_cart_test, mint(d_cart_test, "cart-ui-test-results.txt", "Initial upload.",
                                  "Cart UI test results.\nTwo accessibility defects open.\n"))
        # A PENDING revision behind an approved one: the register shows a green current badge
        # beside a slate pending row, which is exactly the state the pointer rule produces.
        mint(d_cart_test, "cart-ui-test-results-r2.txt",
             "Re-test after the accessibility fixes.",
             "Cart UI test results, revision 2.\nAccessibility defects retested.\n")
        mint(d_checkout, "checkout-integration-test-plan.txt", "Initial upload.",
             "Checkout integration test plan.\nAwaiting the integration work package.\n")
        mint(d_handover, "handover-pack-release-3.txt", "Initial upload.",
             "Handover pack - release 3.\nOperations runbook and support model.\n")
        approve(d_photo, mint(d_photo, "site-photo-log.txt", "Scanned pages uploaded.",
                              "Site photo log.\nThis plain-text stand-in stands for a scanned "
                              "image, which would carry no text layer.\n"))
        approve(d_nda, mint(d_nda, "vendor-nda-northwind.txt", "Signed NDA filed.",
                            "Vendor NDA - Northwind.\nExecuted copy.\n"))
        approve(d_fire, mint(d_fire, "fire-safety-certificate.txt", "Certificate filed.",
                             "Fire safety certificate.\nIssued against the new floor.\n"))
        approve(d_hold, mint(d_hold, "litigation-bundle-2026.txt", "Bundle assembled.",
                             "Litigation bundle 2026.\nCorrespondence and the decision log.\n"))
        approve(d_superseded, mint(d_superseded, "integration-plan.txt",
                                   "Initial upload, since superseded.",
                                   "Integration plan.\nSuperseded by the release 3 plan.\n"))
        # Its revision is approved and still on the pointer; the STATUS says the plan it described
        # has been replaced. Nothing was un-approved to express that.
        d_superseded.status = "superseded"
        d_superseded.save(update_fields=["status", "updated_at"])
        approve(d_arch_a, mint(d_arch_a, "legacy-migration-spike.txt", "Closed with the spike.",
                               "Legacy migration spike report.\nThe spike was cancelled.\n"))
        approve(d_arch_b, mint(d_arch_b, "status-pack-2025.txt", "Annual pack.",
                               "2025 status pack.\nTwelve monthly reports.\n"))
        if d_other_charter is not None:
            approve(d_other_charter, mint(d_other_charter, "pilot-charter.txt", "Initial upload.",
                                          "Charter - pilot programme.\nApproved for the pilot "
                                          "workspace.\n"))
            mint(d_other_plan, "pilot-delivery-plan.txt", "Initial upload.",
                 "Pilot delivery plan.\nStill in draft.\n")

        # -- the standards library (tenant-wide: no project FK, by design) -----------------------
        standard("Project charter", "charter", "charter", "3.0",
                 description="The organisation's charter format, with the approval block.",
                 filename="standard-charter.txt",
                 body="Project charter - standard format.\nSections: context, objectives, scope, "
                      "governance, approval.\n")
        standard("Project charter (light)", "charter", "charter", "1.2",
                 description="A one-page variant for small internal projects.")
        standard("Project plan", "plan", "plan", "4.1",
                 description="Work breakdown, schedule baseline and resource summary.",
                 filename="standard-project-plan.txt",
                 body="Project plan - standard format.\nWBS, schedule, resources, risks.\n")
        standard("Detailed schedule template", "schedule", "schedule", "2.0",
                 description="The level-3 schedule layout the PMO reviews against.")
        standard("Monthly status report", "status_update", "status_update", "5.0",
                 description="The monthly report the steering group receives.",
                 filename="standard-status-report.txt",
                 body="Monthly status report - standard format.\nProgress, variance, risks, "
                      "decisions needed.\n")
        standard("Weekly status note", "status_update", "status_update", "1.4", is_active=False,
                 description="Retired in favour of the monthly report.")
        standard("Steering pack", "report", "report", "2.3",
                 description="The pack circulated before each steering review.",
                 filename="standard-steering-pack.txt",
                 body="Steering pack - standard format.\nVariance table, decisions, next "
                      "period.\n")
        standard("Post-implementation review", "report", "report", "1.1",
                 description="Benefits realisation and lessons capture after go-live.")
        standard("Meeting minutes", "minutes", "minutes", "3.2",
                 description="Minutes format, with the action table the register reads.",
                 filename="standard-minutes.txt",
                 body="Meeting minutes - standard format.\nAttendees, decisions, actions with "
                      "owners and dates.\n")
        standard("Decision log", "register", "other", "1.0", locked=True,
                 description="The decision register format. The lock is recorded as intent.",
                 filename="standard-decision-log.txt",
                 body="Decision log - standard format.\nDate, decision, rationale, owner.\n")
        standard("Risk register", "register", "other", "2.6",
                 description="Risk scoring and response columns.")
        standard("Issue log", "register", "other", "1.5", is_active=False,
                 description="Retired - issues now live in the risk register.")
        standard("Handover checklist", "checklist", "handover", "2.0",
                 description="What operations needs before a release is accepted.",
                 filename="standard-handover-checklist.txt",
                 body="Handover checklist - standard format.\nRunbook, support model, "
                      "certificates, access.\n")
        standard("Go-live readiness checklist", "checklist", "other", "1.3",
                 description="The gate the release is signed off against.",
                 review_on=today - timedelta(days=5))
        standard("Benefits realisation plan", "other", "report", "1.0",
                 description="Baseline, target and measurement for each benefit.")
        standard("Lessons learned log", "other", "other", "1.2",
                 description="The capture sheet a retrospective fills in.",
                 filename="standard-lessons-log.txt",
                 body="Lessons learned log - standard format.\nWhat happened, so what, now "
                      "what.\n")

        # -- the knowledge library --------------------------------------------------------------
        insight("Anchor the SSO spike to a real identity provider", "lesson_learned",
                "A spike against a stub answered the wrong question and cost two weeks.",
                body="The spike proved our own code could talk to a stub. It told us nothing about "
                     "the client's identity provider, which is where the integration actually "
                     "broke. Next time the spike goes against the real tenant, in their "
                     "environment.",
                featured=True, used=14, project=active, tags="sso, integration, spike",
                category="Delivery")
        insight("Baseline before you forecast", "best_practice",
                "Forecasts without a frozen baseline cannot be argued with, only believed.",
                body="Every variance conversation needs a baseline both sides accepted. Freeze it, "
                     "date it, and record what changed it.",
                featured=True, used=11, project=active, tags="baseline, forecasting",
                category="Governance")
        insight("Release 3 retrospective", "retrospective",
                "What worked, what did not, and the three changes we are keeping.",
                body="Kept: the weekly integration checkpoint. Changed: requirements sign-off now "
                     "happens before estimation. Dropped: the separate design review board.",
                featured=True, used=9, project=active, tags="retrospective, release-3",
                category="Delivery")
        insight("Discovery retrospective - what the workshops missed", "retrospective",
                "We captured the happy path and missed every exception.",
                body="The workshops were run against a script. Nobody asked what happens when the "
                     "payment is declined.",
                status="retired", used=4, project=active, tags="discovery, workshops",
                category="Delivery")
        insight("Estimating integration work", "playbook",
                "A repeatable way to size work that depends on somebody else's system.",
                body="Count the interfaces, not the screens. For each interface, ask who owns the "
                     "contract, whether a test environment exists, and who can grant access. Any "
                     "answer of 'we will find out' is an unbounded risk.",
                used=13, project=active, document_row=d_handover,
                tags="estimating, integration, playbook", category="Delivery")
        insight("Running a requirements workshop", "playbook",
                "How to get testable requirements out of a room in one day.",
                body="Bring the exception cases as cards, not slides. Ask for the last three "
                     "things that went wrong with the current system before asking what the new "
                     "one should do.",
                used=12, project=active, tags="requirements, workshops, facilitation",
                category="Delivery")
        insight("Change control in practice", "playbook",
                "The route a change takes, and why the CCB needs a cost before it decides.",
                body="A change without an impact assessment is a wish. Get the cost, the schedule "
                     "effect and the risk, then decide.",
                status="draft", used=2, project=active, tags="change-control, ccb",
                category="Governance")
        insight("Go-live readiness checklist", "checklist",
                "The gate items that have actually blocked a release here.",
                body="Access provisioned in production. Rollback rehearsed. Support rota agreed. "
                     "Monitoring dashboards live. Data migration reconciled to the penny.",
                used=16, project=active, document_row=d_charter, tags="go-live, checklist",
                category="Delivery")
        insight("Data migration readiness checklist", "checklist",
                "What to confirm before the first migration rehearsal.",
                body="Row counts agreed. Field mappings signed off. Reconciliation query written. "
                     "An owner named for every source system.",
                used=7, project=active, tags="migration, checklist", category="Delivery")
        insight("Handover acceptance checklist", "checklist",
                "What operations signs when it accepts a release.",
                body="Runbook complete. Support model agreed. Certificates filed. Access "
                     "transferred. Monitoring in place.",
                used=6, project=active, document_row=d_handover, tags="handover, checklist",
                category="Delivery")
        insight("Vendor onboarding playbook", "playbook",
                "The sequence that avoids a vendor starting work without a contract.",
                body="NDA, then due diligence, then the contract, then purchase order, then "
                     "access. Never access before the order.",
                used=5, project=active, tags="vendor, onboarding, procurement",
                category="Governance")
        insight("Standard: status report format", "standard",
                "The written standard behind the monthly report template.",
                body="One page. Progress against the baseline, variance with a cause, top three "
                     "risks, decisions needed. No narrative padding.",
                used=10, project=active, tags="status, standard", category="Governance")
        insight("Standard: document naming convention", "standard",
                "Project, document type, title, revision - in that order.",
                body="`PRJ3-SPEC-Order-API-v2`. The type segment comes from the register's own "
                     "document-type vocabulary so the two agree.",
                used=8, project=active, tags="naming, standard, repository",
                category="Governance")
        insight("Template: decision log entry", "template",
                "The four fields a decision needs to be usable later.",
                body="Date, decision, rationale, owner. The rationale is the field everybody "
                     "skips and everybody needs eighteen months later.",
                used=3, project=active, tags="decision, template", category="Governance")
        insight("Template: risk description", "template",
                "Cause, event, consequence - so the description can be scored.",
                body="Because of <cause>, <event> may occur, resulting in <consequence>. Without "
                     "all three the score is a guess.",
                status="draft", used=1, project=active, tags="risk, template",
                category="Governance")
        insight("Lessons from the legacy migration spike", "lesson_learned",
                "A spike that was cancelled still paid for itself.",
                body="We spent four days and learned the legacy schema could not be mapped "
                     "automatically. That was cheaper than finding out during delivery.",
                used=6, project=active, document_row=d_arch_a, tags="legacy, migration, spike",
                category="Delivery")
        insight("Cost variance triage", "lesson_learned",
                "Separate the variance you caused from the variance you inherited.",
                body="Inherited variance is a conversation with the sponsor. Self-inflicted "
                     "variance is a conversation with the team. Mixing them hides both.",
                status="draft", used=0, project=other, tags="cost, variance",
                category="Cost")

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {ProjectFolder.objects.filter(tenant=tenant).count()} folders, "
            f"{ProjectDocument.objects.filter(tenant=tenant).count()} documents, "
            f"{ProjectDocumentRevision.objects.filter(tenant=tenant).count()} revisions, "
            f"{DocumentTemplate.objects.filter(tenant=tenant).count()} standards, "
            f"{KnowledgeEntry.objects.filter(tenant=tenant).count()} knowledge entries."))


    def _time_attendance(self, tenant, now):
        """7.11 Time & Attendance Tracking: activity codes, overtime rules, overtime records."""
        if TimeActivityCode.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: 7.11 time & attendance tracking already seeded.")
            return

        today = timezone.localdate()
        with transaction.atomic():
            # 1. Standard Activity Codes
            activity_specs = [
                ("DEV", "Software Development", "direct_project", True, "Core application programming and feature development."),
                ("QA", "Quality Assurance & Testing", "direct_project", True, "Manual & automated test case execution and defect verification."),
                ("UI", "UI/UX & Product Design", "direct_project", True, "Wireframing, mockups, design system components, and usability review."),
                ("PM", "Project Management & Agile Delivery", "direct_project", True, "Sprint planning, stakeholder reviews, WBS tracking, and status reports."),
                ("MTG", "Client Meetings & Advisory", "client_service", True, "Direct meetings with client project teams and consulting."),
                ("ADM", "General Administration & Overhead", "general_admin", False, "Administrative work, workspace management, and internal coordination."),
                ("TRN", "Training & Professional Development", "training", False, "Continuing technical education, certifications, and workshops."),
                ("RD", "Internal Research & Innovation", "research_dev", False, "Prototyping, architectural spikes, and internal tooling."),
            ]
            codes = {}
            for code, name, cat, billable, desc in activity_specs:
                tac = TimeActivityCode(
                    tenant=tenant,
                    code=code,
                    name=name,
                    category=cat,
                    is_billable_default=billable,
                    is_active=True,
                    description=desc,
                )
                tac.save()
                codes[code] = tac

            # 2. Overtime Rules
            active_project = Project.objects.filter(tenant=tenant, status="active").order_by("id").first()
            rule_default = OvertimeRule(
                tenant=tenant,
                project=None,
                name="Standard Company Overtime Policy",
                standard_daily_hours=Decimal("8.00"),
                standard_weekly_hours=Decimal("40.00"),
                daily_overtime_multiplier=Decimal("1.50"),
                weekly_overtime_multiplier=Decimal("1.50"),
                weekend_multiplier=Decimal("1.50"),
                holiday_multiplier=Decimal("2.00"),
                requires_pre_approval=False,
                is_active=True,
                notes="Default company policy for project overtime.",
            )
            rule_default.save()

            if active_project:
                rule_project = OvertimeRule(
                    tenant=tenant,
                    project=active_project,
                    name=f"{active_project.name} Premium Delivery Rule",
                    standard_daily_hours=Decimal("8.00"),
                    standard_weekly_hours=Decimal("40.00"),
                    daily_overtime_multiplier=Decimal("1.50"),
                    weekly_overtime_multiplier=Decimal("1.50"),
                    weekend_multiplier=Decimal("2.00"),
                    holiday_multiplier=Decimal("2.50"),
                    requires_pre_approval=True,
                    is_active=True,
                    notes="Project specific overtime rule for critical deliverables.",
                )
                rule_project.save()

            # 3. Update existing ResourceTimeEntry rows with activity codes and billable flags
            entries = list(ResourceTimeEntry.objects.filter(tenant=tenant).order_by("id"))
            code_cycle = ["DEV", "QA", "UI", "PM", "MTG", "ADM"]
            for idx, entry in enumerate(entries):
                code_name = code_cycle[idx % len(code_cycle)]
                entry.activity_code = code_name
                entry.is_billable = codes[code_name].is_billable_default
                entry.save(update_fields=["activity_code", "is_billable"])

            # 4. Project Overtime Records
            profiles = list(ResourceProfile.objects.filter(tenant=tenant, status="active").order_by("id"))
            users = list(get_user_model().objects.filter(tenant=tenant).order_by("id"))
            manager = users[2] if len(users) > 2 else users[0]

            if profiles and active_project:
                ot1 = ProjectOvertimeRecord(
                    tenant=tenant,
                    resource=profiles[0],
                    project=active_project,
                    date=today - timedelta(days=2),
                    overtime_hours=Decimal("3.50"),
                    overtime_type="daily",
                    pay_multiplier=Decimal("1.50"),
                    billable_multiplier=Decimal("1.25"),
                    is_billable=True,
                    status="approved",
                    approved_by=manager,
                    approved_at=now,
                    notes="Sprint deadline overtime for critical bug triage.",
                )
                ot1.save()

                ot2 = ProjectOvertimeRecord(
                    tenant=tenant,
                    resource=profiles[1] if len(profiles) > 1 else profiles[0],
                    project=active_project,
                    date=today - timedelta(days=1),
                    overtime_hours=Decimal("4.00"),
                    overtime_type="weekend",
                    pay_multiplier=Decimal("1.50"),
                    billable_multiplier=Decimal("1.00"),
                    is_billable=True,
                    status="submitted",
                    submitted_at=now,
                    notes="Weekend emergency server migration and cutover support.",
                )
                ot2.save()

                ot3 = ProjectOvertimeRecord(
                    tenant=tenant,
                    resource=profiles[0],
                    project=active_project,
                    date=today,
                    overtime_hours=Decimal("2.00"),
                    overtime_type="daily",
                    pay_multiplier=Decimal("1.50"),
                    billable_multiplier=Decimal("1.00"),
                    is_billable=True,
                    status="draft",
                    notes="Draft overtime claim.",
                )
                ot3.save()

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: 7.11 seeded: {len(activity_specs)} activity codes, "
            f"2 overtime rules, 3 overtime records, time entries updated."))

    def _portfolio_management(self, tenant, now):
        """7.12 Portfolio & Program Management: portfolios, programs, investments, dependencies."""
        if Portfolio.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: 7.12 portfolio & program management already seeded.")
            return

        projects_qs = Project.objects.filter(tenant=tenant).order_by("id")
        if not projects_qs.exists():
            return

        projects_list = list(projects_qs)
        active_proj = projects_list[0]
        second_proj = projects_list[1] if len(projects_list) > 1 else active_proj
        third_proj = projects_list[2] if len(projects_list) > 2 else active_proj

        User = get_user_model()
        users = list(User.objects.filter(tenant=tenant).order_by("id"))
        owner = users[0] if users else None
        manager = users[1] if len(users) > 1 else owner
        currency = self._currency()

        with transaction.atomic():
            # 1. Portfolios
            prt1 = Portfolio(
                tenant=tenant,
                name="Digital Transformation & Modernization",
                code="DTM-2026",
                description="Core portfolio governing cloud ERP transition, platform modernization, and process automation.",
                status="active",
                owner=owner,
                strategic_theme="transformation",
                budget_envelope=Decimal("2500000.00"),
                currency=currency,
                start_date=timezone.localdate() - timezone.timedelta(days=90),
                end_date=timezone.localdate() + timezone.timedelta(days=275),
                is_active=True,
            )
            prt1.save()

            prt2 = Portfolio(
                tenant=tenant,
                name="Operational Excellence & Growth",
                code="OEG-2026",
                description="Strategic expansion into new operational territories and customer experience enhancement.",
                status="active",
                owner=owner,
                strategic_theme="growth",
                budget_envelope=Decimal("1200000.00"),
                currency=currency,
                start_date=timezone.localdate() - timezone.timedelta(days=60),
                end_date=timezone.localdate() + timezone.timedelta(days=300),
                is_active=True,
            )
            prt2.save()

            # 2. Programs
            pgm1 = Program(
                tenant=tenant,
                portfolio=prt1,
                name="Core Enterprise Cloud Modernization",
                code="PGM-CLOUD",
                description="Consolidated program rolling out infrastructure, microservices, and ERP foundational layers.",
                manager=manager,
                status="active",
                target_start_date=timezone.localdate() - timezone.timedelta(days=90),
                target_end_date=timezone.localdate() + timezone.timedelta(days=180),
                objectives="Migrate 100% of monolithic workloads to multi-tenant cloud; reduce incident response time by 40%.",
                budget_target=Decimal("1500000.00"),
            )
            pgm1.save()

            pgm2 = Program(
                tenant=tenant,
                portfolio=prt1,
                name="Intelligent Automation & AI Enablement",
                code="PGM-AUTO",
                description="Integration of automated workflows, ML pipelines, and customer self-service portals.",
                manager=manager,
                status="planning",
                target_start_date=timezone.localdate(),
                target_end_date=timezone.localdate() + timezone.timedelta(days=270),
                objectives="Automate top 15 repetitive operational workflows; improve throughput by 25%.",
                budget_target=Decimal("800000.00"),
            )
            pgm2.save()

            pgm3 = Program(
                tenant=tenant,
                portfolio=prt2,
                name="Regional Operations Expansion",
                code="PGM-ROX",
                description="Scaling logistics hubs, regional supply chain presence, and local onboarding.",
                manager=owner,
                status="active",
                target_start_date=timezone.localdate() - timezone.timedelta(days=45),
                target_end_date=timezone.localdate() + timezone.timedelta(days=300),
                objectives="Establish 3 regional delivery centers and achieve full compliance.",
                budget_target=Decimal("950000.00"),
            )
            pgm3.save()

            # 3. Portfolio Investments & Multi-Criteria Scoring
            pin1 = PortfolioInvestment(
                tenant=tenant,
                portfolio=prt1,
                project=active_proj,
                program=pgm1,
                status="funded",
                strategic_fit=90,
                financial_return=85,
                delivery_risk=80,
                capacity_fit=85,
                weight_strategic=30,
                weight_financial=30,
                weight_risk=20,
                weight_capacity=20,
                allocated_budget=Decimal("750000.00"),
                approved_by=owner,
                approved_at=now - timezone.timedelta(days=60),
                decision_notes="Priority 1 strategic foundation project. Fully funded with executive sponsorship.",
            )
            pin1.save()

            pin2 = PortfolioInvestment(
                tenant=tenant,
                portfolio=prt1,
                project=second_proj,
                program=pgm2,
                status="under_review",
                strategic_fit=80,
                financial_return=75,
                delivery_risk=70,
                capacity_fit=65,
                weight_strategic=25,
                weight_financial=25,
                weight_risk=25,
                weight_capacity=25,
                allocated_budget=Decimal("400000.00"),
                decision_notes="High ROI potential; awaiting final Q3 resource allocation review before full funding.",
            )
            pin2.save()

            if third_proj != active_proj and third_proj != second_proj:
                pin3 = PortfolioInvestment(
                    tenant=tenant,
                    portfolio=prt2,
                    project=third_proj,
                    program=pgm3,
                    status="funded",
                    strategic_fit=85,
                    financial_return=80,
                    delivery_risk=75,
                    capacity_fit=80,
                    allocated_budget=Decimal("500000.00"),
                    approved_by=owner,
                    approved_at=now - timezone.timedelta(days=30),
                    decision_notes="Approved for expansion wave 1.",
                )
                pin3.save()

            # 4. Program Dependencies
            if second_proj != active_proj:
                dep1 = ProgramDependency(
                    tenant=tenant,
                    source_project=active_proj,
                    target_project=second_proj,
                    program=pgm1,
                    dependency_type="finish_to_start",
                    criticality="critical",
                    status="open",
                    lead_lag_days=7,
                    description="Cloud architecture baseline and authentication layer must land before AI API integration begins.",
                    owner=owner,
                )
                dep1.save()

                dep2 = ProgramDependency(
                    tenant=tenant,
                    source_project=active_proj,
                    target_project=second_proj,
                    program=pgm1,
                    dependency_type="shared_resource",
                    criticality="high",
                    status="mitigated",
                    lead_lag_days=0,
                    description="Lead database architect shared across foundation and data ingestion work packages.",
                    owner=manager,
                )
                dep2.save()

            if third_proj != active_proj:
                dep3 = ProgramDependency(
                    tenant=tenant,
                    source_project=active_proj,
                    target_project=third_proj,
                    program=None,
                    dependency_type="deliverable_handover",
                    criticality="medium",
                    status="cleared",
                    cleared_at=now - timezone.timedelta(days=10),
                    description="Core API integration endpoints handed over for regional branch testing.",
                    owner=owner,
                )
                dep3.save()

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: 7.12 seeded: 2 portfolios, 3 programs, investments & dependencies."))


    def _agile_scrum(self, tenant, now):
        """7.13 Agile & Scrum Management: sprints, epics, releases, impediments, and retrospectives."""
        if Sprint.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: 7.13 Agile & Scrum Management already seeded — skipping.")
            return

        today = now.date()
        active_proj = Project.objects.filter(tenant=tenant, status="active").order_by("id").first()
        if not active_proj:
            active_proj = Project.objects.filter(tenant=tenant).order_by("id").first()
        if not active_proj:
            return

        second_proj = Project.objects.filter(tenant=tenant).exclude(id=active_proj.id).first() or active_proj

        manager = (
            active_proj.project_manager
            or active_proj.created_by
            or get_user_model().objects.filter(tenant=tenant, is_superuser=False).first()
        )

        with transaction.atomic():
            # 1. Epics
            epc1 = ProjectEpic(
                tenant=tenant,
                project=active_proj,
                name="Customer Onboarding & Authentication",
                summary="Unified SSO, OAuth 2.0 gateway, and responsive profile registration flows.",
                status="completed",
                owner=manager,
                target_start=today - timedelta(days=60),
                target_end=today - timedelta(days=35),
                color_code="#10b981",
            )
            epc1.save()

            epc2 = ProjectEpic(
                tenant=tenant,
                project=active_proj,
                name="Core Transaction & Checkout Flow",
                summary="Self-service ordering API, interactive cart UI, and payment gateway integration.",
                status="in_progress",
                owner=manager,
                target_start=today - timedelta(days=35),
                target_end=today + timedelta(days=25),
                color_code="#3b82f6",
            )
            epc2.save()

            epc3 = ProjectEpic(
                tenant=tenant,
                project=second_proj,
                name="Self-Service Returns & Refunds",
                summary="Customer return request portal, RMA workflow, and automated ledger refund reconciliation.",
                status="draft",
                owner=manager,
                target_start=today + timedelta(days=20),
                target_end=today + timedelta(days=75),
                color_code="#8b5cf6",
            )
            epc3.save()

            # 2. Releases
            rel1 = ProjectRelease(
                tenant=tenant,
                project=active_proj,
                name="v1.0-GA Core Platform Release",
                version_tag="v1.0.0",
                status="released",
                release_date=today - timedelta(days=30),
                released_at=now - timedelta(days=30),
                released_by=manager,
                release_notes="Initial General Availability release delivering customer authentication and order API foundations.",
                feature_flags="AUTH_SSO=true, ORDER_API_V1=true, CART_V1=true",
            )
            rel1.save()

            rel2 = ProjectRelease(
                tenant=tenant,
                project=active_proj,
                name="v1.1-Beta Cart & Checkout Stream",
                version_tag="v1.1.0-beta",
                status="in_progress",
                release_date=today + timedelta(days=25),
                release_notes="Public beta introducing modernized shopping cart and checkout integrations.",
                feature_flags="CART_STREAM=true, CHECKOUT_V2=false, PAYMENTS_SANDBOX=true",
            )
            rel2.save()

            rel3 = ProjectRelease(
                tenant=tenant,
                project=second_proj,
                name="v2.0-Alpha Customer Portal & Returns",
                version_tag="v2.0.0-alpha",
                status="unreleased",
                release_date=today + timedelta(days=90),
                release_notes="Major version release with self-service customer returns portal.",
                feature_flags="RETURNS_PORTAL=false, AUTOMATED_REFUNDS=false",
            )
            rel3.save()

            # 3. Sprints
            spt1 = Sprint(
                tenant=tenant,
                project=active_proj,
                name="Sprint 1 — Discovery & Authentication Spike",
                goal="Establish requirements baseline and deliver operational SSO authentication spike.",
                status="completed",
                start_date=today - timedelta(days=60),
                end_date=today - timedelta(days=46),
                committed_points=34,
                scrum_master=manager,
                standup_notes="Sprint goal achieved 100%. Authentication spike integrated ahead of schedule.",
                started_at=now - timedelta(days=60),
                completed_at=now - timedelta(days=46),
            )
            spt1.save()

            spt2 = Sprint(
                tenant=tenant,
                project=active_proj,
                name="Sprint 2 — Order API & UX Wireframing",
                goal="Design cart interface and build robust high-throughput order intake endpoints.",
                status="completed",
                start_date=today - timedelta(days=45),
                end_date=today - timedelta(days=31),
                committed_points=21,
                scrum_master=manager,
                standup_notes="Order API contracts signed off; UX design prototypes validated by client stakeholders.",
                started_at=now - timedelta(days=45),
                completed_at=now - timedelta(days=31),
            )
            spt2.save()

            spt3 = Sprint(
                tenant=tenant,
                project=active_proj,
                name="Sprint 3 — Cart Engine & Checkout Integration",
                goal="Implement stateful cart engine and connect payment gateway checkout flow.",
                status="active",
                start_date=today - timedelta(days=14),
                end_date=today + timedelta(days=14),
                committed_points=34,
                scrum_master=manager,
                standup_notes="Daily standup: Checkout integration underway. 1 critical impediment resolved on SSL renewal.",
                started_at=now - timedelta(days=14),
            )
            spt3.save()

            spt4 = Sprint(
                tenant=tenant,
                project=active_proj,
                name="Sprint 4 — Returns Module & Stabilization",
                goal="Begin returns portal groundwork and perform end-to-end regression stabilization.",
                status="planning",
                start_date=today + timedelta(days=15),
                end_date=today + timedelta(days=35),
                committed_points=0,
                scrum_master=manager,
                standup_notes="Backlog grooming in progress. Story point estimates pending final team sizing.",
            )
            spt4.save()

            # 4. Link existing tasks on active_proj to sprints, epics, releases, and story points
            task_mapping = [
                ("Requirements workshops", 8, spt1, epc1, rel1),
                ("UX design: ordering", 13, spt1, epc1, rel1),
                ("Technical spike: SSO", 13, spt1, epc1, rel1),
                ("Order API", 21, spt2, epc2, rel1),
                ("Cart UI", 13, spt3, epc2, rel2),
                ("Checkout integration", 21, spt3, epc2, rel2),
                ("Returns portal UI", 13, spt4, epc3, rel3),
                ("Refund service hooks", 8, None, epc3, rel3),
            ]

            for tname, pts, sp, ep, rel in task_mapping:
                t = ProjectTask.objects.filter(tenant=tenant, project=active_proj, name=tname).first()
                if t:
                    t.story_points = pts
                    t.sprint = sp
                    t.epic = ep
                    t.release = rel
                    t.save(update_fields=["story_points", "sprint", "epic", "release"])

            # 5. Sprint Impediments
            imp1 = SprintImpediment(
                tenant=tenant,
                sprint=spt3,
                title="Payment gateway sandbox latency spikes",
                description="Simulated checkout responses intermittently timing out during automated test sweeps.",
                severity="high",
                status="open",
                owner=manager,
                raised_by=manager,
            )
            imp1.save()

            imp2 = SprintImpediment(
                tenant=tenant,
                sprint=spt3,
                title="Third-party SSL certificate renewal pending",
                description="Sandbox webhook callback endpoint SSL certificate expiring within 48 hours.",
                severity="critical",
                status="resolved",
                owner=manager,
                raised_by=manager,
                resolved_at=now - timedelta(days=2),
                resolution_notes="Renewed wildcard SSL certificate and verified TLS 1.3 handshake across all callbacks.",
            )
            imp2.save()

            # 6. Sprint Retrospectives
            ret1 = SprintRetrospective(
                tenant=tenant,
                sprint=spt1,
                conducted_date=today - timedelta(days=45),
                conducted_by=manager,
                status="closed",
                sentiment_score=Decimal("4.2"),
                what_went_well="Strong team alignment on discovery goals. SSO technical spike delivered earlier than planned.",
                what_needs_improvement="Spike acceptance criteria had slight ambiguity during mid-sprint review.",
                action_items="Adopt formal spike contract template for upcoming technical proofs.",
                closed_at=now - timedelta(days=45),
            )
            ret1.save()

            ret2 = SprintRetrospective(
                tenant=tenant,
                sprint=spt2,
                conducted_date=today - timedelta(days=30),
                conducted_by=manager,
                status="closed",
                sentiment_score=Decimal("4.6"),
                what_went_well="Order API delivered with 100% automated test coverage. Flawless stakeholder demo.",
                what_needs_improvement="Deployment notifications between backend and UI devs were inconsistent.",
                action_items="Configure automated CI/CD Slack notification bot on staging deployment completions.",
                closed_at=now - timedelta(days=30),
            )
            ret2.save()

            ret3 = SprintRetrospective(
                tenant=tenant,
                sprint=spt3,
                conducted_date=today,
                conducted_by=manager,
                status="open",
                sentiment_score=Decimal("3.8"),
                what_went_well="Solid velocity on cart UI components and responsive checkout views.",
                what_needs_improvement="Payment sandbox instability created testing delays.",
                action_items="Escalate sandbox provider SLA and configure mock payment adapter for unit test suite.",
            )
            ret3.save()

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: 7.13 seeded: 4 sprints, 3 epics, 3 releases, 2 impediments, 3 retrospectives, updated agile tasks."))

    def _client_collaboration(self, tenant, now):
        """7.14 Client & External Collaboration: client portal access, approval requests,
        SOWs & amendments, vendor handoffs, and client billing schedules."""
        if ClientPortalAccess.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: 7.14 Client & External Collaboration already seeded — skipping.")
            return

        today = now.date()
        active_proj = Project.objects.filter(tenant=tenant, status="active").order_by("id").first()
        if not active_proj:
            active_proj = Project.objects.filter(tenant=tenant).order_by("id").first()
        if not active_proj:
            return

        second_proj = Project.objects.filter(tenant=tenant).exclude(id=active_proj.id).first() or active_proj

        manager = (
            active_proj.project_manager
            or active_proj.created_by
            or get_user_model().objects.filter(tenant=tenant, is_superuser=False).first()
        )

        client_party = self._client(tenant)
        if not client_party:
            return

        other_parties = list(Party.objects.filter(tenant=tenant).exclude(id=client_party.id)[:5])
        second_contact = other_parties[0] if other_parties else client_party
        third_contact = other_parties[1] if len(other_parties) > 1 else client_party

        vendor_party = (
            Party.objects.filter(tenant=tenant, roles__role="supplier").first()
            or Party.objects.filter(tenant=tenant, roles__role="vendor").first()
            or second_contact
        )

        milestone = ProjectMilestone.objects.filter(tenant=tenant, project=active_proj).first()
        task = ProjectTask.objects.filter(tenant=tenant, project=active_proj).first()
        doc = Document.objects.filter(tenant=tenant).first()
        currency = self._currency()

        with transaction.atomic():
            # 1. Client Portal Access
            cpa1 = ClientPortalAccess(
                tenant=tenant,
                project=active_proj,
                client_contact=client_party,
                portal_user=None,
                can_view_progress=True,
                can_view_milestones=True,
                can_view_deliverables=True,
                can_view_financials=True,
                can_submit_feedback=True,
                is_active=True,
                notes="Primary client delivery lead portal profile.",
            )
            cpa1.save()

            cpa2 = ClientPortalAccess(
                tenant=tenant,
                project=active_proj,
                client_contact=second_contact,
                portal_user=None,
                can_view_progress=True,
                can_view_milestones=True,
                can_view_deliverables=True,
                can_view_financials=False,
                can_submit_feedback=False,
                is_active=True,
                notes="Executive sponsor read-only visibility.",
            )
            cpa2.save()

            cpa3 = ClientPortalAccess(
                tenant=tenant,
                project=second_proj,
                client_contact=third_contact,
                portal_user=None,
                can_view_progress=False,
                can_view_milestones=False,
                can_view_deliverables=False,
                can_view_financials=False,
                can_submit_feedback=False,
                is_active=False,
                notes="Former auditor account - access revoked.",
            )
            cpa3.save()


            # 2. Client Approval Requests
            cfb1 = ClientApprovalRequest(
                tenant=tenant,
                project=active_proj,
                deliverable_name="System Architecture & Cloud Threat Model",
                document=doc,
                milestone=milestone,
                requested_by=manager,
                assigned_contact=client_party,
                status="approved",
                due_date=today - timedelta(days=10),
                signed_by_name="Jane Client",
                signed_at=now - timedelta(days=12),
                review_notes="Comprehensive architecture document reviewed with external security team.",
                client_feedback="Approved without reservations. Clean threat boundary definitions.",
            )
            cfb1.save()

            cfb2 = ClientApprovalRequest(
                tenant=tenant,
                project=active_proj,
                deliverable_name="Sprint 1 Functional Deliverables & Acceptance Demo",
                document=None,
                milestone=milestone,
                requested_by=manager,
                assigned_contact=client_party,
                status="pending_review",
                due_date=today + timedelta(days=5),
                review_notes="Please verify end-to-end checkout flow on staging before Friday.",
                client_feedback="",
            )
            cfb2.save()

            cfb3 = ClientApprovalRequest(
                tenant=tenant,
                project=second_proj,
                deliverable_name="Draft UI Design System & Component Guidelines",
                document=None,
                milestone=None,
                requested_by=manager,
                assigned_contact=client_party,
                status="rejected",
                due_date=today - timedelta(days=2),
                rejection_reason="Color palette in high-contrast mode does not comply with WCAG 2.1 AA.",
                review_notes="Initial design token export for client brand review.",
                client_feedback="Requires color contrast revisions on warning and error states.",
            )
            cfb3.save()

            # 3. Statement of Work & Amendments
            sow1 = StatementOfWork(
                tenant=tenant,
                project=active_proj,
                client=client_party,
                title="Enterprise Platform Core Implementation",
                sow_code="SOW-2026-001",
                billing_type="milestone_based",
                contract_value=Decimal("185000.00"),
                currency=currency,
                start_date=today - timedelta(days=60),
                end_date=today + timedelta(days=120),
                status="amended",
                scope_summary="Full delivery of backend ERP services, data ingestion pipelines, and client portal.",
                terms_and_conditions="Net 30 payment terms upon milestone acceptance signoff.",
                activated_at=now - timedelta(days=60),
                activated_by=manager,
            )
            sow1.save()

            swa1 = SOWAmendment(
                tenant=tenant,
                sow=sow1,
                amendment_number=1,
                title="Mobile Companion Application Addendum",
                effective_date=today - timedelta(days=15),
                value_change=Decimal("35000.00"),
                revised_scope="Include iOS and Android responsive companion shells with push notification services.",
                justification="Client executive request to support warehouse field staff on handheld tablets.",
                status="approved",
                approved_by=manager,
                approved_at=now - timedelta(days=15),
            )
            swa1.save()

            sow2 = StatementOfWork(
                tenant=tenant,
                project=second_proj,
                client=client_party,
                title="Cloud Infrastructure Optimization & Security Hardening",
                sow_code="SOW-2026-002",
                billing_type="time_and_materials",
                contract_value=Decimal("75000.00"),
                currency=currency,
                start_date=today + timedelta(days=15),
                end_date=today + timedelta(days=180),
                status="draft",
                scope_summary="Multi-region disaster recovery setup and automated Kubernetes scaling policies.",
                terms_and_conditions="Bi-weekly T&M invoices with attached verified consultant timesheets.",
            )
            sow2.save()

            # 4. Vendor Handoffs
            vhd1 = VendorHandoff(
                tenant=tenant,
                project=active_proj,
                vendor=vendor_party,
                task=task,
                title="Third-Party Penetration Testing & Vulnerability Assessment",
                handoff_date=today - timedelta(days=30),
                due_date=today - timedelta(days=10),
                description="OWASP Top 10 penetration testing report with verified remediation steps.",
                status="accepted",
                scorecard_rating=5,
                performance_notes="Delivered 3 days ahead of schedule with zero missed critical items.",
                accepted_at=now - timedelta(days=8),
                accepted_by=manager,
            )
            vhd1.save()

            vhd2 = VendorHandoff(
                tenant=tenant,
                project=active_proj,
                vendor=vendor_party,
                task=task,
                title="External Load & Performance Stress Testing",
                handoff_date=today - timedelta(days=5),
                due_date=today + timedelta(days=10),
                description="Distributed JMeter stress testing up to 50,000 simulated concurrent users.",
                status="in_progress",
            )
            vhd2.save()

            vhd3 = VendorHandoff(
                tenant=tenant,
                project=second_proj,
                vendor=vendor_party,
                task=None,
                title="Legacy Customer Data Scrubbing Pipeline",
                handoff_date=today - timedelta(days=20),
                due_date=today - timedelta(days=5),
                description="ETL script extracting historical purchase records to UTF-8 CSV.",
                status="rejected",
                deficiency_notes="Scripts failed on accented characters and invalid tax identifiers.",
            )
            vhd3.save()

            # 5. Project Client Invoices
            pci1 = ProjectClientInvoice(
                tenant=tenant,
                project=active_proj,
                sow=sow1,
                milestone=milestone,
                billing_type="milestone",
                billing_date=today - timedelta(days=15),
                due_date=today + timedelta(days=15),
                currency=currency,
                amount=Decimal("50000.00"),
                tax_amount=Decimal("5000.00"),
                status="ready_to_bill",
                notes="Milestone 1 completion billing: Architecture design and baseline schemas signed off.",
            )
            pci1.save()

            pci2 = ProjectClientInvoice(
                tenant=tenant,
                project=active_proj,
                sow=sow1,
                milestone=None,
                billing_type="fixed_fee",
                billing_date=today + timedelta(days=15),
                due_date=today + timedelta(days=45),
                currency=currency,
                amount=Decimal("40000.00"),
                tax_amount=Decimal("4000.00"),
                status="draft",
                notes="Project kickoff retainer fee and initial platform configuration allowance.",
            )
            pci2.save()

            pci3 = ProjectClientInvoice(
                tenant=tenant,
                project=second_proj,
                sow=sow2,
                milestone=None,
                billing_type="time_and_materials",
                billing_date=today + timedelta(days=30),
                due_date=today + timedelta(days=60),
                currency=currency,
                amount=Decimal("22500.00"),
                tax_amount=Decimal("2250.00"),
                status="draft",
                notes="Estimated month 1 engineering sprint hours (150 hours @ 150/hr).",
            )
            pci3.save()

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: 7.14 seeded: 3 portal access rows, 3 approval requests, 2 SOWs (+1 amendment), 3 vendor handoffs, 3 billing schedules."))

    def _client(self, tenant):
        """A Party carrying a customer role, else any party — never a new duplicate master."""
        role = PartyRole.objects.filter(tenant=tenant, role="customer").select_related("party").first()
        if role is not None and role.party_id:
            return role.party
        return Party.objects.filter(tenant=tenant).order_by("id").first()

    def _currency(self):
        """accounting.Currency is GLOBAL — no tenant filter (L29)."""
        try:
            from apps.accounting.models import Currency
        except ImportError:
            return None
        return Currency.objects.order_by("id").first()

    def _print_logins(self):
        admins = list(get_user_model().objects.filter(
            is_superuser=False, tenant__isnull=False).order_by("tenant__name", "username"))
        self.stdout.write("")
        self.stdout.write("Log in as a TENANT ADMIN to see the data:")
        for u in admins[:8]:
            self.stdout.write(f"  {u.username}  (tenant: {u.tenant})")
        self.stdout.write(self.style.WARNING(
            "  Superuser 'admin' has no tenant — data won't appear when logged in as admin"))
