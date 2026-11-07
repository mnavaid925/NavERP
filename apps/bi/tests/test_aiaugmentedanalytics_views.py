"""View tests for Sub-module 10.14: AI & Augmented Analytics (apps/bi).

Entities covered:
1. AugmentedInsight:
   - augmented_insight_list (GET, context contract, search, filters)
   - augmented_insight_feed (GET, context contract, tab filters)
   - augmented_insight_detail (GET, context contract, driver decomposition)
   - augmented_insight_create (GET, POST valid -> 302, POST invalid -> 200)
   - augmented_insight_edit (GET, POST valid -> 302)
   - augmented_insight_delete (POST -> 302, GET -> 405)
   - augmented_insight_triage (POST action -> 302, open redirect defense, GET -> 405)

2. SmartDataPrepSuggestion:
   - smart_data_prep_suggestion_list (GET, context contract, search, filters)
   - smart_data_prep_suggestion_detail (GET, context contract, config_items)
   - smart_data_prep_suggestion_create (GET, POST valid -> 302, POST invalid -> 200)
   - smart_data_prep_suggestion_edit (GET, POST valid -> 302)
   - smart_data_prep_suggestion_delete (POST -> 302, GET -> 405)
   - smart_data_prep_suggestion_action (POST action, already applied guard, open redirect defense, GET -> 405)

3. TextSentimentAnalysis:
   - text_sentiment_analysis_list (GET, context contract, search, filters)
   - text_sentiment_analysis_detail (GET, context contract, thematic_tags_list)
   - text_sentiment_analysis_create (GET, POST valid -> 302 with auto-scoring, POST invalid -> 200)
   - text_sentiment_analysis_edit (GET, POST valid -> 302)
   - text_sentiment_analysis_delete (POST -> 302, GET -> 405)
   - text_sentiment_analysis_recalculate (POST action -> 302, open redirect defense, GET -> 405)

4. AnalyticsRecommendation:
   - analytics_recommendation_list (GET, context contract, search, filters)
   - analytics_recommendation_detail (GET, context contract)
   - analytics_recommendation_create (GET, POST valid -> 302, POST invalid -> 200)
   - analytics_recommendation_edit (GET, POST valid -> 302)
   - analytics_recommendation_delete (POST -> 302, GET -> 405)
   - analytics_recommendation_interact (POST action, permission check, open redirect defense, GET -> 405)
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.bi.models.AiAugmentedAnalytics.AnalyticsRecommendations import AnalyticsRecommendation
from apps.bi.models.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsight
from apps.bi.models.AiAugmentedAnalytics.SmartDataPrepSuggestions import SmartDataPrepSuggestion
from apps.bi.models.AiAugmentedAnalytics.TextSentimentAnalyses import TextSentimentAnalysis
from apps.core.models import AuditLog

User = get_user_model()


# ==============================================================================
# Module Helpers (named _aiaugmentedanalytics_views_*)
# ==============================================================================


def _aiaugmentedanalytics_views_create_insight(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped AugmentedInsight instance."""
    defaults = {
        "tenant": tenant,
        "title": "Helper Augmented Insight",
        "insight_type": "key_driver",
        "metric_name": "gross_margin_pct",
        "baseline_value": Decimal("32.5000"),
        "observed_value": Decimal("38.2000"),
        "variance_percentage": Decimal("17.54"),
        "impact_direction": "favorable",
        "severity": "medium",
        "confidence_score": Decimal("92.00"),
        "narrative_summary": "Helper narrative explanation of margin growth.",
        "dimension_name": "region",
        "dimension_value": "EMEA",
        "status": "new",
        "created_by": user,
    }
    defaults.update(kwargs)
    return AugmentedInsight.objects.create(**defaults)


def _aiaugmentedanalytics_views_create_suggestion(tenant, target_table, **kwargs):
    """Helper to create a tenant-scoped SmartDataPrepSuggestion instance."""
    defaults = {
        "tenant": tenant,
        "target_table": target_table,
        "target_column": "customer_uuid",
        "suggestion_type": "type_cast",
        "confidence_score": Decimal("88.50"),
        "rationale": "Helper rationale for type cast inference.",
        "status": "pending",
        "suggested_config": {"source_format": "UUIDv4", "target_type": "CHAR(36)"},
    }
    defaults.update(kwargs)
    return SmartDataPrepSuggestion.objects.create(**defaults)


def _aiaugmentedanalytics_views_create_sentiment(tenant, **kwargs):
    """Helper to create a tenant-scoped TextSentimentAnalysis instance."""
    defaults = {
        "tenant": tenant,
        "source_type": "customer_review",
        "source_reference": "REV-HELPER-001",
        "text_content": "Fantastic onboarding experience and great customer support!",
        "language": "en",
        "sentiment_category": "positive",
        "polarity_score": Decimal("0.75"),
        "subjectivity_score": Decimal("0.60"),
        "thematic_tags": ["support", "onboarding"],
    }
    defaults.update(kwargs)
    return TextSentimentAnalysis.objects.create(**defaults)


def _aiaugmentedanalytics_views_create_recommendation(tenant, user, **kwargs):
    """Helper to create a tenant-scoped AnalyticsRecommendation instance."""
    defaults = {
        "tenant": tenant,
        "user": user,
        "recommendation_type": "dashboard",
        "target_title": "Executive Financial Overview",
        "target_url": "/bi/dashboards/1/",
        "reason": "role_relevance",
        "rationale_text": "Suggested based on corporate finance role.",
        "affinity_score": Decimal("91.00"),
        "status": "active",
    }
    defaults.update(kwargs)
    return AnalyticsRecommendation.objects.create(**defaults)


# ==============================================================================
# 1. AugmentedInsight Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_list_context_and_render(client_a, augmented_insight_a):
    """Test augmented insight list returns 200, contract context keys, and rendered content."""
    url = reverse("bi:augmented_insight_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "insights" in resp.context
    assert augmented_insight_a in resp.context["insights"]
    assert "insight_type_choices" in resp.context
    assert "impact_choices" in resp.context
    assert "severity_choices" in resp.context
    assert "status_choices" in resp.context
    assert resp.context["total_count"] >= 1
    assert "critical_count" in resp.context
    assert "key_driver_count" in resp.context
    content = resp.content.decode()
    assert augmented_insight_a.title in content
    assert augmented_insight_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_list_search_and_filters(client_a, tenant_a, augmented_insight_a):
    """Test search query parameter and choice filters on augmented insight list."""
    url = reverse("bi:augmented_insight_list")

    # Search match
    resp_search = client_a.get(f"{url}?q=Enterprise")
    assert resp_search.status_code == 200
    assert augmented_insight_a in resp_search.context["insights"]

    # Search non-match
    resp_empty = client_a.get(f"{url}?q=NonexistentKeyword12345")
    assert resp_empty.status_code == 200
    assert augmented_insight_a not in resp_empty.context["insights"]

    # Choice filters
    resp_type = client_a.get(f"{url}?insight_type=trend_shift")
    assert resp_type.status_code == 200
    assert augmented_insight_a in resp_type.context["insights"]

    resp_wrong_type = client_a.get(f"{url}?insight_type=anomaly")
    assert resp_wrong_type.status_code == 200
    assert augmented_insight_a not in resp_wrong_type.context["insights"]

    resp_impact = client_a.get(f"{url}?impact_direction=favorable")
    assert resp_impact.status_code == 200
    assert augmented_insight_a in resp_impact.context["insights"]

    resp_sev = client_a.get(f"{url}?severity=high")
    assert resp_sev.status_code == 200
    assert augmented_insight_a in resp_sev.context["insights"]

    resp_status = client_a.get(f"{url}?status=new")
    assert resp_status.status_code == 200
    assert augmented_insight_a in resp_status.context["insights"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_feed_context_and_tabs(client_a, augmented_insight_a):
    """Test augmented insight feed returns 200, contract keys, and handles tab filters."""
    url = reverse("bi:augmented_insight_feed")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "feed_items" in resp.context
    assert "severity_choices" in resp.context
    assert "impact_choices" in resp.context
    assert "active_tab" in resp.context
    assert resp.context["active_tab"] == "all"
    assert augmented_insight_a in resp.context["feed_items"]

    # Tab: high
    resp_high = client_a.get(f"{url}?tab=high")
    assert resp_high.status_code == 200
    assert resp_high.context["active_tab"] == "high"
    assert augmented_insight_a in resp_high.context["feed_items"]

    # Tab: critical
    resp_crit = client_a.get(f"{url}?tab=critical")
    assert resp_crit.status_code == 200
    assert resp_crit.context["active_tab"] == "critical"
    assert augmented_insight_a not in resp_crit.context["feed_items"]

    # Tab: unfavorable
    resp_unfav = client_a.get(f"{url}?tab=unfavorable")
    assert resp_unfav.status_code == 200
    assert resp_unfav.context["active_tab"] == "unfavorable"
    assert augmented_insight_a not in resp_unfav.context["feed_items"]

    # Tab: bookmarked
    resp_bkm = client_a.get(f"{url}?tab=bookmarked")
    assert resp_bkm.status_code == 200
    assert resp_bkm.context["active_tab"] == "bookmarked"
    assert augmented_insight_a not in resp_bkm.context["feed_items"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_detail_context_and_drivers(client_a, augmented_insight_a):
    """Test detail view returns 200, exact context keys, and normalized driver list."""
    url = reverse("bi:augmented_insight_detail", kwargs={"pk": augmented_insight_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "insight" in resp.context
    assert resp.context["insight"] == augmented_insight_a
    assert "drivers" in resp.context
    drivers = resp.context["drivers"]
    assert len(drivers) == 1
    assert drivers[0]["name"] == "New Enterprise Logos"
    assert drivers[0]["weight"] == 65
    content = resp.content.decode()
    assert augmented_insight_a.title in content
    assert augmented_insight_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_create_get_form(client_a):
    """Test create view GET returns 200 and context keys."""
    url = reverse("bi:augmented_insight_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["insight"] is None
    assert resp.context["is_edit"] is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_create_post_success(
    client_a, tenant_a, admin_user, semantic_model_a, kpi_definition_a, warehouse_table
):
    """Test create view POST creates record with tenant and audit log, redirects to detail."""
    url = reverse("bi:augmented_insight_create")
    payload = {
        "title": "North America Sales Variance Spike",
        "insight_type": "period_comparison",
        "metric_name": "quarterly_bookings",
        "baseline_value": "500000.0000",
        "observed_value": "620000.0000",
        "variance_percentage": "24.00",
        "impact_direction": "favorable",
        "severity": "high",
        "confidence_score": "95.50",
        "narrative_summary": "Quarterly bookings grew 24% over prior baseline.",
        "dimension_name": "region",
        "dimension_value": "NA-East",
        "status": "new",
        "action_notes": "Follow up with East territory VP.",
        "semantic_model": semantic_model_a.pk,
        "kpi_definition": kpi_definition_a.pk,
        "warehouse_table": warehouse_table.pk,
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AugmentedInsight.objects.filter(
        tenant=tenant_a, title="North America Sales Variance Spike"
    ).first()
    assert created is not None
    assert created.number.startswith("BAIN-")
    assert created.created_by == admin_user
    assert resp.url == reverse("bi:augmented_insight_detail", kwargs={"pk": created.pk})

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("created successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_create_post_invalid(client_a):
    """Test create view POST with invalid data returns 200 with form errors."""
    url = reverse("bi:augmented_insight_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_edit_get_form(client_a, augmented_insight_a):
    """Test edit view GET returns 200 and context keys."""
    url = reverse("bi:augmented_insight_edit", kwargs={"pk": augmented_insight_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["insight"] == augmented_insight_a
    assert resp.context["is_edit"] is True


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_edit_post_success(client_a, tenant_a, augmented_insight_a):
    """Test edit view POST updates record, writes audit log, and redirects to detail."""
    url = reverse("bi:augmented_insight_edit", kwargs={"pk": augmented_insight_a.pk})
    payload = {
        "title": "Q3 Enterprise ARR Surge - Confirmed",
        "insight_type": augmented_insight_a.insight_type,
        "metric_name": augmented_insight_a.metric_name,
        "baseline_value": str(augmented_insight_a.baseline_value),
        "observed_value": str(augmented_insight_a.observed_value),
        "variance_percentage": str(augmented_insight_a.variance_percentage),
        "impact_direction": augmented_insight_a.impact_direction,
        "severity": "critical",
        "confidence_score": "98.00",
        "narrative_summary": "Updated narrative confirmation.",
        "dimension_name": augmented_insight_a.dimension_name,
        "dimension_value": augmented_insight_a.dimension_value,
        "status": "bookmarked",
        "action_notes": "Audited by revenue leadership.",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:augmented_insight_detail", kwargs={"pk": augmented_insight_a.pk})

    augmented_insight_a.refresh_from_db()
    assert augmented_insight_a.title == "Q3 Enterprise ARR Surge - Confirmed"
    assert augmented_insight_a.severity == "critical"
    assert augmented_insight_a.confidence_score == Decimal("98.00")
    assert augmented_insight_a.status == "bookmarked"

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("updated successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_delete_post_and_guard(client_a, tenant_a, admin_user):
    """Test delete view removes record on POST; GET returns 405 Method Not Allowed."""
    insight = _aiaugmentedanalytics_views_create_insight(
        tenant=tenant_a, user=admin_user, title="Insight To Be Deleted"
    )
    url = reverse("bi:augmented_insight_delete", kwargs={"pk": insight.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert AugmentedInsight.objects.filter(pk=insight.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:augmented_insight_list")
    assert not AugmentedInsight.objects.filter(pk=insight.pk).exists()

    messages = [m.message for m in get_messages(resp_post.wsgi_request)]
    assert any("deleted" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_insight_triage_action_and_open_redirect_defense(
    client_a, tenant_a, augmented_insight_a
):
    """Test triage action updates status, notes, writes audit log, and guards open redirects."""
    url = reverse("bi:augmented_insight_triage", kwargs={"pk": augmented_insight_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST with malicious external redirect -> should fallback safely to detail view
    payload_malicious = {
        "status": "actioned",
        "action_notes": "Management took remediation actions.",
        "next": "https://malicious-external-site.com/steal-creds",
    }
    resp_post = client_a.post(url, data=payload_malicious)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:augmented_insight_detail", kwargs={"pk": augmented_insight_a.pk})

    augmented_insight_a.refresh_from_db()
    assert augmented_insight_a.status == "actioned"
    assert "remediation actions" in augmented_insight_a.action_notes

    audit = AuditLog.objects.filter(tenant=tenant_a, action="triage").first()
    assert audit is not None

    # POST with valid safe local next URL
    payload_safe = {
        "status": "bookmarked",
        "action_notes": "Bookmarked for Q4 board review.",
        "next": "/bi/augmented-insights/",
    }
    resp_safe = client_a.post(url, data=payload_safe)
    assert resp_safe.status_code == 302
    assert resp_safe.url == "/bi/augmented-insights/"
    augmented_insight_a.refresh_from_db()
    assert augmented_insight_a.status == "bookmarked"


# ==============================================================================
# 2. SmartDataPrepSuggestion Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_list_context_and_render(
    client_a, smart_data_prep_suggestion_a
):
    """Test smart data prep suggestion list returns 200, contract context keys, and content."""
    url = reverse("bi:smart_data_prep_suggestion_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "suggestions" in resp.context
    assert smart_data_prep_suggestion_a in resp.context["suggestions"]
    assert "suggestion_type_choices" in resp.context
    assert "status_choices" in resp.context
    assert "tables" in resp.context
    assert "pending_count" in resp.context
    assert resp.context["pending_count"] >= 1
    content = resp.content.decode()
    assert smart_data_prep_suggestion_a.target_column in content
    assert smart_data_prep_suggestion_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_list_search_and_filters(
    client_a, smart_data_prep_suggestion_a, warehouse_table
):
    """Test search query and filter parameters on smart data prep suggestions list."""
    url = reverse("bi:smart_data_prep_suggestion_list")

    # Search match
    resp_search = client_a.get(f"{url}?q=order_timestamp")
    assert resp_search.status_code == 200
    assert smart_data_prep_suggestion_a in resp_search.context["suggestions"]

    # Search non-match
    resp_empty = client_a.get(f"{url}?q=NonexistentPrepColumn999")
    assert resp_empty.status_code == 200
    assert smart_data_prep_suggestion_a not in resp_empty.context["suggestions"]

    # Filter: suggestion_type
    resp_type = client_a.get(f"{url}?suggestion_type=type_cast")
    assert resp_type.status_code == 200
    assert smart_data_prep_suggestion_a in resp_type.context["suggestions"]

    resp_wrong_type = client_a.get(f"{url}?suggestion_type=impute_missing")
    assert resp_wrong_type.status_code == 200
    assert smart_data_prep_suggestion_a not in resp_wrong_type.context["suggestions"]

    # Filter: status
    resp_status = client_a.get(f"{url}?status=pending")
    assert resp_status.status_code == 200
    assert smart_data_prep_suggestion_a in resp_status.context["suggestions"]

    # Filter: target_table
    resp_tbl = client_a.get(f"{url}?target_table={warehouse_table.pk}")
    assert resp_tbl.status_code == 200
    assert smart_data_prep_suggestion_a in resp_tbl.context["suggestions"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_detail_context_and_config(
    client_a, smart_data_prep_suggestion_a
):
    """Test smart data prep detail view returns 200, contract keys, and parsed config items."""
    url = reverse("bi:smart_data_prep_suggestion_detail", kwargs={"pk": smart_data_prep_suggestion_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "suggestion" in resp.context
    assert resp.context["suggestion"] == smart_data_prep_suggestion_a
    assert "config_items" in resp.context
    config_dict = dict(resp.context["config_items"])
    assert config_dict.get("target_type") == "TIMESTAMP"
    content = resp.content.decode()
    assert smart_data_prep_suggestion_a.target_column in content
    assert smart_data_prep_suggestion_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_create_get_form(client_a):
    """Test smart data prep create view GET returns 200 and contract keys."""
    url = reverse("bi:smart_data_prep_suggestion_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["suggestion"] is None
    assert resp.context["is_edit"] is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_create_post_success(
    client_a, tenant_a, warehouse_table
):
    """Test smart data prep create POST creates suggestion with tenant and audit log."""
    url = reverse("bi:smart_data_prep_suggestion_create")
    payload = {
        "target_table": warehouse_table.pk,
        "target_column": "customer_id",
        "suggestion_type": "join_relationship",
        "related_table": warehouse_table.pk,
        "related_column": "id",
        "confidence_score": "96.50",
        "rationale": "High statistical cardinality match between customer_id and dimension id.",
        "status": "pending",
        "review_notes": "Pending schema reviewer approval.",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = SmartDataPrepSuggestion.objects.filter(
        tenant=tenant_a, target_column="customer_id"
    ).first()
    assert created is not None
    assert created.number.startswith("BSDP-")
    assert resp.url == reverse("bi:smart_data_prep_suggestion_detail", kwargs={"pk": created.pk})

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("created successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_create_post_invalid(client_a):
    """Test smart data prep create POST with missing required fields returns 200."""
    url = reverse("bi:smart_data_prep_suggestion_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_edit_get_form(client_a, smart_data_prep_suggestion_a):
    """Test smart data prep edit view GET returns 200 and context keys."""
    url = reverse("bi:smart_data_prep_suggestion_edit", kwargs={"pk": smart_data_prep_suggestion_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["suggestion"] == smart_data_prep_suggestion_a
    assert resp.context["is_edit"] is True


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_edit_post_success(
    client_a, tenant_a, smart_data_prep_suggestion_a, warehouse_table
):
    """Test smart data prep edit POST updates suggestion, writes audit log, redirects."""
    url = reverse("bi:smart_data_prep_suggestion_edit", kwargs={"pk": smart_data_prep_suggestion_a.pk})
    payload = {
        "target_table": warehouse_table.pk,
        "target_column": "order_timestamp",
        "suggestion_type": smart_data_prep_suggestion_a.suggestion_type,
        "confidence_score": "98.00",
        "rationale": "Updated rationale for timestamp casting.",
        "status": "pending",
        "review_notes": "Reviewed by lead ETL engineer.",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:smart_data_prep_suggestion_detail", kwargs={"pk": smart_data_prep_suggestion_a.pk})

    smart_data_prep_suggestion_a.refresh_from_db()
    assert smart_data_prep_suggestion_a.confidence_score == Decimal("98.00")
    assert smart_data_prep_suggestion_a.review_notes == "Reviewed by lead ETL engineer."

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("updated successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_delete_post_and_guard(
    client_a, tenant_a, warehouse_table
):
    """Test delete prep suggestion removes record on POST; GET returns 405 Method Not Allowed."""
    sugg = _aiaugmentedanalytics_views_create_suggestion(
        tenant=tenant_a, target_table=warehouse_table, target_column="temp_col"
    )
    url = reverse("bi:smart_data_prep_suggestion_delete", kwargs={"pk": sugg.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert SmartDataPrepSuggestion.objects.filter(pk=sugg.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:smart_data_prep_suggestion_list")
    assert not SmartDataPrepSuggestion.objects.filter(pk=sugg.pk).exists()

    messages = [m.message for m in get_messages(resp_post.wsgi_request)]
    assert any("deleted" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_action_accept_and_apply(
    client_a, tenant_a, admin_user, smart_data_prep_suggestion_a
):
    """Test action view transition from pending to accepted and then applied."""
    url = reverse("bi:smart_data_prep_suggestion_action", kwargs={"pk": smart_data_prep_suggestion_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # Accept action
    payload_accept = {
        "action_type": "accept",
        "review_notes": "Accepted transformation proposal.",
    }
    resp_accept = client_a.post(url, data=payload_accept)
    assert resp_accept.status_code == 302
    assert resp_accept.url == reverse("bi:smart_data_prep_suggestion_detail", kwargs={"pk": smart_data_prep_suggestion_a.pk})

    smart_data_prep_suggestion_a.refresh_from_db()
    assert smart_data_prep_suggestion_a.status == "accepted"
    assert smart_data_prep_suggestion_a.reviewed_by == admin_user
    assert smart_data_prep_suggestion_a.reviewed_at is not None

    audit = AuditLog.objects.filter(tenant=tenant_a, action="accept").first()
    assert audit is not None

    # Apply action
    payload_apply = {
        "action_type": "apply",
        "review_notes": "Applied migration script to warehouse table.",
    }
    resp_apply = client_a.post(url, data=payload_apply)
    assert resp_apply.status_code == 302
    smart_data_prep_suggestion_a.refresh_from_db()
    assert smart_data_prep_suggestion_a.status == "applied"


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_action_already_applied_warning(
    client_a, smart_data_prep_suggestion_a
):
    """Test that modifying an already applied suggestion triggers warning message."""
    smart_data_prep_suggestion_a.status = "applied"
    smart_data_prep_suggestion_a.save()

    url = reverse("bi:smart_data_prep_suggestion_action", kwargs={"pk": smart_data_prep_suggestion_a.pk})
    resp = client_a.post(url, data={"action_type": "reject"})
    assert resp.status_code == 302

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("already been applied" in m for m in messages)

    smart_data_prep_suggestion_a.refresh_from_db()
    assert smart_data_prep_suggestion_a.status == "applied"


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_dataprep_action_open_redirect_defense(
    client_a, smart_data_prep_suggestion_a
):
    """Test open redirect defense on smart data prep suggestion action."""
    url = reverse("bi:smart_data_prep_suggestion_action", kwargs={"pk": smart_data_prep_suggestion_a.pk})

    # Malicious external redirect
    resp = client_a.post(
        url,
        data={
            "action_type": "reject",
            "review_notes": "Rejected due to schema incompatibility.",
            "next": "//evil-phishing-url.com",
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse("bi:smart_data_prep_suggestion_detail", kwargs={"pk": smart_data_prep_suggestion_a.pk})

    # Safe local redirect
    resp_safe = client_a.post(
        url,
        data={
            "action_type": "accept",
            "next": "/bi/data-prep-suggestions/",
        },
    )
    assert resp_safe.status_code == 302
    assert resp_safe.url == "/bi/data-prep-suggestions/"


# ==============================================================================
# 3. TextSentimentAnalysis Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_list_context_and_render(
    client_a, text_sentiment_analysis_a
):
    """Test text sentiment analysis list returns 200, contract keys, and aggregations."""
    url = reverse("bi:text_sentiment_analysis_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "analyses" in resp.context
    assert text_sentiment_analysis_a in resp.context["analyses"]
    assert "source_type_choices" in resp.context
    assert "sentiment_category_choices" in resp.context
    assert "positive_count" in resp.context
    assert "negative_count" in resp.context
    assert "avg_polarity" in resp.context
    assert resp.context["positive_count"] >= 1
    content = resp.content.decode()
    assert text_sentiment_analysis_a.source_reference in content
    assert text_sentiment_analysis_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_list_search_and_filters(
    client_a, text_sentiment_analysis_a
):
    """Test search query parameter and choices filters on sentiment analysis list."""
    url = reverse("bi:text_sentiment_analysis_list")

    # Search match
    resp_search = client_a.get(f"{url}?q=TKT-88412")
    assert resp_search.status_code == 200
    assert text_sentiment_analysis_a in resp_search.context["analyses"]

    # Search non-match
    resp_empty = client_a.get(f"{url}?q=NonexistentTicket99999")
    assert resp_empty.status_code == 200
    assert text_sentiment_analysis_a not in resp_empty.context["analyses"]

    # Filter: source_type
    resp_src = client_a.get(f"{url}?source_type=support_ticket")
    assert resp_src.status_code == 200
    assert text_sentiment_analysis_a in resp_src.context["analyses"]

    resp_wrong_src = client_a.get(f"{url}?source_type=customer_review")
    assert resp_wrong_src.status_code == 200
    assert text_sentiment_analysis_a not in resp_wrong_src.context["analyses"]

    # Filter: sentiment_category
    resp_cat = client_a.get(f"{url}?sentiment_category=positive")
    assert resp_cat.status_code == 200
    assert text_sentiment_analysis_a in resp_cat.context["analyses"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_detail_context_and_tags(
    client_a, text_sentiment_analysis_a
):
    """Test sentiment analysis detail returns 200, contract keys, and parsed thematic tags."""
    url = reverse("bi:text_sentiment_analysis_detail", kwargs={"pk": text_sentiment_analysis_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "analysis" in resp.context
    assert resp.context["analysis"] == text_sentiment_analysis_a
    assert "thematic_tags_list" in resp.context
    tags = resp.context["thematic_tags_list"]
    assert "support" in tags
    assert "onboarding" in tags
    content = resp.content.decode()
    assert text_sentiment_analysis_a.source_reference in content
    assert text_sentiment_analysis_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_create_get_form(client_a):
    """Test sentiment analysis create view GET returns 200 and contract keys."""
    url = reverse("bi:text_sentiment_analysis_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["analysis"] is None
    assert resp.context["is_edit"] is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_create_post_success_with_autoscore(
    client_a, tenant_a
):
    """Test sentiment create POST auto-calculates polarity when left default neutral."""
    url = reverse("bi:text_sentiment_analysis_create")
    payload = {
        "source_type": "customer_review",
        "source_reference": "REV-2026-AUTO",
        "text_content": "The application is fantastic, smooth, clean and really great!",
        "language": "en",
        "sentiment_category": "neutral",
        "polarity_score": "0.00",
        "subjectivity_score": "0.50",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = TextSentimentAnalysis.objects.filter(
        tenant=tenant_a, source_reference="REV-2026-AUTO"
    ).first()
    assert created is not None
    assert created.number.startswith("BSNT-")
    # Natural language auto-scoring evaluated positive words
    assert created.polarity_score > Decimal("0.00")
    assert created.sentiment_category in ["positive", "very_positive"]
    assert len(created.thematic_tags) > 0
    assert resp.url == reverse("bi:text_sentiment_analysis_detail", kwargs={"pk": created.pk})

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("created successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_create_post_invalid(client_a):
    """Test sentiment create POST with missing required fields returns 200."""
    url = reverse("bi:text_sentiment_analysis_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_edit_get_form(client_a, text_sentiment_analysis_a):
    """Test sentiment edit view GET returns 200 and contract keys."""
    url = reverse("bi:text_sentiment_analysis_edit", kwargs={"pk": text_sentiment_analysis_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["analysis"] == text_sentiment_analysis_a
    assert resp.context["is_edit"] is True


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_edit_post_success(
    client_a, tenant_a, text_sentiment_analysis_a
):
    """Test sentiment edit POST updates values, writes audit log, redirects."""
    url = reverse("bi:text_sentiment_analysis_edit", kwargs={"pk": text_sentiment_analysis_a.pk})
    payload = {
        "source_type": text_sentiment_analysis_a.source_type,
        "source_reference": "TKT-88412-EDITED",
        "text_content": text_sentiment_analysis_a.text_content,
        "language": "en",
        "sentiment_category": "very_positive",
        "polarity_score": "0.95",
        "subjectivity_score": "0.70",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:text_sentiment_analysis_detail", kwargs={"pk": text_sentiment_analysis_a.pk})

    text_sentiment_analysis_a.refresh_from_db()
    assert text_sentiment_analysis_a.source_reference == "TKT-88412-EDITED"
    assert text_sentiment_analysis_a.sentiment_category == "very_positive"
    assert text_sentiment_analysis_a.polarity_score == Decimal("0.95")

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("updated successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_delete_post_and_guard(client_a, tenant_a):
    """Test delete sentiment record removes record on POST; GET returns 405 Method Not Allowed."""
    rec = _aiaugmentedanalytics_views_create_sentiment(
        tenant=tenant_a, source_reference="REV-TO-BE-DELETED"
    )
    url = reverse("bi:text_sentiment_analysis_delete", kwargs={"pk": rec.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert TextSentimentAnalysis.objects.filter(pk=rec.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:text_sentiment_analysis_list")
    assert not TextSentimentAnalysis.objects.filter(pk=rec.pk).exists()

    messages = [m.message for m in get_messages(resp_post.wsgi_request)]
    assert any("deleted" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_sentiment_recalculate_action_and_open_redirect_defense(
    client_a, tenant_a
):
    """Test recalculate sentiment action re-evaluates text and guards open redirects."""
    rec = _aiaugmentedanalytics_views_create_sentiment(
        tenant=tenant_a,
        source_reference="REV-RECALC-TEST",
        text_content="Awful slow system, terrible broken bug and worst frustrating delay!",
        polarity_score=Decimal("0.00"),
        sentiment_category="neutral",
    )
    url = reverse("bi:text_sentiment_analysis_recalculate", kwargs={"pk": rec.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST with malicious open redirect
    payload = {"next": "https://attacker.site/leak"}
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:text_sentiment_analysis_detail", kwargs={"pk": rec.pk})

    rec.refresh_from_db()
    assert rec.polarity_score < Decimal("0.00")
    assert rec.sentiment_category in ["negative", "very_negative"]
    assert "bug" in rec.thematic_tags or "delay" in rec.thematic_tags or "slow" in rec.thematic_tags

    audit = AuditLog.objects.filter(tenant=tenant_a, action="recalc").first()
    assert audit is not None

    # Safe local redirect
    resp_safe = client_a.post(url, data={"next": "/bi/sentiment-analyses/"})
    assert resp_safe.status_code == 302
    assert resp_safe.url == "/bi/sentiment-analyses/"


# ==============================================================================
# 4. AnalyticsRecommendation Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_list_context_and_render(
    client_a, analytics_recommendation_a
):
    """Test analytics recommendation list returns 200, contract keys, and content."""
    url = reverse("bi:analytics_recommendation_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "recommendations" in resp.context
    assert analytics_recommendation_a in resp.context["recommendations"]
    assert "recommendation_type_choices" in resp.context
    assert "reason_choices" in resp.context
    assert "status_choices" in resp.context
    assert "active_count" in resp.context
    assert resp.context["active_count"] >= 1
    content = resp.content.decode()
    assert analytics_recommendation_a.target_title in content
    assert analytics_recommendation_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_list_search_and_filters(
    client_a, analytics_recommendation_a
):
    """Test search query parameter and choice filters on recommendation list."""
    url = reverse("bi:analytics_recommendation_list")

    # Search match
    resp_search = client_a.get(f"{url}?q=Executive")
    assert resp_search.status_code == 200
    assert analytics_recommendation_a in resp_search.context["recommendations"]

    # Search non-match
    resp_empty = client_a.get(f"{url}?q=NonexistentRecommendation999")
    assert resp_empty.status_code == 200
    assert analytics_recommendation_a not in resp_empty.context["recommendations"]

    # Filter: recommendation_type
    resp_type = client_a.get(f"{url}?recommendation_type=dashboard")
    assert resp_type.status_code == 200
    assert analytics_recommendation_a in resp_type.context["recommendations"]

    resp_wrong_type = client_a.get(f"{url}?recommendation_type=kpi")
    assert resp_wrong_type.status_code == 200
    assert analytics_recommendation_a not in resp_wrong_type.context["recommendations"]

    # Filter: reason
    resp_reason = client_a.get(f"{url}?reason=role_relevance")
    assert resp_reason.status_code == 200
    assert analytics_recommendation_a in resp_reason.context["recommendations"]

    # Filter: status
    resp_status = client_a.get(f"{url}?status=active")
    assert resp_status.status_code == 200
    assert analytics_recommendation_a in resp_status.context["recommendations"]


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_detail_context(
    client_a, analytics_recommendation_a
):
    """Test recommendation detail view returns 200 and contract keys."""
    url = reverse("bi:analytics_recommendation_detail", kwargs={"pk": analytics_recommendation_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "recommendation" in resp.context
    assert resp.context["recommendation"] == analytics_recommendation_a
    content = resp.content.decode()
    assert analytics_recommendation_a.target_title in content
    assert analytics_recommendation_a.number in content


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_create_get_form(client_a):
    """Test recommendation create view GET returns 200 and contract keys."""
    url = reverse("bi:analytics_recommendation_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["recommendation"] is None
    assert resp.context["is_edit"] is False


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_create_post_success(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test recommendation create POST creates record with tenant and audit log."""
    url = reverse("bi:analytics_recommendation_create")
    payload = {
        "user": admin_user.pk,
        "recommendation_type": "dashboard",
        "target_title": "Operations Supply Chain Dashboard",
        "target_url": "/bi/dashboards/10/",
        "reason": "trending_metric",
        "rationale_text": "High usage among peer operational directors.",
        "affinity_score": "87.50",
        "status": "active",
        "dashboard": bi_dashboard_a.pk,
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AnalyticsRecommendation.objects.filter(
        tenant=tenant_a, target_title="Operations Supply Chain Dashboard"
    ).first()
    assert created is not None
    assert created.number.startswith("BARC-")
    assert resp.url == reverse("bi:analytics_recommendation_detail", kwargs={"pk": created.pk})

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("created successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_create_post_invalid(client_a):
    """Test recommendation create POST with invalid data returns 200."""
    url = reverse("bi:analytics_recommendation_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_edit_get_form(
    client_a, analytics_recommendation_a
):
    """Test recommendation edit view GET returns 200 and contract keys."""
    url = reverse("bi:analytics_recommendation_edit", kwargs={"pk": analytics_recommendation_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["recommendation"] == analytics_recommendation_a
    assert resp.context["is_edit"] is True


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_edit_post_success(
    client_a, tenant_a, admin_user, analytics_recommendation_a
):
    """Test recommendation edit POST updates record, writes audit log, redirects."""
    url = reverse("bi:analytics_recommendation_edit", kwargs={"pk": analytics_recommendation_a.pk})
    payload = {
        "user": admin_user.pk,
        "recommendation_type": analytics_recommendation_a.recommendation_type,
        "target_title": "Executive Revenue Dashboard (Refreshed)",
        "target_url": "/bi/dashboards/1/",
        "reason": "role_relevance",
        "rationale_text": "Updated rationale for executive user.",
        "affinity_score": "96.00",
        "status": "saved",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:analytics_recommendation_detail", kwargs={"pk": analytics_recommendation_a.pk})

    analytics_recommendation_a.refresh_from_db()
    assert analytics_recommendation_a.target_title == "Executive Revenue Dashboard (Refreshed)"
    assert analytics_recommendation_a.affinity_score == Decimal("96.00")
    assert analytics_recommendation_a.status == "saved"

    messages = [m.message for m in get_messages(resp.wsgi_request)]
    assert any("updated successfully" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_delete_post_and_guard(
    client_a, tenant_a, admin_user
):
    """Test delete recommendation removes record on POST; GET returns 405 Method Not Allowed."""
    rec = _aiaugmentedanalytics_views_create_recommendation(
        tenant=tenant_a, user=admin_user, target_title="Recommendation Scheduled For Deletion"
    )
    url = reverse("bi:analytics_recommendation_delete", kwargs={"pk": rec.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert AnalyticsRecommendation.objects.filter(pk=rec.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:analytics_recommendation_list")
    assert not AnalyticsRecommendation.objects.filter(pk=rec.pk).exists()

    messages = [m.message for m in get_messages(resp_post.wsgi_request)]
    assert any("deleted" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").first()
    assert audit is not None


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_interact_action_and_open_redirect_defense(
    client_a, tenant_a, analytics_recommendation_a
):
    """Test interact action updates status to saved/clicked, records timestamp, and guards redirects."""
    url = reverse("bi:analytics_recommendation_interact", kwargs={"pk": analytics_recommendation_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST with malicious redirect -> fallback to detail
    payload = {
        "interaction_type": "save",
        "next": "https://malicious-external-site.com/exploit",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:analytics_recommendation_detail", kwargs={"pk": analytics_recommendation_a.pk})

    analytics_recommendation_a.refresh_from_db()
    assert analytics_recommendation_a.status == "saved"
    assert analytics_recommendation_a.last_interacted_at is not None

    audit = AuditLog.objects.filter(tenant=tenant_a, action="save").first()
    assert audit is not None

    # Safe local redirect
    resp_safe = client_a.post(
        url,
        data={
            "interaction_type": "click",
            "next": "/bi/recommendations/",
        },
    )
    assert resp_safe.status_code == 302
    assert resp_safe.url == "/bi/recommendations/"
    analytics_recommendation_a.refresh_from_db()
    assert analytics_recommendation_a.status == "clicked"


@pytest.mark.django_db
def test_aiaugmentedanalytics_views_recommendation_interact_permission_denied(
    client, tenant_a, analytics_recommendation_a
):
    """Test that another regular user cannot interact with another user's recommendation."""
    other_user = User.objects.create_user(
        username="other_staff_user",
        email="other@acme.com",
        password="TestPassword123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )
    client.force_login(other_user)

    url = reverse("bi:analytics_recommendation_interact", kwargs={"pk": analytics_recommendation_a.pk})
    resp = client.post(url, data={"interaction_type": "save"})
    assert resp.status_code == 403
