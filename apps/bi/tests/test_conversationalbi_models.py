"""Unit tests for Sub-module 10.15 Natural Language & Conversational BI models.

Models covered:
- NaturalLanguageQuery (BNLQ)
- BiConversationSession (BCON)
- NarrativeExplanation (BNLG)
- SearchDiscoveryIndex (BSDI)
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.bi.models import (
    BiConversationSession,
    NarrativeExplanation,
    NaturalLanguageQuery,
    SearchDiscoveryIndex,
)
from apps.core.models import Tenant

_CONVERSATIONALBI_VALID_BADGES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-slate",
    "badge-muted",
}


def _conversationalbi_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


def _conversationalbi_assert_valid_badge(badge):
    """Helper to verify badge is in valid color-named badge classes and not purple or indigo."""
    assert badge in _CONVERSATIONALBI_VALID_BADGES
    assert badge != "badge-purple"
    assert badge != "badge-indigo"
    assert badge.startswith("badge-")


def _conversationalbi_create_session(tenant, user, **kwargs):
    """Helper to create a BiConversationSession with defaults."""
    defaults = {
        "title": "Executive Revenue Analysis Thread",
        "session_status": "active",
    }
    defaults.update(kwargs)
    return BiConversationSession.objects.create(tenant=tenant, user=user, **defaults)


def _conversationalbi_create_nlq(tenant, user=None, session=None, **kwargs):
    """Helper to create a NaturalLanguageQuery with defaults."""
    defaults = {
        "query_text": "What was total revenue by region in Q3 2026?",
        "user": user,
        "conversation_session": session,
    }
    defaults.update(kwargs)
    return NaturalLanguageQuery.objects.create(tenant=tenant, **defaults)


def _conversationalbi_create_narrative(tenant, created_by=None, **kwargs):
    """Helper to create a NarrativeExplanation with defaults."""
    defaults = {
        "title": "Q3 Revenue Variance Narrative",
        "headline": "Q3 revenue grew 14% quarter-over-quarter led by enterprise renewals.",
        "narrative_body": "Total revenue reached 12.8M against plan. North America was the primary driver.",
        "created_by": created_by,
    }
    defaults.update(kwargs)
    return NarrativeExplanation.objects.create(tenant=tenant, **defaults)


def _conversationalbi_create_search_index(tenant, **kwargs):
    """Helper to create a SearchDiscoveryIndex with defaults."""
    defaults = {
        "asset_name": "Executive Profitability Dashboard",
        "asset_type": "dashboard",
        "target_url": "/bi/dashboards/1/",
    }
    defaults.update(kwargs)
    return SearchDiscoveryIndex.objects.create(tenant=tenant, **defaults)


# ===========================================================================
# 1. NaturalLanguageQuery Model Tests (BNLQ)
# ===========================================================================


@pytest.mark.django_db
def test_conversationalbi_nlq_defaults_and_autonumber(tenant_a, admin_user):
    """Test NaturalLanguageQuery creation, BNLQ prefix, defaults, __str__, and URL."""
    nlq = NaturalLanguageQuery.objects.create(
        tenant=tenant_a,
        query_text="What was our total revenue by product line for Q3?",
        user=admin_user,
    )
    assert nlq.NUMBER_PREFIX == "BNLQ"
    assert nlq.number.startswith("BNLQ-")
    assert nlq.input_modality == "text"
    assert nlq.intent_type == "metric_lookup"
    assert nlq.chart_type == "bar_chart"
    assert nlq.execution_status == "completed"
    assert nlq.user_rating == "unrated"
    assert nlq.confidence_score == Decimal("85.00")
    assert nlq.execution_duration_ms == 0
    assert nlq.audio_duration_seconds == Decimal("0.00")
    assert nlq.parsed_measures == []
    assert nlq.parsed_dimensions == []
    assert nlq.parsed_filters == {}
    assert nlq.chart_config == {}
    assert nlq.result_summary == {}
    assert nlq.generated_sql == ""
    assert nlq.user_feedback_notes == ""
    assert str(nlq) == f"{nlq.number} — What was our total revenue by product line for Q3?"
    assert nlq.get_absolute_url() == f"/bi/natural-language-queries/{nlq.pk}/"


@pytest.mark.django_db
def test_conversationalbi_nlq_autonumber_increment_and_tenant_isolation(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Test autonumber incrementing within a tenant and isolation across tenants."""
    q1 = _conversationalbi_create_nlq(tenant_a, user=admin_user)
    q2 = _conversationalbi_create_nlq(tenant_a, user=admin_user)
    assert q1.number.startswith("BNLQ-")
    assert q2.number.startswith("BNLQ-")
    n1 = int(q1.number.split("-")[1])
    n2 = int(q2.number.split("-")[1])
    assert n2 == n1 + 1

    # Cross-tenant query gets valid prefix and isolated numbering
    q_b = _conversationalbi_create_nlq(tenant_b, user=admin_user_b)
    assert q_b.tenant == tenant_b
    assert q_b.number.startswith("BNLQ-")


@pytest.mark.django_db
def test_conversationalbi_nlq_str_representation(tenant_a, admin_user):
    """Test NaturalLanguageQuery __str__ behavior for short and long text (> 50 chars)."""
    short_query = "What is ARR?"
    q_short = _conversationalbi_create_nlq(tenant_a, user=admin_user, query_text=short_query)
    assert str(q_short) == f"{q_short.number} — {short_query}"

    exact_50_chars = "A" * 50
    q_50 = _conversationalbi_create_nlq(tenant_a, user=admin_user, query_text=exact_50_chars)
    assert str(q_50) == f"{q_50.number} — {exact_50_chars}"

    long_query = "What was the total gross margin by sales region and product category in 2026?"
    q_long = _conversationalbi_create_nlq(tenant_a, user=admin_user, query_text=long_query)
    expected_truncated = long_query[:47] + "..."
    assert str(q_long) == f"{q_long.number} — {expected_truncated}"


@pytest.mark.django_db
def test_conversationalbi_nlq_get_absolute_url(tenant_a, admin_user):
    """Test get_absolute_url maps to bi:natural_language_query_detail."""
    nlq = _conversationalbi_create_nlq(tenant_a, user=admin_user)
    assert nlq.get_absolute_url() == f"/bi/natural-language-queries/{nlq.pk}/"


@pytest.mark.django_db
def test_conversationalbi_nlq_choices():
    """Test choices enumerations for NaturalLanguageQuery."""
    modality_keys = _conversationalbi_choice_keys(NaturalLanguageQuery.INPUT_MODALITY_CHOICES)
    assert "text" in modality_keys
    assert "voice" in modality_keys
    assert "api" in modality_keys

    intent_keys = _conversationalbi_choice_keys(NaturalLanguageQuery.INTENT_TYPE_CHOICES)
    assert "metric_lookup" in intent_keys
    assert "trend_analysis" in intent_keys
    assert "ranking_top_bottom" in intent_keys
    assert "comparative_analysis" in intent_keys
    assert "distribution" in intent_keys
    assert "correlation" in intent_keys
    assert "drill_down" in intent_keys

    chart_keys = _conversationalbi_choice_keys(NaturalLanguageQuery.CHART_TYPE_CHOICES)
    assert "metric_card" in chart_keys
    assert "bar_chart" in chart_keys
    assert "horizontal_bar" in chart_keys
    assert "line_chart" in chart_keys
    assert "donut_chart" in chart_keys
    assert "scatter_plot" in chart_keys
    assert "pivot_table" in chart_keys
    assert "data_table" in chart_keys

    status_keys = _conversationalbi_choice_keys(NaturalLanguageQuery.EXECUTION_STATUS_CHOICES)
    assert "pending" in status_keys
    assert "completed" in status_keys
    assert "failed" in status_keys
    assert "ambiguous" in status_keys

    rating_keys = _conversationalbi_choice_keys(NaturalLanguageQuery.USER_RATING_CHOICES)
    assert "unrated" in rating_keys
    assert "helpful" in rating_keys
    assert "unhelpful" in rating_keys


@pytest.mark.django_db
def test_conversationalbi_nlq_badge_colors(tenant_a):
    """Test computed status_badge_color, modality_badge_color, rating_badge_color on NaturalLanguageQuery."""
    nlq = NaturalLanguageQuery(tenant=tenant_a, query_text="Test Badge Query")

    # Status badge color
    nlq.execution_status = "completed"
    assert nlq.status_badge_color == "badge-green"
    _conversationalbi_assert_valid_badge(nlq.status_badge_color)

    nlq.execution_status = "pending"
    assert nlq.status_badge_color == "badge-amber"
    _conversationalbi_assert_valid_badge(nlq.status_badge_color)

    nlq.execution_status = "ambiguous"
    assert nlq.status_badge_color == "badge-info"
    _conversationalbi_assert_valid_badge(nlq.status_badge_color)

    nlq.execution_status = "failed"
    assert nlq.status_badge_color == "badge-red"
    _conversationalbi_assert_valid_badge(nlq.status_badge_color)

    nlq.execution_status = "unknown_status"
    assert nlq.status_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(nlq.status_badge_color)

    # Modality badge color
    nlq.input_modality = "voice"
    assert nlq.modality_badge_color == "badge-info"
    _conversationalbi_assert_valid_badge(nlq.modality_badge_color)

    nlq.input_modality = "api"
    assert nlq.modality_badge_color == "badge-info"
    _conversationalbi_assert_valid_badge(nlq.modality_badge_color)

    nlq.input_modality = "text"
    assert nlq.modality_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(nlq.modality_badge_color)

    # Rating badge color
    nlq.user_rating = "helpful"
    assert nlq.rating_badge_color == "badge-green"
    _conversationalbi_assert_valid_badge(nlq.rating_badge_color)

    nlq.user_rating = "unhelpful"
    assert nlq.rating_badge_color == "badge-red"
    _conversationalbi_assert_valid_badge(nlq.rating_badge_color)

    nlq.user_rating = "unrated"
    assert nlq.rating_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(nlq.rating_badge_color)


@pytest.mark.django_db
def test_conversationalbi_nlq_json_fields(tenant_a, admin_user):
    """Test parsed_measures, parsed_dimensions, parsed_filters, chart_config, result_summary serialization."""
    measures = ["gross_revenue", "discount_amount", "net_revenue"]
    dimensions = ["sales_territory", "fiscal_quarter"]
    filters = {"territory": "EMEA", "year": 2026, "active_only": True}
    chart_cfg = {
        "type": "bar",
        "data": {"labels": ["Q1", "Q2", "Q3"], "datasets": [{"data": [120, 150, 180]}]},
        "options": {"responsive": True},
    }
    summary = {"total_rows": 3, "headline_metric": 450000}

    nlq = NaturalLanguageQuery.objects.create(
        tenant=tenant_a,
        query_text="Complex parsed analytical query",
        user=admin_user,
        parsed_measures=measures,
        parsed_dimensions=dimensions,
        parsed_filters=filters,
        chart_config=chart_cfg,
        result_summary=summary,
    )

    reloaded = NaturalLanguageQuery.objects.get(pk=nlq.pk)
    assert reloaded.parsed_measures == measures
    assert reloaded.parsed_dimensions == dimensions
    assert reloaded.parsed_filters == filters
    assert reloaded.chart_config == chart_cfg
    assert reloaded.result_summary == summary


@pytest.mark.django_db
def test_conversationalbi_nlq_unique_constraint(tenant_a, tenant_b, admin_user, admin_user_b):
    """Verify unique constraint on (tenant, number) for NaturalLanguageQuery."""
    q1 = _conversationalbi_create_nlq(tenant_a, user=admin_user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NaturalLanguageQuery.objects.create(
                tenant=tenant_a,
                number=q1.number,
                query_text="Duplicate number query in same tenant",
            )

    # Reusing same number across distinct tenants must succeed
    q_b = NaturalLanguageQuery.objects.create(
        tenant=tenant_b,
        number=q1.number,
        query_text="Same number in Tenant B",
        user=admin_user_b,
    )
    assert q_b.number == q1.number
    assert q_b.tenant == tenant_b


@pytest.mark.django_db
def test_conversationalbi_nlq_foreign_keys_and_cascade(
    tenant_a, admin_user, semantic_model_a, warehouse_table_a, kpi_definition_a
):
    """Test foreign keys and SET_NULL behavior on NaturalLanguageQuery."""
    User = get_user_model()
    temp_user = User.objects.create_user(
        email="temp_nlq@example.com", username="temp_nlq_user", password="password123"
    )
    session = _conversationalbi_create_session(tenant_a, user=admin_user)

    nlq = NaturalLanguageQuery.objects.create(
        tenant=tenant_a,
        query_text="Foreign key linkage verification query",
        user=temp_user,
        conversation_session=session,
        semantic_model=semantic_model_a,
        warehouse_table=warehouse_table_a,
        kpi_definition=kpi_definition_a,
    )

    # Assert related reverse managers
    assert nlq in session.queries.all()
    assert nlq in temp_user.nlq_queries.all()
    assert nlq in semantic_model_a.nlq_queries.all()
    assert nlq in warehouse_table_a.nlq_queries.all()
    assert nlq in kpi_definition_a.nlq_queries.all()

    # Test SET_NULL on deleting user
    temp_user.delete()
    nlq.refresh_from_db()
    assert nlq.user is None

    # Test SET_NULL on deleting session
    session.delete()
    nlq.refresh_from_db()
    assert nlq.conversation_session is None


@pytest.mark.django_db
def test_conversationalbi_nlq_ordering_and_indexes():
    """Verify NaturalLanguageQuery Meta ordering and defined indexes."""
    assert NaturalLanguageQuery._meta.ordering == ["-created_at", "-id"]
    index_names = [idx.name for idx in NaturalLanguageQuery._meta.indexes]
    assert "idx_bnlq_ten_mod" in index_names
    assert "idx_bnlq_ten_intent" in index_names
    assert "idx_bnlq_ten_status" in index_names
    assert "idx_bnlq_ten_created" in index_names


# ===========================================================================
# 2. BiConversationSession Model Tests (BCON)
# ===========================================================================


@pytest.mark.django_db
def test_conversationalbi_session_defaults_and_autonumber(tenant_a, admin_user):
    """Test BiConversationSession creation, BCON prefix, defaults, __str__, and URL."""
    session = BiConversationSession.objects.create(
        tenant=tenant_a,
        user=admin_user,
        title="Fiscal Year 2026 Budget Deliberation",
    )
    assert session.NUMBER_PREFIX == "BCON"
    assert session.number.startswith("BCON-")
    assert session.session_status == "active"
    assert session.is_pinned is False
    assert session.message_count == 0
    assert session.context_state == {}
    assert session.suggested_prompts == []
    assert str(session) == f"{session.number} — Fiscal Year 2026 Budget Deliberation"
    assert session.get_absolute_url() == f"/bi/conversations/{session.pk}/"


@pytest.mark.django_db
def test_conversationalbi_session_autonumber_increment_and_tenant_isolation(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Test autonumber incrementing for BiConversationSession and tenant isolation."""
    s1 = _conversationalbi_create_session(tenant_a, admin_user)
    s2 = _conversationalbi_create_session(tenant_a, admin_user)
    assert s1.number.startswith("BCON-")
    assert s2.number.startswith("BCON-")
    n1 = int(s1.number.split("-")[1])
    n2 = int(s2.number.split("-")[1])
    assert n2 == n1 + 1

    s_b = _conversationalbi_create_session(tenant_b, admin_user_b)
    assert s_b.tenant == tenant_b
    assert s_b.number.startswith("BCON-")


@pytest.mark.django_db
def test_conversationalbi_session_str_representation(tenant_a, admin_user):
    """Test BiConversationSession string representation format."""
    session = _conversationalbi_create_session(
        tenant=tenant_a, user=admin_user, title="Weekly Ops Chat"
    )
    assert str(session) == f"{session.number} — Weekly Ops Chat"


@pytest.mark.django_db
def test_conversationalbi_session_get_absolute_url(tenant_a, admin_user):
    """Test BiConversationSession get_absolute_url matches reverse routing."""
    session = _conversationalbi_create_session(tenant_a, admin_user)
    assert session.get_absolute_url() == f"/bi/conversations/{session.pk}/"


@pytest.mark.django_db
def test_conversationalbi_session_choices():
    """Test choices enumeration on BiConversationSession."""
    status_keys = _conversationalbi_choice_keys(BiConversationSession.SESSION_STATUS_CHOICES)
    assert "active" in status_keys
    assert "closed" in status_keys
    assert "archived" in status_keys


@pytest.mark.django_db
def test_conversationalbi_session_badge_colors(tenant_a, admin_user):
    """Test computed status_badge_color property mappings on BiConversationSession."""
    session = BiConversationSession(tenant=tenant_a, user=admin_user, title="Badge Test Session")

    session.session_status = "active"
    assert session.status_badge_color == "badge-green"
    _conversationalbi_assert_valid_badge(session.status_badge_color)

    session.session_status = "closed"
    assert session.status_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(session.status_badge_color)

    session.session_status = "archived"
    assert session.status_badge_color == "badge-amber"
    _conversationalbi_assert_valid_badge(session.status_badge_color)

    session.session_status = "unknown_status"
    assert session.status_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(session.status_badge_color)


@pytest.mark.django_db
def test_conversationalbi_session_json_fields(tenant_a, admin_user):
    """Test suggested_prompts and context_state JSONField serialization on BiConversationSession."""
    prompts = [
        "Which sales territories are trailing target?",
        "Show gross margin trend by product family",
        "What is our projected Q4 inventory turnover?",
    ]
    ctx = {
        "perspective": "financial",
        "timeframe": "Q3",
        "pinned_dimensions": ["territory", "family"],
    }
    session = BiConversationSession.objects.create(
        tenant=tenant_a,
        user=admin_user,
        title="Session JSON Test",
        suggested_prompts=prompts,
        context_state=ctx,
    )
    reloaded = BiConversationSession.objects.get(pk=session.pk)
    assert reloaded.suggested_prompts == prompts
    assert reloaded.context_state == ctx
    if hasattr(reloaded, "suggested_followups"):
        assert reloaded.suggested_followups is not None


@pytest.mark.django_db
def test_conversationalbi_session_unique_constraint(tenant_a, tenant_b, admin_user, admin_user_b):
    """Verify unique constraint on (tenant, number) for BiConversationSession."""
    s1 = _conversationalbi_create_session(tenant_a, admin_user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiConversationSession.objects.create(
                tenant=tenant_a,
                number=s1.number,
                title="Duplicate Number Session",
                user=admin_user,
            )

    s_b = BiConversationSession.objects.create(
        tenant=tenant_b,
        number=s1.number,
        title="Same Number in Tenant B",
        user=admin_user_b,
    )
    assert s_b.number == s1.number
    assert s_b.tenant == tenant_b


@pytest.mark.django_db
def test_conversationalbi_session_foreign_keys_and_cascade(
    tenant_a, admin_user, semantic_model_a, bi_dashboard_a
):
    """Test foreign keys, CASCADE on user, and SET_NULL on models/dashboards."""
    User = get_user_model()
    temp_user = User.objects.create_user(
        email="temp_session@example.com", username="temp_session_user", password="password123"
    )

    session = BiConversationSession.objects.create(
        tenant=tenant_a,
        user=temp_user,
        title="Session Relation Verification",
        primary_semantic_model=semantic_model_a,
        primary_dashboard=bi_dashboard_a,
    )
    assert session in temp_user.bi_conversations.all()
    assert session in semantic_model_a.bi_conversations.all()
    assert session in bi_dashboard_a.bi_conversations.all()

    # User deletion must CASCADE delete session
    session_pk = session.pk
    temp_user.delete()
    assert not BiConversationSession.objects.filter(pk=session_pk).exists()


@pytest.mark.django_db
def test_conversationalbi_session_ordering_and_indexes(tenant_a, admin_user):
    """Verify BiConversationSession Meta ordering and indexes."""
    assert BiConversationSession._meta.ordering == ["-is_pinned", "-last_interaction_at", "-id"]
    index_names = [idx.name for idx in BiConversationSession._meta.indexes]
    assert "idx_bcon_ten_stat" in index_names
    assert "idx_bcon_ten_usr" in index_names
    assert "idx_bcon_ten_pin" in index_names
    assert "idx_bcon_ten_interact" in index_names

    # Pinned sessions should appear first
    unpinned = _conversationalbi_create_session(tenant_a, admin_user, is_pinned=False, title="Unpinned")
    pinned = _conversationalbi_create_session(tenant_a, admin_user, is_pinned=True, title="Pinned")
    sessions = list(BiConversationSession.objects.filter(pk__in=[unpinned.pk, pinned.pk]))
    assert sessions[0].pk == pinned.pk
    assert sessions[1].pk == unpinned.pk


# ===========================================================================
# 3. NarrativeExplanation Model Tests (BNLG)
# ===========================================================================


@pytest.mark.django_db
def test_conversationalbi_narrative_defaults_and_autonumber(tenant_a):
    """Test NarrativeExplanation creation, BNLG prefix, defaults, __str__, and URL."""
    narrative = NarrativeExplanation.objects.create(
        tenant=tenant_a,
        title="Quarterly Variance Narrative",
        headline="Revenue exceeded target by 14.2% driven by enterprise expansion.",
        narrative_body="Executive briefing highlighting software renewals across EMEA and APAC.",
    )
    assert narrative.NUMBER_PREFIX == "BNLG"
    assert narrative.number.startswith("BNLG-")
    assert narrative.target_artifact_type == "dashboard"
    assert narrative.narrative_style == "executive_briefing"
    assert narrative.status == "generated"
    assert narrative.language == "en"
    assert narrative.key_takeaways == []
    assert narrative.top_positive_driver == ""
    assert narrative.top_negative_driver == ""
    assert narrative.audio_ready_script == ""
    assert str(narrative) == f"{narrative.number} — Quarterly Variance Narrative"
    assert narrative.get_absolute_url() == f"/bi/narratives/{narrative.pk}/"


@pytest.mark.django_db
def test_conversationalbi_narrative_autonumber_increment_and_tenant_isolation(
    tenant_a, tenant_b
):
    """Test autonumber incrementing for NarrativeExplanation and tenant isolation."""
    n1 = _conversationalbi_create_narrative(tenant_a)
    n2 = _conversationalbi_create_narrative(tenant_a)
    assert n1.number.startswith("BNLG-")
    assert n2.number.startswith("BNLG-")
    val1 = int(n1.number.split("-")[1])
    val2 = int(n2.number.split("-")[1])
    assert val2 == val1 + 1

    n_b = _conversationalbi_create_narrative(tenant_b)
    assert n_b.tenant == tenant_b
    assert n_b.number.startswith("BNLG-")


@pytest.mark.django_db
def test_conversationalbi_narrative_str_representation(tenant_a):
    """Test NarrativeExplanation string representation format."""
    narrative = _conversationalbi_create_narrative(
        tenant=tenant_a, title="Executive ARR Variance Summary"
    )
    assert str(narrative) == f"{narrative.number} — Executive ARR Variance Summary"


@pytest.mark.django_db
def test_conversationalbi_narrative_get_absolute_url(tenant_a):
    """Test NarrativeExplanation get_absolute_url maps to bi:narrative_explanation_detail."""
    narrative = _conversationalbi_create_narrative(tenant_a)
    assert narrative.get_absolute_url() == f"/bi/narratives/{narrative.pk}/"


@pytest.mark.django_db
def test_conversationalbi_narrative_choices():
    """Test choices enumerations for NarrativeExplanation."""
    artifact_keys = _conversationalbi_choice_keys(NarrativeExplanation.TARGET_ARTIFACT_TYPE_CHOICES)
    assert "dashboard" in artifact_keys
    assert "report" in artifact_keys
    assert "kpi_scorecard" in artifact_keys
    assert "query_result" in artifact_keys
    assert "custom_dataset" in artifact_keys

    style_keys = _conversationalbi_choice_keys(NarrativeExplanation.NARRATIVE_STYLE_CHOICES)
    assert "executive_briefing" in style_keys
    assert "analytical_deepdive" in style_keys
    assert "bulleted_highlights" in style_keys
    assert "anomaly_alert" in style_keys
    assert "spoken_voice_script" in style_keys

    status_keys = _conversationalbi_choice_keys(NarrativeExplanation.STATUS_CHOICES)
    assert "draft" in status_keys
    assert "generated" in status_keys
    assert "reviewed" in status_keys
    assert "published" in status_keys


@pytest.mark.django_db
def test_conversationalbi_narrative_badge_colors(tenant_a):
    """Test computed status_badge_color and style_badge_color on NarrativeExplanation."""
    narrative = NarrativeExplanation(
        tenant=tenant_a,
        title="Badge Test Narrative",
        headline="Headline",
        narrative_body="Body",
    )

    # Status badge color
    narrative.status = "published"
    assert narrative.status_badge_color == "badge-green"
    _conversationalbi_assert_valid_badge(narrative.status_badge_color)

    narrative.status = "reviewed"
    assert narrative.status_badge_color == "badge-info"
    _conversationalbi_assert_valid_badge(narrative.status_badge_color)

    narrative.status = "generated"
    assert narrative.status_badge_color == "badge-info"
    _conversationalbi_assert_valid_badge(narrative.status_badge_color)

    narrative.status = "draft"
    assert narrative.status_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(narrative.status_badge_color)

    # Style badge color
    narrative.narrative_style = "executive_briefing"
    assert narrative.style_badge_color == "badge-info"
    _conversationalbi_assert_valid_badge(narrative.style_badge_color)

    narrative.narrative_style = "anomaly_alert"
    assert narrative.style_badge_color == "badge-amber"
    _conversationalbi_assert_valid_badge(narrative.style_badge_color)

    narrative.narrative_style = "analytical_deepdive"
    assert narrative.style_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(narrative.style_badge_color)

    narrative.narrative_style = "spoken_voice_script"
    assert narrative.style_badge_color == "badge-green"
    _conversationalbi_assert_valid_badge(narrative.style_badge_color)

    narrative.narrative_style = "bulleted_highlights"
    assert narrative.style_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(narrative.style_badge_color)


@pytest.mark.django_db
def test_conversationalbi_narrative_json_fields(tenant_a):
    """Test key_takeaways JSONField serialization on NarrativeExplanation."""
    bullets = [
        "Subscription revenue exceeded plan by $1.2M",
        "Operating margin held steady at 28.4%",
        "Churn reduced to record low 1.2% in enterprise tier",
    ]
    narrative = NarrativeExplanation.objects.create(
        tenant=tenant_a,
        title="Key Takeaways JSON Test",
        headline="Solid Quarter Performance",
        narrative_body="Narrative details...",
        key_takeaways=bullets,
    )
    reloaded = NarrativeExplanation.objects.get(pk=narrative.pk)
    assert reloaded.key_takeaways == bullets


@pytest.mark.django_db
def test_conversationalbi_narrative_unique_constraint(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, number) for NarrativeExplanation."""
    n1 = _conversationalbi_create_narrative(tenant_a)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NarrativeExplanation.objects.create(
                tenant=tenant_a,
                number=n1.number,
                title="Duplicate Narrative",
                headline="Duplicate headline",
                narrative_body="Duplicate body",
            )

    n_b = NarrativeExplanation.objects.create(
        tenant=tenant_b,
        number=n1.number,
        title="Same Number in Tenant B",
        headline="Tenant B headline",
        narrative_body="Tenant B body",
    )
    assert n_b.number == n1.number
    assert n_b.tenant == tenant_b


@pytest.mark.django_db
def test_conversationalbi_narrative_foreign_keys_and_cascade(
    tenant_a, bi_dashboard_a, kpi_definition_a
):
    """Test foreign keys and SET_NULL behavior on NarrativeExplanation."""
    User = get_user_model()
    temp_user = User.objects.create_user(
        email="temp_narrative@example.com", username="narrative_temp_user", password="password123"
    )
    query = _conversationalbi_create_nlq(tenant_a)

    narrative = NarrativeExplanation.objects.create(
        tenant=tenant_a,
        title="Linkage Test Narrative",
        headline="Linkage headline",
        narrative_body="Linkage body",
        dashboard=bi_dashboard_a,
        kpi=kpi_definition_a,
        query=query,
        created_by=temp_user,
    )

    assert narrative in bi_dashboard_a.narrative_explanations.all()
    assert narrative in kpi_definition_a.narrative_explanations.all()
    assert narrative in query.narrative_explanations.all()
    assert narrative in temp_user.created_narratives.all()

    # User SET_NULL
    temp_user.delete()
    narrative.refresh_from_db()
    assert narrative.created_by is None

    # Query SET_NULL
    query.delete()
    narrative.refresh_from_db()
    assert narrative.query is None


@pytest.mark.django_db
def test_conversationalbi_narrative_ordering_and_indexes():
    """Verify NarrativeExplanation Meta ordering and indexes."""
    assert NarrativeExplanation._meta.ordering == ["-created_at", "-id"]
    index_names = [idx.name for idx in NarrativeExplanation._meta.indexes]
    assert "idx_bnlg_ten_art" in index_names
    assert "idx_bnlg_ten_style" in index_names
    assert "idx_bnlg_ten_stat" in index_names
    assert "idx_bnlg_ten_created" in index_names


# ===========================================================================
# 4. SearchDiscoveryIndex Model Tests (BSDI)
# ===========================================================================


@pytest.mark.django_db
def test_conversationalbi_search_discovery_defaults_and_autonumber(tenant_a):
    """Test SearchDiscoveryIndex creation, BSDI prefix, defaults, __str__, and URL."""
    idx = SearchDiscoveryIndex.objects.create(
        tenant=tenant_a,
        asset_name="Executive Profitability Overview",
        target_url="/bi/dashboards/1/",
    )
    assert idx.NUMBER_PREFIX == "BSDI"
    assert idx.number.startswith("BSDI-")
    assert idx.asset_type == "dashboard"
    assert idx.relevance_weight == Decimal("1.00")
    assert idx.search_hit_count == 0
    assert idx.view_count == 0
    assert idx.is_featured is False
    assert idx.is_verified is True
    assert idx.synonyms == []
    assert idx.description == ""
    assert idx.category == ""
    assert idx.search_keywords == ""
    assert str(idx) == f"{idx.number} — Executive Profitability Overview"
    assert idx.get_absolute_url() == f"/bi/search-discovery/{idx.pk}/"


@pytest.mark.django_db
def test_conversationalbi_search_discovery_autonumber_increment_and_tenant_isolation(
    tenant_a, tenant_b
):
    """Test autonumber incrementing for SearchDiscoveryIndex and tenant isolation."""
    idx1 = _conversationalbi_create_search_index(tenant_a)
    idx2 = _conversationalbi_create_search_index(tenant_a)
    assert idx1.number.startswith("BSDI-")
    assert idx2.number.startswith("BSDI-")
    n1 = int(idx1.number.split("-")[1])
    n2 = int(idx2.number.split("-")[1])
    assert n2 == n1 + 1

    idx_b = _conversationalbi_create_search_index(tenant_b)
    assert idx_b.tenant == tenant_b
    assert idx_b.number.startswith("BSDI-")


@pytest.mark.django_db
def test_conversationalbi_search_discovery_str_representation(tenant_a):
    """Test SearchDiscoveryIndex string representation format."""
    idx = _conversationalbi_create_search_index(
        tenant=tenant_a, asset_name="Enterprise Customer Churn Model"
    )
    assert str(idx) == f"{idx.number} — Enterprise Customer Churn Model"


@pytest.mark.django_db
def test_conversationalbi_search_discovery_get_absolute_url(tenant_a):
    """Test SearchDiscoveryIndex get_absolute_url matches reverse routing."""
    idx = _conversationalbi_create_search_index(tenant_a)
    assert idx.get_absolute_url() == f"/bi/search-discovery/{idx.pk}/"


@pytest.mark.django_db
def test_conversationalbi_search_discovery_choices():
    """Test choices enumeration for SearchDiscoveryIndex."""
    type_keys = _conversationalbi_choice_keys(SearchDiscoveryIndex.ASSET_TYPE_CHOICES)
    assert "dashboard" in type_keys
    assert "report" in type_keys
    assert "kpi" in type_keys
    assert "semantic_model" in type_keys
    assert "warehouse_table" in type_keys
    assert "glossary_term" in type_keys
    assert "ad_hoc_query" in type_keys


@pytest.mark.django_db
def test_conversationalbi_search_discovery_badge_colors(tenant_a):
    """Test computed asset_type_badge_color, type_badge_color, and verification_badge_color."""
    idx = SearchDiscoveryIndex(
        tenant=tenant_a, asset_name="Badge Test Asset", target_url="/test/"
    )

    idx.asset_type = "dashboard"
    assert idx.asset_type_badge_color == "badge-info"
    assert idx.type_badge_color == "badge-info"
    _conversationalbi_assert_valid_badge(idx.asset_type_badge_color)

    idx.asset_type = "report"
    assert idx.asset_type_badge_color == "badge-slate"
    assert idx.type_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(idx.asset_type_badge_color)

    idx.asset_type = "kpi"
    assert idx.asset_type_badge_color == "badge-green"
    assert idx.type_badge_color == "badge-green"
    _conversationalbi_assert_valid_badge(idx.asset_type_badge_color)

    idx.asset_type = "semantic_model"
    assert idx.asset_type_badge_color == "badge-amber"
    assert idx.type_badge_color == "badge-amber"
    _conversationalbi_assert_valid_badge(idx.asset_type_badge_color)

    idx.asset_type = "warehouse_table"
    assert idx.asset_type_badge_color == "badge-amber"
    assert idx.type_badge_color == "badge-amber"
    _conversationalbi_assert_valid_badge(idx.asset_type_badge_color)

    idx.asset_type = "glossary_term"
    assert idx.asset_type_badge_color == "badge-muted"
    assert idx.type_badge_color == "badge-muted"
    _conversationalbi_assert_valid_badge(idx.asset_type_badge_color)

    idx.asset_type = "ad_hoc_query"
    assert idx.asset_type_badge_color == "badge-muted"
    _conversationalbi_assert_valid_badge(idx.asset_type_badge_color)

    # Verification badge color
    idx.is_verified = True
    assert idx.verification_badge_color == "badge-green"
    _conversationalbi_assert_valid_badge(idx.verification_badge_color)

    idx.is_verified = False
    assert idx.verification_badge_color == "badge-slate"
    _conversationalbi_assert_valid_badge(idx.verification_badge_color)


@pytest.mark.django_db
def test_conversationalbi_search_discovery_json_fields(tenant_a):
    """Test synonyms JSONField serialization on SearchDiscoveryIndex."""
    syns = ["revenue", "turnover", "topline", "gross sales", "invoiced volume"]
    idx = SearchDiscoveryIndex.objects.create(
        tenant=tenant_a,
        asset_name="Sales & Revenue Hub",
        target_url="/bi/dashboards/revenue/",
        synonyms=syns,
    )
    reloaded = SearchDiscoveryIndex.objects.get(pk=idx.pk)
    assert reloaded.synonyms == syns


@pytest.mark.django_db
def test_conversationalbi_search_discovery_unique_constraint(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, number) for SearchDiscoveryIndex."""
    idx1 = _conversationalbi_create_search_index(tenant_a)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SearchDiscoveryIndex.objects.create(
                tenant=tenant_a,
                number=idx1.number,
                asset_name="Duplicate Index",
                target_url="/dup/",
            )

    idx_b = SearchDiscoveryIndex.objects.create(
        tenant=tenant_b,
        number=idx1.number,
        asset_name="Same Number in Tenant B",
        target_url="/tenant-b/",
    )
    assert idx_b.number == idx1.number
    assert idx_b.tenant == tenant_b


@pytest.mark.django_db
def test_conversationalbi_search_discovery_foreign_keys_and_cascade(
    tenant_a, bi_dashboard_a, semantic_model_a, warehouse_table_a, kpi_definition_a
):
    """Test foreign keys and related reverse managers on SearchDiscoveryIndex."""
    idx = SearchDiscoveryIndex.objects.create(
        tenant=tenant_a,
        asset_name="Master Financial Discovery Entry",
        target_url="/bi/dashboards/1/",
        dashboard=bi_dashboard_a,
        semantic_model=semantic_model_a,
        warehouse_table=warehouse_table_a,
        kpi=kpi_definition_a,
    )

    assert idx in bi_dashboard_a.discovery_indexes.all()
    assert idx in semantic_model_a.discovery_indexes.all()
    assert idx in warehouse_table_a.discovery_indexes.all()
    assert idx in kpi_definition_a.discovery_indexes.all()


@pytest.mark.django_db
def test_conversationalbi_search_discovery_composite_index_and_ordering(tenant_a):
    """Verify composite index idx_bsdi_ten_feat_rw and ordering on SearchDiscoveryIndex."""
    assert SearchDiscoveryIndex._meta.ordering == [
        "-is_featured",
        "-relevance_weight",
        "-view_count",
        "-id",
    ]

    index_names = [idx.name for idx in SearchDiscoveryIndex._meta.indexes]
    assert "idx_bsdi_ten_type" in index_names
    assert "idx_bsdi_ten_cat" in index_names
    assert "idx_bsdi_ten_feat" in index_names
    assert "idx_bsdi_ten_ver" in index_names
    assert "idx_bsdi_ten_feat_rw" in index_names

    # Assert composite index field specification
    composite_idx = next(
        i for i in SearchDiscoveryIndex._meta.indexes if i.name == "idx_bsdi_ten_feat_rw"
    )
    assert composite_idx.fields == ["tenant", "is_featured", "-relevance_weight"]

    # Test sorting behavior: featured with higher relevance weight precedes others
    idx_standard = SearchDiscoveryIndex.objects.create(
        tenant=tenant_a,
        asset_name="Standard Asset",
        target_url="/standard/",
        is_featured=False,
        relevance_weight=Decimal("1.00"),
        view_count=50,
    )
    idx_featured = SearchDiscoveryIndex.objects.create(
        tenant=tenant_a,
        asset_name="Featured Asset",
        target_url="/featured/",
        is_featured=True,
        relevance_weight=Decimal("2.50"),
        view_count=10,
    )

    results = list(
        SearchDiscoveryIndex.objects.filter(pk__in=[idx_standard.pk, idx_featured.pk])
    )
    assert results[0].pk == idx_featured.pk
    assert results[1].pk == idx_standard.pk


# ===========================================================================
# 5. Tenant Cascade Deletion Across All Conversational BI Models
# ===========================================================================


@pytest.mark.django_db
def test_conversationalbi_tenant_cascade_delete():
    """Verify that deleting a tenant cascades and removes all associated conversational BI records."""
    temp_tenant = Tenant.objects.create(
        name="ConversationalBI Temp Tenant",
        slug="cbi-temp-tenant",
    )
    User = get_user_model()
    temp_user = User.objects.create_user(
        email="temp_cbi@example.com", username="temp_cbi_user", password="password123"
    )

    session = _conversationalbi_create_session(temp_tenant, temp_user)
    nlq = _conversationalbi_create_nlq(temp_tenant, user=temp_user, session=session)
    narrative = _conversationalbi_create_narrative(temp_tenant, created_by=temp_user)
    search_idx = _conversationalbi_create_search_index(temp_tenant)

    session_pk = session.pk
    nlq_pk = nlq.pk
    narrative_pk = narrative.pk
    search_idx_pk = search_idx.pk

    temp_tenant.delete()

    assert not BiConversationSession.objects.filter(pk=session_pk).exists()
    assert not NaturalLanguageQuery.objects.filter(pk=nlq_pk).exists()
    assert not NarrativeExplanation.objects.filter(pk=narrative_pk).exists()
    assert not SearchDiscoveryIndex.objects.filter(pk=search_idx_pk).exists()
