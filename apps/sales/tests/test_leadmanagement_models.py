import json
from datetime import timedelta

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.sales.models import (
    LeadNurtureEnrollment,
    LeadQualification,
    LeadRoutingRule,
    LeadScoreEvent,
)
from apps.sales.models.LeadManagement.LeadRoutingRules import (
    ROUTING_FIELDS,
    ROUTING_OPERATORS,
    validate_routing_conditions,
)
from apps.sales.services import (
    activate_nurture,
    apply_qualification_decision,
    project_lead_score,
    recompute_lead_score,
    record_score_event,
    score_rating,
    transition_nurture,
)
from apps.sales.tests.conftest import (
    LEADMANAGEMENT_CHOICES,
    LEADMANAGEMENT_MODEL_FIELDS,
    LEADMANAGEMENT_ROUTING_FIELDS,
    LEADMANAGEMENT_ROUTING_OPERATORS,
    _leadmanagement_account,
    _leadmanagement_campaign,
    _leadmanagement_consent_purpose,
    _leadmanagement_email_campaign,
    _leadmanagement_lead,
    _leadmanagement_nurture_enrollment,
    _leadmanagement_opportunity,
    _leadmanagement_qualification,
    _leadmanagement_routing_rule,
    _leadmanagement_score_event,
    _leadmanagement_territory,
)

pytestmark = pytest.mark.django_db


def _leadmanagement_persisted_round_robin_rule(tenant, name, eligible_owners):
    rule = LeadRoutingRule.objects.create(
        tenant=tenant,
        name=name,
        conditions=[{"field": "status", "operator": "in", "value": ["new", "recycled"]}],
        assignment_mode="round_robin",
    )
    rule.eligible_owners.set(eligible_owners)
    return rule


def _leadmanagement_alternate_nurture_identity(tenant, owner):
    lead = _leadmanagement_lead(
        tenant,
        owner=owner,
        name="Alternate Nurture Lead",
        email="alternate@acme.example",
    )
    campaign = _leadmanagement_campaign(
        tenant,
        owner=owner,
        name="Alternate Nurture Campaign",
    )
    email_campaign = _leadmanagement_email_campaign(
        tenant,
        campaign,
        owner=owner,
        name="Alternate Drip Campaign",
    )
    consent_purpose = _leadmanagement_consent_purpose(
        tenant,
        name="Alternate Marketing Email",
        code="alternate-marketing-email",
    )
    return lead, email_campaign, consent_purpose


def _leadmanagement_add_baseline_score_event(tenant, lead):
    return _leadmanagement_score_event(
        tenant,
        lead,
        event_type="manual_adjustment",
        score_delta=25,
        source_ref="leadmanagement:baseline",
        reason="Baseline score fact for the test.",
    )


def test_leadmanagement_model_fields_match_contract():
    classes = {
        "LeadScoreEvent": LeadScoreEvent,
        "LeadQualification": LeadQualification,
        "LeadRoutingRule": LeadRoutingRule,
        "LeadNurtureEnrollment": LeadNurtureEnrollment,
    }
    for name, model in classes.items():
        actual_fields = tuple(
            field.name
            for field in model._meta.fields
            if not field.primary_key
        )
        assert actual_fields == LEADMANAGEMENT_MODEL_FIELDS[name]


@pytest.mark.parametrize(
    ("model_name", "expected_choices"),
    LEADMANAGEMENT_CHOICES.items(),
    ids=tuple(LEADMANAGEMENT_CHOICES),
)
def test_leadmanagement_model_choices_match_contract(model_name, expected_choices):
    model = apps.get_model("sales", model_name)
    for field_name, choices in expected_choices.items():
        actual = tuple(tuple(choice) for choice in model._meta.get_field(field_name).choices)
        assert actual == choices


def test_leadmanagement_field_validators_reject_out_of_range_values(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_routing_rule_a,
    leadmanagement_nurture_enrollment_a,
):
    for invalid_delta in (-101, 101):
        event = LeadScoreEvent(
            tenant=leadmanagement_tenant_a,
            lead=leadmanagement_lead_a,
            signal_category="behavioral",
            event_type="web_visit",
            score_delta=invalid_delta,
            source_kind="api",
        )
        with pytest.raises(ValidationError) as error:
            event.full_clean()
        assert "score_delta" in error.value.message_dict

    manual = LeadScoreEvent(
        tenant=leadmanagement_tenant_a,
        lead=leadmanagement_lead_a,
        signal_category="manual",
        event_type="manual_adjustment",
        score_delta=1,
        source_kind="manual",
        reason="",
    )
    with pytest.raises(ValidationError) as error:
        manual.full_clean()
    assert "reason" in error.value.message_dict

    leadmanagement_qualification_a.employee_count = 0
    with pytest.raises(ValidationError) as error:
        leadmanagement_qualification_a.full_clean()
    assert "employee_count" in error.value.message_dict

    leadmanagement_routing_rule_a.priority = 0
    with pytest.raises(ValidationError) as error:
        leadmanagement_routing_rule_a.full_clean()
    assert "priority" in error.value.message_dict

    leadmanagement_nurture_enrollment_a.score_at_enrollment = 101
    with pytest.raises(ValidationError) as error:
        leadmanagement_nurture_enrollment_a.full_clean()
    assert "score_at_enrollment" in error.value.message_dict


def test_leadmanagement_ownership_boundary_is_exactly_four_models():
    owned_models = {
        model._meta.object_name
        for model in apps.get_models(include_auto_created=False)
        if model._meta.app_label == "sales"
        and model.__module__.startswith("apps.sales.models.LeadManagement.")
    }
    assert owned_models == {
        "LeadScoreEvent",
        "LeadQualification",
        "LeadRoutingRule",
        "LeadNurtureEnrollment",
    }

    relation_contracts = {
        "LeadScoreEvent": {
            "lead": "crm.Lead",
            "corrects_event": "sales.LeadScoreEvent",
            "recorded_by": "accounts.User",
        },
        "LeadQualification": {
            "lead": "crm.Lead",
            "budget_currency": "accounting.Currency",
            "assessed_by": "accounts.User",
        },
        "LeadRoutingRule": {
            "default_owner": "accounts.User",
            "territory": "crm.Territory",
            "eligible_owners": "accounts.User",
            "fallback_owner": "accounts.User",
        },
        "LeadNurtureEnrollment": {
            "lead": "crm.Lead",
            "email_campaign": "crm.EmailCampaign",
            "consent_purpose": "core.ConsentPurpose",
            "owner": "accounts.User",
        },
    }
    for model_name, relations in relation_contracts.items():
        model = apps.get_model("sales", model_name)
        assert model._meta.get_field("tenant").related_model._meta.label == "core.Tenant"
        for field_name, expected_label in relations.items():
            field = model._meta.get_field(field_name)
            assert field.related_model._meta.label == expected_label

    assert LeadQualification._meta.get_field("lead").remote_field.field.one_to_one is True
    assert LeadScoreEvent._meta.get_field("lead").remote_field.field.one_to_one is False
    assert LeadNurtureEnrollment._meta.get_field("lead").remote_field.field.one_to_one is False
    assert LeadRoutingRule._meta.get_field("eligible_owners").remote_field.through._meta.auto_created is LeadRoutingRule

    for canonical_label in (
        "crm.Lead",
        "crm.Opportunity",
        "crm.Campaign",
        "crm.EmailCampaign",
        "crm.Territory",
        "crm.CrmTask",
        "core.Party",
        "core.ContactMethod",
        "core.PartyRole",
        "core.ConsentRecord",
        "accounts.User",
    ):
        model = apps.get_model(canonical_label)
        assert model._meta.app_label == canonical_label.split(".")[0]


def test_leadmanagement_score_idempotency_key_is_tenant_scoped(
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
):
    event_a = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        idempotency_key="shared-import-key",
    )
    event_b = _leadmanagement_score_event(
        leadmanagement_tenant_b,
        leadmanagement_lead_b,
        idempotency_key="shared-import-key",
    )
    assert event_a.pk != event_b.pk
    assert LeadScoreEvent.objects.filter(idempotency_key="shared-import-key").count() == 2


def test_leadmanagement_routing_rule_name_is_unique_per_tenant(
    leadmanagement_routing_rule_a,
    leadmanagement_routing_rule_b,
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
):
    assert leadmanagement_routing_rule_a.name == leadmanagement_routing_rule_b.name
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LeadRoutingRule.objects.create(
                tenant=leadmanagement_tenant_a,
                name=leadmanagement_routing_rule_a.name,
                conditions=[{"field": "status", "operator": "eq", "value": "new"}],
                assignment_mode="fixed_owner",
                default_owner=leadmanagement_admin_a,
            )


def test_leadmanagement_nurture_identity_and_number_are_tenant_scoped(
    leadmanagement_nurture_enrollment_a,
    leadmanagement_nurture_enrollment_b,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_admin_a,
):
    assert leadmanagement_nurture_enrollment_a.number == "LNE-00001"
    assert leadmanagement_nurture_enrollment_b.number == "LNE-00001"

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LeadNurtureEnrollment.objects.create(
                tenant=leadmanagement_tenant_a,
                lead=leadmanagement_lead_a,
                email_campaign=leadmanagement_email_campaign_a,
                consent_purpose=leadmanagement_consent_purpose_a,
            )

    alternate_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=leadmanagement_admin_a,
        name="Number collision lead",
        email="number-collision@acme.example",
    )
    alternate_campaign = _leadmanagement_campaign(
        leadmanagement_tenant_a,
        owner=leadmanagement_admin_a,
        name="Number collision campaign",
    )
    alternate_email_campaign = _leadmanagement_email_campaign(
        leadmanagement_tenant_a,
        alternate_campaign,
        owner=leadmanagement_admin_a,
        name="Number collision drip",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LeadNurtureEnrollment.objects.create(
                tenant=leadmanagement_tenant_a,
                lead=alternate_lead,
                email_campaign=alternate_email_campaign,
                consent_purpose=leadmanagement_consent_purpose_a,
                number=leadmanagement_nurture_enrollment_a.number,
            )


def test_leadmanagement_qualification_is_one_current_assessment_per_lead(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
):
    separate_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=leadmanagement_admin_a,
        name="Separate qualification lead",
        email="separate-qualification@acme.example",
    )
    LeadQualification.objects.create(
        tenant=leadmanagement_tenant_a,
        lead=separate_lead,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LeadQualification.objects.create(
                tenant=leadmanagement_tenant_a,
                lead=separate_lead,
            )


def test_leadmanagement_score_projection_sums_clamps_and_updates_rating(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
):
    _leadmanagement_add_baseline_score_event(leadmanagement_tenant_a, leadmanagement_lead_a)
    _leadmanagement_score_event(leadmanagement_tenant_a, leadmanagement_lead_a, event_type="form_submitted")
    _leadmanagement_score_event(leadmanagement_tenant_a, leadmanagement_lead_a, event_type="demo_request")
    leadmanagement_lead_a.refresh_from_db()
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (45, "warm")

    _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        event_type="manual_adjustment",
        score_delta=100,
        reason="Promote a high-fit account.",
    )
    leadmanagement_lead_a.refresh_from_db()
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (100, "hot")

    for event_type in ("email_click", "fit_match", "unsubscribe"):
        _leadmanagement_score_event(leadmanagement_tenant_a, leadmanagement_lead_a, event_type=event_type)
    leadmanagement_lead_a.refresh_from_db()
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (100, "hot")

    _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        event_type="manual_adjustment",
        score_delta=-100,
        reason="Reset an invalid score.",
    )
    leadmanagement_lead_a.refresh_from_db()
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (48, "warm")

    _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        event_type="manual_adjustment",
        score_delta=-100,
        reason="Reset the remaining score.",
    )
    leadmanagement_lead_a.refresh_from_db()
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (0, "cold")


@pytest.mark.parametrize(
    ("score", "rating"),
    ((0, "cold"), (39, "cold"), (40, "warm"), (69, "warm"), (70, "hot"), (100, "hot")),
)
def test_leadmanagement_score_projection_bands(score, rating):
    assert score_rating(score) == rating


def test_leadmanagement_score_projection_excludes_future_and_expired_events(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
):
    _leadmanagement_add_baseline_score_event(leadmanagement_tenant_a, leadmanagement_lead_a)
    now = timezone.now()
    active_event = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        event_type="manual_adjustment",
        score_delta=10,
        reason="Temporarily active score.",
        effective_until=now + timedelta(hours=1),
    )
    future_time = now + timedelta(days=1)
    LeadScoreEvent.objects.create(
        tenant=leadmanagement_tenant_a,
        lead=leadmanagement_lead_a,
        signal_category="behavioral",
        event_type="demo_request",
        score_delta=20,
        source_kind="web_tracking",
        occurred_at=future_time,
    )
    LeadScoreEvent.objects.filter(pk=active_event.pk).update(effective_until=now - timedelta(seconds=1))

    assert recompute_lead_score(leadmanagement_lead_a, leadmanagement_tenant_a, None) == 25
    assert project_lead_score(
        leadmanagement_lead_a,
        leadmanagement_tenant_a,
        at=future_time + timedelta(seconds=1),
    ) == 45


def test_leadmanagement_score_idempotency_replays_only_identical_payloads(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
):
    first = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        idempotency_key="lead-form-42",
    )
    replay = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        idempotency_key="lead-form-42",
    )
    assert replay.pk == first.pk
    assert LeadScoreEvent.objects.filter(idempotency_key="lead-form-42").count() == 1

    with pytest.raises(ValidationError, match="different score event"):
        _leadmanagement_score_event(
            leadmanagement_tenant_a,
            leadmanagement_lead_a,
            event_type="web_visit",
            idempotency_key="lead-form-42",
        )
    assert LeadScoreEvent.objects.filter(idempotency_key="lead-form-42").count() == 1


def test_leadmanagement_score_correction_is_inverse_append_only_and_single_use(
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_admin_a,
):
    _leadmanagement_add_baseline_score_event(leadmanagement_tenant_a, leadmanagement_lead_a)
    original = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        event_type="form_submitted",
    )
    with pytest.raises(ValidationError, match="inverse score delta"):
        record_score_event(
            leadmanagement_lead_a,
            leadmanagement_tenant_a,
            event_type="correction",
            score_delta=-4,
            reason="Correct an invalid import.",
            recorded_by=leadmanagement_admin_a,
            corrects_event=original,
        )

    correction = _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        recorded_by=leadmanagement_admin_a,
        event_type="correction",
        score_delta=-5,
        reason="Reverse a duplicate form submission.",
        idempotency_key="correct-form-42",
        corrects_event=original,
    )
    assert correction.corrects_event == original
    leadmanagement_lead_a.refresh_from_db()
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (25, "cold")

    with pytest.raises(ValidationError, match="already been corrected"):
        _leadmanagement_score_event(
            leadmanagement_tenant_a,
            leadmanagement_lead_a,
            recorded_by=leadmanagement_admin_a,
            event_type="correction",
            score_delta=-5,
            reason="Attempt a second correction.",
            corrects_event=original,
        )

    with pytest.raises(ValidationError, match="does not belong"):
        record_score_event(
            leadmanagement_lead_b,
            leadmanagement_tenant_b,
            event_type="correction",
            score_delta=-5,
            reason="Cross-tenant correction attempt.",
            recorded_by=leadmanagement_admin_a,
            corrects_event=original,
        )


def test_leadmanagement_qualification_transition_compensates_prior_fit_event(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_qualification_a,
    leadmanagement_lead_a,
):
    _leadmanagement_add_baseline_score_event(leadmanagement_tenant_a, leadmanagement_lead_a)
    qualified = apply_qualification_decision(
        leadmanagement_qualification_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        status="qualified",
    )
    assert qualified.status == "qualified"
    assert qualified.assessed_by == leadmanagement_admin_a
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.status == "qualified"
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (45, "warm")

    disqualified = apply_qualification_decision(
        qualified,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        status="disqualified",
        disqualification_reason="No viable buying budget.",
    )
    assert disqualified.status == "disqualified"
    leadmanagement_lead_a.refresh_from_db()
    assert leadmanagement_lead_a.status == "unqualified"
    assert (leadmanagement_lead_a.score, leadmanagement_lead_a.rating) == (10, "cold")

    events = list(
        LeadScoreEvent.objects.filter(
            tenant=leadmanagement_tenant_a,
            lead=leadmanagement_lead_a,
            source_kind="qualification",
        ).order_by("pk")
    )
    assert [event.score_delta for event in events] == [20, -20, -15]
    assert events[1].source_ref.endswith(f":compensate:{events[0].pk}")
    assert sum(event.score_delta for event in events) == -15

    replay = apply_qualification_decision(
        disqualified,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        status="disqualified",
        disqualification_reason="No viable buying budget.",
    )
    assert replay.pk == disqualified.pk
    assert LeadScoreEvent.objects.filter(source_kind="qualification").count() == 3


def test_leadmanagement_bant_qualification_requires_complete_buying_evidence(
    leadmanagement_qualification_a,
    leadmanagement_admin_a,
):
    leadmanagement_qualification_a.status = "qualified"
    leadmanagement_qualification_a.assessed_by = leadmanagement_admin_a
    leadmanagement_qualification_a.need_summary = ""
    leadmanagement_qualification_a.expected_purchase_on = None
    leadmanagement_qualification_a.budget_status = "unknown"
    leadmanagement_qualification_a.authority_level = "unknown"

    with pytest.raises(ValidationError) as error:
        leadmanagement_qualification_a.full_clean()
    assert set(error.value.message_dict) == {
        "need_summary",
        "expected_purchase_on",
        "budget_status",
        "authority_level",
    }


def test_leadmanagement_meddic_qualification_requires_buying_committee_evidence(
    leadmanagement_qualification_a,
    leadmanagement_admin_a,
):
    leadmanagement_qualification_a.framework = "both"
    leadmanagement_qualification_a.status = "qualified"
    leadmanagement_qualification_a.assessed_by = leadmanagement_admin_a
    leadmanagement_qualification_a.economic_buyer = ""
    leadmanagement_qualification_a.decision_criteria = ""
    leadmanagement_qualification_a.decision_process = ""

    with pytest.raises(ValidationError) as error:
        leadmanagement_qualification_a.full_clean()
    assert set(error.value.message_dict) == {
        "economic_buyer",
        "decision_criteria",
        "decision_process",
    }


def test_leadmanagement_qualification_normalizes_country_and_requires_budget_currency(
    leadmanagement_currency,
    leadmanagement_qualification_a,
):
    leadmanagement_qualification_a.country_code = " us "
    leadmanagement_qualification_a.budget_currency = None
    with pytest.raises(ValidationError) as error:
        leadmanagement_qualification_a.full_clean()
    assert leadmanagement_qualification_a.country_code == "US"
    assert "budget_currency" in error.value.message_dict

    leadmanagement_qualification_a.budget_currency = leadmanagement_currency
    leadmanagement_qualification_a.full_clean()


def test_leadmanagement_disqualified_assessment_requires_reason_and_terminal_metadata(
    leadmanagement_qualification_a,
    leadmanagement_admin_a,
):
    leadmanagement_qualification_a.status = "disqualified"
    leadmanagement_qualification_a.assessed_by = leadmanagement_admin_a
    leadmanagement_qualification_a.disqualification_reason = ""
    with pytest.raises(ValidationError) as error:
        leadmanagement_qualification_a.full_clean()
    assert "disqualification_reason" in error.value.message_dict

    leadmanagement_qualification_a.disqualification_reason = "No budget authority."
    leadmanagement_qualification_a.full_clean()
    leadmanagement_qualification_a.save()
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.assessed_at is not None
    assert leadmanagement_qualification_a.is_terminal is True


@pytest.mark.parametrize("status", ("qualified", "disqualified", "archived"))
def test_leadmanagement_terminal_qualification_requires_assessor(
    leadmanagement_qualification_a,
    status,
):
    leadmanagement_qualification_a.status = status
    leadmanagement_qualification_a.assessed_by = None
    leadmanagement_qualification_a.disqualification_reason = "No viable budget."
    with pytest.raises(ValidationError) as error:
        leadmanagement_qualification_a.full_clean()
    assert "assessed_by" in error.value.message_dict


def test_leadmanagement_archived_qualification_cannot_be_reopened(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_currency,
    leadmanagement_admin_a,
):
    qualification = _leadmanagement_qualification(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        leadmanagement_currency,
        assessed_by=leadmanagement_admin_a,
        status="archived",
    )
    qualification.status = "partially_qualified"
    with pytest.raises(ValidationError, match="cannot be reopened"):
        qualification.save()
    qualification.refresh_from_db()
    assert qualification.status == "archived"

    with pytest.raises(ValidationError, match="cannot be reopened"):
        apply_qualification_decision(
            qualification,
            leadmanagement_tenant_a,
            leadmanagement_admin_a,
            status="partially_qualified",
        )


def test_leadmanagement_converted_lead_cannot_be_requalified(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_admin_a,
):
    leadmanagement_lead_a.status = "converted"
    leadmanagement_lead_a.save(update_fields=["status", "updated_at"])

    with pytest.raises(ValidationError, match="converted lead"):
        apply_qualification_decision(
            leadmanagement_qualification_a,
            leadmanagement_tenant_a,
            leadmanagement_admin_a,
            status="qualified",
        )
    leadmanagement_qualification_a.refresh_from_db()
    assert leadmanagement_qualification_a.status == "unassessed"


def test_leadmanagement_qualification_relations_are_tenant_locked(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_admin_b,
):
    with pytest.raises(ValidationError) as error:
        LeadQualification(
            tenant=leadmanagement_tenant_a,
            lead=leadmanagement_lead_b,
        ).full_clean()
    assert "lead" in error.value.message_dict

    with pytest.raises(ValidationError) as error:
        LeadQualification(
            tenant=leadmanagement_tenant_a,
            lead=leadmanagement_lead_a,
            assessed_by=leadmanagement_admin_b,
        ).full_clean()
    assert "assessed_by" in error.value.message_dict


def test_leadmanagement_routing_validator_accepts_only_bounded_allowlisted_conditions():
    assert ROUTING_FIELDS == set(LEADMANAGEMENT_ROUTING_FIELDS)
    assert ROUTING_OPERATORS == set(LEADMANAGEMENT_ROUTING_OPERATORS)

    conditions = [
        {"field": "status", "operator": "in", "value": ["new", "recycled"]},
        {"field": "score", "operator": "gte", "value": 40},
        {"field": "email_present", "operator": "is_set", "value": True},
    ]
    assert validate_routing_conditions(conditions) == conditions
    assert validate_routing_conditions(json.dumps(conditions)) == conditions
    assert validate_routing_conditions([], is_catch_all=True) == []

    twenty_conditions = [
        {"field": "status", "operator": "eq", "value": "new"}
        for _ in range(20)
    ]
    assert validate_routing_conditions(twenty_conditions) == twenty_conditions


@pytest.mark.parametrize(
    "conditions",
    (
        "not-json",
        {"field": "status", "operator": "eq", "value": "new"},
        [],
        [{"field": "status", "operator": "eq"}],
        [{"field": "status", "operator": "eq", "value": "new", "extra": True}],
        [{"field": "owner__tenant_id", "operator": "eq", "value": 1}],
        [{"field": "status", "operator": "eval", "value": "new"}],
        [{"field": "status", "operator": "in", "value": [["nested"]]}],
        [{"field": "company", "operator": "icontains", "value": "x" * 256}],
        [{"field": "status", "operator": "in", "value": [str(index) for index in range(21)]}],
        [{"field": "email_present", "operator": "is_set", "value": "true"}],
        [{"field": "score", "operator": "eq", "value": float("nan")}],
        [{"field": "company", "operator": "icontains", "value": "x" * 17_000}],
        [
            {"field": "status", "operator": "eq", "value": "new"}
            for _ in range(21)
        ],
    ),
    ids=(
        "malformed-json",
        "not-list",
        "empty-not-catch-all",
        "missing-key",
        "extra-key",
        "unsupported-field",
        "unsupported-operator",
        "nested-value",
        "overlong-scalar",
        "oversized-list",
        "invalid-set-value",
        "non-finite-number",
        "over-16-kib",
        "over-20-conditions",
    ),
)
def test_leadmanagement_routing_validator_rejects_unsafe_conditions(conditions):
    with pytest.raises(ValidationError):
        validate_routing_conditions(conditions)


def test_leadmanagement_routing_direct_owner_must_be_active_and_same_tenant(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
):
    rule = LeadRoutingRule(
        tenant=leadmanagement_tenant_a,
        name="Missing fixed owner",
        conditions=[{"field": "status", "operator": "eq", "value": "new"}],
        assignment_mode="fixed_owner",
    )
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "default_owner" in error.value.message_dict

    rule.default_owner = leadmanagement_admin_b
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "default_owner" in error.value.message_dict

    leadmanagement_admin_a.is_active = False
    leadmanagement_admin_a.save(update_fields=["is_active"])
    rule.default_owner = leadmanagement_admin_a
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "default_owner" in error.value.message_dict


def test_leadmanagement_routing_fallback_owner_must_be_same_tenant(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
):
    rule = LeadRoutingRule(
        tenant=leadmanagement_tenant_a,
        name="Cross-tenant fallback",
        conditions=[{"field": "status", "operator": "eq", "value": "new"}],
        assignment_mode="fixed_owner",
        default_owner=leadmanagement_admin_a,
        fallback_owner=leadmanagement_admin_b,
    )
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "fallback_owner" in error.value.message_dict


def test_leadmanagement_round_robin_eligible_owners_are_active_and_same_tenant(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
):
    rule = _leadmanagement_persisted_round_robin_rule(
        leadmanagement_tenant_a,
        "Cross-tenant round robin",
        (leadmanagement_admin_a, leadmanagement_admin_b),
    )
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "eligible_owners" in error.value.message_dict

    rule.eligible_owners.set((leadmanagement_admin_a,))
    rule.full_clean()

    leadmanagement_admin_a.is_active = False
    leadmanagement_admin_a.save(update_fields=["is_active"])
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "eligible_owners" in error.value.message_dict


def test_leadmanagement_territory_manager_must_be_same_tenant_active_and_present(
    leadmanagement_tenant_a,
    leadmanagement_territory_b,
    leadmanagement_admin_a,
):
    territory_without_manager = _leadmanagement_territory(
        leadmanagement_tenant_a,
        manager=None,
        name="Territory without manager",
    )
    rule = LeadRoutingRule(
        tenant=leadmanagement_tenant_a,
        name="Territory manager required",
        conditions=[{"field": "status", "operator": "eq", "value": "new"}],
        assignment_mode="territory_manager",
        territory=territory_without_manager,
    )
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "territory" in error.value.message_dict

    rule.territory = leadmanagement_territory_b
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "territory" in error.value.message_dict

    rule.territory = territory_without_manager
    territory_without_manager.manager = leadmanagement_admin_a
    territory_without_manager.save(update_fields=["manager"])
    leadmanagement_admin_a.is_active = False
    leadmanagement_admin_a.save(update_fields=["is_active"])
    with pytest.raises(ValidationError) as error:
        rule.full_clean()
    assert "territory" in error.value.message_dict


def test_leadmanagement_nurture_model_requires_drip_campaign_and_same_tenant_relations(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_email_campaign_a,
    leadmanagement_email_campaign_b,
    leadmanagement_consent_purpose_a,
    leadmanagement_consent_purpose_b,
    leadmanagement_admin_b,
):
    base = {
        "tenant": leadmanagement_tenant_a,
        "lead": leadmanagement_lead_a,
        "email_campaign": leadmanagement_email_campaign_a,
        "consent_purpose": leadmanagement_consent_purpose_a,
    }
    cross_tenant_cases = (
        ("lead", {**base, "lead": leadmanagement_lead_b}),
        ("email_campaign", {**base, "email_campaign": leadmanagement_email_campaign_b}),
        ("consent_purpose", {**base, "consent_purpose": leadmanagement_consent_purpose_b}),
        ("owner", {**base, "owner": leadmanagement_admin_b}),
    )
    for field_name, values in cross_tenant_cases:
        with pytest.raises(ValidationError) as error:
            LeadNurtureEnrollment(**values).full_clean()
        assert field_name in error.value.message_dict

    one_time_campaign = leadmanagement_email_campaign_a
    one_time_campaign.send_type = "one_time"
    with pytest.raises(ValidationError) as error:
        LeadNurtureEnrollment(**base).full_clean()
    assert "email_campaign" in error.value.message_dict


def test_leadmanagement_nurture_activation_snapshots_state(
    leadmanagement_tenant_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_admin_a,
):
    _leadmanagement_add_baseline_score_event(leadmanagement_tenant_a, leadmanagement_nurture_enrollment_a.lead)
    next_touch = timezone.now() + timedelta(days=5)
    activated = activate_nurture(
        leadmanagement_nurture_enrollment_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        next_touch_at=next_touch,
    )
    activated.refresh_from_db()
    assert activated.status == "active"
    assert activated.started_at is not None
    assert activated.score_at_enrollment == 25
    assert activated.next_touch_at == next_touch
    assert activated.touch_count == 0
    assert activated.exit_reason == ""


def test_leadmanagement_nurture_activation_requires_admin_and_optional_consent_evidence(
    leadmanagement_tenant_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_admin_a,
    leadmanagement_member_a,
):
    with pytest.raises(ValidationError, match="administrator"):
        activate_nurture(
            leadmanagement_nurture_enrollment_a,
            leadmanagement_tenant_a,
            leadmanagement_member_a,
        )

    leadmanagement_nurture_enrollment_a.consent_evidence = ""
    leadmanagement_nurture_enrollment_a.save(update_fields=["consent_evidence", "updated_at"])
    with pytest.raises(ValidationError, match="Consent evidence"):
        activate_nurture(
            leadmanagement_nurture_enrollment_a,
            leadmanagement_tenant_a,
            leadmanagement_admin_a,
        )
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "pending"


def test_leadmanagement_nurture_activation_rejects_inactive_purpose_and_converted_lead(
    leadmanagement_tenant_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_lead_a,
    leadmanagement_admin_a,
):
    leadmanagement_consent_purpose_a.is_active = False
    leadmanagement_consent_purpose_a.save(update_fields=["is_active"])
    with pytest.raises(ValidationError, match="active consent purpose"):
        activate_nurture(
            leadmanagement_nurture_enrollment_a,
            leadmanagement_tenant_a,
            leadmanagement_admin_a,
        )

    leadmanagement_consent_purpose_a.is_active = True
    leadmanagement_consent_purpose_a.save(update_fields=["is_active"])
    leadmanagement_lead_a.status = "converted"
    leadmanagement_lead_a.save(update_fields=["status", "updated_at"])
    with pytest.raises(ValidationError, match="converted lead"):
        activate_nurture(
            leadmanagement_nurture_enrollment_a,
            leadmanagement_tenant_a,
            leadmanagement_admin_a,
        )
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.status == "pending"


def test_leadmanagement_nurture_lifecycle_pause_resume_and_complete(
    leadmanagement_tenant_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_admin_a,
):
    _leadmanagement_add_baseline_score_event(leadmanagement_tenant_a, leadmanagement_nurture_enrollment_a.lead)
    active = activate_nurture(
        leadmanagement_nurture_enrollment_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    started_at = active.started_at
    paused = transition_nurture(
        active,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        "paused",
    )
    assert paused.status == "paused"
    assert paused.exit_reason == ""

    resumed = transition_nurture(
        paused,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        "active",
    )
    assert resumed.status == "active"
    assert resumed.started_at == started_at
    assert resumed.score_at_enrollment == 25

    completed = transition_nurture(
        resumed,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        "completed",
        exit_reason="completed",
        notes="All drip steps delivered.",
    )
    assert completed.status == "completed"
    assert completed.exit_reason == "completed"
    assert completed.notes == "All drip steps delivered."
    assert completed.completed_at is not None


@pytest.mark.parametrize(
    ("status", "invalid_reason"),
    (
        ("completed", "qualified"),
        ("cancelled", "converted"),
        ("replied", "completed"),
        ("converted", "qualified"),
    ),
)
def test_leadmanagement_nurture_model_rejects_incompatible_exit_reasons(
    leadmanagement_nurture_enrollment_a,
    status,
    invalid_reason,
):
    leadmanagement_nurture_enrollment_a.status = status
    leadmanagement_nurture_enrollment_a.exit_reason = invalid_reason
    with pytest.raises(ValidationError) as error:
        leadmanagement_nurture_enrollment_a.full_clean()
    assert "exit_reason" in error.value.message_dict


@pytest.mark.parametrize(
    ("status", "reason"),
    (
        ("completed", "completed"),
        ("cancelled", "qualified"),
        ("replied", "replied"),
        ("converted", "converted"),
    ),
)
def test_leadmanagement_nurture_model_accepts_compatible_exit_reasons(
    leadmanagement_nurture_enrollment_a,
    status,
    reason,
):
    leadmanagement_nurture_enrollment_a.status = status
    leadmanagement_nurture_enrollment_a.exit_reason = reason
    leadmanagement_nurture_enrollment_a.full_clean()


def test_leadmanagement_nurture_identity_locks_after_activation(
    leadmanagement_tenant_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_member_a,
    leadmanagement_admin_a,
):
    alternate_lead, alternate_campaign, alternate_purpose = _leadmanagement_alternate_nurture_identity(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    activate_nurture(
        leadmanagement_nurture_enrollment_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )

    identity_changes = (
        ("lead", alternate_lead),
        ("email_campaign", alternate_campaign),
        ("consent_purpose", alternate_purpose),
        ("owner", leadmanagement_member_a),
        ("consent_evidence", "Updated evidence reference."),
    )
    for field_name, replacement in identity_changes:
        leadmanagement_nurture_enrollment_a.refresh_from_db()
        setattr(leadmanagement_nurture_enrollment_a, field_name, replacement)
        with pytest.raises(ValidationError, match="identity is fixed") as error:
            leadmanagement_nurture_enrollment_a.save()
        assert "lead" in error.value.message_dict

    leadmanagement_nurture_enrollment_a.refresh_from_db()
    original_lead_id = leadmanagement_nurture_enrollment_a.lead_id
    leadmanagement_nurture_enrollment_a.notes = "Operational notes may change."
    leadmanagement_nurture_enrollment_a.save()
    leadmanagement_nurture_enrollment_a.refresh_from_db()
    assert leadmanagement_nurture_enrollment_a.lead_id == original_lead_id
    assert leadmanagement_nurture_enrollment_a.notes == "Operational notes may change."


def test_leadmanagement_nurture_conversion_exit_requires_verified_crm_opportunity(
    leadmanagement_tenant_a,
    leadmanagement_nurture_enrollment_a,
    leadmanagement_lead_a,
    leadmanagement_admin_a,
    leadmanagement_currency,
):
    activate_nurture(
        leadmanagement_nurture_enrollment_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    leadmanagement_lead_a.status = "converted"
    leadmanagement_lead_a.save(update_fields=["status", "updated_at"])

    with pytest.raises(ValidationError, match="verified CRM conversion"):
        transition_nurture(
            leadmanagement_nurture_enrollment_a,
            leadmanagement_tenant_a,
            leadmanagement_admin_a,
            "converted",
            exit_reason="converted",
        )

    account = _leadmanagement_account(leadmanagement_tenant_a, name="Conversion Verification Account")
    opportunity = _leadmanagement_opportunity(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        account,
        currency=leadmanagement_currency,
        owner=leadmanagement_admin_a,
    )
    converted = transition_nurture(
        leadmanagement_nurture_enrollment_a,
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
        "converted",
        exit_reason="converted",
    )
    assert converted.status == "converted"
    assert converted.exit_reason == "converted"
    assert converted.completed_at is not None
    assert converted.email_campaign_id == leadmanagement_nurture_enrollment_a.email_campaign_id
    assert opportunity.source_lead_id == leadmanagement_lead_a.pk
