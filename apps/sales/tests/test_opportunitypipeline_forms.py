import pytest
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OrgUnit, Party, Tenant
from apps.crm.models import Opportunity
from apps.sales import forms as sales_forms
from apps.sales.forms.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfileForm,
    OpportunityCompetitorForm,
)
from apps.sales.forms.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityTransitionForm,
    WinLossReasonForm,
)
from apps.sales.forms.OpportunityPipeline.Pipelines import (
    OpportunityPipelinePlacementForm,
    PipelineForm,
    PipelineStageForm,
    PipelineStageOrderForm,
    _opportunity_pipeline_positive_id,
)
from apps.sales.forms.OpportunityTeams.OpportunityTeams import OpportunityTeamMemberForm
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
)
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember

# Alias OpportunityPipelineForm to PipelineForm per sub-module contract
OpportunityPipelineForm = getattr(sales_forms, "OpportunityPipelineForm", PipelineForm)
sales_forms.OpportunityPipelineForm = OpportunityPipelineForm

pytestmark = pytest.mark.django_db


# ============================================================================
# Module Helpers (_opportunitypipeline_*)
# ============================================================================

def _opportunitypipeline_tenant(name="Acme Corp", slug=None):
    slug = slug or f"tenant-{int(timezone.now().timestamp() * 1000) % 1000000}-{timezone.now().microsecond}"
    return Tenant.objects.create(name=name, slug=slug)


def _opportunitypipeline_user(tenant, email=None, *, is_admin=False, is_active=True):
    email = email or f"user_{int(timezone.now().timestamp() * 1000) % 1000000}_{timezone.now().microsecond}@example.com"
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
    name = name or f"Party_{int(timezone.now().timestamp() * 1000) % 1000000}_{timezone.now().microsecond}"
    return Party.objects.create(tenant=tenant, name=name, kind=kind)


def _opportunitypipeline_org_unit(tenant, name=None):
    name = name or f"OrgUnit_{int(timezone.now().timestamp() * 1000) % 1000000}_{timezone.now().microsecond}"
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _opportunitypipeline_opportunity(
    tenant, name=None, owner=None, stage="prospecting", amount=Decimal("15000.00"), **kwargs
):
    name = name or kwargs.pop("title", None) or f"Deal_{int(timezone.now().timestamp() * 1000) % 1000000}_{timezone.now().microsecond}"
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
    code = code or f"stg_{sequence}_{int(timezone.now().timestamp() * 1000) % 100000}_{timezone.now().microsecond}"
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
    code = code or f"rsn_{int(timezone.now().timestamp() * 1000) % 100000}_{timezone.now().microsecond}"
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


# ----------------------------------------------------------------------------
# Payload generators
# ----------------------------------------------------------------------------

def _opportunitypipeline_pipeline_payload(name="Direct Sales", **overrides):
    payload = {
        "name": name,
        "description": "Standard direct sales pipeline.",
        "is_default": False,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_stage_payload(pipeline, name="Stage 1", code="stg1", sequence=10, **overrides):
    payload = {
        "pipeline": str(pipeline.pk) if hasattr(pipeline, "pk") else str(pipeline),
        "name": name,
        "code": code,
        "sequence": sequence,
        "stage_kind": "open",
        "crm_stage_key": "prospecting",
        "probability": 20,
        "forecast_category": "pipeline",
        "entry_guidance": "Verify company fit.",
        "exit_guidance": "Schedule follow up.",
        "entry_criteria": [],
        "exit_criteria": [],
        "target_days": 14,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_placement_payload(opportunity, pipeline, current_stage, **overrides):
    payload = {
        "opportunity": str(opportunity.pk) if hasattr(opportunity, "pk") else str(opportunity),
        "pipeline": str(pipeline.pk) if hasattr(pipeline, "pk") else str(pipeline),
        "current_stage": str(current_stage.pk) if hasattr(current_stage, "pk") else str(current_stage),
        "probability_override": "",
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_team_member_payload(user, role="collaborator", org_unit=None, **overrides):
    payload = {
        "user": str(user.pk) if hasattr(user, "pk") else str(user),
        "org_unit": str(org_unit.pk) if (org_unit and hasattr(org_unit, "pk")) else "",
        "role": role,
        "responsibility": "Technical evaluation support.",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_competitor_profile_payload(party, **overrides):
    payload = {
        "party": str(party.pk) if hasattr(party, "pk") else str(party),
        "aliases": "Rival, Competitor Inc",
        "website_url": "https://competitor.example.com",
        "description": "Primary market competitor.",
        "market_positioning": "Leader in enterprise segment.",
        "strengths": "Brand recognition.",
        "weaknesses": "Higher pricing.",
        "differentiators": "Modular deployment.",
        "objection_handling": "Emphasize total cost of ownership.",
        "last_reviewed_on": "2026-01-15",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_opportunity_competitor_payload(competitor_profile, relationship="evaluating", **overrides):
    payload = {
        "competitor_profile": str(competitor_profile.pk) if hasattr(competitor_profile, "pk") else str(competitor_profile),
        "relationship": relationship,
        "is_primary": False,
        "pricing_notes": "Undercutting by 10%.",
        "deal_notes": "Incumbent renewal.",
        "positioning_notes": "Pitch agility and modern API.",
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_win_loss_reason_payload(code="comp_pricing", name="Competitor Pricing", **overrides):
    payload = {
        "code": code,
        "name": name,
        "description": "Lost deal due to competitor aggressive pricing.",
        "sequence": 10,
        "result": "lost",
        "category": "price",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _opportunitypipeline_transition_payload(target_stage, reason=None, competitor_link=None, notes="Transition test", **overrides):
    payload = {
        "target_stage": str(target_stage.pk) if (target_stage and hasattr(target_stage, "pk")) else "",
        "reason": str(reason.pk) if (reason and hasattr(reason, "pk")) else "",
        "competitor_link": str(competitor_link.pk) if (competitor_link and hasattr(competitor_link, "pk")) else "",
        "notes": notes,
    }
    payload.update(overrides)
    return payload


# ============================================================================
# 1. OpportunityPipelineForm (PipelineForm) Tests
# ============================================================================

def test_opportunitypipeline_pipeline_form_fields_exclusions_and_defaults(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    form = OpportunityPipelineForm(tenant=tenant)

    # Exposed fields
    expected_fields = ["name", "description", "is_default", "is_active"]
    assert list(form.fields.keys()) == expected_fields
    assert list(form._meta.fields) == expected_fields

    # Excluded fields
    excluded = {"tenant", "number", "id", "created_at", "updated_at", "code", "currency", "owner"}
    assert not excluded.intersection(form.fields.keys())

    # Name is required; others optional/boolean
    assert form.fields["name"].required is True
    assert form.fields["description"].required is False
    assert form.fields["is_default"].required is False
    assert form.fields["is_active"].required is False


def test_opportunitypipeline_pipeline_form_valid_submission_create_and_save(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    payload = _opportunitypipeline_pipeline_payload(
        name="Global Mid-Market Pipeline",
        description="Dedicated pipeline for mid-market.",
        is_default=False,
        is_active=True,
    )
    form = OpportunityPipelineForm(data=payload, tenant=tenant)
    assert form.is_valid(), form.errors
    pipeline = form.save()
    assert pipeline.pk is not None
    assert pipeline.tenant == tenant
    assert pipeline.name == "Global Mid-Market Pipeline"
    assert pipeline.description == "Standard direct sales pipeline." or "Dedicated pipeline for mid-market." in pipeline.description
    assert pipeline.number.startswith("PIPE-")
    assert pipeline.is_default is False
    assert pipeline.is_active is True


def test_opportunitypipeline_pipeline_form_is_default_and_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    # Create an initial default pipeline
    pipe1 = _opportunitypipeline_pipeline(tenant, name="Existing Default", is_default=True, is_active=True)
    pipe2 = _opportunitypipeline_pipeline(tenant, name="Second Pipe", is_default=False, is_active=True)

    # Attempting to edit pipe2 with is_default=True when pipe1 is default triggers validation error
    payload = _opportunitypipeline_pipeline_payload(name="Second Pipe", is_default=True, is_active=True)
    edit_form = OpportunityPipelineForm(data=payload, instance=pipe2, tenant=tenant)
    assert not edit_form.is_valid()
    assert "Only one active default pipeline is allowed." in str(edit_form.errors)

    # Default pipeline cannot be inactive
    pipe_inactive = Pipeline(tenant=tenant, name="Inactive Default", is_default=True, is_active=False)
    with pytest.raises(ValidationError) as exc:
        pipe_inactive.clean()
    assert "The default pipeline must be active." in str(exc.value)


def test_opportunitypipeline_pipeline_form_name_required_and_unexposed_fields(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    # Blank name fails
    form = OpportunityPipelineForm(data={"name": "", "description": "No name"}, tenant=tenant)
    assert not form.is_valid()
    assert "name" in form.errors

    # Unexposed fields injected into payload do not pollute cleaned_data
    forged_payload = _opportunitypipeline_pipeline_payload(
        name="Security Invariant Test",
        tenant=99999,
        number="FORGED-001",
        currency="EUR",
        code="FORGED_CODE",
    )
    form_forged = OpportunityPipelineForm(data=forged_payload, tenant=tenant)
    assert form_forged.is_valid(), form_forged.errors
    assert "tenant" not in form_forged.cleaned_data
    assert "number" not in form_forged.cleaned_data
    assert "currency" not in form_forged.cleaned_data
    assert "code" not in form_forged.cleaned_data


# ============================================================================
# 2. PipelineStageForm Tests
# ============================================================================

def test_opportunitypipeline_stage_form_fields_exclusions_and_widgets(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Widgets Pipe")
    form = PipelineStageForm(tenant=tenant, pipeline=pipeline)

    expected_fields = [
        "pipeline", "name", "code", "sequence", "stage_kind", "crm_stage_key",
        "probability", "forecast_category", "entry_guidance", "exit_guidance",
        "entry_criteria", "exit_criteria", "target_days", "is_active",
    ]
    assert list(form.fields.keys()) == expected_fields
    assert list(form._meta.fields) == expected_fields

    excluded = {"tenant", "id", "created_at", "updated_at"}
    assert not excluded.intersection(form.fields.keys())

    # Textarea widgets
    assert isinstance(form.fields["entry_guidance"].widget, forms.Textarea)
    assert isinstance(form.fields["exit_guidance"].widget, forms.Textarea)
    assert isinstance(form.fields["entry_criteria"].widget, forms.CheckboxSelectMultiple)
    assert isinstance(form.fields["exit_criteria"].widget, forms.CheckboxSelectMultiple)


def test_opportunitypipeline_stage_form_querysets_and_pipeline_scoping(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b
    pipe_a = _opportunitypipeline_pipeline(t_a, name="Pipeline A")
    pipe_b = _opportunitypipeline_pipeline(t_b, name="Pipeline B")

    # tenant=None produces empty pipeline queryset
    form_none = PipelineStageForm(tenant=None, pipeline=pipe_a)
    assert form_none.fields["pipeline"].queryset.count() == 0

    # tenant=t_a only includes pipe_a, excludes pipe_b
    form_a = PipelineStageForm(tenant=t_a, pipeline=pipe_a)
    assert pipe_a in form_a.fields["pipeline"].queryset
    assert pipe_b not in form_a.fields["pipeline"].queryset

    # Passing pipeline kwarg sets self.pipeline and instance.pipeline
    form_pipe = PipelineStageForm(tenant=t_a, pipeline=pipe_a)
    assert form_pipe.pipeline == pipe_a
    assert form_pipe.instance.pipeline == pipe_a
    assert form_pipe.instance.tenant == t_a


def test_opportunitypipeline_stage_form_open_stage_validation_and_bounds(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Sales Cycle")

    # Valid open stage
    payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Qualification",
        code="qual",
        sequence=10,
        stage_kind="open",
        crm_stage_key="qualification",
        probability=25,
        forecast_category="pipeline",
        target_days=10,
    )
    form = PipelineStageForm(data=payload, tenant=tenant, pipeline=pipeline)
    assert form.is_valid(), form.errors
    stage = form.save()
    assert stage.pk is not None
    assert stage.stage_kind == "open"
    assert stage.probability == 25
    assert stage.target_days == 10

    # Open stage with closed forecast category fails form validation
    bad_forecast_payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Invalid Forecast Open",
        code="bad_fc",
        stage_kind="open",
        crm_stage_key="qualification",
        probability=30,
        forecast_category="closed",
    )
    form_bad_fc = PipelineStageForm(data=bad_forecast_payload, tenant=tenant, pipeline=pipeline)
    assert not form_bad_fc.is_valid()
    assert "Open stages require an open CRM stage" in str(form_bad_fc.errors)

    # Open stage with 0 or 100 probability fails
    bad_prob_payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Zero Prob Open",
        code="zero_prob",
        stage_kind="open",
        crm_stage_key="qualification",
        probability=0,
        forecast_category="pipeline",
    )
    form_zero = PipelineStageForm(data=bad_prob_payload, tenant=tenant, pipeline=pipeline)
    assert not form_zero.is_valid()
    assert "Open stages require an open CRM stage, probability from 1 to 99" in str(form_zero.errors)

    # Probability bounds in form (< 0 or > 100)
    out_of_bounds_payload = _opportunitypipeline_stage_payload(pipeline, probability=101)
    form_oob = PipelineStageForm(data=out_of_bounds_payload, tenant=tenant, pipeline=pipeline)
    assert not form_oob.is_valid()
    assert "probability" in form_oob.errors

    # Sequence bounds (< 1)
    bad_seq_payload = _opportunitypipeline_stage_payload(pipeline, sequence=0)
    form_bad_seq = PipelineStageForm(data=bad_seq_payload, tenant=tenant, pipeline=pipeline)
    assert not form_bad_seq.is_valid()
    assert "sequence" in form_bad_seq.errors


def test_opportunitypipeline_stage_form_won_and_lost_stage_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Outcome Cycle")

    # Valid won stage
    won_payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Closed Won",
        code="won",
        sequence=90,
        stage_kind="won",
        crm_stage_key="closed_won",
        probability=100,
        forecast_category="closed",
    )
    form_won = PipelineStageForm(data=won_payload, tenant=tenant, pipeline=pipeline)
    assert form_won.is_valid(), form_won.errors
    won_stage = form_won.save()
    assert won_stage.stage_kind == "won"
    assert won_stage.probability == 100

    # Invalid won stage: not 100%
    bad_won_payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Bad Won",
        code="bad_won",
        sequence=91,
        stage_kind="won",
        crm_stage_key="closed_won",
        probability=95,
        forecast_category="closed",
    )
    form_bad_won = PipelineStageForm(data=bad_won_payload, tenant=tenant, pipeline=pipeline)
    assert not form_bad_won.is_valid()
    assert "Won stages require Closed Won, 100%, and Closed category." in str(form_bad_won.errors)

    # Valid lost stage
    lost_payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Closed Lost",
        code="lost",
        sequence=100,
        stage_kind="lost",
        crm_stage_key="closed_lost",
        probability=0,
        forecast_category="closed",
    )
    form_lost = PipelineStageForm(data=lost_payload, tenant=tenant, pipeline=pipeline)
    assert form_lost.is_valid(), form_lost.errors
    lost_stage = form_lost.save()
    assert lost_stage.stage_kind == "lost"
    assert lost_stage.probability == 0

    # Invalid lost stage: not 0%
    bad_lost_payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Bad Lost",
        code="bad_lost",
        sequence=101,
        stage_kind="lost",
        crm_stage_key="closed_lost",
        probability=5,
        forecast_category="closed",
    )
    form_bad_lost = PipelineStageForm(data=bad_lost_payload, tenant=tenant, pipeline=pipeline)
    assert not form_bad_lost.is_valid()
    assert "Lost stages require Closed Lost, 0%, and Closed category." in str(form_bad_lost.errors)


def test_opportunitypipeline_stage_form_criteria_normalization_and_initial(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Criteria Pipeline")

    # Initializing form with stage that already has entry and exit criteria
    existing_stage = _opportunitypipeline_stage(
        tenant,
        pipeline,
        name="Solutioning",
        sequence=30,
        entry_criteria=[{"key": "account", "label": "Account is linked"}],
        exit_criteria=[{"key": "amount", "label": "Amount is greater than zero"}],
    )

    edit_form = PipelineStageForm(instance=existing_stage, tenant=tenant, pipeline=pipeline)
    assert edit_form.fields["entry_criteria"].initial == ["account"]
    assert edit_form.fields["exit_criteria"].initial == ["amount"]

    # Submitting with selected criteria normalizes keys to key-label dictionaries
    payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Solutioning",
        code=existing_stage.code,
        sequence=30,
        entry_criteria=["account", "primary_contact"],
        exit_criteria=["amount", "close_date"],
    )
    bound_form = PipelineStageForm(data=payload, instance=existing_stage, tenant=tenant, pipeline=pipeline)
    assert bound_form.is_valid(), bound_form.errors
    assert bound_form.cleaned_data["entry_criteria"] == [
        {"key": "account", "label": "Account is linked"},
        {"key": "primary_contact", "label": "Primary contact is linked"},
    ]
    assert bound_form.cleaned_data["exit_criteria"] == [
        {"key": "amount", "label": "Amount is greater than zero"},
        {"key": "close_date", "label": "Close date is set"},
    ]


def test_opportunitypipeline_stage_form_locked_fields_with_current_placements(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Placement Active Pipe")
    stage = _opportunitypipeline_stage(tenant, pipeline, name="In Use Stage", sequence=10, stage_kind="open", probability=20)
    opp = _opportunitypipeline_opportunity(tenant, name="Active Placement Opp")
    _opportunitypipeline_placement(tenant, opp, pipeline, stage)

    # When placements exist, stage fields are locked: stage_kind, crm_stage_key, probability, forecast_category, is_active
    form = PipelineStageForm(instance=stage, tenant=tenant, pipeline=pipeline)
    assert form.fields["pipeline"].disabled is True
    assert form.fields["stage_kind"].disabled is True
    assert form.fields["crm_stage_key"].disabled is True
    assert form.fields["probability"].disabled is True
    assert form.fields["forecast_category"].disabled is True
    assert form.fields["is_active"].disabled is True

    # Submitting unchanged data passes
    valid_payload = _opportunitypipeline_stage_payload(
        pipeline,
        name="Updated Name Permitted",
        code=stage.code,
        sequence=stage.sequence,
        stage_kind=stage.stage_kind,
        crm_stage_key=stage.crm_stage_key,
        probability=stage.probability,
        forecast_category=stage.forecast_category,
        is_active=True,
    )
    bound_valid = PipelineStageForm(data=valid_payload, instance=stage, tenant=tenant, pipeline=pipeline)
    assert bound_valid.is_valid(), bound_valid.errors

    # Tampering with locked non-boolean field (e.g. stage_kind) produces error
    tamper_non_bool = valid_payload.copy()
    tamper_non_bool["stage_kind"] = "won"
    bound_tamper_kind = PipelineStageForm(data=tamper_non_bool, instance=stage, tenant=tenant, pipeline=pipeline)
    assert not bound_tamper_kind.is_valid()
    assert "stage_kind" in bound_tamper_kind.errors
    assert "This field cannot be changed for the current record." in bound_tamper_kind.errors["stage_kind"]

    # Tampering with locked boolean field (e.g. unchecking is_active) produces error
    tamper_bool = valid_payload.copy()
    tamper_bool["is_active"] = ""
    bound_tamper_bool = PipelineStageForm(data=tamper_bool, instance=stage, tenant=tenant, pipeline=pipeline)
    assert not bound_tamper_bool.is_valid()
    assert "is_active" in bound_tamper_bool.errors
    assert "This field cannot be changed for the current record." in bound_tamper_bool.errors["is_active"]


# ============================================================================
# 3. PipelineStageOrderForm & Helper Tests
# ============================================================================

def test_opportunitypipeline_stage_order_form_initial_and_valid_reorder(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipeline = _opportunitypipeline_pipeline(tenant, name="Reorder Pipeline")
    s1 = _opportunitypipeline_stage(tenant, pipeline, name="S1", sequence=10)
    s2 = _opportunitypipeline_stage(tenant, pipeline, name="S2", sequence=20)
    s3 = _opportunitypipeline_stage(tenant, pipeline, name="S3", sequence=30)

    # Initial order check
    form = PipelineStageOrderForm(tenant=tenant, pipeline=pipeline)
    assert form.fields["ordered_stage_ids"].initial == f"{s1.pk},{s2.pk},{s3.pk}"

    # Valid reordering submission
    reversed_order = f"{s3.pk},{s1.pk},{s2.pk}"
    bound_form = PipelineStageOrderForm(data={"ordered_stage_ids": reversed_order}, tenant=tenant, pipeline=pipeline)
    assert bound_form.is_valid(), bound_form.errors
    assert bound_form.cleaned_data["ordered_stage_ids"] == [s3.pk, s1.pk, s2.pk]


def test_opportunitypipeline_stage_order_form_validation_errors(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b
    p_a = _opportunitypipeline_pipeline(t_a, name="Pipe A")
    s1 = _opportunitypipeline_stage(t_a, p_a, name="Stage 1", sequence=10)
    s2 = _opportunitypipeline_stage(t_a, p_a, name="Stage 2", sequence=20)

    # Empty tokens
    f_empty = PipelineStageOrderForm(data={"ordered_stage_ids": ""}, tenant=t_a, pipeline=p_a)
    assert not f_empty.is_valid()
    assert "Choose every pipeline stage exactly once." in str(f_empty.errors)

    # Non-digit tokens
    f_nondigit = PipelineStageOrderForm(data={"ordered_stage_ids": f"{s1.pk},abc,{s2.pk}"}, tenant=t_a, pipeline=p_a)
    assert not f_nondigit.is_valid()
    assert "Choose every pipeline stage exactly once." in str(f_nondigit.errors)

    # Duplicate IDs
    f_dup = PipelineStageOrderForm(data={"ordered_stage_ids": f"{s1.pk},{s1.pk}"}, tenant=t_a, pipeline=p_a)
    assert not f_dup.is_valid()
    assert "Choose every pipeline stage exactly once." in str(f_dup.errors)

    # Missing tenant or pipeline
    f_no_pipe = PipelineStageOrderForm(data={"ordered_stage_ids": f"{s1.pk},{s2.pk}"}, tenant=t_a, pipeline=None)
    assert not f_no_pipe.is_valid()
    assert "Pipeline stages are unavailable for this workspace." in str(f_no_pipe.errors)

    # Mismatched stage IDs (missing stage 2 or containing foreign stage)
    foreign_stage = _opportunitypipeline_stage(t_b, _opportunitypipeline_pipeline(t_b, name="Pipe B"), sequence=10)
    f_mismatch = PipelineStageOrderForm(data={"ordered_stage_ids": f"{s1.pk},{foreign_stage.pk}"}, tenant=t_a, pipeline=p_a)
    assert not f_mismatch.is_valid()
    assert "Choose every pipeline stage exactly once." in str(f_mismatch.errors)


def test_opportunitypipeline_positive_id_helper_branches():
    # Valid positive integers
    assert _opportunity_pipeline_positive_id(1) == 1
    assert _opportunity_pipeline_positive_id("42") == 42
    assert _opportunity_pipeline_positive_id(9223372036854775807) == 9223372036854775807

    # None, empty, booleans
    assert _opportunity_pipeline_positive_id(None) is None
    assert _opportunity_pipeline_positive_id("") is None
    assert _opportunity_pipeline_positive_id(True) is None
    assert _opportunity_pipeline_positive_id(False) is None

    # Zero, negative, overflows, and unparseable
    assert _opportunity_pipeline_positive_id(0) is None
    assert _opportunity_pipeline_positive_id(-10) is None
    assert _opportunity_pipeline_positive_id("invalid") is None
    assert _opportunity_pipeline_positive_id(9223372036854775808) is None
    assert _opportunity_pipeline_positive_id([]) is None


# ============================================================================
# 4. OpportunityPipelinePlacementForm Tests
# ============================================================================

def test_opportunitypipeline_placement_form_fields_exclusions_and_defaults(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    form = OpportunityPipelinePlacementForm(tenant=tenant)

    expected_fields = ["opportunity", "pipeline", "current_stage", "probability_override"]
    assert list(form.fields.keys()) == expected_fields
    assert list(form._meta.fields) == expected_fields

    excluded = {"tenant", "id", "created_at", "updated_at", "stage_entered_at"}
    assert not excluded.intersection(form.fields.keys())


def test_opportunitypipeline_placement_form_querysets_and_open_stages_only(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    p_a = _opportunitypipeline_pipeline(t_a, name="Pipe A", is_default=True)
    open_stage_a = _opportunitypipeline_stage(t_a, p_a, name="Open A", sequence=10, stage_kind="open")
    won_stage_a = _opportunitypipeline_stage(t_a, p_a, name="Won A", sequence=90, stage_kind="won", crm_stage_key="closed_won", probability=100, forecast_category="closed")
    lost_stage_a = _opportunitypipeline_stage(t_a, p_a, name="Lost A", sequence=100, stage_kind="lost", crm_stage_key="closed_lost", probability=0, forecast_category="closed")
    opp_a = _opportunitypipeline_opportunity(t_a, name="Opp A")

    opp_b = _opportunitypipeline_opportunity(t_b, name="Opp B")
    p_b = _opportunitypipeline_pipeline(t_b, name="Pipe B")

    # tenant=None querysets are none
    form_none = OpportunityPipelinePlacementForm(tenant=None)
    assert form_none.fields["opportunity"].queryset.count() == 0
    assert form_none.fields["pipeline"].queryset.count() == 0
    assert form_none.fields["current_stage"].queryset.count() == 0

    # Unbound form automatically defaults to default active pipeline
    form_a = OpportunityPipelinePlacementForm(tenant=t_a)
    assert opp_a in form_a.fields["opportunity"].queryset
    assert opp_b not in form_a.fields["opportunity"].queryset
    assert p_a in form_a.fields["pipeline"].queryset
    assert p_b not in form_a.fields["pipeline"].queryset

    # Current stage queryset ONLY includes open stages; won and lost stages are strictly excluded
    stage_qs = form_a.fields["current_stage"].queryset
    assert open_stage_a in stage_qs
    assert won_stage_a not in stage_qs
    assert lost_stage_a not in stage_qs


def test_opportunitypipeline_placement_form_selected_pipeline_handling(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    p_a = _opportunitypipeline_pipeline(t_a, name="Active Pipe", is_active=True)
    p_inactive = _opportunitypipeline_pipeline(t_a, name="Inactive Pipe", is_active=False)
    p_foreign = _opportunitypipeline_pipeline(t_b, name="Foreign Pipe", is_active=True)

    # Inactive or foreign selected_pipeline is rejected / ignored
    form_inact = OpportunityPipelinePlacementForm(tenant=t_a, selected_pipeline=p_inactive)
    assert form_inact.selected_pipeline is None

    form_for = OpportunityPipelinePlacementForm(tenant=t_a, selected_pipeline=p_foreign)
    assert form_for.selected_pipeline is None

    # Valid selected pipeline sets disabled=True, required=False, initial value
    form_valid = OpportunityPipelinePlacementForm(tenant=t_a, selected_pipeline=p_a)
    assert form_valid.selected_pipeline == p_a
    assert form_valid.fields["pipeline"].disabled is True
    assert form_valid.fields["pipeline"].required is False
    assert form_valid.initial["pipeline"] == p_a.pk


def test_opportunitypipeline_placement_form_disabled_opportunity_on_edit(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Placement Edit Pipe")
    stage = _opportunitypipeline_stage(tenant, pipe, name="Discovery", sequence=10, stage_kind="open")
    opp = _opportunitypipeline_opportunity(tenant, name="Locked Placement Opp")
    placement = _opportunitypipeline_placement(tenant, opp, pipe, stage)

    edit_form = OpportunityPipelinePlacementForm(instance=placement, tenant=tenant)
    assert edit_form.fields["opportunity"].disabled is True


def test_opportunitypipeline_placement_form_cross_tenant_and_invalid_stage_clean(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    p_a = _opportunitypipeline_pipeline(t_a, name="Tenant A Pipe")
    s_a = _opportunitypipeline_stage(t_a, p_a, name="Open A", sequence=10, stage_kind="open")
    opp_a = _opportunitypipeline_opportunity(t_a, name="Deal A")

    p_b = _opportunitypipeline_pipeline(t_b, name="Tenant B Pipe")
    s_b = _opportunitypipeline_stage(t_b, p_b, name="Open B", sequence=10, stage_kind="open")
    opp_b = _opportunitypipeline_opportunity(t_b, name="Deal B")

    # Cross-tenant opportunity rejected
    payload_bad_opp = _opportunitypipeline_placement_payload(opp_b, p_a, s_a)
    f_bad_opp = OpportunityPipelinePlacementForm(data=payload_bad_opp, tenant=t_a)
    f_bad_opp.fields["opportunity"].queryset = Opportunity.objects.all()
    assert not f_bad_opp.is_valid()
    assert "Choose an opportunity from this workspace." in str(f_bad_opp.errors["opportunity"])

    # Cross-tenant pipeline rejected
    payload_bad_pipe = _opportunitypipeline_placement_payload(opp_a, p_b, s_a)
    f_bad_pipe = OpportunityPipelinePlacementForm(data=payload_bad_pipe, tenant=t_a)
    f_bad_pipe.fields["pipeline"].queryset = Pipeline.objects.all()
    assert not f_bad_pipe.is_valid()
    assert "Choose an active pipeline from this workspace." in str(f_bad_pipe.errors["pipeline"])

    # Cross-tenant stage rejected
    payload_bad_stage = _opportunitypipeline_placement_payload(opp_a, p_a, s_b)
    f_bad_stage = OpportunityPipelinePlacementForm(data=payload_bad_stage, tenant=t_a)
    f_bad_stage.fields["current_stage"].queryset = PipelineStage.objects.all()
    assert not f_bad_stage.is_valid()
    assert "Choose an active stage from this workspace." in str(f_bad_stage.errors["current_stage"])

    # Stage from another pipeline rejected
    p_a2 = _opportunitypipeline_pipeline(t_a, name="Second Pipe A")
    s_a2 = _opportunitypipeline_stage(t_a, p_a2, name="Other Pipe Stage", sequence=10, stage_kind="open")
    payload_wrong_pipe_stage = _opportunitypipeline_placement_payload(opp_a, p_a, s_a2)
    f_wrong = OpportunityPipelinePlacementForm(data=payload_wrong_pipe_stage, tenant=t_a)
    f_wrong.fields["current_stage"].queryset = PipelineStage.objects.all()
    assert not f_wrong.is_valid()
    assert "Choose a stage from the selected pipeline." in str(f_wrong.errors["current_stage"])

    # Non-open (won or lost) stage rejected
    won_stage = _opportunitypipeline_stage(t_a, p_a, name="Won", sequence=90, stage_kind="won", crm_stage_key="closed_won", probability=100, forecast_category="closed")
    payload_won = _opportunitypipeline_placement_payload(opp_a, p_a, won_stage)
    f_won = OpportunityPipelinePlacementForm(data=payload_won, tenant=t_a)
    f_won.fields["current_stage"].queryset = PipelineStage.objects.all()
    assert not f_won.is_valid()
    assert "Choose an open stage. Won and lost stages must be transitioned through the workspace with an outcome reason." in str(f_won.errors["current_stage"])


def test_opportunitypipeline_placement_form_probability_override_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Override Pipe")
    open_stage = _opportunitypipeline_stage(tenant, pipe, name="Discovery", sequence=10, stage_kind="open")
    won_stage = _opportunitypipeline_stage(tenant, pipe, name="Won", sequence=90, stage_kind="won", crm_stage_key="closed_won", probability=100, forecast_category="closed")
    lost_stage = _opportunitypipeline_stage(tenant, pipe, name="Lost", sequence=100, stage_kind="lost", crm_stage_key="closed_lost", probability=0, forecast_category="closed")
    opp = _opportunitypipeline_opportunity(tenant, name="Override Opp")

    # Valid override on open stage
    payload_valid = _opportunitypipeline_placement_payload(opp, pipe, open_stage, probability_override="45")
    f_valid = OpportunityPipelinePlacementForm(data=payload_valid, tenant=tenant)
    assert f_valid.is_valid(), f_valid.errors
    placement = f_valid.save()
    assert placement.probability_override == 45
    assert placement.effective_probability == 45

    # Won stage requires 100%
    f_won = OpportunityPipelinePlacementForm(
        data=_opportunitypipeline_placement_payload(opp, pipe, won_stage, probability_override="90"),
        tenant=tenant,
    )
    f_won.fields["current_stage"].queryset = PipelineStage.objects.all()
    assert not f_won.is_valid()
    assert "Won placements require 100%." in str(f_won.errors["probability_override"])

    # Lost stage requires 0%
    f_lost = OpportunityPipelinePlacementForm(
        data=_opportunitypipeline_placement_payload(opp, pipe, lost_stage, probability_override="10"),
        tenant=tenant,
    )
    f_lost.fields["current_stage"].queryset = PipelineStage.objects.all()
    assert not f_lost.is_valid()
    assert "Lost placements require 0%." in str(f_lost.errors["probability_override"])


# ============================================================================
# 5. OpportunityTeamMemberForm Tests
# ============================================================================

def test_opportunitypipeline_team_member_form_fields_and_exclusions(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, name="Deal TM")
    form = OpportunityTeamMemberForm(tenant=tenant, opportunity=opp)

    expected_fields = ["user", "org_unit", "role", "responsibility", "is_active"]
    assert list(form.fields.keys()) == expected_fields
    assert list(form._meta.fields) == expected_fields

    excluded = {"tenant", "id", "created_at", "updated_at", "number", "opportunity"}
    assert not excluded.intersection(form.fields.keys())


def test_opportunitypipeline_team_member_form_querysets_and_scoping(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    user_a = _opportunitypipeline_user(t_a, "active_a@example.com", is_active=True)
    inactive_user_a = _opportunitypipeline_user(t_a, "inact_a@example.com", is_active=False)
    user_b = _opportunitypipeline_user(t_b, "user_b@example.com", is_active=True)

    org_a = _opportunitypipeline_org_unit(t_a, "Sales East")
    org_b = _opportunitypipeline_org_unit(t_b, "Sales West")

    opp_a = _opportunitypipeline_opportunity(t_a, name="Opp Team QS")

    # tenant=None produces empty querysets
    form_none = OpportunityTeamMemberForm(tenant=None, opportunity=opp_a)
    assert form_none.fields["user"].queryset.count() == 0
    assert form_none.fields["org_unit"].queryset.count() == 0

    # tenant=t_a includes active user_a, excludes inactive_user_a and user_b
    form_a = OpportunityTeamMemberForm(tenant=t_a, opportunity=opp_a)
    assert user_a in form_a.fields["user"].queryset
    assert inactive_user_a not in form_a.fields["user"].queryset
    assert user_b not in form_a.fields["user"].queryset
    assert org_a in form_a.fields["org_unit"].queryset
    assert org_b not in form_a.fields["org_unit"].queryset


def test_opportunitypipeline_team_member_form_clean_validations_and_scoping(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    user_a = _opportunitypipeline_user(t_a, "tm_a@example.com")
    inact_user_a = _opportunitypipeline_user(t_a, "tm_inact@example.com", is_active=False)
    user_b = _opportunitypipeline_user(t_b, "tm_b@example.com")
    opp_a = _opportunitypipeline_opportunity(t_a, name="Opp TM Valid")
    opp_b = _opportunitypipeline_opportunity(t_b, name="Opp TM B")
    org_b = _opportunitypipeline_org_unit(t_b, "Org B")

    # Missing tenant workspace
    f_no_tenant = OpportunityTeamMemberForm(data=_opportunitypipeline_team_member_payload(user_a), tenant=None, opportunity=opp_a)
    assert not f_no_tenant.is_valid()
    assert "A tenant workspace is required." in str(f_no_tenant.errors)

    # Missing opportunity
    f_no_opp = OpportunityTeamMemberForm(data=_opportunitypipeline_team_member_payload(user_a), tenant=t_a, opportunity=None)
    assert not f_no_opp.is_valid()
    assert "Choose an opportunity from this workspace." in str(f_no_opp.errors)

    # Opportunity belonging to another workspace (clean method non-field error)
    f_bad_opp = OpportunityTeamMemberForm(tenant=t_a, opportunity=opp_b)
    f_bad_opp.cleaned_data = {}
    f_bad_opp.clean()
    assert "The opportunity must belong to this workspace." in str(f_bad_opp.errors)

    # User belonging to another workspace
    f_bad_user = OpportunityTeamMemberForm(data=_opportunitypipeline_team_member_payload(user_b), tenant=t_a, opportunity=opp_a)
    f_bad_user.fields["user"].queryset = User.objects.all()
    assert not f_bad_user.is_valid()
    assert "The user must belong to this workspace." in str(f_bad_user.errors["user"])

    # Inactive user for new membership rejected
    f_inact_user = OpportunityTeamMemberForm(data=_opportunitypipeline_team_member_payload(inact_user_a), tenant=t_a, opportunity=opp_a)
    f_inact_user.fields["user"].queryset = User.objects.all()
    assert not f_inact_user.is_valid()
    assert "Choose an active user for this membership." in str(f_inact_user.errors["user"])

    # Org unit belonging to another workspace
    f_bad_org = OpportunityTeamMemberForm(data=_opportunitypipeline_team_member_payload(user_a, org_unit=org_b), tenant=t_a, opportunity=opp_a)
    f_bad_org.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not f_bad_org.is_valid()
    assert "The organizational unit must belong to this workspace." in str(f_bad_org.errors["org_unit"])


def test_opportunitypipeline_team_member_form_duplicate_and_edit_handling(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, name="Dup TM Opp")
    opp2 = _opportunitypipeline_opportunity(tenant, name="Opp Two")
    user = _opportunitypipeline_user(tenant, "unique_tm@example.com")
    member = _opportunitypipeline_team_member(tenant, opp, user, role="collaborator")

    # Creating duplicate membership (same user and role) on same opportunity fails
    dup_payload = _opportunitypipeline_team_member_payload(user, role="collaborator")
    f_dup = OpportunityTeamMemberForm(data=dup_payload, tenant=tenant, opportunity=opp)
    assert not f_dup.is_valid()
    assert "This user already has that role on the opportunity." in str(f_dup.errors["role"])

    # Different role on same user passes
    diff_role_payload = _opportunitypipeline_team_member_payload(user, role="sales_support")
    f_diff = OpportunityTeamMemberForm(data=diff_role_payload, tenant=tenant, opportunity=opp)
    assert f_diff.is_valid(), f_diff.errors

    # Editing existing membership with same role does NOT trigger duplicate error
    edit_payload = _opportunitypipeline_team_member_payload(user, role="collaborator", responsibility="Updated role notes.")
    f_edit = OpportunityTeamMemberForm(data=edit_payload, instance=member, tenant=tenant, opportunity=opp)
    assert f_edit.is_valid(), f_edit.errors
    updated = f_edit.save()
    assert updated.responsibility == "Updated role notes."

    # Moving member to different opportunity on edit is blocked
    f_move = OpportunityTeamMemberForm(data=edit_payload, instance=member, tenant=tenant, opportunity=opp2)
    assert not f_move.is_valid()
    assert "A team member cannot move to another opportunity." in str(f_move.errors)


# ============================================================================
# 6. CompetitorProfileForm Tests
# ============================================================================

def test_opportunitypipeline_competitor_profile_form_fields_exclusions_and_querysets(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    party_org_a = _opportunitypipeline_party(t_a, name="Rival Org A", kind="organization")
    party_person_a = _opportunitypipeline_party(t_a, name="Person A", kind="person")
    party_org_b = _opportunitypipeline_party(t_b, name="Rival Org B", kind="organization")

    form = CompetitorProfileForm(tenant=t_a)

    expected_fields = [
        "party", "aliases", "website_url", "description", "market_positioning",
        "strengths", "weaknesses", "differentiators", "objection_handling",
        "last_reviewed_on", "is_active",
    ]
    assert list(form.fields.keys()) == expected_fields
    assert list(form._meta.fields) == expected_fields

    excluded = {"tenant", "number", "id", "created_at", "updated_at", "tier", "website"}
    assert not excluded.intersection(form.fields.keys())

    # Queryset filters to organizations in workspace
    assert party_org_a in form.fields["party"].queryset
    assert party_person_a not in form.fields["party"].queryset
    assert party_org_b not in form.fields["party"].queryset

    # tenant=None produces empty party queryset
    form_none = CompetitorProfileForm(tenant=None)
    assert form_none.fields["party"].queryset.count() == 0


def test_opportunitypipeline_competitor_profile_form_party_organization_validation(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    party_person = _opportunitypipeline_party(t_a, name="Individual Contact", kind="person")
    party_foreign = _opportunitypipeline_party(t_b, name="Foreign Org", kind="organization")
    party_org = _opportunitypipeline_party(t_a, name="Valid Rival", kind="organization")

    # Person party is rejected
    f_person = CompetitorProfileForm(data=_opportunitypipeline_competitor_profile_payload(party_person), tenant=t_a)
    f_person.fields["party"].queryset = Party.objects.all()
    assert not f_person.is_valid()
    assert "Choose a same-tenant organization." in str(f_person.errors["party"])

    # Foreign party is rejected
    f_foreign = CompetitorProfileForm(data=_opportunitypipeline_competitor_profile_payload(party_foreign), tenant=t_a)
    f_foreign.fields["party"].queryset = Party.objects.all()
    assert not f_foreign.is_valid()
    assert "Choose a same-tenant organization." in str(f_foreign.errors["party"])

    # Valid organization party passes and saves
    f_valid = CompetitorProfileForm(data=_opportunitypipeline_competitor_profile_payload(party_org), tenant=t_a)
    assert f_valid.is_valid(), f_valid.errors
    comp = f_valid.save()
    assert comp.pk is not None
    assert comp.tenant == t_a
    assert comp.party == party_org
    assert comp.number.startswith("CMP-")


def test_opportunitypipeline_competitor_profile_form_save_and_clean_without_tenant(opportunitypipeline_tenant_a):
    party = _opportunitypipeline_party(opportunitypipeline_tenant_a, kind="organization")
    form = CompetitorProfileForm(data=_opportunitypipeline_competitor_profile_payload(party), tenant=None)
    assert not form.is_valid()
    assert "A tenant workspace is required." in str(form.errors)


# ============================================================================
# 7. OpportunityCompetitorForm Tests
# ============================================================================

def test_opportunitypipeline_opportunity_competitor_form_fields_and_exclusions(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, name="Deal Comp Link")
    form = OpportunityCompetitorForm(tenant=tenant, opportunity=opp)

    expected_fields = [
        "competitor_profile", "relationship", "is_primary",
        "pricing_notes", "deal_notes", "positioning_notes",
    ]
    assert list(form.fields.keys()) == expected_fields
    assert list(form._meta.fields) == expected_fields

    excluded = {"tenant", "id", "created_at", "updated_at", "opportunity", "threat_level", "strategy_notes"}
    assert not excluded.intersection(form.fields.keys())


def test_opportunitypipeline_opportunity_competitor_form_querysets_and_scoping(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    comp_a = _opportunitypipeline_competitor_profile(t_a, name="Comp A", is_active=True)
    comp_inact_a = _opportunitypipeline_competitor_profile(t_a, name="Comp Inact A", is_active=False)
    comp_b = _opportunitypipeline_competitor_profile(t_b, name="Comp B", is_active=True)
    opp_a = _opportunitypipeline_opportunity(t_a, name="Opp Comp QS")

    # tenant=None produces empty queryset
    form_none = OpportunityCompetitorForm(tenant=None, opportunity=opp_a)
    assert form_none.fields["competitor_profile"].queryset.count() == 0

    # tenant=t_a filters active profiles
    form_a = OpportunityCompetitorForm(tenant=t_a, opportunity=opp_a)
    assert comp_a in form_a.fields["competitor_profile"].queryset
    assert comp_inact_a not in form_a.fields["competitor_profile"].queryset
    assert comp_b not in form_a.fields["competitor_profile"].queryset


def test_opportunitypipeline_opportunity_competitor_form_clean_validations(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    comp_a = _opportunitypipeline_competitor_profile(t_a, name="Profile A", is_active=True)
    comp_inact_a = _opportunitypipeline_competitor_profile(t_a, name="Profile Inactive", is_active=False)
    comp_b = _opportunitypipeline_competitor_profile(t_b, name="Profile B", is_active=True)
    opp_a = _opportunitypipeline_opportunity(t_a, name="Opp Link A")
    opp_b = _opportunitypipeline_opportunity(t_b, name="Opp Link B")

    # Missing tenant workspace
    f_no_tenant = OpportunityCompetitorForm(data=_opportunitypipeline_opportunity_competitor_payload(comp_a), tenant=None, opportunity=opp_a)
    assert not f_no_tenant.is_valid()
    assert "A tenant workspace is required." in str(f_no_tenant.errors)

    # Missing opportunity
    f_no_opp = OpportunityCompetitorForm(data=_opportunitypipeline_opportunity_competitor_payload(comp_a), tenant=t_a, opportunity=None)
    assert not f_no_opp.is_valid()
    assert "Choose an opportunity from this workspace." in str(f_no_opp.errors)

    # Foreign opportunity (clean method non-field error)
    f_bad_opp = OpportunityCompetitorForm(tenant=t_a, opportunity=opp_b)
    f_bad_opp.cleaned_data = {}
    f_bad_opp.clean()
    assert "The opportunity must belong to this workspace." in str(f_bad_opp.errors)

    # Foreign competitor profile
    f_bad_comp = OpportunityCompetitorForm(data=_opportunitypipeline_opportunity_competitor_payload(comp_b), tenant=t_a, opportunity=opp_a)
    f_bad_comp.fields["competitor_profile"].queryset = CompetitorProfile.objects.all()
    assert not f_bad_comp.is_valid()
    assert "Choose a competitor profile from this workspace." in str(f_bad_comp.errors["competitor_profile"])

    # Inactive competitor profile on new link
    f_inact_comp = OpportunityCompetitorForm(data=_opportunitypipeline_opportunity_competitor_payload(comp_inact_a), tenant=t_a, opportunity=opp_a)
    f_inact_comp.fields["competitor_profile"].queryset = CompetitorProfile.objects.all()
    assert not f_inact_comp.is_valid()
    assert "Choose an active competitor profile." in str(f_inact_comp.errors["competitor_profile"])


def test_opportunitypipeline_opportunity_competitor_form_duplicate_and_edit_handling(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, name="Dup Link Opp")
    opp2 = _opportunitypipeline_opportunity(tenant, name="Second Opp")
    comp = _opportunitypipeline_competitor_profile(tenant, name="Dup Profile", is_active=True)
    link = _opportunitypipeline_opportunity_competitor(tenant, opp, comp, relationship="shortlisted")

    # Duplicate link fails
    payload_dup = _opportunitypipeline_opportunity_competitor_payload(comp, relationship="shortlisted")
    f_dup = OpportunityCompetitorForm(data=payload_dup, tenant=tenant, opportunity=opp)
    assert not f_dup.is_valid()
    assert "That competitor is already linked to this opportunity." in str(f_dup.errors["competitor_profile"])

    # Editing existing link succeeds
    payload_edit = _opportunitypipeline_opportunity_competitor_payload(comp, relationship="preferred", is_primary=True)
    f_edit = OpportunityCompetitorForm(data=payload_edit, instance=link, tenant=tenant, opportunity=opp)
    assert f_edit.is_valid(), f_edit.errors
    updated = f_edit.save()
    assert updated.relationship == "preferred"
    assert updated.is_primary is True

    # Moving competitor link to another opportunity fails
    f_move = OpportunityCompetitorForm(data=payload_edit, instance=link, tenant=tenant, opportunity=opp2)
    assert not f_move.is_valid()
    assert "A competitor link cannot move to another opportunity." in str(f_move.errors)


# ============================================================================
# 8. WinLossReasonForm Tests
# ============================================================================

def test_opportunitypipeline_win_loss_reason_form_fields_and_exclusions(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    form = WinLossReasonForm(tenant=tenant)

    expected_fields = ["code", "name", "description", "sequence", "result", "category", "is_active"]
    assert list(form.fields.keys()) == expected_fields
    assert list(form._meta.fields) == expected_fields

    excluded = {"tenant", "number", "id", "created_at", "updated_at", "requires_competitor", "notes"}
    assert not excluded.intersection(form.fields.keys())

    # Result and category are strictly required
    assert form.fields["result"].required is True
    assert form.fields["category"].required is True


def test_opportunitypipeline_win_loss_reason_form_code_cleaning_and_uniqueness(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    # clean_code strips whitespace and forces lowercase
    payload = _opportunitypipeline_win_loss_reason_payload(code="  PRODUCT_FIT_EXCELLENT  ", name="Excellent Fit")
    form = WinLossReasonForm(data=payload, tenant=t_a)
    assert form.is_valid(), form.errors
    reason = form.save()
    assert reason.code == "product_fit_excellent"
    assert reason.number.startswith("WLR-")

    # Duplicate code in same tenant fails database unique constraint
    from django.db import transaction
    payload_dup = _opportunitypipeline_win_loss_reason_payload(code="product_fit_excellent", name="Duplicate Fit")
    form_dup = WinLossReasonForm(data=payload_dup, tenant=t_a)
    assert form_dup.is_valid()
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            form_dup.save()

    # Same code in different tenant succeeds
    form_other_tenant = WinLossReasonForm(data=payload_dup, tenant=t_b)
    assert form_other_tenant.is_valid(), form_other_tenant.errors
    reason_b = form_other_tenant.save()
    assert reason_b.tenant == t_b
    assert reason_b.code == "product_fit_excellent"


def test_opportunitypipeline_win_loss_reason_form_clean_validations_and_scoping(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    # Missing tenant workspace
    f_no_tenant = WinLossReasonForm(data=_opportunitypipeline_win_loss_reason_payload(), tenant=None)
    assert not f_no_tenant.is_valid()
    assert "A tenant workspace is required." in str(f_no_tenant.errors)

    # Cross-tenant instance editing
    existing = _opportunitypipeline_win_loss_reason(t_b, code="foreign_reason")
    f_foreign = WinLossReasonForm(
        data=_opportunitypipeline_win_loss_reason_payload(code="foreign_reason", name="Hacked Reason"),
        instance=existing,
        tenant=t_a,
    )
    assert not f_foreign.is_valid()
    assert "The win/loss reason must belong to this workspace." in str(f_foreign.errors)


# ============================================================================
# 9. OpportunityTransitionForm Tests
# ============================================================================

def test_opportunitypipeline_transition_form_fields_and_context_validation(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    p_a = _opportunitypipeline_pipeline(t_a, name="Transition Pipe A")
    s1 = _opportunitypipeline_stage(t_a, p_a, name="Stage 1", sequence=10, stage_kind="open")
    s2 = _opportunitypipeline_stage(t_a, p_a, name="Stage 2", sequence=20, stage_kind="open")
    opp_a = _opportunitypipeline_opportunity(t_a, name="Opp Transition Context")
    placement_a = _opportunitypipeline_placement(t_a, opp_a, p_a, s1)

    opp_b = _opportunitypipeline_opportunity(t_b, name="Opp B")
    placement_b = _opportunitypipeline_placement(t_b, opp_b, _opportunitypipeline_pipeline(t_b, name="Pipe B"), _opportunitypipeline_stage(t_b, _opportunitypipeline_pipeline(t_b, name="Pipe B2"), sequence=10))

    form = OpportunityTransitionForm(tenant=t_a, opportunity=opp_a, placement=placement_a)
    assert list(form.fields.keys()) == ["target_stage", "reason", "competitor_link", "notes"]
    assert form.fields["target_stage"].required is True
    assert form.fields["reason"].required is False
    assert form.fields["competitor_link"].required is False
    assert form.fields["notes"].required is False

    # Invalid context: tenant=None
    f_no_tenant = OpportunityTransitionForm(tenant=None, opportunity=opp_a, placement=placement_a)
    assert not f_no_tenant._placement_valid

    # Invalid context: foreign opportunity
    f_foreign_opp = OpportunityTransitionForm(tenant=t_a, opportunity=opp_b, placement=placement_a)
    assert not f_foreign_opp._placement_valid

    # Invalid context: placement does not belong to opportunity
    f_mismatch = OpportunityTransitionForm(tenant=t_a, opportunity=opp_a, placement=placement_b)
    assert not f_mismatch._placement_valid

    # When context is invalid, clean() reports error
    payload = _opportunitypipeline_transition_payload(s2)
    f_bad_clean = OpportunityTransitionForm(data=payload, tenant=None, opportunity=opp_a, placement=placement_a)
    assert not f_bad_clean.is_valid()
    assert "Place this opportunity in a pipeline before transitioning it." in str(f_bad_clean.errors)


def test_opportunitypipeline_transition_form_querysets_filtering_and_hints(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Hint Pipe")
    s1 = _opportunitypipeline_stage(tenant, pipe, name="Discovery", sequence=10, stage_kind="open")
    s2 = _opportunitypipeline_stage(tenant, pipe, name="Proposal", sequence=20, stage_kind="open")
    s_won = _opportunitypipeline_stage(tenant, pipe, name="Won", sequence=90, stage_kind="won", crm_stage_key="closed_won", probability=100, forecast_category="closed")
    s_lost = _opportunitypipeline_stage(tenant, pipe, name="Lost", sequence=100, stage_kind="lost", crm_stage_key="closed_lost", probability=0, forecast_category="closed")

    r_both = _opportunitypipeline_win_loss_reason(tenant, name="General Reason", result="both")
    r_won = _opportunitypipeline_win_loss_reason(tenant, name="Won Only Reason", result="won")
    r_lost = _opportunitypipeline_win_loss_reason(tenant, name="Lost Only Reason", result="lost")

    opp = _opportunitypipeline_opportunity(tenant, name="Hint Opp")
    placement = _opportunitypipeline_placement(tenant, opp, pipe, s1)
    comp_prof = _opportunitypipeline_competitor_profile(tenant, name="Comp Hint", is_active=True)
    comp_link = _opportunitypipeline_opportunity_competitor(tenant, opp, comp_prof)

    # Target queryset excludes current stage (s1)
    form = OpportunityTransitionForm(tenant=tenant, opportunity=opp, placement=placement)
    target_qs = form.fields["target_stage"].queryset
    assert s1 not in target_qs
    assert s2 in target_qs
    assert s_won in target_qs
    assert s_lost in target_qs

    # Competitor queryset includes links for this opportunity
    comp_qs = form.fields["competitor_link"].queryset
    assert comp_link in comp_qs

    # Allowed target stages restriction
    form_restricted = OpportunityTransitionForm(
        tenant=tenant,
        opportunity=opp,
        placement=placement,
        allowed_target_stages=[s2],
    )
    assert list(form_restricted.fields["target_stage"].queryset) == [s2]

    # Target hint for won filters reasons to both + won
    payload_won = _opportunitypipeline_transition_payload(s_won)
    form_bound_won = OpportunityTransitionForm(data=payload_won, tenant=tenant, opportunity=opp, placement=placement)
    reason_qs_won = form_bound_won.fields["reason"].queryset
    assert r_both in reason_qs_won
    assert r_won in reason_qs_won
    assert r_lost not in reason_qs_won

    # Target hint for lost filters reasons to both + lost
    payload_lost = _opportunitypipeline_transition_payload(s_lost)
    form_bound_lost = OpportunityTransitionForm(data=payload_lost, tenant=tenant, opportunity=opp, placement=placement)
    reason_qs_lost = form_bound_lost.fields["reason"].queryset
    assert r_both in reason_qs_lost
    assert r_lost in reason_qs_lost
    assert r_won not in reason_qs_lost


def test_opportunitypipeline_transition_form_target_stage_validation(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    p_a = _opportunitypipeline_pipeline(t_a, name="Stage Valid Pipe")
    s1 = _opportunitypipeline_stage(t_a, p_a, name="Open S1", sequence=10, stage_kind="open")
    s_inact = _opportunitypipeline_stage(t_a, p_a, name="Inact S", sequence=15, is_active=False)
    opp = _opportunitypipeline_opportunity(t_a, name="Target Stage Opp")
    placement = _opportunitypipeline_placement(t_a, opp, p_a, s1)

    p_foreign = _opportunitypipeline_pipeline(t_b, name="Foreign Target Pipe")
    s_foreign = _opportunitypipeline_stage(t_b, p_foreign, sequence=10)

    # Foreign stage
    f_foreign = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_foreign),
        tenant=t_a,
        opportunity=opp,
        placement=placement,
    )
    f_foreign.fields["target_stage"].queryset = PipelineStage.objects.all()
    assert not f_foreign.is_valid()
    assert "Choose an active stage from the current pipeline." in str(f_foreign.errors["target_stage"])

    # Inactive stage
    f_inact = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_inact),
        tenant=t_a,
        opportunity=opp,
        placement=placement,
    )
    f_inact.fields["target_stage"].queryset = PipelineStage.objects.all()
    assert not f_inact.is_valid()
    assert "Choose an active stage from the current pipeline." in str(f_inact.errors["target_stage"])


def test_opportunitypipeline_transition_form_closing_won_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Won Flow Pipe")
    s_open = _opportunitypipeline_stage(tenant, pipe, name="Discovery", sequence=10, stage_kind="open")
    s_won = _opportunitypipeline_stage(tenant, pipe, name="Won", sequence=90, stage_kind="won", crm_stage_key="closed_won", probability=100, forecast_category="closed")

    r_won = _opportunitypipeline_win_loss_reason(tenant, name="Superior Capability", result="won")
    r_lost = _opportunitypipeline_win_loss_reason(tenant, name="Too Expensive", result="lost")

    opp = _opportunitypipeline_opportunity(tenant, name="Won Opp")
    placement = _opportunitypipeline_placement(tenant, opp, pipe, s_open)

    # Missing reason on Won closure fails
    f_no_reason = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_won, reason=None),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    assert not f_no_reason.is_valid()
    assert "A reason is required when closing an opportunity." in str(f_no_reason.errors["reason"])

    # Incompatible reason (lost-only reason) on Won closure fails
    f_bad_reason = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_won, reason=r_lost),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    f_bad_reason.fields["reason"].queryset = WinLossReason.objects.all()
    assert not f_bad_reason.is_valid()
    assert "Choose a reason compatible with the closing result." in str(f_bad_reason.errors["reason"])

    # Valid won reason passes
    f_valid = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_won, reason=r_won),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    assert f_valid.is_valid(), f_valid.errors
    assert f_valid.cleaned_data["target_stage"] == s_won
    assert f_valid.cleaned_data["reason"] == r_won


def test_opportunitypipeline_transition_form_closing_lost_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Lost Flow Pipe")
    s_open = _opportunitypipeline_stage(tenant, pipe, name="Discovery", sequence=10, stage_kind="open")
    s_lost = _opportunitypipeline_stage(tenant, pipe, name="Lost", sequence=100, stage_kind="lost", crm_stage_key="closed_lost", probability=0, forecast_category="closed")

    r_won = _opportunitypipeline_win_loss_reason(tenant, name="Feature Leader", result="won")
    r_lost = _opportunitypipeline_win_loss_reason(tenant, name="Lost on Price", result="lost")

    opp = _opportunitypipeline_opportunity(tenant, name="Lost Opp")
    placement = _opportunitypipeline_placement(tenant, opp, pipe, s_open)

    # Missing reason on Lost closure fails
    f_no_reason = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_lost, reason=None),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    assert not f_no_reason.is_valid()
    assert "A reason is required when closing an opportunity." in str(f_no_reason.errors["reason"])

    # Incompatible reason (won-only reason) on Lost closure fails
    f_bad_reason = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_lost, reason=r_won),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    f_bad_reason.fields["reason"].queryset = WinLossReason.objects.all()
    assert not f_bad_reason.is_valid()
    assert "Choose a reason compatible with the closing result." in str(f_bad_reason.errors["reason"])

    # Valid lost reason passes
    f_valid = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_lost, reason=r_lost),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    assert f_valid.is_valid(), f_valid.errors


def test_opportunitypipeline_transition_form_open_stage_validation(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Open Transition Pipe")
    s1 = _opportunitypipeline_stage(tenant, pipe, name="Stage 1", sequence=10, stage_kind="open")
    s2 = _opportunitypipeline_stage(tenant, pipe, name="Stage 2", sequence=20, stage_kind="open")

    r = _opportunitypipeline_win_loss_reason(tenant, name="Any Reason", result="both")
    opp = _opportunitypipeline_opportunity(tenant, name="Open Opp")
    placement = _opportunitypipeline_placement(tenant, opp, pipe, s1)
    comp_prof = _opportunitypipeline_competitor_profile(tenant, name="Comp Link Test")
    comp_link = _opportunitypipeline_opportunity_competitor(tenant, opp, comp_prof)

    # Supplying a reason when advancing to an open stage is invalid
    f_reason = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s2, reason=r),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    assert not f_reason.is_valid()
    assert "A reason is only valid when closing an opportunity." in str(f_reason.errors["reason"])

    # Supplying a competitor link when transitioning to an open stage is invalid
    f_comp = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s2, competitor_link=comp_link),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    assert not f_comp.is_valid()
    assert "A competitor link is only valid on a lost closure." in str(f_comp.errors["competitor_link"])

    # Advancing without reason and competitor link passes
    f_valid = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s2),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    assert f_valid.is_valid(), f_valid.errors


def test_opportunitypipeline_transition_form_competitor_link_relationship_validation(opportunitypipeline_tenant_a, opportunitypipeline_tenant_b):
    t_a = opportunitypipeline_tenant_a
    t_b = opportunitypipeline_tenant_b

    pipe = _opportunitypipeline_pipeline(t_a, name="Competitor Flow Pipe")
    s_open = _opportunitypipeline_stage(t_a, pipe, name="Discovery", sequence=10, stage_kind="open")
    s_won = _opportunitypipeline_stage(t_a, pipe, name="Won", sequence=90, stage_kind="won", crm_stage_key="closed_won", probability=100, forecast_category="closed")
    s_lost = _opportunitypipeline_stage(t_a, pipe, name="Lost", sequence=100, stage_kind="lost", crm_stage_key="closed_lost", probability=0, forecast_category="closed")

    r_won = _opportunitypipeline_win_loss_reason(t_a, name="Won Reason", result="won")
    r_lost = _opportunitypipeline_win_loss_reason(t_a, name="Lost Reason", result="lost")

    opp = _opportunitypipeline_opportunity(t_a, name="Competitor Opp")
    placement = _opportunitypipeline_placement(t_a, opp, pipe, s_open)

    comp_prof = _opportunitypipeline_competitor_profile(t_a, name="Rival Inc")
    comp_link_lost = _opportunitypipeline_opportunity_competitor(t_a, opp, comp_prof, relationship="lost_to")

    opp_other = _opportunitypipeline_opportunity(t_a, name="Other Opp")
    comp_link_other = _opportunitypipeline_opportunity_competitor(t_a, opp_other, comp_prof)

    # Competitor link with 'lost_to' relationship requires target to be lost (fails on won)
    f_won_lostto = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_won, reason=r_won, competitor_link=comp_link_lost),
        tenant=t_a,
        opportunity=opp,
        placement=placement,
    )
    f_won_lostto.fields["competitor_link"].queryset = OpportunityCompetitor.objects.all()
    assert not f_won_lostto.is_valid()
    assert "This competitor relationship requires a lost target." in str(f_won_lostto.errors["competitor_link"])

    # Competitor link belonging to different opportunity is rejected
    f_other_link = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_lost, reason=r_lost, competitor_link=comp_link_other),
        tenant=t_a,
        opportunity=opp,
        placement=placement,
    )
    f_other_link.fields["competitor_link"].queryset = OpportunityCompetitor.objects.all()
    assert not f_other_link.is_valid()
    assert "Choose a competitor link from this opportunity." in str(f_other_link.errors["competitor_link"])

    # Valid competitor link on lost target passes
    f_valid = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_lost, reason=r_lost, competitor_link=comp_link_lost),
        tenant=t_a,
        opportunity=opp,
        placement=placement,
    )
    assert f_valid.is_valid(), f_valid.errors
    assert f_valid.cleaned_data["competitor_link"] == comp_link_lost


def test_opportunitypipeline_team_member_form_instance_resolution_and_exceptions(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    opp = _opportunitypipeline_opportunity(tenant, name="TM Inst Opp")
    user = _opportunitypipeline_user(tenant, "inst_tm@example.com")
    member = _opportunitypipeline_team_member(tenant, opp, user, role="observer")

    # Instance without tenant_id gets tenant set on __init__
    unsaved_member = OpportunityTeamMember(user=user, role="observer")
    form_set_tenant = OpportunityTeamMemberForm(instance=unsaved_member, tenant=tenant, opportunity=opp)
    assert unsaved_member.tenant == tenant

    # Edit form with opportunity=None resolves from instance.opportunity
    form_res = OpportunityTeamMemberForm(
        data=_opportunitypipeline_team_member_payload(user, role="observer"),
        instance=member,
        tenant=tenant,
        opportunity=None,
    )
    assert form_res.is_valid(), form_res.errors

    # When instance has non-existent opportunity_id, ObjectDoesNotExist is handled
    ghost_member = OpportunityTeamMember(tenant=tenant, user=user, role="observer")
    ghost_member.opportunity_id = 999999
    f_ghost = OpportunityTeamMemberForm(instance=ghost_member, tenant=tenant, opportunity=None)
    f_ghost.cleaned_data = {}
    f_ghost.clean()
    assert "Choose an opportunity from this workspace." in str(f_ghost.errors)


def test_opportunitypipeline_competitor_profile_and_competitor_instance_resolution(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    party = _opportunitypipeline_party(tenant, kind="organization")

    # CompetitorProfileForm sets instance.tenant if None
    unsaved_prof = CompetitorProfile(party=party)
    form_prof = CompetitorProfileForm(instance=unsaved_prof, tenant=tenant)
    assert unsaved_prof.tenant == tenant

    # OpportunityCompetitorForm sets instance.tenant and instance.opportunity if None
    opp = _opportunitypipeline_opportunity(tenant, name="Comp Inst Opp")
    comp_prof = _opportunitypipeline_competitor_profile(tenant, party=party)
    link = _opportunitypipeline_opportunity_competitor(tenant, opp, comp_prof)

    unsaved_link = OpportunityCompetitor(relationship="identified")
    form_link = OpportunityCompetitorForm(instance=unsaved_link, tenant=tenant, opportunity=opp)
    assert unsaved_link.tenant == tenant
    assert unsaved_link.opportunity == opp

    # Edit form with opportunity=None resolves from instance.opportunity
    form_link_res = OpportunityCompetitorForm(
        data=_opportunitypipeline_opportunity_competitor_payload(comp_prof, relationship="identified"),
        instance=link,
        tenant=tenant,
        opportunity=None,
    )
    assert form_link_res.is_valid(), form_link_res.errors

    # When instance has non-existent opportunity_id, ObjectDoesNotExist is handled
    ghost_link = OpportunityCompetitor(tenant=tenant, competitor_profile=comp_prof, relationship="identified")
    ghost_link.opportunity_id = 999999
    f_ghost = OpportunityCompetitorForm(instance=ghost_link, tenant=tenant, opportunity=None)
    f_ghost.cleaned_data = {}
    f_ghost.clean()
    assert "Choose an opportunity from this workspace." in str(f_ghost.errors)


def test_opportunitypipeline_win_loss_reason_instance_tenant_assignment(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    unsaved_reason = WinLossReason(name="Test Rsn", code="test_rsn")
    form = WinLossReasonForm(instance=unsaved_reason, tenant=tenant)
    assert unsaved_reason.tenant == tenant


def test_opportunitypipeline_transition_form_edge_cases_and_clean_branches(opportunitypipeline_tenant_a):
    tenant = opportunitypipeline_tenant_a
    pipe = _opportunitypipeline_pipeline(tenant, name="Branch Transition Pipe")
    s_open = _opportunitypipeline_stage(tenant, pipe, name="Discovery", sequence=10, stage_kind="open")
    s_inact_current = _opportunitypipeline_stage(tenant, pipe, name="Inactive Current", sequence=15, is_active=False)
    s_won = _opportunitypipeline_stage(tenant, pipe, name="Won", sequence=90, stage_kind="won", crm_stage_key="closed_won", probability=100, forecast_category="closed")

    opp = _opportunitypipeline_opportunity(tenant, name="Branch Opp")
    placement = _opportunitypipeline_placement(tenant, opp, pipe, s_open)

    # Inactive current stage makes context invalid
    placement_inact = _opportunitypipeline_placement(tenant, _opportunitypipeline_opportunity(tenant, name="Opp Inact"), pipe, s_inact_current)
    f_inact_curr = OpportunityTransitionForm(tenant=tenant, opportunity=placement_inact.opportunity, placement=placement_inact)
    assert not f_inact_curr._placement_valid

    # Placement with invalid stage_id handled
    placement.current_stage_id = 999999
    f_bad_stage_id = OpportunityTransitionForm(tenant=tenant, opportunity=opp, placement=placement)
    assert not f_bad_stage_id._placement_valid
    placement.current_stage_id = s_open.pk

    # Bound form with empty target_stage
    f_empty_target = OpportunityTransitionForm(data={"target_stage": ""}, tenant=tenant, opportunity=opp, placement=placement)
    assert not f_empty_target.is_valid()
    assert "target_stage" in f_empty_target.errors

    # Invalid stage_kind on target tested via clean()
    f_bad_kind = OpportunityTransitionForm(tenant=tenant, opportunity=opp, placement=placement)
    f_bad_kind.cleaned_data = {"target_stage": s_won}
    s_won.stage_kind = "unknown"
    f_bad_kind.clean()
    assert "Choose a valid pipeline stage." in str(f_bad_kind.errors["target_stage"])
    s_won.stage_kind = "won"

    # Won stage with inactive reason
    r_inact = _opportunitypipeline_win_loss_reason(tenant, name="Inactive Reason", result="won", is_active=False)
    f_inact_rsn = OpportunityTransitionForm(
        data=_opportunitypipeline_transition_payload(s_won, reason=r_inact),
        tenant=tenant,
        opportunity=opp,
        placement=placement,
    )
    f_inact_rsn.fields["reason"].queryset = WinLossReason.objects.all()
    assert not f_inact_rsn.is_valid()
    assert "Choose an active reason from this workspace." in str(f_inact_rsn.errors["reason"])

