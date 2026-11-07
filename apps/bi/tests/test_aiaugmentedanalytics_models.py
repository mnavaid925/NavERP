"""Unit tests for Sub-module 10.14 AI & Augmented Analytics models.

Models covered:
- AugmentedInsight (BAIN)
- SmartDataPrepSuggestion (BSDP)
- TextSentimentAnalysis (BSNT)
- AnalyticsRecommendation (BARC)
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.bi.models import (
    AnalyticsRecommendation,
    AugmentedInsight,
    SmartDataPrepSuggestion,
    TextSentimentAnalysis,
)

_AIAUGMENTEDANALYTICS_VALID_BADGES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-slate",
}


def _aiaugmentedanalytics_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


def _aiaugmentedanalytics_assert_valid_badge(badge):
    """Helper to verify badge is in valid color-named badge classes and not purple."""
    assert badge in _AIAUGMENTEDANALYTICS_VALID_BADGES
    assert badge != "badge-purple"


# ===========================================================================
# 1. AugmentedInsight Model Tests (BAIN)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_defaults_and_autonumber(tenant_a, admin_user):
    """Test AugmentedInsight creation, BAIN prefix, defaults, __str__, and URL."""
    insight = AugmentedInsight.objects.create(
        tenant=tenant_a,
        title="Gross Margin Variance in APAC",
        metric_name="Gross Margin %",
        narrative_summary="Gross margin expanded unexpectedly across APAC region.",
        created_by=admin_user,
    )
    assert insight.NUMBER_PREFIX == "BAIN"
    assert insight.number.startswith("BAIN-")
    assert insight.insight_type == "key_driver"
    assert insight.baseline_value == Decimal("0.0000")
    assert insight.observed_value == Decimal("0.0000")
    assert insight.variance_percentage == Decimal("0.00")
    assert insight.impact_direction == "neutral"
    assert insight.severity == "medium"
    assert insight.confidence_score == Decimal("90.00")
    assert insight.status == "new"
    assert insight.dimension_name == ""
    assert insight.dimension_value == ""
    assert insight.action_notes == ""
    assert insight.driver_decomposition == []
    assert str(insight) == f"{insight.number} — {insight.title}"
    assert insight.get_absolute_url() == f"/bi/augmented-insights/{insight.pk}/"


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_fixture_and_relations(
    augmented_insight_a, tenant_a, semantic_model_a, kpi_definition_a, admin_user
):
    """Test AugmentedInsight fixture data and foreign key relationships."""
    assert augmented_insight_a.pk is not None
    assert augmented_insight_a.tenant == tenant_a
    assert augmented_insight_a.number == "BAIN-00001"
    assert augmented_insight_a.title == "Q3 Enterprise ARR Surge"
    assert augmented_insight_a.insight_type == "trend_shift"
    assert augmented_insight_a.severity == "high"
    assert augmented_insight_a.impact_direction == "favorable"
    assert augmented_insight_a.semantic_model == semantic_model_a
    assert augmented_insight_a.kpi_definition == kpi_definition_a
    assert augmented_insight_a.created_by == admin_user
    assert augmented_insight_a in semantic_model_a.augmented_insights.all()
    assert augmented_insight_a in kpi_definition_a.augmented_insights.all()


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_choices():
    """Test choice enumerations and human-readable display values for AugmentedInsight."""
    type_keys = _aiaugmentedanalytics_choice_keys(AugmentedInsight.INSIGHT_TYPE_CHOICES)
    assert "key_driver" in type_keys
    assert "anomaly" in type_keys
    assert "trend_shift" in type_keys
    assert "outlier" in type_keys
    assert "period_comparison" in type_keys

    impact_keys = _aiaugmentedanalytics_choice_keys(AugmentedInsight.IMPACT_DIRECTION_CHOICES)
    assert "favorable" in impact_keys
    assert "unfavorable" in impact_keys
    assert "neutral" in impact_keys

    severity_keys = _aiaugmentedanalytics_choice_keys(AugmentedInsight.SEVERITY_CHOICES)
    assert "low" in severity_keys
    assert "medium" in severity_keys
    assert "high" in severity_keys
    assert "critical" in severity_keys

    status_keys = _aiaugmentedanalytics_choice_keys(AugmentedInsight.STATUS_CHOICES)
    assert "new" in status_keys
    assert "bookmarked" in status_keys
    assert "dismissed" in status_keys
    assert "actioned" in status_keys


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_badge_colors(tenant_a):
    """Test computed badge_color and impact_badge_color property mappings."""
    insight = AugmentedInsight(
        tenant=tenant_a,
        title="Badge Test Insight",
        metric_name="Revenue",
        narrative_summary="Summary text",
    )

    # Severity badge color mapping
    insight.severity = "critical"
    assert insight.badge_color == "badge-red"
    _aiaugmentedanalytics_assert_valid_badge(insight.badge_color)

    insight.severity = "high"
    assert insight.badge_color == "badge-amber"
    _aiaugmentedanalytics_assert_valid_badge(insight.badge_color)

    insight.severity = "medium"
    assert insight.badge_color == "badge-info"
    _aiaugmentedanalytics_assert_valid_badge(insight.badge_color)

    insight.severity = "low"
    assert insight.badge_color == "badge-slate"
    _aiaugmentedanalytics_assert_valid_badge(insight.badge_color)

    # Impact badge color mapping
    insight.impact_direction = "favorable"
    assert insight.impact_badge_color == "badge-green"
    _aiaugmentedanalytics_assert_valid_badge(insight.impact_badge_color)

    insight.impact_direction = "unfavorable"
    assert insight.impact_badge_color == "badge-red"
    _aiaugmentedanalytics_assert_valid_badge(insight.impact_badge_color)

    insight.impact_direction = "neutral"
    assert insight.impact_badge_color == "badge-slate"
    _aiaugmentedanalytics_assert_valid_badge(insight.impact_badge_color)


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_tenant_isolation_and_unique_number(
    augmented_insight_a, augmented_insight_b, tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify tenant isolation and unique constraint on (tenant, number)."""
    # Tenant isolation
    tenant_a_insights = AugmentedInsight.objects.filter(tenant=tenant_a)
    tenant_b_insights = AugmentedInsight.objects.filter(tenant=tenant_b)
    assert augmented_insight_a in tenant_a_insights
    assert augmented_insight_a not in tenant_b_insights
    assert augmented_insight_b in tenant_b_insights
    assert augmented_insight_b not in tenant_a_insights

    # Unique number within tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AugmentedInsight.objects.create(
                tenant=tenant_a,
                number=augmented_insight_a.number,
                title="Duplicate Number Insight",
                metric_name="Test Metric",
                narrative_summary="Duplicate summary",
                created_by=admin_user,
            )

    # Reusing same number across distinct tenant must succeed
    diff_tenant_insight = AugmentedInsight.objects.create(
        tenant=tenant_b,
        number="BAIN-00001",
        title="Same Number in Tenant B",
        metric_name="Test Metric B",
        narrative_summary="Summary B",
        created_by=admin_user_b,
    )
    assert diff_tenant_insight.number == augmented_insight_a.number
    assert diff_tenant_insight.tenant == tenant_b


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_driver_decomposition_json(tenant_a, admin_user):
    """Verify driver_decomposition JSONField serialization and complex payload retrieval."""
    drivers_data = [
        {"name": "Price Increase", "weight": 45, "impact": "positive", "explanation": "List price revision"},
        {"name": "Volume Decline", "weight": 25, "impact": "negative", "explanation": "Fewer units sold"},
        {"name": "FX Headwind", "weight": 10, "impact": "negative", "explanation": "EUR depreciation"},
    ]
    insight = AugmentedInsight.objects.create(
        tenant=tenant_a,
        title="EBITDA Bridge Analysis",
        metric_name="EBITDA",
        narrative_summary="Quarterly EBITDA decomposition shows positive net price impact.",
        driver_decomposition=drivers_data,
        created_by=admin_user,
    )
    reloaded = AugmentedInsight.objects.get(pk=insight.pk)
    assert len(reloaded.driver_decomposition) == 3
    assert reloaded.driver_decomposition[0]["name"] == "Price Increase"
    assert reloaded.driver_decomposition[1]["weight"] == 25
    assert reloaded.driver_decomposition[2]["impact"] == "negative"


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_ordering(tenant_a, admin_user):
    """Verify AugmentedInsight Meta ordering default is ['-created_at', '-id']."""
    assert AugmentedInsight._meta.ordering == ["-created_at", "-id"]

    ins1 = AugmentedInsight.objects.create(
        tenant=tenant_a,
        title="Insight Chrono 1",
        metric_name="Metric 1",
        narrative_summary="Summary 1",
        created_by=admin_user,
    )
    ins2 = AugmentedInsight.objects.create(
        tenant=tenant_a,
        title="Insight Chrono 2",
        metric_name="Metric 2",
        narrative_summary="Summary 2",
        created_by=admin_user,
    )
    insights = list(AugmentedInsight.objects.filter(tenant=tenant_a, pk__in=[ins1.pk, ins2.pk]))
    assert insights[0].pk == ins2.pk
    assert insights[1].pk == ins1.pk


@pytest.mark.django_db
def test_aiaugmentedanalytics_insight_indexes():
    """Verify composite database indexes on AugmentedInsight."""
    index_names = [idx.name for idx in AugmentedInsight._meta.indexes]
    assert "idx_bain_ten_type" in index_names
    assert "idx_bain_ten_status" in index_names
    assert "idx_bain_ten_sev" in index_names
    assert "idx_bain_ten_dir" in index_names
    assert "idx_bain_ten_created" in index_names


# ===========================================================================
# 2. SmartDataPrepSuggestion Model Tests (BSDP)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_defaults_and_autonumber(tenant_a, warehouse_table):
    """Test SmartDataPrepSuggestion creation, BSDP prefix, defaults, __str__, and URL."""
    suggestion = SmartDataPrepSuggestion.objects.create(
        tenant=tenant_a,
        target_table=warehouse_table,
        target_column="customer_id",
        rationale="Column pattern matches customer master key.",
    )
    assert suggestion.NUMBER_PREFIX == "BSDP"
    assert suggestion.number.startswith("BSDP-")
    assert suggestion.suggestion_type == "join_relationship"
    assert suggestion.confidence_score == Decimal("85.00")
    assert suggestion.status == "pending"
    assert suggestion.suggested_config == {}
    assert suggestion.related_table is None
    assert suggestion.related_column == ""
    assert suggestion.reviewed_by is None
    assert suggestion.reviewed_at is None
    assert suggestion.review_notes == ""

    expected_str = f"{suggestion.number} — Suggested Foreign Key Join on {warehouse_table.name}.customer_id"
    assert str(suggestion) == expected_str
    assert suggestion.get_absolute_url() == f"/bi/data-prep-suggestions/{suggestion.pk}/"


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_fixture_and_relations(
    smart_data_prep_suggestion_a, warehouse_table, admin_user
):
    """Test SmartDataPrepSuggestion fixture values and relations."""
    assert smart_data_prep_suggestion_a.pk is not None
    assert smart_data_prep_suggestion_a.number == "BSDP-00001"
    assert smart_data_prep_suggestion_a.target_table == warehouse_table
    assert smart_data_prep_suggestion_a.target_column == "order_timestamp"
    assert smart_data_prep_suggestion_a.suggestion_type == "type_cast"
    assert smart_data_prep_suggestion_a.confidence_score == Decimal("95.00")
    assert smart_data_prep_suggestion_a.status == "pending"
    assert smart_data_prep_suggestion_a.reviewed_by == admin_user
    assert smart_data_prep_suggestion_a in warehouse_table.target_prep_suggestions.all()


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_choices():
    """Test choice enumerations on SmartDataPrepSuggestion."""
    sug_keys = _aiaugmentedanalytics_choice_keys(SmartDataPrepSuggestion.SUGGESTION_TYPE_CHOICES)
    assert "join_relationship" in sug_keys
    assert "type_cast" in sug_keys
    assert "split_column" in sug_keys
    assert "impute_missing" in sug_keys
    assert "deduplicate_fuzzy" in sug_keys
    assert "filter_outliers" in sug_keys

    stat_keys = _aiaugmentedanalytics_choice_keys(SmartDataPrepSuggestion.STATUS_CHOICES)
    assert "pending" in stat_keys
    assert "accepted" in stat_keys
    assert "rejected" in stat_keys
    assert "applied" in stat_keys


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_badge_colors(tenant_a, warehouse_table):
    """Test computed badge_color property on SmartDataPrepSuggestion."""
    suggestion = SmartDataPrepSuggestion(
        tenant=tenant_a,
        target_table=warehouse_table,
        target_column="price",
        rationale="Filter price spikes.",
    )

    suggestion.status = "applied"
    assert suggestion.badge_color == "badge-green"
    _aiaugmentedanalytics_assert_valid_badge(suggestion.badge_color)

    suggestion.status = "accepted"
    assert suggestion.badge_color == "badge-info"
    _aiaugmentedanalytics_assert_valid_badge(suggestion.badge_color)

    suggestion.status = "rejected"
    assert suggestion.badge_color == "badge-red"
    _aiaugmentedanalytics_assert_valid_badge(suggestion.badge_color)

    suggestion.status = "pending"
    assert suggestion.badge_color == "badge-amber"
    _aiaugmentedanalytics_assert_valid_badge(suggestion.badge_color)


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_tenant_isolation_and_unique_number(
    smart_data_prep_suggestion_a, smart_data_prep_suggestion_b, tenant_a, tenant_b, warehouse_table, warehouse_table_b
):
    """Verify tenant isolation and unique constraint on SmartDataPrepSuggestion."""
    assert smart_data_prep_suggestion_a in SmartDataPrepSuggestion.objects.filter(tenant=tenant_a)
    assert smart_data_prep_suggestion_a not in SmartDataPrepSuggestion.objects.filter(tenant=tenant_b)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SmartDataPrepSuggestion.objects.create(
                tenant=tenant_a,
                number=smart_data_prep_suggestion_a.number,
                target_table=warehouse_table,
                target_column="order_id",
                rationale="Duplicate suggestion number",
            )

    diff_tenant_sug = SmartDataPrepSuggestion.objects.create(
        tenant=tenant_b,
        number="BSDP-00001",
        target_table=warehouse_table_b,
        target_column="order_id",
        rationale="Suggestion in tenant B with BSDP-00001",
    )
    assert diff_tenant_sug.number == smart_data_prep_suggestion_a.number
    assert diff_tenant_sug.tenant == tenant_b


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_suggested_config_json(tenant_a, warehouse_table):
    """Verify suggested_config JSONField storing structured join or transformation specs."""
    config_payload = {
        "join_type": "LEFT OUTER JOIN",
        "primary_key": "customer_id",
        "foreign_key": "client_uuid",
        "null_handling": "drop",
    }
    sug = SmartDataPrepSuggestion.objects.create(
        tenant=tenant_a,
        target_table=warehouse_table,
        target_column="client_uuid",
        suggestion_type="join_relationship",
        suggested_config=config_payload,
        rationale="Fuzzy link with customer master table",
    )
    reloaded = SmartDataPrepSuggestion.objects.get(pk=sug.pk)
    assert reloaded.suggested_config["join_type"] == "LEFT OUTER JOIN"
    assert reloaded.suggested_config["foreign_key"] == "client_uuid"


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_ordering():
    """Verify SmartDataPrepSuggestion Meta ordering default is ['-created_at', '-id']."""
    assert SmartDataPrepSuggestion._meta.ordering == ["-created_at", "-id"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_dataprep_indexes():
    """Verify database indexes on SmartDataPrepSuggestion."""
    index_names = [idx.name for idx in SmartDataPrepSuggestion._meta.indexes]
    assert "idx_bsdp_ten_type" in index_names
    assert "idx_bsdp_ten_stat" in index_names
    assert "idx_bsdp_ten_tbl" in index_names
    assert "idx_bsdp_ten_created" in index_names


# ===========================================================================
# 3. TextSentimentAnalysis Model Tests (BSNT)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_defaults_and_autonumber(tenant_a):
    """Test TextSentimentAnalysis creation, BSNT prefix, defaults, __str__, and URL."""
    analysis = TextSentimentAnalysis.objects.create(
        tenant=tenant_a,
        source_reference="REV-10001",
        text_content="The platform performance is adequate for daily operational needs.",
    )
    assert analysis.NUMBER_PREFIX == "BSNT"
    assert analysis.number.startswith("BSNT-")
    assert analysis.source_type == "customer_review"
    assert analysis.language == "en"
    assert analysis.sentiment_category == "neutral"
    assert analysis.polarity_score == Decimal("0.00")
    assert analysis.subjectivity_score == Decimal("0.50")
    assert analysis.thematic_tags == []
    assert analysis.linked_party is None
    assert analysis.linked_org_unit is None

    expected_str = f"{analysis.number} — Neutral ({analysis.source_reference})"
    assert str(analysis) == expected_str
    assert analysis.get_absolute_url() == f"/bi/sentiment-analyses/{analysis.pk}/"


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_fixture_and_relations(text_sentiment_analysis_a, tenant_a):
    """Test TextSentimentAnalysis fixture values."""
    assert text_sentiment_analysis_a.pk is not None
    assert text_sentiment_analysis_a.tenant == tenant_a
    assert text_sentiment_analysis_a.number == "BSNT-00001"
    assert text_sentiment_analysis_a.source_type == "support_ticket"
    assert text_sentiment_analysis_a.sentiment_category == "positive"
    assert text_sentiment_analysis_a.polarity_score == Decimal("0.85")
    assert text_sentiment_analysis_a.subjectivity_score == Decimal("0.60")
    assert text_sentiment_analysis_a.thematic_tags == ["support", "onboarding", "consulting"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_choices():
    """Test choice enumerations on TextSentimentAnalysis."""
    src_keys = _aiaugmentedanalytics_choice_keys(TextSentimentAnalysis.SOURCE_TYPE_CHOICES)
    assert "customer_review" in src_keys
    assert "support_ticket" in src_keys
    assert "survey_feedback" in src_keys
    assert "crm_note" in src_keys
    assert "internal_comment" in src_keys

    cat_keys = _aiaugmentedanalytics_choice_keys(TextSentimentAnalysis.SENTIMENT_CATEGORY_CHOICES)
    assert "very_positive" in cat_keys
    assert "positive" in cat_keys
    assert "neutral" in cat_keys
    assert "negative" in cat_keys
    assert "very_negative" in cat_keys


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_badge_colors(tenant_a):
    """Test computed badge_color property on TextSentimentAnalysis."""
    item = TextSentimentAnalysis(
        tenant=tenant_a,
        source_reference="SR-1",
        text_content="Sample text",
    )

    item.sentiment_category = "very_positive"
    assert item.badge_color == "badge-green"
    _aiaugmentedanalytics_assert_valid_badge(item.badge_color)

    item.sentiment_category = "positive"
    assert item.badge_color == "badge-green"
    _aiaugmentedanalytics_assert_valid_badge(item.badge_color)

    item.sentiment_category = "very_negative"
    assert item.badge_color == "badge-red"
    _aiaugmentedanalytics_assert_valid_badge(item.badge_color)

    item.sentiment_category = "negative"
    assert item.badge_color == "badge-red"
    _aiaugmentedanalytics_assert_valid_badge(item.badge_color)

    item.sentiment_category = "neutral"
    assert item.badge_color == "badge-slate"
    _aiaugmentedanalytics_assert_valid_badge(item.badge_color)


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_tenant_isolation_and_unique_number(
    text_sentiment_analysis_a, text_sentiment_analysis_b, tenant_a, tenant_b
):
    """Verify tenant isolation and unique constraint on TextSentimentAnalysis."""
    assert text_sentiment_analysis_a in TextSentimentAnalysis.objects.filter(tenant=tenant_a)
    assert text_sentiment_analysis_a not in TextSentimentAnalysis.objects.filter(tenant=tenant_b)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TextSentimentAnalysis.objects.create(
                tenant=tenant_a,
                number=text_sentiment_analysis_a.number,
                source_reference="DUP-100",
                text_content="Duplicate analysis number in tenant a",
            )

    diff_tenant_item = TextSentimentAnalysis.objects.create(
        tenant=tenant_b,
        number="BSNT-00001",
        source_reference="DUP-100",
        text_content="Same number in tenant b",
    )
    assert diff_tenant_item.number == text_sentiment_analysis_a.number
    assert diff_tenant_item.tenant == tenant_b


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_thematic_tags_json(tenant_a):
    """Verify thematic_tags (extracted themes) JSONField serialization and querying."""
    tags = ["billing_issue", "payment_gateway", "refund_delay"]
    record = TextSentimentAnalysis.objects.create(
        tenant=tenant_a,
        source_reference="TKT-0099",
        text_content="Payment gateway errored and refund took 5 days.",
        thematic_tags=tags,
    )
    reloaded = TextSentimentAnalysis.objects.get(pk=record.pk)
    assert reloaded.thematic_tags == ["billing_issue", "payment_gateway", "refund_delay"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_ordering():
    """Verify TextSentimentAnalysis Meta ordering default is ['-analyzed_at', '-id']."""
    assert TextSentimentAnalysis._meta.ordering == ["-analyzed_at", "-id"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_sentiment_indexes():
    """Verify database indexes on TextSentimentAnalysis."""
    index_names = [idx.name for idx in TextSentimentAnalysis._meta.indexes]
    assert "idx_bsnt_ten_src" in index_names
    assert "idx_bsnt_ten_cat" in index_names
    assert "idx_bsnt_ten_date" in index_names
    assert "idx_bsnt_ten_party" in index_names


# ===========================================================================
# 4. AnalyticsRecommendation Model Tests (BARC)
# ===========================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_recommendation_defaults_and_autonumber(tenant_a, admin_user):
    """Test AnalyticsRecommendation creation, BARC prefix, defaults, __str__, and URL."""
    rec = AnalyticsRecommendation.objects.create(
        tenant=tenant_a,
        user=admin_user,
        target_title="Q4 Financial Health Scorecard",
        target_url="/bi/scorecards/1/",
    )
    assert rec.NUMBER_PREFIX == "BARC"
    assert rec.number.startswith("BARC-")
    assert rec.recommendation_type == "dashboard"
    assert rec.reason == "role_relevance"
    assert rec.affinity_score == Decimal("80.00")
    assert rec.status == "active"
    assert rec.rationale_text == ""
    assert rec.dashboard is None
    assert rec.report is None
    assert rec.kpi is None
    assert rec.semantic_model is None
    assert rec.last_interacted_at is None

    expected_str = f"{rec.number} — Suggest {rec.target_title} to {admin_user.username}"
    assert str(rec) == expected_str
    assert rec.get_absolute_url() == f"/bi/recommendations/{rec.pk}/"


@pytest.mark.django_db
def test_aiaugmentedanalytics_recommendation_fixture_and_relations(
    analytics_recommendation_a, admin_user, bi_dashboard_a, semantic_model_a
):
    """Test AnalyticsRecommendation fixture data and foreign key links."""
    assert analytics_recommendation_a.pk is not None
    assert analytics_recommendation_a.number == "BARC-00001"
    assert analytics_recommendation_a.user == admin_user
    assert analytics_recommendation_a.dashboard == bi_dashboard_a
    assert analytics_recommendation_a.semantic_model == semantic_model_a
    assert analytics_recommendation_a in admin_user.analytics_recommendations.all()
    assert analytics_recommendation_a in bi_dashboard_a.recommendations.all()
    assert analytics_recommendation_a in semantic_model_a.recommendations.all()


@pytest.mark.django_db
def test_aiaugmentedanalytics_recommendation_choices():
    """Test choice enumerations on AnalyticsRecommendation."""
    rec_keys = _aiaugmentedanalytics_choice_keys(AnalyticsRecommendation.RECOMMENDATION_TYPE_CHOICES)
    assert "dashboard" in rec_keys
    assert "report" in rec_keys
    assert "kpi" in rec_keys
    assert "dataset" in rec_keys
    assert "drill_path" in rec_keys

    reason_keys = _aiaugmentedanalytics_choice_keys(AnalyticsRecommendation.REASON_CHOICES)
    assert "peer_usage" in reason_keys
    assert "trending_metric" in reason_keys
    assert "anomaly_in_domain" in reason_keys
    assert "recent_search" in reason_keys
    assert "role_relevance" in reason_keys

    stat_keys = _aiaugmentedanalytics_choice_keys(AnalyticsRecommendation.STATUS_CHOICES)
    assert "active" in stat_keys
    assert "clicked" in stat_keys
    assert "dismissed" in stat_keys
    assert "saved" in stat_keys


@pytest.mark.django_db
def test_aiaugmentedanalytics_recommendation_badge_colors(tenant_a, admin_user):
    """Test computed badge_color property on AnalyticsRecommendation."""
    rec = AnalyticsRecommendation(
        tenant=tenant_a,
        user=admin_user,
        target_title="Asset",
        target_url="/bi/test/",
    )

    rec.status = "saved"
    assert rec.badge_color == "badge-green"
    _aiaugmentedanalytics_assert_valid_badge(rec.badge_color)

    rec.status = "clicked"
    assert rec.badge_color == "badge-info"
    _aiaugmentedanalytics_assert_valid_badge(rec.badge_color)

    rec.status = "dismissed"
    assert rec.badge_color == "badge-slate"
    _aiaugmentedanalytics_assert_valid_badge(rec.badge_color)

    rec.status = "active"
    assert rec.badge_color == "badge-amber"
    _aiaugmentedanalytics_assert_valid_badge(rec.badge_color)


@pytest.mark.django_db
def test_aiaugmentedanalytics_recommendation_tenant_isolation_and_unique_number(
    analytics_recommendation_a, analytics_recommendation_b, tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify tenant isolation and unique constraint on AnalyticsRecommendation."""
    assert analytics_recommendation_a in AnalyticsRecommendation.objects.filter(tenant=tenant_a)
    assert analytics_recommendation_a not in AnalyticsRecommendation.objects.filter(tenant=tenant_b)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AnalyticsRecommendation.objects.create(
                tenant=tenant_a,
                number=analytics_recommendation_a.number,
                user=admin_user,
                target_title="Dup Recommendation",
                target_url="/bi/dup/",
            )

    diff_tenant_rec = AnalyticsRecommendation.objects.create(
        tenant=tenant_b,
        number="BARC-00001",
        user=admin_user_b,
        target_title="Diff Tenant Recommendation",
        target_url="/bi/diff/",
    )
    assert diff_tenant_rec.number == analytics_recommendation_a.number
    assert diff_tenant_rec.tenant == tenant_b


@pytest.mark.django_db
def test_aiaugmentedanalytics_recommendation_ordering(tenant_a, admin_user):
    """Verify AnalyticsRecommendation Meta ordering default is ['-affinity_score', '-created_at']."""
    assert AnalyticsRecommendation._meta.ordering == ["-affinity_score", "-created_at"]

    r_low = AnalyticsRecommendation.objects.create(
        tenant=tenant_a,
        user=admin_user,
        target_title="Low Affinity Recommendation",
        target_url="/bi/low/",
        affinity_score=Decimal("45.00"),
    )
    r_high = AnalyticsRecommendation.objects.create(
        tenant=tenant_a,
        user=admin_user,
        target_title="High Affinity Recommendation",
        target_url="/bi/high/",
        affinity_score=Decimal("98.50"),
    )
    results = list(AnalyticsRecommendation.objects.filter(tenant=tenant_a, pk__in=[r_low.pk, r_high.pk]))
    assert results[0].pk == r_high.pk
    assert results[1].pk == r_low.pk


@pytest.mark.django_db
def test_aiaugmentedanalytics_recommendation_indexes():
    """Verify database indexes on AnalyticsRecommendation."""
    index_names = [idx.name for idx in AnalyticsRecommendation._meta.indexes]
    assert "idx_barc_ten_user_stat" in index_names
    assert "idx_barc_ten_type" in index_names
    assert "idx_barc_ten_score" in index_names
