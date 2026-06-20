"""Seed CRM (Module 1) demo data — leads, opportunities, campaigns, cases, KB articles, and
tasks, per tenant. Idempotent: skips a tenant that already has CRM leads. Reuses the core
spine Parties seeded by ``seed_core`` (no duplicate customers/contacts). Run after
``seed_core`` / ``seed_accounts`` / ``seed_tenants``.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Party, Tenant
from apps.crm.models import Campaign, Case, CrmTask, KnowledgeArticle, Lead, Opportunity

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
            if Lead.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"{tenant.name}: CRM data already exists — skipping")
                continue
            self._seed_tenant(tenant)
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
