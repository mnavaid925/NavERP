"""Unit tests for Sub-module 10.14 AI & Augmented Analytics forms.

Forms covered:
- AugmentedInsightForm (AugmentedInsight)
- SmartDataPrepSuggestionForm (SmartDataPrepSuggestion)
- TextSentimentAnalysisForm (TextSentimentAnalysis)
- AnalyticsRecommendationForm (AnalyticsRecommendation)
"""
from decimal import Decimal

import pytest
from django import forms

from apps.bi.forms import (
    AnalyticsRecommendationForm,
    AugmentedInsightForm,
    SmartDataPrepSuggestionForm,
    TextSentimentAnalysisForm,
)
from apps.bi.models import (
    AnalyticsRecommendation,
    AugmentedInsight,
    ReportDefinition,
    SmartDataPrepSuggestion,
    TextSentimentAnalysis,
)
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party


# ---------------------------------------------------------------------------
# Module-level helpers (prefixed with _aiaugmentedanalytics_forms_*)
# ---------------------------------------------------------------------------


def _aiaugmentedanalytics_forms_create_party(tenant, name="Test Party"):
    """Helper to create a tenant-scoped Party record."""
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _aiaugmentedanalytics_forms_create_org_unit(tenant, name="Test Org Unit"):
    """Helper to create a tenant-scoped OrgUnit record."""
    return OrgUnit.objects.create(tenant=tenant, name=name, kind="department")


def _aiaugmentedanalytics_forms_create_report(tenant, name="Test Report", slug="test-report"):
    """Helper to create a tenant-scoped ReportDefinition record."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        slug=slug,
        category="finance",
        report_type="standard_tabular",
    )


def _aiaugmentedanalytics_forms_valid_insight_data(
    semantic_model=None, kpi_definition=None, warehouse_table=None
):
    """Helper returning a valid data payload for AugmentedInsightForm."""
    data = {
        "title": "Gross Margin Compression Q4",
        "insight_type": "key_driver",
        "metric_name": "Gross Margin %",
        "baseline_value": "42.5000",
        "observed_value": "38.1000",
        "variance_percentage": "-10.35",
        "impact_direction": "unfavorable",
        "severity": "high",
        "confidence_score": "92.50",
        "narrative_summary": "Gross margin contracted by 10.35% due to component cost inflation.",
        "dimension_name": "Product Category",
        "dimension_value": "Hardware",
        "status": "new",
        "action_notes": "Procurement team reviewing vendor contracts.",
    }
    if semantic_model:
        data["semantic_model"] = semantic_model.pk
    if kpi_definition:
        data["kpi_definition"] = kpi_definition.pk
    if warehouse_table:
        data["warehouse_table"] = warehouse_table.pk
    return data


def _aiaugmentedanalytics_forms_valid_dataprep_data(target_table, related_table=None):
    """Helper returning a valid data payload for SmartDataPrepSuggestionForm."""
    data = {
        "target_table": target_table.pk,
        "target_column": "customer_id",
        "suggestion_type": "join_relationship",
        "related_column": "id",
        "confidence_score": "95.00",
        "rationale": "Suggested foreign key relationship between sales fact and customer dimension.",
        "status": "pending",
        "review_notes": "Awaiting schema approval from data architect.",
    }
    if related_table:
        data["related_table"] = related_table.pk
    return data


def _aiaugmentedanalytics_forms_valid_sentiment_data(linked_party=None, linked_org_unit=None):
    """Helper returning a valid data payload for TextSentimentAnalysisForm."""
    data = {
        "source_type": "customer_review",
        "source_reference": "REV-2027-0012",
        "text_content": "The platform analytics dashboard is exceptionally fast and intuitive to use.",
        "language": "en",
        "sentiment_category": "positive",
        "polarity_score": "0.85",
        "subjectivity_score": "0.60",
    }
    if linked_party:
        data["linked_party"] = linked_party.pk
    if linked_org_unit:
        data["linked_org_unit"] = linked_org_unit.pk
    return data


def _aiaugmentedanalytics_forms_valid_recommendation_data(
    user, dashboard=None, report=None, kpi=None, semantic_model=None
):
    """Helper returning a valid data payload for AnalyticsRecommendationForm."""
    data = {
        "user": user.pk,
        "recommendation_type": "dashboard",
        "target_title": "Executive Revenue Performance Dashboard",
        "target_url": "/bi/dashboards/1/",
        "reason": "role_relevance",
        "rationale_text": "Highly accessed by executives in your department during month-end close.",
        "affinity_score": "94.50",
        "status": "active",
    }
    if dashboard:
        data["dashboard"] = dashboard.pk
    if report:
        data["report"] = report.pk
    if kpi:
        data["kpi"] = kpi.pk
    if semantic_model:
        data["semantic_model"] = semantic_model.pk
    return data


# ===========================================================================
# 1. AugmentedInsightForm Tests (BAIN)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_system_field_exclusions():
    """Verify system fields (tenant, number, created_by, timestamps, driver_decomposition) are excluded from Meta.fields."""
    form = AugmentedInsightForm()
    excluded_fields = [
        "tenant",
        "number",
        "created_by",
        "driver_decomposition",
        "created_at",
        "updated_at",
    ]
    for field in excluded_fields:
        assert field not in form.fields, f"Security violation: {field} exposed in AugmentedInsightForm"


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_tenant_scoping(
    tenant_a,
    semantic_model_a,
    semantic_model_b,
    kpi_definition_a,
    kpi_definition_b,
    warehouse_table,
    warehouse_table_b,
):
    """Verify ForeignKeys (semantic_model, kpi_definition, warehouse_table) querysets only display tenant A records."""
    form = AugmentedInsightForm(tenant=tenant_a)

    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs

    kpi_qs = form.fields["kpi_definition"].queryset
    assert kpi_definition_a in kpi_qs
    assert kpi_definition_b not in kpi_qs

    tbl_qs = form.fields["warehouse_table"].queryset
    assert warehouse_table in tbl_qs
    assert warehouse_table_b not in tbl_qs


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_unscoped_initialization():
    """Verify form initializes safely without tenant without raising exceptions."""
    form = AugmentedInsightForm(tenant=None)
    assert form.fields["semantic_model"].required is False
    assert form.fields["kpi_definition"].required is False
    assert form.fields["warehouse_table"].required is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_reject_foreign_semantic_model(
    tenant_a, semantic_model_b
):
    """Verify reject_foreign rejects assigning a cross-tenant semantic model."""
    data = _aiaugmentedanalytics_forms_valid_insight_data(semantic_model=semantic_model_b)
    form = AugmentedInsightForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_reject_foreign_kpi_definition(
    tenant_a, kpi_definition_b
):
    """Verify reject_foreign rejects assigning a cross-tenant KPI definition."""
    data = _aiaugmentedanalytics_forms_valid_insight_data(kpi_definition=kpi_definition_b)
    form = AugmentedInsightForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi_definition" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_reject_foreign_warehouse_table(
    tenant_a, warehouse_table_b
):
    """Verify reject_foreign rejects assigning a cross-tenant warehouse table."""
    data = _aiaugmentedanalytics_forms_valid_insight_data(warehouse_table=warehouse_table_b)
    form = AugmentedInsightForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_clean_driver_decomposition_valid_json_list():
    """Verify clean_driver_decomposition accepts valid JSON list string and returns parsed list."""
    form = AugmentedInsightForm()
    form.cleaned_data = {
        "driver_decomposition": '[{"name": "Supply Chain Delays", "weight": 45, "impact": "negative"}]'
    }
    result = form.clean_driver_decomposition()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["name"] == "Supply Chain Delays"


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_clean_driver_decomposition_valid_json_dict():
    """Verify clean_driver_decomposition accepts valid JSON dictionary string and returns parsed dict."""
    form = AugmentedInsightForm()
    form.cleaned_data = {"driver_decomposition": '{"factor": "Price Increase", "impact": "positive"}'}
    result = form.clean_driver_decomposition()
    assert isinstance(result, dict)
    assert result["factor"] == "Price Increase"


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_clean_driver_decomposition_empty_or_none():
    """Verify clean_driver_decomposition returns empty list when given None or empty string."""
    form = AugmentedInsightForm()
    form.cleaned_data = {"driver_decomposition": ""}
    assert form.clean_driver_decomposition() == []
    form.cleaned_data = {"driver_decomposition": None}
    assert form.clean_driver_decomposition() == []


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_clean_driver_decomposition_invalid_json():
    """Verify clean_driver_decomposition raises ValidationError on malformed JSON string."""
    form = AugmentedInsightForm()
    form.cleaned_data = {"driver_decomposition": '{"incomplete_json": '}
    with pytest.raises(forms.ValidationError) as excinfo:
        form.clean_driver_decomposition()
    assert "Invalid JSON" in str(excinfo.value)


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_clean_driver_decomposition_invalid_type():
    """Verify clean_driver_decomposition raises ValidationError when parsed JSON is not list or dict."""
    form = AugmentedInsightForm()
    form.cleaned_data = {"driver_decomposition": '"just a string"'}
    with pytest.raises(forms.ValidationError) as excinfo:
        form.clean_driver_decomposition()
    assert "list or object" in str(excinfo.value)


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_valid_submission_and_save(
    tenant_a, admin_user, semantic_model_a, kpi_definition_a, warehouse_table
):
    """Test valid form submission and form.save(commit=False) flow with tenant assignment."""
    data = _aiaugmentedanalytics_forms_valid_insight_data(
        semantic_model=semantic_model_a,
        kpi_definition=kpi_definition_a,
        warehouse_table=warehouse_table,
    )
    form = AugmentedInsightForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.number = "BAIN-99001"
    instance.created_by = admin_user
    instance.save()

    saved = AugmentedInsight.objects.get(pk=instance.pk)
    assert saved.title == "Gross Margin Compression Q4"
    assert saved.tenant == tenant_a
    assert saved.created_by == admin_user
    assert saved.semantic_model == semantic_model_a
    assert saved.kpi_definition == kpi_definition_a
    assert saved.warehouse_table == warehouse_table
    assert saved.baseline_value == Decimal("42.5000")
    assert saved.observed_value == Decimal("38.1000")
    assert saved.variance_percentage == Decimal("-10.35")
    assert saved.impact_direction == "unfavorable"
    assert saved.severity == "high"


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_required_fields(tenant_a):
    """Verify required fields fail validation when submitted with empty data."""
    form = AugmentedInsightForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "metric_name" in form.errors
    assert "baseline_value" in form.errors
    assert "observed_value" in form.errors
    assert "variance_percentage" in form.errors
    assert "narrative_summary" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_optional_foreign_keys(tenant_a, admin_user):
    """Verify foreign keys are optional on AugmentedInsightForm."""
    data = _aiaugmentedanalytics_forms_valid_insight_data()
    form = AugmentedInsightForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed with optional FKs: {form.errors}"
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.created_by = admin_user
    instance.save()
    assert instance.semantic_model is None
    assert instance.kpi_definition is None
    assert instance.warehouse_table is None


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_insight_widget_classes():
    """Verify Tailwind widget styling classes on AugmentedInsightForm."""
    form = AugmentedInsightForm()
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["insight_type"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["narrative_summary"].widget.attrs.get("class", "")


# ===========================================================================
# 2. SmartDataPrepSuggestionForm Tests (BSDP)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_system_field_exclusions():
    """Verify system fields (tenant, number, reviewed_by, reviewed_at, suggested_config, timestamps) are excluded."""
    form = SmartDataPrepSuggestionForm()
    excluded_fields = [
        "tenant",
        "number",
        "reviewed_by",
        "reviewed_at",
        "suggested_config",
        "created_at",
        "updated_at",
    ]
    for field in excluded_fields:
        assert field not in form.fields, f"Security violation: {field} exposed in SmartDataPrepSuggestionForm"


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_tenant_scoping(
    tenant_a, warehouse_table, warehouse_table_b
):
    """Verify foreign keys (target_table, related_table) only display tenant A tables."""
    form = SmartDataPrepSuggestionForm(tenant=tenant_a)

    target_qs = form.fields["target_table"].queryset
    assert warehouse_table in target_qs
    assert warehouse_table_b not in target_qs

    related_qs = form.fields["related_table"].queryset
    assert warehouse_table in related_qs
    assert warehouse_table_b not in related_qs


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_unscoped_initialization():
    """Verify form initializes safely without tenant without raising exceptions."""
    form = SmartDataPrepSuggestionForm(tenant=None)
    assert form.fields["related_table"].required is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_reject_foreign_target_table(
    tenant_a, warehouse_table_b
):
    """Verify reject_foreign rejects assigning a cross-tenant target_table."""
    data = _aiaugmentedanalytics_forms_valid_dataprep_data(target_table=warehouse_table_b)
    form = SmartDataPrepSuggestionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_table" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_reject_foreign_related_table(
    tenant_a, warehouse_table, warehouse_table_b
):
    """Verify reject_foreign rejects assigning a cross-tenant related_table."""
    data = _aiaugmentedanalytics_forms_valid_dataprep_data(
        target_table=warehouse_table, related_table=warehouse_table_b
    )
    form = SmartDataPrepSuggestionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "related_table" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_clean_suggested_config_valid_json_dict():
    """Verify clean_suggested_config accepts valid JSON dict string and returns parsed dict."""
    form = SmartDataPrepSuggestionForm()
    form.cleaned_data = {
        "suggested_config": '{"target_type": "TIMESTAMP", "format": "ISO8601", "nullable": true}'
    }
    result = form.clean_suggested_config()
    assert isinstance(result, dict)
    assert result["target_type"] == "TIMESTAMP"
    assert result["nullable"] is True


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_clean_suggested_config_empty_or_none():
    """Verify clean_suggested_config returns empty dict when given None or empty string."""
    form = SmartDataPrepSuggestionForm()
    form.cleaned_data = {"suggested_config": ""}
    assert form.clean_suggested_config() == {}
    form.cleaned_data = {"suggested_config": None}
    assert form.clean_suggested_config() == {}


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_clean_suggested_config_invalid_json():
    """Verify clean_suggested_config raises ValidationError on malformed JSON string."""
    form = SmartDataPrepSuggestionForm()
    form.cleaned_data = {"suggested_config": '{"incomplete":'}
    with pytest.raises(forms.ValidationError) as excinfo:
        form.clean_suggested_config()
    assert "Invalid JSON" in str(excinfo.value)


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_clean_suggested_config_non_dict_rejected():
    """Verify clean_suggested_config raises ValidationError when parsed JSON is not a dictionary."""
    form = SmartDataPrepSuggestionForm()
    form.cleaned_data = {"suggested_config": '["item1", "item2"]'}
    with pytest.raises(forms.ValidationError) as excinfo:
        form.clean_suggested_config()
    assert "dictionary" in str(excinfo.value)


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_valid_submission_and_save(
    tenant_a, warehouse_table
):
    """Test valid form submission and form.save(commit=False) flow with tenant assignment."""
    data = _aiaugmentedanalytics_forms_valid_dataprep_data(target_table=warehouse_table)
    form = SmartDataPrepSuggestionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.number = "BSDP-99001"
    instance.save()

    saved = SmartDataPrepSuggestion.objects.get(pk=instance.pk)
    assert saved.target_table == warehouse_table
    assert saved.target_column == "customer_id"
    assert saved.suggestion_type == "join_relationship"
    assert saved.confidence_score == Decimal("95.00")
    assert saved.status == "pending"
    assert saved.tenant == tenant_a


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_required_fields(tenant_a):
    """Verify required fields fail validation on empty payload."""
    form = SmartDataPrepSuggestionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_table" in form.errors
    assert "target_column" in form.errors
    assert "suggestion_type" in form.errors
    assert "rationale" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_dataprep_optional_related_table(tenant_a, warehouse_table):
    """Verify related_table and related_column are optional on SmartDataPrepSuggestionForm."""
    data = _aiaugmentedanalytics_forms_valid_dataprep_data(target_table=warehouse_table)
    form = SmartDataPrepSuggestionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed with optional related table: {form.errors}"
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.related_table is None
    assert instance.related_column == "id"


# ===========================================================================
# 3. TextSentimentAnalysisForm Tests (BSNT)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_system_field_exclusions():
    """Verify system fields (tenant, number, thematic_tags, analyzed_at, timestamps, status) are excluded."""
    form = TextSentimentAnalysisForm()
    excluded_fields = [
        "tenant",
        "number",
        "thematic_tags",
        "analyzed_at",
        "created_at",
        "updated_at",
        "status",
    ]
    for field in excluded_fields:
        assert field not in form.fields, f"Security violation: {field} exposed in TextSentimentAnalysisForm"


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_tenant_scoping(tenant_a, tenant_b):
    """Verify foreign keys (linked_party, linked_org_unit) only display tenant A records."""
    party_a = _aiaugmentedanalytics_forms_create_party(tenant_a, "Acme Customer")
    party_b = _aiaugmentedanalytics_forms_create_party(tenant_b, "Globex Customer")
    org_unit_a = _aiaugmentedanalytics_forms_create_org_unit(tenant_a, "Acme Support")
    org_unit_b = _aiaugmentedanalytics_forms_create_org_unit(tenant_b, "Globex Support")

    form = TextSentimentAnalysisForm(tenant=tenant_a)

    party_qs = form.fields["linked_party"].queryset
    assert party_a in party_qs
    assert party_b not in party_qs

    ou_qs = form.fields["linked_org_unit"].queryset
    assert org_unit_a in ou_qs
    assert org_unit_b not in ou_qs


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_unscoped_initialization():
    """Verify form initializes safely without tenant without raising exceptions."""
    form = TextSentimentAnalysisForm(tenant=None)
    assert form.fields["linked_party"].required is False
    assert form.fields["linked_org_unit"].required is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_reject_foreign_linked_party(tenant_a, tenant_b):
    """Verify reject_foreign rejects assigning a cross-tenant linked_party."""
    party_b = _aiaugmentedanalytics_forms_create_party(tenant_b, "Globex Party")
    data = _aiaugmentedanalytics_forms_valid_sentiment_data(linked_party=party_b)
    form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "linked_party" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_reject_foreign_linked_org_unit(tenant_a, tenant_b):
    """Verify reject_foreign rejects assigning a cross-tenant linked_org_unit."""
    org_unit_b = _aiaugmentedanalytics_forms_create_org_unit(tenant_b, "Globex Org Unit")
    data = _aiaugmentedanalytics_forms_valid_sentiment_data(linked_org_unit=org_unit_b)
    form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "linked_org_unit" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_polarity_score_valid_bounds(tenant_a):
    """Verify polarity_score passes validation for boundary and typical valid decimal values."""
    valid_scores = ["-1.00", "-0.75", "0.00", "0.85", "1.00"]
    for score in valid_scores:
        data = _aiaugmentedanalytics_forms_valid_sentiment_data()
        data["polarity_score"] = score
        form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid polarity {score} failed validation: {form.errors}"
        assert form.cleaned_data["polarity_score"] == Decimal(score)


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_polarity_score_below_minimum(tenant_a):
    """Verify clean_polarity_score raises ValidationError when score < -1.00."""
    data = _aiaugmentedanalytics_forms_valid_sentiment_data()
    data["polarity_score"] = "-1.05"
    form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "polarity_score" in form.errors
    assert "between -1.00 and 1.00" in str(form.errors["polarity_score"])


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_polarity_score_above_maximum(tenant_a):
    """Verify clean_polarity_score raises ValidationError when score > 1.00."""
    data = _aiaugmentedanalytics_forms_valid_sentiment_data()
    data["polarity_score"] = "1.05"
    form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "polarity_score" in form.errors
    assert "between -1.00 and 1.00" in str(form.errors["polarity_score"])


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_subjectivity_score_valid_bounds(tenant_a):
    """Verify subjectivity_score passes validation for boundary and typical valid decimal values."""
    valid_scores = ["0.00", "0.35", "0.50", "0.95", "1.00"]
    for score in valid_scores:
        data = _aiaugmentedanalytics_forms_valid_sentiment_data()
        data["subjectivity_score"] = score
        form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid subjectivity {score} failed validation: {form.errors}"
        assert form.cleaned_data["subjectivity_score"] == Decimal(score)


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_subjectivity_score_below_minimum(tenant_a):
    """Verify clean_subjectivity_score raises ValidationError when score < 0.00."""
    data = _aiaugmentedanalytics_forms_valid_sentiment_data()
    data["subjectivity_score"] = "-0.01"
    form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subjectivity_score" in form.errors
    assert "between 0.00 and 1.00" in str(form.errors["subjectivity_score"])


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_subjectivity_score_above_maximum(tenant_a):
    """Verify clean_subjectivity_score raises ValidationError when score > 1.00."""
    data = _aiaugmentedanalytics_forms_valid_sentiment_data()
    data["subjectivity_score"] = "1.01"
    form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subjectivity_score" in form.errors
    assert "between 0.00 and 1.00" in str(form.errors["subjectivity_score"])


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_extracted_themes_comma_separated():
    """Verify clean_extracted_themes parses comma-separated tags into cleaned list."""
    form = TextSentimentAnalysisForm()
    form.cleaned_data = {"extracted_themes": "billing, onboarding, customer support, latency "}
    result = form.clean_extracted_themes()
    assert result == ["billing", "onboarding", "customer support", "latency"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_extracted_themes_json_list():
    """Verify clean_extracted_themes parses JSON array string into cleaned list."""
    form = TextSentimentAnalysisForm()
    form.cleaned_data = {"extracted_themes": '["reconciliation", "pricing", "delivery_time"]'}
    result = form.clean_extracted_themes()
    assert result == ["reconciliation", "pricing", "delivery_time"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_clean_extracted_themes_empty():
    """Verify clean_extracted_themes returns empty list when given None or empty string."""
    form = TextSentimentAnalysisForm()
    form.cleaned_data = {"extracted_themes": ""}
    assert form.clean_extracted_themes() == []
    form.cleaned_data = {"extracted_themes": None}
    assert form.clean_extracted_themes() == []


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_valid_submission_and_save(tenant_a):
    """Test valid form submission and form.save(commit=False) flow with tenant assignment."""
    party = _aiaugmentedanalytics_forms_create_party(tenant_a, "Premier Client")
    org_unit = _aiaugmentedanalytics_forms_create_org_unit(tenant_a, "Enterprise Support")

    data = _aiaugmentedanalytics_forms_valid_sentiment_data(
        linked_party=party, linked_org_unit=org_unit
    )
    form = TextSentimentAnalysisForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.number = "BSNT-99001"
    instance.thematic_tags = ["performance", "speed"]
    instance.save()

    saved = TextSentimentAnalysis.objects.get(pk=instance.pk)
    assert saved.source_type == "customer_review"
    assert saved.source_reference == "REV-2027-0012"
    assert saved.sentiment_category == "positive"
    assert saved.polarity_score == Decimal("0.85")
    assert saved.subjectivity_score == Decimal("0.60")
    assert saved.linked_party == party
    assert saved.linked_org_unit == org_unit
    assert saved.thematic_tags == ["performance", "speed"]
    assert saved.tenant == tenant_a


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_sentiment_required_fields(tenant_a):
    """Verify required fields fail validation on empty payload."""
    form = TextSentimentAnalysisForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "source_type" in form.errors
    assert "source_reference" in form.errors
    assert "text_content" in form.errors
    assert "language" in form.errors


# ===========================================================================
# 4. AnalyticsRecommendationForm Tests (BARC)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_system_field_exclusions():
    """Verify system fields (tenant, number, last_interacted_at, timestamps) are excluded."""
    form = AnalyticsRecommendationForm()
    excluded_fields = [
        "tenant",
        "number",
        "last_interacted_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded_fields:
        assert field not in form.fields, f"Security violation: {field} exposed in AnalyticsRecommendationForm"


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_tenant_scoping(
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
    bi_dashboard_a,
    bi_dashboard_b,
    kpi_definition_a,
    kpi_definition_b,
    semantic_model_a,
    semantic_model_b,
):
    """Verify foreign keys (user, dashboard, report, kpi, semantic_model) only display tenant A records."""
    report_definition_a = _aiaugmentedanalytics_forms_create_report(tenant_a, slug="test-rep-a")
    report_definition_b = _aiaugmentedanalytics_forms_create_report(tenant_b, slug="test-rep-b")
    form = AnalyticsRecommendationForm(tenant=tenant_a)

    user_qs = form.fields["user"].queryset
    assert admin_user in user_qs
    assert admin_user_b not in user_qs

    dash_qs = form.fields["dashboard"].queryset
    assert bi_dashboard_a in dash_qs
    assert bi_dashboard_b not in dash_qs

    rep_qs = form.fields["report"].queryset
    assert report_definition_a in rep_qs
    assert report_definition_b not in rep_qs

    kpi_qs = form.fields["kpi"].queryset
    assert kpi_definition_a in kpi_qs
    assert kpi_definition_b not in kpi_qs

    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_unscoped_initialization():
    """Verify form initializes safely without tenant without raising exceptions."""
    form = AnalyticsRecommendationForm(tenant=None)
    assert form.fields["dashboard"].required is False
    assert form.fields["report"].required is False
    assert form.fields["kpi"].required is False
    assert form.fields["semantic_model"].required is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_reject_foreign_user(
    tenant_a, admin_user_b
):
    """Verify reject_foreign rejects assigning a cross-tenant user."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user_b)
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "user" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_reject_foreign_dashboard(
    tenant_a, admin_user, bi_dashboard_b
):
    """Verify reject_foreign rejects assigning a cross-tenant dashboard."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(
        user=admin_user, dashboard=bi_dashboard_b
    )
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_reject_foreign_report(
    tenant_a, tenant_b, admin_user
):
    """Verify reject_foreign rejects assigning a cross-tenant report."""
    report_b = _aiaugmentedanalytics_forms_create_report(tenant_b, slug="test-rep-foreign")
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(
        user=admin_user, report=report_b
    )
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_reject_foreign_kpi(
    tenant_a, admin_user, kpi_definition_b
):
    """Verify reject_foreign rejects assigning a cross-tenant KPI definition."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(
        user=admin_user, kpi=kpi_definition_b
    )
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_reject_foreign_semantic_model(
    tenant_a, admin_user, semantic_model_b
):
    """Verify reject_foreign rejects assigning a cross-tenant semantic model."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(
        user=admin_user, semantic_model=semantic_model_b
    )
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_clean_target_url_valid_relative(
    tenant_a, admin_user
):
    """Verify valid relative URLs starting with a single '/' pass clean_target_url."""
    valid_urls = [
        "/bi/dashboards/1/",
        "/bi/reports/42/",
        "/bi/kpis/view/12/",
        "/bi/recommendations/",
    ]
    for url in valid_urls:
        data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user)
        data["target_url"] = url
        form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid URL {url} failed validation: {form.errors}"
        assert form.cleaned_data["target_url"] == url


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_clean_target_url_empty_allowed(
    tenant_a, admin_user
):
    """Verify empty target_url is returned as empty string without error in clean_target_url."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user)
    data["target_url"] = ""
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    # Required field error might trigger if target_url is required, but clean_target_url itself permits empty
    form.is_valid()
    assert form.clean_target_url() == ""


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_clean_target_url_reject_missing_slash(
    tenant_a, admin_user
):
    """Verify clean_target_url rejects URL not starting with '/'."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user)
    data["target_url"] = "bi/dashboards/1/"
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors
    assert "starting with a single" in str(form.errors["target_url"])


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_clean_target_url_reject_protocol_relative(
    tenant_a, admin_user
):
    """Verify clean_target_url rejects protocol-relative URL starting with '//' (open redirect defense)."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user)
    data["target_url"] = "//evil.com/phishing"
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors
    assert "starting with a single" in str(form.errors["target_url"])


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_clean_target_url_reject_javascript_protocol(
    tenant_a, admin_user
):
    """Verify clean_target_url rejects javascript: pseudo-protocol (XSS defense)."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user)
    data["target_url"] = "javascript:alert(document.cookie)"
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_clean_target_url_reject_backslash(
    tenant_a, admin_user
):
    """Verify clean_target_url rejects backslash-escaped URL /\\\\ (IE open redirect vector)."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user)
    data["target_url"] = "/\\evil.com"
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_valid_submission_and_save(
    tenant_a, admin_user, bi_dashboard_a, semantic_model_a
):
    """Test valid form submission and form.save(commit=False) flow with tenant assignment."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(
        user=admin_user, dashboard=bi_dashboard_a, semantic_model=semantic_model_a
    )
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.number = "BARC-99001"
    instance.save()

    saved = AnalyticsRecommendation.objects.get(pk=instance.pk)
    assert saved.user == admin_user
    assert saved.recommendation_type == "dashboard"
    assert saved.target_title == "Executive Revenue Performance Dashboard"
    assert saved.target_url == "/bi/dashboards/1/"
    assert saved.reason == "role_relevance"
    assert saved.affinity_score == Decimal("94.50")
    assert saved.status == "active"
    assert saved.dashboard == bi_dashboard_a
    assert saved.semantic_model == semantic_model_a
    assert saved.tenant == tenant_a


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_required_fields(tenant_a):
    """Verify required fields fail validation on empty payload."""
    form = AnalyticsRecommendationForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "user" in form.errors
    assert "recommendation_type" in form.errors
    assert "target_title" in form.errors
    assert "target_url" in form.errors
    assert "reason" in form.errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_forms_recommendation_optional_foreign_keys(
    tenant_a, admin_user
):
    """Verify dashboard, report, kpi, semantic_model are optional on AnalyticsRecommendationForm."""
    data = _aiaugmentedanalytics_forms_valid_recommendation_data(user=admin_user)
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed with optional FKs: {form.errors}"
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.dashboard is None
    assert instance.report is None
    assert instance.kpi is None
    assert instance.semantic_model is None
