"""Unit tests for Sub-module 10.5 Data Quality & Cleansing forms.

Forms covered:
- DataQualityProfileForm
- DataQualityRuleForm
- DataQualityExceptionForm
- DataQualityExceptionRemediationForm
- DataQualityScorecardForm
"""
import json
from decimal import Decimal

import pytest
from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms import (
    DataQualityExceptionForm,
    DataQualityExceptionRemediationForm,
    DataQualityProfileForm,
    DataQualityRuleForm,
    DataQualityScorecardForm,
)
from apps.bi.models import (
    DataMart,
    DataQualityException,
    DataQualityProfile,
    DataQualityRule,
    DataQualityScorecard,
    SemanticModel,
    WarehouseTable,
)
from apps.core.models.OrgUnit import OrgUnit


User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (prefixed with _dataquality_*)
# ---------------------------------------------------------------------------


def _dataquality_create_user(tenant, username, is_active=True):
    """Helper to create a user with specified active status in a tenant."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_active=is_active,
    )


def _dataquality_create_org_unit(tenant, name="BI Operations"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _dataquality_base_profile_data(table=None, model=None, **overrides):
    """Helper generating valid DataQualityProfile form payload."""
    data = {
        "name": "Fact Sales Profiling",
        "target_type": "warehouse_table",
        "notes": "Automated dataset scan",
        "is_active": True,
    }
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    data.update(overrides)
    return data


def _dataquality_base_rule_data(table=None, model=None, steward=None, **overrides):
    """Helper generating valid DataQualityRule form payload."""
    data = {
        "name": "Non-Negative Revenue Check",
        "code": "non_neg_rev_check",
        "rule_category": "validation",
        "dimension": "validity",
        "target_type": "warehouse_table",
        "target_column": "revenue_amount",
        "rule_type": "range_between",
        "parameters_json": json.dumps({"min_value": 0}),
        "severity": "critical",
        "failure_tolerance_pct": "0.00",
        "description": "Revenue cannot be negative.",
        "is_active": True,
    }
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    if steward:
        data["steward"] = steward.pk
    data.update(overrides)
    return data


def _dataquality_base_exception_data(rule=None, profile=None, table=None, model=None, steward=None, **overrides):
    """Helper generating valid DataQualityException form payload."""
    data = {
        "record_identifier": "INV-2026-0042",
        "target_column": "revenue_amount",
        "invalid_value": "-120.50",
        "expected_condition": "revenue_amount >= 0",
        "exception_type": "range_outlier",
        "severity": "critical",
        "status": "open",
        "remediation_action": "manual_edit",
        "proposed_value": "120.50",
        "remediated_value": "",
        "resolution_notes": "Pending customer invoice audit.",
        "is_active": True,
    }
    if rule:
        data["rule"] = rule.pk
    if profile:
        data["profile"] = profile.pk
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    if steward:
        data["assigned_steward"] = steward.pk
    data.update(overrides)
    return data


def _dataquality_base_remediation_data(steward=None, **overrides):
    """Helper generating valid DataQualityExceptionRemediation form payload."""
    data = {
        "status": "remediated",
        "remediation_action": "manual_edit",
        "proposed_value": "120.50",
        "remediated_value": "120.50",
        "resolution_notes": "Corrected sign error from credit memo ingestion.",
    }
    if steward:
        data["assigned_steward"] = steward.pk
    data.update(overrides)
    return data


def _dataquality_base_scorecard_data(table=None, model=None, mart=None, org_unit=None, steward=None, **overrides):
    """Helper generating valid DataQualityScorecard form payload."""
    data = {
        "name": "Finance Analytics Quality Scorecard",
        "code": "fin_analytics_scorecard",
        "scope_type": "warehouse_table",
        "target_quality_score": "95.00",
        "evaluation_period": "monthly",
        "description": "Executive scorecard for financial accuracy SLAs.",
        "is_active": True,
    }
    if table:
        data["warehouse_table"] = table.pk
    if model:
        data["semantic_model"] = model.pk
    if mart:
        data["data_mart"] = mart.pk
    if org_unit:
        data["org_unit"] = org_unit.pk
    if steward:
        data["steward"] = steward.pk
    data.update(overrides)
    return data


# ===========================================================================
# 1. DataQualityProfileForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_profile_form_system_field_exclusions(tenant_a):
    """Verify DataQualityProfileForm excludes system and profiling metrics fields."""
    form = DataQualityProfileForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "status",
        "total_row_count",
        "total_column_count",
        "completeness_score",
        "uniqueness_score",
        "validity_score",
        "column_profiles_json",
        "profiled_by",
        "profiled_at",
        "duration_seconds",
        "error_message",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from DataQualityProfileForm"


@pytest.mark.django_db
def test_dataquality_profile_form_valid_warehouse_table(tenant_a, warehouse_table_a):
    """Verify valid profile creation targeting a warehouse table."""
    data = _dataquality_base_profile_data(
        table=warehouse_table_a,
        name="Warehouse Table Scan Profile",
        notes="Deep completeness audit",
    )
    form = DataQualityProfileForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BDQP-")
    assert instance.target_type == "warehouse_table"
    assert instance.warehouse_table == warehouse_table_a
    assert instance.semantic_model is None
    assert instance.name == "Warehouse Table Scan Profile"
    assert instance.notes == "Deep completeness audit"


@pytest.mark.django_db
def test_dataquality_profile_form_valid_semantic_model(tenant_a, semantic_model_a):
    """Verify valid profile creation targeting a semantic model."""
    data = _dataquality_base_profile_data(
        target_type="semantic_model",
        model=semantic_model_a,
        name="Semantic Model Profiling Scan",
    )
    form = DataQualityProfileForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.target_type == "semantic_model"
    assert instance.semantic_model == semantic_model_a


@pytest.mark.django_db
def test_dataquality_profile_form_target_type_warehouse_table_missing_table(tenant_a):
    """Verify error raised when target_type is warehouse_table but no table is selected."""
    data = _dataquality_base_profile_data(target_type="warehouse_table")
    form = DataQualityProfileForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors
    assert "A warehouse table must be selected when target type is Warehouse Table." in form.errors["warehouse_table"]


@pytest.mark.django_db
def test_dataquality_profile_form_target_type_semantic_model_missing_model(tenant_a):
    """Verify error raised when target_type is semantic_model but no model is selected."""
    data = _dataquality_base_profile_data(target_type="semantic_model")
    form = DataQualityProfileForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert "A semantic model must be selected when target type is Semantic Model." in form.errors["semantic_model"]


@pytest.mark.django_db
def test_dataquality_profile_form_scoped_querysets(
    tenant_a,
    tenant_b,
    warehouse_table_a,
    warehouse_table_b,
    semantic_model_a,
    semantic_model_b,
):
    """Verify warehouse_table and semantic_model querysets are scoped to self.tenant."""
    form = DataQualityProfileForm(tenant=tenant_a)
    assert warehouse_table_a in form.fields["warehouse_table"].queryset
    assert warehouse_table_b not in form.fields["warehouse_table"].queryset

    assert semantic_model_a in form.fields["semantic_model"].queryset
    assert semantic_model_b not in form.fields["semantic_model"].queryset


@pytest.mark.django_db
def test_dataquality_profile_form_unbound_tenant_none():
    """Verify DataQualityProfileForm handles initialization when tenant is None."""
    form = DataQualityProfileForm(tenant=None)
    assert form.fields["warehouse_table"].queryset.count() >= 0
    assert form.fields["semantic_model"].queryset.count() >= 0


@pytest.mark.django_db
def test_dataquality_profile_form_rejects_foreign_warehouse_table(tenant_a, warehouse_table_b):
    """Verify reject_foreign stops foreign tenant warehouse table."""
    data = _dataquality_base_profile_data(table=warehouse_table_b)
    # Scoped queryset rejection
    form = DataQualityProfileForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityProfileForm(data=data, tenant=tenant_a)
    form_wide.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["warehouse_table"]


@pytest.mark.django_db
def test_dataquality_profile_form_rejects_foreign_semantic_model(tenant_a, semantic_model_b):
    """Verify reject_foreign stops foreign tenant semantic model."""
    data = _dataquality_base_profile_data(
        target_type="semantic_model",
        model=semantic_model_b,
    )
    # Scoped queryset rejection
    form = DataQualityProfileForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityProfileForm(data=data, tenant=tenant_a)
    form_wide.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["semantic_model"]


@pytest.mark.django_db
def test_dataquality_profile_form_edit_existing_instance(tenant_a, dq_profile_a):
    """Verify editing existing profile updates instance fields."""
    data = {
        "name": "Updated Profile Name",
        "target_type": "warehouse_table",
        "warehouse_table": dq_profile_a.warehouse_table.pk,
        "notes": "Revised notes description",
        "is_active": False,
    }
    form = DataQualityProfileForm(data=data, instance=dq_profile_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == dq_profile_a.pk
    assert updated.name == "Updated Profile Name"
    assert updated.notes == "Revised notes description"
    assert updated.is_active is False


# ===========================================================================
# 2. DataQualityRuleForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_rule_form_system_field_exclusions(tenant_a):
    """Verify DataQualityRuleForm excludes system metrics and execution counters."""
    form = DataQualityRuleForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "last_run_at",
        "last_status",
        "passed_records_count",
        "failed_records_count",
        "pass_rate_pct",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from DataQualityRuleForm"


@pytest.mark.django_db
def test_dataquality_rule_form_valid_creation_warehouse_table(tenant_a, warehouse_table_a, admin_user):
    """Verify valid creation of a rule on a warehouse table."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        code="invoice_total_positive",
        name="Invoice Total Positive",
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BDQR-")
    assert instance.code == "invoice_total_positive"
    assert instance.target_type == "warehouse_table"
    assert instance.warehouse_table == warehouse_table_a
    assert instance.steward == admin_user
    assert instance.parameters_json == {"min_value": 0}


@pytest.mark.django_db
def test_dataquality_rule_form_valid_creation_semantic_model(tenant_a, semantic_model_a, admin_user):
    """Verify valid creation of a rule on a semantic model."""
    data = _dataquality_base_rule_data(
        target_type="semantic_model",
        model=semantic_model_a,
        steward=admin_user,
        code="customer_tier_valid",
        name="Customer Tier Validity",
        rule_type="set_membership",
        parameters_json=json.dumps({"allowed_values": ["bronze", "silver", "gold"]}),
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.target_type == "semantic_model"
    assert instance.semantic_model == semantic_model_a
    assert instance.parameters_json == {"allowed_values": ["bronze", "silver", "gold"]}


@pytest.mark.django_db
def test_dataquality_rule_form_parameters_json_valid_dict_string(tenant_a, warehouse_table_a, admin_user):
    """Verify parameters_json parses valid JSON string dictionary into dict."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        parameters_json='{"min_val": 10, "max_val": 100, "inclusive": true}',
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameters_json"] == {"min_val": 10, "max_val": 100, "inclusive": True}


@pytest.mark.django_db
def test_dataquality_rule_form_parameters_json_valid_dict_object(tenant_a, warehouse_table_a, admin_user):
    """Verify parameters_json passes through directly when already a python dict."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        parameters_json={"regex": "^[0-9]{5}(-[0-9]{4})?$"},
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameters_json"] == {"regex": "^[0-9]{5}(-[0-9]{4})?$"}


@pytest.mark.django_db
def test_dataquality_rule_form_parameters_json_empty_and_whitespace(tenant_a, warehouse_table_a, admin_user):
    """Verify empty string in parameters_json normalizes to empty dict."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        parameters_json="",
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameters_json"] == {}

    # Verify whitespace normalization directly in clean_parameters_json method
    mock_form = DataQualityRuleForm(tenant=tenant_a)
    mock_form.cleaned_data = {"parameters_json": "   "}
    assert mock_form.clean_parameters_json() == {}


@pytest.mark.django_db
def test_dataquality_rule_form_parameters_json_invalid_json_string(tenant_a, warehouse_table_a, admin_user):
    """Verify malformed JSON syntax raises ValidationError on parameters_json."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        parameters_json="{malformed json: true,",
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "parameters_json" in form.errors

    # Verify clean_parameters_json explicitly handles JSONDecodeError when receiving raw string
    mock_form = DataQualityRuleForm(tenant=tenant_a)
    mock_form.cleaned_data = {"parameters_json": "{invalid json"}
    with pytest.raises(forms.ValidationError) as exc:
        mock_form.clean_parameters_json()
    assert "Invalid JSON configuration" in str(exc.value)


@pytest.mark.django_db
def test_dataquality_rule_form_parameters_json_non_dict_json_array(tenant_a, warehouse_table_a, admin_user):
    """Verify valid JSON array string raises ValidationError stating dictionary required."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        parameters_json='["not", "a", "dict"]',
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "parameters_json" in form.errors
    assert any("Parameters must be a JSON object (dictionary)" in str(e) for e in form.errors["parameters_json"])


@pytest.mark.django_db
def test_dataquality_rule_form_parameters_json_non_dict_json_primitive(tenant_a, warehouse_table_a, admin_user):
    """Verify JSON primitive (scalar number or raw non-dict string) raises ValidationError."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        parameters_json="12345",
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "parameters_json" in form.errors
    assert any("Parameters must be a JSON object (dictionary)" in str(e) for e in form.errors["parameters_json"])

    # Test raw non-dict string in clean_parameters_json directly
    mock_form = DataQualityRuleForm(tenant=tenant_a)
    mock_form.cleaned_data = {"parameters_json": "scalar string"}
    with pytest.raises(forms.ValidationError):
        mock_form.clean_parameters_json()


@pytest.mark.django_db
def test_dataquality_rule_form_parameters_json_non_dict_primitive_val(tenant_a, warehouse_table_a, admin_user):
    """Verify passing a raw list object raises ValidationError."""
    mock_form = DataQualityRuleForm(tenant=tenant_a)
    mock_form.cleaned_data = {"parameters_json": [1, 2, 3]}
    with pytest.raises(forms.ValidationError) as exc:
        mock_form.clean_parameters_json()
    assert "Parameters must be a JSON object (dictionary)" in str(exc.value)


@pytest.mark.django_db
def test_dataquality_rule_form_target_type_warehouse_table_missing(tenant_a, admin_user):
    """Verify error raised when target_type is warehouse_table but no table is supplied."""
    data = _dataquality_base_rule_data(
        target_type="warehouse_table",
        steward=admin_user,
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors
    assert "A warehouse table must be selected when target type is Warehouse Table." in form.errors["warehouse_table"]


@pytest.mark.django_db
def test_dataquality_rule_form_target_type_semantic_model_missing(tenant_a, admin_user):
    """Verify error raised when target_type is semantic_model but no model is supplied."""
    data = _dataquality_base_rule_data(
        target_type="semantic_model",
        steward=admin_user,
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert "A semantic model must be selected when target type is Semantic Model." in form.errors["semantic_model"]


@pytest.mark.django_db
def test_dataquality_rule_form_scoped_querysets(
    tenant_a,
    tenant_b,
    warehouse_table_a,
    warehouse_table_b,
    semantic_model_a,
    semantic_model_b,
    admin_user,
    admin_user_b,
):
    """Verify querysets for warehouse_table, semantic_model, and steward are strictly tenant-scoped."""
    inactive_user_a = _dataquality_create_user(tenant_a, "inactive_steward_a", is_active=False)
    form = DataQualityRuleForm(tenant=tenant_a)

    wt_qs = form.fields["warehouse_table"].queryset
    assert warehouse_table_a in wt_qs
    assert warehouse_table_b not in wt_qs

    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs

    steward_qs = form.fields["steward"].queryset
    assert admin_user in steward_qs
    assert inactive_user_a not in steward_qs
    assert admin_user_b not in steward_qs


@pytest.mark.django_db
def test_dataquality_rule_form_scoped_querysets_retains_bound_inactive_steward(tenant_a, warehouse_table_a):
    """Verify existing inactive steward is retained in steward queryset during edit."""
    inactive_steward = _dataquality_create_user(tenant_a, "retired_data_steward", is_active=False)
    rule = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Legacy Postal Code Format",
        code="legacy_postal_code",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=inactive_steward,
    )
    form = DataQualityRuleForm(instance=rule, tenant=tenant_a)
    assert inactive_steward in form.fields["steward"].queryset


@pytest.mark.django_db
def test_dataquality_rule_form_code_uniqueness_within_tenant(tenant_a, warehouse_table_a, admin_user):
    """Verify TenantUniqueMixin blocks duplicate rule code within the same tenant."""
    rule_existing = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Existing Rule",
        code="existing_rule_code",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        code=rule_existing.code,
        name="Duplicate Rule Attempt",
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.non_field_errors()) or "code" in form.errors


@pytest.mark.django_db
def test_dataquality_rule_form_code_uniqueness_across_tenants(
    tenant_a,
    tenant_b,
    warehouse_table_a,
    warehouse_table_b,
    admin_user,
    admin_user_b,
):
    """Verify same rule code is permitted in a different tenant."""
    DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Tenant A Base Rule",
        code="shared_rule_code",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    data = _dataquality_base_rule_data(
        table=warehouse_table_b,
        steward=admin_user_b,
        code="shared_rule_code",
        name="Globex Same Code Rule",
    )
    form = DataQualityRuleForm(data=data, tenant=tenant_b)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_b
    assert instance.code == "shared_rule_code"


@pytest.mark.django_db
def test_dataquality_rule_form_edit_existing_instance_retains_code(
    tenant_a,
    warehouse_table_a,
    admin_user,
):
    """Verify editing existing rule while retaining same code succeeds."""
    rule = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Initial Rule Name",
        code="retained_rule_code",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user,
        code="retained_rule_code",
        name="Updated Rule Description Only",
        description="Updated rule narrative context.",
    )
    form = DataQualityRuleForm(data=data, instance=rule, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == rule.pk
    assert updated.name == "Updated Rule Description Only"
    assert updated.code == "retained_rule_code"


@pytest.mark.django_db
def test_dataquality_rule_form_rejects_foreign_warehouse_table(tenant_a, warehouse_table_b, admin_user):
    """Verify reject_foreign prevents foreign warehouse table in rule creation."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_b,
        steward=admin_user,
    )
    # Scoped queryset rejection
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["warehouse_table"]


@pytest.mark.django_db
def test_dataquality_rule_form_rejects_foreign_semantic_model(tenant_a, semantic_model_b, admin_user):
    """Verify reject_foreign prevents foreign semantic model in rule creation."""
    data = _dataquality_base_rule_data(
        target_type="semantic_model",
        model=semantic_model_b,
        steward=admin_user,
    )
    # Scoped queryset rejection
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["semantic_model"]


@pytest.mark.django_db
def test_dataquality_rule_form_rejects_foreign_steward(tenant_a, warehouse_table_a, admin_user_b):
    """Verify reject_foreign prevents assigning a steward from another tenant."""
    data = _dataquality_base_rule_data(
        table=warehouse_table_a,
        steward=admin_user_b,
    )
    # Scoped queryset rejection
    form = DataQualityRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "steward" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["steward"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["steward"]


# ===========================================================================
# 3. DataQualityExceptionForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_exception_form_system_field_exclusions(tenant_a):
    """Verify DataQualityExceptionForm excludes system lifecycle and resolver fields."""
    form = DataQualityExceptionForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "resolved_by",
        "resolved_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from DataQualityExceptionForm"


@pytest.mark.django_db
def test_dataquality_exception_form_valid_creation(
    tenant_a,
    dq_rule_a,
    dq_profile_a,
    warehouse_table_a,
    admin_user,
):
    """Verify valid creation of a data quality exception."""
    data = _dataquality_base_exception_data(
        rule=dq_rule_a,
        profile=dq_profile_a,
        table=warehouse_table_a,
        steward=admin_user,
        record_identifier="ORD-2026-8801",
        invalid_value="-99.99",
    )
    form = DataQualityExceptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BDQE-")
    assert instance.rule == dq_rule_a
    assert instance.profile == dq_profile_a
    assert instance.warehouse_table == warehouse_table_a
    assert instance.assigned_steward == admin_user
    assert instance.record_identifier == "ORD-2026-8801"
    assert instance.invalid_value == "-99.99"


@pytest.mark.django_db
def test_dataquality_exception_form_valid_edit(tenant_a, dq_exception_a, admin_user):
    """Verify editing an existing exception updates status and remediation fields."""
    data = {
        "rule": dq_exception_a.rule.pk,
        "profile": dq_exception_a.profile.pk,
        "warehouse_table": dq_exception_a.warehouse_table.pk,
        "record_identifier": dq_exception_a.record_identifier,
        "target_column": dq_exception_a.target_column,
        "invalid_value": dq_exception_a.invalid_value,
        "expected_condition": dq_exception_a.expected_condition,
        "exception_type": dq_exception_a.exception_type,
        "severity": dq_exception_a.severity,
        "status": "investigating",
        "remediation_action": "manual_edit",
        "proposed_value": "45.00",
        "remediated_value": "",
        "assigned_steward": admin_user.pk,
        "resolution_notes": "Steward confirmed amount was inverted in source batch.",
        "is_active": True,
    }
    form = DataQualityExceptionForm(data=data, instance=dq_exception_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == dq_exception_a.pk
    assert updated.status == "investigating"
    assert updated.proposed_value == "45.00"
    assert updated.resolution_notes == "Steward confirmed amount was inverted in source batch."


@pytest.mark.django_db
def test_dataquality_exception_form_scoped_querysets(
    tenant_a,
    tenant_b,
    dq_rule_a,
    dq_rule_b,
    dq_profile_a,
    dq_profile_b,
    warehouse_table_a,
    warehouse_table_b,
    semantic_model_a,
    semantic_model_b,
    admin_user,
    admin_user_b,
):
    """Verify all foreign key querysets are strictly tenant-scoped."""
    inactive_user = _dataquality_create_user(tenant_a, "inactive_dq_user", is_active=False)
    form = DataQualityExceptionForm(tenant=tenant_a)

    assert dq_rule_a in form.fields["rule"].queryset
    assert dq_rule_b not in form.fields["rule"].queryset

    assert dq_profile_a in form.fields["profile"].queryset
    assert dq_profile_b not in form.fields["profile"].queryset

    assert warehouse_table_a in form.fields["warehouse_table"].queryset
    assert warehouse_table_b not in form.fields["warehouse_table"].queryset

    assert semantic_model_a in form.fields["semantic_model"].queryset
    assert semantic_model_b not in form.fields["semantic_model"].queryset

    assert admin_user in form.fields["assigned_steward"].queryset
    assert inactive_user not in form.fields["assigned_steward"].queryset
    assert admin_user_b not in form.fields["assigned_steward"].queryset


@pytest.mark.django_db
def test_dataquality_exception_form_scoped_querysets_retains_bound_inactive_steward(
    tenant_a,
    warehouse_table_a,
):
    """Verify existing inactive assigned steward is retained in assigned_steward queryset."""
    inactive_user = _dataquality_create_user(tenant_a, "former_dq_assignee", is_active=False)
    exception = DataQualityException.objects.create(
        tenant=tenant_a,
        warehouse_table=warehouse_table_a,
        record_identifier="REC-TEMP-99",
        assigned_steward=inactive_user,
    )
    form = DataQualityExceptionForm(instance=exception, tenant=tenant_a)
    assert inactive_user in form.fields["assigned_steward"].queryset


@pytest.mark.django_db
def test_dataquality_exception_form_rejects_foreign_rule(tenant_a, dq_rule_b, warehouse_table_a):
    """Verify reject_foreign prevents foreign tenant rule."""
    data = _dataquality_base_exception_data(
        rule=dq_rule_b,
        table=warehouse_table_a,
    )
    # Scoped queryset rejection
    form = DataQualityExceptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "rule" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityExceptionForm(data=data, tenant=tenant_a)
    form_wide.fields["rule"].queryset = DataQualityRule.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["rule"]


@pytest.mark.django_db
def test_dataquality_exception_form_rejects_foreign_profile(tenant_a, dq_profile_b, warehouse_table_a):
    """Verify reject_foreign prevents foreign tenant profile."""
    data = _dataquality_base_exception_data(
        profile=dq_profile_b,
        table=warehouse_table_a,
    )
    # Scoped queryset rejection
    form = DataQualityExceptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "profile" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityExceptionForm(data=data, tenant=tenant_a)
    form_wide.fields["profile"].queryset = DataQualityProfile.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["profile"]


@pytest.mark.django_db
def test_dataquality_exception_form_rejects_foreign_warehouse_table(tenant_a, warehouse_table_b):
    """Verify reject_foreign prevents foreign tenant warehouse table."""
    data = _dataquality_base_exception_data(table=warehouse_table_b)
    # Scoped queryset rejection
    form = DataQualityExceptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityExceptionForm(data=data, tenant=tenant_a)
    form_wide.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["warehouse_table"]


@pytest.mark.django_db
def test_dataquality_exception_form_rejects_foreign_semantic_model(tenant_a, semantic_model_b):
    """Verify reject_foreign prevents foreign tenant semantic model."""
    data = _dataquality_base_exception_data(model=semantic_model_b)
    # Scoped queryset rejection
    form = DataQualityExceptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityExceptionForm(data=data, tenant=tenant_a)
    form_wide.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["semantic_model"]


@pytest.mark.django_db
def test_dataquality_exception_form_rejects_foreign_steward(tenant_a, warehouse_table_a, admin_user_b):
    """Verify reject_foreign prevents foreign tenant assigned steward."""
    data = _dataquality_base_exception_data(
        table=warehouse_table_a,
        steward=admin_user_b,
    )
    # Scoped queryset rejection
    form = DataQualityExceptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "assigned_steward" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityExceptionForm(data=data, tenant=tenant_a)
    form_wide.fields["assigned_steward"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["assigned_steward"]


# ===========================================================================
# 4. DataQualityExceptionRemediationForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_remediation_form_system_field_exclusions(tenant_a, dq_exception_a):
    """Verify DataQualityExceptionRemediationForm restricts fields to remediation actions."""
    form = DataQualityExceptionRemediationForm(instance=dq_exception_a, tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "record_identifier",
        "target_column",
        "invalid_value",
        "expected_condition",
        "exception_type",
        "severity",
        "rule",
        "profile",
        "warehouse_table",
        "semantic_model",
        "resolved_by",
        "resolved_at",
        "is_active",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from Remediation form"


@pytest.mark.django_db
def test_dataquality_remediation_form_valid_save(tenant_a, dq_exception_a, admin_user):
    """Verify saving valid remediation payload updates target exception."""
    data = _dataquality_base_remediation_data(
        steward=admin_user,
        status="remediated",
        remediation_action="manual_edit",
        proposed_value="55.00",
        remediated_value="55.00",
        resolution_notes="Corrected total amount manually in ledger view.",
    )
    form = DataQualityExceptionRemediationForm(data=data, instance=dq_exception_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == dq_exception_a.pk
    assert updated.status == "remediated"
    assert updated.remediation_action == "manual_edit"
    assert updated.remediated_value == "55.00"
    assert updated.assigned_steward == admin_user
    assert updated.resolution_notes == "Corrected total amount manually in ledger view."


@pytest.mark.django_db
def test_dataquality_remediation_form_scoped_steward_queryset(
    tenant_a,
    tenant_b,
    dq_exception_a,
    admin_user,
    admin_user_b,
):
    """Verify assigned_steward dropdown is scoped to active users of tenant."""
    inactive_user = _dataquality_create_user(tenant_a, "inactive_assignee", is_active=False)
    form = DataQualityExceptionRemediationForm(instance=dq_exception_a, tenant=tenant_a)

    steward_qs = form.fields["assigned_steward"].queryset
    assert admin_user in steward_qs
    assert inactive_user not in steward_qs
    assert admin_user_b not in steward_qs


@pytest.mark.django_db
def test_dataquality_remediation_form_scoped_steward_retains_bound_inactive(
    tenant_a,
    dq_rule_a,
    warehouse_table_a,
):
    """Verify bound inactive assigned steward remains selectable during remediation edit."""
    inactive_user = _dataquality_create_user(tenant_a, "retired_handler", is_active=False)
    exception = DataQualityException.objects.create(
        tenant=tenant_a,
        warehouse_table=warehouse_table_a,
        rule=dq_rule_a,
        record_identifier="REC-REM-01",
        assigned_steward=inactive_user,
    )
    form = DataQualityExceptionRemediationForm(instance=exception, tenant=tenant_a)
    assert inactive_user in form.fields["assigned_steward"].queryset


@pytest.mark.django_db
def test_dataquality_remediation_form_rejects_foreign_steward(tenant_a, dq_exception_a, admin_user_b):
    """Verify reject_foreign blocks foreign tenant steward in remediation form."""
    data = _dataquality_base_remediation_data(steward=admin_user_b)
    # Scoped queryset rejection
    form = DataQualityExceptionRemediationForm(data=data, instance=dq_exception_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "assigned_steward" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityExceptionRemediationForm(data=data, instance=dq_exception_a, tenant=tenant_a)
    form_wide.fields["assigned_steward"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["assigned_steward"]


# ===========================================================================
# 5. DataQualityScorecardForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_scorecard_form_system_field_exclusions(tenant_a):
    """Verify DataQualityScorecardForm excludes aggregated trust index and roll-up counters."""
    form = DataQualityScorecardForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "overall_quality_score",
        "grade",
        "health_status",
        "meets_sla",
        "last_calculated_at",
        "completeness_score",
        "accuracy_score",
        "consistency_score",
        "timeliness_score",
        "uniqueness_score",
        "validity_score",
        "total_rules_evaluated",
        "rules_passed_count",
        "rules_failed_count",
        "open_exceptions_count",
        "critical_exceptions_count",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from DataQualityScorecardForm"


@pytest.mark.django_db
def test_dataquality_scorecard_form_valid_creation_warehouse_table(tenant_a, warehouse_table_a, admin_user):
    """Verify valid creation of a scorecard scoping a warehouse table."""
    data = _dataquality_base_scorecard_data(
        table=warehouse_table_a,
        steward=admin_user,
        name="Orders Warehouse Table SLA",
        code="orders_wh_table_sla",
        target_quality_score="98.00",
        evaluation_period="daily",
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BDQS-")
    assert instance.code == "orders_wh_table_sla"
    assert instance.scope_type == "warehouse_table"
    assert instance.warehouse_table == warehouse_table_a
    assert instance.target_quality_score == Decimal("98.00")
    assert instance.evaluation_period == "daily"
    assert instance.steward == admin_user


@pytest.mark.django_db
def test_dataquality_scorecard_form_valid_creation_semantic_model(tenant_a, semantic_model_a, admin_user):
    """Verify valid creation of a scorecard scoping a semantic model."""
    data = _dataquality_base_scorecard_data(
        scope_type="semantic_model",
        model=semantic_model_a,
        steward=admin_user,
        name="Customer 360 Semantic Model DTI",
        code="c360_semantic_dti",
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.scope_type == "semantic_model"
    assert instance.semantic_model == semantic_model_a


@pytest.mark.django_db
def test_dataquality_scorecard_form_valid_creation_data_mart(tenant_a, data_mart_a, admin_user):
    """Verify valid creation of a scorecard scoping a data mart domain."""
    data = _dataquality_base_scorecard_data(
        scope_type="data_mart",
        mart=data_mart_a,
        steward=admin_user,
        name="Commercial Data Mart DTI",
        code="comm_data_mart_dti",
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.scope_type == "data_mart"
    assert instance.data_mart == data_mart_a


@pytest.mark.django_db
def test_dataquality_scorecard_form_valid_creation_tenant_wide(tenant_a, admin_user):
    """Verify valid creation of a tenant-wide aggregate scorecard with no target entity."""
    data = _dataquality_base_scorecard_data(
        scope_type="tenant_wide",
        steward=admin_user,
        name="Enterprise-Wide Master Scorecard",
        code="enterprise_master_scorecard",
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.scope_type == "tenant_wide"
    assert instance.warehouse_table is None
    assert instance.semantic_model is None
    assert instance.data_mart is None


@pytest.mark.django_db
def test_dataquality_scorecard_form_scope_warehouse_table_missing(tenant_a, admin_user):
    """Verify validation error when scope_type is warehouse_table but no table is selected."""
    data = _dataquality_base_scorecard_data(
        scope_type="warehouse_table",
        steward=admin_user,
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors
    assert "A warehouse table is required when scope is Warehouse Table." in form.errors["warehouse_table"]


@pytest.mark.django_db
def test_dataquality_scorecard_form_scope_semantic_model_missing(tenant_a, admin_user):
    """Verify validation error when scope_type is semantic_model but no model is selected."""
    data = _dataquality_base_scorecard_data(
        scope_type="semantic_model",
        steward=admin_user,
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert "A semantic model is required when scope is Semantic Model." in form.errors["semantic_model"]


@pytest.mark.django_db
def test_dataquality_scorecard_form_scope_data_mart_missing(tenant_a, admin_user):
    """Verify validation error when scope_type is data_mart but no data mart is selected."""
    data = _dataquality_base_scorecard_data(
        scope_type="data_mart",
        steward=admin_user,
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "data_mart" in form.errors
    assert "A data mart is required when scope is Data Mart Domain." in form.errors["data_mart"]


@pytest.mark.django_db
def test_dataquality_scorecard_form_scoped_querysets(
    tenant_a,
    tenant_b,
    warehouse_table_a,
    warehouse_table_b,
    semantic_model_a,
    semantic_model_b,
    data_mart_a,
    data_mart_b,
    admin_user,
    admin_user_b,
):
    """Verify querysets for warehouse_table, semantic_model, data_mart, org_unit, and steward are tenant-scoped."""
    org_unit_a = _dataquality_create_org_unit(tenant_a, "Finance BI Dept")
    org_unit_b = _dataquality_create_org_unit(tenant_b, "Globex Foreign Dept")
    inactive_user = _dataquality_create_user(tenant_a, "inactive_scorecard_steward", is_active=False)

    form = DataQualityScorecardForm(tenant=tenant_a)

    assert warehouse_table_a in form.fields["warehouse_table"].queryset
    assert warehouse_table_b not in form.fields["warehouse_table"].queryset

    assert semantic_model_a in form.fields["semantic_model"].queryset
    assert semantic_model_b not in form.fields["semantic_model"].queryset

    assert data_mart_a in form.fields["data_mart"].queryset
    assert data_mart_b not in form.fields["data_mart"].queryset

    assert org_unit_a in form.fields["org_unit"].queryset
    assert org_unit_b not in form.fields["org_unit"].queryset

    assert admin_user in form.fields["steward"].queryset
    assert inactive_user not in form.fields["steward"].queryset
    assert admin_user_b not in form.fields["steward"].queryset


@pytest.mark.django_db
def test_dataquality_scorecard_form_scoped_querysets_retains_bound_inactive_steward(
    tenant_a,
    warehouse_table_a,
):
    """Verify existing inactive steward is retained in steward dropdown during edit."""
    inactive_user = _dataquality_create_user(tenant_a, "retired_scorecard_steward", is_active=False)
    scorecard = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Legacy Operations Scorecard",
        code="legacy_ops_scorecard",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=inactive_user,
    )
    form = DataQualityScorecardForm(instance=scorecard, tenant=tenant_a)
    assert inactive_user in form.fields["steward"].queryset


@pytest.mark.django_db
def test_dataquality_scorecard_form_code_uniqueness_within_tenant(
    tenant_a,
    warehouse_table_a,
    admin_user,
):
    """Verify code uniqueness is enforced within the same tenant."""
    scorecard = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Existing Scorecard",
        code="existing_scorecard_code",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    data = _dataquality_base_scorecard_data(
        table=warehouse_table_a,
        steward=admin_user,
        code=scorecard.code,
        name="Duplicate Scorecard Title",
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.non_field_errors()) or "code" in form.errors


@pytest.mark.django_db
def test_dataquality_scorecard_form_code_uniqueness_across_tenants(
    tenant_a,
    tenant_b,
    warehouse_table_a,
    warehouse_table_b,
    admin_user,
    admin_user_b,
):
    """Verify same scorecard code is valid when registered in a different tenant."""
    DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Tenant A Scorecard",
        code="parallel_scorecard_code",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    data = _dataquality_base_scorecard_data(
        table=warehouse_table_b,
        steward=admin_user_b,
        code="parallel_scorecard_code",
        name="Globex Parallel Scorecard",
    )
    form = DataQualityScorecardForm(data=data, tenant=tenant_b)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_b
    assert instance.code == "parallel_scorecard_code"


@pytest.mark.django_db
def test_dataquality_scorecard_form_edit_existing_instance_retains_code(
    tenant_a,
    warehouse_table_a,
    admin_user,
):
    """Verify updating existing scorecard retaining same code is valid."""
    scorecard = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Original Scorecard",
        code="retained_scorecard_code",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    data = _dataquality_base_scorecard_data(
        table=warehouse_table_a,
        steward=admin_user,
        code="retained_scorecard_code",
        name="Updated Scorecard Title",
        description="Refreshed description narrative.",
    )
    form = DataQualityScorecardForm(data=data, instance=scorecard, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == scorecard.pk
    assert updated.name == "Updated Scorecard Title"
    assert updated.code == "retained_scorecard_code"


@pytest.mark.django_db
def test_dataquality_scorecard_form_rejects_foreign_warehouse_table(tenant_a, warehouse_table_b, admin_user):
    """Verify reject_foreign prevents foreign warehouse table."""
    data = _dataquality_base_scorecard_data(
        table=warehouse_table_b,
        steward=admin_user,
    )
    # Scoped queryset rejection
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityScorecardForm(data=data, tenant=tenant_a)
    form_wide.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["warehouse_table"]


@pytest.mark.django_db
def test_dataquality_scorecard_form_rejects_foreign_semantic_model(tenant_a, semantic_model_b, admin_user):
    """Verify reject_foreign prevents foreign semantic model."""
    data = _dataquality_base_scorecard_data(
        scope_type="semantic_model",
        model=semantic_model_b,
        steward=admin_user,
    )
    # Scoped queryset rejection
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityScorecardForm(data=data, tenant=tenant_a)
    form_wide.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["semantic_model"]


@pytest.mark.django_db
def test_dataquality_scorecard_form_rejects_foreign_data_mart(tenant_a, data_mart_b, admin_user):
    """Verify reject_foreign prevents foreign data mart."""
    data = _dataquality_base_scorecard_data(
        scope_type="data_mart",
        mart=data_mart_b,
        steward=admin_user,
    )
    # Scoped queryset rejection
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "data_mart" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityScorecardForm(data=data, tenant=tenant_a)
    form_wide.fields["data_mart"].queryset = DataMart.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["data_mart"]


@pytest.mark.django_db
def test_dataquality_scorecard_form_rejects_foreign_org_unit(tenant_a, tenant_b, warehouse_table_a, admin_user):
    """Verify reject_foreign prevents foreign org unit."""
    foreign_org_unit = _dataquality_create_org_unit(tenant_b, "Globex Business Unit")
    data = _dataquality_base_scorecard_data(
        table=warehouse_table_a,
        org_unit=foreign_org_unit,
        steward=admin_user,
    )
    # Scoped queryset rejection
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityScorecardForm(data=data, tenant=tenant_a)
    form_wide.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["org_unit"]


@pytest.mark.django_db
def test_dataquality_scorecard_form_rejects_foreign_steward(tenant_a, warehouse_table_a, admin_user_b):
    """Verify reject_foreign prevents foreign steward."""
    data = _dataquality_base_scorecard_data(
        table=warehouse_table_a,
        steward=admin_user_b,
    )
    # Scoped queryset rejection
    form = DataQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "steward" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = DataQualityScorecardForm(data=data, tenant=tenant_a)
    form_wide.fields["steward"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["steward"]
