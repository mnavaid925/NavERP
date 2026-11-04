"""Unit tests for Sub-module 10.4 Semantic Layer models.

Models covered:
- SemanticModel (BSMD)
- BusinessGlossaryTerm (BGLO)
- CalculatedMeasure (BCMS)
- DrillHierarchy (BDHI)
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.bi.models import (
    BusinessGlossaryTerm,
    CalculatedMeasure,
    DataMart,
    DrillHierarchy,
    LakehouseZone,
    SemanticModel,
    WarehouseStoragePolicy,
    WarehouseTable,
)


# ---------------------------------------------------------------------------
# Fixture Bridges (to support semantic_model_a when conftest expects warehouse_table/data_mart)
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
# Module Helpers
# ---------------------------------------------------------------------------


def _semanticlayer_extract_choice_keys(choices_list):
    """Helper to extract keys from Django choices tuple/list."""
    return [c[0] for c in choices_list]


# ---------------------------------------------------------------------------
# 1. SemanticModel Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_semanticlayer_semantic_model_creation_and_prefix(tenant_a, admin_user):
    """Test SemanticModel creation, BSMD prefix, and string representation."""
    model = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Customer 360 Dimension",
        code="customer_360_dim",
        owner=admin_user,
    )
    assert model.NUMBER_PREFIX == "BSMD"
    assert model.number.startswith("BSMD-")
    assert str(model) == f"{model.name} ({model.number})"
    assert model.code == "customer_360_dim"
    assert model.tenant == tenant_a
    assert model.owner == admin_user


@pytest.mark.django_db
def test_semanticlayer_semantic_model_absolute_url(semantic_model_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/semantic/models/{semantic_model_a.pk}/"
    assert semantic_model_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_semanticlayer_semantic_model_defaults_and_fields(tenant_a):
    """Verify default field values for SemanticModel."""
    model = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Minimal Semantic Model",
        code="min_semantic_model",
    )
    assert model.model_type == "fact"
    assert model.warehouse_table is None
    assert model.data_mart is None
    assert model.primary_key_column == "id"
    assert model.natural_key_columns == ""
    assert model.grain_description == ""
    assert model.is_conformed_dimension is False
    assert model.scd_type == "type_1"
    assert model.is_virtual_view is False
    assert model.sql_definition == ""
    assert model.access_tier == "department"
    assert model.certification_status == "draft"
    assert model.certified_by is None
    assert model.certified_at is None
    assert model.certification_notes == ""
    assert model.source_fingerprint == ""
    assert model.last_introspected_at is None
    assert model.owner is None
    assert model.description == ""
    assert model.is_active is True
    assert model.created_at is not None
    assert model.updated_at is not None


@pytest.mark.django_db
def test_semanticlayer_semantic_model_choices_contract():
    """Verify choice keys on SemanticModel match specification."""
    model_types = _semanticlayer_extract_choice_keys(SemanticModel.MODEL_TYPE_CHOICES)
    assert model_types == [
        "fact",
        "dimension",
        "bridge",
        "virtual_view",
        "reusable_dataset",
    ]

    scd_types = _semanticlayer_extract_choice_keys(SemanticModel.SCD_TYPE_CHOICES)
    assert scd_types == ["type_0", "type_1", "type_2", "type_3"]

    access_tiers = _semanticlayer_extract_choice_keys(SemanticModel.ACCESS_TIER_CHOICES)
    assert access_tiers == ["public", "department", "restricted"]

    cert_statuses = _semanticlayer_extract_choice_keys(SemanticModel.CERTIFICATION_STATUS_CHOICES)
    assert cert_statuses == ["draft", "in_review", "certified", "deprecated"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_unique_constraints(tenant_a, tenant_b):
    """Verify UniqueConstraints on [tenant, code] and [tenant, number] for SemanticModel."""
    m1 = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Sales Invoicing Model",
        code="sales_invoicing",
    )

    # Duplicate code in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        SemanticModel.objects.create(
            tenant=tenant_a,
            name="Another Sales Invoicing",
            code="sales_invoicing",
        )

    # Same code in different tenant must succeed
    m_b = SemanticModel.objects.create(
        tenant=tenant_b,
        name="Globex Sales Invoicing",
        code="sales_invoicing",
    )
    assert m_b.pk != m1.pk
    assert m_b.tenant == tenant_b

    # Duplicate number in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        SemanticModel.objects.create(
            tenant=tenant_a,
            name="Manual Number Collision",
            code="manual_num_collision",
            number=m1.number,
        )


# ---------------------------------------------------------------------------
# 2. BusinessGlossaryTerm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_semanticlayer_glossary_term_creation_and_prefix(tenant_a, admin_user):
    """Test BusinessGlossaryTerm creation, BGLO prefix, and string representation."""
    term = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Customer Acquisition Cost",
        code="cac",
        short_definition="Total sales & marketing cost divided by new customers acquired",
        steward=admin_user,
    )
    assert term.NUMBER_PREFIX == "BGLO"
    assert term.number.startswith("BGLO-")
    assert str(term) == f"{term.name} ({term.number})"
    assert term.code == "cac"
    assert term.tenant == tenant_a
    assert term.steward == admin_user


@pytest.mark.django_db
def test_semanticlayer_glossary_term_absolute_url(glossary_term_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/semantic/glossary/{glossary_term_a.pk}/"
    assert glossary_term_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_semanticlayer_glossary_term_defaults_and_fields(tenant_a):
    """Verify default field values for BusinessGlossaryTerm."""
    term = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Average Order Value",
        code="aov",
        short_definition="Total revenue divided by order count",
    )
    assert term.domain_category == "finance"
    assert term.full_definition == ""
    assert term.calculation_rule == ""
    assert term.synonyms == ""
    assert term.steward is None
    assert term.org_unit is None
    assert term.certification_status == "draft"
    assert term.certified_by is None
    assert term.certified_at is None
    assert term.certification_notes == ""
    assert term.is_active is True
    assert term.created_at is not None
    assert term.updated_at is not None


@pytest.mark.django_db
def test_semanticlayer_glossary_term_choices_contract():
    """Verify choice keys on BusinessGlossaryTerm match specification."""
    domain_categories = _semanticlayer_extract_choice_keys(BusinessGlossaryTerm.DOMAIN_CATEGORY_CHOICES)
    assert domain_categories == [
        "finance",
        "sales",
        "marketing",
        "hr",
        "supply_chain",
        "operations",
        "general",
    ]

    cert_statuses = _semanticlayer_extract_choice_keys(BusinessGlossaryTerm.CERTIFICATION_STATUS_CHOICES)
    assert cert_statuses == ["draft", "in_review", "certified", "deprecated"]


@pytest.mark.django_db
def test_semanticlayer_glossary_term_unique_constraints(tenant_a, tenant_b):
    """Verify UniqueConstraints on [tenant, code] and [tenant, number] for BusinessGlossaryTerm."""
    t1 = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Monthly Recurring Revenue",
        code="mrr",
        short_definition="Normalized monthly subscription revenue",
    )

    # Duplicate code in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        BusinessGlossaryTerm.objects.create(
            tenant=tenant_a,
            name="Duplicate MRR",
            code="mrr",
            short_definition="Duplicate definition",
        )

    # Same code in tenant_b must succeed
    t_b = BusinessGlossaryTerm.objects.create(
        tenant=tenant_b,
        name="Globex MRR",
        code="mrr",
        short_definition="Globex MRR definition",
    )
    assert t_b.pk != t1.pk
    assert t_b.tenant == tenant_b

    # Duplicate number in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        BusinessGlossaryTerm.objects.create(
            tenant=tenant_a,
            name="Number Collision Term",
            code="num_collision_term",
            short_definition="Collision test",
            number=t1.number,
        )


@pytest.mark.django_db
def test_semanticlayer_glossary_term_symmetrical_m2m(tenant_a):
    """Verify symmetrical ManyToMany relationship on related_terms."""
    term1 = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Gross Profit",
        code="gross_profit",
        short_definition="Revenue minus COGS",
    )
    term2 = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Gross Margin Percentage",
        code="gross_margin_pct",
        short_definition="Gross profit divided by revenue",
    )

    # Add relation from term1 -> term2
    term1.related_terms.add(term2)

    # Due to symmetrical=True, term2 must automatically have term1
    assert term2.related_terms.filter(pk=term1.pk).exists()
    assert term1.related_terms.filter(pk=term2.pk).exists()

    # Removing from term2 should remove from term1 symmetrically
    term2.related_terms.remove(term1)
    assert not term1.related_terms.filter(pk=term2.pk).exists()
    assert not term2.related_terms.filter(pk=term1.pk).exists()


# ---------------------------------------------------------------------------
# 3. CalculatedMeasure Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_creation_and_prefix(tenant_a, semantic_model_a, glossary_term_a):
    """Test CalculatedMeasure creation, BCMS prefix, and string representation."""
    measure = CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        glossary_term=glossary_term_a,
        name="Average Deal Size",
        code="avg_deal_size",
        aggregation_type="avg",
        source_column="deal_value",
    )
    assert measure.NUMBER_PREFIX == "BCMS"
    assert measure.number.startswith("BCMS-")
    assert str(measure) == f"{measure.name} ({measure.number})"
    assert measure.code == "avg_deal_size"
    assert measure.semantic_model == semantic_model_a
    assert measure.glossary_term == glossary_term_a


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_absolute_url(calculated_measure_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/semantic/measures/{calculated_measure_a.pk}/"
    assert calculated_measure_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_defaults_and_fields(tenant_a, semantic_model_a):
    """Verify default field values for CalculatedMeasure."""
    measure = CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        name="Orders Count",
        code="orders_count",
    )
    assert measure.glossary_term is None
    assert measure.aggregation_type == "sum"
    assert measure.source_column == ""
    assert measure.formula_expression == ""
    assert measure.filter_expression == ""
    assert measure.time_intelligence == "none"
    assert measure.format_string == "decimal"
    assert measure.display_units == "auto"
    assert measure.target_value is None
    assert measure.warning_threshold is None
    assert measure.critical_threshold is None
    assert measure.description == ""
    assert measure.is_active is True
    assert measure.created_at is not None
    assert measure.updated_at is not None


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_choices_contract():
    """Verify choice keys on CalculatedMeasure match specification."""
    agg_types = _semanticlayer_extract_choice_keys(CalculatedMeasure.AGGREGATION_TYPE_CHOICES)
    assert agg_types == [
        "sum",
        "avg",
        "count",
        "count_distinct",
        "min",
        "max",
        "formula",
    ]

    time_intelligences = _semanticlayer_extract_choice_keys(CalculatedMeasure.TIME_INTELLIGENCE_CHOICES)
    assert time_intelligences == [
        "none",
        "yoy_growth",
        "qtd",
        "ytd",
        "rolling_30d",
        "prior_period",
    ]

    format_strings = _semanticlayer_extract_choice_keys(CalculatedMeasure.FORMAT_STRING_CHOICES)
    assert format_strings == ["currency", "percentage", "integer", "decimal", "raw"]

    display_units = _semanticlayer_extract_choice_keys(CalculatedMeasure.DISPLAY_UNITS_CHOICES)
    assert display_units == ["auto", "none", "thousands", "millions", "billions"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_unique_constraints(tenant_a, tenant_b, semantic_model_a, semantic_model_b):
    """Verify UniqueConstraints on [tenant, semantic_model, code] and [tenant, number]."""
    meas1 = CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        name="Total Invoice Amount",
        code="total_inv_amount",
    )

    # Duplicate code on the SAME model in tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        CalculatedMeasure.objects.create(
            tenant=tenant_a,
            semantic_model=semantic_model_a,
            name="Duplicate Invoice Amount",
            code="total_inv_amount",
        )

    # Same code on a DIFFERENT model in tenant_a must succeed
    other_model_a = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Second Analytics Model",
        code="second_analytics_model",
    )
    meas_diff_model = CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=other_model_a,
        name="Other Model Invoice Amount",
        code="total_inv_amount",
    )
    assert meas_diff_model.pk != meas1.pk

    # Same code in tenant_b on semantic_model_b must succeed
    meas_b = CalculatedMeasure.objects.create(
        tenant=tenant_b,
        semantic_model=semantic_model_b,
        name="Globex Invoice Amount",
        code="total_inv_amount",
    )
    assert meas_b.pk != meas1.pk
    assert meas_b.tenant == tenant_b

    # Duplicate number in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        CalculatedMeasure.objects.create(
            tenant=tenant_a,
            semantic_model=semantic_model_a,
            name="Number Collision Measure",
            code="num_collision_measure",
            number=meas1.number,
        )


# ---------------------------------------------------------------------------
# 4. DrillHierarchy Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_creation_and_prefix(tenant_a, semantic_model_a):
    """Test DrillHierarchy creation, BDHI prefix, and string representation."""
    hierarchy = DrillHierarchy.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        name="Regional Geography Hierarchy",
        code="regional_geo_hierarchy",
        hierarchy_type="geography",
        levels_json=[
            {"level": 1, "name": "Global Region", "column": "global_region"},
            {"level": 2, "name": "Country Code", "column": "country_code"},
        ],
    )
    assert hierarchy.NUMBER_PREFIX == "BDHI"
    assert hierarchy.number.startswith("BDHI-")
    assert str(hierarchy) == f"{hierarchy.name} ({hierarchy.number})"
    assert hierarchy.code == "regional_geo_hierarchy"
    assert hierarchy.semantic_model == semantic_model_a


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_absolute_url(drill_hierarchy_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/semantic/hierarchies/{drill_hierarchy_a.pk}/"
    assert drill_hierarchy_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_defaults_and_fields(tenant_a, semantic_model_a):
    """Verify default field values for DrillHierarchy."""
    hierarchy = DrillHierarchy.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        name="Default Time Hierarchy",
        code="default_time_hierarchy",
    )
    assert hierarchy.hierarchy_type == "time"
    assert hierarchy.levels_json == []
    assert hierarchy.primary_drill_path is True
    assert hierarchy.description == ""
    assert hierarchy.is_active is True
    assert hierarchy.created_at is not None
    assert hierarchy.updated_at is not None


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_choices_contract():
    """Verify choice keys on DrillHierarchy match specification."""
    hierarchy_types = _semanticlayer_extract_choice_keys(DrillHierarchy.HIERARCHY_TYPE_CHOICES)
    assert hierarchy_types == [
        "time",
        "geography",
        "organizational",
        "product",
        "custom",
    ]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_unique_constraints(tenant_a, tenant_b, semantic_model_a, semantic_model_b):
    """Verify UniqueConstraints on [tenant, semantic_model, code] and [tenant, number]."""
    dh1 = DrillHierarchy.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        name="Calendar Hierarchy",
        code="calendar_hierarchy",
    )

    # Duplicate code on the SAME model in tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        DrillHierarchy.objects.create(
            tenant=tenant_a,
            semantic_model=semantic_model_a,
            name="Duplicate Calendar Hierarchy",
            code="calendar_hierarchy",
        )

    # Same code on a DIFFERENT model in tenant_a must succeed
    other_model_a = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Different Analytics Model",
        code="diff_analytics_model",
    )
    dh_diff_model = DrillHierarchy.objects.create(
        tenant=tenant_a,
        semantic_model=other_model_a,
        name="Other Model Calendar",
        code="calendar_hierarchy",
    )
    assert dh_diff_model.pk != dh1.pk

    # Same code in tenant_b on semantic_model_b must succeed
    dh_b = DrillHierarchy.objects.create(
        tenant=tenant_b,
        semantic_model=semantic_model_b,
        name="Globex Calendar Hierarchy",
        code="calendar_hierarchy",
    )
    assert dh_b.pk != dh1.pk
    assert dh_b.tenant == tenant_b

    # Duplicate number in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        DrillHierarchy.objects.create(
            tenant=tenant_a,
            semantic_model=semantic_model_a,
            name="Number Collision Hierarchy",
            code="num_collision_hierarchy",
            number=dh1.number,
        )


# ---------------------------------------------------------------------------
# 5. Foreign Key Cascades and Cross-Model Relations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_semanticlayer_relations_model_to_measures_cascade(tenant_a):
    """Verify model.measures related_name accessor and CASCADE deletion."""
    model = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Cascade Test Model Measures",
        code="cascade_test_model_meas",
    )
    m1 = CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=model,
        name="Measure Alpha",
        code="meas_alpha",
    )
    m2 = CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=model,
        name="Measure Beta",
        code="meas_beta",
    )

    # Test reverse relationship accessor
    measures = model.measures.all()
    assert measures.count() == 2
    assert m1 in measures
    assert m2 in measures

    # Delete parent model -> child measures must be CASCADE deleted
    model.delete()
    assert not CalculatedMeasure.objects.filter(pk__in=[m1.pk, m2.pk]).exists()


@pytest.mark.django_db
def test_semanticlayer_relations_model_to_drill_hierarchies_cascade(tenant_a):
    """Verify model.drill_hierarchies related_name accessor and CASCADE deletion."""
    model = SemanticModel.objects.create(
        tenant=tenant_a,
        name="Cascade Test Model Hierarchies",
        code="cascade_test_model_hier",
    )
    dh1 = DrillHierarchy.objects.create(
        tenant=tenant_a,
        semantic_model=model,
        name="Hierarchy One",
        code="hier_one",
    )
    dh2 = DrillHierarchy.objects.create(
        tenant=tenant_a,
        semantic_model=model,
        name="Hierarchy Two",
        code="hier_two",
    )

    # Test reverse relationship accessor
    hierarchies = model.drill_hierarchies.all()
    assert hierarchies.count() == 2
    assert dh1 in hierarchies
    assert dh2 in hierarchies

    # Delete parent model -> child hierarchies must be CASCADE deleted
    model.delete()
    assert not DrillHierarchy.objects.filter(pk__in=[dh1.pk, dh2.pk]).exists()


@pytest.mark.django_db
def test_semanticlayer_relations_glossary_term_to_measures_set_null(tenant_a, semantic_model_a):
    """Verify term.measures reverse accessor and on_delete=SET_NULL on glossary_term deletion."""
    term = BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Churn Rate Definition",
        code="churn_rate_def",
        short_definition="Standard definition of churn",
    )
    meas = CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        glossary_term=term,
        name="Monthly Churn Rate Measure",
        code="monthly_churn_rate_meas",
    )

    # Verify reverse relationship accessor
    assert term.measures.filter(pk=meas.pk).exists()

    # Deleting the glossary term must NOT delete the measure; FK is set to NULL
    term.delete()
    meas.refresh_from_db()
    assert meas.glossary_term is None
    assert CalculatedMeasure.objects.filter(pk=meas.pk).exists()


@pytest.mark.django_db
def test_semanticlayer_relations_warehouse_table_and_data_mart_set_null(tenant_a, admin_user):
    """Verify on_delete=SET_NULL on warehouse_table and data_mart deletion."""
    mart = DataMart.objects.create(
        tenant=tenant_a,
        name="Temp Finance Mart",
        code="temp_fin_mart",
        owner=admin_user,
    )
    zone = LakehouseZone.objects.create(
        tenant=tenant_a,
        name="Temp Gold Zone",
        code="temp_gold_zone",
        zone_type="gold",
        storage_backend="internal_db",
        base_uri_path="/tmp/gold",
    )
    policy = WarehouseStoragePolicy.objects.create(
        tenant=tenant_a,
        name="Temp Policy",
    )
    table = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=zone,
        storage_policy=policy,
        data_mart=mart,
        name="Temp Ledger Fact",
        table_name="temp_fact_ledger",
    )

    model = SemanticModel.objects.create(
        tenant=tenant_a,
        warehouse_table=table,
        data_mart=mart,
        name="Temp Ledger Analytics",
        code="temp_ledger_analytics",
    )

    # Verify reverse relationships
    assert table.semantic_models.filter(pk=model.pk).exists()
    assert mart.semantic_models.filter(pk=model.pk).exists()

    # Deleting table sets warehouse_table to NULL
    table.delete()
    model.refresh_from_db()
    assert model.warehouse_table is None
    assert model.data_mart == mart

    # Deleting mart sets data_mart to NULL
    mart.delete()
    model.refresh_from_db()
    assert model.data_mart is None
    assert SemanticModel.objects.filter(pk=model.pk).exists()


# ---------------------------------------------------------------------------
# 6. Meta Table Names, Ordering, and Indexes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_semanticlayer_meta_table_names_and_ordering():
    """Verify metadata table names and ordering for all 4 models."""
    assert SemanticModel._meta.db_table == "bi_semantic_model"
    assert SemanticModel._meta.ordering == ["-created_at"]

    assert BusinessGlossaryTerm._meta.db_table == "bi_business_glossary_term"
    assert BusinessGlossaryTerm._meta.ordering == ["domain_category", "name"]

    assert CalculatedMeasure._meta.db_table == "bi_calculated_measure"
    assert CalculatedMeasure._meta.ordering == ["semantic_model", "name"]

    assert DrillHierarchy._meta.db_table == "bi_drill_hierarchy"
    assert DrillHierarchy._meta.ordering == ["semantic_model", "name"]
