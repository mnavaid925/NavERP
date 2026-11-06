"""Unit tests for Sub-module 10.10 Self-Service & Ad-Hoc Analytics forms.

Forms covered:
- AdHocQueryForm & AdHocQueryComposerForm
- AdHocCalculatedFieldForm
- DataBlendDefinitionForm
- SavedAnalysisViewForm & SavedAnalysisViewShareForm
"""
import pytest

from apps.bi.forms.SelfServiceAnalytics import (
    AdHocCalculatedFieldForm,
    AdHocQueryComposerForm,
    AdHocQueryForm,
    DataBlendDefinitionForm,
    SavedAnalysisViewForm,
    SavedAnalysisViewShareForm,
)


# ---------------------------------------------------------------------------
# AdHocQueryForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_query_form_valid(tenant_a):
    form = AdHocQueryForm(
        data={
            "name": "Q4 Gross Margin Analysis",
            "source_type": "semantic_model",
            "visualization_type": "table",
            "row_limit": 500,
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.slug == "q4-gross-margin-analysis"


@pytest.mark.django_db
def test_selfserviceanalytics_query_form_missing_required(tenant_a):
    form = AdHocQueryForm(
        data={
            "description": "Missing name should fail",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_selfserviceanalytics_query_form_reject_foreign(tenant_a, semantic_model_b):
    form = AdHocQueryForm(
        data={
            "name": "Acme Query Foreign SModel",
            "source_type": "semantic_model",
            "semantic_model": semantic_model_b.pk,
            "visualization_type": "table",
            "row_limit": 500,
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "semantic_model" in form.errors


@pytest.mark.django_db
def test_selfserviceanalytics_query_composer_form_valid(tenant_a):
    form = AdHocQueryComposerForm(
        data={
            "name": "Composer Visual Exploration",
            "source_type": "semantic_model",
            "visualization_type": "bar_chart",
            "row_limit": 250,
            "status": "active",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


# ---------------------------------------------------------------------------
# AdHocCalculatedFieldForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_form_valid(tenant_a, adhoc_query_a):
    form = AdHocCalculatedFieldForm(
        data={
            "query": adhoc_query_a.pk,
            "display_label": "Net Operating Margin",
            "formula_expression": "([revenue] - [operating_cost]) / [revenue] * 100",
            "return_type": "percentage",
            "aggregation_mode": "formula",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.field_name == "net_operating_margin"


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_form_unbalanced_brackets(tenant_a, adhoc_query_a):
    form = AdHocCalculatedFieldForm(
        data={
            "query": adhoc_query_a.pk,
            "display_label": "Broken Bracket Formula",
            "formula_expression": "[revenue - [cost]",
            "return_type": "currency",
            "aggregation_mode": "formula",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "formula_expression" in form.errors
    assert "Unbalanced brackets" in str(form.errors["formula_expression"])


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_form_unbalanced_parentheses(tenant_a, adhoc_query_a):
    form = AdHocCalculatedFieldForm(
        data={
            "query": adhoc_query_a.pk,
            "display_label": "Broken Paren Formula",
            "formula_expression": "(([revenue] - [cost]) * 100",
            "return_type": "currency",
            "aggregation_mode": "formula",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "formula_expression" in form.errors
    assert "Unbalanced parentheses" in str(form.errors["formula_expression"])


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_form_reject_foreign(tenant_a, adhoc_query_b):
    form = AdHocCalculatedFieldForm(
        data={
            "query": adhoc_query_b.pk,
            "display_label": "Cross-Tenant Query Calc Field",
            "formula_expression": "[rev] - [cogs]",
            "return_type": "currency",
            "aggregation_mode": "formula",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "query" in form.errors


# ---------------------------------------------------------------------------
# DataBlendDefinitionForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_blend_form_valid(tenant_a):
    form = DataBlendDefinitionForm(
        data={
            "name": "Opportunities and Orders Blend",
            "primary_source_type": "semantic_model",
            "secondary_source_type": "warehouse_table",
            "join_type": "left_outer",
            "cardinality": "many_to_one",
            "collision_resolution": "prefix_secondary",
            "join_keys_mapping_json": '[{"primary_field": "opp_id", "secondary_field": "id"}]',
            "status": "active",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.slug == "opportunities-and-orders-blend"


@pytest.mark.django_db
def test_selfserviceanalytics_blend_form_invalid_json(tenant_a):
    form = DataBlendDefinitionForm(
        data={
            "name": "Invalid Blend JSON",
            "primary_source_type": "semantic_model",
            "secondary_source_type": "warehouse_table",
            "join_type": "left_outer",
            "cardinality": "many_to_one",
            "join_keys_mapping_json": "NOT VALID JSON {[{",
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "join_keys_mapping_json" in form.errors


# ---------------------------------------------------------------------------
# SavedAnalysisViewForm & ShareForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_form_valid(tenant_a, adhoc_query_a):
    form = SavedAnalysisViewForm(
        data={
            "name": "Executive Revenue Run Rate",
            "query": adhoc_query_a.pk,
            "sharing_scope": "tenant_public",
            "is_template": True,
            "is_favorite": True,
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.slug == "executive-revenue-run-rate"


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_form_reject_foreign(tenant_a, adhoc_query_b):
    form = SavedAnalysisViewForm(
        data={
            "name": "Foreign Query Saved View",
            "query": adhoc_query_b.pk,
            "sharing_scope": "personal",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "query" in form.errors


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_share_form_valid(tenant_a, saved_analysis_view_a):
    form = SavedAnalysisViewShareForm(
        data={
            "sharing_scope": "personal",
        },
        instance=saved_analysis_view_a,
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.sharing_scope == "personal"
