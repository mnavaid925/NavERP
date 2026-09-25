from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, connection, models, transaction
from django.db.models import Q
from django.db.models.deletion import CASCADE, PROTECT, SET_NULL
from django.db.models.fields import NOT_PROVIDED
from django.utils import timezone

from apps.crm.models import Opportunity
from apps.sales.models import (
    AccountClassification,
    AccountPlan,
    AccountStakeholder,
    PartyEnrichmentEvent,
)
from apps.sales.models.ContactAccountManagement.AccountPlans import (
    validate_account_plan_opportunities,
    validate_account_plan_opportunity_links,
)
from apps.sales.models.ContactAccountManagement.PartyEnrichment import (
    ENRICHMENT_FIELD_CHOICES,
    ENRICHMENT_FIELDS,
    EXTERNAL_SOURCE_KINDS,
    ORGANIZATION_ENRICHMENT_FIELDS,
    PERSON_ENRICHMENT_FIELDS,
    validate_enrichment_changes,
    validate_enrichment_fields_for_party,
)
from apps.sales.tests.conftest import (
    _contactaccountmanagement_classification,
    _contactaccountmanagement_enrichment_event,
    _contactaccountmanagement_plan,
    _contactaccountmanagement_stakeholder,
)

pytestmark = pytest.mark.django_db


_contactaccountmanagement_model_fields = {
    PartyEnrichmentEvent: (
        "tenant",
        "created_at",
        "party",
        "kind",
        "source_kind",
        "source_name",
        "source_reference",
        "status",
        "match_confidence",
        "changes",
        "legal_basis_purpose",
        "requested_by",
        "reviewed_by",
        "occurred_at",
        "applied_at",
        "idempotency_key",
        "error_code",
        "error_summary",
    ),
    AccountStakeholder: (
        "tenant",
        "created_at",
        "updated_at",
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
    AccountClassification: (
        "tenant",
        "created_at",
        "updated_at",
        "account",
        "tier",
        "lifecycle_stage",
        "strategic_priority",
        "revenue_potential",
        "wallet_category",
        "rationale",
        "effective_on",
        "review_due_on",
        "classified_by",
    ),
    AccountPlan: (
        "tenant",
        "created_at",
        "updated_at",
        "number",
        "account",
        "title",
        "period_start",
        "period_end",
        "status",
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
    ),
}

_contactaccountmanagement_choices = {
    PartyEnrichmentEvent: {
        "kind": (
            ("firmographic", "Firmographic"),
            ("contact", "Contact"),
            ("email_validation", "Email validation"),
            ("phone_validation", "Phone validation"),
            ("social", "Social profile"),
            ("employment_change", "Employment change"),
            ("duplicate_check", "Duplicate check"),
        ),
        "source_kind": (
            ("manual", "Manual"),
            ("provider", "Provider"),
            ("email_signature", "Email signature"),
            ("linkedin", "LinkedIn"),
            ("import", "Import"),
            ("api", "API"),
        ),
        "status": (
            ("proposed", "Proposed"),
            ("applied", "Applied"),
            ("rejected", "Rejected"),
            ("no_match", "No match"),
            ("failed", "Failed"),
        ),
    },
    AccountStakeholder: {
        "role": (
            ("decision_maker", "Decision Maker"),
            ("economic_buyer", "Economic Buyer"),
            ("champion", "Champion"),
            ("influencer", "Influencer"),
            ("blocker", "Blocker"),
            ("technical_evaluator", "Technical Evaluator"),
            ("procurement", "Procurement"),
            ("end_user", "End User"),
            ("advisor", "Advisor"),
            ("other", "Other"),
        ),
        "influence": (
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
            ("unknown", "Unknown"),
        ),
        "attitude": (
            ("positive", "Positive"),
            ("neutral", "Neutral"),
            ("negative", "Negative"),
            ("unknown", "Unknown"),
        ),
        "relationship_strength": (
            ("strong", "Strong"),
            ("moderate", "Moderate"),
            ("weak", "Weak"),
            ("unknown", "Unknown"),
        ),
        "status": (
            ("active", "Active"),
            ("former", "Former"),
        ),
    },
    AccountClassification: {
        "tier": (
            ("strategic", "Strategic"),
            ("key", "Key"),
            ("growth", "Growth"),
            ("nurture", "Nurture"),
        ),
        "lifecycle_stage": (
            ("prospect", "Prospect"),
            ("active_customer", "Active Customer"),
            ("expansion_candidate", "Expansion Candidate"),
            ("dormant", "Dormant"),
            ("former_customer", "Former Customer"),
        ),
        "strategic_priority": (
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
        ),
        "revenue_potential": (
            ("very_high", "Very High"),
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
            ("unknown", "Unknown"),
        ),
        "wallet_category": (
            ("none", "None"),
            ("small", "Small"),
            ("medium", "Medium"),
            ("large", "Large"),
            ("full_wallet", "Full Wallet"),
        ),
    },
    AccountPlan: {
        "status": (
            ("draft", "Draft"),
            ("active", "Active"),
            ("review_due", "Review Due"),
            ("completed", "Completed"),
            ("archived", "Archived"),
        ),
    },
}

_contactaccountmanagement_relation_contracts = {
    PartyEnrichmentEvent: {
        "tenant": ("core.Tenant", CASCADE, "+", False, True, False),
        "party": ("core.Party", PROTECT, "sales_enrichment_events", False, True, False),
        "legal_basis_purpose": ("core.ConsentPurpose", PROTECT, "sales_enrichment_events", True, True, False),
        "requested_by": ("accounts.User", SET_NULL, "sales_requested_enrichment_events", True, False, False),
        "reviewed_by": ("accounts.User", SET_NULL, "sales_reviewed_enrichment_events", True, False, False),
    },
    AccountStakeholder: {
        "tenant": ("core.Tenant", CASCADE, "+", False, True, False),
        "account": ("core.Party", PROTECT, "sales_account_stakeholders", False, True, False),
        "contact": ("core.Party", PROTECT, "sales_stakeholder_contacts", False, True, False),
    },
    AccountClassification: {
        "tenant": ("core.Tenant", CASCADE, "+", False, True, False),
        "account": ("core.Party", PROTECT, "sales_account_classification", False, True, True),
        "classified_by": ("accounts.User", SET_NULL, "sales_account_classifications", True, False, False),
    },
    AccountPlan: {
        "tenant": ("core.Tenant", CASCADE, "+", False, True, False),
        "account": ("core.Party", PROTECT, "sales_account_plans", False, True, False),
        "owner": ("accounts.User", PROTECT, "sales_owned_account_plans", False, True, False),
    },
}

_contactaccountmanagement_unique_constraints = {
    PartyEnrichmentEvent: {
        "sales_pee_tenant_key_uniq": ("tenant", "idempotency_key"),
    },
    AccountStakeholder: {
        "sales_ast_tenant_account_contact_role_uniq": ("tenant", "account", "contact", "role"),
    },
    AccountClassification: {
        "sales_aclass_tenant_account_uniq": ("tenant", "account"),
    },
    AccountPlan: {
        "sales_acpl_tenant_number_uniq": ("tenant", "number"),
    },
}

_contactaccountmanagement_index_contracts = {
    PartyEnrichmentEvent: {
        "sales_pee_tnt_party_idx": ("tenant", "party", "-occurred_at"),
        "sales_pee_tnt_status_idx": ("tenant", "status", "-occurred_at"),
        "sales_pee_tnt_kind_idx": ("tenant", "kind", "-occurred_at"),
    },
    AccountStakeholder: {
        "sales_ast_acct_status_idx": ("tenant", "account", "status"),
        "sales_ast_contact_status_idx": ("tenant", "contact", "status"),
        "sales_ast_role_attitude_idx": ("tenant", "role", "attitude"),
    },
    AccountClassification: {
        "sales_aclass_tnt_tier_life_idx": ("tenant", "tier", "lifecycle_stage"),
        "sales_aclass_prio_idx": ("tenant", "strategic_priority", "review_due_on"),
    },
    AccountPlan: {
        "sales_acpl_acct_status_idx": ("tenant", "account", "status"),
        "sales_acpl_owner_rev_idx": ("tenant", "owner", "next_review_on"),
        "sales_acpl_stat_rev_idx": ("tenant", "status", "next_review_on"),
    },
}


def _contactaccountmanagement_assert_relation(
    model,
    field_name,
    related_label,
    on_delete,
    related_name,
    null,
    editable,
    one_to_one,
):
    field = model._meta.get_field(field_name)
    assert field.related_model._meta.label == related_label
    assert field.remote_field.on_delete is on_delete
    assert field.remote_field.related_name == related_name
    assert field.null is null
    assert field.editable is editable
    assert field.one_to_one is one_to_one


def _contactaccountmanagement_unsaved_enrichment(
    tenant,
    party,
    requested_by,
    changes,
    **overrides,
):
    fields = {
        "tenant": tenant,
        "party": party,
        "kind": "contact" if party.kind == "person" else "firmographic",
        "source_kind": "manual",
        "changes": changes,
        "requested_by": requested_by,
    }
    fields.update(overrides)
    return PartyEnrichmentEvent(**fields)


def test_contactaccountmanagement_model_fields_choices_constraints_and_indexes():
    expected_ordering = {
        PartyEnrichmentEvent: ["-occurred_at", "-id"],
        AccountStakeholder: ["account__name", "contact__name", "role"],
        AccountClassification: ["-effective_on", "account__name"],
        AccountPlan: ["-period_start", "-created_at"],
    }
    expected_tables = {
        "sales_partyenrichmentevent",
        "sales_accountstakeholder",
        "sales_accountclassification",
        "sales_accountplan",
    }

    for model, expected_fields in _contactaccountmanagement_model_fields.items():
        actual_fields = tuple(field.name for field in model._meta.fields if not field.primary_key)
        assert actual_fields == expected_fields
        assert model._meta.ordering == expected_ordering[model]
        assert apps.get_model("sales", model._meta.model_name) is model
        for field_name, expected_choices in _contactaccountmanagement_choices.get(model, {}).items():
            assert tuple(tuple(choice) for choice in model._meta.get_field(field_name).choices) == expected_choices
        for field_name, expected in _contactaccountmanagement_relation_contracts[model].items():
            _contactaccountmanagement_assert_relation(model, field_name, *expected)
        actual_unique = {
            constraint.name: tuple(constraint.fields)
            for constraint in model._meta.constraints
            if isinstance(constraint, models.UniqueConstraint)
        }
        assert actual_unique == _contactaccountmanagement_unique_constraints[model]
        actual_indexes = {
            index.name: tuple(index.fields)
            for index in model._meta.indexes
        }
        assert actual_indexes == _contactaccountmanagement_index_contracts[model]

    confidence = PartyEnrichmentEvent._meta.get_field("match_confidence")
    assert (confidence.max_digits, confidence.decimal_places, confidence.null, confidence.blank) == (5, 4, True, True)
    assert tuple(
        validator.limit_value
        for validator in confidence.validators
        if isinstance(validator, (MinValueValidator, MaxValueValidator))
    ) == (Decimal("0"), Decimal("1"))
    assert PartyEnrichmentEvent._meta.get_field("status").get_default() == "proposed"
    assert AccountStakeholder._meta.get_field("status").get_default() == "active"
    assert AccountPlan._meta.get_field("status").get_default() == "draft"
    assert AccountStakeholder._meta.get_field("role").default is NOT_PROVIDED
    assert AccountClassification._meta.get_field("tier").get_default() == "growth"
    assert AccountClassification._meta.get_field("lifecycle_stage").get_default() == "prospect"
    assert AccountClassification._meta.get_field("strategic_priority").get_default() == "medium"
    assert AccountClassification._meta.get_field("revenue_potential").get_default() == "unknown"
    assert AccountClassification._meta.get_field("wallet_category").get_default() == "none"
    assert AccountPlan.NUMBER_PREFIX == "ACPL"
    assert AccountPlan._meta.get_field("number").max_length == 20
    assert AccountPlan._meta.get_field("number").editable is False
    assert PartyEnrichmentEvent._meta.get_field("occurred_at").editable is False
    assert PartyEnrichmentEvent._meta.get_field("applied_at").editable is False

    opportunity_field = AccountPlan._meta.get_field("related_opportunities")
    assert opportunity_field.related_model._meta.label == "crm.Opportunity"
    assert opportunity_field.remote_field.related_name == "sales_account_plans"
    assert opportunity_field.blank is True
    assert opportunity_field.remote_field.through._meta.auto_created is AccountPlan

    confidence_constraint = {
        constraint.name: constraint
        for constraint in PartyEnrichmentEvent._meta.constraints
        if isinstance(constraint, models.CheckConstraint)
    }
    assert set(confidence_constraint) == {"sales_pee_confidence_valid"}
    expected_condition = Q(match_confidence__isnull=True) | Q(match_confidence__gte=0, match_confidence__lte=1)
    assert confidence_constraint["sales_pee_confidence_valid"].condition == expected_condition

    assert connection.vendor == "sqlite"
    assert expected_tables <= set(connection.introspection.table_names())


def test_contactaccountmanagement_enrichment_allowlist_and_party_kind_validation(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
):
    assert tuple(tuple(choice) for choice in ENRICHMENT_FIELD_CHOICES) == (
        ("job_title", "Job title"),
        ("department", "Department"),
        ("linkedin", "LinkedIn URL"),
        ("work_email", "Work email"),
        ("phone", "Phone"),
        ("mobile", "Mobile"),
        ("website", "Website"),
        ("industry", "Industry"),
        ("employee_count", "Employee count"),
        ("annual_revenue", "Annual revenue"),
    )
    assert ENRICHMENT_FIELDS == {choice[0] for choice in ENRICHMENT_FIELD_CHOICES}
    assert PERSON_ENRICHMENT_FIELDS == {
        "job_title",
        "department",
        "linkedin",
        "work_email",
        "phone",
        "mobile",
    }
    assert ORGANIZATION_ENRICHMENT_FIELDS == {
        "website",
        "industry",
        "employee_count",
        "annual_revenue",
    }

    person_changes = {
        "job_title": {"value": "Chief Operating Officer", "confidence": 1},
        "department": {"value": "Operations"},
        "linkedin": {"value": "https://www.linkedin.com/in/acme-contact", "confidence": 0.9},
        "work_email": {"value": "person@acme.example"},
        "phone": {"value": "123"},
        "mobile": {"value": "1" * 40},
    }
    organization_changes = {
        "website": {"value": "https://account.acme.example", "confidence": 0},
        "industry": {"value": "technology"},
        "employee_count": {"value": 42, "confidence": 0.5},
        "annual_revenue": {"value": "125000.50", "confidence": 0.8},
    }

    assert validate_enrichment_changes(person_changes) == person_changes
    normalized_organization = validate_enrichment_changes(organization_changes)
    assert normalized_organization["employee_count"]["value"] == 42
    assert normalized_organization["annual_revenue"]["value"] == "125000.50"
    assert normalized_organization["annual_revenue"]["confidence"] == 0.8
    assert validate_enrichment_fields_for_party(contactaccountmanagement_contact_a, person_changes) is None
    assert validate_enrichment_fields_for_party(contactaccountmanagement_account_a, organization_changes) is None

    person_event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_contact_a,
        contactaccountmanagement_admin_a,
        changes=person_changes,
    )
    organization_event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        changes=organization_changes,
    )
    assert person_event.changes == person_changes
    assert organization_event.changes == normalized_organization

    invalid_applicability = (
        (
            contactaccountmanagement_contact_a,
            "contact",
            {"website": {"value": "https://person.example"}},
        ),
        (
            contactaccountmanagement_contact_a,
            "contact",
            {"industry": {"value": "technology"}},
        ),
        (
            contactaccountmanagement_account_a,
            "firmographic",
            {"job_title": {"value": "Chief Operating Officer"}},
        ),
        (
            contactaccountmanagement_account_a,
            "firmographic",
            {"work_email": {"value": "person@acme.example"}},
        ),
    )
    for party, kind, changes in invalid_applicability:
        with pytest.raises(ValidationError):
            validate_enrichment_fields_for_party(party, changes)
        event = _contactaccountmanagement_unsaved_enrichment(
            contactaccountmanagement_tenant_a,
            party,
            contactaccountmanagement_admin_a,
            changes,
            kind=kind,
        )
        with pytest.raises(ValidationError) as error:
            event.full_clean()
        assert "changes" in error.value.message_dict

    unsupported = _contactaccountmanagement_unsaved_enrichment(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_contact_a,
        contactaccountmanagement_admin_a,
        {"unsupported_field": {"value": "value"}},
    )
    with pytest.raises(ValidationError) as error:
        unsupported.full_clean()
    assert "changes" in error.value.message_dict


def test_contactaccountmanagement_enrichment_scalar_credential_and_boundary_validation():
    assert validate_enrichment_changes({"employee_count": {"value": 0}}) == {"employee_count": {"value": 0}}
    assert validate_enrichment_changes({"employee_count": {"value": 2_147_483_647}}) == {
        "employee_count": {"value": 2_147_483_647}
    }
    assert validate_enrichment_changes({"annual_revenue": {"value": "0"}}) == {"annual_revenue": {"value": "0.00"}}
    assert validate_enrichment_changes({"annual_revenue": {"value": "999999999999.99"}}) == {
        "annual_revenue": {"value": "999999999999.99"}
    }
    assert validate_enrichment_changes({"job_title": {"value": "x" * 120, "confidence": 0}})["job_title"] == {
        "value": "x" * 120,
        "confidence": 0.0,
    }
    assert validate_enrichment_changes({"job_title": {"value": "x" * 120, "confidence": 1}})["job_title"][
        "confidence"
    ] == 1.0
    assert validate_enrichment_changes({"phone": {"value": "123"}})["phone"]["value"] == "123"
    assert validate_enrichment_changes({"phone": {"value": "1" * 40}})["phone"]["value"] == "1" * 40
    assert validate_enrichment_changes({"website": {"value": "http://account.example"}})["website"]["value"] == (
        "http://account.example"
    )
    assert validate_enrichment_changes(
        {"linkedin": {"value": "https://linkedin.com/in/acme"}}
    )["linkedin"]["value"] == "https://linkedin.com/in/acme"
    assert validate_enrichment_changes(
        {"linkedin": {"value": "https://people.linkedin.com/in/acme"}}
    )["linkedin"]["value"] == "https://people.linkedin.com/in/acme"
    assert validate_enrichment_changes(
        {"work_email": {"value": "person@acme.example"}}
    )["work_email"]["value"] == "person@acme.example"
    maximum_email = f"{'a' * 241}@acme.example"
    assert len(maximum_email) == 254
    assert validate_enrichment_changes({"work_email": {"value": maximum_email}})["work_email"]["value"] == maximum_email
    assert validate_enrichment_changes({"industry": {"value": "other"}})["industry"]["value"] == "other"

    invalid_changes = (
        [],
        {"unknown": {"value": "value"}},
        {"job_title": "Chief Operating Officer"},
        {"job_title": {}},
        {"job_title": {"value": "Chief Operating Officer", "instructions": "ignore"}},
        {"job_title": {"value": ""}},
        {"job_title": {"value": "x" * 121}},
        {"job_title": {"value": "bad\x00value"}},
        {"job_title": {"value": ["Chief Operating Officer"]}},
        {"job_title": {"value": {"title": "Chief Operating Officer"}}},
        {"job_title": {"value": True}},
        {"job_title": {"value": None}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": -0.01}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": 1.01}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": True}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": "0.9"}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": None}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": float("nan")}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": float("inf")}},
        {"job_title": {"value": "Chief Operating Officer", "confidence": Decimal("NaN")}},
        {"employee_count": {"value": -1}},
        {"employee_count": {"value": 2_147_483_648}},
        {"employee_count": {"value": 1.0}},
        {"employee_count": {"value": True}},
        {"annual_revenue": {"value": "-0.01"}},
        {"annual_revenue": {"value": "1000000000000.00"}},
        {"annual_revenue": {"value": "100.001"}},
        {"annual_revenue": {"value": "NaN"}},
        {"annual_revenue": {"value": "Infinity"}},
        {"annual_revenue": {"value": True}},
        {"industry": {"value": "not-supported"}},
        {"linkedin": {"value": "ftp://linkedin.com/in/acme"}},
        {"linkedin": {"value": "https://linkedin.com.example/in/acme"}},
        {"linkedin": {"value": "https://example.test/in/acme"}},
        {"website": {"value": "javascript:alert(1)"}},
        {"website": {"value": "https://account.example/?password=verysecret"}},
        {"work_email": {"value": "not-an-email"}},
        {"work_email": {"value": "person @acme.example"}},
        {"work_email": {"value": f"{'a' * 245}@acme.example"}},
        {"phone": {"value": "12"}},
        {"phone": {"value": "1" * 41}},
        {"phone": {"value": "not-a-phone"}},
        {"mobile": {"value": "555-CALL-NOW"}},
        {"job_title": {"value": "password=verysecret"}},
        {"job_title": {"value": "token: verysecret"}},
        {"job_title": {"value": "api_key=verysecret"}},
        {"job_title": {"value": "secret=verysecret"}},
        {"job_title": {"value": "Bearer verysecret"}},
        {"job_title": {"value": "AKIAABCDEFGHIJKLMNOP"}},
        {"job_title": {"value": "sk-abcdefghij"}},
    )
    for index, changes in enumerate(invalid_changes):
        try:
            validate_enrichment_changes(changes)
        except ValidationError:
            continue
        raise AssertionError(f"invalid change case {index} was accepted: {changes!r}")


def test_contactaccountmanagement_enrichment_source_purpose_confidence_and_tenant_validation(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_consent_purpose_a,
    contactaccountmanagement_consent_purpose_b,
):
    assert EXTERNAL_SOURCE_KINDS == {"provider", "email_signature", "linkedin", "import", "api"}
    for source_kind in sorted(EXTERNAL_SOURCE_KINDS):
        event = _contactaccountmanagement_enrichment_event(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            legal_basis_purpose=contactaccountmanagement_consent_purpose_a,
            source_kind=source_kind,
        )
        assert event.legal_basis_purpose_id == contactaccountmanagement_consent_purpose_a.pk

    for source_kind in sorted(EXTERNAL_SOURCE_KINDS):
        event = _contactaccountmanagement_unsaved_enrichment(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            {"industry": {"value": "technology"}},
            source_kind=source_kind,
        )
        with pytest.raises(ValidationError) as error:
            event.full_clean()
        assert "legal_basis_purpose" in error.value.message_dict

    for confidence in (None, Decimal("0"), Decimal("0.0001"), Decimal("1.0000"), Decimal("1")):
        event = _contactaccountmanagement_enrichment_event(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            match_confidence=confidence,
        )
        if confidence is None:
            assert event.match_confidence is None
        else:
            assert event.match_confidence == confidence

    for confidence in (Decimal("-0.0001"), Decimal("1.0001"), Decimal("NaN"), "not-decimal"):
        event = _contactaccountmanagement_unsaved_enrichment(
            contactaccountmanagement_tenant_a,
            contactaccountmanagement_account_a,
            contactaccountmanagement_admin_a,
            {"industry": {"value": "technology"}},
            match_confidence=confidence,
        )
        with pytest.raises(ValidationError) as error:
            event.save()
        assert "match_confidence" in error.value.message_dict

    contactaccountmanagement_consent_purpose_a.is_active = False
    contactaccountmanagement_consent_purpose_a.save(update_fields=["is_active"])
    inactive_purpose_event = _contactaccountmanagement_unsaved_enrichment(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        {"industry": {"value": "technology"}},
        legal_basis_purpose=contactaccountmanagement_consent_purpose_a,
    )
    with pytest.raises(ValidationError) as error:
        inactive_purpose_event.full_clean()
    assert "legal_basis_purpose" in error.value.message_dict

    contactaccountmanagement_admin_a.is_active = False
    contactaccountmanagement_admin_a.save(update_fields=["is_active"])
    inactive_requester = _contactaccountmanagement_unsaved_enrichment(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        {"industry": {"value": "technology"}},
    )
    with pytest.raises(ValidationError) as error:
        inactive_requester.full_clean()
    assert "requested_by" in error.value.message_dict

    cases = (
        (
            _contactaccountmanagement_unsaved_enrichment(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_b,
                contactaccountmanagement_admin_a,
                {"industry": {"value": "technology"}},
            ),
            "party",
        ),
        (
            _contactaccountmanagement_unsaved_enrichment(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_a,
                contactaccountmanagement_admin_b,
                {"industry": {"value": "technology"}},
            ),
            "requested_by",
        ),
        (
            _contactaccountmanagement_unsaved_enrichment(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_a,
                contactaccountmanagement_admin_a,
                {"industry": {"value": "technology"}},
                legal_basis_purpose=contactaccountmanagement_consent_purpose_b,
            ),
            "legal_basis_purpose",
        ),
        (
            _contactaccountmanagement_unsaved_enrichment(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_a,
                contactaccountmanagement_admin_a,
                {"industry": {"value": "technology"}},
                reviewed_by=contactaccountmanagement_admin_b,
            ),
            "reviewed_by",
        ),
    )
    for event, expected_field in cases:
        with pytest.raises(ValidationError) as error:
            event.full_clean()
        assert expected_field in error.value.message_dict


def test_contactaccountmanagement_enrichment_metadata_is_sanitized(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
):
    event = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        source_name="password=verysecret",
        source_reference="https://provider.example/?access_token=verysecret",
        error_summary="person@acme.example or +1-555-0199",
    )
    persisted_values = f"{event.source_name} {event.source_reference} {event.error_summary}"
    assert "verysecret" not in persisted_values
    assert "person@acme.example" not in persisted_values
    assert "+1-555-0199" not in persisted_values
    assert "[redacted" in persisted_values
    assert "provider_response" not in PartyEnrichmentEvent._meta.fields
    assert "raw_payload" not in PartyEnrichmentEvent._meta.fields


def test_contactaccountmanagement_enrichment_database_constraints_are_tenant_scoped(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
):
    first = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
        idempotency_key="shared-enrichment-key",
    )
    second = _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_account_b,
        contactaccountmanagement_admin_b,
        idempotency_key="shared-enrichment-key",
    )
    assert PartyEnrichmentEvent.objects.filter(idempotency_key="shared-enrichment-key").count() == 2
    assert first.pk != second.pk

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PartyEnrichmentEvent.objects.create(
                tenant=contactaccountmanagement_tenant_a,
                party=contactaccountmanagement_account_a,
                kind="firmographic",
                source_kind="manual",
                changes={"industry": {"value": "finance"}},
                requested_by=contactaccountmanagement_admin_a,
                idempotency_key="shared-enrichment-key",
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PartyEnrichmentEvent.objects.filter(pk=first.pk).update(match_confidence=Decimal("1.0001"))
    first.refresh_from_db()
    assert first.match_confidence == Decimal("0.9500")


def test_contactaccountmanagement_stakeholder_identity_kind_tenant_and_date_validation(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_stakeholder_a,
):
    today = timezone.localdate()
    assert contactaccountmanagement_stakeholder_a.status == "active"
    assert contactaccountmanagement_stakeholder_a.valid_from == today - timedelta(days=30)
    assert contactaccountmanagement_stakeholder_a.valid_to is None

    base = {
        "tenant": contactaccountmanagement_tenant_a,
        "account": contactaccountmanagement_account_a,
        "contact": contactaccountmanagement_contact_a,
        "role": "advisor",
    }
    defaults = AccountStakeholder(**base)
    defaults.full_clean()
    assert (defaults.influence, defaults.attitude, defaults.relationship_strength, defaults.status) == (
        "unknown",
        "unknown",
        "unknown",
        "active",
    )

    equal_period = AccountStakeholder(
        **base,
        valid_from=today,
        valid_to=today,
    )
    equal_period.full_clean()
    open_started_period = AccountStakeholder(
        **base,
        valid_from=None,
        valid_to=today,
    )
    open_started_period.full_clean()

    reversed_period = AccountStakeholder(
        **base,
        valid_from=today,
        valid_to=today - timedelta(days=1),
    )
    with pytest.raises(ValidationError) as error:
        reversed_period.full_clean()
    assert "valid_to" in error.value.message_dict

    identity_cases = (
        ({"account": contactaccountmanagement_contact_a}, "account"),
        ({"contact": contactaccountmanagement_account_a}, "contact"),
        (
            {
                "account": contactaccountmanagement_account_a,
                "contact": contactaccountmanagement_account_a,
            },
            "contact",
        ),
    )
    for overrides, expected_field in identity_cases:
        stakeholder = AccountStakeholder(**{**base, **overrides})
        with pytest.raises(ValidationError) as error:
            stakeholder.full_clean()
        assert expected_field in error.value.message_dict


def test_contactaccountmanagement_stakeholder_unique_account_contact_role(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_manager_a,
    contactaccountmanagement_stakeholder_a,
    contactaccountmanagement_stakeholder_b,
):
    same_account_other_role = _contactaccountmanagement_stakeholder(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_contact_a,
        role="champion",
    )
    same_account_other_contact = _contactaccountmanagement_stakeholder(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_manager_a,
        role="decision_maker",
    )
    same_contact_other_account = _contactaccountmanagement_stakeholder(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_child_a,
        contactaccountmanagement_contact_a,
        role="decision_maker",
    )
    assert same_account_other_role.pk != contactaccountmanagement_stakeholder_a.pk
    assert same_account_other_contact.pk != contactaccountmanagement_stakeholder_a.pk
    assert same_contact_other_account.pk != contactaccountmanagement_stakeholder_a.pk
    assert contactaccountmanagement_stakeholder_a.pk != contactaccountmanagement_stakeholder_b.pk
    assert AccountStakeholder.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account=contactaccountmanagement_account_a,
        contact=contactaccountmanagement_contact_a,
        role="decision_maker",
    ).count() == 1

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AccountStakeholder.objects.create(
                tenant=contactaccountmanagement_tenant_a,
                account=contactaccountmanagement_account_a,
                contact=contactaccountmanagement_contact_a,
                role="decision_maker",
            )


def test_contactaccountmanagement_classification_current_row_and_review_rules(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
):
    today = timezone.localdate()
    base = {
        "tenant": contactaccountmanagement_tenant_a,
        "account": contactaccountmanagement_account_a,
        "rationale": "Expansion potential and executive sponsorship.",
    }
    defaults = AccountClassification(**base)
    defaults.full_clean()
    assert defaults.effective_on == today
    assert defaults.tier == "growth"
    assert defaults.lifecycle_stage == "prospect"
    assert defaults.strategic_priority == "medium"
    assert defaults.revenue_potential == "unknown"
    assert defaults.wallet_category == "none"
    assert defaults.review_due_on is None

    missing_rationale = AccountClassification(
        **{**base, "rationale": "   "},
    )
    with pytest.raises(ValidationError) as error:
        missing_rationale.full_clean()
    assert "rationale" in error.value.message_dict

    person_account = AccountClassification(
        **{**base, "account": contactaccountmanagement_contact_a},
    )
    with pytest.raises(ValidationError) as error:
        person_account.full_clean()
    assert "account" in error.value.message_dict

    for tier in ("strategic", "key"):
        missing_review = AccountClassification(**{**base, "tier": tier})
        with pytest.raises(ValidationError) as error:
            missing_review.full_clean()
        assert "review_due_on" in error.value.message_dict

    reversed_review = AccountClassification(
        **{
            **base,
            "tier": "strategic",
            "effective_on": today,
            "review_due_on": today - timedelta(days=1),
        }
    )
    with pytest.raises(ValidationError) as error:
        reversed_review.full_clean()
    assert "review_due_on" in error.value.message_dict

    growth_without_review = AccountClassification(**{**base, "tier": "growth"})
    growth_without_review.full_clean()

    classification = _contactaccountmanagement_classification(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        classified_by=contactaccountmanagement_admin_a,
    )
    assert classification.account_id == contactaccountmanagement_account_a.pk
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AccountClassification.objects.create(
                tenant=contactaccountmanagement_tenant_a,
                account=contactaccountmanagement_account_a,
                rationale="A second current classification is forbidden.",
            )


def test_contactaccountmanagement_plan_number_owner_period_and_tenant_rules(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_plan_a,
    contactaccountmanagement_plan_b,
):
    today = timezone.localdate()
    assert contactaccountmanagement_plan_a.number == "ACPL-00001"
    assert contactaccountmanagement_plan_b.number == "ACPL-00001"
    assert contactaccountmanagement_plan_a.status == "draft"
    assert contactaccountmanagement_plan_a.related_opportunities.count() == 0

    base = {
        "tenant": contactaccountmanagement_tenant_a,
        "account": contactaccountmanagement_account_a,
        "title": "Deterministic Account Plan",
        "period_start": today,
        "period_end": today + timedelta(days=90),
        "owner": contactaccountmanagement_admin_a,
    }
    default_status = AccountPlan(**base)
    default_status.full_clean()
    assert default_status.status == "draft"

    same_day = AccountPlan(**{**base, "period_start": today, "period_end": today})
    same_day.full_clean()
    reversed_period = AccountPlan(**{**base, "period_end": today - timedelta(days=1)})
    with pytest.raises(ValidationError) as error:
        reversed_period.full_clean()
    assert "period_end" in error.value.message_dict

    person_account = AccountPlan(**{**base, "account": contactaccountmanagement_contact_a})
    with pytest.raises(ValidationError) as error:
        person_account.full_clean()
    assert "account" in error.value.message_dict

    foreign_owner = AccountPlan(**{**base, "owner": contactaccountmanagement_admin_b})
    with pytest.raises(ValidationError) as error:
        foreign_owner.full_clean()
    assert "owner" in error.value.message_dict

    contactaccountmanagement_admin_a.is_active = False
    contactaccountmanagement_admin_a.save(update_fields=["is_active"])
    inactive_owner = AccountPlan(**base)
    with pytest.raises(ValidationError) as error:
        inactive_owner.full_clean()
    assert "owner" in error.value.message_dict


def test_contactaccountmanagement_plan_m2m_invariants_without_opportunity_rows(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_plan_a,
):
    plan = contactaccountmanagement_plan_a
    opportunity_field = AccountPlan._meta.get_field("related_opportunities")
    assert opportunity_field.related_model is Opportunity
    assert Opportunity.objects.count() == 0
    assert validate_account_plan_opportunities(contactaccountmanagement_tenant_a, plan.account, ()) is None

    for opportunity_id in (0, 9_223_372_036_854_775_808):
        with pytest.raises(ValidationError):
            validate_account_plan_opportunity_links(
                sender=AccountPlan.related_opportunities.through,
                instance=plan,
                action="pre_add",
                reverse=False,
                model=Opportunity,
                pk_set={opportunity_id},
            )
        assert plan.related_opportunities.count() == 0
        assert Opportunity.objects.count() == 0


def test_contactaccountmanagement_models_reject_cross_tenant_relationships(
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_admin_a,
    contactaccountmanagement_admin_b,
    contactaccountmanagement_account_a,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_consent_purpose_b,
):
    today = timezone.localdate()
    stakeholder_cases = (
        ({"account": contactaccountmanagement_account_b}, "account"),
        ({"contact": contactaccountmanagement_contact_b}, "contact"),
    )
    stakeholder_base = {
        "tenant": contactaccountmanagement_tenant_a,
        "account": contactaccountmanagement_account_a,
        "contact": contactaccountmanagement_contact_a,
        "role": "advisor",
    }
    for overrides, expected_field in stakeholder_cases:
        stakeholder = AccountStakeholder(**{**stakeholder_base, **overrides})
        with pytest.raises(ValidationError) as error:
            stakeholder.full_clean()
        assert expected_field in error.value.message_dict

    classification_cases = (
        ({"account": contactaccountmanagement_account_b}, "account"),
        ({"classified_by": contactaccountmanagement_admin_b}, "classified_by"),
    )
    classification_base = {
        "tenant": contactaccountmanagement_tenant_a,
        "account": contactaccountmanagement_account_a,
        "rationale": "Cross-tenant validation case.",
    }
    for overrides, expected_field in classification_cases:
        classification = AccountClassification(**{**classification_base, **overrides})
        with pytest.raises(ValidationError) as error:
            classification.full_clean()
        assert expected_field in error.value.message_dict

    plan_cases = (
        ({"account": contactaccountmanagement_account_b}, "account"),
        ({"owner": contactaccountmanagement_admin_b}, "owner"),
    )
    plan_base = {
        "tenant": contactaccountmanagement_tenant_a,
        "account": contactaccountmanagement_account_a,
        "title": "Cross-tenant validation case.",
        "period_start": today,
        "period_end": today + timedelta(days=30),
        "owner": contactaccountmanagement_admin_a,
    }
    for overrides, expected_field in plan_cases:
        plan = AccountPlan(**{**plan_base, **overrides})
        with pytest.raises(ValidationError) as error:
            plan.full_clean()
        assert expected_field in error.value.message_dict

    enrichment_cases = (
        (
            _contactaccountmanagement_unsaved_enrichment(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_b,
                contactaccountmanagement_admin_a,
                {"industry": {"value": "technology"}},
            ),
            "party",
        ),
        (
            _contactaccountmanagement_unsaved_enrichment(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_a,
                contactaccountmanagement_admin_b,
                {"industry": {"value": "technology"}},
            ),
            "requested_by",
        ),
        (
            _contactaccountmanagement_unsaved_enrichment(
                contactaccountmanagement_tenant_a,
                contactaccountmanagement_account_a,
                contactaccountmanagement_admin_a,
                {"industry": {"value": "technology"}},
                legal_basis_purpose=contactaccountmanagement_consent_purpose_b,
            ),
            "legal_basis_purpose",
        ),
    )
    for event, expected_field in enrichment_cases:
        with pytest.raises(ValidationError) as error:
            event.full_clean()
        assert expected_field in error.value.message_dict

    assert not AccountStakeholder.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account__in=(contactaccountmanagement_account_b, contactaccountmanagement_account_a),
    ).exists()
    assert not AccountClassification.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account__in=(contactaccountmanagement_account_b, contactaccountmanagement_account_a),
    ).exists()
    assert not AccountPlan.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        account__in=(contactaccountmanagement_account_b, contactaccountmanagement_account_a),
    ).exists()
    assert not PartyEnrichmentEvent.objects.filter(
        tenant=contactaccountmanagement_tenant_a,
        party__in=(contactaccountmanagement_account_a, contactaccountmanagement_account_b),
    ).exists()
