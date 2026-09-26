from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Currency
from apps.core.models import ConsentPurpose, Party, Tenant
from apps.crm.models import AccountProfile, Campaign, ContactProfile, EmailCampaign, EmailTemplate, Lead, Opportunity, Territory
from apps.sales.models import (
    AccountClassification,
    AccountPlan,
    AccountStakeholder,
    CompetitorProfile,
    ForecastAdjustment,
    ForecastPeriod,
    ForecastScenario,
    ForecastSubmission,
    LeadNurtureEnrollment,
    LeadQualification,
    LeadRoutingRule,
    LeadScoreEvent,
    OpportunityCompetitor,
    OpportunityOutcome,
    OpportunityPipelinePlacement,
    OpportunityTeamMember,
    PartyEnrichmentEvent,
    Pipeline,
    PipelineStage,
    WinLossReason,
    CPQQuote,
    CPQQuoteLine,
    ProductBundleOption,
    QuoteApprovalRule,
)
from apps.sales.cpq_services import cpq_recalc_quote_totals, cpq_render_proposal_html, cpq_convert_to_sales_order
from apps.sales.forecast_services import forecast_submission_snapshot

from apps.sales.opportunity_services import opportunity_pipeline_baseline_stages
from apps.sales.services import (
    activate_nurture,
    apply_enrichment_event,
    apply_qualification_decision,
    create_enrichment_event,
    record_score_event,
    reject_enrichment_event,
    transition_account_plan,
)



User = get_user_model()


class Command(BaseCommand):
    help = "Seed Sales 8.1, 8.2, 8.3, and 8.4 data idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--backfill",
            action="store_true",
            default=False,
            help="Safely attach existing CRM opportunities to pipelines without overwriting probability overrides or stage timestamps.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        backfill = options.get("backfill", False)
        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run seed_core first."))
            return
        for tenant in tenants:
            self._seed_tenant(tenant, backfill=backfill)
        self.stdout.write(self.style.SUCCESS("Sales 8.1, 8.2, 8.3, and 8.4 seed complete."))
        self.stdout.write("Log in as a tenant admin (e.g. admin_acme / password) to view Sales data.")
        self.stdout.write(self.style.WARNING("Superuser 'admin' has tenant=None — Sales pages show no tenant data when logged in as admin."))
        self.stdout.write(self.style.WARNING("CRM email sends remain simulated; no ESP or delivery worker is seeded."))
        self.stdout.write(self.style.WARNING("Sales 8.3 enrichment is local review evidence only; provider, LinkedIn, verification, and sending workers are not seeded."))

    def _seed_tenant(self, tenant, backfill=False):
        owner = User.objects.filter(tenant=tenant, is_tenant_admin=True).first() or User.objects.filter(tenant=tenant, is_active=True).first()
        leads = list(Lead.objects.filter(tenant=tenant).order_by("created_at")[:3])
        if owner is None:
            self.stdout.write(self.style.WARNING(f"{tenant.name}: no active tenant user; skipped Sales 8.1, 8.2, and 8.3 seeding."))
            return
        self._seed_contact_account_management(tenant, owner)
        self._seed_opportunity_pipeline(tenant, owner, backfill=backfill)
        self._seed_sales_forecasting(tenant, owner)
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

    def _seed_contact_account_management(self, tenant, owner):
        today = timezone.localdate()
        for model, label in (
            (AccountStakeholder, "account stakeholders"),
            (AccountClassification, "account classifications"),
            (AccountPlan, "account plans"),
            (PartyEnrichmentEvent, "enrichment events"),
        ):
            if model.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"{tenant.name}: {label} already exist; preserving them and filling only missing demo rows.")

        def party_for(name, kind):
            party = Party.objects.filter(tenant=tenant, kind=kind, name=name).first()
            if party is None:
                party = Party.objects.create(tenant=tenant, kind=kind, name=name)
            return party

        def account_for(name, parent=None):
            party = party_for(name, "organization")
            profile, _ = AccountProfile.objects.get_or_create(
                tenant=tenant,
                party=party,
                defaults={"industry": "technology", "employee_count": 100},
            )
            if parent is not None and profile.parent_account_id is None:
                profile.parent_account = parent
                profile.save(update_fields=["parent_account", "updated_at"])
            return party

        root = account_for("Sales 8.3 Global Account")
        child = account_for("Sales 8.3 Operating Company", root)
        grandchild = account_for("Sales 8.3 Regional Unit", child)
        separate_root = account_for("Sales 8.3 Independent Account")
        accounts = [root, child, grandchild, separate_root]

        contact_specs = [
            ("Sales 8.3 Decision Maker", root),
            ("Sales 8.3 Champion", root),
            ("Sales 8.3 Economic Buyer", child),
            ("Sales 8.3 Technical Evaluator", grandchild),
            ("Sales 8.3 Procurement Contact", separate_root),
        ]
        contacts = []
        for name, account in contact_specs:
            party = party_for(name, "person")
            ContactProfile.objects.get_or_create(
                tenant=tenant,
                party=party,
                defaults={"account": account, "owner": owner, "job_title": "Sales stakeholder"},
            )
            contacts.append((party, account))

        role_specs = [
            (root, contacts[0][0], "decision_maker", "high", "positive", "strong"),
            (root, contacts[1][0], "champion", "high", "positive", "strong"),
            (child, contacts[2][0], "economic_buyer", "high", "neutral", "moderate"),
            (grandchild, contacts[3][0], "technical_evaluator", "medium", "positive", "moderate"),
            (separate_root, contacts[4][0], "procurement", "medium", "neutral", "moderate"),
            (root, contacts[2][0], "influencer", "medium", "positive", "moderate"),
        ]
        for account, contact, role, influence, attitude, strength in role_specs:
            AccountStakeholder.objects.get_or_create(
                tenant=tenant,
                account=account,
                contact=contact,
                role=role,
                defaults={
                    "influence": influence,
                    "attitude": attitude,
                    "relationship_strength": strength,
                    "status": "active",
                    "notes": "Seeded buying-center relationship.",
                },
            )

        classification_specs = [
            (root, "strategic", "active_customer", "high", "very_high", "full_wallet"),
            (child, "key", "expansion_candidate", "high", "high", "large"),
            (grandchild, "growth", "prospect", "medium", "medium", "medium"),
            (separate_root, "nurture", "dormant", "low", "unknown", "small"),
        ]
        for account, tier, lifecycle, priority, potential, wallet in classification_specs:
            AccountClassification.objects.get_or_create(
                tenant=tenant,
                account=account,
                defaults={
                    "tier": tier,
                    "lifecycle_stage": lifecycle,
                    "strategic_priority": priority,
                    "revenue_potential": potential,
                    "wallet_category": wallet,
                    "rationale": "Seeded classification for the Sales 8.3 workspace.",
                    "effective_on": today,
                    "review_due_on": today + timedelta(days=90) if tier in {"strategic", "key"} else None,
                    "classified_by": owner,
                },
            )

        opportunity = Opportunity.objects.filter(tenant=tenant, account=root).only("id", "account_id", "created_at").order_by("-created_at").first()
        if opportunity is None:
            self.stdout.write(f"{tenant.name}: no existing CRM opportunity for the 8.3 demo; account plans will remain unlinked.")

        plan_specs = [
            ("draft", "Sales 8.3 Draft Plan"),
            ("active", "Sales 8.3 Active Plan"),
            ("review_due", "Sales 8.3 Review Plan"),
            ("completed", "Sales 8.3 Completed Plan"),
            ("archived", "Sales 8.3 Archived Plan"),
        ]
        plan_sequence = ("draft", "active", "review_due", "completed", "archived")
        for target_status, title in plan_specs:
            plan = AccountPlan.objects.filter(tenant=tenant, account=root, title=title).first()
            if plan is None:
                plan = AccountPlan.objects.create(
                    tenant=tenant,
                    account=root,
                    title=title,
                    period_start=today - timedelta(days=30),
                    period_end=today + timedelta(days=180),
                    owner=owner,
                    business_drivers="Seeded strategic account planning context.",
                    objectives="Build a measurable account growth plan.",
                    strategy="Align the buying center and expand adoption.",
                    white_space_assessment="Qualitative assessment; product mapping is not governed yet.",
                    growth_initiatives="Sponsor an executive alignment workshop.",
                    risk_summary="Confirm authority and procurement timing.",
                    next_review_on=today + timedelta(days=30),
                )
            if plan.status not in plan_sequence:
                self.stdout.write(self.style.WARNING(f"{tenant.name}: plan {plan.number} has an unsupported lifecycle state; preserved it."))
                continue
            if opportunity is not None and not plan.related_opportunities.filter(pk=opportunity.pk).exists():
                plan.related_opportunities.add(opportunity)
            current_index = plan_sequence.index(plan.status)
            target_index = plan_sequence.index(target_status)
            for next_status in plan_sequence[current_index + 1:target_index + 1]:
                plan = transition_account_plan(plan, tenant, owner, next_status)

        enrichment_purpose, _ = ConsentPurpose.objects.get_or_create(
            tenant=tenant,
            code="account-research",
            defaults={
                "name": "Account research",
                "lawful_basis": "legitimate_interest",
                "is_optional": False,
                "is_active": True,
            },
        )
        if not enrichment_purpose.is_active:
            enrichment_purpose.is_active = True
            enrichment_purpose.save(update_fields=["is_active"])
        event_specs = [
            (root, "proposed", "firmographic", "manual", None, {"industry": {"value": "technology", "confidence": 0.8}}),
            (contacts[0][0], "applied", "contact", "manual", None, {"job_title": {"value": "Sales stakeholder", "confidence": 0.9}}),
            (root, "rejected", "duplicate_check", "manual", None, {"annual_revenue": {"value": "1000000.00", "confidence": 0.4}}),
            (contacts[0][0], "proposed", "email_validation", "import", enrichment_purpose, {"work_email": {"value": "sales8.3@example.com", "confidence": 0.7}}),
        ]
        # Applying/rejecting an enrichment event is a tenant-ADMIN action
        # (`apply_enrichment_event` re-checks the right server-side). A tenant with no
        # tenant-admin falls back to its first active user, and calling the admin-only
        # action with that user raised and aborted the whole command before any later
        # tenant was seeded. Skip the review action instead of failing the run; the
        # evidence is still seeded as a pending "proposed" event either way.
        owner_is_admin = bool(
            getattr(owner, "is_superuser", False) or getattr(owner, "is_tenant_admin", False)
        )
        for party, outcome, kind, source_kind, purpose, changes in event_specs:
            event = create_enrichment_event(
                tenant,
                owner,
                party=party,
                kind=kind,
                source_kind=source_kind,
                source_name="Sales 8.3 seed",
                source_reference=f"seed:party-enrichment:{party.pk}:{kind}:{outcome}",
                changes=changes,
                legal_basis_purpose=purpose,
                idempotency_key=f"seed-party-enrichment:{party.pk}:{kind}:{outcome}",
            )
            if not owner_is_admin:
                continue
            if event.status == "proposed" and outcome == "applied":
                apply_enrichment_event(event, tenant, owner, tuple(event.changes), "Seeded reviewed contact title.")
            elif event.status == "proposed" and outcome == "rejected":
                reject_enrichment_event(event, tenant, owner, "Seeded duplicate evidence was not applied.")

    def _seed_opportunity_pipeline(self, tenant, owner, backfill=False):
        pipeline = Pipeline.objects.filter(tenant=tenant, is_default=True).first()
        if pipeline is None:
            pipeline = Pipeline.objects.create(
                tenant=tenant,
                name="Standard Sales Pipeline",
                description="Default pipeline for standard sales opportunities.",
                is_default=True,
                is_active=True,
            )
        if not pipeline.stages.exists():
            for stage_data in opportunity_pipeline_baseline_stages():
                PipelineStage.objects.create(
                    tenant=tenant,
                    pipeline=pipeline,
                    **stage_data,
                )

        reasons = [
            ("price_discount", "Price / Discount", "Won or lost due to pricing or discount terms", 10, "both", "price"),
            ("product_fit", "Product Feature Fit", "Met requirements and feature scope", 20, "both", "product_fit"),
            ("competitor_feature", "Competitor Superiority", "Competitor had superior features or incumbency", 30, "lost", "competition"),
            ("relationship", "Strong Executive Relationship", "Executive sponsor alignment and trust", 40, "won", "relationship"),
            ("budget_freeze", "Budget Cancelled / Frozen", "Project postponed due to capital freeze", 50, "lost", "budget"),
            ("no_decision", "No Decision / Status Quo", "Prospect decided to stay with current process", 60, "lost", "no_decision"),
        ]
        for code, name, desc, seq, res, cat in reasons:
            WinLossReason.objects.get_or_create(
                tenant=tenant,
                code=code,
                defaults={
                    "name": name,
                    "description": desc,
                    "sequence": seq,
                    "result": res,
                    "category": cat,
                    "is_active": True,
                },
            )

        competitor_party = Party.objects.filter(tenant=tenant, kind="organization").exclude(
            pk__in=AccountProfile.objects.filter(tenant=tenant).values_list("party_id", flat=True)
        ).first()
        if competitor_party is None:
            competitor_party, _ = Party.objects.get_or_create(
                tenant=tenant,
                name="Apex Solutions Corp",
                kind="organization",
            )
        competitor_profile = CompetitorProfile.objects.filter(tenant=tenant, party=competitor_party).first()

        if competitor_profile is None:
            competitor_profile = CompetitorProfile.objects.create(
                tenant=tenant,
                party=competitor_party,
                website_url="https://apex-solutions.example.com",
                description="Leading incumbent provider in enterprise sales.",
                market_positioning="Legacy vendor with broad but dated suite.",
                strengths="Deep brand recognition, installed customer base.",
                weaknesses="Slow product iterations, expensive maintenance, complex UI.",
                differentiators="NavERP offers unified core data and real-time ledger accounting.",
                objection_handling="Emphasize total cost of ownership and rapid time-to-value.",
                is_active=True,
            )

        opportunities = list(Opportunity.objects.filter(tenant=tenant).order_by("created_at"))
        stages_by_key = {s.crm_stage_key: s for s in pipeline.stages.all()}
        open_stage = stages_by_key.get("qualification") or stages_by_key.get("prospecting") or next((s for s in stages_by_key.values() if s.stage_kind == "open"), None)

        existing_placement_opp_ids = set(
            OpportunityPipelinePlacement.objects.filter(tenant=tenant).values_list("opportunity_id", flat=True)
        )
        existing_team_opp_ids = set(
            OpportunityTeamMember.objects.filter(tenant=tenant, user=owner).values_list("opportunity_id", flat=True)
        )
        existing_outcome_opp_ids = set(
            OpportunityOutcome.objects.filter(tenant=tenant).values_list("opportunity_id", flat=True)
        )
        existing_competitor_opp_ids = set(
            OpportunityCompetitor.objects.filter(tenant=tenant).values_list("opportunity_id", flat=True)
        )
        existing_comp_profile_opp_ids = set(
            OpportunityCompetitor.objects.filter(
                tenant=tenant, competitor_profile=competitor_profile
            ).values_list("opportunity_id", flat=True)
        )
        all_active_competitors = list(
            CompetitorProfile.objects.filter(tenant=tenant, is_active=True).select_related("party")
        )
        competitors_by_name = {
            c.party.name.strip().lower(): c for c in all_active_competitors if c.party and c.party.name
        }
        all_active_reasons = list(WinLossReason.objects.filter(tenant=tenant, is_active=True))
        won_reasons = [r for r in all_active_reasons if r.result in ("won", "both")]
        lost_reasons = [r for r in all_active_reasons if r.result in ("lost", "both")]
        first_won_reason = won_reasons[0] if won_reasons else None
        first_lost_reason = lost_reasons[0] if lost_reasons else None
        reasons_by_name_lost = {
            r.name.strip().lower(): r for r in lost_reasons
        }

        for idx, opp in enumerate(opportunities):
            if opp.pk not in existing_placement_opp_ids:
                target_stage = stages_by_key.get(opp.stage) or open_stage
                if target_stage:
                    prob_override = (
                        opp.probability
                        if opp.probability is not None and opp.probability != target_stage.probability
                        else None
                    )
                    if target_stage.stage_kind == "won" and prob_override is not None and prob_override != 100:
                        prob_override = 100
                    elif target_stage.stage_kind == "lost" and prob_override is not None and prob_override != 0:
                        prob_override = 0
                    stage_entered = opp.stage_changed_at or opp.created_at or timezone.now()
                    OpportunityPipelinePlacement.objects.create(
                        tenant=tenant,
                        opportunity=opp,
                        pipeline=pipeline,
                        current_stage=target_stage,
                        probability_override=prob_override,
                        stage_entered_at=stage_entered,
                    )
                    existing_placement_opp_ids.add(opp.pk)
            if backfill:
                if opp.competitor and opp.pk not in existing_competitor_opp_ids:
                    comp_match = competitors_by_name.get(opp.competitor.strip().lower())
                    if comp_match:
                        OpportunityCompetitor.objects.create(
                            tenant=tenant,
                            opportunity=opp,
                            competitor_profile=comp_match,
                            relationship="shortlisted",
                            is_primary=True,
                            positioning_notes="Backfilled from legacy competitor field.",
                        )
                        existing_competitor_opp_ids.add(opp.pk)
                        if comp_match.pk == competitor_profile.pk:
                            existing_comp_profile_opp_ids.add(opp.pk)
                if opp.stage == "closed_lost" and opp.loss_reason and opp.pk not in existing_outcome_opp_ids:
                    loss_match = reasons_by_name_lost.get(opp.loss_reason.strip().lower())
                    if loss_match:
                        OpportunityOutcome.objects.create(
                            tenant=tenant,
                            opportunity=opp,
                            result="lost",
                            reason=loss_match,
                            notes=opp.loss_reason,
                            recorded_by=owner,
                            closed_at=opp.lost_at or opp.stage_changed_at or opp.created_at,
                        )
                        existing_outcome_opp_ids.add(opp.pk)
            if opp.pk not in existing_team_opp_ids:
                OpportunityTeamMember.objects.create(
                    tenant=tenant,
                    opportunity=opp,
                    user=owner,
                    role="executive_sponsor" if idx == 0 else "collaborator",
                    responsibility="Oversee strategic alignment and deal execution.",
                    is_active=True,
                )
                existing_team_opp_ids.add(opp.pk)
            if idx == 0 and opp.pk not in existing_comp_profile_opp_ids:
                OpportunityCompetitor.objects.create(
                    tenant=tenant,
                    opportunity=opp,
                    competitor_profile=competitor_profile,
                    relationship="shortlisted",
                    is_primary=True,
                    positioning_notes="Client evaluating against Apex legacy suite.",
                )
                existing_comp_profile_opp_ids.add(opp.pk)
                existing_competitor_opp_ids.add(opp.pk)
            if opp.stage in ("closed_won", "closed_lost") and opp.pk not in existing_outcome_opp_ids:
                outcome_res = "won" if opp.stage == "closed_won" else "lost"
                wlr = first_won_reason if outcome_res == "won" else first_lost_reason
                if wlr:
                    OpportunityOutcome.objects.create(
                        tenant=tenant,
                        opportunity=opp,
                        result=outcome_res,
                        reason=wlr,
                        notes="Seeded outcome closure record.",
                        recorded_by=owner,
                    )
                    existing_outcome_opp_ids.add(opp.pk)



    def _seed_sales_forecasting(self, tenant, owner):
        """8.4 Sales Forecasting demo rows, idempotent by construction.

        Reuses the Opportunity / Pipeline / Territory / Currency rows seeded above. Every
        model here is auto-numbered (`FCP-`, `FCS-`, `FAD-`, `FSC-`) and the number is
        minted by `TenantNumbered.save()`, so the guard is an existence check on a natural
        key rather than on the number — a second run finds every row and creates nothing.

        The AI gate is deliberately NOT satisfied: 40 won AND 40 lost outcomes are never
        seeded, so the forecast pages render the "not enough history" message and no
        prediction value (contract 10).
        """
        for model, label in (
            (ForecastPeriod, "forecast periods"),
            (ForecastSubmission, "forecast submissions"),
            (ForecastAdjustment, "forecast adjustments"),
            (ForecastScenario, "forecast scenarios"),
        ):
            if model.objects.filter(tenant=tenant).exists():
                self.stdout.write(
                    f"{tenant.name}: {label} already exist; preserving them and filling only "
                    "missing demo rows."
                )

        currency, _ = Currency.objects.get_or_create(
            code="USD", defaults={"name": "US Dollar", "symbol": "$"}
        )
        today = timezone.localdate()
        pipeline = Pipeline.objects.filter(tenant=tenant, is_active=True).order_by("id").first()
        territory = Territory.objects.filter(tenant=tenant).order_by("id").first()
        opportunities = list(
            Opportunity.objects.filter(tenant=tenant)
            .exclude(stage="closed_lost")
            .order_by("created_at")[:10]
        )

        # --- 2 periods: one current, one past -----------------------------------------
        current_quarter = (today.month - 1) // 3 + 1
        prior_year = today.year - 1 if current_quarter == 1 else today.year
        prior_number = 4 if current_quarter == 1 else current_quarter - 1
        period_specs = [
            ("Current Forecast Quarter", "quarter", today.year, current_quarter, "user", True),
            ("Prior Forecast Quarter", "quarter", prior_year, prior_number, "org_unit", False),
        ]
        periods = {}
        for name, period_type, year, number, dimension, active in period_specs:
            period = ForecastPeriod.objects.filter(
                tenant=tenant, period_type=period_type, period_year=year, period_number=number
            ).first()
            if period is None:
                period = ForecastPeriod.objects.create(
                    tenant=tenant,
                    name=name,
                    period_type=period_type,
                    period_year=year,
                    period_number=number,
                    rollup_dimension=dimension,
                    reporting_currency=currency,
                    is_active=active,
                    is_locked=False,
                )
            periods[name] = period
        current_period = periods["Current Forecast Quarter"]

        # --- 2-3 submissions across two owners ---------------------------------------
        owners = list(User.objects.filter(tenant=tenant, is_active=True).order_by("id")[:2]) or [owner]
        submission_amounts = [Decimal("45000.00"), Decimal("120000.00"), Decimal("78000.00")]
        submissions = []
        for index, submission_owner in enumerate(owners):
            existing = ForecastSubmission.objects.filter(
                tenant=tenant, period=current_period, owner=submission_owner
            ).first()
            if existing is not None:
                submissions.append(existing)
                continue
            base = submission_amounts[index % len(submission_amounts)]
            submission = ForecastSubmission(
                tenant=tenant,
                period=current_period,
                owner=submission_owner,
                territory=territory,
                pipeline=pipeline,
                status="submitted" if index == 0 else "draft",
                pipeline_amount=base * Decimal("2.5"),
                best_case_amount=base * Decimal("1.4"),
                commit_amount=base,
                closed_amount=Decimal("0.00"),
                notes="Seeded 8.4 forecast call.",
            )
            if index == 0:
                submission.submitted_at = timezone.now()
                submission.submitted_by = submission_owner
            submission.save()
            # The three snapshot figures are service-written, never hand-typed.
            snapshot = forecast_submission_snapshot(submission, tenant=tenant)
            submission.weighted_amount = snapshot["weighted_amount"]
            submission.quota_amount = snapshot["quota_amount"]
            submission.actual_amount = snapshot["actual_amount"]
            submission.save(
                update_fields=["weighted_amount", "quota_amount", "actual_amount", "updated_at"]
            )
            submissions.append(submission)

        # --- 2-3 adjustments, one of them reverted ------------------------------------
        if submissions:
            opportunity = opportunities[0] if opportunities else None
            adjustment_specs = [
                (submissions[0], "amount", "deal_advanced", Decimal("15000.00"),
                 "Seeded manager uplift for an advanced deal.", False),
                (submissions[-1], "category", "deal_slipped", None,
                 "Seeded downgrade after a slipped close date.", False),
                (submissions[0], "amount", "amount_revised", Decimal("2500.00"),
                 "Seeded correction later reset by the manager.", True),
            ]
            for submission, target_field, reason_code, value, note, reverted in adjustment_specs:
                if ForecastAdjustment.objects.filter(
                    tenant=tenant, submission=submission, reason_code=reason_code, note=note
                ).exists():
                    continue
                adjustment = ForecastAdjustment(
                    tenant=tenant,
                    submission=submission,
                    opportunity=opportunity,
                    adjustment_kind="direct",
                    target_field=target_field,
                    adjusted_value=value,
                    reason_code=reason_code,
                    note=note,
                    created_by=owner,
                )
                if target_field == "category":
                    adjustment.original_category = "pipeline"
                    adjustment.adjusted_category = "commit"
                else:
                    adjustment.original_value = Decimal("10000.00")
                adjustment.save()
                if reverted:
                    adjustment.mark_reverted(owner, "Seeded Reset with a mandatory reason.")
                    adjustment.save()

        # --- 2 scenarios: one baseline (and therefore selected) and one what-if --------
        # `scenario_type` is the model's own upside/base/downside/custom vocabulary; the
        # separate `is_baseline` flag is what marks the current plan.
        scenario_specs = [
            ("Baseline Plan", "base", 100, Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), True),
            ("Upside Case", "upside", 90, Decimal("15.00"), Decimal("25.00"), Decimal("20.00"), False),
        ]
        for name, scenario_type, probability, pipeline_delta, best_case_delta, commit_delta, baseline in scenario_specs:
            if ForecastScenario.objects.filter(tenant=tenant, period=current_period, name=name).exists():
                continue
            scenario = ForecastScenario(
                tenant=tenant,
                period=current_period,
                owner=owner,
                name=name,
                scenario_type=scenario_type,
                probability_pct=probability,
                is_baseline=baseline,
                # The CheckConstraint pins baseline => selected, so only the baseline is.
                is_selected=baseline,
                pipeline_delta_pct=pipeline_delta,
                best_case_delta_pct=best_case_delta,
                commit_delta_pct=commit_delta,
                assumption_notes="Seeded 8.4 what-if scenario. Applying it never changes a call.",
            )
            scenario.save()
            # projected_* are editable=False: only the apply action may write them.
            scenario.projected_commit_amount = Decimal("0.00")
            scenario.projected_total_amount = Decimal("0.00")
            scenario.save(
                update_fields=["projected_commit_amount", "projected_total_amount", "updated_at"]
            )
        self.stdout.write(f"{tenant.name}: Sales 8.4 forecasting demo rows ensured.")

        # ================================================================
        # 8.5 Quote & Proposal Management (CPQ)
        # ================================================================
        from apps.crm.models import Product, PriceBook
        from apps.scm.models.InventoryManagement.Items import Item, UOM

        currency_usd = Currency.objects.filter(code="USD").first()
        primary_opp = opportunities[0] if opportunities else None
        primary_account = primary_opp.account if primary_opp else Party.objects.filter(tenant=tenant, kind="organization").first()
        primary_contact = primary_opp.contact if primary_opp and hasattr(primary_opp, "contact") else Party.objects.filter(tenant=tenant, kind="person").first()

        # --- 1. Quote Approval Rules -------------------------------------
        rule_specs = [
            ("Executive Discount Floor", "max_discount", Decimal("25.00"), Decimal("15.00"), None, "vp_sales", 10, False, "Quotes with over 25% discount require VP sign-off."),
            ("Standard Margin Floor", "min_margin", Decimal("20.00"), Decimal("15.00"), None, "sales_manager", 20, False, "Quotes below 15% net margin require manager review."),
            ("Enterprise Value Ceiling", "max_amount", Decimal("20.00"), Decimal("15.00"), Decimal("50000.00"), "finance_manager", 30, False, "Contracts exceeding $50k require finance approval."),
        ]
        for r_name, r_type, r_disc, r_margin, r_amt, r_role, r_prio, r_reject, r_desc in rule_specs:
            if not QuoteApprovalRule.objects.filter(tenant=tenant, name=r_name).exists():
                QuoteApprovalRule.objects.create(
                    tenant=tenant,
                    name=r_name,
                    rule_type=r_type,
                    discount_threshold_pct=r_disc,
                    min_margin_pct=r_margin,
                    amount_threshold=r_amt,
                    approver_role=r_role,
                    priority=r_prio,
                    auto_reject=r_reject,
                    is_active=True,
                    description=r_desc,
                )

        # --- 2. Products & Bundle Options --------------------------------
        bundle_prod, _ = Product.objects.get_or_create(
            tenant=tenant,
            name="Enterprise Cloud Platform",
            defaults={"unit_price": Decimal("12500.00"), "is_active": True}
        )
        comp_gateway, _ = Product.objects.get_or_create(
            tenant=tenant,
            name="Dedicated Security Gateway Appliance",
            defaults={"unit_price": Decimal("4500.00"), "is_active": True}
        )
        comp_licenses, _ = Product.objects.get_or_create(
            tenant=tenant,
            name="Enterprise User Analytics License",
            defaults={"unit_price": Decimal("150.00"), "is_active": True}
        )
        comp_support, _ = Product.objects.get_or_create(
            tenant=tenant,
            name="24/7 Mission-Critical SLA Support",
            defaults={"unit_price": Decimal("2000.00"), "is_active": True}
        )

        item_sku = Item.objects.filter(tenant=tenant).first()
        uom_unit = UOM.objects.filter(tenant=tenant).first()

        bundle_specs = [
            ("Security Gateway Appliance", bundle_prod, comp_gateway, "Hardware", True, True, Decimal("1"), Decimal("1"), Decimal("2"), None, None, "none", None, 10),
            ("User Analytics Licenses (10-Pack)", bundle_prod, comp_licenses, "Software", False, True, Decimal("5"), Decimal("10"), Decimal("50"), Decimal("120.00"), Decimal("10.00"), "none", None, 20),
            ("24/7 Enterprise SLA Support Tier", bundle_prod, comp_support, "Support", False, False, Decimal("1"), Decimal("1"), Decimal("1"), None, None, "requires", comp_gateway, 30),
        ]
        for b_name, b_prod, c_prod, o_grp, req, dflt, min_q, dflt_q, max_q, p_ovr, d_ovr, c_rule, dep_prod, s_ord in bundle_specs:
            if not ProductBundleOption.objects.filter(tenant=tenant, bundle_product=b_prod, component_product=c_prod).exists():
                ProductBundleOption.objects.create(
                    tenant=tenant,
                    name=b_name,
                    bundle_product=b_prod,
                    component_product=c_prod,
                    component_item=item_sku,
                    option_group=o_grp,
                    is_required=req,
                    is_default=dflt,
                    min_quantity=min_q,
                    default_quantity=dflt_q,
                    max_quantity=max_q,
                    unit_price_override=p_ovr,
                    discount_pct_override=d_ovr,
                    compatibility_rule=c_rule,
                    depends_on_product=dep_prod,
                    sort_order=s_ord,
                    is_active=True,
                )

        # --- 3. CPQ Quotes Lifecycle Demos -------------------------------
        if not CPQQuote.objects.filter(tenant=tenant, name="Enterprise Platform Suite — Acme Corp").exists():
            # Quote 1: Primary quote with bundle hierarchy
            q1 = CPQQuote.objects.create(
                tenant=tenant,
                name="Enterprise Platform Suite — Acme Corp",
                opportunity=primary_opp,
                account=primary_account,
                contact=primary_contact,
                currency=currency_usd,
                status="draft",
                approval_status="not_required",
                valid_until=timezone.localdate() + timedelta(days=30),
                is_primary=True,
                header_discount_pct=Decimal("5.00"),
                terms_and_conditions="Net 30 payment terms. Includes standard 1-year warranty and platform onboarding.",
                owner=owner,
            )
            # Add package parent line
            parent_ln = CPQQuoteLine.objects.create(
                tenant=tenant,
                quote=q1,
                parent_line=None,
                line_type="bundle_parent",
                product=bundle_prod,
                item=item_sku,
                uom=uom_unit,
                description=f"Package: {bundle_prod.name}",
                quantity=Decimal("1.00"),
                list_price=Decimal("12500.00"),
                unit_price=Decimal("12500.00"),
                unit_cost=Decimal("7000.00"),
                sequence=10,
            )
            # Component 1
            CPQQuoteLine.objects.create(
                tenant=tenant,
                quote=q1,
                parent_line=parent_ln,
                line_type="bundle_component",
                product=comp_gateway,
                item=item_sku,
                uom=uom_unit,
                description=f"Hardware: {comp_gateway.name}",
                quantity=Decimal("1.00"),
                list_price=Decimal("4500.00"),
                unit_price=Decimal("4500.00"),
                unit_cost=Decimal("2800.00"),
                sequence=20,
            )
            # Component 2
            CPQQuoteLine.objects.create(
                tenant=tenant,
                quote=q1,
                parent_line=parent_ln,
                line_type="bundle_component",
                product=comp_licenses,
                item=item_sku,
                uom=uom_unit,
                description=f"Software: {comp_licenses.name}",
                quantity=Decimal("10.00"),
                list_price=Decimal("150.00"),
                discount_pct=Decimal("10.00"),
                unit_price=Decimal("135.00"),
                unit_cost=Decimal("40.00"),
                sequence=30,
            )
            # Component 3 (Optional Add-on)
            CPQQuoteLine.objects.create(
                tenant=tenant,
                quote=q1,
                parent_line=parent_ln,
                line_type="optional_addon",
                product=comp_support,
                item=item_sku,
                uom=uom_unit,
                description=f"Support: {comp_support.name}",
                quantity=Decimal("1.00"),
                list_price=Decimal("2000.00"),
                unit_price=Decimal("2000.00"),
                unit_cost=Decimal("800.00"),
                is_optional=True,
                is_selected=True,
                sequence=40,
            )
            cpq_recalc_quote_totals(q1, save=True)

        if not CPQQuote.objects.filter(tenant=tenant, name="Global Security & SLA Expansion").exists():
            # Quote 2: E-Signed & Accepted proposal
            q2 = CPQQuote.objects.create(
                tenant=tenant,
                name="Global Security & SLA Expansion",
                opportunity=primary_opp,
                account=primary_account,
                contact=primary_contact,
                currency=currency_usd,
                status="accepted",
                approval_status="approved",
                approved_by=owner,
                approved_at=timezone.now() - timedelta(days=2),
                valid_until=timezone.localdate() + timedelta(days=20),
                is_primary=False,
                header_discount_pct=Decimal("10.00"),
                terms_and_conditions="Annual prepaid commitment. Full 24/7 SLA response within 15 minutes.",
                signer_name="Sarah Jenkins",
                signer_title="VP Information Technology",
                signer_email="sarah.jenkins@acmecorp.com",
                signed_at=timezone.now() - timedelta(days=1),
                signature_data="Sarah Jenkins",
                owner=owner,
            )
            CPQQuoteLine.objects.create(
                tenant=tenant,
                quote=q2,
                line_type="standard",
                product=comp_gateway,
                item=item_sku,
                uom=uom_unit,
                description=f"{comp_gateway.name} — Redundant Cluster",
                quantity=Decimal("2.00"),
                list_price=Decimal("4500.00"),
                unit_price=Decimal("4500.00"),
                unit_cost=Decimal("2800.00"),
                sequence=10,
            )
            CPQQuoteLine.objects.create(
                tenant=tenant,
                quote=q2,
                line_type="standard",
                product=comp_support,
                item=item_sku,
                uom=uom_unit,
                description=f"{comp_support.name} (Multi-Year)",
                quantity=Decimal("2.00"),
                list_price=Decimal("2000.00"),
                unit_price=Decimal("2000.00"),
                unit_cost=Decimal("800.00"),
                sequence=20,
            )
            cpq_recalc_quote_totals(q2, save=True)
            cpq_render_proposal_html(q2)

        if not CPQQuote.objects.filter(tenant=tenant, name="Infrastructure Hardware Order Handoff").exists():
            # Quote 3: Approved & Converted to Sales Order
            q3 = CPQQuote.objects.create(
                tenant=tenant,
                name="Infrastructure Hardware Order Handoff",
                opportunity=primary_opp,
                account=primary_account,
                contact=primary_contact,
                currency=currency_usd,
                status="accepted",
                approval_status="approved",
                approved_by=owner,
                approved_at=timezone.now() - timedelta(days=5),
                valid_until=timezone.localdate() + timedelta(days=15),
                is_primary=False,
                header_discount_pct=Decimal("0.00"),
                terms_and_conditions="Immediate warehouse fulfillment upon signature.",
                owner=owner,
            )
            CPQQuoteLine.objects.create(
                tenant=tenant,
                quote=q3,
                line_type="standard",
                product=comp_gateway,
                item=item_sku,
                uom=uom_unit,
                description="Production Security Gateway System",
                quantity=Decimal("1.00"),
                list_price=Decimal("4500.00"),
                unit_price=Decimal("4500.00"),
                unit_cost=Decimal("2800.00"),
                sequence=10,
            )
            cpq_recalc_quote_totals(q3, save=True)
            # Perform automated order conversion
            try:
                cpq_convert_to_sales_order(q3, user=owner)
            except Exception:
                pass

        self.stdout.write(f"{tenant.name}: Sales 8.5 CPQ demo rows ensured.")

