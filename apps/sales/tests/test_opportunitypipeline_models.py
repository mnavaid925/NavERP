from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit, Party, Tenant
from apps.crm.models import AccountProfile, Opportunity
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfile,
    OpportunityCompetitor,
)
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityOutcome,
    WinLossReason,
)
from apps.sales.models.OpportunityPipeline.Pipelines import (
    PIPELINE_CRITERION_CHOICES,
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
    _validate_pipeline_criteria,
)
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember
from apps.sales.tests.conftest import (
    OPPORTUNITYPIPELINE_CHOICES,
    OPPORTUNITYPIPELINE_MODEL_FIELDS,
)

# Alias OpportunityPipeline to Pipeline per sub-module contract
OpportunityPipeline = Pipeline

pytestmark = pytest.mark.django_db


# ============================================================================
# Module Helpers (_opportunitypipeline_*)
# ============================================================================

def _opportunitypipeline_tenant(name="Acme Corp", slug=None):
    slug = slug or f"tenant-{int(timezone.now().timestamp() * 1000) % 1000000}"
    return Tenant.objects.create(name=name, slug=slug)


def _opportunitypipeline_user(tenant, email=None, *, is_admin=False, is_active=True):
    email = email or f"user_{int(timezone.now().timestamp() * 1000) % 1000000}@example.com"
    username = email.split("@")[0][:30]
    return User.objects.create_user(
        email=email,
        username=username,
        password="TestPassword123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
        is_active=is_active,
    )


def _opportunitypipeline_party(tenant, name=None, kind="organization"):
    name = name or f"Party_{int(timezone.now().timestamp() * 1000) % 1000000}"
    return Party.objects.create(tenant=tenant, name=name, kind=kind)


def _opportunitypipeline_org_unit(tenant, name=None):
    name = name or f"OrgUnit_{int(timezone.now().timestamp() * 1000) % 1000000}"
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _opportunitypipeline_opportunity(
    tenant, name=None, owner=None, stage="prospecting", amount=Decimal("15000.00"), **kwargs
):
    name = name or kwargs.pop("title", None) or f"Deal_{int(timezone.now().timestamp() * 1000) % 1000000}"
    party = _opportunitypipeline_party(tenant, name=f"AccountParty_{name}")
    return Opportunity.objects.create(
        tenant=tenant,
        name=name,
        account=party,
        owner=owner,
        stage=stage,
        amount=amount,
        **kwargs,
    )


def _opportunitypipeline_pipeline(
    tenant, name="Standard Pipeline", is_default=False, is_active=True, **kwargs
):
    return Pipeline.objects.create(
        tenant=tenant,
        name=name,
        is_default=is_default,
        is_active=is_active,
        **kwargs,
    )


def _opportunitypipeline_stage(
    tenant,
    pipeline,
    name="Discovery",
    code=None,
    sequence=10,
    stage_kind="open",
    crm_stage_key="prospecting",
    probability=10,
    forecast_category="pipeline",
    **kwargs,
):
    code = code or f"stage_{sequence}_{int(timezone.now().timestamp() * 1000) % 100000}"
    return PipelineStage.objects.create(
        tenant=tenant,
        pipeline=pipeline,
        name=name,
        code=code,
        sequence=sequence,
        stage_kind=stage_kind,
        crm_stage_key=crm_stage_key,
        probability=probability,
        forecast_category=forecast_category,
        **kwargs,
    )


def _opportunitypipeline_placement(
    tenant, opportunity, pipeline, current_stage, probability_override=None, **kwargs
):
    return OpportunityPipelinePlacement.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        pipeline=pipeline,
        current_stage=current_stage,
        probability_override=probability_override,
        **kwargs,
    )


def _opportunitypipeline_team_member(
    tenant, opportunity, user, role="collaborator", org_unit=None, is_active=True, **kwargs
):
    return OpportunityTeamMember.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        user=user,
        role=role,
        org_unit=org_unit,
        is_active=is_active,
        **kwargs,
    )


def _opportunitypipeline_competitor_profile(
    tenant, party=None, name="Rival Inc", website_url="https://rival.example.com", is_active=True, **kwargs
):
    if party is None:
        party = _opportunitypipeline_party(tenant, name=name, kind="organization")
    return CompetitorProfile.objects.create(
        tenant=tenant,
        party=party,
        website_url=website_url,
        is_active=is_active,
        **kwargs,
    )


def _opportunitypipeline_opportunity_competitor(
    tenant, opportunity, competitor_profile, relationship="evaluating", is_primary=False, **kwargs
):
    return OpportunityCompetitor.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        competitor_profile=competitor_profile,
        relationship=relationship,
        is_primary=is_primary,
        **kwargs,
    )


def _opportunitypipeline_win_loss_reason(
    tenant, name="Price Match", code=None, result="both", category="price", sequence=1, is_active=True, **kwargs
):
    code = code or f"rsn_{int(timezone.now().timestamp() * 1000) % 100000}"
    return WinLossReason.objects.create(
        tenant=tenant,
        name=name,
        code=code,
        result=result,
        category=category,
        sequence=sequence,
        is_active=is_active,
        **kwargs,
    )


def _opportunitypipeline_outcome(
    tenant, opportunity, result="won", reason=None, competitor_link=None, recorded_by=None, **kwargs
):
    if reason is None:
        reason = _opportunitypipeline_win_loss_reason(tenant, result=result)
    return OpportunityOutcome.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        result=result,
        reason=reason,
        competitor_link=competitor_link,
        recorded_by=recorded_by,
        **kwargs,
    )


# ============================================================================
# 1. Pipeline (OpportunityPipeline) Tests
# ============================================================================

def test_opportunitypipeline_pipeline_defaults_autonumbering_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Direct Enterprise")

    assert pipe.name == "Direct Enterprise"
    assert pipe.description == ""
    assert pipe.is_default is False
    assert pipe.is_active is True
    assert pipe.number.startswith("PIPE-")
    assert str(pipe) == f"{pipe.number} · Direct Enterprise"

    # Second pipeline in same tenant increments number
    pipe2 = _opportunitypipeline_pipeline(tenant, name="Channel Pipeline")
    assert pipe2.number.startswith("PIPE-")
    assert pipe2.number != pipe.number


def test_opportunitypipeline_pipeline_is_default_and_unique_constraints(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    tenant_a = opportunitypipeline_tenant_a
    tenant_b = opportunitypipeline_tenant_b

    # Default pipeline must be active
    inactive_default = Pipeline(tenant=tenant_a, name="Inactive Default", is_default=True, is_active=False)
    with pytest.raises(ValidationError) as exc_info:
        inactive_default.clean()
    assert "is_default" in exc_info.value.message_dict

    # Active default pipeline succeeds
    pipe_default_a = _opportunitypipeline_pipeline(tenant_a, name="Acme Default", is_default=True, is_active=True)
    pipe_default_a.full_clean()

    # Second active default pipeline in same tenant is rejected by clean()
    second_default_a = Pipeline(tenant=tenant_a, name="Acme Second Default", is_default=True, is_active=True)
    second_default_a.save()
    with pytest.raises(ValidationError) as exc_info:
        second_default_a.clean()
    assert "is_default" in exc_info.value.message_dict

    # Another tenant can have its own active default pipeline
    pipe_default_b = _opportunitypipeline_pipeline(tenant_b, name="Globex Default", is_default=True, is_active=True)
    pipe_default_b.full_clean()
    assert pipe_default_b.is_default is True

    # Unique number per tenant constraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Pipeline.objects.create(tenant=tenant_a, number=pipe_default_a.number, name="Duplicate Number")


def test_opportunitypipeline_pipeline_deactivation_and_deletion_protection(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Protected Pipeline")
    open_stage = _opportunitypipeline_stage(tenant, pipeline, name="Prospecting", sequence=10, stage_kind="open", probability=20)
    opp = _opportunitypipeline_opportunity(tenant, title="Deal In Pipeline")
    placement = _opportunitypipeline_placement(tenant, opp, pipeline, open_stage)

    # Deactivating pipeline with open placements fails validation in clean() and save()
    pipeline.is_active = False
    with pytest.raises(ValidationError) as exc_info:
        pipeline.clean()
    assert "is_active" in exc_info.value.message_dict

    with pytest.raises(ValidationError) as exc_info:
        pipeline.save()
    assert "is_active" in exc_info.value.message_dict

    # Deleting pipeline with placements fails validation in delete()
    with pytest.raises(ValidationError) as exc_info:
        pipeline.delete()
    assert "cannot be deleted" in str(exc_info.value)

    # Deleting an unreferenced pipeline succeeds
    empty_pipeline = _opportunitypipeline_pipeline(tenant, name="Empty Pipeline")
    empty_pipeline_id = empty_pipeline.pk
    empty_pipeline.delete()
    assert not Pipeline.objects.filter(pk=empty_pipeline_id).exists()


# ============================================================================
# 2. PipelineStage Tests
# ============================================================================

def test_opportunitypipeline_stage_defaults_ordering_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Sales Cycle")

    stage = _opportunitypipeline_stage(
        tenant,
        pipeline,
        name="Qualification",
        code="qual",
        sequence=20,
        stage_kind="open",
        crm_stage_key="qualification",
        probability=30,
    )

    assert stage.name == "Qualification"
    assert stage.code == "qual"
    assert stage.sequence == 20
    assert stage.stage_kind == "open"
    assert stage.crm_stage_key == "qualification"
    assert stage.probability == 30
    assert stage.forecast_category == "pipeline"
    assert stage.target_days is None
    assert stage.entry_guidance == ""
    assert stage.exit_guidance == ""
    assert stage.entry_criteria == []
    assert stage.exit_criteria == []
    assert stage.is_active is True
    assert str(stage) == f"{pipeline} · Qualification"

    # Stage sequence ordering
    stage_first = _opportunitypipeline_stage(
        tenant,
        pipeline,
        name="Initial Contact",
        code="init",
        sequence=5,
        stage_kind="open",
        crm_stage_key="prospecting",
        probability=10,
    )
    stages = list(pipeline.stages.all())
    assert stages[0] == stage_first
    assert stages[1] == stage


def test_opportunitypipeline_stage_choices_and_kind_integrity(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Integrity Pipeline")

    # Valid Won stage
    won_stage = _opportunitypipeline_stage(
        tenant,
        pipeline,
        name="Closed Won",
        code="won",
        sequence=90,
        stage_kind="won",
        crm_stage_key="closed_won",
        probability=100,
        forecast_category="closed",
    )
    won_stage.full_clean()

    # Invalid Won stage (e.g. probability not 100)
    won_stage.probability = 95
    with pytest.raises(ValidationError):
        won_stage.clean()

    # Valid Lost stage
    lost_stage = _opportunitypipeline_stage(
        tenant,
        pipeline,
        name="Closed Lost",
        code="lost",
        sequence=100,
        stage_kind="lost",
        crm_stage_key="closed_lost",
        probability=0,
        forecast_category="closed",
    )
    lost_stage.full_clean()

    # Invalid Lost stage (e.g. crm_stage_key not closed_lost)
    lost_stage.crm_stage_key = "prospecting"
    with pytest.raises(ValidationError):
        lost_stage.clean()

    # Invalid Open stage (e.g. probability 0 or 100)
    open_stage = PipelineStage(
        tenant=tenant,
        pipeline=pipeline,
        name="Bad Open",
        code="bad_open",
        sequence=15,
        stage_kind="open",
        crm_stage_key="prospecting",
        probability=100,
        forecast_category="pipeline",
    )
    with pytest.raises(ValidationError):
        open_stage.clean()


def test_opportunitypipeline_stage_criteria_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Criteria Pipeline")

    valid_criteria = [
        {"key": "account", "label": "Account is linked"},
        {"key": "primary_contact", "label": "Primary contact is linked"},
    ]
    normalized = _validate_pipeline_criteria(valid_criteria)
    assert len(normalized) == 2
    assert normalized[0]["key"] == "account"

    # Non-list criteria raises ValidationError
    with pytest.raises(ValidationError) as exc:
        _validate_pipeline_criteria({"key": "account", "label": "Bad"})
    assert "Criteria must be a list." in str(exc.value)

    # Invalid key raises ValidationError
    with pytest.raises(ValidationError) as exc:
        _validate_pipeline_criteria([{"key": "unknown_key", "label": "Test"}])
    assert "Choose a supported stage criterion." in str(exc.value)

    # Duplicate key raises ValidationError
    with pytest.raises(ValidationError) as exc:
        _validate_pipeline_criteria([
            {"key": "amount", "label": "Amount"},
            {"key": "amount", "label": "Amount duplicate"},
        ])
    assert "Stage criteria must be unique." in str(exc.value)

    # More than 20 criteria raises ValidationError
    too_many = [{"key": k, "label": lbl} for k, lbl in PIPELINE_CRITERION_CHOICES] * 3
    with pytest.raises(ValidationError) as exc:
        _validate_pipeline_criteria(too_many[:25])
    assert "A stage may contain at most 20 criteria." in str(exc.value)


def test_opportunitypipeline_stage_constraints_uniqueness_and_ranges(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Constraints Pipeline")

    stage1 = _opportunitypipeline_stage(
        tenant, pipeline, name="Stage 1", code="stage1", sequence=10, stage_kind="open", probability=20
    )

    # Duplicate code in same pipeline raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PipelineStage.objects.create(
                tenant=tenant,
                pipeline=pipeline,
                name="Stage 1 Dupe Code",
                code="stage1",
                sequence=11,
                stage_kind="open",
                crm_stage_key="prospecting",
                probability=20,
            )

    # Duplicate sequence in same pipeline raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PipelineStage.objects.create(
                tenant=tenant,
                pipeline=pipeline,
                name="Stage 1 Dupe Seq",
                code="stage_other",
                sequence=10,
                stage_kind="open",
                crm_stage_key="prospecting",
                probability=20,
            )

    # Sequence >= 1 CheckConstraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PipelineStage.objects.create(
                tenant=tenant,
                pipeline=pipeline,
                name="Zero Seq",
                code="zero_seq",
                sequence=0,
                stage_kind="open",
                crm_stage_key="prospecting",
                probability=20,
            )

    # Code lowercased on save
    upper_stage = _opportunitypipeline_stage(
        tenant, pipeline, name="Upper Stage", code="UPPER_CODE", sequence=30, stage_kind="open", probability=30
    )
    upper_stage.refresh_from_db()
    assert upper_stage.code == "upper_code"


def test_opportunitypipeline_stage_locked_fields_and_deletion_protection(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Lock Pipeline")
    stage = _opportunitypipeline_stage(
        tenant, pipeline, name="Locked Stage", code="locked_stg", sequence=10, stage_kind="open", probability=25
    )
    opp = _opportunitypipeline_opportunity(tenant, title="Lock Deal")
    _opportunitypipeline_placement(tenant, opp, pipeline, stage)

    # Locked configuration field change raises ValidationError
    stage.probability = 40
    with pytest.raises(ValidationError) as exc_info:
        stage.clean()
    assert "probability" in exc_info.value.message_dict

    with pytest.raises(ValidationError) as exc_info:
        stage.save()
    assert "probability" in exc_info.value.message_dict

    # Revert probability and change non-locked field (name) succeeds
    stage.probability = 25
    stage.name = "Locked Stage Renamed"
    stage.save()
    stage.refresh_from_db()
    assert stage.name == "Locked Stage Renamed"

    # Deleting stage used by placement raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        stage.delete()
    assert "cannot be deleted" in str(exc_info.value)


# ============================================================================
# 3. OpportunityPipelinePlacement Tests
# ============================================================================

def test_opportunitypipeline_placement_defaults_autonow_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Placement Pipeline")
    stage = _opportunitypipeline_stage(tenant, pipeline, name="Entry Stage", sequence=10, stage_kind="open", probability=15)
    opp = _opportunitypipeline_opportunity(tenant, title="Deal Placement 1")

    placement = _opportunitypipeline_placement(tenant, opp, pipeline, stage)
    assert placement.stage_entered_at is not None
    assert placement.probability_override is None
    assert str(placement) == f"{opp} · {stage}"

    # OneToOneField: cannot place same opportunity twice
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OpportunityPipelinePlacement.objects.create(
                tenant=tenant,
                opportunity=opp,
                pipeline=pipeline,
                current_stage=stage,
            )


def test_opportunitypipeline_placement_effective_probability_and_overrides(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Prob Pipeline")
    open_stage = _opportunitypipeline_stage(tenant, pipeline, name="Open Stg", sequence=10, stage_kind="open", probability=25)
    won_stage = _opportunitypipeline_stage(tenant, pipeline, name="Won Stg", sequence=90, stage_kind="won", probability=100, crm_stage_key="closed_won", forecast_category="closed")
    lost_stage = _opportunitypipeline_stage(tenant, pipeline, name="Lost Stg", sequence=100, stage_kind="lost", probability=0, crm_stage_key="closed_lost", forecast_category="closed")

    opp1 = _opportunitypipeline_opportunity(tenant, title="Deal Prob 1")
    placement1 = _opportunitypipeline_placement(tenant, opp1, pipeline, open_stage)
    assert placement1.effective_probability == 25

    placement1.probability_override = 60
    assert placement1.effective_probability == 60
    placement1.full_clean()
    placement1.save()

    # Out of bounds override (< 0 or > 100)
    placement1.probability_override = 150
    with pytest.raises(ValidationError):
        placement1.clean()

    # Won stage requires override 100
    opp_won = _opportunitypipeline_opportunity(tenant, title="Deal Won")
    placement_won = OpportunityPipelinePlacement(
        tenant=tenant, opportunity=opp_won, pipeline=pipeline, current_stage=won_stage, probability_override=80
    )
    with pytest.raises(ValidationError) as exc:
        placement_won.clean()
    assert "probability_override" in exc.value.message_dict

    # Lost stage requires override 0
    opp_lost = _opportunitypipeline_opportunity(tenant, title="Deal Lost")
    placement_lost = OpportunityPipelinePlacement(
        tenant=tenant, opportunity=opp_lost, pipeline=pipeline, current_stage=lost_stage, probability_override=50
    )
    with pytest.raises(ValidationError) as exc:
        placement_lost.clean()
    assert "probability_override" in exc.value.message_dict


def test_opportunitypipeline_placement_stage_and_pipeline_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline_a = _opportunitypipeline_pipeline(tenant, name="Pipeline A")
    pipeline_b = _opportunitypipeline_pipeline(tenant, name="Pipeline B")
    stage_a = _opportunitypipeline_stage(tenant, pipeline_a, name="Stage of A", sequence=10, stage_kind="open", probability=20)
    stage_b = _opportunitypipeline_stage(tenant, pipeline_b, name="Stage of B", sequence=10, stage_kind="open", probability=20)

    opp = _opportunitypipeline_opportunity(tenant, title="Deal Mismatch")

    # Stage belongs to pipeline_b but placement pipeline is pipeline_a
    mismatched = OpportunityPipelinePlacement(
        tenant=tenant, opportunity=opp, pipeline=pipeline_a, current_stage=stage_b
    )
    with pytest.raises(ValidationError) as exc_info:
        mismatched.clean()
    assert "current_stage" in exc_info.value.message_dict

    # Inactive stage rejected
    stage_a.is_active = False
    stage_a.save()
    inactive_placement = OpportunityPipelinePlacement(
        tenant=tenant, opportunity=opp, pipeline=pipeline_a, current_stage=stage_a
    )
    with pytest.raises(ValidationError) as exc_info:
        inactive_placement.clean()
    assert "current_stage" in exc_info.value.message_dict


# ============================================================================
# 4. OpportunityTeamMember Tests
# ============================================================================

def test_opportunitypipeline_team_member_defaults_roles_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, title="Team Deal")
    user = _opportunitypipeline_user(tenant, email="rep@example.com")

    member = _opportunitypipeline_team_member(tenant, opp, user, role="solution_consultant")
    assert member.role == "solution_consultant"
    assert member.responsibility == ""
    assert member.is_active is True
    assert member.number.startswith("OTM-")
    assert str(member) == f"{member.number} · {opp} · {user} (Solution Consultant)"

    # Inactive user cannot be added as new team member
    inactive_user = _opportunitypipeline_user(tenant, email="inactive@example.com", is_active=False)
    new_member = OpportunityTeamMember(
        tenant=tenant, opportunity=opp, user=inactive_user, role="observer"
    )
    with pytest.raises(ValidationError) as exc_info:
        new_member.clean()
    assert "user" in exc_info.value.message_dict


def test_opportunitypipeline_team_member_uniqueness_and_roles(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, title="Uniq Team Deal")
    user = _opportunitypipeline_user(tenant, email="uniqrep@example.com")

    _opportunitypipeline_team_member(tenant, opp, user, role="collaborator")

    # Duplicate role for same user and opportunity raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OpportunityTeamMember.objects.create(
                tenant=tenant,
                opportunity=opp,
                user=user,
                role="collaborator",
            )

    # Different role for same user and opportunity is allowed
    member2 = _opportunitypipeline_team_member(tenant, opp, user, role="executive_sponsor")
    assert member2.pk is not None


# ============================================================================
# 5. CompetitorProfile Tests
# ============================================================================

def test_opportunitypipeline_competitor_profile_defaults_fields_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    party = _opportunitypipeline_party(tenant, name="Megacorp Rival", kind="organization")

    profile = _opportunitypipeline_competitor_profile(
        tenant,
        party=party,
        website_url="https://megacorp.example.com",
        market_positioning="Legacy market leader",
        strengths="Broad product line",
        weaknesses="Slow innovation, high cost",
    )

    assert profile.number.startswith("CMP-")
    assert profile.website_url == "https://megacorp.example.com"
    assert profile.market_positioning == "Legacy market leader"
    assert profile.strengths == "Broad product line"
    assert profile.weaknesses == "Slow innovation, high cost"
    assert profile.is_active is True
    assert str(profile) == f"{profile.number} · {party}"

    # OneToOneField on party prevents second profile for same party
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CompetitorProfile.objects.create(tenant=tenant, party=party, website_url="https://other.com")


def test_opportunitypipeline_competitor_profile_party_validation_and_deletion(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    person_party = _opportunitypipeline_party(tenant, name="John Doe", kind="person")

    # Party must be organization kind
    profile = CompetitorProfile(tenant=tenant, party=person_party)
    with pytest.raises(ValidationError) as exc_info:
        profile.clean()
    assert "party" in exc_info.value.message_dict

    # Deleting profile referenced by OpportunityCompetitor fails
    org_party = _opportunitypipeline_party(tenant, name="Acme Rival", kind="organization")
    competitor = _opportunitypipeline_competitor_profile(tenant, party=org_party)
    opp = _opportunitypipeline_opportunity(tenant, title="Competitor Deal")
    _opportunitypipeline_opportunity_competitor(tenant, opp, competitor, relationship="evaluating")

    with pytest.raises(ValidationError) as exc_info:
        competitor.delete()
    assert "cannot be deleted" in str(exc_info.value)


# ============================================================================
# 6. OpportunityCompetitor Tests
# ============================================================================

def test_opportunitypipeline_opportunity_competitor_defaults_relationships_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, title="Opp Comp Deal")
    profile = _opportunitypipeline_competitor_profile(tenant, name="Competitor Alpha")

    link = _opportunitypipeline_opportunity_competitor(
        tenant, opp, profile, relationship="shortlisted", is_primary=True, deal_notes="Evaluating pricing"
    )

    assert link.relationship == "shortlisted"
    assert link.is_primary is True
    assert link.deal_notes == "Evaluating pricing"
    assert str(link) == f"{opp} · {profile} · Shortlisted"

    # Unique constraint on (tenant, opportunity, competitor_profile)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OpportunityCompetitor.objects.create(
                tenant=tenant,
                opportunity=opp,
                competitor_profile=profile,
                relationship="incumbent",
            )


# ============================================================================
# 7. WinLossReason Tests
# ============================================================================

def test_opportunitypipeline_win_loss_reason_defaults_choices_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    reason = _opportunitypipeline_win_loss_reason(
        tenant, name="Pricing Was Too High", code="PRICE_HIGH", result="lost", category="price", sequence=5
    )

    assert reason.number.startswith("WLR-")
    assert reason.code == "price_high"  # auto lowercased
    assert reason.result == "lost"
    assert reason.category == "price"
    assert reason.sequence == 5
    assert reason.is_active is True
    assert str(reason) == f"{reason.number} · Pricing Was Too High"

    # Unique code per tenant
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            WinLossReason.objects.create(
                tenant=tenant,
                name="Duplicate Code Reason",
                code="price_high",
                result="lost",
            )


def test_opportunitypipeline_win_loss_reason_deletion_protection(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    reason = _opportunitypipeline_win_loss_reason(tenant, name="Critical Feature", result="won")
    opp = _opportunitypipeline_opportunity(tenant, title="Outcome Deal")
    _opportunitypipeline_outcome(tenant, opp, result="won", reason=reason)

    with pytest.raises(ValidationError) as exc_info:
        reason.delete()
    assert "cannot be deleted" in str(exc_info.value)


# ============================================================================
# 8. OpportunityOutcome Tests
# ============================================================================

def test_opportunitypipeline_opportunity_outcome_defaults_fields_and_str(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, title="Outcome Winner")
    user = _opportunitypipeline_user(tenant, email="closer@example.com")
    reason = _opportunitypipeline_win_loss_reason(tenant, name="Superior Performance", result="won")

    outcome = _opportunitypipeline_outcome(
        tenant, opp, result="won", reason=reason, recorded_by=user, notes="Customer signed multi-year"
    )

    assert outcome.number.startswith("OUT-")
    assert outcome.result == "won"
    assert outcome.reason == reason
    assert outcome.recorded_by == user
    assert outcome.notes == "Customer signed multi-year"
    assert outcome.closed_at is not None
    assert str(outcome) == f"{outcome.number} · {opp} · Won"


def test_opportunitypipeline_opportunity_outcome_reason_and_competitor_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, title="Outcome Validate Deal")
    lost_reason = _opportunitypipeline_win_loss_reason(tenant, name="Too Expensive", result="lost")
    won_reason = _opportunitypipeline_win_loss_reason(tenant, name="Best Solution", result="won")

    # Incompatible reason: won outcome with lost reason raises ValidationError
    bad_outcome = OpportunityOutcome(
        tenant=tenant, opportunity=opp, result="won", reason=lost_reason
    )
    with pytest.raises(ValidationError) as exc_info:
        bad_outcome.clean()
    assert "reason" in exc_info.value.message_dict

    # Competitor relationship lost_to requires lost outcome
    competitor = _opportunitypipeline_competitor_profile(tenant, name="Rival Beta")
    comp_link = _opportunitypipeline_opportunity_competitor(
        tenant, opp, competitor, relationship="lost_to"
    )

    bad_won_comp = OpportunityOutcome(
        tenant=tenant, opportunity=opp, result="won", reason=won_reason, competitor_link=comp_link
    )
    with pytest.raises(ValidationError) as exc_info:
        bad_won_comp.clean()
    assert "competitor_link" in exc_info.value.message_dict


def test_opportunitypipeline_opportunity_outcome_append_only_immutability(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, title="Immutable Deal")
    reason = _opportunitypipeline_win_loss_reason(tenant, name="Standard Win", result="won")
    outcome = _opportunitypipeline_outcome(tenant, opp, result="won", reason=reason)

    # Trying to modify and save an existing outcome raises ValidationError
    outcome.notes = "Attempting modification"
    with pytest.raises(ValidationError) as exc_info:
        outcome.save()
    assert "append-only" in str(exc_info.value)

    # Trying to delete an existing outcome raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        outcome.delete()
    assert "cannot be deleted" in str(exc_info.value)


# ============================================================================
# 9. Cross-Tenant Isolation Across All 8 Models
# ============================================================================

def test_opportunitypipeline_cross_tenant_isolation_all_eight_models(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    tenant_a = opportunitypipeline_tenant_a
    tenant_b = opportunitypipeline_tenant_b

    # 1. Pipeline
    pipe_a = _opportunitypipeline_pipeline(tenant_a, name="Pipeline A")
    pipe_b = _opportunitypipeline_pipeline(tenant_b, name="Pipeline B")
    assert list(Pipeline.objects.filter(tenant=tenant_a)) == [pipe_a]
    assert list(Pipeline.objects.filter(tenant=tenant_b)) == [pipe_b]

    # 2. PipelineStage
    stage_a = _opportunitypipeline_stage(tenant_a, pipe_a, name="Stage A", sequence=10, stage_kind="open", probability=10)
    stage_b = _opportunitypipeline_stage(tenant_b, pipe_b, name="Stage B", sequence=10, stage_kind="open", probability=10)
    assert list(PipelineStage.objects.filter(tenant=tenant_a)) == [stage_a]
    assert list(PipelineStage.objects.filter(tenant=tenant_b)) == [stage_b]

    # Cross-tenant stage clean raises ValidationError
    cross_stage = PipelineStage(
        tenant=tenant_a, pipeline=pipe_b, name="Cross Stage", code="cr_stg", sequence=20, stage_kind="open", probability=20, crm_stage_key="prospecting", forecast_category="pipeline"
    )
    with pytest.raises(ValidationError) as exc:
        cross_stage.clean()
    assert "pipeline" in exc.value.message_dict

    # 3. OpportunityPipelinePlacement
    opp_a = _opportunitypipeline_opportunity(tenant_a, title="Opp A")
    opp_b = _opportunitypipeline_opportunity(tenant_b, title="Opp B")
    place_a = _opportunitypipeline_placement(tenant_a, opp_a, pipe_a, stage_a)
    place_b = _opportunitypipeline_placement(tenant_b, opp_b, pipe_b, stage_b)
    assert list(OpportunityPipelinePlacement.objects.filter(tenant=tenant_a)) == [place_a]
    assert list(OpportunityPipelinePlacement.objects.filter(tenant=tenant_b)) == [place_b]

    # Cross-tenant placement clean raises ValidationError
    cross_placement = OpportunityPipelinePlacement(
        tenant=tenant_a, opportunity=opp_b, pipeline=pipe_a, current_stage=stage_a
    )
    with pytest.raises(ValidationError) as exc:
        cross_placement.clean()
    assert "opportunity" in exc.value.message_dict

    # 4. OpportunityTeamMember
    user_a = _opportunitypipeline_user(tenant_a, email="team_a@example.com")
    user_b = _opportunitypipeline_user(tenant_b, email="team_b@example.com")
    member_a = _opportunitypipeline_team_member(tenant_a, opp_a, user_a, role="collaborator")
    member_b = _opportunitypipeline_team_member(tenant_b, opp_b, user_b, role="collaborator")
    assert list(OpportunityTeamMember.objects.filter(tenant=tenant_a)) == [member_a]
    assert list(OpportunityTeamMember.objects.filter(tenant=tenant_b)) == [member_b]

    # Cross-tenant member clean raises ValidationError
    cross_member = OpportunityTeamMember(
        tenant=tenant_a, opportunity=opp_a, user=user_b, role="collaborator"
    )
    with pytest.raises(ValidationError) as exc:
        cross_member.clean()
    assert "user" in exc.value.message_dict

    # 5. CompetitorProfile
    comp_a = _opportunitypipeline_competitor_profile(tenant_a, name="Comp A")
    comp_b = _opportunitypipeline_competitor_profile(tenant_b, name="Comp B")
    assert list(CompetitorProfile.objects.filter(tenant=tenant_a)) == [comp_a]
    assert list(CompetitorProfile.objects.filter(tenant=tenant_b)) == [comp_b]

    # Cross-tenant competitor profile clean raises ValidationError
    party_b = _opportunitypipeline_party(tenant_b, name="Party B Org", kind="organization")
    cross_comp = CompetitorProfile(tenant=tenant_a, party=party_b)
    with pytest.raises(ValidationError) as exc:
        cross_comp.clean()
    assert "party" in exc.value.message_dict

    # 6. OpportunityCompetitor
    oc_a = _opportunitypipeline_opportunity_competitor(tenant_a, opp_a, comp_a)
    oc_b = _opportunitypipeline_opportunity_competitor(tenant_b, opp_b, comp_b)
    assert list(OpportunityCompetitor.objects.filter(tenant=tenant_a)) == [oc_a]
    assert list(OpportunityCompetitor.objects.filter(tenant=tenant_b)) == [oc_b]

    # Cross-tenant opportunity competitor clean raises ValidationError
    cross_oc = OpportunityCompetitor(tenant=tenant_a, opportunity=opp_a, competitor_profile=comp_b, relationship="identified")
    with pytest.raises(ValidationError) as exc:
        cross_oc.clean()
    assert "competitor_profile" in exc.value.message_dict

    # 7. WinLossReason
    rsn_a = _opportunitypipeline_win_loss_reason(tenant_a, name="Reason A", result="won")
    rsn_b = _opportunitypipeline_win_loss_reason(tenant_b, name="Reason B", result="won")
    assert list(WinLossReason.objects.filter(tenant=tenant_a)) == [rsn_a]
    assert list(WinLossReason.objects.filter(tenant=tenant_b)) == [rsn_b]

    # 8. OpportunityOutcome
    out_a = _opportunitypipeline_outcome(tenant_a, opp_a, result="won", reason=rsn_a)
    out_b = _opportunitypipeline_outcome(tenant_b, opp_b, result="won", reason=rsn_b)
    assert list(OpportunityOutcome.objects.filter(tenant=tenant_a)) == [out_a]
    assert list(OpportunityOutcome.objects.filter(tenant=tenant_b)) == [out_b]

    # Cross-tenant outcome clean raises ValidationError
    cross_out = OpportunityOutcome(
        tenant=tenant_a, opportunity=opp_a, result="won", reason=rsn_b
    )
    with pytest.raises(ValidationError) as exc:
        cross_out.clean()
    assert "reason" in exc.value.message_dict


# ============================================================================
# 10. Conftest Fixtures and Contract Constants Alignment
# ============================================================================

def test_opportunitypipeline_conftest_fixtures_and_contract_constants(
    opportunitypipeline_tenant_a,
    opportunitypipeline_tenant_b,
    opportunitypipeline_admin_a,
    opportunitypipeline_user_a,
):
    assert opportunitypipeline_tenant_a is not None
    assert opportunitypipeline_tenant_b is not None
    assert opportunitypipeline_admin_a.is_tenant_admin is True
    assert opportunitypipeline_user_a.is_tenant_admin is False

    # Check that contract constants are present and structured
    assert "OpportunityPipeline" in OPPORTUNITYPIPELINE_MODEL_FIELDS
    assert "PipelineStage" in OPPORTUNITYPIPELINE_MODEL_FIELDS
    assert "OpportunityPipelinePlacement" in OPPORTUNITYPIPELINE_MODEL_FIELDS
    assert "OpportunityTeamMember" in OPPORTUNITYPIPELINE_MODEL_FIELDS
    assert "CompetitorProfile" in OPPORTUNITYPIPELINE_MODEL_FIELDS
    assert "OpportunityCompetitor" in OPPORTUNITYPIPELINE_MODEL_FIELDS
    assert "WinLossReason" in OPPORTUNITYPIPELINE_MODEL_FIELDS
    assert "OpportunityOutcome" in OPPORTUNITYPIPELINE_MODEL_FIELDS

    # Verify choices constants
    assert "PipelineStage" in OPPORTUNITYPIPELINE_CHOICES
    assert "OpportunityTeamMember" in OPPORTUNITYPIPELINE_CHOICES
    assert "WinLossReason" in OPPORTUNITYPIPELINE_CHOICES
    assert "OpportunityOutcome" in OPPORTUNITYPIPELINE_CHOICES


# ============================================================================
# 11. Edge Cases, Null FK String Representations, and Boundary Validations
# ============================================================================

def test_opportunitypipeline_string_representations_with_null_relations(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a

    # PipelineStage criteria edge cases
    with pytest.raises(ValidationError) as exc:
        _validate_pipeline_criteria([{"key": "account"}])  # missing label
    assert "Each criterion must contain only key and label." in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        _validate_pipeline_criteria([{"key": "account", "label": ""}])  # empty label
    assert "Criterion labels must be 1 to 120 characters." in str(exc.value)

    # OpportunityTeamMember __str__ without opportunity and user
    member = OpportunityTeamMember(tenant=tenant, role="observer")
    member_str = str(member)
    assert member_str == "— · — · —"

    user = _opportunitypipeline_user(tenant, email="obs@example.com")
    member_with_user = OpportunityTeamMember(tenant=tenant, user=user, role="observer")
    assert "Observer" in str(member_with_user)

    # Clean without tenant_id returns early safely
    member_no_tenant = OpportunityTeamMember(role="observer")
    member_no_tenant.clean()

    # CompetitorProfile __str__ without party
    comp = CompetitorProfile(tenant=tenant)
    assert str(comp) == "— · —"

    # Clean without tenant_id returns early safely
    comp_no_tenant = CompetitorProfile()
    comp_no_tenant.clean()

    # OpportunityCompetitor __str__ without opportunity and profile
    opp_comp = OpportunityCompetitor(tenant=tenant, relationship="identified")
    assert str(opp_comp) == "— · — · Identified"

    # Clean without tenant_id returns early safely
    opp_comp_no_tenant = OpportunityCompetitor(relationship="identified")
    opp_comp_no_tenant.clean()

    # WinLossReason clean without code
    reason = WinLossReason(tenant=tenant, name="No Code")
    reason.clean()
    assert reason.code == ""

    # OpportunityOutcome __str__ without opportunity
    outcome = OpportunityOutcome(tenant=tenant, result="won")
    assert "Won" in str(outcome)

    # Clean without tenant_id returns early safely
    outcome_no_tenant = OpportunityOutcome(result="won")
    outcome_no_tenant.clean()


def test_opportunitypipeline_additional_placement_and_outcome_validations(
    opportunitypipeline_tenant_a, opportunitypipeline_tenant_b
):
    tenant_a = opportunitypipeline_tenant_a
    tenant_b = opportunitypipeline_tenant_b

    # Placement cross-tenant pipeline validation
    pipe_b = _opportunitypipeline_pipeline(tenant_b, name="Pipe B")
    pipe_a = _opportunitypipeline_pipeline(tenant_a, name="Pipe A")
    stage_a = _opportunitypipeline_stage(tenant_a, pipe_a, name="Stage A")
    opp_a = _opportunitypipeline_opportunity(tenant_a, name="Opp Cross Check")

    cross_pipe_placement = OpportunityPipelinePlacement(
        tenant=tenant_a, opportunity=opp_a, pipeline=pipe_b, current_stage=stage_a
    )
    with pytest.raises(ValidationError) as exc:
        cross_pipe_placement.clean()
    assert "pipeline" in exc.value.message_dict

    # Placement cross-tenant stage validation
    stage_b = _opportunitypipeline_stage(tenant_b, pipe_b, name="Stage B")
    cross_stage_placement = OpportunityPipelinePlacement(
        tenant=tenant_a, opportunity=opp_a, pipeline=pipe_a, current_stage=stage_b
    )
    with pytest.raises(ValidationError) as exc:
        cross_stage_placement.clean()
    assert "current_stage" in exc.value.message_dict

    # Outcome with competitor_link belonging to a different opportunity
    opp_other = _opportunitypipeline_opportunity(tenant_a, name="Opp Other Deal")
    comp_prof = _opportunitypipeline_competitor_profile(tenant_a, name="Rival Gamma")
    link_other = _opportunitypipeline_opportunity_competitor(tenant_a, opp_other, comp_prof, relationship="evaluating")
    reason_won = _opportunitypipeline_win_loss_reason(tenant_a, name="Win Reason", result="won")

    mismatched_outcome = OpportunityOutcome(
        tenant=tenant_a,
        opportunity=opp_a,
        result="won",
        reason=reason_won,
        competitor_link=link_other,
    )
    with pytest.raises(ValidationError) as exc:
        mismatched_outcome.clean()
    assert "competitor_link" in exc.value.message_dict
