"""Projects 7.11 — Time and Attendance Tracking model tests.

Covers the three 7.11 entities:
- TimeActivityCode [TAC-] (activity codes, overhead categories, billing defaults)
- OvertimeRule [OTR-] (overtime thresholds, multipliers, project/tenant scope)
- ProjectOvertimeRecord [POT-] (overtime claims, status lifecycle, pay/billable calculations)

Naming: every test ``test_timeattendance_*``, every helper ``_timeattendance_*``.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.projects.models import (
    OvertimeRule,
    ProjectOvertimeRecord,
    TimeActivityCode,
    ZERO,
    q2,
)
from apps.projects.tests.conftest import (
    _timeattendance_activity_code,
    _timeattendance_overtime_rule,
    _timeattendance_overtime_record,
    _resource_profile,
)

pytestmark = pytest.mark.django_db

_NUMBERED_MODELS = [
    (TimeActivityCode, "TAC"),
    (OvertimeRule, "OTR"),
    (ProjectOvertimeRecord, "POT"),
]


# ==================================================================================================
# Numbering & Tenant Isolation
# ==================================================================================================

@pytest.mark.parametrize("model,prefix", _NUMBERED_MODELS)
def test_timeattendance_number_prefix_is_pinned(model, prefix):
    assert model.NUMBER_PREFIX == prefix


def test_timeattendance_numbers_are_per_tenant_not_global(tenant_a, tenant_b):
    code_a = _timeattendance_activity_code(tenant_a, code="DEV")
    code_b = _timeattendance_activity_code(tenant_b, code="DEV")
    assert code_a.number == code_b.number
    assert code_a.tenant != code_b.tenant


def test_timeattendance_number_mints_sequentially(tenant_a):
    c1 = _timeattendance_activity_code(tenant_a, code="ACT-1")
    c2 = _timeattendance_activity_code(tenant_a, code="ACT-2")
    assert int(c2.number.split("-")[1]) == int(c1.number.split("-")[1]) + 1


# ==================================================================================================
# TimeActivityCode — clean, constraints, string representation
# ==================================================================================================

def test_timeattendance_activity_code_clean_uppercases_and_strips(tenant_a):
    code = TimeActivityCode(
        tenant=tenant_a,
        code="  dev-impl  ",
        name="Development Implementation",
        category="direct_project",
    )
    code.clean()
    assert code.code == "DEV-IMPL"


def test_timeattendance_activity_code_unique_code_per_tenant(tenant_a, tenant_b):
    _timeattendance_activity_code(tenant_a, code="CODE1", name="First")
    # Duplicate code in same tenant raises ValidationError during full_clean
    with pytest.raises(ValidationError):
        _timeattendance_activity_code(tenant_a, code="CODE1", name="Duplicate")

    # Raw save bypasses full_clean and hits DB unique constraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup = TimeActivityCode(tenant=tenant_a, number="TAC-99999", code="CODE1", name="Duplicate Raw")
            dup.save()

    # Same code in different tenant is allowed
    other = _timeattendance_activity_code(tenant_b, code="CODE1", name="Different Tenant")
    assert other.pk is not None


def test_timeattendance_activity_code_str(tenant_a):
    code = _timeattendance_activity_code(tenant_a, code="QA", name="Quality Assurance")
    assert str(code) == "QA — Quality Assurance"


# ==================================================================================================
# OvertimeRule — project vs tenant-wide scope, multipliers, string representation
# ==================================================================================================

def test_timeattendance_overtime_rule_tenant_default_scope_str(tenant_a):
    rule = _timeattendance_overtime_rule(tenant_a, name="Company Policy", project=None)
    assert "Tenant Default" in str(rule)
    assert rule.number in str(rule)


def test_timeattendance_overtime_rule_project_scope_str(tenant_a, resource_project):
    rule = _timeattendance_overtime_rule(tenant_a, name="Project Rush Policy", project=resource_project)
    assert resource_project.name in str(rule)


def test_timeattendance_overtime_rule_validators(tenant_a):
    rule = OvertimeRule(
        tenant=tenant_a,
        name="Invalid Multipliers",
        daily_overtime_multiplier=Decimal("0.50"),
    )
    with pytest.raises(ValidationError):
        rule.full_clean(exclude=["number"])


# ==================================================================================================
# ProjectOvertimeRecord — equivalent hours calculations, billable toggle, string representation
# ==================================================================================================

def test_timeattendance_overtime_record_pay_equivalent_calculation(tenant_a, resource_profile_internal, resource_project):
    rec = _timeattendance_overtime_record(
        tenant_a, resource_profile_internal, resource_project,
        overtime_hours=Decimal("4.00"),
        pay_multiplier=Decimal("1.50"),
    )
    assert rec.pay_equivalent_hours == Decimal("6.00")


def test_timeattendance_overtime_record_billable_equivalent_calculation(tenant_a, resource_profile_internal, resource_project):
    rec_billable = _timeattendance_overtime_record(
        tenant_a, resource_profile_internal, resource_project,
        overtime_hours=Decimal("4.00"),
        billable_multiplier=Decimal("1.25"),
        is_billable=True,
    )
    assert rec_billable.billable_equivalent_hours == Decimal("5.00")

    rec_non_billable = _timeattendance_overtime_record(
        tenant_a, resource_profile_internal, resource_project,
        overtime_hours=Decimal("4.00"),
        billable_multiplier=Decimal("1.25"),
        is_billable=False,
    )
    assert rec_non_billable.billable_equivalent_hours == ZERO


def test_timeattendance_overtime_record_str(tenant_a, resource_profile_internal, resource_project):
    rec = _timeattendance_overtime_record(
        tenant_a, resource_profile_internal, resource_project,
        overtime_hours=Decimal("3.50"),
    )
    assert "3.50h OT on" in str(rec)
    assert rec.number in str(rec)
