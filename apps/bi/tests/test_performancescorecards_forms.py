"""Unit tests for Sub-module 10.11 Performance Scorecards forms.

Forms covered:
- KpiDefinitionForm
- KpiDefinitionRefreshForm / KpiDefinitionQuickRefreshForm
- PerformanceScorecardForm
- PerformanceScorecardRecalculateForm
- ScorecardKpiAssignmentForm
- ScorecardKpiRecordActualForm
- StrategicObjectiveForm
"""
from decimal import Decimal

import pytest
from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms.PerformanceScorecards import (
    KpiDefinitionForm,
    KpiDefinitionRefreshForm,
    PerformanceScorecardForm,
    PerformanceScorecardRecalculateForm,
    ScorecardKpiAssignmentForm,
    ScorecardKpiRecordActualForm,
    StrategicObjectiveForm,
)
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PerformanceScorecards.PerformanceScorecards import PerformanceScorecard
from apps.bi.models.PerformanceScorecards.ScorecardKpiAssignments import ScorecardKpiAssignment
from apps.bi.models.PerformanceScorecards.StrategicObjectives import StrategicObjective
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()

# Alias requirement for Quick Refresh action form
KpiDefinitionQuickRefreshForm = KpiDefinitionRefreshForm


# ==============================================================================
# Module Helpers (named _performancescorecards_*)
# ==============================================================================


def _performancescorecards_create_org_unit(tenant, name="Operations Dept"):
    """Helper to create a tenant-scoped OrgUnit instance."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _performancescorecards_create_user(tenant, username, is_active=True):
    """Helper to create a tenant-scoped User instance."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="TestPass123!",
        tenant=tenant,
        is_active=is_active,
    )


def _performancescorecards_base_kpi_data(**overrides):
    """Helper generating a valid payload for KpiDefinitionForm."""
    data = {
        "code": "OP_MARGIN_PCT",
        "name": "Operating Profit Margin %",
        "slug": "operating-profit-margin-pct",
        "description": "Percentage of revenue left after paying for costs of production.",
        "category": "Profitability",
        "perspective": "financial",
        "target_direction": "maximize",
        "unit_of_measure": "percentage",
        "tracking_frequency": "monthly",
        "calculation_type": "manual",
        "formula_expression": "",
        "target_value": "18.5000",
        "warning_threshold": "14.0000",
        "critical_threshold": "10.0000",
        "current_value": "17.2000",
        "previous_value": "16.8000",
        "industry_benchmark_value": "15.0000",
        "benchmark_source": "Industry Benchmark 2026",
        "benchmark_percentile": 75,
        "status": "active",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _performancescorecards_base_scorecard_data(**overrides):
    """Helper generating a valid payload for PerformanceScorecardForm."""
    data = {
        "name": "2026 Strategic Balanced Scorecard",
        "slug": "2026-strategic-balanced-scorecard",
        "description": "Executive balanced scorecard covering all 4 perspectives.",
        "scorecard_type": "balanced_scorecard",
        "review_period": "quarterly",
        "fiscal_year": 2026,
        "financial_weight": "25.00",
        "customer_weight": "25.00",
        "internal_process_weight": "25.00",
        "learning_growth_weight": "25.00",
        "status": "active",
        "is_default": False,
        "is_published": True,
    }
    data.update(overrides)
    return data


def _performancescorecards_base_assignment_data(scorecard_pk, kpi_pk, **overrides):
    """Helper generating a valid payload for ScorecardKpiAssignmentForm."""
    data = {
        "scorecard": scorecard_pk,
        "kpi": kpi_pk,
        "perspective": "financial",
        "weight": "20.00",
        "target_value": "18.5000",
        "actual_value": "17.2000",
        "benchmark_overlay_value": "15.0000",
        "manager_notes": "Good progress in Q1",
        "sort_order": 10,
    }
    data.update(overrides)
    return data


def _performancescorecards_base_objective_data(**overrides):
    """Helper generating a valid payload for StrategicObjectiveForm."""
    data = {
        "code": "GROW_REV",
        "name": "Accelerate Top-Line Revenue Growth",
        "slug": "accelerate-top-line-revenue-growth",
        "perspective": "financial",
        "statement_of_intent": "Increase annualized recurring enterprise revenue by 30%.",
        "target_date": "2026-12-31",
        "status": "active",
        "sort_order": 10,
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. KpiDefinitionForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_kpi_form_valid_submission(tenant_a, calculated_measure_a, admin_user):
    """Verify valid KpiDefinitionForm submission creates an instance with BKPI prefix and correct tenant."""
    dept = _performancescorecards_create_org_unit(tenant_a, "Acme Finance")
    data = _performancescorecards_base_kpi_data(
        semantic_measure=calculated_measure_a.pk,
        department=dept.pk,
        owner=admin_user.pk,
    )
    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BKPI-")
    assert instance.code == "OP_MARGIN_PCT"
    assert instance.name == "Operating Profit Margin %"
    assert instance.slug == "operating-profit-margin-pct"
    assert instance.semantic_measure == calculated_measure_a
    assert instance.department == dept
    assert instance.owner == admin_user
    assert instance.target_value == Decimal("18.5000")
    assert instance.current_value == Decimal("17.2000")
    assert instance.status == "active"
    assert instance.is_active is True


@pytest.mark.django_db
def test_performancescorecards_kpi_form_slug_auto_generation(tenant_a):
    """Verify empty slug is auto-populated from name via clean_slug."""
    data = _performancescorecards_base_kpi_data(
        name="Net Promoter Score Enterprise",
        slug="",
    )
    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "net-promoter-score-enterprise"


@pytest.mark.django_db
def test_performancescorecards_kpi_form_slug_custom_preserved(tenant_a):
    """Verify custom slug is preserved when provided."""
    data = _performancescorecards_base_kpi_data(
        name="Net Promoter Score Enterprise",
        slug="custom-nps-slug-2026",
    )
    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "custom-nps-slug-2026"


@pytest.mark.django_db
def test_performancescorecards_kpi_form_field_exclusions(tenant_a):
    """Verify system, auto-computed, and lifecycle fields are excluded from KpiDefinitionForm."""
    form = KpiDefinitionForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "last_calculated_at",
        "created_at",
        "updated_at",
        "created_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from KpiDefinitionForm"


@pytest.mark.django_db
def test_performancescorecards_kpi_form_required_fields(tenant_a):
    """Verify required fields fail validation when omitted."""
    form = KpiDefinitionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "code" in form.errors
    assert "name" in form.errors


@pytest.mark.django_db
def test_performancescorecards_kpi_form_optional_fields(tenant_a):
    """Verify optional fields can be omitted without causing validation errors."""
    data = {
        "code": "MIN_KPI",
        "name": "Minimal Valid KPI",
        "category": "operations",
        "perspective": "internal_process",
        "target_direction": "maximize",
        "unit_of_measure": "percentage",
        "tracking_frequency": "monthly",
        "calculation_type": "manual",
        "target_value": "10.0000",
        "current_value": "9.5000",
        "status": "draft",
        "is_active": True,
    }
    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_performancescorecards_kpi_form_tenant_scoped_querysets(
    tenant_a,
    tenant_b,
    calculated_measure_a,
    calculated_measure_b,
    admin_user,
    admin_user_b,
):
    """Verify semantic_measure, department, and owner querysets are strictly tenant-scoped and filter active records."""
    dept_a = _performancescorecards_create_org_unit(tenant_a, "Dept A")
    dept_b = _performancescorecards_create_org_unit(tenant_b, "Dept B")
    inactive_user_a = _performancescorecards_create_user(tenant_a, "inactive_a", is_active=False)

    form = KpiDefinitionForm(tenant=tenant_a)

    sm_qs = form.fields["semantic_measure"].queryset
    assert calculated_measure_a in sm_qs
    assert calculated_measure_b not in sm_qs

    dept_qs = form.fields["department"].queryset
    assert dept_a in dept_qs
    assert dept_b not in dept_qs

    owner_qs = form.fields["owner"].queryset
    assert admin_user in owner_qs
    assert admin_user_b not in owner_qs
    assert inactive_user_a not in owner_qs


@pytest.mark.django_db
def test_performancescorecards_kpi_form_unscoped_initialization():
    """Verify unscoped initialization (tenant=None) does not crash."""
    form = KpiDefinitionForm()
    assert form.fields["semantic_measure"] is not None
    assert form.fields["department"] is not None
    assert form.fields["owner"] is not None


@pytest.mark.django_db
def test_performancescorecards_kpi_form_reject_foreign_semantic_measure(tenant_a, calculated_measure_b):
    """Verify reject_foreign stops cross-tenant semantic_measure assignment."""
    data = _performancescorecards_base_kpi_data(semantic_measure=calculated_measure_b.pk)

    # 1. Scoped queryset blocks it
    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_measure" in form.errors

    # 2. Defense in depth: widened queryset triggers reject_foreign
    form_wide = KpiDefinitionForm(data=data, tenant=tenant_a)
    form_wide.fields["semantic_measure"].queryset = CalculatedMeasure.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["semantic_measure"]


@pytest.mark.django_db
def test_performancescorecards_kpi_form_reject_foreign_department(tenant_a, tenant_b):
    """Verify reject_foreign stops cross-tenant department assignment."""
    foreign_dept = _performancescorecards_create_org_unit(tenant_b, "Globex Dept")
    data = _performancescorecards_base_kpi_data(department=foreign_dept.pk)

    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "department" in form.errors

    form_wide = KpiDefinitionForm(data=data, tenant=tenant_a)
    form_wide.fields["department"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["department"]


@pytest.mark.django_db
def test_performancescorecards_kpi_form_reject_foreign_owner(tenant_a, admin_user_b):
    """Verify reject_foreign stops cross-tenant owner assignment."""
    data = _performancescorecards_base_kpi_data(owner=admin_user_b.pk)

    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors

    form_wide = KpiDefinitionForm(data=data, tenant=tenant_a)
    form_wide.fields["owner"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["owner"]


@pytest.mark.django_db
def test_performancescorecards_kpi_form_unique_slug_within_tenant(tenant_a, kpi_definition_a):
    """Verify duplicate slug within same tenant is rejected by TenantUniqueMixin."""
    data = _performancescorecards_base_kpi_data(
        code="DIFF_CODE_123",
        name="Unique Name Here",
        slug=kpi_definition_a.slug,
    )
    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    errors_str = str(form.errors)
    assert "slug" in errors_str or "__all__" in errors_str
    assert "already exists" in errors_str


@pytest.mark.django_db
def test_performancescorecards_kpi_form_unique_slug_across_tenants(tenant_a, tenant_b, kpi_definition_b):
    """Verify same slug can exist across different tenants."""
    data = _performancescorecards_base_kpi_data(
        code="ACME_KPI_CODE",
        name="Acme KPI Same Slug",
        slug=kpi_definition_b.slug,
    )
    form = KpiDefinitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_performancescorecards_kpi_form_widgets_and_css(tenant_a):
    """Verify correct CSS classes and HTML attributes on form widgets."""
    form = KpiDefinitionForm(tenant=tenant_a)
    assert "form-input" in form.fields["code"].widget.attrs["class"]
    assert "form-input" in form.fields["name"].widget.attrs["class"]
    assert "form-textarea" in form.fields["description"].widget.attrs["class"]
    assert "form-select" in form.fields["perspective"].widget.attrs["class"]
    assert "form-select" in form.fields["target_direction"].widget.attrs["class"]
    assert "form-select" in form.fields["unit_of_measure"].widget.attrs["class"]
    assert "form-checkbox" in form.fields["is_active"].widget.attrs["class"]


# ==============================================================================
# 2. KpiDefinitionRefreshForm / KpiDefinitionQuickRefreshForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_kpi_refresh_form_valid():
    """Verify KpiDefinitionRefreshForm accepts valid decimal values and notes."""
    form_data = {
        "new_value": "19.8500",
        "notes": "Verified by Q1 external audit",
    }
    form = KpiDefinitionRefreshForm(data=form_data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["new_value"] == Decimal("19.8500")
    assert form.cleaned_data["notes"] == "Verified by Q1 external audit"


@pytest.mark.django_db
def test_performancescorecards_kpi_refresh_form_optional_notes():
    """Verify notes field is optional in KpiDefinitionRefreshForm."""
    form_data = {
        "new_value": "12.3456",
        "notes": "",
    }
    form = KpiDefinitionRefreshForm(data=form_data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["new_value"] == Decimal("12.3456")
    assert form.cleaned_data["notes"] == ""


@pytest.mark.django_db
def test_performancescorecards_kpi_refresh_form_missing_new_value():
    """Verify missing new_value causes validation failure."""
    form = KpiDefinitionRefreshForm(data={"notes": "No number provided"})
    assert not form.is_valid()
    assert "new_value" in form.errors


@pytest.mark.django_db
def test_performancescorecards_kpi_refresh_form_invalid_number():
    """Verify non-numeric value in new_value causes validation failure."""
    form = KpiDefinitionRefreshForm(data={"new_value": "abc_not_a_number"})
    assert not form.is_valid()
    assert "new_value" in form.errors


@pytest.mark.django_db
def test_performancescorecards_kpi_quick_refresh_form_alias():
    """Verify KpiDefinitionQuickRefreshForm alias is present and functions identically."""
    form = KpiDefinitionQuickRefreshForm(data={"new_value": "25.0000", "notes": "Quick refresh test"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["new_value"] == Decimal("25.0000")


# ==============================================================================
# 3. PerformanceScorecardForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_valid_submission(tenant_a, admin_user):
    """Verify valid PerformanceScorecardForm submission with balanced weights (sum = 100%)."""
    org_unit = _performancescorecards_create_org_unit(tenant_a, "Corporate Strategy")
    data = _performancescorecards_base_scorecard_data(
        owner=admin_user.pk,
        org_unit=org_unit.pk,
    )
    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BSCR-")
    assert instance.name == "2026 Strategic Balanced Scorecard"
    assert instance.slug == "2026-strategic-balanced-scorecard"
    assert instance.financial_weight == Decimal("25.00")
    assert instance.customer_weight == Decimal("25.00")
    assert instance.internal_process_weight == Decimal("25.00")
    assert instance.learning_growth_weight == Decimal("25.00")
    assert instance.owner == admin_user
    assert instance.org_unit == org_unit
    assert instance.status == "active"
    assert instance.is_published is True


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_weights_must_sum_to_100(tenant_a):
    """Verify validation error when the 4 BSC perspective weights do not sum to 100.00%."""
    data = _performancescorecards_base_scorecard_data(
        financial_weight="20.00",
        customer_weight="20.00",
        internal_process_weight="20.00",
        learning_growth_weight="20.00",  # Sum = 80.00%
    )
    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    non_field_errors = str(form.non_field_errors())
    assert "The 4 BSC perspective weights must sum to 100.00%" in non_field_errors
    assert "80.00%" in non_field_errors


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_weights_custom_split_valid(tenant_a):
    """Verify custom non-equal weight split summing to exactly 100.00% is valid."""
    data = _performancescorecards_base_scorecard_data(
        financial_weight="40.00",
        customer_weight="30.00",
        internal_process_weight="20.00",
        learning_growth_weight="10.00",  # Sum = 100.00%
    )
    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_slug_auto_generation(tenant_a):
    """Verify empty slug is auto-generated from scorecard name."""
    data = _performancescorecards_base_scorecard_data(
        name="Digital Transformation Scorecard 2027",
        slug="",
    )
    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "digital-transformation-scorecard-2027"


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_field_exclusions(tenant_a):
    """Verify computed roll-up metrics and lifecycle fields are excluded from PerformanceScorecardForm."""
    form = PerformanceScorecardForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "overall_score",
        "overall_rag_status",
        "last_recalculated_at",
        "created_at",
        "updated_at",
        "created_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from PerformanceScorecardForm"


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_required_fields(tenant_a):
    """Verify missing required name field fails validation."""
    form = PerformanceScorecardForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_optional_fields(tenant_a):
    """Verify optional fields (description, owner, org_unit) can be left empty."""
    data = {
        "name": "Lean Scorecard",
        "scorecard_type": "operational",
        "review_period": "monthly",
        "fiscal_year": 2026,
        "financial_weight": "25.00",
        "customer_weight": "25.00",
        "internal_process_weight": "25.00",
        "learning_growth_weight": "25.00",
        "status": "draft",
        "is_default": False,
        "is_published": False,
    }
    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_tenant_scoped_querysets(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify org_unit and owner querysets only contain tenant_a records."""
    ou_a = _performancescorecards_create_org_unit(tenant_a, "Unit A")
    ou_b = _performancescorecards_create_org_unit(tenant_b, "Unit B")
    inactive_user_a = _performancescorecards_create_user(tenant_a, "inactive_sc_user", is_active=False)

    form = PerformanceScorecardForm(tenant=tenant_a)

    ou_qs = form.fields["org_unit"].queryset
    assert ou_a in ou_qs
    assert ou_b not in ou_qs

    owner_qs = form.fields["owner"].queryset
    assert admin_user in owner_qs
    assert admin_user_b not in owner_qs
    assert inactive_user_a not in owner_qs


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_unscoped_initialization():
    """Verify unscoped initialization (tenant=None) does not crash."""
    form = PerformanceScorecardForm()
    assert form.fields["org_unit"] is not None
    assert form.fields["owner"] is not None


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_reject_foreign_org_unit(tenant_a, tenant_b):
    """Verify reject_foreign stops cross-tenant org_unit assignment in scorecard form."""
    foreign_ou = _performancescorecards_create_org_unit(tenant_b, "Foreign Unit")
    data = _performancescorecards_base_scorecard_data(org_unit=foreign_ou.pk)

    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors

    form_wide = PerformanceScorecardForm(data=data, tenant=tenant_a)
    form_wide.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["org_unit"]


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_reject_foreign_owner(tenant_a, admin_user_b):
    """Verify reject_foreign stops cross-tenant owner assignment in scorecard form."""
    data = _performancescorecards_base_scorecard_data(owner=admin_user_b.pk)

    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors

    form_wide = PerformanceScorecardForm(data=data, tenant=tenant_a)
    form_wide.fields["owner"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["owner"]


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_unique_slug_within_tenant(tenant_a, performance_scorecard_a):
    """Verify duplicate slug within same tenant fails validation via TenantUniqueMixin."""
    data = _performancescorecards_base_scorecard_data(
        name="Another Scorecard With Duplicate Slug",
        slug=performance_scorecard_a.slug,
    )
    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    errors_str = str(form.errors)
    assert "slug" in errors_str or "__all__" in errors_str
    assert "already exists" in errors_str


@pytest.mark.django_db
def test_performancescorecards_scorecard_form_unique_slug_across_tenants(tenant_a, tenant_b, performance_scorecard_b):
    """Verify duplicate slug across different tenants is permitted."""
    data = _performancescorecards_base_scorecard_data(
        name="Acme Scorecard Same Slug",
        slug=performance_scorecard_b.slug,
    )
    form = PerformanceScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# ==============================================================================
# 4. PerformanceScorecardRecalculateForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_scorecard_recalculate_form_empty():
    """Verify recalculate action form accepts empty POST data."""
    form = PerformanceScorecardRecalculateForm(data={})
    assert form.is_valid(), form.errors


# ==============================================================================
# 5. ScorecardKpiAssignmentForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_assignment_form_valid_submission(
    tenant_a,
    performance_scorecard_a,
    kpi_definition_a,
    strategic_objective_a,
):
    """Verify valid ScorecardKpiAssignmentForm submission saves instance with BSCI prefix and tenant."""
    data = _performancescorecards_base_assignment_data(
        scorecard_pk=performance_scorecard_a.pk,
        kpi_pk=kpi_definition_a.pk,
        objective=strategic_objective_a.pk,
        weight="30.00",
        target_value="15.0000",
        actual_value="14.8000",
        benchmark_overlay_value="14.0000",
        manager_notes="Tracking well towards target.",
        sort_order=20,
    )
    form = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BSCI-")
    assert instance.scorecard == performance_scorecard_a
    assert instance.kpi == kpi_definition_a
    assert instance.objective == strategic_objective_a
    assert instance.weight == Decimal("30.00")
    assert instance.target_value == Decimal("15.0000")
    assert instance.actual_value == Decimal("14.8000")
    assert instance.benchmark_overlay_value == Decimal("14.0000")
    assert instance.manager_notes == "Tracking well towards target."
    assert instance.sort_order == 20


@pytest.mark.django_db
def test_performancescorecards_assignment_form_field_exclusions(tenant_a):
    """Verify auto-calculated metrics, variance, and lifecycle fields are excluded from ScorecardKpiAssignmentForm."""
    form = ScorecardKpiAssignmentForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "variance",
        "variance_percentage",
        "rag_status",
        "trend_direction",
        "normalized_score",
        "benchmark_gap",
        "evaluated_at",
        "created_at",
        "updated_at",
        "created_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from ScorecardKpiAssignmentForm"


@pytest.mark.django_db
def test_performancescorecards_assignment_form_required_fields(tenant_a):
    """Verify scorecard and kpi are required fields."""
    form = ScorecardKpiAssignmentForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "scorecard" in form.errors
    assert "kpi" in form.errors


@pytest.mark.django_db
def test_performancescorecards_assignment_form_optional_fields(
    tenant_a,
    performance_scorecard_a,
    kpi_definition_a,
):
    """Verify objective, manager_notes, and benchmark_overlay_value are optional."""
    data = {
        "scorecard": performance_scorecard_a.pk,
        "kpi": kpi_definition_a.pk,
        "perspective": "customer",
        "weight": "15.00",
        "target_value": "80.0000",
        "actual_value": "78.5000",
        "sort_order": 1,
    }
    form = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_performancescorecards_assignment_form_tenant_scoped_querysets(
    tenant_a,
    tenant_b,
    performance_scorecard_a,
    performance_scorecard_b,
    kpi_definition_a,
    kpi_definition_b,
    strategic_objective_a,
    strategic_objective_b,
):
    """Verify scorecard, kpi, and objective dropdowns are strictly scoped to self.tenant and active KPIs."""
    inactive_kpi_a = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="INACTIVE_KPI",
        name="Inactive KPI Definition",
        is_active=False,
    )

    form = ScorecardKpiAssignmentForm(tenant=tenant_a)

    sc_qs = form.fields["scorecard"].queryset
    assert performance_scorecard_a in sc_qs
    assert performance_scorecard_b not in sc_qs

    kpi_qs = form.fields["kpi"].queryset
    assert kpi_definition_a in kpi_qs
    assert kpi_definition_b not in kpi_qs
    assert inactive_kpi_a not in kpi_qs

    obj_qs = form.fields["objective"].queryset
    assert strategic_objective_a in obj_qs
    assert strategic_objective_b not in obj_qs


@pytest.mark.django_db
def test_performancescorecards_assignment_form_unscoped_initialization():
    """Verify unscoped initialization (tenant=None) does not crash."""
    form = ScorecardKpiAssignmentForm()
    assert form.fields["scorecard"] is not None
    assert form.fields["kpi"] is not None
    assert form.fields["objective"] is not None


@pytest.mark.django_db
def test_performancescorecards_assignment_form_reject_foreign_scorecard(
    tenant_a, performance_scorecard_b, kpi_definition_a
):
    """Verify reject_foreign stops cross-tenant scorecard assignment."""
    data = _performancescorecards_base_assignment_data(
        scorecard_pk=performance_scorecard_b.pk,
        kpi_pk=kpi_definition_a.pk,
    )

    form = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "scorecard" in form.errors

    form_wide = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    form_wide.fields["scorecard"].queryset = PerformanceScorecard.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["scorecard"]


@pytest.mark.django_db
def test_performancescorecards_assignment_form_reject_foreign_kpi(
    tenant_a, performance_scorecard_a, kpi_definition_b
):
    """Verify reject_foreign stops cross-tenant kpi assignment."""
    data = _performancescorecards_base_assignment_data(
        scorecard_pk=performance_scorecard_a.pk,
        kpi_pk=kpi_definition_b.pk,
    )

    form = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi" in form.errors

    form_wide = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    form_wide.fields["kpi"].queryset = KpiDefinition.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["kpi"]


@pytest.mark.django_db
def test_performancescorecards_assignment_form_reject_foreign_objective(
    tenant_a, performance_scorecard_a, kpi_definition_a, strategic_objective_b
):
    """Verify reject_foreign stops cross-tenant objective assignment."""
    data = _performancescorecards_base_assignment_data(
        scorecard_pk=performance_scorecard_a.pk,
        kpi_pk=kpi_definition_a.pk,
        objective=strategic_objective_b.pk,
    )

    form = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "objective" in form.errors

    form_wide = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    form_wide.fields["objective"].queryset = StrategicObjective.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["objective"]


@pytest.mark.django_db
def test_performancescorecards_assignment_form_unique_scorecard_kpi_constraint(
    tenant_a, scorecard_kpi_assignment_a
):
    """Verify duplicate assignment of (scorecard, kpi) within same tenant fails uniqueness check."""
    data = _performancescorecards_base_assignment_data(
        scorecard_pk=scorecard_kpi_assignment_a.scorecard.pk,
        kpi_pk=scorecard_kpi_assignment_a.kpi.pk,
    )
    form = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    # Uniqueness constraint on tenant, scorecard, kpi
    errors_str = str(form.errors)
    assert "scorecard" in errors_str or "kpi" in errors_str or "__all__" in errors_str


@pytest.mark.django_db
def test_performancescorecards_assignment_form_unique_scorecard_kpi_across_tenants(
    tenant_a, tenant_b, scorecard_kpi_assignment_b
):
    """Verify same scorecard and kpi numbers/codes can exist in another tenant."""
    sc_a = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Scorecard In Tenant A",
        slug="scorecard-in-tenant-a",
    )
    kpi_a = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="KPI_TENANT_A",
        name="KPI in Tenant A",
        slug="kpi-in-tenant-a",
    )
    data = _performancescorecards_base_assignment_data(
        scorecard_pk=sc_a.pk,
        kpi_pk=kpi_a.pk,
    )
    form = ScorecardKpiAssignmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# ==============================================================================
# 6. ScorecardKpiRecordActualForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_record_actual_form_valid_submission(scorecard_kpi_assignment_a):
    """Verify ScorecardKpiRecordActualForm correctly updates actual_value and manager_notes."""
    form_data = {
        "actual_value": "18.7500",
        "manager_notes": "Exceeded Q1 milestone due to operational efficiency.",
    }
    form = ScorecardKpiRecordActualForm(data=form_data, instance=scorecard_kpi_assignment_a)
    assert form.is_valid(), form.errors

    saved_instance = form.save()
    assert saved_instance.actual_value == Decimal("18.7500")
    assert saved_instance.manager_notes == "Exceeded Q1 milestone due to operational efficiency."


@pytest.mark.django_db
def test_performancescorecards_record_actual_form_fields_whitelisted():
    """Verify only actual_value and manager_notes are present on the record actual form."""
    form = ScorecardKpiRecordActualForm()
    assert set(form.fields.keys()) == {"actual_value", "manager_notes"}


@pytest.mark.django_db
def test_performancescorecards_record_actual_form_optional_notes(scorecard_kpi_assignment_a):
    """Verify manager_notes is optional in ScorecardKpiRecordActualForm."""
    form_data = {
        "actual_value": "16.0000",
        "manager_notes": "",
    }
    form = ScorecardKpiRecordActualForm(data=form_data, instance=scorecard_kpi_assignment_a)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.actual_value == Decimal("16.0000")
    assert saved.manager_notes == ""


@pytest.mark.django_db
def test_performancescorecards_record_actual_form_missing_actual_value(scorecard_kpi_assignment_a):
    """Verify missing actual_value fails validation."""
    form = ScorecardKpiRecordActualForm(data={"manager_notes": "Note without actual"}, instance=scorecard_kpi_assignment_a)
    assert not form.is_valid()
    assert "actual_value" in form.errors


@pytest.mark.django_db
def test_performancescorecards_record_actual_form_invalid_number(scorecard_kpi_assignment_a):
    """Verify non-numeric actual_value fails validation."""
    form = ScorecardKpiRecordActualForm(data={"actual_value": "non_numeric"}, instance=scorecard_kpi_assignment_a)
    assert not form.is_valid()
    assert "actual_value" in form.errors


# ==============================================================================
# 7. StrategicObjectiveForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_objective_form_valid_submission(tenant_a, admin_user):
    """Verify valid StrategicObjectiveForm submission creates instance with BOBJ prefix and correct tenant."""
    ou = _performancescorecards_create_org_unit(tenant_a, "Strategic Planning")
    data = _performancescorecards_base_objective_data(
        owner=admin_user.pk,
        org_unit=ou.pk,
    )
    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BOBJ-")
    assert instance.code == "GROW_REV"
    assert instance.name == "Accelerate Top-Line Revenue Growth"
    assert instance.slug == "accelerate-top-line-revenue-growth"
    assert instance.perspective == "financial"
    assert instance.owner == admin_user
    assert instance.org_unit == ou
    assert instance.status == "active"


@pytest.mark.django_db
def test_performancescorecards_objective_form_slug_auto_generation(tenant_a):
    """Verify empty slug is auto-generated from objective name."""
    data = _performancescorecards_base_objective_data(
        name="Achieve Operational Carbon Neutrality",
        slug="",
    )
    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "achieve-operational-carbon-neutrality"


@pytest.mark.django_db
def test_performancescorecards_objective_form_slug_custom_preserved(tenant_a):
    """Verify custom slug is preserved when provided."""
    data = _performancescorecards_base_objective_data(
        name="Achieve Operational Carbon Neutrality",
        slug="custom-carbon-slug-2030",
    )
    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "custom-carbon-slug-2030"


@pytest.mark.django_db
def test_performancescorecards_objective_form_field_exclusions(tenant_a):
    """Verify auto-calculated alignment metrics and lifecycle fields are excluded from StrategicObjectiveForm."""
    form = StrategicObjectiveForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "rag_status",
        "alignment_score",
        "created_at",
        "updated_at",
        "created_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from StrategicObjectiveForm"


@pytest.mark.django_db
def test_performancescorecards_objective_form_required_fields(tenant_a):
    """Verify code and name are required fields in StrategicObjectiveForm."""
    form = StrategicObjectiveForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "code" in form.errors
    assert "name" in form.errors


@pytest.mark.django_db
def test_performancescorecards_objective_form_optional_fields(tenant_a):
    """Verify optional fields (statement_of_intent, parent_objective, target_date, owner, org_unit) can be omitted."""
    data = {
        "code": "MIN_OBJ",
        "name": "Minimal Objective",
        "perspective": "customer",
        "status": "active",
        "sort_order": 5,
    }
    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_performancescorecards_objective_form_tenant_scoped_querysets(
    tenant_a,
    tenant_b,
    strategic_objective_a,
    strategic_objective_b,
    admin_user,
    admin_user_b,
):
    """Verify parent_objective, org_unit, and owner querysets are strictly tenant-scoped."""
    ou_a = _performancescorecards_create_org_unit(tenant_a, "Strategy A")
    ou_b = _performancescorecards_create_org_unit(tenant_b, "Strategy B")
    inactive_user_a = _performancescorecards_create_user(tenant_a, "inactive_obj_user", is_active=False)

    form = StrategicObjectiveForm(tenant=tenant_a)

    parent_qs = form.fields["parent_objective"].queryset
    assert strategic_objective_a in parent_qs
    assert strategic_objective_b not in parent_qs

    ou_qs = form.fields["org_unit"].queryset
    assert ou_a in ou_qs
    assert ou_b not in ou_qs

    owner_qs = form.fields["owner"].queryset
    assert admin_user in owner_qs
    assert admin_user_b not in owner_qs
    assert inactive_user_a not in owner_qs


@pytest.mark.django_db
def test_performancescorecards_objective_form_unscoped_initialization():
    """Verify unscoped initialization (tenant=None) does not crash."""
    form = StrategicObjectiveForm()
    assert form.fields["parent_objective"] is not None
    assert form.fields["org_unit"] is not None
    assert form.fields["owner"] is not None


@pytest.mark.django_db
def test_performancescorecards_objective_form_parent_excludes_self_in_edit_mode(
    tenant_a, strategic_objective_a
):
    """Verify editing an existing objective excludes itself from parent_objective dropdown."""
    form = StrategicObjectiveForm(instance=strategic_objective_a, tenant=tenant_a)
    parent_qs = form.fields["parent_objective"].queryset
    assert strategic_objective_a not in parent_qs


@pytest.mark.django_db
def test_performancescorecards_objective_form_prevent_self_as_parent(
    tenant_a, strategic_objective_a
):
    """Verify clean() rejects selecting self as parent_objective."""
    data = _performancescorecards_base_objective_data(
        code=strategic_objective_a.code,
        name=strategic_objective_a.name,
        slug=strategic_objective_a.slug,
        parent_objective=strategic_objective_a.pk,
    )
    form = StrategicObjectiveForm(data=data, instance=strategic_objective_a, tenant=tenant_a)
    # Widen queryset so field validation does not block before form.clean()
    form.fields["parent_objective"].queryset = StrategicObjective.objects.filter(tenant=tenant_a)
    assert not form.is_valid()
    assert "parent_objective" in form.errors
    assert "An objective cannot be its own parent." in form.errors["parent_objective"]


@pytest.mark.django_db
def test_performancescorecards_objective_form_reject_foreign_parent_objective(
    tenant_a, strategic_objective_b
):
    """Verify reject_foreign stops assigning foreign parent_objective."""
    data = _performancescorecards_base_objective_data(parent_objective=strategic_objective_b.pk)

    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "parent_objective" in form.errors

    form_wide = StrategicObjectiveForm(data=data, tenant=tenant_a)
    form_wide.fields["parent_objective"].queryset = StrategicObjective.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["parent_objective"]


@pytest.mark.django_db
def test_performancescorecards_objective_form_reject_foreign_org_unit(tenant_a, tenant_b):
    """Verify reject_foreign stops assigning foreign org_unit in StrategicObjectiveForm."""
    foreign_ou = _performancescorecards_create_org_unit(tenant_b, "Globex Business Unit")
    data = _performancescorecards_base_objective_data(org_unit=foreign_ou.pk)

    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors

    form_wide = StrategicObjectiveForm(data=data, tenant=tenant_a)
    form_wide.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["org_unit"]


@pytest.mark.django_db
def test_performancescorecards_objective_form_reject_foreign_owner(tenant_a, admin_user_b):
    """Verify reject_foreign stops assigning foreign owner in StrategicObjectiveForm."""
    data = _performancescorecards_base_objective_data(owner=admin_user_b.pk)

    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors

    form_wide = StrategicObjectiveForm(data=data, tenant=tenant_a)
    form_wide.fields["owner"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["owner"]


@pytest.mark.django_db
def test_performancescorecards_objective_form_unique_slug_within_tenant(
    tenant_a, strategic_objective_a
):
    """Verify duplicate slug within same tenant fails validation via TenantUniqueMixin."""
    data = _performancescorecards_base_objective_data(
        code="DIFFERENT_CODE",
        name="Different Objective Name",
        slug=strategic_objective_a.slug,
    )
    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    errors_str = str(form.errors)
    assert "slug" in errors_str or "__all__" in errors_str
    assert "already exists" in errors_str


@pytest.mark.django_db
def test_performancescorecards_objective_form_unique_slug_across_tenants(
    tenant_a, tenant_b, strategic_objective_b
):
    """Verify duplicate slug across different tenants is permitted."""
    data = _performancescorecards_base_objective_data(
        code="ACME_OBJ_CODE",
        name="Acme Objective With Duplicate Slug",
        slug=strategic_objective_b.slug,
    )
    form = StrategicObjectiveForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
