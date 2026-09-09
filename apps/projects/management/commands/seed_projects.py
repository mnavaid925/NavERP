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

from apps.core.models import Activity, OrgUnit, Party, PartyRole, Tenant
from apps.core.utils import write_audit_log
from apps.projects.models import (
    Project,
    ProjectKickoff,
    ProjectMilestone,
    ProjectRequest,
    ProjectStakeholder,
    ProjectTask,
    ScheduleBaseline,
    TaskDependency,
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
    help = "Seed Module 7 Project Management demo data (7.1 Initiation & 7.2 Planning)."
    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help=("Delete ALL projects rows for ALL tenants before seeding "
                  "(baselines, milestones, dependencies, tasks, kickoffs, stakeholders, "
                  "projects, requests) - not just seeder-created ones."))

    def handle(self, *args, **options):
        if options["flush"]:
            # Children first: dependencies and milestones hang off tasks, tasks and baselines
            # hang off projects, requests own the converted_project link (SET_NULL).
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
