"""Projects 7.11 — Time & Attendance Tracking form tests.

Covers form validation, clean methods, and tenant query scoping:
- TimeActivityCodeForm (code uppercase/strip clean, uniqueness, valid submissions)
- OvertimeRuleForm (scoping project FK to request tenant)
- ProjectOvertimeRecordForm (scoping resource, project, task, time_entry querysets to request tenant)

Naming: every test ``test_timeattendance_*``, every helper ``_timeattendance_*``.
"""
from decimal import Decimal
import pytest

from apps.projects.forms import (
    OvertimeRuleForm,
    ProjectOvertimeRecordForm,
    TimeActivityCodeForm,
)
from apps.projects.models import (
    OvertimeRule,
    ProjectOvertimeRecord,
    TimeActivityCode,
)
from apps.projects.tests.conftest import (
    _timeattendance_activity_code,
    _timeattendance_today,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# TimeActivityCodeForm
# ==================================================================================================

def test_timeattendance_activity_code_form_fields(tenant_a):
    form = TimeActivityCodeForm(tenant=tenant_a)
    expected_fields = ["code", "name", "category", "is_billable_default", "is_active", "description"]
    assert list(form.fields.keys()) == expected_fields


def test_timeattendance_activity_code_form_clean_code_uppercase(tenant_a):
    data = {
        "code": "  analysis  ",
        "name": "Requirement Analysis",
        "category": "direct_project",
        "is_billable_default": True,
        "is_active": True,
        "description": "Initial discovery phase",
    }
    form = TimeActivityCodeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.code == "ANALYSIS"


def test_timeattendance_activity_code_form_rejects_duplicate_code_in_same_tenant(tenant_a):
    _timeattendance_activity_code(tenant_a, code="DUP-CODE", name="Original")
    data = {
        "code": "DUP-CODE",
        "name": "Duplicate Attempt",
        "category": "direct_project",
        "is_billable_default": True,
        "is_active": True,
        "description": "",
    }
    form = TimeActivityCodeForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "code" in form.errors or "__all__" in form.errors


def test_timeattendance_activity_code_form_allows_same_code_different_tenant(tenant_a, tenant_b):
    _timeattendance_activity_code(tenant_a, code="SHARED", name="Tenant A Code")
    data = {
        "code": "SHARED",
        "name": "Tenant B Code",
        "category": "direct_project",
        "is_billable_default": True,
        "is_active": True,
        "description": "",
    }
    form = TimeActivityCodeForm(data=data, tenant=tenant_b)
    assert form.is_valid(), form.errors


# ==================================================================================================
# OvertimeRuleForm
# ==================================================================================================

def test_timeattendance_overtime_rule_form_scopes_projects_to_tenant(tenant_a, tenant_b, resource_project, resource_project_b):
    form = OvertimeRuleForm(tenant=tenant_a)
    project_pks = list(form.fields["project"].queryset.values_list("pk", flat=True))
    assert resource_project.pk in project_pks
    assert resource_project_b.pk not in project_pks


def test_timeattendance_overtime_rule_form_valid_submission(tenant_a, resource_project):
    data = {
        "project": resource_project.pk,
        "name": "Sprint Crunch Policy",
        "standard_daily_hours": "8.00",
        "standard_weekly_hours": "40.00",
        "daily_overtime_multiplier": "1.50",
        "weekly_overtime_multiplier": "1.50",
        "weekend_multiplier": "2.00",
        "holiday_multiplier": "2.50",
        "requires_pre_approval": True,
        "is_active": True,
        "notes": "Approved by PMO",
    }
    form = OvertimeRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk is not None
    assert obj.name == "Sprint Crunch Policy"
    assert obj.holiday_multiplier == Decimal("2.50")


# ==================================================================================================
# ProjectOvertimeRecordForm
# ==================================================================================================

def test_timeattendance_overtime_record_form_scopes_foreign_keys_to_tenant(
    tenant_a, tenant_b, resource_profile_internal, resource_project, resource_project_b
):
    form = ProjectOvertimeRecordForm(tenant=tenant_a)
    res_pks = list(form.fields["resource"].queryset.values_list("pk", flat=True))
    prj_pks = list(form.fields["project"].queryset.values_list("pk", flat=True))
    assert resource_profile_internal.pk in res_pks
    assert resource_project.pk in prj_pks
    assert resource_project_b.pk not in prj_pks


def test_timeattendance_overtime_record_form_valid_submission(
    tenant_a, resource_profile_internal, resource_project
):
    data = {
        "resource": resource_profile_internal.pk,
        "project": resource_project.pk,
        "date": _timeattendance_today(),
        "overtime_hours": "3.50",
        "overtime_type": "daily",
        "pay_multiplier": "1.50",
        "billable_multiplier": "1.25",
        "is_billable": True,
        "notes": "Late night deployment",
    }
    form = ProjectOvertimeRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk is not None
    assert obj.overtime_hours == Decimal("3.50")
    assert obj.status == "draft"
