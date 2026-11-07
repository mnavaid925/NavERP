"""Unit tests for Sub-module 10.15 Natural Language & Conversational BI forms.

Forms covered:
1. NaturalLanguageQueryForm (apps/bi/forms/ConversationalBi/NaturalLanguageQueries.py)
2. NaturalLanguageQueryRateForm (Rating action form)
3. BiConversationSessionForm (apps/bi/forms/ConversationalBi/BiConversationSessions.py)
4. BiConversationSessionAskForm (Interactive ask action form)
5. NarrativeExplanationForm (apps/bi/forms/ConversationalBi/NarrativeExplanations.py)
6. SearchDiscoveryIndexForm (apps/bi/forms/ConversationalBi/SearchDiscoveryIndexes.py)
7. SearchDiscoveryIndexReweightForm (Relevance reweighting action form)
"""
import json
from decimal import Decimal, InvalidOperation

import pytest
from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms import (
    BiConversationSessionForm,
    NarrativeExplanationForm,
    NaturalLanguageQueryForm,
    SearchDiscoveryIndexForm,
)
from apps.bi.forms._common import reject_foreign
from apps.bi.models import (
    BiConversationSession,
    NarrativeExplanation,
    NaturalLanguageQuery,
    SearchDiscoveryIndex,
)
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition


# ==============================================================================
# Action / Auxiliary Form Definitions for Sub-module 10.15
# ==============================================================================


class NaturalLanguageQueryRateForm(forms.Form):
    """Auxiliary action form for user accuracy ratings on natural language queries."""

    USER_RATING_CHOICES = [
        ("helpful", "Helpful / Accurate"),
        ("partially_helpful", "Partially Helpful"),
        ("unhelpful", "Unhelpful / Inaccurate"),
    ]

    user_rating = forms.ChoiceField(
        choices=USER_RATING_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    rating_feedback = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
    )

    def clean_rating_feedback(self):
        feedback = self.cleaned_data.get("rating_feedback", "")
        return feedback.strip() if feedback else ""


class BiConversationSessionAskForm(forms.Form):
    """Auxiliary action form for asking an analytical question inside a chat session."""

    question_text = forms.CharField(
        required=True,
        max_length=500,
        widget=forms.TextInput(
            attrs={"class": "form-input", "placeholder": "Ask an analytical question..."}
        ),
    )

    def clean_question_text(self):
        text = self.cleaned_data.get("question_text", "").strip()
        if not text:
            raise forms.ValidationError("Please enter an analytical question.")
        return text


class SearchDiscoveryIndexReweightForm(forms.Form):
    """Auxiliary action form for hand-parsed search discovery weight adjustments."""

    weight = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "1.00"}),
    )

    def clean_weight(self):
        val = self.cleaned_data.get("weight", "").strip()
        if not val:
            return None
        try:
            dec = Decimal(val)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Invalid weight format.")

        if not dec.is_finite():
            raise forms.ValidationError("Non-finite Decimal rejected.")

        if dec < Decimal("0.00"):
            raise forms.ValidationError("Weight cannot be negative.")

        if dec < Decimal("0.10") or dec > Decimal("99.99"):
            raise forms.ValidationError("Weight must be between 0.10 and 99.99.")

        return dec


# ==============================================================================
# Module Helpers (prefixed with _conversationalbi_*)
# ==============================================================================


def _conversationalbi_create_report(tenant, name="Executive Financial Summary", slug="exec-fin-summary"):
    """Helper to create a tenant-scoped ReportDefinition instance."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        slug=slug,
        category="finance",
        report_type="standard_tabular",
    )


def _conversationalbi_clean_newline_text(text):
    """Convert newline-delimited text into a list of stripped non-empty lines."""
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _conversationalbi_valid_nlq_data(**kwargs):
    """Return a valid dictionary payload for NaturalLanguageQueryForm."""
    data = {
        "query_text": "What was total gross revenue by region in Q3 2026?",
        "input_modality": "text",
        "intent_type": "metric_lookup",
        "chart_type": "bar_chart",
        "user_rating": "helpful",
        "user_feedback_notes": "Accurate response with correct metric breakdowns.",
    }
    data.update(kwargs)
    return data


def _conversationalbi_valid_session_data(**kwargs):
    """Return a valid dictionary payload for BiConversationSessionForm."""
    data = {
        "title": "Q4 Executive Revenue and Profitability Thread",
        "session_status": "active",
        "is_pinned": True,
    }
    data.update(kwargs)
    return data


def _conversationalbi_valid_narrative_data(**kwargs):
    """Return a valid dictionary payload for NarrativeExplanationForm."""
    data = {
        "title": "Q3 Executive Performance Briefing",
        "headline": "Gross margin expanded +3.4% driven by European direct sales expansion",
        "target_artifact_type": "dashboard",
        "narrative_style": "executive_briefing",
        "narrative_body": "Total gross revenue reached 14.2M against plan, outperforming budget by 11.2%.",
        "top_positive_driver": "European Direct Sales Expansion",
        "top_negative_driver": "Freight and Tariff Surcharges",
        "language": "en",
    }
    data.update(kwargs)
    return data


def _conversationalbi_valid_search_index_data(**kwargs):
    """Return a valid dictionary payload for SearchDiscoveryIndexForm."""
    data = {
        "asset_name": "Executive Profitability Overview Dashboard",
        "asset_type": "dashboard",
        "target_url": "/bi/dashboards/1/",
        "description": "Enterprise overview of revenue, margins, and customer retention metrics.",
        "category": "Finance",
        "synonyms": json.dumps(["sales", "revenue", "margin", "turnover"]),
        "search_keywords": "q3 revenue gross margin cfo",
        "relevance_weight": "1.25",
        "is_featured": True,
        "is_verified": True,
    }
    data.update(kwargs)
    return data


# ==============================================================================
# 1. NaturalLanguageQueryForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_form_nlq_system_field_exclusions():
    """Verify system and telemetry fields are strictly excluded from NaturalLanguageQueryForm."""
    form = NaturalLanguageQueryForm()
    expected_fields = {
        "query_text",
        "input_modality",
        "intent_type",
        "semantic_model",
        "warehouse_table",
        "kpi_definition",
        "conversation_session",
        "chart_type",
        "user_rating",
        "user_feedback_notes",
    }
    assert set(form.fields.keys()) == expected_fields

    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "user",
        "parsed_measures",
        "parsed_dimensions",
        "parsed_filters",
        "generated_sql",
        "chart_config",
        "result_summary",
        "confidence_score",
        "execution_status",
        "execution_duration_ms",
        "audio_duration_seconds",
    ]
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} exposed in NaturalLanguageQueryForm"


@pytest.mark.django_db
def test_conversationalbi_form_nlq_tenant_scoping(
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
    warehouse_table_a,
    warehouse_table_b,
    kpi_definition_a,
    kpi_definition_b,
    bi_conversation_session_a,
    bi_conversation_session_b,
):
    """Verify foreign key choices only contain tenant_a records, never tenant_b."""
    form = NaturalLanguageQueryForm(tenant=tenant_a)

    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs

    wt_qs = form.fields["warehouse_table"].queryset
    assert warehouse_table_a in wt_qs
    assert warehouse_table_b not in wt_qs

    kpi_qs = form.fields["kpi_definition"].queryset
    assert kpi_definition_a in kpi_qs
    assert kpi_definition_b not in kpi_qs

    session_qs = form.fields["conversation_session"].queryset
    assert bi_conversation_session_a in session_qs
    assert bi_conversation_session_b not in session_qs


@pytest.mark.django_db
def test_conversationalbi_form_nlq_unscoped_initialization():
    """Verify NaturalLanguageQueryForm initializes safely without tenant without crashing."""
    form = NaturalLanguageQueryForm(tenant=None)
    assert form.fields["semantic_model"].required is False
    assert form.fields["warehouse_table"].required is False
    assert form.fields["kpi_definition"].required is False
    assert form.fields["conversation_session"].required is False


@pytest.mark.django_db
def test_conversationalbi_form_nlq_reject_foreign_semantic_model(tenant_a, semantic_model_b):
    """Verify cross-tenant semantic model submission is rejected."""
    data = _conversationalbi_valid_nlq_data(semantic_model=semantic_model_b.pk)
    form = NaturalLanguageQueryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_nlq_reject_foreign_warehouse_table(tenant_a, warehouse_table_b):
    """Verify cross-tenant warehouse table submission is rejected."""
    data = _conversationalbi_valid_nlq_data(warehouse_table=warehouse_table_b.pk)
    form = NaturalLanguageQueryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_nlq_reject_foreign_kpi_definition(tenant_a, kpi_definition_b):
    """Verify cross-tenant KPI definition submission is rejected."""
    data = _conversationalbi_valid_nlq_data(kpi_definition=kpi_definition_b.pk)
    form = NaturalLanguageQueryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi_definition" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_nlq_reject_foreign_conversation_session(tenant_a, bi_conversation_session_b):
    """Verify cross-tenant conversation session submission is rejected."""
    data = _conversationalbi_valid_nlq_data(conversation_session=bi_conversation_session_b.pk)
    form = NaturalLanguageQueryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "conversation_session" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_nlq_reject_foreign_helper(
    tenant_a,
    semantic_model_b,
    warehouse_table_b,
    kpi_definition_b,
    bi_conversation_session_b,
):
    """Verify reject_foreign helper explicitly tags cross-tenant records."""
    form = NaturalLanguageQueryForm(tenant=tenant_a)
    form._errors = {}
    form.cleaned_data = {
        "semantic_model": semantic_model_b,
        "warehouse_table": warehouse_table_b,
        "kpi_definition": kpi_definition_b,
        "conversation_session": bi_conversation_session_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["semantic_model", "warehouse_table", "kpi_definition", "conversation_session"],
    )
    assert "semantic_model" in form.errors
    assert "warehouse_table" in form.errors
    assert "kpi_definition" in form.errors
    assert "conversation_session" in form.errors
    for name in ["semantic_model", "warehouse_table", "kpi_definition", "conversation_session"]:
        assert form.errors[name] == ["That record belongs to another workspace."]


@pytest.mark.django_db
def test_conversationalbi_form_nlq_input_modality_validation(tenant_a):
    """Verify valid and invalid input modality choices."""
    for valid_modality in ["text", "voice", "api"]:
        form = NaturalLanguageQueryForm(
            data=_conversationalbi_valid_nlq_data(input_modality=valid_modality),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid modality {valid_modality}: {form.errors}"

    invalid_form = NaturalLanguageQueryForm(
        data=_conversationalbi_valid_nlq_data(input_modality="telepathy"),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "input_modality" in invalid_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_nlq_intent_type_validation(tenant_a):
    """Verify valid and invalid intent type choices."""
    valid_intents = [
        "metric_lookup",
        "trend_analysis",
        "ranking_top_bottom",
        "comparative_analysis",
        "distribution",
        "correlation",
        "drill_down",
    ]
    for intent in valid_intents:
        form = NaturalLanguageQueryForm(
            data=_conversationalbi_valid_nlq_data(intent_type=intent),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid intent {intent}: {form.errors}"

    invalid_form = NaturalLanguageQueryForm(
        data=_conversationalbi_valid_nlq_data(intent_type="unsupported_prediction"),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "intent_type" in invalid_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_nlq_chart_type_validation(tenant_a):
    """Verify valid chart type choices."""
    valid_charts = [
        "metric_card",
        "bar_chart",
        "horizontal_bar",
        "line_chart",
        "donut_chart",
        "scatter_plot",
        "pivot_table",
        "data_table",
    ]
    for chart in valid_charts:
        form = NaturalLanguageQueryForm(
            data=_conversationalbi_valid_nlq_data(chart_type=chart),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid chart {chart}: {form.errors}"


@pytest.mark.django_db
def test_conversationalbi_form_nlq_required_fields(tenant_a):
    """Verify required field validation fails when mandatory query_text is omitted."""
    form = NaturalLanguageQueryForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "query_text" in form.errors

    whitespace_form = NaturalLanguageQueryForm(
        data=_conversationalbi_valid_nlq_data(query_text="   "),
        tenant=tenant_a,
    )
    assert not whitespace_form.is_valid()
    assert "query_text" in whitespace_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_nlq_optional_fields(tenant_a):
    """Verify optional foreign keys and feedback notes can be omitted."""
    data = {
        "query_text": "What is our customer churn percentage?",
        "input_modality": "text",
        "intent_type": "metric_lookup",
        "chart_type": "metric_card",
        "user_rating": "unrated",
        "user_feedback_notes": "",
    }
    form = NaturalLanguageQueryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"


@pytest.mark.django_db
def test_conversationalbi_form_nlq_valid_submission_create_and_save(
    tenant_a,
    admin_user,
    semantic_model_a,
    warehouse_table_a,
    kpi_definition_a,
    bi_conversation_session_a,
):
    """Verify valid form submission and instance persistence with tenant scoping."""
    data = _conversationalbi_valid_nlq_data(
        semantic_model=semantic_model_a.pk,
        warehouse_table=warehouse_table_a.pk,
        kpi_definition=kpi_definition_a.pk,
        conversation_session=bi_conversation_session_a.pk,
    )
    form = NaturalLanguageQueryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.user = admin_user
    instance.number = "BNLQ-99001"
    instance.save()

    saved = NaturalLanguageQuery.objects.get(pk=instance.pk)
    assert saved.tenant == tenant_a
    assert saved.query_text == "What was total gross revenue by region in Q3 2026?"
    assert saved.semantic_model == semantic_model_a
    assert saved.warehouse_table == warehouse_table_a
    assert saved.kpi_definition == kpi_definition_a
    assert saved.conversation_session == bi_conversation_session_a
    assert saved.user_rating == "helpful"


@pytest.mark.django_db
def test_conversationalbi_form_nlq_valid_submission_update(
    tenant_a,
    natural_language_query_a,
):
    """Verify editing an existing NaturalLanguageQuery instance through form."""
    edit_data = _conversationalbi_valid_nlq_data(
        query_text="Updated analytical query text?",
        user_rating="unhelpful",
        user_feedback_notes="Returned revenue instead of profit margins.",
    )
    form = NaturalLanguageQueryForm(data=edit_data, instance=natural_language_query_a, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    updated = form.save()

    assert updated.pk == natural_language_query_a.pk
    assert updated.query_text == "Updated analytical query text?"
    assert updated.user_rating == "unhelpful"
    assert updated.user_feedback_notes == "Returned revenue instead of profit margins."


@pytest.mark.django_db
def test_conversationalbi_form_nlq_widget_attributes(tenant_a):
    """Verify CSS form-control widget classes on NaturalLanguageQueryForm."""
    form = NaturalLanguageQueryForm(tenant=tenant_a)
    assert "form-input" in form.fields["query_text"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["input_modality"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["intent_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["chart_type"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["user_feedback_notes"].widget.attrs.get("class", "")


# ==============================================================================
# 2. NaturalLanguageQueryRateForm Tests
# ==============================================================================


def test_conversationalbi_form_nlq_rate_valid_choices():
    """Verify valid rating choices succeed in NaturalLanguageQueryRateForm."""
    valid_ratings = ["helpful", "partially_helpful", "unhelpful"]
    for rating in valid_ratings:
        form = NaturalLanguageQueryRateForm(
            data={"user_rating": rating, "rating_feedback": "Helpful result."}
        )
        assert form.is_valid(), f"Failed on rating {rating}: {form.errors}"
        assert form.cleaned_data["user_rating"] == rating
        assert form.cleaned_data["rating_feedback"] == "Helpful result."


def test_conversationalbi_form_nlq_rate_invalid_choice():
    """Verify invalid rating choice is rejected."""
    invalid_ratings = ["terrible", "5_stars", "superb", ""]
    for invalid in invalid_ratings:
        form = NaturalLanguageQueryRateForm(
            data={"user_rating": invalid, "rating_feedback": "Notes"}
        )
        assert not form.is_valid()
        assert "user_rating" in form.errors


def test_conversationalbi_form_nlq_rate_feedback_optional_and_stripped():
    """Verify rating_feedback is optional and strips leading/trailing whitespace."""
    form = NaturalLanguageQueryRateForm(
        data={"user_rating": "helpful", "rating_feedback": "   Great insight!   "}
    )
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["rating_feedback"] == "Great insight!"

    form_empty = NaturalLanguageQueryRateForm(
        data={"user_rating": "unhelpful", "rating_feedback": ""}
    )
    assert form_empty.is_valid()
    assert form_empty.cleaned_data["rating_feedback"] == ""


def test_conversationalbi_form_nlq_rate_feedback_max_length():
    """Verify rating_feedback respects max length constraint."""
    too_long = "A" * 1001
    form = NaturalLanguageQueryRateForm(
        data={"user_rating": "helpful", "rating_feedback": too_long}
    )
    assert not form.is_valid()
    assert "rating_feedback" in form.errors


# ==============================================================================
# 3. BiConversationSessionForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_form_session_system_field_exclusions():
    """Verify system, thread state, and user fields are excluded from BiConversationSessionForm."""
    form = BiConversationSessionForm()
    expected_fields = {
        "title",
        "session_status",
        "is_pinned",
        "primary_semantic_model",
        "primary_dashboard",
    }
    assert set(form.fields.keys()) == expected_fields

    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "user",
        "context_state",
        "suggested_prompts",
        "suggested_followups",
        "message_count",
        "last_interaction_at",
    ]
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} exposed in BiConversationSessionForm"


@pytest.mark.django_db
def test_conversationalbi_form_session_tenant_scoping(
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
    bi_dashboard_a,
    bi_dashboard_b,
):
    """Verify session FK dropdowns only expose tenant_a models and dashboards."""
    form = BiConversationSessionForm(tenant=tenant_a)

    sm_qs = form.fields["primary_semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs

    dash_qs = form.fields["primary_dashboard"].queryset
    assert bi_dashboard_a in dash_qs
    assert bi_dashboard_b not in dash_qs


@pytest.mark.django_db
def test_conversationalbi_form_session_unscoped_initialization():
    """Verify BiConversationSessionForm initializes cleanly when tenant is None."""
    form = BiConversationSessionForm(tenant=None)
    assert form.fields["primary_semantic_model"].required is False
    assert form.fields["primary_dashboard"].required is False


@pytest.mark.django_db
def test_conversationalbi_form_session_reject_foreign_semantic_model(tenant_a, semantic_model_b):
    """Verify cross-tenant primary_semantic_model is rejected."""
    data = _conversationalbi_valid_session_data(primary_semantic_model=semantic_model_b.pk)
    form = BiConversationSessionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "primary_semantic_model" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_session_reject_foreign_dashboard(tenant_a, bi_dashboard_b):
    """Verify cross-tenant primary_dashboard is rejected."""
    data = _conversationalbi_valid_session_data(primary_dashboard=bi_dashboard_b.pk)
    form = BiConversationSessionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "primary_dashboard" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_session_reject_foreign_helper(
    tenant_a,
    semantic_model_b,
    bi_dashboard_b,
):
    """Verify reject_foreign helper marks foreign records on BiConversationSessionForm."""
    form = BiConversationSessionForm(tenant=tenant_a)
    form._errors = {}
    form.cleaned_data = {
        "primary_semantic_model": semantic_model_b,
        "primary_dashboard": bi_dashboard_b,
    }
    reject_foreign(form, form.cleaned_data, ["primary_semantic_model", "primary_dashboard"])
    assert "primary_semantic_model" in form.errors
    assert "primary_dashboard" in form.errors
    assert form.errors["primary_semantic_model"] == ["That record belongs to another workspace."]
    assert form.errors["primary_dashboard"] == ["That record belongs to another workspace."]


@pytest.mark.django_db
def test_conversationalbi_form_session_title_validation(tenant_a):
    """Verify title is required and cannot be empty or whitespace-only."""
    empty_form = BiConversationSessionForm(
        data=_conversationalbi_valid_session_data(title=""),
        tenant=tenant_a,
    )
    assert not empty_form.is_valid()
    assert "title" in empty_form.errors

    whitespace_form = BiConversationSessionForm(
        data=_conversationalbi_valid_session_data(title="   "),
        tenant=tenant_a,
    )
    assert not whitespace_form.is_valid()
    assert "title" in whitespace_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_session_status_choices(tenant_a):
    """Verify valid and invalid session status choices."""
    valid_statuses = ["active", "closed", "archived"]
    for status in valid_statuses:
        form = BiConversationSessionForm(
            data=_conversationalbi_valid_session_data(session_status=status),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid status {status}: {form.errors}"

    invalid_form = BiConversationSessionForm(
        data=_conversationalbi_valid_session_data(session_status="invalid_status"),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "session_status" in invalid_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_session_clean_suggested_followups(tenant_a):
    """Test suggested followups newline-delimited text conversion and field protection."""
    form = BiConversationSessionForm(tenant=tenant_a)
    assert "suggested_followups" not in form.fields
    assert "suggested_prompts" not in form.fields

    raw_text = "Show forecast for next quarter\n\n  Break down by customer segment  \n\nCompare against FY2025"
    cleaned_lines = _conversationalbi_clean_newline_text(raw_text)
    assert cleaned_lines == [
        "Show forecast for next quarter",
        "Break down by customer segment",
        "Compare against FY2025",
    ]
    assert _conversationalbi_clean_newline_text("") == []
    assert _conversationalbi_clean_newline_text("   \n\n  ") == []


@pytest.mark.django_db
def test_conversationalbi_form_session_optional_fields(tenant_a):
    """Verify primary_semantic_model and primary_dashboard are optional."""
    data = {
        "title": "Minimal Chat Session Thread",
        "session_status": "active",
        "is_pinned": False,
    }
    form = BiConversationSessionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"


@pytest.mark.django_db
def test_conversationalbi_form_session_valid_submission_create_and_save(
    tenant_a,
    admin_user,
    semantic_model_a,
    bi_dashboard_a,
):
    """Verify creating and saving a new BiConversationSession."""
    data = _conversationalbi_valid_session_data(
        primary_semantic_model=semantic_model_a.pk,
        primary_dashboard=bi_dashboard_a.pk,
        is_pinned=True,
    )
    form = BiConversationSessionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.user = admin_user
    instance.number = "BCON-99001"
    instance.save()

    saved = BiConversationSession.objects.get(pk=instance.pk)
    assert saved.title == "Q4 Executive Revenue and Profitability Thread"
    assert saved.tenant == tenant_a
    assert saved.user == admin_user
    assert saved.is_pinned is True
    assert saved.primary_semantic_model == semantic_model_a
    assert saved.primary_dashboard == bi_dashboard_a


@pytest.mark.django_db
def test_conversationalbi_form_session_valid_submission_update(
    tenant_a,
    bi_conversation_session_a,
):
    """Verify updating an existing BiConversationSession instance."""
    edit_data = _conversationalbi_valid_session_data(
        title="Updated Session Thread Title",
        session_status="closed",
        is_pinned=False,
    )
    form = BiConversationSessionForm(data=edit_data, instance=bi_conversation_session_a, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"
    updated = form.save()

    assert updated.pk == bi_conversation_session_a.pk
    assert updated.title == "Updated Session Thread Title"
    assert updated.session_status == "closed"
    assert updated.is_pinned is False


@pytest.mark.django_db
def test_conversationalbi_form_session_widget_classes(tenant_a):
    """Verify widget class attributes on BiConversationSessionForm."""
    form = BiConversationSessionForm(tenant=tenant_a)
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["session_status"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["is_pinned"].widget.attrs.get("class", "")


# ==============================================================================
# 4. BiConversationSessionAskForm Tests
# ==============================================================================


def test_conversationalbi_form_session_ask_valid():
    """Verify valid analytical question submission."""
    form = BiConversationSessionAskForm(
        data={"question_text": "What is our customer acquisition cost trend?"}
    )
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["question_text"] == "What is our customer acquisition cost trend?"


def test_conversationalbi_form_session_ask_empty_or_whitespace():
    """Verify empty or whitespace-only question is rejected with specific error."""
    empty_form = BiConversationSessionAskForm(data={"question_text": ""})
    assert not empty_form.is_valid()
    assert "question_text" in empty_form.errors

    whitespace_form = BiConversationSessionAskForm(data={"question_text": "    "})
    assert not whitespace_form.is_valid()
    assert "question_text" in whitespace_form.errors


def test_conversationalbi_form_session_ask_whitespace_stripping():
    """Verify leading and trailing whitespace are stripped."""
    form = BiConversationSessionAskForm(
        data={"question_text": "   Show quarterly revenue by product   "}
    )
    assert form.is_valid()
    assert form.cleaned_data["question_text"] == "Show quarterly revenue by product"


def test_conversationalbi_form_session_ask_max_length():
    """Verify question_text max length (500 chars)."""
    too_long = "W" * 501
    form = BiConversationSessionAskForm(data={"question_text": too_long})
    assert not form.is_valid()
    assert "question_text" in form.errors


# ==============================================================================
# 5. NarrativeExplanationForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_form_narrative_system_field_exclusions():
    """Verify system, script, and status fields (M9) are excluded from NarrativeExplanationForm."""
    form = NarrativeExplanationForm()
    expected_fields = {
        "title",
        "headline",
        "target_artifact_type",
        "dashboard",
        "report",
        "kpi",
        "query",
        "insight",
        "narrative_style",
        "narrative_body",
        "top_positive_driver",
        "top_negative_driver",
        "language",
    }
    assert set(form.fields.keys()) == expected_fields

    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "created_by",
        "status",  # Excluded per finding M9 to prevent mass assignment
        "audio_ready_script",
        "key_takeaways",
    ]
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} exposed in NarrativeExplanationForm"


@pytest.mark.django_db
def test_conversationalbi_form_narrative_status_excluded_m9(tenant_a):
    """Ensure status cannot be manipulated via mass assignment in NarrativeExplanationForm (M9)."""
    data = _conversationalbi_valid_narrative_data(status="published")
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert "status" not in form.fields
    if form.is_valid():
        instance = form.save(commit=False)
        assert instance.status == "generated"


@pytest.mark.django_db
def test_conversationalbi_form_narrative_tenant_scoping(
    tenant_a,
    tenant_b,
    bi_dashboard_a,
    bi_dashboard_b,
    kpi_definition_a,
    kpi_definition_b,
    natural_language_query_a,
    natural_language_query_b,
    augmented_insight_a,
    augmented_insight_b,
):
    """Verify all 5 foreign key querysets are strictly tenant-scoped."""
    report_a = _conversationalbi_create_report(tenant_a, name="Report A", slug="narrative-rep-a")
    report_b = _conversationalbi_create_report(tenant_b, name="Report B", slug="narrative-rep-b")

    form = NarrativeExplanationForm(tenant=tenant_a)

    dash_qs = form.fields["dashboard"].queryset
    assert bi_dashboard_a in dash_qs
    assert bi_dashboard_b not in dash_qs

    rep_qs = form.fields["report"].queryset
    assert report_a in rep_qs
    assert report_b not in rep_qs

    kpi_qs = form.fields["kpi"].queryset
    assert kpi_definition_a in kpi_qs
    assert kpi_definition_b not in kpi_qs

    query_qs = form.fields["query"].queryset
    assert natural_language_query_a in query_qs
    assert natural_language_query_b not in query_qs

    insight_qs = form.fields["insight"].queryset
    assert augmented_insight_a in insight_qs
    assert augmented_insight_b not in insight_qs


@pytest.mark.django_db
def test_conversationalbi_form_narrative_unscoped_initialization():
    """Verify NarrativeExplanationForm initializes safely when tenant is None."""
    form = NarrativeExplanationForm(tenant=None)
    assert form.fields["dashboard"].required is False
    assert form.fields["report"].required is False
    assert form.fields["kpi"].required is False
    assert form.fields["query"].required is False
    assert form.fields["insight"].required is False


@pytest.mark.django_db
def test_conversationalbi_form_narrative_reject_foreign_dashboard(tenant_a, bi_dashboard_b):
    """Verify cross-tenant dashboard is rejected."""
    data = _conversationalbi_valid_narrative_data(dashboard=bi_dashboard_b.pk)
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_reject_foreign_report(tenant_a, tenant_b):
    """Verify cross-tenant report is rejected."""
    report_b = _conversationalbi_create_report(tenant_b, name="Foreign Report", slug="foreign-report")
    data = _conversationalbi_valid_narrative_data(report=report_b.pk)
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_reject_foreign_kpi(tenant_a, kpi_definition_b):
    """Verify cross-tenant KPI is rejected."""
    data = _conversationalbi_valid_narrative_data(kpi=kpi_definition_b.pk)
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_reject_foreign_query(tenant_a, natural_language_query_b):
    """Verify cross-tenant query is rejected."""
    data = _conversationalbi_valid_narrative_data(query=natural_language_query_b.pk)
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "query" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_reject_foreign_insight(tenant_a, augmented_insight_b):
    """Verify cross-tenant augmented insight is rejected."""
    data = _conversationalbi_valid_narrative_data(insight=augmented_insight_b.pk)
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "insight" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_reject_foreign_helper(
    tenant_a,
    bi_dashboard_b,
    kpi_definition_b,
    natural_language_query_b,
    augmented_insight_b,
):
    """Verify reject_foreign helper marks foreign records on NarrativeExplanationForm."""
    form = NarrativeExplanationForm(tenant=tenant_a)
    form._errors = {}
    form.cleaned_data = {
        "dashboard": bi_dashboard_b,
        "kpi": kpi_definition_b,
        "query": natural_language_query_b,
        "insight": augmented_insight_b,
    }
    reject_foreign(form, form.cleaned_data, ["dashboard", "kpi", "query", "insight"])
    for name in ["dashboard", "kpi", "query", "insight"]:
        assert name in form.errors
        assert form.errors[name] == ["That record belongs to another workspace."]


@pytest.mark.django_db
def test_conversationalbi_form_narrative_clean_key_takeaways(tenant_a):
    """Test key takeaways newline-delimited text conversion and field protection."""
    form = NarrativeExplanationForm(tenant=tenant_a)
    assert "key_takeaways" not in form.fields

    raw_text = "Gross margin widened by 340 bps\n\n  Operating cash flow hit record 8.4M  \n\nRegional backlog fell 12%"
    cleaned_lines = _conversationalbi_clean_newline_text(raw_text)
    assert cleaned_lines == [
        "Gross margin widened by 340 bps",
        "Operating cash flow hit record 8.4M",
        "Regional backlog fell 12%",
    ]
    assert _conversationalbi_clean_newline_text("") == []
    assert _conversationalbi_clean_newline_text("   \n\n ") == []


@pytest.mark.django_db
def test_conversationalbi_form_narrative_required_fields(tenant_a):
    """Verify title, headline, and narrative_body are required."""
    form = NarrativeExplanationForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "headline" in form.errors
    assert "narrative_body" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_target_artifact_choices(tenant_a):
    """Verify valid and invalid target artifact type choices."""
    valid_choices = [
        "dashboard",
        "report",
        "kpi_scorecard",
        "query_result",
        "custom_dataset",
    ]
    for choice in valid_choices:
        form = NarrativeExplanationForm(
            data=_conversationalbi_valid_narrative_data(target_artifact_type=choice),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid choice {choice}: {form.errors}"

    invalid_form = NarrativeExplanationForm(
        data=_conversationalbi_valid_narrative_data(target_artifact_type="arbitrary_file"),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "target_artifact_type" in invalid_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_style_choices(tenant_a):
    """Verify valid and invalid narrative style choices."""
    valid_styles = [
        "executive_briefing",
        "analytical_deepdive",
        "bulleted_highlights",
        "anomaly_alert",
        "spoken_voice_script",
    ]
    for style in valid_styles:
        form = NarrativeExplanationForm(
            data=_conversationalbi_valid_narrative_data(narrative_style=style),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid style {style}: {form.errors}"

    invalid_form = NarrativeExplanationForm(
        data=_conversationalbi_valid_narrative_data(narrative_style="poetic_verse"),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "narrative_style" in invalid_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_narrative_optional_fields(tenant_a):
    """Verify target artifact FKs, driver callouts, and language default."""
    data = {
        "title": "Minimal Executive Summary",
        "headline": "Q3 performance aligned with budget target.",
        "target_artifact_type": "dashboard",
        "narrative_style": "executive_briefing",
        "narrative_body": "Detailed executive summary commentary with no attached FKs.",
        "top_positive_driver": "",
        "top_negative_driver": "",
        "language": "en",
    }
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"


@pytest.mark.django_db
def test_conversationalbi_form_narrative_valid_submission_create_and_save(
    tenant_a,
    admin_user,
    bi_dashboard_a,
    kpi_definition_a,
    natural_language_query_a,
):
    """Verify creating and saving a NarrativeExplanation instance."""
    data = _conversationalbi_valid_narrative_data(
        dashboard=bi_dashboard_a.pk,
        kpi=kpi_definition_a.pk,
        query=natural_language_query_a.pk,
    )
    form = NarrativeExplanationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.created_by = admin_user
    instance.number = "BNLG-99001"
    instance.save()

    saved = NarrativeExplanation.objects.get(pk=instance.pk)
    assert saved.title == "Q3 Executive Performance Briefing"
    assert saved.tenant == tenant_a
    assert saved.dashboard == bi_dashboard_a
    assert saved.kpi == kpi_definition_a
    assert saved.query == natural_language_query_a
    assert saved.created_by == admin_user
    assert saved.narrative_style == "executive_briefing"


@pytest.mark.django_db
def test_conversationalbi_form_narrative_valid_submission_update(
    tenant_a,
    narrative_explanation_a,
):
    """Verify updating an existing NarrativeExplanation instance."""
    edit_data = _conversationalbi_valid_narrative_data(
        title="Revised Q3 Briefing Headline",
        headline="Operating margin outperformed revised plan by 4.1%",
        narrative_style="analytical_deepdive",
    )
    form = NarrativeExplanationForm(data=edit_data, instance=narrative_explanation_a, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"
    updated = form.save()

    assert updated.pk == narrative_explanation_a.pk
    assert updated.title == "Revised Q3 Briefing Headline"
    assert updated.headline == "Operating margin outperformed revised plan by 4.1%"
    assert updated.narrative_style == "analytical_deepdive"


# ==============================================================================
# 6. SearchDiscoveryIndexForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_form_search_index_system_field_exclusions():
    """Verify system and telemetry counters are excluded from SearchDiscoveryIndexForm."""
    form = SearchDiscoveryIndexForm()
    expected_fields = {
        "asset_name",
        "asset_type",
        "target_url",
        "description",
        "category",
        "synonyms",
        "search_keywords",
        "semantic_model",
        "dashboard",
        "report",
        "kpi",
        "warehouse_table",
        "glossary_term",
        "relevance_weight",
        "is_featured",
        "is_verified",
    }
    assert set(form.fields.keys()) == expected_fields

    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "search_hit_count",
        "view_count",
    ]
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} exposed in SearchDiscoveryIndexForm"


@pytest.mark.django_db
def test_conversationalbi_form_search_index_tenant_scoping(
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
    bi_dashboard_a,
    bi_dashboard_b,
    kpi_definition_a,
    kpi_definition_b,
    warehouse_table_a,
    warehouse_table_b,
    glossary_term_a,
    glossary_term_b,
):
    """Verify all 6 asset reference querysets are strictly tenant-scoped."""
    report_a = _conversationalbi_create_report(tenant_a, name="Report A", slug="search-rep-a")
    report_b = _conversationalbi_create_report(tenant_b, name="Report B", slug="search-rep-b")

    form = SearchDiscoveryIndexForm(tenant=tenant_a)

    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs

    dash_qs = form.fields["dashboard"].queryset
    assert bi_dashboard_a in dash_qs
    assert bi_dashboard_b not in dash_qs

    rep_qs = form.fields["report"].queryset
    assert report_a in rep_qs
    assert report_b not in rep_qs

    kpi_qs = form.fields["kpi"].queryset
    assert kpi_definition_a in kpi_qs
    assert kpi_definition_b not in kpi_qs

    tbl_qs = form.fields["warehouse_table"].queryset
    assert warehouse_table_a in tbl_qs
    assert warehouse_table_b not in tbl_qs

    term_qs = form.fields["glossary_term"].queryset
    assert glossary_term_a in term_qs
    assert glossary_term_b not in term_qs


@pytest.mark.django_db
def test_conversationalbi_form_search_index_unscoped_initialization():
    """Verify SearchDiscoveryIndexForm initializes cleanly without tenant."""
    form = SearchDiscoveryIndexForm(tenant=None)
    assert form.fields["semantic_model"].required is False
    assert form.fields["dashboard"].required is False
    assert form.fields["report"].required is False
    assert form.fields["kpi"].required is False
    assert form.fields["warehouse_table"].required is False
    assert form.fields["glossary_term"].required is False


@pytest.mark.django_db
def test_conversationalbi_form_search_index_reject_foreign_semantic_model(tenant_a, semantic_model_b):
    """Verify cross-tenant semantic model is rejected."""
    data = _conversationalbi_valid_search_index_data(semantic_model=semantic_model_b.pk)
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_reject_foreign_dashboard(tenant_a, bi_dashboard_b):
    """Verify cross-tenant dashboard is rejected."""
    data = _conversationalbi_valid_search_index_data(dashboard=bi_dashboard_b.pk)
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_reject_foreign_report(tenant_a, tenant_b):
    """Verify cross-tenant report is rejected."""
    report_b = _conversationalbi_create_report(tenant_b, name="Foreign Search Report", slug="foreign-search-rep")
    data = _conversationalbi_valid_search_index_data(report=report_b.pk)
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_reject_foreign_kpi(tenant_a, kpi_definition_b):
    """Verify cross-tenant KPI is rejected."""
    data = _conversationalbi_valid_search_index_data(kpi=kpi_definition_b.pk)
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_reject_foreign_warehouse_table(tenant_a, warehouse_table_b):
    """Verify cross-tenant warehouse table is rejected."""
    data = _conversationalbi_valid_search_index_data(warehouse_table=warehouse_table_b.pk)
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_reject_foreign_glossary_term(tenant_a, glossary_term_b):
    """Verify cross-tenant glossary term is rejected."""
    data = _conversationalbi_valid_search_index_data(glossary_term=glossary_term_b.pk)
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "glossary_term" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_reject_foreign_helper(
    tenant_a,
    semantic_model_b,
    bi_dashboard_b,
    kpi_definition_b,
    warehouse_table_b,
    glossary_term_b,
):
    """Verify reject_foreign helper marks foreign records on SearchDiscoveryIndexForm."""
    form = SearchDiscoveryIndexForm(tenant=tenant_a)
    form._errors = {}
    form.cleaned_data = {
        "semantic_model": semantic_model_b,
        "dashboard": bi_dashboard_b,
        "kpi": kpi_definition_b,
        "warehouse_table": warehouse_table_b,
        "glossary_term": glossary_term_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["semantic_model", "dashboard", "kpi", "warehouse_table", "glossary_term"],
    )
    for name in ["semantic_model", "dashboard", "kpi", "warehouse_table", "glossary_term"]:
        assert name in form.errors
        assert form.errors[name] == ["That record belongs to another workspace."]


@pytest.mark.django_db
def test_conversationalbi_form_search_index_clean_target_url_valid():
    """Verify clean_target_url accepts valid relative and absolute HTTP(S) URLs."""
    form = SearchDiscoveryIndexForm()

    valid_urls = [
        "/bi/dashboards/1/",
        "/bi/reports/42/",
        "https://example.com/bi/reports/1/",
        "http://nav-erp.local/bi/explore/",
    ]
    for url in valid_urls:
        form.cleaned_data = {"target_url": url}
        assert form.clean_target_url() == url


@pytest.mark.django_db
def test_conversationalbi_form_search_index_clean_target_url_reject_protocol_relative():
    """Verify protocol-relative URLs starting with // are rejected with ValidationError (M8)."""
    form = SearchDiscoveryIndexForm()
    form.cleaned_data = {"target_url": "//evil.com/phishing"}
    with pytest.raises(ValidationError) as excinfo:
        form.clean_target_url()
    assert "Protocol-relative URLs are not allowed" in str(excinfo.value)


@pytest.mark.django_db
def test_conversationalbi_form_search_index_clean_target_url_reject_invalid_schemes():
    """Verify URLs without leading slash or non-HTTP schemes are rejected."""
    form = SearchDiscoveryIndexForm()
    invalid_urls = [
        "dashboards/1/",
        "javascript:alert(1)",
        "ftp://storage.nav-erp.local/exports",
        "data:text/html;base64,PHNjcmlwdD4=",
    ]
    for invalid in invalid_urls:
        form.cleaned_data = {"target_url": invalid}
        with pytest.raises(ValidationError) as excinfo:
            form.clean_target_url()
        assert "Target URL must start with a leading slash" in str(excinfo.value)


@pytest.mark.django_db
def test_conversationalbi_form_search_index_clean_synonyms_comma_separated():
    """Verify clean_synonyms parses comma-separated string into stripped non-empty list."""
    form = SearchDiscoveryIndexForm()
    form.cleaned_data = {"synonyms": "sales, revenue , turnover  , ,  top line "}
    result = form.clean_synonyms()
    assert result == ["sales", "revenue", "turnover", "top line"]


@pytest.mark.django_db
def test_conversationalbi_form_search_index_clean_synonyms_empty_inputs():
    """Verify clean_synonyms returns empty list on empty string, whitespace, or None."""
    form = SearchDiscoveryIndexForm()
    for empty_val in ["", "   ", None, []]:
        form.cleaned_data = {"synonyms": empty_val}
        assert form.clean_synonyms() == []


@pytest.mark.django_db
def test_conversationalbi_form_search_index_clean_synonyms_json_array():
    """Verify clean_synonyms parses JSON-encoded array strings."""
    form = SearchDiscoveryIndexForm()
    form.cleaned_data = {"synonyms": '["income", "turnover", "arr"]'}
    result = form.clean_synonyms()
    assert result == ["income", "turnover", "arr"]


@pytest.mark.django_db
def test_conversationalbi_form_search_index_clean_synonyms_list_input():
    """Verify clean_synonyms handles already-parsed python list with extra whitespace."""
    form = SearchDiscoveryIndexForm()
    form.cleaned_data = {"synonyms": [" revenue ", "  ebitda  ", ""]}
    result = form.clean_synonyms()
    assert result == ["revenue", "ebitda"]


@pytest.mark.django_db
def test_conversationalbi_form_search_index_numeric_bounds(tenant_a):
    """Verify relevance_weight numeric bounds."""
    for valid_weight in ["0.10", "1.00", "5.50", "99.99"]:
        form = SearchDiscoveryIndexForm(
            data=_conversationalbi_valid_search_index_data(relevance_weight=valid_weight),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid weight {valid_weight}: {form.errors}"

    invalid_form = SearchDiscoveryIndexForm(
        data=_conversationalbi_valid_search_index_data(relevance_weight="not_a_weight"),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "relevance_weight" in invalid_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_asset_type_choices(tenant_a):
    """Verify valid and invalid asset_type choices."""
    valid_types = [
        "dashboard",
        "report",
        "kpi",
        "semantic_model",
        "warehouse_table",
        "glossary_term",
        "ad_hoc_query",
    ]
    for asset_type in valid_types:
        form = SearchDiscoveryIndexForm(
            data=_conversationalbi_valid_search_index_data(asset_type=asset_type),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Failed on valid asset_type {asset_type}: {form.errors}"

    invalid_form = SearchDiscoveryIndexForm(
        data=_conversationalbi_valid_search_index_data(asset_type="excel_spreadsheet"),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "asset_type" in invalid_form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_required_fields(tenant_a):
    """Verify asset_name is required for form validation."""
    form = SearchDiscoveryIndexForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset_name" in form.errors


@pytest.mark.django_db
def test_conversationalbi_form_search_index_optional_fields(tenant_a):
    """Verify description, category, keywords, and foreign keys are optional."""
    data = {
        "asset_name": "Barebones Analytical Asset",
        "asset_type": "report",
        "target_url": "/bi/reports/12/",
        "description": "",
        "category": "",
        "synonyms": "",
        "search_keywords": "",
        "relevance_weight": "1.00",
        "is_featured": False,
        "is_verified": True,
    }
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"


@pytest.mark.django_db
def test_conversationalbi_form_search_index_valid_submission_create_and_save(
    tenant_a,
    bi_dashboard_a,
    semantic_model_a,
    kpi_definition_a,
):
    """Verify creating and saving a SearchDiscoveryIndex instance."""
    data = _conversationalbi_valid_search_index_data(
        dashboard=bi_dashboard_a.pk,
        semantic_model=semantic_model_a.pk,
        kpi=kpi_definition_a.pk,
        synonyms=json.dumps(["revenue", "arr", "sales"]),
    )
    form = SearchDiscoveryIndexForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.number = "BSDI-99001"
    instance.save()

    saved = SearchDiscoveryIndex.objects.get(pk=instance.pk)
    assert saved.asset_name == "Executive Profitability Overview Dashboard"
    assert saved.tenant == tenant_a
    assert saved.dashboard == bi_dashboard_a
    assert saved.semantic_model == semantic_model_a
    assert saved.kpi == kpi_definition_a
    assert saved.synonyms == ["revenue", "arr", "sales"]
    assert saved.relevance_weight == Decimal("1.25")
    assert saved.is_featured is True
    assert saved.is_verified is True


@pytest.mark.django_db
def test_conversationalbi_form_search_index_valid_submission_update(
    tenant_a,
    search_discovery_index_a,
):
    """Verify updating an existing SearchDiscoveryIndex instance."""
    edit_data = _conversationalbi_valid_search_index_data(
        asset_name="Updated Enterprise Revenue Portal",
        category="Sales & Operations",
        synonyms=json.dumps(["income", "topline", "growth"]),
        relevance_weight="2.00",
        is_featured=False,
    )
    form = SearchDiscoveryIndexForm(data=edit_data, instance=search_discovery_index_a, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"
    updated = form.save()

    assert updated.pk == search_discovery_index_a.pk
    assert updated.asset_name == "Updated Enterprise Revenue Portal"
    assert updated.category == "Sales & Operations"
    assert updated.synonyms == ["income", "topline", "growth"]
    assert updated.relevance_weight == Decimal("2.00")
    assert updated.is_featured is False


# ==============================================================================
# 7. SearchDiscoveryIndexReweightForm Tests
# ==============================================================================


def test_conversationalbi_form_search_reweight_valid_values():
    """Verify valid weights in SearchDiscoveryIndexReweightForm."""
    valid_cases = [
        ("0.10", Decimal("0.10")),
        ("1.00", Decimal("1.00")),
        ("1.25", Decimal("1.25")),
        ("50.00", Decimal("50.00")),
        ("99.99", Decimal("99.99")),
    ]
    for weight_str, expected in valid_cases:
        form = SearchDiscoveryIndexReweightForm(data={"weight": weight_str})
        assert form.is_valid(), f"Failed on weight {weight_str}: {form.errors}"
        assert form.cleaned_data["weight"] == expected


def test_conversationalbi_form_search_reweight_empty_returns_none():
    """Verify empty weight returns None (allowing default increment logic)."""
    form = SearchDiscoveryIndexReweightForm(data={"weight": ""})
    assert form.is_valid()
    assert form.cleaned_data["weight"] is None

    form_spaces = SearchDiscoveryIndexReweightForm(data={"weight": "   "})
    assert form_spaces.is_valid()
    assert form_spaces.cleaned_data["weight"] is None


def test_conversationalbi_form_search_reweight_non_finite_rejected():
    """Verify NaN, Infinity, -Infinity are rejected."""
    for non_finite in ["NaN", "Infinity", "-Infinity", "snan", "+inf"]:
        form = SearchDiscoveryIndexReweightForm(data={"weight": non_finite})
        assert not form.is_valid(), f"Expected failure on {non_finite}"
        assert "weight" in form.errors


def test_conversationalbi_form_search_reweight_negative_rejected():
    """Verify negative weights are rejected."""
    for neg in ["-0.01", "-1.00", "-50.00"]:
        form = SearchDiscoveryIndexReweightForm(data={"weight": neg})
        assert not form.is_valid()
        assert "weight" in form.errors


def test_conversationalbi_form_search_reweight_out_of_bounds():
    """Verify weights below 0.10 or above 99.99 are rejected."""
    form_low = SearchDiscoveryIndexReweightForm(data={"weight": "0.05"})
    assert not form_low.is_valid()
    assert "weight" in form_low.errors

    form_high = SearchDiscoveryIndexReweightForm(data={"weight": "100.00"})
    assert not form_high.is_valid()
    assert "weight" in form_high.errors


def test_conversationalbi_form_search_reweight_non_numeric_rejected():
    """Verify non-numeric strings are rejected."""
    for bad in ["abc", "one", "1.2.3", "reweight"]:
        form = SearchDiscoveryIndexReweightForm(data={"weight": bad})
        assert not form.is_valid()
        assert "weight" in form.errors
