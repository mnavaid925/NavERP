import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import ConsentPurpose, Party
from apps.crm.models import Opportunity
from apps.sales import forms as sales_forms
from apps.sales.models import AccountClassification, AccountPlan, AccountStakeholder, PartyEnrichmentEvent
from apps.sales.models.ContactAccountManagement.PartyEnrichment import ENRICHMENT_FIELD_CHOICES
from apps.sales.tests.conftest import (
    _contactaccountmanagement_consent_purpose,
    _contactaccountmanagement_user,
)


pytestmark = pytest.mark.django_db


_contactaccountmanagement_form_fields = {
    sales_forms.PartyEnrichmentProposalForm: (
        "party",
        "kind",
        "source_kind",
        "source_name",
        "source_reference",
        "changes",
        "legal_basis_purpose",
    ),
    sales_forms.PartyEnrichmentApplyForm: ("selected_fields", "review_note"),
    sales_forms.PartyEnrichmentRejectForm: ("review_note",),
    sales_forms.AccountStakeholderForm: (
        "account",
        "contact",
        "role",
        "influence",
        "attitude",
        "relationship_strength",
        "status",
        "valid_from",
        "valid_to",
        "notes",
    ),
    sales_forms.AccountClassificationForm: (
        "account",
        "tier",
        "lifecycle_stage",
        "strategic_priority",
        "revenue_potential",
        "wallet_category",
        "rationale",
        "effective_on",
        "review_due_on",
    ),
    sales_forms.AccountPlanForm: (
        "account",
        "title",
        "period_start",
        "period_end",
        "owner",
        "business_drivers",
        "objectives",
        "strategy",
        "strengths",
        "weaknesses",
        "opportunities",
        "threats",
        "white_space_assessment",
        "growth_initiatives",
        "risk_summary",
        "next_review_on",
        "related_opportunities",
    ),
}


_contactaccountmanagement_excluded_fields = {
    sales_forms.PartyEnrichmentProposalForm: {
        "tenant",
        "id",
        "created_at",
        "status",
        "match_confidence",
        "requested_by",
        "reviewed_by",
        "occurred_at",
        "applied_at",
        "idempotency_key",
        "error_code",
        "error_summary",
    },
    sales_forms.PartyEnrichmentApplyForm: {
        "tenant",
        "id",
        "status",
        "match_confidence",
        "requested_by",
        "reviewed_by",
        "occurred_at",
        "applied_at",
    },
    sales_forms.PartyEnrichmentRejectForm: {
        "tenant",
        "id",
        "status",
        "match_confidence",
        "requested_by",
        "reviewed_by",
        "occurred_at",
        "applied_at",
    },
    sales_forms.AccountStakeholderForm: {"tenant", "id", "created_at", "updated_at"},
    sales_forms.AccountClassificationForm: {
        "tenant",
        "id",
        "created_at",
        "updated_at",
        "classified_by",
    },
    sales_forms.AccountPlanForm: {"tenant", "id", "created_at", "updated_at", "number", "status"},
}


def _contactaccountmanagement_proposal_payload(party, purpose=None, **overrides):
    if party.kind == "organization":
        kind = "firmographic"
        changes = {"industry": {"value": "technology", "confidence": 0.9}}
    else:
        kind = "contact"
        changes = {"job_title": {"value": "Operations Director", "confidence": 0.9}}
    data = {
        "party": str(party.pk),
        "kind": kind,
        "source_kind": "manual",
        "source_name": "Manual review",
        "source_reference": "contactaccountmanagement:form",
        "changes": json.dumps(changes),
        "legal_basis_purpose": str(purpose.pk) if purpose is not None else "",
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_stakeholder_payload(account, contact, **overrides):
    today = timezone.localdate()
    data = {
        "account": str(account.pk),
        "contact": str(contact.pk),
        "role": "advisor",
        "influence": "medium",
        "attitude": "neutral",
        "relationship_strength": "moderate",
        "status": "active",
        "valid_from": today.isoformat(),
        "valid_to": today.isoformat(),
        "notes": "Deterministic stakeholder form evidence.",
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_classification_payload(account, **overrides):
    today = timezone.localdate()
    data = {
        "account": str(account.pk),
        "tier": "growth",
        "lifecycle_stage": "prospect",
        "strategic_priority": "medium",
        "revenue_potential": "unknown",
        "wallet_category": "none",
        "rationale": "Deterministic account classification rationale.",
        "effective_on": today.isoformat(),
        "review_due_on": "",
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_plan_payload(account, owner, **overrides):
    today = timezone.localdate()
    data = {
        "account": str(account.pk),
        "title": "Deterministic account plan",
        "period_start": today.isoformat(),
        "period_end": (today + timedelta(days=90)).isoformat(),
        "owner": str(owner.pk),
        "business_drivers": "Growth",
        "objectives": "Retain and expand",
        "strategy": "Executive coverage",
        "strengths": "Strong relationship",
        "weaknesses": "Limited reach",
        "opportunities": "New region",
        "threats": "Competitor",
        "white_space_assessment": "No product mapping",
        "growth_initiatives": "Executive briefing",
        "risk_summary": "Low",
        "next_review_on": (today + timedelta(days=30)).isoformat(),
        "related_opportunities": [],
    }
    data.update(overrides)
    return data


def _contactaccountmanagement_widen(form, field_name, queryset):
    form.fields[field_name].queryset = queryset
    return form


def _contactaccountmanagement_opportunity_selector_probe():
    manager = MagicMock()
    first = MagicMock()
    final = MagicMock()
    for probe in (first, final):
        probe.filter.return_value = probe
        probe.all.return_value = probe
        probe.only.return_value = probe
        probe.order_by.return_value = probe
        probe.values_list.return_value = probe
        probe.__getitem__.return_value = []
    manager.filter.side_effect = [first, final]
    return manager, first, final


def test_contactaccountmanagement_forms_expose_exact_fields_and_exclusions():
    for form_class, expected_fields in _contactaccountmanagement_form_fields.items():
        assert tuple(form_class.base_fields) == expected_fields
        model = getattr(getattr(form_class, "_meta", None), "model", None)
        if model is not None:
            assert tuple(form_class._meta.fields) == expected_fields

    for form_class, excluded in _contactaccountmanagement_excluded_fields.items():
        assert not excluded.intersection(form_class.base_fields)

    assert "raw_payload" not in {field.name for field in PartyEnrichmentEvent._meta.fields}
    assert "provider_response" not in {field.name for field in PartyEnrichmentEvent._meta.fields}


def test_contactaccountmanagement_forms_use_exact_closed_choices(contactaccountmanagement_tenant_a, contactaccountmanagement_enrichment_event_a):
    proposal = sales_forms.PartyEnrichmentProposalForm(tenant=contactaccountmanagement_tenant_a)
    assert tuple(proposal.fields["kind"].choices) == tuple(PartyEnrichmentEvent.KIND_CHOICES)
    assert tuple(proposal.fields["source_kind"].choices) == tuple(PartyEnrichmentEvent.SOURCE_KIND_CHOICES)

    apply = sales_forms.PartyEnrichmentApplyForm(tenant=contactaccountmanagement_tenant_a)
    assert tuple(apply.fields["selected_fields"].choices) == tuple(ENRICHMENT_FIELD_CHOICES)
    event_apply = sales_forms.PartyEnrichmentApplyForm(
        tenant=contactaccountmanagement_tenant_a,
        event=contactaccountmanagement_enrichment_event_a,
    )
    available = set(contactaccountmanagement_enrichment_event_a.changes)
    assert tuple(event_apply.fields["selected_fields"].choices) == tuple(
        choice for choice in ENRICHMENT_FIELD_CHOICES if choice[0] in available
    )

    stakeholder = sales_forms.AccountStakeholderForm(tenant=contactaccountmanagement_tenant_a)
    for field_name, expected in {
        "role": AccountStakeholder.ROLE_CHOICES,
        "influence": AccountStakeholder.INFLUENCE_CHOICES,
        "attitude": AccountStakeholder.ATTITUDE_CHOICES,
        "relationship_strength": AccountStakeholder.RELATIONSHIP_STRENGTH_CHOICES,
        "status": AccountStakeholder.STATUS_CHOICES,
    }.items():
        assert tuple(choice for choice in stakeholder.fields[field_name].choices if choice[0]) == tuple(expected)

    classification = sales_forms.AccountClassificationForm(tenant=contactaccountmanagement_tenant_a)
    for field_name, expected in {
        "tier": AccountClassification.TIER_CHOICES,
        "lifecycle_stage": AccountClassification.LIFECYCLE_STAGE_CHOICES,
        "strategic_priority": AccountClassification.STRATEGIC_PRIORITY_CHOICES,
        "revenue_potential": AccountClassification.REVENUE_POTENTIAL_CHOICES,
        "wallet_category": AccountClassification.WALLET_CATEGORY_CHOICES,
    }.items():
        assert tuple(choice for choice in classification.fields[field_name].choices if choice[0]) == tuple(expected)

    assert "status" not in sales_forms.AccountPlanForm.base_fields


def test_contactaccountmanagement_forms_scope_party_user_and_purpose_querysets(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_member_a,
    contactaccountmanagement_member_b,
    contactaccountmanagement_consent_purpose_a,
    contactaccountmanagement_consent_purpose_b,
):
    inactive_purpose = _contactaccountmanagement_consent_purpose(
        contactaccountmanagement_tenant_a,
        code="inactive-contact-enrichment",
        name="Inactive contact enrichment",
        is_active=False,
    )
    inactive_user = _contactaccountmanagement_user(
        contactaccountmanagement_tenant_a,
        "inactive-owner",
    )
    inactive_user.is_active = False
    inactive_user.save(update_fields=["is_active"])

    proposal = sales_forms.PartyEnrichmentProposalForm(tenant=contactaccountmanagement_tenant_a)
    assert contactaccountmanagement_account_a in proposal.fields["party"].queryset
    assert contactaccountmanagement_contact_a in proposal.fields["party"].queryset
    assert contactaccountmanagement_account_b not in proposal.fields["party"].queryset
    assert contactaccountmanagement_contact_b not in proposal.fields["party"].queryset
    assert contactaccountmanagement_consent_purpose_a in proposal.fields["legal_basis_purpose"].queryset
    assert contactaccountmanagement_consent_purpose_b not in proposal.fields["legal_basis_purpose"].queryset
    assert inactive_purpose not in proposal.fields["legal_basis_purpose"].queryset

    stakeholder = sales_forms.AccountStakeholderForm(tenant=contactaccountmanagement_tenant_a)
    assert contactaccountmanagement_account_a in stakeholder.fields["account"].queryset
    assert contactaccountmanagement_account_child_a in stakeholder.fields["account"].queryset
    assert contactaccountmanagement_account_b not in stakeholder.fields["account"].queryset
    assert contactaccountmanagement_contact_a not in stakeholder.fields["account"].queryset
    assert contactaccountmanagement_contact_a in stakeholder.fields["contact"].queryset
    assert contactaccountmanagement_manager_a in stakeholder.fields["contact"].queryset
    assert contactaccountmanagement_contact_b not in stakeholder.fields["contact"].queryset
    assert contactaccountmanagement_account_a not in stakeholder.fields["contact"].queryset

    classification = sales_forms.AccountClassificationForm(tenant=contactaccountmanagement_tenant_a)
    assert contactaccountmanagement_account_a in classification.fields["account"].queryset
    assert contactaccountmanagement_account_child_a in classification.fields["account"].queryset
    assert contactaccountmanagement_account_b not in classification.fields["account"].queryset
    assert contactaccountmanagement_contact_a not in classification.fields["account"].queryset

    plan = sales_forms.AccountPlanForm(tenant=contactaccountmanagement_tenant_a)
    assert contactaccountmanagement_account_a in plan.fields["account"].queryset
    assert contactaccountmanagement_account_child_a in plan.fields["account"].queryset
    assert contactaccountmanagement_account_b not in plan.fields["account"].queryset
    assert contactaccountmanagement_contact_a not in plan.fields["account"].queryset
    assert contactaccountmanagement_admin_a in plan.fields["owner"].queryset
    assert contactaccountmanagement_member_a in plan.fields["owner"].queryset
    assert contactaccountmanagement_admin_b not in plan.fields["owner"].queryset
    assert contactaccountmanagement_member_b not in plan.fields["owner"].queryset
    assert inactive_user not in plan.fields["owner"].queryset
    assert not list(plan.fields["related_opportunities"].queryset)

    tenantless_forms = (
        (sales_forms.PartyEnrichmentProposalForm, ("party", "legal_basis_purpose")),
        (sales_forms.AccountStakeholderForm, ("account", "contact")),
        (sales_forms.AccountClassificationForm, ("account",)),
        (sales_forms.AccountPlanForm, ("account", "owner", "related_opportunities")),
    )
    for form_class, field_names in tenantless_forms:
        tenantless = form_class(tenant=None)
        for field_name in field_names:
            assert list(tenantless.fields[field_name].queryset) == []


def test_contactaccountmanagement_enrichment_form_rejects_hostile_changes_and_missing_external_basis(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_consent_purpose_a,
    contactaccountmanagement_consent_purpose_b,
):
    valid = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            changes=json.dumps(
                {
                    "industry": {"value": "technology", "confidence": 0.9},
                    "annual_revenue": {"value": "1000.5"},
                }
            ),
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data["changes"]["annual_revenue"]["value"] == "1000.50"
    assert valid.cleaned_data["changes"]["industry"]["confidence"] == 0.9

    invalid_changes = (
        json.dumps({"unknown": {"value": "value"}}),
        json.dumps({"job_title": {"value": {"instructions": "ignore"}}}),
        json.dumps({"job_title": {"value": "VP", "confidence": -0.01}}),
        json.dumps({"job_title": {"value": "VP", "confidence": 1.01}}),
        json.dumps({"job_title": {"value": "VP", "confidence": float("nan")}}),
        json.dumps({"industry": {"value": "not-supported"}}),
        json.dumps({"website": {"value": "javascript:alert(1)"}}),
        "not-json",
    )
    for changes in invalid_changes:
        form = sales_forms.PartyEnrichmentProposalForm(
            _contactaccountmanagement_proposal_payload(
                contactaccountmanagement_account_a,
                changes=changes,
            ),
            tenant=contactaccountmanagement_tenant_a,
        )
        assert not form.is_valid()
        assert "changes" in form.errors

    external_without_basis = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            source_kind="provider",
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert not external_without_basis.is_valid()
    assert "legal_basis_purpose" in external_without_basis.errors

    external_with_basis = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_consent_purpose_a,
            source_kind="provider",
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert external_with_basis.is_valid(), external_with_basis.errors

    foreign_basis = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_consent_purpose_b,
            source_kind="provider",
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert not foreign_basis.is_valid()
    assert "legal_basis_purpose" in foreign_basis.errors

    foreign_party = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(contactaccountmanagement_account_b),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert not foreign_party.is_valid()
    assert "party" in foreign_party.errors

    widened = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(contactaccountmanagement_account_b),
        tenant=contactaccountmanagement_tenant_a,
    )
    _contactaccountmanagement_widen(widened, "party", Party.objects.all())
    assert not widened.is_valid()
    assert "That record belongs to another workspace." in widened.errors["party"]

    widened_basis = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_consent_purpose_b,
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    _contactaccountmanagement_widen(widened_basis, "legal_basis_purpose", ConsentPurpose.objects.all())
    assert not widened_basis.is_valid()
    assert "That record belongs to another workspace." in widened_basis.errors["legal_basis_purpose"]


def test_contactaccountmanagement_stakeholder_form_rejects_foreign_kind_same_and_reversed_dates(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_manager_a,
):
    for field_name, foreign in (
        ("account", contactaccountmanagement_account_b),
        ("contact", contactaccountmanagement_contact_b),
    ):
        payload = _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_contact_a,
        )
        payload[field_name] = str(foreign.pk)
        form = sales_forms.AccountStakeholderForm(
            payload,
            tenant=contactaccountmanagement_tenant_a,
        )
        assert foreign not in form.fields[field_name].queryset
        assert not form.is_valid()
        assert "Select a valid choice" in " ".join(form.errors[field_name])

        widened_payload = _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_contact_a,
        )
        widened_payload[field_name] = str(foreign.pk)
        widened = sales_forms.AccountStakeholderForm(
            widened_payload,
            tenant=contactaccountmanagement_tenant_a,
        )
        _contactaccountmanagement_widen(widened, field_name, Party.objects.all())
        assert not widened.is_valid()
        assert "That record belongs to another workspace." in widened.errors[field_name]

    wrong_account_kind = sales_forms.AccountStakeholderForm(
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_contact_a,
            contactaccountmanagement_manager_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    _contactaccountmanagement_widen(wrong_account_kind, "account", Party.objects.all())
    assert not wrong_account_kind.is_valid()
    assert "account" in wrong_account_kind.errors

    wrong_contact_kind = sales_forms.AccountStakeholderForm(
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_account_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    _contactaccountmanagement_widen(wrong_contact_kind, "contact", Party.objects.all())
    assert not wrong_contact_kind.is_valid()
    assert "contact" in wrong_contact_kind.errors

    same_party = sales_forms.AccountStakeholderForm(
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_contact_a,
            contactaccountmanagement_contact_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    _contactaccountmanagement_widen(same_party, "account", Party.objects.all())
    _contactaccountmanagement_widen(same_party, "contact", Party.objects.all())
    assert not same_party.is_valid()
    assert "An account and contact must be different Parties." in " ".join(same_party.errors["contact"])

    reversed_dates = sales_forms.AccountStakeholderForm(
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_contact_a,
            valid_from=timezone.localdate().isoformat(),
            valid_to=(timezone.localdate() - timedelta(days=1)).isoformat(),
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert not reversed_dates.is_valid()
    assert "valid_to" in reversed_dates.errors

    valid_equal_dates = sales_forms.AccountStakeholderForm(
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_contact_a,
            valid_from=timezone.localdate().isoformat(),
            valid_to=timezone.localdate().isoformat(),
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert valid_equal_dates.is_valid(), valid_equal_dates.errors
    unsaved = valid_equal_dates.save(commit=False)
    assert unsaved.tenant_id == contactaccountmanagement_tenant_a.pk


def test_contactaccountmanagement_classification_form_requires_rationale_and_review_date(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_classification_a,
):
    missing_rationale = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(
            contactaccountmanagement_account_child_a,
            rationale="   ",
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert not missing_rationale.is_valid()
    assert "rationale" in missing_rationale.errors

    for tier in ("strategic", "key"):
        missing_review = sales_forms.AccountClassificationForm(
            _contactaccountmanagement_classification_payload(
                contactaccountmanagement_account_child_a,
                tier=tier,
            ),
            tenant=contactaccountmanagement_tenant_a,
        )
        assert not missing_review.is_valid()
        assert "review_due_on" in missing_review.errors

    today = timezone.localdate()
    reversed_review = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(
            contactaccountmanagement_account_child_a,
            tier="strategic",
            effective_on=today.isoformat(),
            review_due_on=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert not reversed_review.is_valid()
    assert "review_due_on" in reversed_review.errors

    for tier, _tier_label in AccountClassification.TIER_CHOICES:
        for lifecycle_stage, _lifecycle_label in AccountClassification.LIFECYCLE_STAGE_CHOICES:
            review_due_on = (today + timedelta(days=90)).isoformat() if tier in {"strategic", "key"} else ""
            form = sales_forms.AccountClassificationForm(
                _contactaccountmanagement_classification_payload(
                    contactaccountmanagement_account_child_a,
                    tier=tier,
                    lifecycle_stage=lifecycle_stage,
                    review_due_on=review_due_on,
                ),
                tenant=contactaccountmanagement_tenant_a,
            )
            assert form.is_valid(), (tier, lifecycle_stage, form.errors)

    foreign_account = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(contactaccountmanagement_account_b),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert not foreign_account.is_valid()
    assert "account" in foreign_account.errors

    widened = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(contactaccountmanagement_account_b),
        tenant=contactaccountmanagement_tenant_a,
    )
    _contactaccountmanagement_widen(widened, "account", Party.objects.all())
    assert not widened.is_valid()
    assert "That record belongs to another workspace." in widened.errors["account"]

    person_account = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(contactaccountmanagement_contact_a),
        tenant=contactaccountmanagement_tenant_a,
    )
    _contactaccountmanagement_widen(person_account, "account", Party.objects.all())
    assert not person_account.is_valid()
    assert "account" in person_account.errors

    duplicate = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(contactaccountmanagement_account_a),
        tenant=contactaccountmanagement_tenant_a,
    )
    duplicate.is_valid()
    assert AccountClassification.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account=contactaccountmanagement_account_a,
    ).count() == 1

    edit = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(
            contactaccountmanagement_account_a,
            rationale="Updated deterministic rationale.",
        ),
        instance=contactaccountmanagement_classification_a,
        tenant=contactaccountmanagement_tenant_a,
    )
    assert edit.is_valid(), edit.errors


def test_contactaccountmanagement_plan_form_enforces_owner_period_and_account_dependent_choices(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_member_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    monkeypatch,
):
    today = timezone.localdate()
    valid = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data["account"] == contactaccountmanagement_account_a
    assert valid.cleaned_data["owner"] == contactaccountmanagement_admin_a

    reversed_period = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            period_start=today.isoformat(),
            period_end=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert not reversed_period.is_valid()
    assert "period_end" in reversed_period.errors

    foreign_account = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_b,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert not foreign_account.is_valid()
    assert "account" in foreign_account.errors

    widened_account = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_b,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    _contactaccountmanagement_widen(widened_account, "account", Party.objects.all())
    assert not widened_account.is_valid()
    assert "That record belongs to another workspace." in widened_account.errors["account"]

    person_account = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_contact_a,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    _contactaccountmanagement_widen(person_account, "account", Party.objects.all())
    assert not person_account.is_valid()
    assert "account" in person_account.errors

    foreign_owner = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_b,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert not foreign_owner.is_valid()
    assert "owner" in foreign_owner.errors

    widened_owner = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_b,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    _contactaccountmanagement_widen(widened_owner, "owner", User.objects.all())
    assert not widened_owner.is_valid()
    assert "That record belongs to another workspace." in widened_owner.errors["owner"]

    member_form = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_member_a,
    )
    assert member_form.fields["owner"].disabled is True
    assert contactaccountmanagement_member_a in member_form.fields["owner"].queryset
    assert contactaccountmanagement_admin_a not in member_form.fields["owner"].queryset
    assert member_form.is_valid(), member_form.errors
    assert member_form.cleaned_data["owner"] == contactaccountmanagement_member_a

    inactive_user = _contactaccountmanagement_user(contactaccountmanagement_tenant_a, "inactive-plan-owner")
    inactive_user.is_active = False
    inactive_user.save(update_fields=["is_active"])
    inactive_owner = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            inactive_user,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert not inactive_owner.is_valid()
    assert "owner" in inactive_owner.errors

    assert Opportunity.objects.count() == 0
    manager, first, final = _contactaccountmanagement_opportunity_selector_probe()
    monkeypatch.setattr(Opportunity, "objects", manager)
    selector = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert manager.filter.call_count == 2
    assert manager.filter.call_args_list[0].kwargs["tenant"] == contactaccountmanagement_tenant_a
    assert manager.filter.call_args_list[1].kwargs == {"pk__in": []}
    assert first.values_list.call_args.args == ("pk",)
    assert first.values_list.call_args.kwargs == {"flat": True}
    assert first.__getitem__.call_args.args[0].stop == 500
    assert final.only.called
    assert selector.fields["related_opportunities"].queryset is final


def test_contactaccountmanagement_plan_form_rejects_foreign_m2m_and_crafted_ids(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_plan_a,
):
    before = AccountPlan.objects.filter(tenant=contactaccountmanagement_tenant_a).count()
    crafted = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            related_opportunities=[
                str(contactaccountmanagement_account_b.pk),
                "9223372036854775808",
                "not-an-id",
            ],
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert not crafted.is_valid()
    assert "related_opportunities" in crafted.errors
    assert AccountPlan.objects.filter(tenant=contactaccountmanagement_tenant_a).count() == before

    foreign_account_form = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_b,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert contactaccountmanagement_account_b not in foreign_account_form.fields["account"].queryset
    assert not foreign_account_form.is_valid()
    assert "account" in foreign_account_form.errors

    widened = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_b,
            contactaccountmanagement_admin_a,
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    _contactaccountmanagement_widen(widened, "account", Party.objects.all())
    assert not widened.is_valid()
    assert "That record belongs to another workspace." in widened.errors["account"]


def test_contactaccountmanagement_edit_forms_disable_identity_fields(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_classification_a,
    contactaccountmanagement_plan_a,
):
    stakeholder_edit = sales_forms.AccountStakeholderForm(
        _contactaccountmanagement_stakeholder_payload(
            contactaccountmanagement_account_b,
            contactaccountmanagement_contact_b,
            role="advisor",
        ),
        instance=contactaccountmanagement_stakeholder_a,
        tenant=contactaccountmanagement_tenant_a,
    )
    assert stakeholder_edit.fields["account"].disabled is True
    assert stakeholder_edit.fields["contact"].disabled is True
    assert stakeholder_edit.is_valid(), stakeholder_edit.errors
    assert stakeholder_edit.cleaned_data["account"] == contactaccountmanagement_account_a
    assert stakeholder_edit.cleaned_data["contact"] == contactaccountmanagement_contact_a

    classification = sales_forms.AccountClassificationForm(
        _contactaccountmanagement_classification_payload(contactaccountmanagement_account_b),
        instance=contactaccountmanagement_classification_a,
        tenant=contactaccountmanagement_tenant_a,
    )
    assert classification.fields["account"].disabled is True
    assert classification.is_valid(), classification.errors
    assert classification.cleaned_data["account"] == contactaccountmanagement_account_a

    plan = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_b,
            contactaccountmanagement_plan_a.owner,
        ),
        instance=contactaccountmanagement_plan_a,
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_plan_a.owner,
    )
    assert plan.fields["account"].disabled is True
    assert plan.is_valid(), plan.errors
    assert plan.cleaned_data["account"] == contactaccountmanagement_account_a


def test_contactaccountmanagement_forms_do_not_expose_sensitive_or_derived_fields(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_consent_purpose_a,
    contactaccountmanagement_enrichment_event_a,
):
    proposal = sales_forms.PartyEnrichmentProposalForm(
        _contactaccountmanagement_proposal_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_consent_purpose_a,
            tenant=contactaccountmanagement_tenant_a.pk,
            status="applied",
            match_confidence="1.0",
            requested_by=contactaccountmanagement_admin_a.pk,
            reviewed_by=contactaccountmanagement_admin_a.pk,
            occurred_at="2026-01-01T00:00:00Z",
        ),
        tenant=contactaccountmanagement_tenant_a,
    )
    assert proposal.is_valid(), proposal.errors
    assert not {"tenant", "status", "match_confidence", "requested_by", "reviewed_by", "occurred_at"}.intersection(
        proposal.cleaned_data
    )

    plan = sales_forms.AccountPlanForm(
        _contactaccountmanagement_plan_payload(
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            tenant=contactaccountmanagement_tenant_a.pk,
            number="ACPL-FORGED",
            status="completed",
            created_at="2026-01-01T00:00:00Z",
        ),
        tenant=contactaccountmanagement_tenant_a,
        user=contactaccountmanagement_admin_a,
    )
    assert plan.is_valid(), plan.errors
    assert not {"tenant", "number", "status", "created_at"}.intersection(plan.cleaned_data)

    apply = sales_forms.PartyEnrichmentApplyForm(
        {"selected_fields": ["industry"], "review_note": "Reviewed."},
        tenant=contactaccountmanagement_tenant_a,
        event=contactaccountmanagement_enrichment_event_a,
    )
    assert apply.is_valid(), apply.errors
    invalid_apply = sales_forms.PartyEnrichmentApplyForm(
        {"selected_fields": ["job_title"]},
        tenant=contactaccountmanagement_tenant_a,
        event=contactaccountmanagement_enrichment_event_a,
    )
    assert not invalid_apply.is_valid()
    assert "selected_fields" in invalid_apply.errors

    reject = sales_forms.PartyEnrichmentRejectForm(
        {"review_note": "Deterministic rejection."},
        tenant=contactaccountmanagement_tenant_a,
    )
    assert reject.is_valid(), reject.errors
    assert not sales_forms.PartyEnrichmentRejectForm(
        {"review_note": ""},
        tenant=contactaccountmanagement_tenant_a,
    ).is_valid()
    assert not sales_forms.PartyEnrichmentRejectForm(
        {"review_note": "x" * 1001},
        tenant=contactaccountmanagement_tenant_a,
    ).is_valid()

    assert "raw_payload" not in {field.name for field in PartyEnrichmentEvent._meta.fields}
    assert "provider_response" not in {field.name for field in PartyEnrichmentEvent._meta.fields}
    assert "health" not in sales_forms.AccountPlanForm.base_fields
    assert "annual_revenue" not in sales_forms.AccountClassificationForm.base_fields
    assert "account" not in sales_forms.PartyEnrichmentRejectForm.base_fields
