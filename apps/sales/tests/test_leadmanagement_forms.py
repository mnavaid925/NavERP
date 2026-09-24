import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounting.models import Currency
from apps.crm.models import Lead
from apps.sales import forms as sales_forms
from apps.sales.models import (
    LeadNurtureEnrollment,
    LeadQualification,
    LeadRoutingRule,
    LeadScoreEvent,
)
from apps.sales.services import activate_nurture
from apps.sales.tests.conftest import (
    LEADMANAGEMENT_DECISION_STATUSES,
    LEADMANAGEMENT_FORM_FIELDS,
    _leadmanagement_campaign,
    _leadmanagement_consent_purpose,
    _leadmanagement_email_campaign,
    _leadmanagement_lead,
    _leadmanagement_qualification,
    _leadmanagement_score_event,
    _leadmanagement_territory,
)


pytestmark = pytest.mark.django_db

_LEADMANAGEMENT_FOREIGN_ERROR = "That record belongs to another workspace."


def _leadmanagement_day(offset=0):
    return (timezone.localdate() + timedelta(days=offset)).isoformat()


def _leadmanagement_score_payload(lead, score_delta=0, reason="Deterministic form evidence."):
    return {
        "lead": str(lead.pk),
        "score_delta": str(score_delta),
        "reason": reason,
    }


def _leadmanagement_correction_payload(lead, event, score_delta, reason="Reverse an invalid event."):
    return {
        "lead": str(lead.pk),
        "corrects_event": str(event.pk),
        "score_delta": str(score_delta),
        "reason": reason,
    }


def _leadmanagement_qualification_payload(lead, **overrides):
    data = {
        "lead": str(lead.pk) if lead is not None else "",
        "framework": "bant",
        "country_code": "US",
        "region": "North",
        "city": "Springfield",
        "industry": "Industrial Technology",
        "employee_count": "240",
        "seniority": "director",
        "budget_status": "confirmed",
        "budget_amount": "75000.00",
        "budget_currency": "",
        "authority_level": "director",
        "need_summary": "Replace fragmented lead intake.",
        "expected_purchase_on": _leadmanagement_day(45),
        "economic_buyer": "Operations Director",
        "decision_criteria": "Time to value and adoption.",
        "decision_process": "Director review and finance approval.",
        "technical_requirements": "CRM integration and role-based access.",
        "pain_points": "Slow routing and inconsistent evidence.",
        "success_metrics": "Reduce response time and improve conversion.",
        "next_review_on": _leadmanagement_day(14),
        "notes": "Deterministic qualification form payload.",
    }
    data.update(overrides)
    return data


def _leadmanagement_routing_payload(
    name="Form routing rule",
    default_owner=None,
    territory=None,
    eligible_owners=(),
    fallback_owner=None,
    **overrides,
):
    data = {
        "name": name,
        "description": "Deterministic routing form payload.",
        "is_active": "on",
        "priority": "10",
        "match_mode": "all",
        "conditions": json.dumps([{"field": "status", "operator": "eq", "value": "new"}]),
        "is_catch_all": "",
        "assignment_mode": "round_robin",
        "default_owner": str(default_owner.pk) if default_owner is not None else "",
        "territory": str(territory.pk) if territory is not None else "",
        "eligible_owners": [str(owner.pk) for owner in eligible_owners],
        "fallback_owner": str(fallback_owner.pk) if fallback_owner is not None else "",
        "max_open_leads": "25",
    }
    data.update(overrides)
    return data


def _leadmanagement_nurture_payload(
    lead,
    email_campaign,
    consent_purpose=None,
    owner=None,
    **overrides,
):
    data = {
        "lead": str(lead.pk),
        "email_campaign": str(email_campaign.pk),
        "trigger_kind": "manual",
        "consent_purpose": str(consent_purpose.pk) if consent_purpose is not None else "",
        "consent_evidence": "Consent reference captured by the form test.",
        "owner": str(owner.pk) if owner is not None else "",
        "notes": "Deterministic nurture form payload.",
    }
    data.update(overrides)
    return data


def _leadmanagement_widen(form, field_name, queryset):
    form.fields[field_name].queryset = queryset
    return form


def _leadmanagement_alternate_nurture_identity(tenant, owner):
    lead = _leadmanagement_lead(
        tenant,
        owner=owner,
        name="Alternate Nurture Identity Lead",
        email="alternate-nurture-identity@acme.example",
    )
    campaign = _leadmanagement_campaign(
        tenant,
        owner=owner,
        name="Alternate Nurture Identity Campaign",
    )
    email_campaign = _leadmanagement_email_campaign(
        tenant,
        campaign,
        owner=owner,
        name="Alternate Nurture Identity Drip",
    )
    consent_purpose = _leadmanagement_consent_purpose(
        tenant,
        name="Alternate Nurture Identity Purpose",
        code="alternate-nurture-identity",
    )
    return lead, email_campaign, consent_purpose


def test_leadmanagement_forms_expose_exact_contract_fields():
    for name, expected_fields in LEADMANAGEMENT_FORM_FIELDS.items():
        form_class = getattr(sales_forms, name)
        assert tuple(form_class.base_fields) == expected_fields
        if getattr(getattr(form_class, "_meta", None), "model", None) is not None:
            assert tuple(form_class._meta.fields) == expected_fields

    assert tuple(
        sales_forms.LeadQualificationDecisionForm.base_fields["status"].choices
    ) == tuple(LEADMANAGEMENT_DECISION_STATUSES)

    excluded_fields = {
        sales_forms.LeadQualificationForm: {
            "tenant", "status", "disqualification_reason", "assessed_by", "assessed_at",
            "created_at", "updated_at", "id",
        },
        sales_forms.LeadRoutingRuleForm: {
            "tenant", "cursor", "last_assigned_owner", "last_assigned_at", "created_at",
            "updated_at", "id",
        },
        sales_forms.LeadNurtureEnrollmentForm: {
            "tenant", "number", "status", "score_at_enrollment", "started_at", "last_touch_at",
            "next_touch_at", "touch_count", "completed_at", "exit_reason", "created_at",
            "updated_at", "id",
        },
    }
    for form_class, excluded in excluded_fields.items():
        assert not excluded.intersection(form_class.base_fields)


def test_leadmanagement_forms_use_closed_model_and_action_choices(leadmanagement_tenant_a):
    qualification = sales_forms.LeadQualificationForm(tenant=leadmanagement_tenant_a)
    for field_name, expected in {
        "framework": LeadQualification.FRAMEWORK_CHOICES,
        "seniority": LeadQualification.SENIORITY_CHOICES,
        "budget_status": LeadQualification.BUDGET_STATUS_CHOICES,
        "authority_level": LeadQualification.AUTHORITY_LEVEL_CHOICES,
    }.items():
        assert tuple(qualification.fields[field_name].choices) == tuple(expected)

    routing = sales_forms.LeadRoutingRuleForm(tenant=leadmanagement_tenant_a)
    assert tuple(routing.fields["match_mode"].choices) == tuple(LeadRoutingRule.MATCH_MODE_CHOICES)
    assert tuple(
        choice for choice in routing.fields["assignment_mode"].choices if choice[0]
    ) == tuple(LeadRoutingRule.ASSIGNMENT_MODE_CHOICES)

    nurture = sales_forms.LeadNurtureEnrollmentForm(tenant=leadmanagement_tenant_a)
    assert tuple(nurture.fields["trigger_kind"].choices) == tuple(LeadNurtureEnrollment.TRIGGER_KIND_CHOICES)

    decision = sales_forms.LeadQualificationDecisionForm(tenant=leadmanagement_tenant_a)
    assert tuple(decision.fields["status"].choices) == tuple(LEADMANAGEMENT_DECISION_STATUSES)

    expected_exit_choices = {
        "completed": ("completed",),
        "cancelled": ("qualified", "disqualified", "unsubscribed", "bounced", "cancelled", "manual"),
        "replied": ("replied",),
        "converted": ("converted",),
    }
    for target_status, expected_values in expected_exit_choices.items():
        form = sales_forms.LeadNurtureExitForm(
            tenant=leadmanagement_tenant_a,
            target_status=target_status,
        )
        assert tuple(value for value, _label in form.fields["exit_reason"].choices) == expected_values


def test_leadmanagement_forms_scope_tenant_owned_querysets(
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_score_event_a,
    leadmanagement_score_event_b,
    leadmanagement_territory_a,
    leadmanagement_territory_b,
    leadmanagement_email_campaign_a,
    leadmanagement_email_campaign_b,
    leadmanagement_consent_purpose_a,
    leadmanagement_consent_purpose_b,
    leadmanagement_campaign_a,
):
    adjustment = sales_forms.LeadScoreAdjustmentForm(tenant=leadmanagement_tenant_a)
    assert leadmanagement_lead_a in adjustment.fields["lead"].queryset
    assert leadmanagement_lead_b not in adjustment.fields["lead"].queryset

    correction = sales_forms.LeadScoreCorrectionForm(tenant=leadmanagement_tenant_a)
    assert leadmanagement_lead_a in correction.fields["lead"].queryset
    assert leadmanagement_lead_b not in correction.fields["lead"].queryset
    assert leadmanagement_score_event_a in correction.fields["corrects_event"].queryset
    assert leadmanagement_score_event_b not in correction.fields["corrects_event"].queryset

    for form_class in (
        sales_forms.LeadRoutingPreviewForm,
        sales_forms.LeadRoutingRunForm,
    ):
        form = form_class(tenant=leadmanagement_tenant_a)
        assert leadmanagement_lead_a in form.fields["lead"].queryset
        assert leadmanagement_lead_b not in form.fields["lead"].queryset

    qualification = sales_forms.LeadQualificationForm(tenant=leadmanagement_tenant_a)
    assert leadmanagement_lead_a in qualification.fields["lead"].queryset
    assert leadmanagement_lead_b not in qualification.fields["lead"].queryset

    routing = sales_forms.LeadRoutingRuleForm(tenant=leadmanagement_tenant_a)
    for field_name, own, foreign in (
        ("default_owner", leadmanagement_admin_a, leadmanagement_admin_b),
        ("territory", leadmanagement_territory_a, leadmanagement_territory_b),
        ("eligible_owners", leadmanagement_admin_a, leadmanagement_admin_b),
        ("fallback_owner", leadmanagement_admin_a, leadmanagement_admin_b),
    ):
        assert own in routing.fields[field_name].queryset
        assert foreign not in routing.fields[field_name].queryset

    one_time = _leadmanagement_email_campaign(
        leadmanagement_tenant_a,
        leadmanagement_campaign_a,
        owner=leadmanagement_admin_a,
        name="One-time campaign excluded by nurture form",
        send_type="one_time",
    )
    inactive_purpose = _leadmanagement_consent_purpose(
        leadmanagement_tenant_a,
        name="Inactive nurture purpose",
        code="inactive-nurture-purpose",
        is_active=False,
    )
    nurture = sales_forms.LeadNurtureEnrollmentForm(tenant=leadmanagement_tenant_a)
    assert leadmanagement_lead_a in nurture.fields["lead"].queryset
    assert leadmanagement_lead_b not in nurture.fields["lead"].queryset
    assert leadmanagement_email_campaign_a in nurture.fields["email_campaign"].queryset
    assert leadmanagement_email_campaign_b not in nurture.fields["email_campaign"].queryset
    assert one_time not in nurture.fields["email_campaign"].queryset
    assert leadmanagement_consent_purpose_a in nurture.fields["consent_purpose"].queryset
    assert leadmanagement_consent_purpose_b not in nurture.fields["consent_purpose"].queryset
    assert inactive_purpose not in nurture.fields["consent_purpose"].queryset
    assert leadmanagement_admin_a in nurture.fields["owner"].queryset
    assert leadmanagement_admin_b not in nurture.fields["owner"].queryset

    for form in (
        sales_forms.LeadScoreAdjustmentForm(tenant=None),
        sales_forms.LeadScoreCorrectionForm(tenant=None),
        sales_forms.LeadRoutingPreviewForm(tenant=None),
        sales_forms.LeadRoutingRunForm(tenant=None),
        sales_forms.LeadQualificationForm(tenant=None),
    ):
        assert list(form.fields["lead"].queryset) == []
    for field_name in ("default_owner", "territory", "eligible_owners", "fallback_owner"):
        assert list(sales_forms.LeadRoutingRuleForm(tenant=None).fields[field_name].queryset) == []
    tenantless_nurture = sales_forms.LeadNurtureEnrollmentForm(tenant=None)
    for field_name in ("lead", "email_campaign", "consent_purpose", "owner"):
        assert list(tenantless_nurture.fields[field_name].queryset) == []


def test_leadmanagement_score_and_preview_forms_reject_foreign_leads(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_score_event_b,
):
    cases = (
        (
            sales_forms.LeadScoreAdjustmentForm,
            _leadmanagement_score_payload(leadmanagement_lead_b, 1),
            "lead",
        ),
        (
            sales_forms.LeadScoreCorrectionForm,
            _leadmanagement_correction_payload(leadmanagement_lead_a, leadmanagement_score_event_b, -5),
            "corrects_event",
        ),
        (
            sales_forms.LeadRoutingPreviewForm,
            {"lead": str(leadmanagement_lead_b.pk)},
            "lead",
        ),
        (
            sales_forms.LeadRoutingRunForm,
            {"lead": str(leadmanagement_lead_b.pk)},
            "lead",
        ),
    )
    for form_class, payload, error_field in cases:
        form = form_class(payload, tenant=leadmanagement_tenant_a)
        assert not form.is_valid()
        assert "Select a valid choice" in " ".join(form.errors[error_field])


def test_leadmanagement_score_adjustment_form_enforces_delta_bounds_and_reason(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
):
    for score_delta in (-100, 100):
        form = sales_forms.LeadScoreAdjustmentForm(
            _leadmanagement_score_payload(leadmanagement_lead_a, score_delta),
            tenant=leadmanagement_tenant_a,
        )
        assert form.is_valid(), form.errors

    for score_delta in (-101, 101):
        form = sales_forms.LeadScoreAdjustmentForm(
            _leadmanagement_score_payload(leadmanagement_lead_a, score_delta),
            tenant=leadmanagement_tenant_a,
        )
        assert not form.is_valid()
        assert "score_delta" in form.errors

    form = sales_forms.LeadScoreAdjustmentForm(
        _leadmanagement_score_payload(leadmanagement_lead_a, 1, reason=""),
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert "reason" in form.errors


def test_leadmanagement_score_correction_form_requires_inverse_delta(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_a,
):
    form = sales_forms.LeadScoreCorrectionForm(
        _leadmanagement_correction_payload(leadmanagement_lead_a, leadmanagement_score_event_a, -5),
        tenant=leadmanagement_tenant_a,
    )
    assert form.is_valid(), form.errors

    form = sales_forms.LeadScoreCorrectionForm(
        _leadmanagement_correction_payload(leadmanagement_lead_a, leadmanagement_score_event_a, -4),
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert "score_delta" in form.errors
    assert "inverse" in " ".join(form.errors["score_delta"])


def test_leadmanagement_score_correction_form_rejects_wrong_lead_and_already_corrected_event(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_admin_a,
    leadmanagement_score_event_a,
):
    other_lead = _leadmanagement_lead(
        leadmanagement_tenant_a,
        owner=leadmanagement_admin_a,
        name="Other lead for score correction",
        email="other-score-correction@acme.example",
    )
    form = sales_forms.LeadScoreCorrectionForm(
        _leadmanagement_correction_payload(other_lead, leadmanagement_score_event_a, -5),
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert "corrects_event" in form.errors

    _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        recorded_by=leadmanagement_admin_a,
        event_type="correction",
        score_delta=-5,
        reason="Reverse the original event.",
        corrects_event=leadmanagement_score_event_a,
    )
    payload = _leadmanagement_correction_payload(leadmanagement_lead_a, leadmanagement_score_event_a, -5)
    narrowed = sales_forms.LeadScoreCorrectionForm(payload, tenant=leadmanagement_tenant_a)
    assert not narrowed.is_valid()
    assert "Select a valid choice" in " ".join(narrowed.errors["corrects_event"])

    widened = sales_forms.LeadScoreCorrectionForm(payload, tenant=leadmanagement_tenant_a)
    _leadmanagement_widen(
        widened,
        "corrects_event",
        LeadScoreEvent.objects.filter(tenant=leadmanagement_tenant_a),
    )
    assert not widened.is_valid()
    assert "already been corrected" in " ".join(widened.errors["corrects_event"])


def test_leadmanagement_score_correction_form_rejects_crafted_foreign_event(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_score_event_b,
):
    payload = _leadmanagement_correction_payload(
        leadmanagement_lead_a,
        leadmanagement_score_event_b,
        -5,
    )
    form = sales_forms.LeadScoreCorrectionForm(payload, tenant=leadmanagement_tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["corrects_event"])

    widened = sales_forms.LeadScoreCorrectionForm(payload, tenant=leadmanagement_tenant_a)
    _leadmanagement_widen(widened, "corrects_event", LeadScoreEvent.objects.all())
    assert not widened.is_valid()
    assert "corrects_event" in widened.errors


def test_leadmanagement_qualification_form_rejects_crafted_foreign_lead(
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
):
    payload = _leadmanagement_qualification_payload(leadmanagement_lead_b)
    form = sales_forms.LeadQualificationForm(payload, tenant=leadmanagement_tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["lead"])

    widened = sales_forms.LeadQualificationForm(payload, tenant=leadmanagement_tenant_a)
    _leadmanagement_widen(widened, "lead", Lead.objects.all())
    assert not widened.is_valid()
    assert _LEADMANAGEMENT_FOREIGN_ERROR in widened.errors["lead"]


def test_leadmanagement_qualification_form_disables_identity_on_edit(
    leadmanagement_tenant_a,
    leadmanagement_qualification_a,
):
    form = sales_forms.LeadQualificationForm(
        instance=leadmanagement_qualification_a,
        tenant=leadmanagement_tenant_a,
    )
    assert form.fields["lead"].disabled is True
    assert form.initial["lead"] == leadmanagement_qualification_a.lead_id


def test_leadmanagement_qualification_decision_form_requires_disqualification_reason(
    leadmanagement_tenant_a,
):
    form = sales_forms.LeadQualificationDecisionForm(
        {"status": "disqualified", "disqualification_reason": "  ", "notes": ""},
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert "disqualification_reason" in form.errors

    form = sales_forms.LeadQualificationDecisionForm(
        {"status": "disqualified", "disqualification_reason": "No viable budget.", "notes": ""},
        tenant=leadmanagement_tenant_a,
    )
    assert form.is_valid(), form.errors

    form = sales_forms.LeadQualificationDecisionForm(
        {"status": "unassessed", "disqualification_reason": "", "notes": ""},
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert "status" in form.errors


def test_leadmanagement_qualification_form_requires_bant_evidence_before_qualified(
    leadmanagement_tenant_a,
    leadmanagement_currency,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_admin_a,
):
    qualification = leadmanagement_qualification_a
    qualification.status = "qualified"
    qualification.assessed_by = leadmanagement_admin_a
    qualification.need_summary = ""
    qualification.expected_purchase_on = None
    qualification.budget_status = "unknown"
    qualification.authority_level = "unknown"
    form = sales_forms.LeadQualificationForm(
        _leadmanagement_qualification_payload(
            leadmanagement_lead_a,
            framework="bant",
            need_summary="",
            expected_purchase_on="",
            budget_currency=str(leadmanagement_currency.pk),
            budget_status="unknown",
            authority_level="unknown",
        ),
        instance=qualification,
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert {
        "need_summary",
        "expected_purchase_on",
        "budget_status",
        "authority_level",
    }.issubset(form.errors)


@pytest.mark.parametrize("framework", ("meddic", "both"))
def test_leadmanagement_qualification_form_requires_meddic_evidence_before_qualified(
    framework,
    leadmanagement_tenant_a,
    leadmanagement_currency,
    leadmanagement_lead_a,
    leadmanagement_qualification_a,
    leadmanagement_admin_a,
):
    qualification = leadmanagement_qualification_a
    qualification.status = "qualified"
    qualification.framework = framework
    qualification.assessed_by = leadmanagement_admin_a
    qualification.need_summary = "Replace fragmented lead intake."
    qualification.expected_purchase_on = timezone.localdate() + timedelta(days=45)
    qualification.economic_buyer = ""
    qualification.decision_criteria = ""
    qualification.decision_process = ""
    form = sales_forms.LeadQualificationForm(
        _leadmanagement_qualification_payload(
            leadmanagement_lead_a,
            framework=framework,
            need_summary=qualification.need_summary,
            expected_purchase_on=qualification.expected_purchase_on.isoformat(),
            budget_amount="75000.00",
            budget_currency=str(leadmanagement_currency.pk),
            budget_status="confirmed",
            authority_level="director",
            economic_buyer="",
            decision_criteria="",
            decision_process="",
        ),
        instance=qualification,
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert {
        "economic_buyer",
        "decision_criteria",
        "decision_process",
    }.issubset(form.errors)


def test_leadmanagement_routing_form_rejects_unhashable_nested_non_finite_and_oversized_json(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
):
    oversized = json.dumps([
        {"field": "company", "operator": "icontains", "value": "x" * 17_000},
    ])
    payloads = (
        json.dumps([{"field": "status", "operator": "eq", "value": {"nested": "object"}}]),
        json.dumps([{"field": "status", "operator": "in", "value": [["nested"]]}]),
        json.dumps([{"field": "score", "operator": "eq", "value": float("nan")}]),
        json.dumps([{"field": "score", "operator": "eq", "value": float("inf")}]),
        oversized,
    )
    for conditions in payloads:
        form = sales_forms.LeadRoutingRuleForm(
            _leadmanagement_routing_payload(
                eligible_owners=(leadmanagement_admin_a,),
                conditions=conditions,
            ),
            tenant=leadmanagement_tenant_a,
        )
        assert not form.is_valid()
        assert "conditions" in form.errors


def test_leadmanagement_routing_form_validates_conditions_and_saves_normalized_json(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
):
    conditions = [
        {"field": "status", "operator": "in", "value": ["new", "recycled"]},
        {"field": "score", "operator": "gte", "value": 40},
    ]
    form = sales_forms.LeadRoutingRuleForm(
        _leadmanagement_routing_payload(
            name="Normalized routing rule",
            eligible_owners=(leadmanagement_admin_a,),
            conditions=json.dumps(conditions),
        ),
        tenant=leadmanagement_tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["conditions"] == conditions
    rule = form.save()
    rule.refresh_from_db()
    assert rule.tenant_id == leadmanagement_tenant_a.pk
    assert rule.conditions == conditions
    assert list(rule.eligible_owners.all()) == [leadmanagement_admin_a]


def test_leadmanagement_routing_form_enforces_assignment_mode_requirements(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_territory_a,
):
    fixed = sales_forms.LeadRoutingRuleForm(
        _leadmanagement_routing_payload(
            name="Missing fixed owner",
            eligible_owners=(leadmanagement_admin_a,),
            assignment_mode="fixed_owner",
            default_owner=None,
        ),
        tenant=leadmanagement_tenant_a,
    )
    assert not fixed.is_valid()
    assert "default_owner" in fixed.errors

    territory_without_manager = _leadmanagement_territory(
        leadmanagement_tenant_a,
        manager=None,
        name="Territory without manager for form",
    )
    territory = sales_forms.LeadRoutingRuleForm(
        _leadmanagement_routing_payload(
            name="Territory manager required",
            eligible_owners=(leadmanagement_admin_a,),
            assignment_mode="territory_manager",
            territory=territory_without_manager,
        ),
        tenant=leadmanagement_tenant_a,
    )
    assert not territory.is_valid()
    assert "territory" in territory.errors

    round_robin = sales_forms.LeadRoutingRuleForm(
        _leadmanagement_routing_payload(
            name="Round robin needs owners",
            eligible_owners=(),
        ),
        tenant=leadmanagement_tenant_a,
    )
    assert not round_robin.is_valid()
    assert "eligible_owners" in round_robin.errors


def test_leadmanagement_routing_form_rejects_crafted_foreign_fk_and_m2m_values(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_territory_b,
):
    foreign_values = {
        "default_owner": leadmanagement_admin_b,
        "territory": leadmanagement_territory_b,
        "eligible_owners": leadmanagement_admin_b,
        "fallback_owner": leadmanagement_admin_b,
    }
    for field_name, foreign in foreign_values.items():
        payload = _leadmanagement_routing_payload(
            name=f"Crafted {field_name}",
            eligible_owners=(leadmanagement_admin_a,),
        )
        payload[field_name] = [str(foreign.pk)] if field_name == "eligible_owners" else str(foreign.pk)
        narrowed = sales_forms.LeadRoutingRuleForm(payload, tenant=leadmanagement_tenant_a)
        assert foreign.pk not in narrowed.fields[field_name].queryset
        assert not narrowed.is_valid()
        assert "Select a valid choice" in " ".join(narrowed.errors[field_name])

        widened = sales_forms.LeadRoutingRuleForm(payload, tenant=leadmanagement_tenant_a)
        _leadmanagement_widen(widened, field_name, type(foreign).objects.all())
        assert not widened.is_valid()
        assert _LEADMANAGEMENT_FOREIGN_ERROR in widened.errors[field_name]


def test_leadmanagement_qualification_form_keeps_accounting_currency_global(
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_currency,
    leadmanagement_lead_a,
):
    assert "tenant" not in {field.name for field in Currency._meta.fields}
    for tenant in (leadmanagement_tenant_a, leadmanagement_tenant_b, None):
        field = sales_forms.LeadQualificationForm(tenant=tenant).fields["budget_currency"]
        assert leadmanagement_currency in field.queryset

    valid_data = _leadmanagement_qualification_payload(
        leadmanagement_lead_a,
        budget_amount="100.00",
        budget_currency=str(leadmanagement_currency.pk),
    )
    form = sales_forms.LeadQualificationForm(valid_data, tenant=leadmanagement_tenant_a)
    assert form.is_valid(), form.errors
    qualification = form.save()
    qualification.refresh_from_db()
    assert qualification.tenant_id == leadmanagement_tenant_a.pk
    assert qualification.budget_currency_id == leadmanagement_currency.pk
    assert qualification.budget_amount == 100

    missing_currency = sales_forms.LeadQualificationForm(
        _leadmanagement_qualification_payload(
            leadmanagement_lead_a,
            budget_amount="100.00",
            budget_currency="",
        ),
        tenant=leadmanagement_tenant_a,
    )
    assert not missing_currency.is_valid()
    assert "budget_currency" in missing_currency.errors


def test_leadmanagement_nurture_form_offers_only_drip_campaigns_and_active_consent(
    leadmanagement_tenant_a,
    leadmanagement_tenant_b,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_campaign_a,
    leadmanagement_email_campaign_a,
    leadmanagement_email_campaign_b,
    leadmanagement_consent_purpose_a,
    leadmanagement_consent_purpose_b,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
):
    one_time = _leadmanagement_email_campaign(
        leadmanagement_tenant_a,
        leadmanagement_campaign_a,
        owner=leadmanagement_admin_a,
        name="One-time campaign excluded from nurture form",
        send_type="one_time",
    )
    inactive_purpose = _leadmanagement_consent_purpose(
        leadmanagement_tenant_a,
        name="Inactive purpose excluded from nurture form",
        code="inactive-purpose-excluded",
        is_active=False,
    )
    form = sales_forms.LeadNurtureEnrollmentForm(tenant=leadmanagement_tenant_a)
    assert leadmanagement_lead_a in form.fields["lead"].queryset
    assert leadmanagement_lead_b not in form.fields["lead"].queryset
    assert leadmanagement_email_campaign_a in form.fields["email_campaign"].queryset
    assert leadmanagement_email_campaign_b not in form.fields["email_campaign"].queryset
    assert one_time not in form.fields["email_campaign"].queryset
    assert leadmanagement_consent_purpose_a in form.fields["consent_purpose"].queryset
    assert leadmanagement_consent_purpose_b not in form.fields["consent_purpose"].queryset
    assert inactive_purpose not in form.fields["consent_purpose"].queryset
    assert leadmanagement_admin_a in form.fields["owner"].queryset
    assert leadmanagement_admin_b not in form.fields["owner"].queryset

    tenantless = sales_forms.LeadNurtureEnrollmentForm(tenant=None)
    for field_name in ("lead", "email_campaign", "consent_purpose", "owner"):
        assert list(tenantless.fields[field_name].queryset) == []


def test_leadmanagement_nurture_form_rejects_crafted_foreign_fk_values(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_admin_b,
    leadmanagement_lead_a,
    leadmanagement_lead_b,
    leadmanagement_email_campaign_a,
    leadmanagement_email_campaign_b,
    leadmanagement_consent_purpose_a,
    leadmanagement_consent_purpose_b,
):
    foreign_values = {
        "lead": leadmanagement_lead_b,
        "email_campaign": leadmanagement_email_campaign_b,
        "consent_purpose": leadmanagement_consent_purpose_b,
        "owner": leadmanagement_admin_b,
    }
    for field_name, foreign in foreign_values.items():
        payload = _leadmanagement_nurture_payload(
            leadmanagement_lead_a,
            leadmanagement_email_campaign_a,
            consent_purpose=leadmanagement_consent_purpose_a,
            owner=leadmanagement_admin_a,
        )
        payload[field_name] = str(foreign.pk)
        narrowed = sales_forms.LeadNurtureEnrollmentForm(payload, tenant=leadmanagement_tenant_a)
        assert foreign.pk not in narrowed.fields[field_name].queryset
        assert not narrowed.is_valid()
        assert "Select a valid choice" in " ".join(narrowed.errors[field_name])

        widened = sales_forms.LeadNurtureEnrollmentForm(payload, tenant=leadmanagement_tenant_a)
        _leadmanagement_widen(widened, field_name, type(foreign).objects.all())
        assert not widened.is_valid()
        assert _LEADMANAGEMENT_FOREIGN_ERROR in widened.errors[field_name]


def test_leadmanagement_nurture_form_allows_pending_identity_edit_but_blocks_active_identity_edit(
    leadmanagement_tenant_a,
    leadmanagement_admin_a,
    leadmanagement_member_a,
    leadmanagement_nurture_enrollment_a,
):
    alternate_lead, alternate_campaign, alternate_purpose = _leadmanagement_alternate_nurture_identity(
        leadmanagement_tenant_a,
        leadmanagement_admin_a,
    )
    pending = leadmanagement_nurture_enrollment_a
    pending_data = _leadmanagement_nurture_payload(
        alternate_lead,
        pending.email_campaign,
        consent_purpose=pending.consent_purpose,
        owner=pending.owner,
    )
    pending_form = sales_forms.LeadNurtureEnrollmentForm(
        pending_data,
        instance=pending,
        tenant=leadmanagement_tenant_a,
    )
    assert pending_form.is_valid(), pending_form.errors
    assert pending_form.cleaned_data["lead"] == alternate_lead

    pending.refresh_from_db()
    activate_nurture(pending, leadmanagement_tenant_a, leadmanagement_admin_a)
    active = pending

    identity_changes = {
        "lead": alternate_lead,
        "email_campaign": alternate_campaign,
        "consent_purpose": alternate_purpose,
        "owner": leadmanagement_member_a,
        "consent_evidence": "Updated evidence after activation.",
    }
    for field_name, replacement in identity_changes.items():
        active.refresh_from_db()
        active_data = _leadmanagement_nurture_payload(
            active.lead,
            active.email_campaign,
            consent_purpose=active.consent_purpose,
            owner=active.owner,
        )
        active_data[field_name] = str(replacement.pk) if hasattr(replacement, "pk") else replacement
        active_form = sales_forms.LeadNurtureEnrollmentForm(
            active_data,
            instance=active,
            tenant=leadmanagement_tenant_a,
        )
        assert not active_form.is_valid()
        assert "Enrollment identity is editable only while it is pending." in active_form.non_field_errors()


def test_leadmanagement_nurture_activation_form_accepts_optional_datetime_and_rejects_malformed_value(
    leadmanagement_tenant_a,
):
    form = sales_forms.LeadNurtureActivationForm({}, tenant=leadmanagement_tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["next_touch_at"] is None

    form = sales_forms.LeadNurtureActivationForm(
        {"next_touch_at": "not-a-datetime"},
        tenant=leadmanagement_tenant_a,
    )
    assert not form.is_valid()
    assert "next_touch_at" in form.errors
