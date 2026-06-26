"""Seed CRM (Module 1) demo data — leads, opportunities, campaigns, cases, KB articles, and
tasks, per tenant. Idempotent: skips a tenant that already has CRM leads. Reuses the core
spine Parties seeded by ``seed_core`` (no duplicate customers/contacts). Run after
``seed_core`` / ``seed_accounts`` / ``seed_tenants``.
"""
import datetime
import secrets
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Party, Tenant
from apps.crm.models import (
    AccountProfile,
    ApprovalRequest,
    Campaign,
    CampaignMember,
    Case,
    ContactProfile,
    ContractDocument,
    CrmMilestone,
    CrmProject,
    CrmTask,
    DocTemplate,
    EmailCampaign,
    EmailTemplate,
    Expense,
    FormSubmission,
    HealthScoreConfig,
    KnowledgeArticle,
    LandingPage,
    Lead,
    OnboardingPlan,
    OnboardingStep,
    Opportunity,
    PartnerPortalAccess,
    ProductStock,
    PurchaseOrder,
    PurchaseOrderLine,
    SignerRecord,
    Survey,
    Timesheet,
    WorkflowLog,
    WorkflowRule,
    compute_health_score,
)

User = get_user_model()

LEADS = [
    ("Marcus Chen", "Brightwave Media", "marcus@brightwave.example", "hot", "new", 72, "web", Decimal("15000")),
    ("Priya Nair", "Northwind Traders", "priya@northwind.example", "warm", "contacted", 48, "referral", Decimal("8000")),
    ("Diego Alvarez", "Quantum Robotics", "diego@quantum.example", "cold", "qualified", 31, "event", Decimal("22000")),
]
OPPS = [
    ("Enterprise License Renewal", "proposal", Decimal("48000"), 60, "Send revised proposal"),
    ("Annual Support Contract", "negotiation", Decimal("12000"), 80, "Agree final terms"),
    ("Pilot Program", "prospecting", Decimal("9000"), 20, "Schedule discovery call"),
    ("Hardware Bundle", "closed_won", Decimal("30000"), 100, ""),
]
CASES = [
    ("Login page returns a 500 error", "problem", "high", "open"),
    ("How do I export reports to CSV?", "question", "low", "new"),
    ("Billing discrepancy on last invoice", "incident", "critical", "in_progress"),
]
ARTICLES = [
    ("Getting Started with NavERP", "Onboarding", "external", "published",
     "A step-by-step guide to setting up your workspace and inviting your team."),
    ("Internal Escalation Matrix", "Support", "internal", "draft",
     "Who to contact for tier-2 and tier-3 issues, with response-time targets."),
]
TASKS = [
    ("Call Brightwave Media about a demo", "call", "high", "open"),
    ("Email the proposal to the account", "email", "medium", "in_progress"),
    ("Prepare the quarterly review deck", "todo", "low", "open"),
]


class Command(BaseCommand):
    help = "Seed CRM demo data (leads, opportunities, campaigns, cases, KB, tasks) — idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run `seed_core` first."))
            return
        for tenant in tenants:
            # Backfill Account/Contact profiles for every tenant (idempotent) so existing demo
            # parties gain firmographics/contact details without a --flush.
            self._backfill_profiles(tenant)
            if Lead.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"{tenant.name}: CRM base data already exists — skipping base seed")
            else:
                self._seed_tenant(tenant)
            # 1.7–1.12 extension data — runs after base data exists; self-guards on Expense.
            self._seed_extension(tenant)
            # 1.3 Marketing Automation — runs unconditionally; self-guards on EmailTemplate so
            # existing seeded DBs gain the new marketing rows without a --flush.
            self._seed_marketing(tenant)
        self.stdout.write(self.style.SUCCESS("CRM seed complete."))
        self.stdout.write("Log in as a tenant admin (e.g. admin_acme / password) to view CRM data.")
        self.stdout.write(self.style.WARNING(
            "Superuser 'admin' has no tenant — CRM pages show no data when logged in as admin."))

    def _seed_tenant(self, tenant):
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        account = Party.objects.filter(tenant=tenant, kind="organization").first()
        contact = Party.objects.filter(tenant=tenant, kind="person").first()

        camp = Campaign.objects.create(
            tenant=tenant, name="Spring Product Launch", type="email", status="active",
            start_date=timezone.localdate() - datetime.timedelta(days=20),
            end_date=timezone.localdate() + datetime.timedelta(days=10),
            budget_planned=Decimal("5000"), budget_actual=Decimal("3200"),
            expected_revenue=Decimal("40000"), actual_revenue=Decimal("18000"),
            target_size=2000, owner=owner,
        )
        Campaign.objects.create(
            tenant=tenant, name="Annual User Conference", type="event", status="planned",
            start_date=timezone.localdate() + datetime.timedelta(days=45),
            budget_planned=Decimal("25000"), expected_revenue=Decimal("120000"),
            target_size=500, owner=owner,
        )

        for name, company, email, rating, status, score, source, value in LEADS:
            Lead.objects.create(
                tenant=tenant, name=name, company=company, email=email, rating=rating,
                status=status, score=score, source=source, est_value=value, owner=owner,
            )

        for i, (oname, stage, amount, prob, nxt) in enumerate(OPPS):
            Opportunity.objects.create(
                tenant=tenant, name=oname, account=account, primary_contact=contact,
                stage=stage, amount=amount, probability=prob,
                close_date=timezone.localdate() + datetime.timedelta(days=15 + i * 10),
                owner=owner, campaign=camp if i == 0 else None, next_step=nxt,
            )

        for subj, ctype, pri, status in CASES:
            Case.objects.create(
                tenant=tenant, subject=subj, account=account, contact=contact, type=ctype,
                priority=pri, status=status, origin="email", owner=owner,
                due_at=timezone.now() + datetime.timedelta(days=2),
            )

        for title, category, visibility, status, body in ARTICLES:
            KnowledgeArticle.objects.create(
                tenant=tenant, title=title, category=category, visibility=visibility,
                status=status, body=body, owner=owner,
            )

        for subj, ttype, pri, status in TASKS:
            CrmTask.objects.create(
                tenant=tenant, subject=subj, type=ttype, priority=pri, status=status,
                due_date=timezone.localdate() + datetime.timedelta(days=3), owner=owner,
                party=contact,
            )

        self.stdout.write(self.style.SUCCESS(
            f"{tenant.name}: seeded CRM leads/opportunities/campaigns/cases/KB/tasks"))

    def _backfill_profiles(self, tenant):
        """Idempotently add a demo AccountProfile + ContactProfile to the tenant's first
        organization / person Party so the rich Account/Contact fields show example data."""
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        org = Party.objects.filter(tenant=tenant, kind="organization").first()
        if org and not AccountProfile.objects.filter(party=org).exists():
            AccountProfile.objects.create(
                tenant=tenant, party=org, industry="technology", website="https://example.com",
                phone="+1 555 0100", email=f"info@{org.name.split()[0].lower()}.example",
                annual_revenue=Decimal("5000000"), employee_count=250,
                address_line="100 Market St", address_city="Springfield", address_state="CA",
                address_postal="94000", address_country="USA", source="referral", owner=owner,
                description="Key strategic account.",
            )
        person = Party.objects.filter(tenant=tenant, kind="person").first()
        if person and not ContactProfile.objects.filter(party=person).exists():
            ContactProfile.objects.create(
                tenant=tenant, party=person, job_title="Operations Lead", department="Operations",
                email=f"{person.name.split()[0].lower()}@example.com", phone="+1 555 0111",
                mobile="+1 555 0112", account=org, address_line="100 Market St",
                address_city="Springfield", address_state="CA", address_postal="94000",
                address_country="USA", source="event", owner=owner,
                description="Primary point of contact.",
            )

    def _seed_marketing(self, tenant):
        """Idempotently seed 1.3 Marketing Automation demo data — campaign members, an email
        template + sent blast (with metrics), a published landing page, and two form
        submissions. Reuses the tenant's first Campaign + existing Party/Lead rows. Guard: skip
        if an EmailTemplate already exists for the tenant (so it backfills without a --flush)."""
        if EmailTemplate.objects.filter(tenant=tenant).exists():
            return
        campaign = Campaign.objects.filter(tenant=tenant).order_by("created_at").first()
        if campaign is None:
            return  # base seed didn't run (no tenant admin / parties) — nothing to attach to
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        org = Party.objects.filter(tenant=tenant, kind="organization").first()
        person = Party.objects.filter(tenant=tenant, kind="person").first()
        leads = list(Lead.objects.filter(tenant=tenant)[:2])

        # Target-list members (varied funnel statuses).
        members = [
            CampaignMember(tenant=tenant, campaign=campaign, party=org,
                           member_name=org.name if org else "Brightwave Media",
                           member_email="info@brightwave.example", status="clicked"),
            CampaignMember(tenant=tenant, campaign=campaign, party=person,
                           member_name=person.name if person else "Jordan Lee",
                           member_email="jordan@example.com", status="responded"),
        ]
        for i, lead in enumerate(leads):
            members.append(CampaignMember(
                tenant=tenant, campaign=campaign, lead=lead, member_name=lead.name,
                member_email=lead.email, status="opened" if i == 0 else "sent"))
        # Pre-stamp responded_at (save() would, but bulk_create skips save()), then one INSERT.
        now = timezone.now()
        for m in members:
            if m.status in CampaignMember.RESPONDED_STATUSES:
                m.responded_at = now
        CampaignMember.objects.bulk_create(members)

        template = EmailTemplate.objects.create(
            tenant=tenant, name="Spring Launch Announcement", category="promotional",
            subject="Introducing our Spring lineup, {{first_name}}",
            preheader="A fresh set of features built for your team.",
            body="<h1>Hello {{first_name}}</h1><p>We're excited to share what's new this season.</p>",
            from_name="NavERP Marketing", from_email="marketing@naverp.example",
            is_active=True, owner=owner,
        )

        member_count = CampaignMember.objects.filter(tenant=tenant, campaign=campaign).count()
        EmailCampaign.objects.create(
            tenant=tenant, name="Spring Launch — Blast A", campaign=campaign, template=template,
            is_ab_test=False, send_type="one_time", status="sent",
            sent_at=timezone.now() - datetime.timedelta(days=5),
            recipients_count=member_count, sent_count=member_count,
            opened_count=max(0, member_count - 1), clicked_count=max(0, member_count - 2),
            bounced_count=0, unsubscribed_count=0, owner=owner,
        )

        page = LandingPage.objects.create(
            tenant=tenant, name="Spring Launch — Free Trial", campaign=campaign,
            slug="spring-free-trial", headline="Start your free 14-day trial",
            subheadline="No credit card required.",
            body="Join thousands of teams streamlining their operations with NavERP.",
            capture_phone=True, capture_company=True, capture_message=False,
            cta_label="Get started", status="published", routing_owner=owner,
            lead_source="web", owner=owner,
        )

        FormSubmission.objects.create(
            tenant=tenant, landing_page=page, name="Sasha Patel", email="sasha@acmestartup.example",
            phone="+1 555 0150", company="Acme Startup", status="new", routed_to=owner,
        )
        converted = FormSubmission.objects.create(
            tenant=tenant, landing_page=page, name="Toni Garcia", email="toni@brightlabs.example",
            phone="+1 555 0151", company="Bright Labs", status="converted", routed_to=owner,
        )
        converted.converted_lead = Lead.objects.create(
            tenant=tenant, name="Toni Garcia", company="Bright Labs", email="toni@brightlabs.example",
            phone="+1 555 0151", source="web", status="new", owner=owner,
            description="Captured via the Spring Launch landing page.",
        )
        converted.save(update_fields=["converted_lead"])
        LandingPage.objects.filter(pk=page.pk).update(submission_count=2)

    def _seed_extension(self, tenant):
        """Idempotently seed the 1.7–1.12 demo data (expenses, projects/milestones/timesheets,
        doc templates/contracts/signers, workflows/approvals, onboarding/health/surveys,
        product stock/purchase orders/partner portal). Guard: skip if Expenses already exist."""
        if Expense.objects.filter(tenant=tenant).exists():
            return
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        account = Party.objects.filter(tenant=tenant, kind="organization").first()
        won_opp = Opportunity.objects.filter(tenant=tenant, stage="closed_won").first()
        any_opp = Opportunity.objects.filter(tenant=tenant).first()
        a_case = Case.objects.filter(tenant=tenant).first()
        acct_label = account.name if account else "Client"
        today = timezone.localdate()
        now = timezone.now()
        td = datetime.timedelta

        # --- 1.8 Projects + milestones + timesheets
        project = CrmProject.objects.create(
            tenant=tenant, name=f"{acct_label} — Delivery", account=account,
            source_opportunity=won_opp, status="active", start_date=today - td(days=10),
            end_date=today + td(days=50), budget=(won_opp.amount if won_opp else Decimal("30000")),
            owner=owner, description="Delivery project for the won deal.")
        CrmProject.objects.create(
            tenant=tenant, name="Discovery Engagement", account=account, status="planning",
            budget=Decimal("12000"), owner=owner, description="Pre-sale scoping engagement.")
        for i, (title, kind, status, off) in enumerate([
            ("Kickoff", "milestone", "completed", -5),
            ("Build Phase", "task", "in_progress", 10),
            ("Go-Live", "milestone", "not_started", 40),
        ]):
            CrmMilestone.objects.create(
                tenant=tenant, project=project, title=title, kind=kind, status=status,
                assignee=owner, order=i, start_date=today, due_date=today + td(days=off))
        for hrs, billable, status, off in [
            (Decimal("7.50"), True, "approved", -3),
            (Decimal("4.00"), True, "submitted", -1),
            (Decimal("2.00"), False, "draft", 0),
        ]:
            Timesheet.objects.create(
                tenant=tenant, project=project, employee=owner, client=account,
                date=today + td(days=off), hours=hrs, is_billable=billable, status=status,
                approved_by=(owner if status == "approved" else None),
                description="Work logged against the project.")

        # --- 1.7 Expenses (linked to the won deal / project)
        for cat, amt, status, off in [
            ("travel", Decimal("450.00"), "approved", -7),
            ("meals", Decimal("85.50"), "submitted", -3),
            ("software", Decimal("120.00"), "draft", -1),
        ]:
            Expense.objects.create(
                tenant=tenant, opportunity=won_opp, project=project, category=cat, amount=amt,
                currency_code="USD", expense_date=today + td(days=off), status=status,
                submitted_by=owner, approved_by=(owner if status == "approved" else None),
                description=f"Deal-related {cat} cost.")

        # --- 1.9 Doc templates + contracts + signers
        tpl = DocTemplate.objects.create(
            tenant=tenant, name="Standard Service Contract", template_type="contract",
            is_active=True, owner=owner,
            body=("<h1>Service Agreement</h1><p>This agreement is between {{ account.name }} "
                  "and our company, dated {{ today }}. Total contract value "
                  "{{ opportunity.amount }}.</p>"))
        DocTemplate.objects.create(
            tenant=tenant, name="Sales Proposal", template_type="proposal", is_active=True,
            owner=owner, body="<h1>Proposal for {{ account.name }}</h1><p>Prepared {{ today }}.</p>")
        signed = ContractDocument.objects.create(
            tenant=tenant, name=f"MSA — {acct_label}", template=tpl, opportunity=won_opp,
            account=account, status="signed", current_version=1, signed_at=now, owner=owner,
            body_snapshot="<h1>Service Agreement</h1><p>Signed copy.</p>")
        draft = ContractDocument.objects.create(
            tenant=tenant, name="Mutual NDA (Draft)", template=tpl, account=account,
            status="draft", owner=owner)
        SignerRecord.objects.create(
            tenant=tenant, contract=signed, signer_name="Jordan Lee",
            signer_email="jordan@example.com", token=secrets.token_urlsafe(32), order=1,
            viewed_at=now, signed_at=now)
        SignerRecord.objects.create(
            tenant=tenant, contract=draft, signer_name="Pat Morgan",
            signer_email="pat@example.com", token=secrets.token_urlsafe(32), order=1)

        # --- 1.10 Workflow rules + log + approvals
        rule = WorkflowRule.objects.create(
            tenant=tenant, name="Auto-task on won deal", is_active=True,
            trigger_entity="opportunity", trigger_event="status_changed", trigger_field="stage",
            trigger_value="closed_won",
            conditions=[{"field": "amount", "operator": ">", "value": 10000}],
            actions=[{"type": "create_task", "params": {"subject": "Kick off delivery"}}],
            owner=owner)
        WorkflowRule.objects.create(
            tenant=tenant, name="Email on new case", is_active=False, trigger_entity="case",
            trigger_event="created",
            actions=[{"type": "send_email", "params": {"template": "new_case"}}], owner=owner)
        WorkflowLog.objects.create(
            tenant=tenant, rule=rule, record_label=(won_opp.number if won_opp else "OPP-00001"),
            status="success")
        ApprovalRequest.objects.create(
            tenant=tenant, rule=rule, subject="Approve 25% discount on deal",
            record_label=(any_opp.number if any_opp else ""), approver=owner, requested_by=owner,
            threshold_field="discount_pct", threshold_value=Decimal("25"), status="pending")
        ApprovalRequest.objects.create(
            tenant=tenant, subject="Approve vendor contract", approver=owner, requested_by=owner,
            status="approved", approved_at=now, reason="Within budget.")

        # --- 1.11 Onboarding + health + surveys
        plan = OnboardingPlan.objects.create(
            tenant=tenant, account=account, name=f"{acct_label} — 90-Day Onboarding",
            status="active", target_date=today + td(days=90), owner=owner,
            description="Standard new-client onboarding checklist.")
        for i, (title, off, done) in enumerate([
            ("Welcome & kickoff call", -5, True),
            ("Product training session", 5, False),
            ("30-day go-live review", 30, False),
        ]):
            OnboardingStep.objects.create(
                tenant=tenant, plan=plan, order=i, title=title, assignee=owner,
                due_date=today + td(days=off), completed_at=(now if done else None))

        HealthScoreConfig.objects.get_or_create(tenant=tenant)
        Survey.objects.create(
            tenant=tenant, account=account, survey_type="nps", trigger="post_close", score=9,
            feedback_text="Great onboarding experience!", sent_at=now - td(days=5),
            responded_at=now - td(days=4))
        Survey.objects.create(
            tenant=tenant, account=account, survey_type="csat", trigger="post_ticket",
            related_case=a_case, score=4, feedback_text="Quick resolution.",
            sent_at=now - td(days=2), responded_at=now - td(days=2))
        Survey.objects.create(
            tenant=tenant, account=account, survey_type="nps", trigger="manual", score=4,
            feedback_text="A few rough edges to fix.", sent_at=now - td(days=1))
        # Compute a health score per org Party (after surveys/cases/tasks exist).
        for party in Party.objects.filter(tenant=tenant, kind="organization")[:3]:
            compute_health_score(party, tenant)

        # --- 1.12 Product stock + purchase order + partner portal
        widget = ProductStock.objects.create(
            tenant=tenant, name="Standard Widget", sku="WID-100", on_hand_qty=Decimal("120"),
            reorder_level=Decimal("50"), unit_cost=Decimal("12.50"))
        gizmo = ProductStock.objects.create(
            tenant=tenant, name="Premium Gizmo", sku="GIZ-200", on_hand_qty=Decimal("8"),
            reorder_level=Decimal("25"), unit_cost=Decimal("40.00"))  # below reorder = low stock
        po = PurchaseOrder.objects.create(
            tenant=tenant, vendor=account, status="sent", order_date=today - td(days=2),
            expected_date=today + td(days=7), owner=owner, notes="Restock order.")
        PurchaseOrderLine.objects.create(
            tenant=tenant, purchase_order=po, product=gizmo, item_name="Premium Gizmo",
            quantity=Decimal("50"), unit_price=Decimal("40.00"), order=0)
        PurchaseOrderLine.objects.create(
            tenant=tenant, purchase_order=po, product=widget, item_name="Standard Widget",
            quantity=Decimal("100"), unit_price=Decimal("12.50"), order=1)
        po.recalc_total()
        PartnerPortalAccess.objects.create(
            tenant=tenant, partner_party=account, access_level="read_only", can_view_stock=True,
            can_register_leads=False, is_active=True)

        self.stdout.write(self.style.SUCCESS(f"{tenant.name}: seeded CRM 1.7–1.12 extension data"))
