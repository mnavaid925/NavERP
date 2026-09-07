"""Seed Project Management (Module 7) demo data — 7.1 Project Initiation & Charter.

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
from apps.projects.models import Project, ProjectKickoff, ProjectRequest, ProjectStakeholder


class Command(BaseCommand):
    help = "Seed Module 7 Project Management demo data (7.1 Project Initiation & Charter)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help=("Delete ALL projects rows for ALL tenants before seeding "
                  "(kickoffs, stakeholders, projects, requests) - not just seeder-created ones."))

    def handle(self, *args, **options):
        if options["flush"]:
            # Children first: stakeholders and kickoffs reference their project (CASCADE, but
            # cleanest in order); requests own the converted_project link (SET_NULL).
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
            return

        currency = self._currency()
        requester, approver = users[0], users[-1]
        sponsor = users[1] if len(users) > 1 else approver
        manager = users[2] if len(users) > 2 else approver

        with transaction.atomic():
            requests = self._requests(tenant, now, org_unit, party, currency, requester, approver)
            converted = self._convert(tenant, requests, now)
            projects = self._projects(tenant, now, org_unit, party, sponsor, manager, converted)
            self._stakeholders(tenant, projects[0], party, users, manager)
            self._kickoffs(tenant, now, projects)
            self._activities(tenant, now, projects[2], manager)

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {len(requests)} requests, {len(projects)} projects, "
            f"{ProjectStakeholder.objects.filter(tenant=tenant).count()} stakeholders, "
            f"{ProjectKickoff.objects.filter(tenant=tenant).count()} kickoffs."))

    # -- blocks ----------------------------------------------------------------------------------

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
        for row in rows:
            status = row.pop("status")
            obj = ProjectRequest(
                tenant=tenant, requested_by=requester, requester_party=party,
                org_unit=org_unit, currency=currency, assigned_approver=approver,
                created_by=requester, status=status, **row)
            obj.save()
            created.append(obj)
            if status not in ("draft",):
                obj.submitted_at = timezone.now() - timedelta(days=len(created))
                obj.save(update_fields=["submitted_at", "updated_at"])
            if obj.decision:
                obj.decided_by = approver
                obj.decided_at = timezone.now() - timedelta(days=1)
                obj.save(update_fields=["decided_by", "decided_at", "updated_at"])
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
        ct = ContentType.objects.get_for_model(Project)
        del ct  # stakeholders are a real FK, not a GFK - kept for symmetry with _activities
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
