from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Currency
from apps.core.models import ConsentPurpose, Tenant
from apps.crm.models import Campaign, EmailCampaign, EmailTemplate, Lead, Territory
from apps.sales.models import LeadNurtureEnrollment, LeadQualification, LeadRoutingRule, LeadScoreEvent
from apps.sales.services import (
    activate_nurture,
    apply_qualification_decision,
    record_score_event,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Seed Sales 8.1 data idempotently."

    @transaction.atomic
    def handle(self, *args, **options):
        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run seed_core first."))
            return
        for tenant in tenants:
            self._seed_tenant(tenant)
        self.stdout.write(self.style.SUCCESS("Sales 8.1 seed complete."))
        self.stdout.write("Log in as a tenant admin (e.g. admin_acme / password) to view Sales data.")
        self.stdout.write(self.style.WARNING("Superuser 'admin' has tenant=None — Sales pages show no tenant data when logged in as admin."))
        self.stdout.write(self.style.WARNING("CRM email sends remain simulated; no ESP or delivery worker is seeded."))

    def _seed_tenant(self, tenant):
        owner = User.objects.filter(tenant=tenant, is_tenant_admin=True).first() or User.objects.filter(tenant=tenant, is_active=True).first()
        leads = list(Lead.objects.filter(tenant=tenant).order_by("created_at")[:3])
        if owner is None:
            self.stdout.write(self.style.WARNING(f"{tenant.name}: no active tenant user; skipped Sales 8.1 seeding."))
            return
        if not leads:
            self.stdout.write(self.style.WARNING(f"{tenant.name}: no CRM leads found; skipped Sales 8.1 lead-management seeding."))
            return
        currency, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})
        for lead in leads:
            if not LeadScoreEvent.objects.filter(tenant=tenant, lead=lead).exists():
                record_score_event(
                    lead,
                    tenant,
                    event_type="fit_match" if lead.score >= 70 else "manual_adjustment",
                    signal_category="demographic" if lead.score < 70 else "qualification",
                    score_delta=lead.score,
                    source_kind="qualification",
                    source_ref=f"seed:{lead.pk}",
                    reason="Backfilled seeded CRM lead score into the Sales projection ledger",
                    recorded_by=owner,
                    idempotency_key=f"seed-score:{lead.pk}",
                )
        qualification = LeadQualification.objects.filter(tenant=tenant, lead=leads[0]).first()
        if qualification is None:
            qualification = LeadQualification.objects.create(
                tenant=tenant,
                lead=leads[0],
                framework="bant",
                status="unassessed",
                country_code="US",
                region="North America",
                industry="Technology",
                seniority="manager",
                budget_status="adequate",
                budget_amount=Decimal("25000"),
                budget_currency=currency,
                authority_level="manager",
                need_summary="Needs a consolidated sales operations workspace.",
                expected_purchase_on=timezone.localdate().replace(month=12, day=1),
                next_review_on=timezone.localdate(),
                notes="Seeded qualification evidence.",
            )
            apply_qualification_decision(qualification, tenant, owner, status="qualified", notes="Seeded qualified assessment.")
        if len(leads) > 1 and not LeadQualification.objects.filter(tenant=tenant, lead=leads[1]).exists():
            LeadQualification.objects.create(
                tenant=tenant,
                lead=leads[1],
                framework="meddic",
                status="partially_qualified",
                country_code="US",
                region="North America",
                seniority="individual_contributor",
                budget_status="not_confirmed",
                authority_level="unknown",
                need_summary="Early discovery; budget and authority remain open.",
                next_review_on=timezone.localdate(),
            )
        if not LeadRoutingRule.objects.filter(tenant=tenant, name="Standard owner").exists():
            rule = LeadRoutingRule.objects.create(
                tenant=tenant,
                name="Standard owner",
                description="Routes otherwise-unmatched leads to the tenant sales administrator.",
                priority=100,
                match_mode="all",
                conditions=[],
                is_catch_all=True,
                assignment_mode="fixed_owner",
                default_owner=owner,
            )
            rule.full_clean()
        territory = Territory.objects.filter(tenant=tenant, manager__isnull=False).first()
        if territory and not LeadRoutingRule.objects.filter(tenant=tenant, name="Territory manager").exists():
            rule = LeadRoutingRule.objects.create(
                tenant=tenant,
                name="Territory manager",
                description="Uses the configured CRM territory manager.",
                priority=50,
                match_mode="all",
                conditions=[{"field": "source", "operator": "in", "value": ["referral", "event"]}],
                assignment_mode="territory_manager",
                territory=territory,
            )
            rule.full_clean()
        if not LeadRoutingRule.objects.filter(tenant=tenant, name="Round robin").exists():
            rule = LeadRoutingRule.objects.create(
                tenant=tenant,
                name="Round robin",
                description="Stable round robin for active tenant users.",
                priority=75,
                match_mode="all",
                conditions=[{"field": "status", "operator": "in", "value": ["new", "contacted"]}],
                assignment_mode="round_robin",
            )
            rule.eligible_owners.set(User.objects.filter(tenant=tenant, is_active=True))
            rule.full_clean()
        campaign = Campaign.objects.filter(tenant=tenant).order_by("created_at").first()
        if campaign is None:
            self.stdout.write(self.style.WARNING(f"{tenant.name}: no CRM campaign found; skipped Sales 8.1 nurture seeding."))
            return
        template = EmailTemplate.objects.filter(tenant=tenant).order_by("created_at").first()
        if template is None:
            template = EmailTemplate.objects.create(
                tenant=tenant,
                name="Lead nurture sequence",
                category="drip",
                subject="A useful next step for {{first_name}}",
                body="Hello {{first_name}}, here is a useful next step.",
                owner=owner,
            )
        base_campaign_name = "Sales 8.1 Nurture Sequence"
        drip = EmailCampaign.objects.filter(tenant=tenant, name=base_campaign_name, send_type="drip").first()
        if drip is None:
            campaign_name = base_campaign_name
            suffix = 2
            while EmailCampaign.objects.filter(tenant=tenant, name=campaign_name).exists():
                campaign_name = f"{base_campaign_name} ({suffix})"
                suffix += 1
            drip = EmailCampaign.objects.create(
                tenant=tenant,
                name=campaign_name,
                campaign=campaign,
                template=template,
                send_type="drip",
                status="draft",
                owner=owner,
            )
        purpose, _ = ConsentPurpose.objects.get_or_create(
            tenant=tenant,
            code="sales-nurture",
            defaults={"name": "Sales nurture", "lawful_basis": "consent", "is_optional": True, "is_active": True},
        )
        if not purpose.is_active:
            purpose.is_active = True
            purpose.save(update_fields=["is_active"])
        enrollment = LeadNurtureEnrollment.objects.filter(tenant=tenant, lead=leads[0], email_campaign=drip).first()
        if enrollment is None:
            enrollment = LeadNurtureEnrollment.objects.create(
                tenant=tenant,
                lead=leads[0],
                email_campaign=drip,
                trigger_kind="qualification",
                consent_purpose=purpose,
                consent_evidence="Seeded CRM form submission reference",
                owner=owner,
                status="pending",
                notes="Enrollment state only; no outbound delivery is configured.",
            )
            activate_nurture(enrollment, tenant, owner, next_touch_at=timezone.now() + timedelta(days=1))
        if len(leads) > 1 and not LeadNurtureEnrollment.objects.filter(tenant=tenant, lead=leads[1], email_campaign=drip).exists():
            LeadNurtureEnrollment.objects.create(
                tenant=tenant,
                lead=leads[1],
                email_campaign=drip,
                trigger_kind="form_source",
                consent_purpose=purpose,
                consent_evidence="Seeded CRM form reference",
                owner=owner,
                status="pending",
            )
