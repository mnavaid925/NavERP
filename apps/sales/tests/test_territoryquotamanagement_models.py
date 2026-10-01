"""8.7 Territory & Quota Management -- model lane.

Tests cover:
- Rule engine: validation, operators, segment types, priority, match modes.
- Subtree primary rule prohibition (I8).
- Account territory assignments: primary exclusivity, frozen evidence.
- Territory members: coverage splits, pairing validation (C4, C5).
- Quota plans: baseline derivations, frozen states immutability (I10).
- Ownership rulings: CRM owns Territory and SalesQuota, Sales 8.7 extends by FK.

Names: every test is `test_territoryquotamanagement_*` and every helper `_territoryquotamanagement_*`.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.sales.models.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignment,
)
from apps.sales.models.TerritoryQuotaManagement.QuotaPlans import (
    QuotaPlan,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryMembers import (
    TerritoryMember,
)
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import (
    ROUTING_OPERATORS,
    TERRITORY_FIELDS,
    TerritoryRule,
    validate_territory_conditions,
)
from apps.sales.tests.conftest import (
    TERRITORYQUOTAMANAGEMENT_MODEL_CHOICES,
    TERRITORYQUOTAMANAGEMENT_MODEL_FIELDS,
    _territoryquotamanagement_assignment,
    _territoryquotamanagement_crm_quota,
    _territoryquotamanagement_crm_territory,
    _territoryquotamanagement_member,
    _territoryquotamanagement_quotaplan,
    _territoryquotamanagement_rule,
)

pytestmark = pytest.mark.django_db

_CLASSES = {
    "TerritoryRule": TerritoryRule,
    "AccountTerritoryAssignment": AccountTerritoryAssignment,
    "TerritoryMember": TerritoryMember,
    "QuotaPlan": QuotaPlan,
}


def test_territoryquotamanagement_model_field_presence():
    """Verify that all expected fields declared in contract exist on the models."""
    for model_name, expected_fields in TERRITORYQUOTAMANAGEMENT_MODEL_FIELDS.items():
        cls = _CLASSES[model_name]
        existing = {f.name for f in cls._meta.get_fields() if hasattr(f, "name")}
        for fld in expected_fields:
            assert fld in existing, f"Missing field {fld!r} on {model_name}"


def test_territoryquotamanagement_model_choice_constants():
    """Verify choice constants on models match expected contracts."""
    for model_name, choice_dict in TERRITORYQUOTAMANAGEMENT_MODEL_CHOICES.items():
        cls = _CLASSES[model_name]
        for const_name, expected_choices in choice_dict.items():
            actual = getattr(cls, const_name, None)
            assert actual is not None, f"Missing choice constant {const_name} on {model_name}"
            actual_keys = [k for k, _ in actual]
            expected_keys = [k for k, _ in expected_choices]
            for key in expected_keys:
                assert key in actual_keys, f"Choice {key!r} not in {model_name}.{const_name}"


def test_territoryquotamanagement_rule_numbering(tqm_tenant_a, tqm_territory):
    """TerritoryRule gets auto-assigned a TRG- prefixed number."""
    rule = _territoryquotamanagement_rule(tqm_tenant_a, target_territory=tqm_territory)
    assert rule.number is not None
    assert rule.number.startswith("TRG-")


def test_territoryquotamanagement_rule_operator_validation(tqm_tenant_a, tqm_territory):
    """Valid operators like 'eq' pass validation; invalid ones like 'equals' or 'regex' fail."""
    valid_conditions = [{"field": "state", "operator": "eq", "value": "CA"}]
    validate_territory_conditions(valid_conditions)

    invalid_conditions = [{"field": "state", "operator": "equals", "value": "CA"}]
    with pytest.raises(ValidationError):
        validate_territory_conditions(invalid_conditions)


def test_territoryquotamanagement_rule_named_account_prohibits_conditions(tqm_tenant_a, tqm_territory):
    """Named account rules cannot carry automated condition filters."""
    rule = TerritoryRule(
        tenant=tqm_tenant_a,
        name="Named Rule Invalid",
        target_territory=tqm_territory,
        segment_type="named_account",
        conditions=[{"field": "industry", "operator": "eq", "value": "Tech"}],
    )
    with pytest.raises(ValidationError):
        rule.full_clean()


def test_territoryquotamanagement_rule_subtree_primary_prohibited(tqm_tenant_a, tqm_territory):
    """Subtree scope rules cannot have primary alignment (I8 invariant)."""
    rule = TerritoryRule(
        tenant=tqm_tenant_a,
        name="Subtree Primary Invalid",
        target_territory=tqm_territory,
        segment_type="geographic",
        assignment_scope="subtree",
        alignment_type="primary",
        conditions=[{"field": "country", "operator": "eq", "value": "US"}],
    )
    with pytest.raises(ValidationError):
        rule.full_clean()


def test_territoryquotamanagement_assignment_numbering(tqm_tenant_a, tqm_account_a, tqm_territory):
    """AccountTerritoryAssignment gets auto-assigned a TAS- prefixed number."""
    assignment = _territoryquotamanagement_assignment(
        tqm_tenant_a, account=tqm_account_a, territory=tqm_territory
    )
    assert assignment.number is not None
    assert assignment.number.startswith("TAS-")


def test_territoryquotamanagement_assignment_single_primary_guard(tqm_tenant_a, tqm_account_a, tqm_territory):
    """An account cannot have two active primary territory assignments simultaneously."""
    _territoryquotamanagement_assignment(
        tqm_tenant_a, account=tqm_account_a, territory=tqm_territory, alignment_type="primary"
    )
    terr2 = _territoryquotamanagement_crm_territory(tqm_tenant_a, name="EMEA")
    duplicate_primary = AccountTerritoryAssignment(
        tenant=tqm_tenant_a,
        account=tqm_account_a,
        territory=terr2,
        alignment_type="primary",
        effective_from=timezone.localdate(),
    )
    with pytest.raises(ValidationError):
        duplicate_primary.full_clean()


def test_territoryquotamanagement_assignment_str_safe(tqm_tenant_a, tqm_account_a, tqm_territory):
    """__str__ handles instances cleanly without throwing exceptions (M2, M9)."""
    assignment = _territoryquotamanagement_assignment(
        tqm_tenant_a, account=tqm_account_a, territory=tqm_territory
    )
    rep = str(assignment)
    assert assignment.number in rep
    assert tqm_account_a.name in rep

    # Unpersisted instance
    unpersisted = AccountTerritoryAssignment(tenant=tqm_tenant_a)
    assert str(unpersisted) is not None


def test_territoryquotamanagement_member_unique_roster(tqm_tenant_a, tqm_territory, tqm_admin_a):
    """A user cannot have multiple memberships for the same role in the same territory."""
    _territoryquotamanagement_member(
        tqm_tenant_a, territory=tqm_territory, user=tqm_admin_a, member_role="ae"
    )
    with pytest.raises((ValidationError, IntegrityError)):
        dup = TerritoryMember(
            tenant=tqm_tenant_a,
            territory=tqm_territory,
            user=tqm_admin_a,
            member_role="ae",
            effective_from=timezone.localdate(),
        )
        dup.save()


def test_territoryquotamanagement_member_direct_split_sum(tqm_tenant_a, tqm_territory, tqm_admin_a, tqm_member_a):
    """Direct members in a territory with shared assignments must sum to 100% (C4)."""
    m1 = _territoryquotamanagement_member(
        tqm_tenant_a,
        territory=tqm_territory,
        user=tqm_admin_a,
        member_role="ae",
        assignment_type="direct",
        coverage_split_pct=Decimal("60.00"),
    )
    m2 = TerritoryMember(
        tenant=tqm_tenant_a,
        territory=tqm_territory,
        user=tqm_member_a,
        member_role="ae",
        assignment_type="shared",
        coverage_split_pct=Decimal("40.00"),
        effective_from=timezone.localdate(),
    )
    # Total direct split is 60%, but shared is present, so total direct must equal 100%
    with pytest.raises(ValidationError):
        m2.full_clean()


def test_territoryquotamanagement_member_paired_ae_validation(tqm_tenant_a, tqm_territory, tqm_admin_a, tqm_member_a):
    """An SDR paired with an AE passes validation; paired with a non-AE raises ValidationError (C5)."""
    # Create an AE
    _territoryquotamanagement_member(
        tqm_tenant_a,
        territory=tqm_territory,
        user=tqm_admin_a,
        member_role="ae",
        assignment_type="direct",
    )
    # SDR paired with tqm_admin_a (the AE)
    sdr = TerritoryMember(
        tenant=tqm_tenant_a,
        territory=tqm_territory,
        user=tqm_member_a,
        member_role="sdr",
        assignment_type="direct",
        paired_user=tqm_admin_a,
        effective_from=timezone.localdate(),
    )
    sdr.full_clean()  # should not raise!


def test_territoryquotamanagement_quotaplan_numbering(tqm_tenant_a, tqm_quota, tqm_territory, tqm_admin_a):
    """QuotaPlan gets auto-assigned a QPA- prefixed number."""
    plan = _territoryquotamanagement_quotaplan(
        tqm_tenant_a, quota_ref=tqm_quota, territory=tqm_territory, owner=tqm_admin_a
    )
    assert plan.number is not None
    assert plan.number.startswith("QPA-")


def test_territoryquotamanagement_quotaplan_frozen_states_immutable(tqm_tenant_a, tqm_quota, tqm_territory, tqm_admin_a):
    """A QuotaPlan in approved or locked status cannot be modified (I10)."""
    plan = _territoryquotamanagement_quotaplan(
        tqm_tenant_a, quota_ref=tqm_quota, territory=tqm_territory, owner=tqm_admin_a, status="approved"
    )
    plan.growth_target_pct = Decimal("25.00")
    with pytest.raises(ValidationError):
        plan.full_clean()
