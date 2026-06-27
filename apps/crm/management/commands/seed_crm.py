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

from apps.accounting.models import Currency, Invoice, InvoiceLine  # 1.7 reuses the ledger (L29)
from apps.core.models import Party, Tenant
from apps.crm.analytics import compute_report
from apps.crm.models import (
    AccountProfile,
    AnalyticsDashboard,
    AnalyticsReport,
    ApprovalRequest,
    CalendarEvent,
    Campaign,
    CampaignMember,
    Case,
    CaseComment,
    CommunicationLog,
    ContactProfile,
    ContractDocument,
    DocumentVersion,
    CrmMilestone,
    CrmProject,
    CrmTask,
    CustomerPortalAccess,
    DashboardWidget,
    DealInvoice,
    DocTemplate,
    EmailCampaign,
    EmailTemplate,
    EventAttendee,
    Expense,
    FormSubmission,
    HealthScoreConfig,
    KbCategory,
    KnowledgeArticle,
    LandingPage,
    Lead,
    OnboardingPlan,
    OnboardingStep,
    Opportunity,
    OpportunitySplit,
    PartnerPortalAccess,
    PaymentReceipt,
    PriceBook,
    Product,
    ProductStock,
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    ResourceAllocation,
    QuoteLine,
    ReportSnapshot,
    SalesQuota,
    SignerRecord,
    SlaPolicy,
    Survey,
    Territory,
    Timesheet,
    Webhook,
    WebhookDelivery,
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
            # 1.2 Sales Force Automation — runs unconditionally; self-guards on Product.
            self._seed_sfa(tenant)
            # 1.4 Customer Service & Support — runs unconditionally; self-guards on SlaPolicy.
            self._seed_service(tenant)
            # 1.5 Activity & Communication Management — runs unconditionally; self-guards on CalendarEvent.
            self._seed_activities(tenant)
            # 1.6 Analytics & Reporting — runs unconditionally; self-guards on AnalyticsDashboard.
            self._seed_analytics(tenant)
            # 1.7 Finance & Billing (recreated) — runs after SFA (needs a quote); self-guards on DealInvoice.
            self._seed_finance17(tenant)
            # 1.8 Resource Allocation (recreated) — capacity bookings for the workload board; guards on ResourceAllocation.
            self._seed_resource18(tenant)
            # 1.9 File Repository (recreated) — render a contract + capture versions; guards on DocumentVersion.
            self._seed_documents19(tenant)
            # 1.10 Webhooks (recreated) — an endpoint + signed deliveries; guards on Webhook.
            self._seed_webhooks110(tenant)
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

    def _seed_sfa(self, tenant):
        """Idempotently seed 1.2 SFA demo data — territories, a sales-product catalog + price
        books, opportunity splits, a quote (+ lines, recalculated), and sales quotas. Reuses the
        tenant's first Opportunity/Party. Guard: skip if a Product already exists for the tenant."""
        if Product.objects.filter(tenant=tenant).exists():
            return
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        if owner is None:
            return
        org = Party.objects.filter(tenant=tenant, kind="organization").first()
        opp = Opportunity.objects.filter(tenant=tenant).order_by("created_at").first()

        emea = Territory.objects.create(tenant=tenant, name="EMEA", region="Europe",
                                        segment="Enterprise", manager=owner)
        amer = Territory.objects.create(tenant=tenant, name="Americas", region="North America",
                                        segment="Mid-Market", manager=owner)

        products = [
            Product(tenant=tenant, name="Pro Plan License", sku="LIC-PRO", product_type="subscription",
                    unit_price=Decimal("1200"), cost=Decimal("300"), tax_pct=Decimal("10")),
            Product(tenant=tenant, name="Onboarding Service", sku="SVC-ONB", product_type="service",
                    unit_price=Decimal("2500"), cost=Decimal("900"), tax_pct=Decimal("0")),
            Product(tenant=tenant, name="Hardware Kit", sku="HW-KIT", product_type="good",
                    unit_price=Decimal("800"), cost=Decimal("500"), tax_pct=Decimal("10")),
        ]
        for p in products:
            p.save()  # TenantNumbered.save assigns the PRD- number

        book = PriceBook.objects.create(
            tenant=tenant, name="Standard (USD)", currency_code="USD", region="Global",
            tier="Standard", price_adjustment_pct=Decimal("0"), is_default=True)
        PriceBook.objects.create(
            tenant=tenant, name="EMEA Enterprise", currency_code="EUR", region="Europe",
            tier="Enterprise", price_adjustment_pct=Decimal("-10"))

        if opp is not None:
            opp.territory = amer
            opp.competitor = "Acme Rival Inc."
            opp.forecast_category = "best_case"
            opp.save()
            OpportunitySplit.objects.create(tenant=tenant, opportunity=opp, user=owner,
                                            split_type="revenue", percentage=Decimal("70"))
            OpportunitySplit.objects.create(tenant=tenant, opportunity=opp, user=owner,
                                            split_type="overlay", percentage=Decimal("25"), notes="SE credit")
            quote = Quote.objects.create(
                tenant=tenant, name="Initial Proposal", opportunity=opp, account=org, price_book=book,
                currency_code="USD", discount_pct=Decimal("5"),
                valid_until=timezone.localdate() + datetime.timedelta(days=30), owner=owner,
                terms="Net 30. Prices valid for 30 days.")
            for i, p in enumerate(products[:2]):
                QuoteLine.objects.create(
                    tenant=tenant, quote=quote, product=p, description=p.name,
                    quantity=Decimal("2") if i == 0 else Decimal("1"),
                    unit_price=p.unit_price, tax_pct=p.tax_pct, order=i)
            quote.recalc_totals()

        # Distinct periods — the unique key is (tenant, owner, period_type, year, number).
        SalesQuota.objects.create(tenant=tenant, owner=owner, territory=amer, period_type="quarter",
                                  period_year=2026, period_number=2, target_amount=Decimal("150000"))
        SalesQuota.objects.create(tenant=tenant, owner=owner, territory=emea, period_type="quarter",
                                  period_year=2026, period_number=3, target_amount=Decimal("90000"))

    def _seed_finance17(self, tenant):
        """Idempotently seed 1.7 Finance & Billing (recreated in detail): take an accepted quote,
        generate a DRAFT ``accounting.Invoice`` from its lines (carrying per-line + quote-level
        discount and tax), wrap it in a ``DealInvoice``, and record a partial ``PaymentReceipt``.
        Reuses the accounting ledger (L29) — no second invoice table. Guard: skip if a DealInvoice
        already exists. Runs AFTER ``_seed_sfa`` (it needs that quote)."""
        if DealInvoice.objects.filter(tenant=tenant).exists():
            return
        quote = (Quote.objects.filter(tenant=tenant, account__isnull=False, lines__isnull=False)
                 .select_related("account", "opportunity").distinct().first())
        if quote is None:
            return  # no quote with lines to invoice yet
        # Tell a consistent story: mark the quote accepted, then convert it.
        if quote.status != "accepted":
            quote.status = "accepted"
            quote.accepted_at = timezone.now()
            quote.save(update_fields=["status", "accepted_at", "updated_at"])

        code = (quote.currency_code or "USD").upper()[:3]  # clamp to the Currency.code max_length
        quote_disc = (Decimal(100) - Decimal(quote.discount_pct or 0)) / Decimal(100)
        # Self-contained atomic block (mirrors the dealinvoice_from_quote view) so a partial
        # failure can't leave an orphaned ledger invoice — handle() is also @transaction.atomic.
        with transaction.atomic():
            currency, _ = Currency.objects.get_or_create(
                code=code, defaults={"name": code, "symbol": "$" if code == "USD" else ""})
            inv = Invoice.objects.create(
                tenant=tenant, party=quote.account, issue_date=timezone.localdate(),
                status="draft", currency=currency, notes=f"Generated from quote {quote.number}")
            for ln in quote.lines.all():
                line_disc = (Decimal(100) - Decimal(ln.discount_pct or 0)) / Decimal(100)
                net_unit = (Decimal(ln.unit_price or 0) * line_disc * quote_disc).quantize(Decimal("0.01"))
                InvoiceLine.objects.create(
                    invoice=inv, description=(ln.description or "Item")[:255],
                    quantity=(ln.quantity or Decimal(1)), unit_price=net_unit,
                    tax_rate_pct=(ln.tax_pct or Decimal(0)))
            inv.recalc_totals()
            deal = DealInvoice.objects.create(
                tenant=tenant, opportunity=quote.opportunity, quote=quote, account=quote.account,
                invoice=inv, notes="Converted from the accepted quote (demo).")
            # A partial (milestone) receipt via a payment gateway, against the deal invoice.
            PaymentReceipt.objects.create(
                tenant=tenant, deal_invoice=deal,
                amount=((inv.total or Decimal("0")) / 2).quantize(Decimal("0.01")),
                received_date=timezone.localdate(), method="card", gateway="stripe",
                gateway_txn_id="ch_demo_0001", notes="Partial (50%) milestone payment via Stripe.")

    def _seed_resource18(self, tenant):
        """Idempotently seed 1.8 Resource Allocations (capacity bookings) so the workload board has
        planned load — the first person is intentionally overbooked (50 h/wk > 40 capacity). Guard:
        skip if allocations already exist. Reuses the seeded project + tenant users."""
        if ResourceAllocation.objects.filter(tenant=tenant).exists():
            return
        project = CrmProject.objects.filter(tenant=tenant).order_by("created_at").first()
        users = list(User.objects.filter(tenant=tenant).order_by("pk")[:3])
        if project is None or not users:
            return
        today = timezone.localdate()
        start = today - datetime.timedelta(days=today.weekday())  # this week's Monday
        end = start + datetime.timedelta(days=55)                 # ~8 weeks
        for i, (role, hpw) in enumerate([("Project Manager", Decimal("50")),   # overbooked
                                         ("Developer", Decimal("25")),
                                         ("QA Engineer", Decimal("15"))]):
            ResourceAllocation.objects.create(
                tenant=tenant, project=project, assignee=users[i % len(users)], role=role,
                hours_per_week=hpw, start_date=start, end_date=end, status="active",
                notes=f"{role} booked on {project.name}.")

    def _seed_documents19(self, tenant):
        """Idempotently seed 1.9 File Repository data — render a draft contract from its template and
        capture two versions so the repository + version history show data. Guard: skip if any
        DocumentVersion exists. Runs after _seed_extension (needs a contract with a linked template)."""
        if DocumentVersion.objects.filter(tenant=tenant).exists():
            return
        tpl = (DocTemplate.objects.filter(tenant=tenant, template_type="contract").first()
               or DocTemplate.objects.filter(tenant=tenant).first())
        account = Party.objects.filter(tenant=tenant, kind="organization").first()
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        if tpl is None or account is None:
            return
        # A dedicated draft contract so the repository + generation demo always have a draft to act on.
        contract = ContractDocument.objects.create(
            tenant=tenant, name="Service Agreement (Repository Demo)", template=tpl,
            account=account, status="draft", owner=owner)
        from apps.crm.views import _render_doc_body  # shared safe render — DRY with the generate action
        try:
            rendered = _render_doc_body(contract)
        except Exception:  # a malformed template must not abort the whole seed  # noqa: BLE001
            rendered = ""
        contract.body_snapshot = rendered
        contract.current_version = 2
        contract.save(update_fields=["body_snapshot", "current_version", "updated_at"])
        DocumentVersion.objects.create(
            tenant=tenant, contract=contract, version_no=1, body_snapshot=rendered,
            change_note=f"Generated from {contract.template.number}", created_by=owner)
        DocumentVersion.objects.create(
            tenant=tenant, contract=contract, version_no=2, body_snapshot=rendered,
            change_note="Revised pricing terms.", created_by=owner)

    def _seed_webhooks110(self, tenant):
        """Idempotently seed 1.10 Webhooks — one Slack-style endpoint + two signed deliveries (a prior
        success + a pending) so the webhook detail + deliveries log show data. Guard: skip if a Webhook
        already exists."""
        if Webhook.objects.filter(tenant=tenant).exists():
            return
        import hashlib  # local — only the webhook demo needs these
        import hmac
        import json
        wh = Webhook.objects.create(
            tenant=tenant, name="Slack — New Opportunity",
            target_url="https://hooks.slack.example/T000/B000/demo",
            trigger_entity="opportunity", trigger_event="created", secret=secrets.token_hex(16),
            is_active=True, description="Posts to #sales when an opportunity is created.")
        for event, status, code in [("opportunity.created", "success", 200), ("manual.test", "pending", None)]:
            payload = json.dumps({"event": event, "demo": True, "at": timezone.now().isoformat()})
            sig = hmac.new(wh.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            WebhookDelivery.objects.create(
                tenant=tenant, webhook=wh, event=event, payload=payload, signature=sig,
                status=status, response_code=code)

    def _seed_service(self, tenant):
        """Idempotently seed 1.4 help-desk demo data — a default SLA policy, 2 KB categories, a
        case conversation thread (internal + public) on the first case, category links + public
        tokens on existing cases/articles, and a customer portal-access row. Guard: skip if an
        SlaPolicy already exists for the tenant."""
        if SlaPolicy.objects.filter(tenant=tenant).exists():
            return
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        agent_name = (owner.get_full_name() or owner.username) if owner else "Support"

        policy = SlaPolicy.objects.create(
            tenant=tenant, name="Standard Support", description="Default first-response + resolution targets.",
            is_active=True, is_default=True)
        getting_started = KbCategory.objects.create(tenant=tenant, name="Getting Started", order=1)
        KbCategory.objects.create(tenant=tenant, name="Troubleshooting", order=2)

        # Attach the policy + a conversation thread to the first case (save() computes SLA dues + token).
        case = Case.objects.filter(tenant=tenant).order_by("created_at").first()
        if case is not None:
            case.sla_policy = policy
            case.save()
            CaseComment.objects.create(
                tenant=tenant, case=case, author=owner, author_name=agent_name,
                body="Thanks for the report — we're looking into this now.", is_public=True)
            CaseComment.objects.create(
                tenant=tenant, case=case, author=owner, author_name=agent_name,
                body="Internal: reproduced on staging, escalating to engineering.", is_public=False)
            if case.first_responded_at is None:
                case.first_responded_at = timezone.now()
                case.save(update_fields=["first_responded_at", "updated_at"])

        # Categorize existing articles (save() also backfills their public_token).
        for art in KnowledgeArticle.objects.filter(tenant=tenant, kb_category__isnull=True):
            art.kb_category = getting_started
            art.save()

        # Backfill a public status-tracking token on any remaining tokenless cases.
        for c in Case.objects.filter(tenant=tenant, public_token__isnull=True):
            c.public_token = secrets.token_urlsafe(32)
            c.save(update_fields=["public_token"])

        # Customer portal access (portal_user unassigned by default — assign a user to demo the login).
        party = Party.objects.filter(tenant=tenant, kind="organization").first()
        CustomerPortalAccess.objects.create(
            tenant=tenant, customer_party=party, can_submit_cases=True, is_active=True)

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

        # --- 1.7 Expenses (linked to the won deal / project). is_billable=True is re-billed to the
        #     client, so it's excluded from the deal's true margin (see DealInvoice detail).
        for cat, amt, status, off, billable in [
            ("travel", Decimal("450.00"), "approved", -7, True),
            ("meals", Decimal("85.50"), "submitted", -3, False),
            ("software", Decimal("120.00"), "draft", -1, False),
        ]:
            Expense.objects.create(
                tenant=tenant, opportunity=won_opp, project=project, category=cat, amount=amt,
                currency_code="USD", expense_date=today + td(days=off), status=status,
                is_billable=billable,
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

    def _seed_activities(self, tenant):
        """Idempotently seed 1.5 Activity & Communication data — a recurring task + its next
        spawned occurrence, calendar events with attendees (incl. RSVPs), and a unified
        call/email/note/SMS communication history. Reuses the tenant's owner / Party /
        Opportunity. Guard: skip if a CalendarEvent already exists for the tenant."""
        if CalendarEvent.objects.filter(tenant=tenant).exists():
            return
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        if owner is None:
            return
        org = Party.objects.filter(tenant=tenant, kind="organization").first()
        person = Party.objects.filter(tenant=tenant, kind="person").first()
        opp = Opportunity.objects.filter(tenant=tenant).order_by("created_at").first()
        now = timezone.now()
        today = timezone.localdate()
        td = datetime.timedelta
        org_name = org.name if org else "Acme Corp"

        # --- Recurring task (weekly) + a manually-created "next occurrence" (demo of the series).
        # Both start status="open", so CrmTask.save() does NOT trigger the spawn-on-done path.
        parent_task = CrmTask.objects.create(
            tenant=tenant, subject="Weekly check-in call", type="call", priority="medium",
            status="open", due_date=today + td(days=7), owner=owner, party=person,
            related_opportunity=opp, recurrence="weekly", recurrence_interval=1,
            recurrence_until=today + td(days=90),
            description="Recurring weekly touch-base with the account.")
        CrmTask.objects.create(
            tenant=tenant, subject="Weekly check-in call", type="call", priority="medium",
            status="open", due_date=today + td(days=14), owner=owner, party=person,
            related_opportunity=opp, recurrence="weekly", recurrence_interval=1,
            recurrence_until=today + td(days=90), recurrence_parent=parent_task,
            description="Recurring weekly touch-base with the account.")

        # --- Calendar events (varied types/statuses) + attendees with RSVPs.
        events_spec = [
            ("Kickoff Meeting", "meeting", "confirmed", now + td(days=2), 60, org),
            ("Product Demo", "demo", "scheduled", now + td(days=7), 45, org),
            ("Quarterly Business Review", "meeting", "completed", now - td(days=14), 90, org),
            ("Follow-up Call", "call", "scheduled", now + td(days=3), 30, person),
        ]
        first_event = None
        for title, etype, status, start, dur, evt_party in events_spec:
            ev = CalendarEvent.objects.create(
                tenant=tenant, title=f"{title} — {org_name}", event_type=etype, status=status,
                start=start, end=start + td(minutes=dur), location="Online",
                video_url="https://meet.example.com/naverp-demo", sync_source="manual",
                reminder_minutes=15, owner=owner, party=evt_party, related_opportunity=opp,
                description=f"{title} with {org_name}.")
            first_event = first_event or ev
            EventAttendee.objects.create(
                tenant=tenant, event=ev, party=None,
                name=(owner.get_full_name() or owner.username),
                email=(owner.email or "rep@naverp.example"),
                rsvp_status="accepted", is_organizer=True)
            EventAttendee.objects.create(
                tenant=tenant, event=ev, party=org, name=org_name,
                email="contact@example.com",
                rsvp_status="tentative" if status == "scheduled" else "accepted")
        # A third (no-response) attendee on the first event.
        if first_event is not None and person is not None:
            EventAttendee.objects.create(
                tenant=tenant, event=first_event, party=person, name=person.name,
                email="contact2@example.com", rsvp_status="no_response")

        # --- Communication history (calls w/ duration+outcome, BCC-synced emails, a note, an SMS).
        comms = [
            ("call", "outbound", "Cold call — intro", "", 243, "connected", "voip", now - td(days=5)),
            ("call", "outbound", "Follow-up call", "", None, "voicemail", "voip", now - td(days=3)),
            ("email", "outbound", "Proposal sent", "Please find the proposal attached.",
             None, "", "bcc_dropbox", now - td(days=4)),
            ("email", "inbound", "Re: Proposal", "Thanks — this looks good, reviewing internally.",
             None, "", "bcc_dropbox", now - td(days=3)),
            ("note", "", "Meeting notes — kickoff", "Discussed Q3 roadmap and success criteria.",
             None, "", "manual", now - td(days=14)),
            ("sms", "outbound", "Reminder: demo tomorrow", "See you at 2pm!",
             None, "", "manual", now - td(days=6)),
        ]
        for channel, direction, subject, body, dur, outcome, via, occurred in comms:
            CommunicationLog.objects.create(
                tenant=tenant, channel=channel, direction=direction, subject=subject, body=body,
                party=org, owner=owner, related_opportunity=opp, occurred_at=occurred,
                duration_seconds=dur, outcome=outcome, logged_via=via)

        self.stdout.write(self.style.SUCCESS(
            f"{tenant.name}: seeded CRM 1.5 activity & communication data"))

    def _seed_analytics(self, tenant):
        """Idempotently seed 1.6 Analytics & Reporting — two saved dashboards (a sales command
        centre + a service desk) with live-computed widgets, the four standard reports, and a
        baseline snapshot of the top-performers report. Reuses the tenant admin as owner.
        Guard: skip if an AnalyticsDashboard already exists for the tenant."""
        if AnalyticsDashboard.objects.filter(tenant=tenant).exists():
            return
        owner = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                 or User.objects.filter(tenant=tenant).first())
        if owner is None:
            return
        dec = Decimal

        # --- Dashboard 1: Sales Command Center (3-column) -----------------------------------
        sales = AnalyticsDashboard.objects.create(
            tenant=tenant, name="Sales Command Center", owner=owner, is_shared=True,
            is_default=True, layout="three",
            description="Live pipeline, forecast and win-rate at a glance.")
        sales_widgets = [
            ("Open Pipeline", "kpi_open_pipeline", "kpi", "last_90", "small", None),
            ("Weighted Forecast", "kpi_weighted_forecast", "kpi", "last_90", "small", None),
            ("Win Rate", "kpi_win_rate", "gauge", "last_90", "small", dec("50")),
            ("Pipeline by Stage", "pipeline_by_stage", "bar", "all", "large", None),
            ("Won vs Lost", "win_loss", "doughnut", "year", "medium", None),
            ("Revenue Won by Month", "revenue_won_by_month", "line", "year", "medium", None),
            ("Top Performers", "top_performers", "table", "year", "large", None),
        ]
        for i, (title, metric, chart, rng, size, target) in enumerate(sales_widgets):
            DashboardWidget.objects.create(
                tenant=tenant, dashboard=sales, title=title, metric=metric, chart_type=chart,
                date_range=rng, size=size, target_value=target, position=i)

        # --- Dashboard 2: Service Desk (2-column) -------------------------------------------
        service = AnalyticsDashboard.objects.create(
            tenant=tenant, name="Service Desk", owner=owner, is_shared=True, is_default=False,
            layout="two", description="Case load, resolution and customer satisfaction.")
        service_widgets = [
            ("Open Cases", "kpi_open_cases", "kpi", "last_30", "small", None),
            ("Average CSAT", "kpi_avg_csat", "gauge", "last_90", "small", None),
            ("Cases by Status", "cases_by_status", "bar", "last_90", "medium", None),
            ("Cases by Priority", "cases_by_priority", "doughnut", "last_90", "medium", None),
        ]
        for i, (title, metric, chart, rng, size, target) in enumerate(service_widgets):
            DashboardWidget.objects.create(
                tenant=tenant, dashboard=service, title=title, metric=metric, chart_type=chart,
                date_range=rng, size=size, target_value=target, position=i)

        # --- The four standard reports ------------------------------------------------------
        reports = [
            ("Sales Activity (Monthly)", "sales_activity", "last_90", "month", True,
             "Opportunities created, tasks completed and communications logged per month."),
            ("Top Performers (YTD)", "sales_performance", "year", "owner", True,
             "Closed-won deals and revenue by sales rep."),
            ("Pipeline Funnel", "funnel", "all", "stage", False,
             "Stage-by-stage conversion and drop-off across the open pipeline."),
            ("Service Resolution & CSAT", "service", "last_90", "priority", False,
             "Resolution time, first-response time and CSAT by priority."),
        ]
        made = {}
        for name, rtype, rng, grp, fav, desc in reports:
            made[rtype] = AnalyticsReport.objects.create(
                tenant=tenant, name=name, report_type=rtype, date_range=rng, group_by=grp,
                is_favorite=fav, owner=owner, description=desc)

        # --- A baseline snapshot of the top-performers report -------------------------------
        perf = made.get("sales_performance")
        if perf is not None:
            result = compute_report(perf)
            ReportSnapshot.objects.create(
                tenant=tenant, report=perf, title=f"{perf.name} — baseline",
                generated_by=owner, summary=result.get("summary", []),
                data={k: result.get(k) for k in
                      ("columns", "rows", "chart_type", "chart_label", "chart_labels", "chart_data")})

        self.stdout.write(self.style.SUCCESS(
            f"{tenant.name}: seeded CRM 1.6 analytics dashboards, reports & a snapshot"))
