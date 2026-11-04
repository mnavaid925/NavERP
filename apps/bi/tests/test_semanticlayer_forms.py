"""Unit tests for Sub-module 10.4 Semantic Layer forms.

Forms covered:
- SemanticModelForm
- SemanticModelCertificationForm
- BusinessGlossaryTermForm
- BusinessGlossaryTermCertificationForm
- CalculatedMeasureForm
- DrillHierarchyForm
"""
import json
import pytest
from django.contrib.auth import get_user_model

from apps.bi.forms import (
    BusinessGlossaryTermCertificationForm,
    BusinessGlossaryTermForm,
    CalculatedMeasureForm,
    DrillHierarchyForm,
    SemanticModelCertificationForm,
    SemanticModelForm,
)
from apps.bi.models import (
    BusinessGlossaryTerm,
    CalculatedMeasure,
    DataMart,
    DrillHierarchy,
    SemanticModel,
    WarehouseTable,
)
from apps.core.models.OrgUnit import OrgUnit


User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture Bridges (to satisfy conftest.semantic_model_a dependencies)
# ---------------------------------------------------------------------------


@pytest.fixture
def warehouse_table(warehouse_table_a):
    """Bridge fixture to satisfy conftest.semantic_model_a dependency."""
    return warehouse_table_a


@pytest.fixture
def data_mart(data_mart_a):
    """Bridge fixture to satisfy conftest.semantic_model_a dependency."""
    return data_mart_a


# ---------------------------------------------------------------------------
# Module Helpers (must be prefixed with _semanticlayer_*)
# ---------------------------------------------------------------------------


def _semanticlayer_create_user(tenant, username, is_active=True):
    """Helper to create a user with specified active status in a tenant."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_active=is_active,
    )


def _semanticlayer_create_org_unit(tenant, name="Business Intelligence Dept"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _semanticlayer_base_semantic_model_data(table=None, mart=None, **overrides):
    """Helper generating valid SemanticModel form payload."""
    data = {
        "name": "Customer Lifetime Value Model",
        "code": "clv_model",
        "model_type": "fact",
        "primary_key_column": "id",
        "natural_key_columns": "customer_id, period_id",
        "grain_description": "One row per customer per accounting period",
        "is_conformed_dimension": False,
        "scd_type": "type_1",
        "is_virtual_view": False,
        "sql_definition": "",
        "access_tier": "department",
        "description": "Calculated customer lifetime value analytical model.",
        "is_active": True,
    }
    if table:
        data["warehouse_table"] = table.pk
    if mart:
        data["data_mart"] = mart.pk
    data.update(overrides)
    return data


def _semanticlayer_base_glossary_term_data(**overrides):
    """Helper generating valid BusinessGlossaryTerm form payload."""
    data = {
        "name": "Gross Margin Percentage",
        "code": "gross_margin_pct",
        "domain_category": "finance",
        "short_definition": "Gross profit divided by total revenue.",
        "full_definition": "Comprehensive corporate formula for gross margin ratio.",
        "calculation_rule": "(Revenue - Cost of Goods Sold) / Revenue * 100",
        "synonyms": "GM%, Gross Margin",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _semanticlayer_base_calculated_measure_data(model, glossary=None, **overrides):
    """Helper generating valid CalculatedMeasure form payload."""
    data = {
        "semantic_model": model.pk,
        "name": "Average Order Value",
        "code": "avg_order_value",
        "aggregation_type": "avg",
        "source_column": "order_amount",
        "formula_expression": "",
        "filter_expression": "order_status = 'completed'",
        "time_intelligence": "none",
        "format_string": "currency",
        "display_units": "auto",
        "target_value": "150.00",
        "warning_threshold": "100.00",
        "critical_threshold": "75.00",
        "description": "Average transaction value across all completed orders.",
        "is_active": True,
    }
    if glossary:
        data["glossary_term"] = glossary.pk
    data.update(overrides)
    return data


def _semanticlayer_base_drill_hierarchy_data(model, **overrides):
    """Helper generating valid DrillHierarchy form payload."""
    data = {
        "semantic_model": model.pk,
        "name": "Calendar Time Drill",
        "code": "calendar_time_drill",
        "hierarchy_type": "time",
        "levels_json_raw": json.dumps([
            {"level": 1, "name": "Year", "column": "order_year"},
            {"level": 2, "name": "Quarter", "column": "order_quarter"},
            {"level": 3, "name": "Month", "column": "order_month"},
        ]),
        "primary_drill_path": True,
        "description": "Standard calendar hierarchy for temporal slicing.",
        "is_active": True,
    }
    data.update(overrides)
    return data


# ===========================================================================
# 1. SemanticModelForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_system_field_exclusions(tenant_a):
    """Verify SemanticModelForm excludes system/lifecycle fields from mass assignment."""
    form = SemanticModelForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "certification_status",
        "certification_notes",
        "certified_by",
        "certified_at",
        "source_fingerprint",
        "last_introspected_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from SemanticModelForm"


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_valid_creation(tenant_a, warehouse_table_a, data_mart_a, admin_user):
    """Verify valid SemanticModelForm submission saves instance with BSMD prefix and tenant."""
    data = _semanticlayer_base_semantic_model_data(
        table=warehouse_table_a,
        mart=data_mart_a,
        owner=admin_user.pk,
    )
    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BSMD-")
    assert instance.code == "clv_model"
    assert instance.warehouse_table == warehouse_table_a
    assert instance.data_mart == data_mart_a
    assert instance.owner == admin_user
    assert instance.certification_status == "draft"


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_scoped_querysets(
    tenant_a,
    tenant_b,
    warehouse_table_a,
    warehouse_table_b,
    data_mart_a,
    data_mart_b,
    admin_user,
    admin_user_b,
):
    """Verify dropdown querysets are strictly scoped to self.tenant and active users."""
    inactive_user_a = _semanticlayer_create_user(tenant_a, "inactive_analyst", is_active=False)
    form = SemanticModelForm(tenant=tenant_a)

    wt_qs = form.fields["warehouse_table"].queryset
    assert warehouse_table_a in wt_qs
    assert warehouse_table_b not in wt_qs

    dm_qs = form.fields["data_mart"].queryset
    assert data_mart_a in dm_qs
    assert data_mart_b not in dm_qs

    owner_qs = form.fields["owner"].queryset
    assert admin_user in owner_qs
    assert inactive_user_a not in owner_qs
    assert admin_user_b not in owner_qs


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_scoped_querysets_bound_inactive_owner(tenant_a):
    """Verify bound inactive owner remains selectable when editing existing model."""
    inactive_owner = _semanticlayer_create_user(tenant_a, "former_lead", is_active=False)
    model = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Legacy Attribution Model",
        code="legacy_attrib",
        owner=inactive_owner,
    )
    form = SemanticModelForm(instance=model, tenant=tenant_a)
    assert inactive_owner in form.fields["owner"].queryset


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_unscoped_tenant_querysets():
    """Verify unscoped initialization (tenant=None) yields empty querysets."""
    form = SemanticModelForm()
    assert form.fields["warehouse_table"].queryset.count() == 0
    assert form.fields["data_mart"].queryset.count() == 0
    assert form.fields["owner"].queryset.count() == 0


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_reject_foreign_warehouse_table(tenant_a, warehouse_table_b):
    """Verify reject_foreign rejects warehouse_table belonging to another tenant."""
    data = _semanticlayer_base_semantic_model_data(table=warehouse_table_b)

    # Rejection by scoped queryset
    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors

    # Explicit defense verification via reject_foreign when queryset widened
    form_wide = SemanticModelForm(data=data, tenant=tenant_a)
    form_wide.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["warehouse_table"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_reject_foreign_data_mart(tenant_a, data_mart_b):
    """Verify reject_foreign rejects data_mart belonging to another tenant."""
    data = _semanticlayer_base_semantic_model_data(mart=data_mart_b)

    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "data_mart" in form.errors

    form_wide = SemanticModelForm(data=data, tenant=tenant_a)
    form_wide.fields["data_mart"].queryset = DataMart.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["data_mart"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_reject_foreign_owner(tenant_a, admin_user_b):
    """Verify reject_foreign rejects owner user belonging to another tenant."""
    data = _semanticlayer_base_semantic_model_data(owner=admin_user_b.pk)

    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors

    form_wide = SemanticModelForm(data=data, tenant=tenant_a)
    form_wide.fields["owner"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["owner"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_virtual_view_requires_sql_definition(tenant_a):
    """Verify is_virtual_view=True requires a non-empty sql_definition."""
    data = _semanticlayer_base_semantic_model_data(
        is_virtual_view=True,
        sql_definition="",
    )
    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "sql_definition" in form.errors
    assert "SQL definition is required when 'is_virtual_view' is enabled." in form.errors["sql_definition"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_virtual_view_with_sql_valid(tenant_a):
    """Verify is_virtual_view=True with valid sql_definition passes validation."""
    data = _semanticlayer_base_semantic_model_data(
        is_virtual_view=True,
        sql_definition="SELECT id, customer_id, SUM(amount) AS total_val FROM staging_orders GROUP BY id, customer_id",
    )
    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_physical_view_sql_optional(tenant_a):
    """Verify is_virtual_view=False allows blank sql_definition."""
    data = _semanticlayer_base_semantic_model_data(
        is_virtual_view=False,
        sql_definition="",
    )
    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_duplicate_code_within_tenant_rejected(tenant_a, semantic_model_a):
    """Verify duplicate code in same tenant is rejected by TenantUniqueMixin."""
    data = _semanticlayer_base_semantic_model_data(
        name="Duplicate Code Model",
        code=semantic_model_a.code,
    )
    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.non_field_errors())


@pytest.mark.django_db
def test_semanticlayer_semantic_model_form_duplicate_code_different_tenant_allowed(tenant_a, semantic_model_b):
    """Verify identical code is accepted across distinct tenants."""
    data = _semanticlayer_base_semantic_model_data(
        name="Tenant A Using Model B Code",
        code=semantic_model_b.code,
    )
    form = SemanticModelForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# ===========================================================================
# 2. SemanticModelCertificationForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_semantic_model_cert_form_valid_statuses():
    """Verify SemanticModelCertificationForm accepts valid status transitions with notes."""
    valid_statuses = ["draft", "in_review", "certified", "deprecated"]
    for status in valid_statuses:
        form = SemanticModelCertificationForm(data={
            "certification_status": status,
            "certification_notes": f"Transitioned to {status} by audit review.",
        })
        assert form.is_valid(), f"Failed for status {status}: {form.errors}"
        assert form.cleaned_data["certification_status"] == status
        assert "audit review" in form.cleaned_data["certification_notes"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_cert_form_invalid_status_rejected():
    """Verify SemanticModelCertificationForm rejects invalid status choice."""
    form = SemanticModelCertificationForm(data={
        "certification_status": "unapproved_status",
        "certification_notes": "Trying invalid status",
    })
    assert not form.is_valid()
    assert "certification_status" in form.errors


@pytest.mark.django_db
def test_semanticlayer_semantic_model_cert_form_notes_optional():
    """Verify certification_notes is optional on SemanticModelCertificationForm."""
    form = SemanticModelCertificationForm(data={
        "certification_status": "certified",
        "certification_notes": "",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["certification_notes"] == ""


# ===========================================================================
# 3. BusinessGlossaryTermForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_system_field_exclusions(tenant_a):
    """Verify BusinessGlossaryTermForm excludes internal system fields from editing."""
    form = BusinessGlossaryTermForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "certification_status",
        "certification_notes",
        "certified_by",
        "certified_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from BusinessGlossaryTermForm"


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_valid_creation(tenant_a, admin_user):
    """Verify valid BusinessGlossaryTermForm saves with BGLO prefix and tenant assignment."""
    ou = _semanticlayer_create_org_unit(tenant_a, "Financial Strategy")
    data = _semanticlayer_base_glossary_term_data(
        name="Customer Acquisition Cost",
        code="cac",
        steward=admin_user.pk,
        org_unit=ou.pk,
    )
    form = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BGLO-")
    assert instance.code == "cac"
    assert instance.steward == admin_user
    assert instance.org_unit == ou
    assert instance.certification_status == "draft"


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_scoped_querysets(
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
    glossary_term_a,
    glossary_term_b,
):
    """Verify BusinessGlossaryTermForm scopes steward, org_unit, and related_terms to self.tenant."""
    ou_a = _semanticlayer_create_org_unit(tenant_a, "Commercial Ops A")
    ou_b = _semanticlayer_create_org_unit(tenant_b, "Commercial Ops B")
    inactive_user_a = _semanticlayer_create_user(tenant_a, "inactive_steward", is_active=False)

    form = BusinessGlossaryTermForm(tenant=tenant_a)

    steward_qs = form.fields["steward"].queryset
    assert admin_user in steward_qs
    assert inactive_user_a not in steward_qs
    assert admin_user_b not in steward_qs

    ou_qs = form.fields["org_unit"].queryset
    assert ou_a in ou_qs
    assert ou_b not in ou_qs

    term_qs = form.fields["related_terms"].queryset
    assert glossary_term_a in term_qs
    assert glossary_term_b not in term_qs


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_scoped_querysets_bound_inactive_steward(tenant_a):
    """Verify bound inactive steward is preserved in queryset during term edit."""
    inactive_steward = _semanticlayer_create_user(tenant_a, "former_steward", is_active=False)
    term = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Legacy KPI Term",
        code="legacy_kpi_term",
        steward=inactive_steward,
        short_definition="Historical metric definition.",
    )
    form = BusinessGlossaryTermForm(instance=term, tenant=tenant_a)
    assert inactive_steward in form.fields["steward"].queryset


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_self_exclusion_in_related_terms(tenant_a, glossary_term_a):
    """Verify existing term instance is excluded from its own related_terms options."""
    sibling_term = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Sibling Metric",
        code="sibling_metric",
        short_definition="Sibling metric description.",
    )
    form = BusinessGlossaryTermForm(instance=glossary_term_a, tenant=tenant_a)
    related_qs = form.fields["related_terms"].queryset
    assert glossary_term_a not in related_qs
    assert sibling_term in related_qs


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_unscoped_tenant_querysets():
    """Verify unscoped initialization (tenant=None) yields empty querysets for BusinessGlossaryTermForm."""
    form = BusinessGlossaryTermForm()
    assert form.fields["steward"].queryset.count() == 0
    assert form.fields["org_unit"].queryset.count() == 0
    assert form.fields["related_terms"].queryset.count() == 0


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_reject_foreign_org_unit(tenant_a, tenant_b):
    """Verify reject_foreign rejects foreign tenant OrgUnit."""
    foreign_ou = _semanticlayer_create_org_unit(tenant_b, "Foreign Division")
    data = _semanticlayer_base_glossary_term_data(org_unit=foreign_ou.pk)

    form = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors

    form_wide = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    form_wide.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["org_unit"]


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_reject_foreign_steward(tenant_a, admin_user_b):
    """Verify reject_foreign rejects steward from a foreign tenant."""
    data = _semanticlayer_base_glossary_term_data(steward=admin_user_b.pk)

    form = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "steward" in form.errors

    form_wide = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    form_wide.fields["steward"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["steward"]


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_reject_foreign_related_terms(tenant_a, glossary_term_b):
    """Verify reject_foreign defense rejects related_terms belonging to foreign tenant."""
    data = _semanticlayer_base_glossary_term_data(related_terms=[glossary_term_b.pk])

    form = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "related_terms" in form.errors

    form_wide = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    form_wide.fields["related_terms"].queryset = BusinessGlossaryTerm.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["related_terms"]


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_duplicate_code_within_tenant_rejected(tenant_a, glossary_term_a):
    """Verify duplicate code in same tenant is rejected by TenantUniqueMixin."""
    data = _semanticlayer_base_glossary_term_data(
        name="Duplicate Glossary Term",
        code=glossary_term_a.code,
    )
    form = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.non_field_errors())


@pytest.mark.django_db
def test_semanticlayer_glossary_term_form_duplicate_code_different_tenant_allowed(tenant_a, glossary_term_b):
    """Verify same code is permitted across different tenants."""
    data = _semanticlayer_base_glossary_term_data(
        name="Tenant A Reusing Term B Code",
        code=glossary_term_b.code,
    )
    form = BusinessGlossaryTermForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# ===========================================================================
# 4. BusinessGlossaryTermCertificationForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_glossary_cert_form_valid_statuses():
    """Verify BusinessGlossaryTermCertificationForm accepts valid status transitions with notes."""
    valid_statuses = ["draft", "in_review", "certified", "deprecated"]
    for status in valid_statuses:
        form = BusinessGlossaryTermCertificationForm(data={
            "certification_status": status,
            "certification_notes": f"Transitioned to {status} by data governance council.",
        })
        assert form.is_valid(), f"Failed for status {status}: {form.errors}"
        assert form.cleaned_data["certification_status"] == status
        assert "governance council" in form.cleaned_data["certification_notes"]


@pytest.mark.django_db
def test_semanticlayer_glossary_cert_form_invalid_status_rejected():
    """Verify BusinessGlossaryTermCertificationForm rejects unknown status values."""
    form = BusinessGlossaryTermCertificationForm(data={
        "certification_status": "bogus_status",
        "certification_notes": "Attempting invalid choice",
    })
    assert not form.is_valid()
    assert "certification_status" in form.errors


@pytest.mark.django_db
def test_semanticlayer_glossary_cert_form_notes_optional():
    """Verify certification_notes is optional on BusinessGlossaryTermCertificationForm."""
    form = BusinessGlossaryTermCertificationForm(data={
        "certification_status": "certified",
        "certification_notes": "",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["certification_notes"] == ""


# ===========================================================================
# 5. CalculatedMeasureForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_system_field_exclusions(tenant_a):
    """Verify CalculatedMeasureForm excludes tenant, number, created_at, updated_at."""
    form = CalculatedMeasureForm(tenant=tenant_a)
    excluded = ["tenant", "number", "created_at", "updated_at"]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from CalculatedMeasureForm"


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_valid_creation(tenant_a, semantic_model_a, glossary_term_a):
    """Verify valid CalculatedMeasureForm submission persists measure with BCMS prefix."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_a,
        glossary=glossary_term_a,
        name="Net Invoice Sum",
        code="net_invoice_sum",
        aggregation_type="sum",
        source_column="net_amount",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BCMS-")
    assert instance.code == "net_invoice_sum"
    assert instance.semantic_model == semantic_model_a
    assert instance.glossary_term == glossary_term_a
    assert instance.aggregation_type == "sum"
    assert instance.source_column == "net_amount"


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_scoped_querysets(
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
    glossary_term_a,
    glossary_term_b,
):
    """Verify CalculatedMeasureForm scopes semantic_model and glossary_term querysets to self.tenant."""
    form = CalculatedMeasureForm(tenant=tenant_a)

    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs

    gt_qs = form.fields["glossary_term"].queryset
    assert glossary_term_a in gt_qs
    assert glossary_term_b not in gt_qs


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_reject_foreign_semantic_model(
    tenant_a,
    semantic_model_b,
):
    """Verify reject_foreign rejects semantic_model belonging to another tenant."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_b,
        name="Measure on Foreign Model",
        code="foreign_model_measure",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors

    form_wide = CalculatedMeasureForm(data=data, tenant=tenant_a)
    form_wide.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["semantic_model"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_reject_foreign_glossary_term(
    tenant_a,
    semantic_model_a,
    glossary_term_b,
):
    """Verify reject_foreign rejects glossary_term belonging to another tenant."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_a,
        glossary=glossary_term_b,
        name="Measure with Foreign Term",
        code="foreign_term_measure",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "glossary_term" in form.errors

    form_wide = CalculatedMeasureForm(data=data, tenant=tenant_a)
    form_wide.fields["glossary_term"].queryset = BusinessGlossaryTerm.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["glossary_term"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_formula_requires_expression(tenant_a, semantic_model_a):
    """Verify aggregation_type='formula' requires formula_expression."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_a,
        name="Custom Ratio Measure",
        code="custom_ratio_measure",
        aggregation_type="formula",
        formula_expression="",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "formula_expression" in form.errors
    assert "A calculation formula is required when aggregation type is set to Formula." in form.errors["formula_expression"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_formula_with_expression_valid(tenant_a, semantic_model_a):
    """Verify aggregation_type='formula' is valid when formula_expression is provided."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_a,
        name="Valid Custom Formula Measure",
        code="valid_custom_formula",
        aggregation_type="formula",
        source_column="",
        formula_expression="([revenue] - [cogs]) / [revenue] * 100",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_standard_agg_requires_source_or_formula(
    tenant_a,
    semantic_model_a,
):
    """Verify standard aggregation (e.g. sum) requires either source_column or formula_expression."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_a,
        name="Missing Target Column",
        code="missing_target_col",
        aggregation_type="sum",
        source_column="",
        formula_expression="",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "source_column" in form.errors
    assert "Specify either a source column or formula expression." in form.errors["source_column"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_standard_agg_with_source_valid(tenant_a, semantic_model_a):
    """Verify standard aggregation with source_column passes validation."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_a,
        name="Sum Amount Measure",
        code="sum_amount_measure",
        aggregation_type="sum",
        source_column="line_amount",
        formula_expression="",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_standard_agg_with_formula_valid(tenant_a, semantic_model_a):
    """Verify standard aggregation with formula_expression instead of source_column passes validation."""
    data = _semanticlayer_base_calculated_measure_data(
        model=semantic_model_a,
        name="Agg With Formula",
        code="agg_with_formula",
        aggregation_type="sum",
        source_column="",
        formula_expression="[unit_price] * [quantity_ordered]",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_duplicate_code_within_model_rejected(
    tenant_a,
    calculated_measure_a,
):
    """Verify duplicate code within same semantic_model is rejected."""
    data = _semanticlayer_base_calculated_measure_data(
        model=calculated_measure_a.semantic_model,
        name="Duplicate Measure Code",
        code=calculated_measure_a.code,
        aggregation_type="sum",
        source_column="amount",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.non_field_errors())


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_form_duplicate_code_different_model_allowed(
    tenant_a,
    calculated_measure_a,
    warehouse_table_a,
    data_mart_a,
):
    """Verify same measure code is accepted under a different semantic_model within the same tenant."""
    second_model = SemanticModel.objects.create(
        tenant=tenant_a,
        warehouse_table=warehouse_table_a,
        data_mart=data_mart_a,
        name="Second Model",
        code="second_model_code",
    )
    data = _semanticlayer_base_calculated_measure_data(
        model=second_model,
        name="Second Model Measure Reusing Code",
        code=calculated_measure_a.code,
        aggregation_type="sum",
        source_column="amount",
    )
    form = CalculatedMeasureForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


# ===========================================================================
# 6. DrillHierarchyForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_system_field_exclusions(tenant_a):
    """Verify DrillHierarchyForm excludes tenant, number, created_at, updated_at."""
    form = DrillHierarchyForm(tenant=tenant_a)
    excluded = ["tenant", "number", "created_at", "updated_at"]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from DrillHierarchyForm"


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_valid_creation(tenant_a, semantic_model_a):
    """Verify valid DrillHierarchyForm saves with BDHI prefix and parsed levels_json."""
    data = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        name="Geographic Hierarchy",
        code="geo_hierarchy",
        hierarchy_type="geography",
        levels_json_raw=json.dumps([
            {"level": 1, "name": "Region", "column": "region_name"},
            {"level": 2, "name": "Country", "column": "country_iso"},
            {"level": 3, "name": "State", "column": "state_province"},
        ]),
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("BDHI-")
    assert instance.code == "geo_hierarchy"
    assert instance.semantic_model == semantic_model_a
    assert instance.hierarchy_type == "geography"
    assert len(instance.levels_json) == 3
    assert instance.levels_json[0] == {"level": 1, "name": "Region", "column": "region_name"}


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_scoped_querysets(
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
):
    """Verify DrillHierarchyForm scopes semantic_model queryset to self.tenant."""
    form = DrillHierarchyForm(tenant=tenant_a)
    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_reject_foreign_semantic_model(
    tenant_a,
    semantic_model_b,
):
    """Verify reject_foreign defense rejects semantic_model from another tenant."""
    data = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_b,
        name="Foreign Model Hierarchy",
        code="foreign_model_hierarchy",
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors

    form_wide = DrillHierarchyForm(data=data, tenant=tenant_a)
    form_wide.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["semantic_model"]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_levels_json_empty_allowed(tenant_a, semantic_model_a):
    """Verify blank or whitespace levels_json_raw parses to an empty list."""
    data = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        levels_json_raw="   ",
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.levels_json == []


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_levels_json_invalid_json_rejected(tenant_a, semantic_model_a):
    """Verify malformed JSON syntax in levels_json_raw raises ValidationError."""
    data = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        levels_json_raw="{not-valid-json",
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "levels_json_raw" in form.errors
    assert "Invalid JSON format" in form.errors["levels_json_raw"][0]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_levels_json_non_list_rejected(tenant_a, semantic_model_a):
    """Verify JSON that parses to a dict or primitive rather than list raises ValidationError."""
    data = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        levels_json_raw='{"level": 1, "name": "Year", "column": "year"}',
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "levels_json_raw" in form.errors
    assert "Hierarchy levels must be a JSON array of level objects." in form.errors["levels_json_raw"][0]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_levels_json_non_dict_element_rejected(tenant_a, semantic_model_a):
    """Verify JSON array containing primitive strings/numbers raises ValidationError."""
    data = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        levels_json_raw='["Year", "Quarter", "Month"]',
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "levels_json_raw" in form.errors
    assert "Item 1 must be an object with 'name' and 'column' keys." in form.errors["levels_json_raw"][0]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_levels_json_missing_keys_rejected(tenant_a, semantic_model_a):
    """Verify array elements missing 'name' or 'column' raise ValidationError."""
    # Missing column key
    data_no_col = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        levels_json_raw='[{"name": "Fiscal Year"}]',
    )
    form_no_col = DrillHierarchyForm(data=data_no_col, tenant=tenant_a)
    assert not form_no_col.is_valid()
    assert "levels_json_raw" in form_no_col.errors
    assert "missing required 'name' or 'column' keys." in form_no_col.errors["levels_json_raw"][0]

    # Missing name key
    data_no_name = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        levels_json_raw='[{"column": "fiscal_year"}]',
    )
    form_no_name = DrillHierarchyForm(data=data_no_name, tenant=tenant_a)
    assert not form_no_name.is_valid()
    assert "levels_json_raw" in form_no_name.errors
    assert "missing required 'name' or 'column' keys." in form_no_name.errors["levels_json_raw"][0]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_initial_value_on_edit(drill_hierarchy_a):
    """Verify initial value of levels_json_raw is populated from instance.levels_json."""
    form = DrillHierarchyForm(instance=drill_hierarchy_a, tenant=drill_hierarchy_a.tenant)
    initial_raw = form.fields["levels_json_raw"].initial
    assert initial_raw is not None
    parsed = json.loads(initial_raw)
    assert parsed == drill_hierarchy_a.levels_json


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_save_commit_false(tenant_a, semantic_model_a):
    """Verify form.save(commit=False) assigns parsed levels_json without persisting to database."""
    levels = [{"level": 1, "name": "Department", "column": "dept_id"}]
    data = _semanticlayer_base_drill_hierarchy_data(
        model=semantic_model_a,
        name="Org Drill",
        code="org_drill",
        levels_json_raw=json.dumps(levels),
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    assert instance.levels_json == levels
    assert instance.pk is None


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_duplicate_code_within_model_rejected(
    tenant_a,
    drill_hierarchy_a,
):
    """Verify duplicate hierarchy code for the same semantic_model is rejected."""
    data = _semanticlayer_base_drill_hierarchy_data(
        model=drill_hierarchy_a.semantic_model,
        name="Duplicate Hierarchy Code",
        code=drill_hierarchy_a.code,
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in str(err) for err in form.non_field_errors())


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_form_duplicate_code_different_model_allowed(
    tenant_a,
    drill_hierarchy_a,
    warehouse_table_a,
    data_mart_a,
):
    """Verify identical hierarchy code is accepted under a distinct semantic_model."""
    other_model = SemanticModel.objects.create(
        tenant=tenant_a,
        warehouse_table=warehouse_table_a,
        data_mart=data_mart_a,
        name="Other Semantic Model",
        code="other_semantic_model",
    )
    data = _semanticlayer_base_drill_hierarchy_data(
        model=other_model,
        name="Other Model Reusing Code",
        code=drill_hierarchy_a.code,
    )
    form = DrillHierarchyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
