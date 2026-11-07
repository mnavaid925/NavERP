"""Security, Multi-Tenancy, Authorization, and RBAC Test Suite for Sub-module 10.14:
AI & Augmented Analytics (apps/bi).

Covers:
1. Cross-Tenant IDOR:
   - Tenant A accessing Tenant B's objects across all object endpoints returns strictly HTTP 404:
     - bi:augmented_insight_detail, bi:augmented_insight_edit, bi:augmented_insight_delete, bi:augmented_insight_triage
     - bi:smart_data_prep_suggestion_detail, bi:smart_data_prep_suggestion_edit, bi:smart_data_prep_suggestion_delete, bi:smart_data_prep_suggestion_action
     - bi:text_sentiment_analysis_detail, bi:text_sentiment_analysis_edit, bi:text_sentiment_analysis_delete, bi:text_sentiment_analysis_recalculate
     - bi:analytics_recommendation_detail, bi:analytics_recommendation_edit, bi:analytics_recommendation_delete, bi:analytics_recommendation_interact
   - Bidirectional reverse IDOR: Tenant B accessing Tenant A's objects returns HTTP 404.
2. Cross-Tenant List Isolation:
   - Tenant A querying lists never sees Tenant B records (list, feed, prep suggestion, sentiment, recommendation).
   - Tenant B querying lists never sees Tenant A records.
3. Authentication Gates (@login_required):
   - Anonymous client accessing any 10.14 endpoint redirected to login (HTTP 302).
4. Authorization Gates (@tenant_admin_required):
   - Deletion views enforce @tenant_admin_required: standard authenticated non-admin user (member_client)
     receives HTTP 403 Forbidden.
   - Non-admin member user retains read access (HTTP 200).
5. Action Permissions & Ownership:
   - analytics_recommendation_interact: non-admin user cannot mutate another user's recommendation (returns 403 / PermissionDenied).
   - Designated user and tenant admin can interact (returns 302).
   - State guard: smart_data_prep_suggestion_action cannot transition an already applied suggestion.
6. Open Redirect Protection:
   - Mutating POST views with external/malicious next parameters safely fall back to detail route.
   - Valid relative internal next parameters are honored.
7. XSS & Injection:
   - AnalyticsRecommendationForm rejects javascript:, protocol-relative (//), and absolute URLs for target_url.
   - Cross-tenant foreign key injection rejection across all forms (reject_foreign).
8. HTTP Method Constraints (@require_POST):
   - Delete and action endpoints reject GET requests with HTTP 405 Method Not Allowed.
9. Audit Logging Security Verification:
   - Security-critical operations generate AuditLog entries correctly scoped to tenant and actor.
"""
from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.bi.forms.AiAugmentedAnalytics.AnalyticsRecommendations import AnalyticsRecommendationForm
from apps.bi.forms.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsightForm
from apps.bi.forms.AiAugmentedAnalytics.SmartDataPrepSuggestions import SmartDataPrepSuggestionForm
from apps.bi.forms.AiAugmentedAnalytics.TextSentimentAnalyses import TextSentimentAnalysisForm
from apps.bi.models.AiAugmentedAnalytics.AnalyticsRecommendations import AnalyticsRecommendation
from apps.bi.models.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsight
from apps.bi.models.AiAugmentedAnalytics.SmartDataPrepSuggestions import SmartDataPrepSuggestion
from apps.bi.models.AiAugmentedAnalytics.TextSentimentAnalyses import TextSentimentAnalysis
from apps.core.models import AuditLog, OrgUnit, Party

User = get_user_model()
pytestmark = pytest.mark.django_db


# ===========================================================================
# Module Helpers (prefixed with _aiaugmentedanalytics_security_*)
# ===========================================================================


def _aiaugmentedanalytics_security_create_recommendation(
    tenant, user, title="Security Target Rec", url="/bi/dashboards/1/", status="active"
):
    """Helper to create a tenant-isolated AnalyticsRecommendation instance."""
    num = f"BARC-{uuid.uuid4().hex[:5].upper()}"
    return AnalyticsRecommendation.objects.create(
        tenant=tenant,
        number=num,
        user=user,
        recommendation_type="dashboard",
        target_title=title,
        target_url=url,
        reason="role_relevance",
        rationale_text="Security test recommendation rationale.",
        affinity_score=Decimal("88.00"),
        status=status,
    )


# ===========================================================================
# 1. Cross-Tenant IDOR Protection
# ===========================================================================


def test_aiaugmentedanalytics_security_cross_tenant_idor_tenant_a_on_b_returns_404(
    client_a,
    augmented_insight_b,
    smart_data_prep_suggestion_b,
    text_sentiment_analysis_b,
    analytics_recommendation_b,
):
    """Verify Client A accessing Client B's objects returns HTTP 404 across all operations."""
    idor_targets = [
        # AugmentedInsight (detail, edit GET/POST, delete POST, triage POST)
        ("GET", reverse("bi:augmented_insight_detail", args=[augmented_insight_b.pk]), {}),
        ("GET", reverse("bi:augmented_insight_edit", args=[augmented_insight_b.pk]), {}),
        ("POST", reverse("bi:augmented_insight_edit", args=[augmented_insight_b.pk]), {"title": "IDOR Attempt"}),
        ("POST", reverse("bi:augmented_insight_delete", args=[augmented_insight_b.pk]), {}),
        ("POST", reverse("bi:augmented_insight_triage", args=[augmented_insight_b.pk]), {"status": "in_review"}),

        # SmartDataPrepSuggestion (detail, edit GET/POST, delete POST, action POST)
        ("GET", reverse("bi:smart_data_prep_suggestion_detail", args=[smart_data_prep_suggestion_b.pk]), {}),
        ("GET", reverse("bi:smart_data_prep_suggestion_edit", args=[smart_data_prep_suggestion_b.pk]), {}),
        ("POST", reverse("bi:smart_data_prep_suggestion_edit", args=[smart_data_prep_suggestion_b.pk]), {"rationale": "IDOR Attempt"}),
        ("POST", reverse("bi:smart_data_prep_suggestion_delete", args=[smart_data_prep_suggestion_b.pk]), {}),
        ("POST", reverse("bi:smart_data_prep_suggestion_action", args=[smart_data_prep_suggestion_b.pk]), {"action_type": "accept"}),

        # TextSentimentAnalysis (detail, edit GET/POST, delete POST, recalculate POST)
        ("GET", reverse("bi:text_sentiment_analysis_detail", args=[text_sentiment_analysis_b.pk]), {}),
        ("GET", reverse("bi:text_sentiment_analysis_edit", args=[text_sentiment_analysis_b.pk]), {}),
        ("POST", reverse("bi:text_sentiment_analysis_edit", args=[text_sentiment_analysis_b.pk]), {"text_content": "IDOR text"}),
        ("POST", reverse("bi:text_sentiment_analysis_delete", args=[text_sentiment_analysis_b.pk]), {}),
        ("POST", reverse("bi:text_sentiment_analysis_recalculate", args=[text_sentiment_analysis_b.pk]), {}),

        # AnalyticsRecommendation (detail, edit GET/POST, delete POST, interact POST)
        ("GET", reverse("bi:analytics_recommendation_detail", args=[analytics_recommendation_b.pk]), {}),
        ("GET", reverse("bi:analytics_recommendation_edit", args=[analytics_recommendation_b.pk]), {}),
        ("POST", reverse("bi:analytics_recommendation_edit", args=[analytics_recommendation_b.pk]), {"target_title": "IDOR title"}),
        ("POST", reverse("bi:analytics_recommendation_delete", args=[analytics_recommendation_b.pk]), {}),
        ("POST", reverse("bi:analytics_recommendation_interact", args=[analytics_recommendation_b.pk]), {"interaction_type": "click"}),
    ]

    for method, url, data in idor_targets:
        res = client_a.get(url) if method == "GET" else client_a.post(url, data)
        assert res.status_code == 404, f"IDOR Vulnerability detected: Client A {method} {url} returned {res.status_code}"


def test_aiaugmentedanalytics_security_reverse_cross_tenant_idor_tenant_b_on_a_returns_404(
    client_b,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify Client B accessing Client A's objects returns HTTP 404 across all operations."""
    reverse_idor_targets = [
        # AugmentedInsight
        ("GET", reverse("bi:augmented_insight_detail", args=[augmented_insight_a.pk]), {}),
        ("GET", reverse("bi:augmented_insight_edit", args=[augmented_insight_a.pk]), {}),
        ("POST", reverse("bi:augmented_insight_edit", args=[augmented_insight_a.pk]), {"title": "Reverse IDOR"}),
        ("POST", reverse("bi:augmented_insight_delete", args=[augmented_insight_a.pk]), {}),
        ("POST", reverse("bi:augmented_insight_triage", args=[augmented_insight_a.pk]), {"status": "in_review"}),

        # SmartDataPrepSuggestion
        ("GET", reverse("bi:smart_data_prep_suggestion_detail", args=[smart_data_prep_suggestion_a.pk]), {}),
        ("GET", reverse("bi:smart_data_prep_suggestion_edit", args=[smart_data_prep_suggestion_a.pk]), {}),
        ("POST", reverse("bi:smart_data_prep_suggestion_edit", args=[smart_data_prep_suggestion_a.pk]), {"rationale": "Reverse IDOR"}),
        ("POST", reverse("bi:smart_data_prep_suggestion_delete", args=[smart_data_prep_suggestion_a.pk]), {}),
        ("POST", reverse("bi:smart_data_prep_suggestion_action", args=[smart_data_prep_suggestion_a.pk]), {"action_type": "accept"}),

        # TextSentimentAnalysis
        ("GET", reverse("bi:text_sentiment_analysis_detail", args=[text_sentiment_analysis_a.pk]), {}),
        ("GET", reverse("bi:text_sentiment_analysis_edit", args=[text_sentiment_analysis_a.pk]), {}),
        ("POST", reverse("bi:text_sentiment_analysis_edit", args=[text_sentiment_analysis_a.pk]), {"text_content": "Reverse IDOR text"}),
        ("POST", reverse("bi:text_sentiment_analysis_delete", args=[text_sentiment_analysis_a.pk]), {}),
        ("POST", reverse("bi:text_sentiment_analysis_recalculate", args=[text_sentiment_analysis_a.pk]), {}),

        # AnalyticsRecommendation
        ("GET", reverse("bi:analytics_recommendation_detail", args=[analytics_recommendation_a.pk]), {}),
        ("GET", reverse("bi:analytics_recommendation_edit", args=[analytics_recommendation_a.pk]), {}),
        ("POST", reverse("bi:analytics_recommendation_edit", args=[analytics_recommendation_a.pk]), {"target_title": "Reverse IDOR title"}),
        ("POST", reverse("bi:analytics_recommendation_delete", args=[analytics_recommendation_a.pk]), {}),
        ("POST", reverse("bi:analytics_recommendation_interact", args=[analytics_recommendation_a.pk]), {"interaction_type": "click"}),
    ]

    for method, url, data in reverse_idor_targets:
        res = client_b.get(url) if method == "GET" else client_b.post(url, data)
        assert res.status_code == 404, f"Reverse IDOR Vulnerability: Client B {method} {url} returned {res.status_code}"


# ===========================================================================
# 2. Cross-Tenant List Isolation
# ===========================================================================


def test_aiaugmentedanalytics_security_list_isolation_tenant_a_never_sees_tenant_b(
    client_a,
    augmented_insight_a,
    augmented_insight_b,
    smart_data_prep_suggestion_a,
    smart_data_prep_suggestion_b,
    text_sentiment_analysis_a,
    text_sentiment_analysis_b,
    analytics_recommendation_a,
    analytics_recommendation_b,
):
    """Verify Tenant A querying lists never sees Tenant B records in context or rendered HTML."""
    # 1. AugmentedInsight list
    res = client_a.get(reverse("bi:augmented_insight_list"))
    assert res.status_code == 200
    insights = list(res.context["insights"])
    assert augmented_insight_a in insights
    assert augmented_insight_b not in insights
    content = res.content.decode()
    assert augmented_insight_b.number not in content
    assert augmented_insight_b.title not in content

    # 2. AugmentedInsight feed
    res_feed = client_a.get(reverse("bi:augmented_insight_feed"))
    assert res_feed.status_code == 200
    feed_items = list(res_feed.context["feed_items"])
    assert augmented_insight_a in feed_items
    assert augmented_insight_b not in feed_items
    feed_content = res_feed.content.decode()
    assert augmented_insight_b.number not in feed_content
    assert augmented_insight_b.title not in feed_content

    # 3. SmartDataPrepSuggestion list
    res_prep = client_a.get(reverse("bi:smart_data_prep_suggestion_list"))
    assert res_prep.status_code == 200
    suggestions = list(res_prep.context["suggestions"])
    assert smart_data_prep_suggestion_a in suggestions
    assert smart_data_prep_suggestion_b not in suggestions
    prep_content = res_prep.content.decode()
    assert smart_data_prep_suggestion_b.number not in prep_content
    assert smart_data_prep_suggestion_b.rationale not in prep_content

    # 4. TextSentimentAnalysis list
    res_snt = client_a.get(reverse("bi:text_sentiment_analysis_list"))
    assert res_snt.status_code == 200
    analyses = list(res_snt.context["analyses"])
    assert text_sentiment_analysis_a in analyses
    assert text_sentiment_analysis_b not in analyses
    snt_content = res_snt.content.decode()
    assert text_sentiment_analysis_b.number not in snt_content
    assert text_sentiment_analysis_b.source_reference not in snt_content

    # 5. AnalyticsRecommendation list
    res_rec = client_a.get(reverse("bi:analytics_recommendation_list"))
    assert res_rec.status_code == 200
    recommendations = list(res_rec.context["recommendations"])
    assert analytics_recommendation_a in recommendations
    assert analytics_recommendation_b not in recommendations
    rec_content = res_rec.content.decode()
    assert analytics_recommendation_b.number not in rec_content
    assert analytics_recommendation_b.target_title not in rec_content


def test_aiaugmentedanalytics_security_reverse_list_isolation_tenant_b_never_sees_tenant_a(
    client_b,
    augmented_insight_a,
    augmented_insight_b,
    smart_data_prep_suggestion_a,
    smart_data_prep_suggestion_b,
    text_sentiment_analysis_a,
    text_sentiment_analysis_b,
    analytics_recommendation_a,
    analytics_recommendation_b,
):
    """Verify Tenant B querying lists never sees Tenant A records."""
    # 1. AugmentedInsight list
    res = client_b.get(reverse("bi:augmented_insight_list"))
    assert res.status_code == 200
    insights = list(res.context["insights"])
    assert augmented_insight_b in insights
    assert augmented_insight_a not in insights
    content = res.content.decode()
    assert augmented_insight_a.number not in content

    # 2. AugmentedInsight feed
    res_feed = client_b.get(reverse("bi:augmented_insight_feed"))
    assert res_feed.status_code == 200
    feed_items = list(res_feed.context["feed_items"])
    assert augmented_insight_b in feed_items
    assert augmented_insight_a not in feed_items

    # 3. SmartDataPrepSuggestion list
    res_prep = client_b.get(reverse("bi:smart_data_prep_suggestion_list"))
    assert res_prep.status_code == 200
    suggestions = list(res_prep.context["suggestions"])
    assert smart_data_prep_suggestion_b in suggestions
    assert smart_data_prep_suggestion_a not in suggestions

    # 4. TextSentimentAnalysis list
    res_snt = client_b.get(reverse("bi:text_sentiment_analysis_list"))
    assert res_snt.status_code == 200
    analyses = list(res_snt.context["analyses"])
    assert text_sentiment_analysis_b in analyses
    assert text_sentiment_analysis_a not in analyses

    # 5. AnalyticsRecommendation list
    res_rec = client_b.get(reverse("bi:analytics_recommendation_list"))
    assert res_rec.status_code == 200
    recommendations = list(res_rec.context["recommendations"])
    assert analytics_recommendation_b in recommendations
    assert analytics_recommendation_a not in recommendations


# ===========================================================================
# 3. Authentication Gates (@login_required)
# ===========================================================================


def test_aiaugmentedanalytics_security_anon_redirects_to_login_list_and_create_endpoints(
    anon_client,
):
    """Verify anonymous access to list and create routes redirects to login."""
    endpoints = [
        reverse("bi:augmented_insight_list"),
        reverse("bi:augmented_insight_feed"),
        reverse("bi:augmented_insight_create"),
        reverse("bi:smart_data_prep_suggestion_list"),
        reverse("bi:smart_data_prep_suggestion_create"),
        reverse("bi:text_sentiment_analysis_list"),
        reverse("bi:text_sentiment_analysis_create"),
        reverse("bi:analytics_recommendation_list"),
        reverse("bi:analytics_recommendation_create"),
    ]
    for url in endpoints:
        res = anon_client.get(url)
        assert res.status_code == 302, f"Anon GET {url} returned {res.status_code}"
        assert "/login/" in res.url


def test_aiaugmentedanalytics_security_anon_redirects_to_login_detail_and_edit_endpoints(
    anon_client,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify anonymous access to detail and edit routes redirects to login."""
    endpoints = [
        reverse("bi:augmented_insight_detail", args=[augmented_insight_a.pk]),
        reverse("bi:augmented_insight_edit", args=[augmented_insight_a.pk]),
        reverse("bi:smart_data_prep_suggestion_detail", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:smart_data_prep_suggestion_edit", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:text_sentiment_analysis_detail", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:text_sentiment_analysis_edit", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:analytics_recommendation_detail", args=[analytics_recommendation_a.pk]),
        reverse("bi:analytics_recommendation_edit", args=[analytics_recommendation_a.pk]),
    ]
    for url in endpoints:
        res = anon_client.get(url)
        assert res.status_code == 302, f"Anon GET {url} returned {res.status_code}"
        assert "/login/" in res.url


def test_aiaugmentedanalytics_security_anon_redirects_to_login_delete_and_action_endpoints(
    anon_client,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify anonymous access to delete and action mutation POST endpoints redirects to login."""
    endpoints = [
        reverse("bi:augmented_insight_delete", args=[augmented_insight_a.pk]),
        reverse("bi:augmented_insight_triage", args=[augmented_insight_a.pk]),
        reverse("bi:smart_data_prep_suggestion_delete", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:smart_data_prep_suggestion_action", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:text_sentiment_analysis_delete", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:text_sentiment_analysis_recalculate", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:analytics_recommendation_delete", args=[analytics_recommendation_a.pk]),
        reverse("bi:analytics_recommendation_interact", args=[analytics_recommendation_a.pk]),
    ]
    for url in endpoints:
        res = anon_client.post(url, {})
        assert res.status_code == 302, f"Anon POST {url} returned {res.status_code}"
        assert "/login/" in res.url


# ===========================================================================
# 4. Authorization Gates (@tenant_admin_required)
# ===========================================================================


def test_aiaugmentedanalytics_security_delete_views_require_tenant_admin_forbidden_for_members(
    member_client,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify non-admin member user receives HTTP 403 Forbidden on all 4 deletion endpoints."""
    delete_routes = [
        reverse("bi:augmented_insight_delete", args=[augmented_insight_a.pk]),
        reverse("bi:smart_data_prep_suggestion_delete", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:text_sentiment_analysis_delete", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:analytics_recommendation_delete", args=[analytics_recommendation_a.pk]),
    ]

    for url in delete_routes:
        res = member_client.post(url)
        assert res.status_code == 403, f"Non-admin allowed to delete at {url}! Status: {res.status_code}"

    # Verify no objects were actually deleted
    assert AugmentedInsight.objects.filter(pk=augmented_insight_a.pk).exists()
    assert SmartDataPrepSuggestion.objects.filter(pk=smart_data_prep_suggestion_a.pk).exists()
    assert TextSentimentAnalysis.objects.filter(pk=text_sentiment_analysis_a.pk).exists()
    assert AnalyticsRecommendation.objects.filter(pk=analytics_recommendation_a.pk).exists()


def test_aiaugmentedanalytics_security_standard_member_can_access_read_views(
    member_client,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify standard non-admin member has read access to list and detail views."""
    read_routes = [
        reverse("bi:augmented_insight_list"),
        reverse("bi:augmented_insight_feed"),
        reverse("bi:augmented_insight_detail", args=[augmented_insight_a.pk]),
        reverse("bi:smart_data_prep_suggestion_list"),
        reverse("bi:smart_data_prep_suggestion_detail", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:text_sentiment_analysis_list"),
        reverse("bi:text_sentiment_analysis_detail", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:analytics_recommendation_list"),
        reverse("bi:analytics_recommendation_detail", args=[analytics_recommendation_a.pk]),
    ]
    for url in read_routes:
        res = member_client.get(url)
        assert res.status_code == 200, f"Standard member was blocked from read view {url}! Status: {res.status_code}"


def test_aiaugmentedanalytics_security_tenant_admin_can_delete_objects(
    client_a,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify tenant admin can successfully execute deletions."""
    # Delete augmented insight
    res_insight = client_a.post(reverse("bi:augmented_insight_delete", args=[augmented_insight_a.pk]))
    assert res_insight.status_code == 302
    assert not AugmentedInsight.objects.filter(pk=augmented_insight_a.pk).exists()

    # Delete smart data prep suggestion
    res_prep = client_a.post(reverse("bi:smart_data_prep_suggestion_delete", args=[smart_data_prep_suggestion_a.pk]))
    assert res_prep.status_code == 302
    assert not SmartDataPrepSuggestion.objects.filter(pk=smart_data_prep_suggestion_a.pk).exists()

    # Delete text sentiment analysis
    res_snt = client_a.post(reverse("bi:text_sentiment_analysis_delete", args=[text_sentiment_analysis_a.pk]))
    assert res_snt.status_code == 302
    assert not TextSentimentAnalysis.objects.filter(pk=text_sentiment_analysis_a.pk).exists()

    # Delete analytics recommendation
    res_rec = client_a.post(reverse("bi:analytics_recommendation_delete", args=[analytics_recommendation_a.pk]))
    assert res_rec.status_code == 302
    assert not AnalyticsRecommendation.objects.filter(pk=analytics_recommendation_a.pk).exists()


# ===========================================================================
# 5. Action Permissions & Ownership Control
# ===========================================================================


def test_aiaugmentedanalytics_security_recommendation_interact_cross_user_forbidden(
    member_client,
    analytics_recommendation_a,
):
    """Verify non-admin member cannot interact with another user's recommendation (returns 403)."""
    # analytics_recommendation_a belongs to admin_user, member_client is member_user (non-admin)
    url = reverse("bi:analytics_recommendation_interact", args=[analytics_recommendation_a.pk])
    res = member_client.post(url, {"interaction_type": "click"})
    assert res.status_code == 403

    analytics_recommendation_a.refresh_from_db()
    assert analytics_recommendation_a.status == "active"


def test_aiaugmentedanalytics_security_recommendation_interact_allowed_for_designated_user(
    tenant_a,
    member_user,
    member_client,
):
    """Verify designated recipient user can interact with their own recommendation."""
    rec = _aiaugmentedanalytics_security_create_recommendation(
        tenant=tenant_a,
        user=member_user,
        title="Personal Workflow Rec",
    )
    url = reverse("bi:analytics_recommendation_interact", args=[rec.pk])
    res = member_client.post(url, {"interaction_type": "click"})
    assert res.status_code == 302

    rec.refresh_from_db()
    assert rec.status == "clicked"
    assert rec.last_interacted_at is not None


def test_aiaugmentedanalytics_security_recommendation_interact_allowed_for_tenant_admin_on_behalf_of_user(
    client_a,
    tenant_a,
    member_user,
):
    """Verify tenant admin can interact with a recommendation assigned to another user."""
    rec = _aiaugmentedanalytics_security_create_recommendation(
        tenant=tenant_a,
        user=member_user,
        title="Managed User Rec",
    )
    url = reverse("bi:analytics_recommendation_interact", args=[rec.pk])
    res = client_a.post(url, {"interaction_type": "dismiss"})
    assert res.status_code == 302

    rec.refresh_from_db()
    assert rec.status == "dismissed"


def test_aiaugmentedanalytics_security_smart_data_prep_suggestion_action_applied_state_guard(
    client_a,
    smart_data_prep_suggestion_a,
):
    """Verify smart_data_prep_suggestion_action cannot transition an already applied suggestion."""
    smart_data_prep_suggestion_a.status = "applied"
    smart_data_prep_suggestion_a.save()

    url = reverse("bi:smart_data_prep_suggestion_action", args=[smart_data_prep_suggestion_a.pk])
    res = client_a.post(url, {"action_type": "reject", "review_notes": "Trying to override applied"})
    assert res.status_code == 302
    assert res.url == reverse("bi:smart_data_prep_suggestion_detail", args=[smart_data_prep_suggestion_a.pk])

    smart_data_prep_suggestion_a.refresh_from_db()
    assert smart_data_prep_suggestion_a.status == "applied"
    assert smart_data_prep_suggestion_a.review_notes != "Trying to override applied"

    # Check warning message
    messages = list(get_messages(res.wsgi_request))
    assert any("already been applied" in m.message for m in messages)


# ===========================================================================
# 6. Open Redirect Protection
# ===========================================================================


def test_aiaugmentedanalytics_security_open_redirect_defense_external_url(
    client_a,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify mutating POST endpoints reject external/malicious next parameter and fall back safely."""
    malicious_targets = [
        "https://malicious.evil.com/phish",
        "//attacker.com/exploit",
        "javascript:alert(document.cookie)",
        "/\\malicious.com",
    ]

    for evil_url in malicious_targets:
        # 1. Insight triage
        url_triage = reverse("bi:augmented_insight_triage", args=[augmented_insight_a.pk])
        res1 = client_a.post(url_triage, {"status": "bookmarked", "next": evil_url})
        assert res1.status_code == 302
        assert not res1.url.startswith("http://malicious")
        assert not res1.url.startswith("https://malicious")
        assert not res1.url.startswith("//")
        assert res1.url == reverse("bi:augmented_insight_detail", args=[augmented_insight_a.pk])

        # 2. Prep suggestion action
        url_action = reverse("bi:smart_data_prep_suggestion_action", args=[smart_data_prep_suggestion_a.pk])
        res2 = client_a.post(url_action, {"action_type": "accept", "next": evil_url})
        assert res2.status_code == 302
        assert not res2.url.startswith("//")
        assert not res2.url.startswith("https://")
        assert res2.url == reverse("bi:smart_data_prep_suggestion_detail", args=[smart_data_prep_suggestion_a.pk])

        # 3. Sentiment recalculate
        url_recalc = reverse("bi:text_sentiment_analysis_recalculate", args=[text_sentiment_analysis_a.pk])
        res3 = client_a.post(url_recalc, {"next": evil_url})
        assert res3.status_code == 302
        assert not res3.url.startswith("//")
        assert not res3.url.startswith("https://")
        assert res3.url == reverse("bi:text_sentiment_analysis_detail", args=[text_sentiment_analysis_a.pk])

        # 4. Recommendation interact
        url_interact = reverse("bi:analytics_recommendation_interact", args=[analytics_recommendation_a.pk])
        res4 = client_a.post(url_interact, {"interaction_type": "save", "next": evil_url})
        assert res4.status_code == 302
        assert not res4.url.startswith("//")
        assert not res4.url.startswith("https://")
        assert res4.url == reverse("bi:analytics_recommendation_detail", args=[analytics_recommendation_a.pk])


def test_aiaugmentedanalytics_security_open_redirect_safe_relative_url_allowed(
    client_a,
    augmented_insight_a,
):
    """Verify safe relative internal redirect is honored."""
    url = reverse("bi:augmented_insight_triage", args=[augmented_insight_a.pk])
    safe_next = "/bi/augmented-insights/feed/"
    res = client_a.post(url, {"status": "in_review", "next": safe_next})
    assert res.status_code == 302
    assert res.url == safe_next


# ===========================================================================
# 7. XSS & Injection Protection
# ===========================================================================


def test_aiaugmentedanalytics_security_recommendation_form_target_url_xss_javascript_rejected(
    tenant_a,
    admin_user,
):
    """Verify AnalyticsRecommendationForm rejects javascript: URI schemes in target_url."""
    data = {
        "user": admin_user.pk,
        "recommendation_type": "dashboard",
        "target_title": "Malicious Script Link",
        "target_url": "javascript:alert(document.cookie)",
        "reason": "role_relevance",
        "rationale_text": "XSS attempt via target_url.",
        "affinity_score": "75.00",
        "status": "active",
    }
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors
    assert "Target URL must be a valid relative path" in form.errors["target_url"][0]


def test_aiaugmentedanalytics_security_recommendation_form_target_url_protocol_relative_rejected(
    tenant_a,
    admin_user,
):
    """Verify AnalyticsRecommendationForm rejects protocol-relative (//) URLs in target_url."""
    data = {
        "user": admin_user.pk,
        "recommendation_type": "dashboard",
        "target_title": "Protocol-Relative Phishing Link",
        "target_url": "//evil.com/phish",
        "reason": "role_relevance",
        "rationale_text": "Protocol relative open redirect exploit.",
        "affinity_score": "75.00",
        "status": "active",
    }
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors


def test_aiaugmentedanalytics_security_recommendation_form_target_url_absolute_external_rejected(
    tenant_a,
    admin_user,
):
    """Verify AnalyticsRecommendationForm rejects absolute HTTP/HTTPS URLs."""
    data = {
        "user": admin_user.pk,
        "recommendation_type": "dashboard",
        "target_title": "External Site Link",
        "target_url": "https://external-phish.com/dashboard",
        "reason": "role_relevance",
        "rationale_text": "External absolute URL rejection check.",
        "affinity_score": "75.00",
        "status": "active",
    }
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors


def test_aiaugmentedanalytics_security_recommendation_form_target_url_safe_relative_accepted(
    tenant_a,
    admin_user,
):
    """Verify AnalyticsRecommendationForm accepts valid relative URLs."""
    data = {
        "user": admin_user.pk,
        "recommendation_type": "dashboard",
        "target_title": "Valid Dashboard Link",
        "target_url": "/bi/dashboards/15/",
        "reason": "role_relevance",
        "rationale_text": "Legitimate internal dashboard navigation link.",
        "affinity_score": "92.00",
        "status": "active",
    }
    form = AnalyticsRecommendationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["target_url"] == "/bi/dashboards/15/"


def test_aiaugmentedanalytics_security_cross_tenant_fk_injection_rejected(
    tenant_a,
    admin_user,
    admin_user_b,
    semantic_model_b,
    kpi_definition_b,
    warehouse_table_b,
    bi_dashboard_b,
):
    """Verify reject_foreign rejects assigning cross-tenant FK objects across all forms."""
    # 1. AugmentedInsightForm with foreign semantic_model_b
    form_insight = AugmentedInsightForm(
        data={
            "title": "Cross-Tenant Insight Test",
            "insight_type": "trend_shift",
            "severity": "high",
            "status": "new",
            "metric_name": "metric_x",
            "dimension_name": "dim_x",
            "dimension_value": "val_x",
            "baseline_value": "100.0000",
            "observed_value": "120.0000",
            "confidence_score": "90.00",
            "impact_direction": "favorable",
            "narrative_summary": "Cross tenant FK test summary narrative.",
            "semantic_model": semantic_model_b.pk,
            "kpi_definition": kpi_definition_b.pk,
            "warehouse_table": warehouse_table_b.pk,
        },
        tenant=tenant_a,
    )
    assert not form_insight.is_valid()
    assert (
        "semantic_model" in form_insight.errors
        or "kpi_definition" in form_insight.errors
        or "warehouse_table" in form_insight.errors
    )

    # 2. SmartDataPrepSuggestionForm with foreign warehouse_table_b
    form_prep = SmartDataPrepSuggestionForm(
        data={
            "target_table": warehouse_table_b.pk,
            "target_column": "foreign_col",
            "suggestion_type": "type_cast",
            "confidence_score": "95.00",
            "status": "pending",
            "rationale": "Cross tenant table injection attempt rationale.",
        },
        tenant=tenant_a,
    )
    assert not form_prep.is_valid()
    assert "target_table" in form_prep.errors

    # 3. AnalyticsRecommendationForm with foreign user and foreign dashboard
    form_rec = AnalyticsRecommendationForm(
        data={
            "user": admin_user_b.pk,
            "recommendation_type": "dashboard",
            "target_title": "Foreign User Rec",
            "target_url": "/bi/dashboards/1/",
            "reason": "role_relevance",
            "rationale_text": "Assigning rec to foreign tenant user.",
            "affinity_score": "80.00",
            "status": "active",
            "dashboard": bi_dashboard_b.pk,
            "semantic_model": semantic_model_b.pk,
        },
        tenant=tenant_a,
    )
    assert not form_rec.is_valid()
    assert (
        "user" in form_rec.errors
        or "dashboard" in form_rec.errors
        or "semantic_model" in form_rec.errors
    )


# ===========================================================================
# 8. HTTP Method Constraints (@require_POST)
# ===========================================================================


def test_aiaugmentedanalytics_security_delete_and_actions_reject_get_with_405(
    client_a,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify delete and mutation action routes reject GET requests with HTTP 405 Method Not Allowed."""
    mutation_routes = [
        reverse("bi:augmented_insight_delete", args=[augmented_insight_a.pk]),
        reverse("bi:augmented_insight_triage", args=[augmented_insight_a.pk]),
        reverse("bi:smart_data_prep_suggestion_delete", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:smart_data_prep_suggestion_action", args=[smart_data_prep_suggestion_a.pk]),
        reverse("bi:text_sentiment_analysis_delete", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:text_sentiment_analysis_recalculate", args=[text_sentiment_analysis_a.pk]),
        reverse("bi:analytics_recommendation_delete", args=[analytics_recommendation_a.pk]),
        reverse("bi:analytics_recommendation_interact", args=[analytics_recommendation_a.pk]),
    ]

    for url in mutation_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"Route {url} failed to reject GET with HTTP 405! Got: {res.status_code}"


# ===========================================================================
# 9. Audit Logging Security Verification
# ===========================================================================


def test_aiaugmentedanalytics_security_audit_logs_recorded_for_all_mutations(
    client_a,
    tenant_a,
    admin_user,
    augmented_insight_a,
    smart_data_prep_suggestion_a,
    text_sentiment_analysis_a,
    analytics_recommendation_a,
):
    """Verify security-critical operations create append-only audit log records scoped to tenant."""
    # 1. Insight triage
    client_a.post(
        reverse("bi:augmented_insight_triage", args=[augmented_insight_a.pk]),
        {"status": "bookmarked", "action_notes": "Security triage check"},
    )
    log_triage = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="triage",
    ).first()
    assert log_triage is not None
    assert log_triage.changes.get("status") == "bookmarked"

    # 2. Prep suggestion action
    client_a.post(
        reverse("bi:smart_data_prep_suggestion_action", args=[smart_data_prep_suggestion_a.pk]),
        {"action_type": "accept", "review_notes": "Accepted under security audit"},
    )
    log_prep = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="accept",
    ).first()
    assert log_prep is not None
    assert log_prep.changes.get("status") == "accepted"

    # 3. Sentiment recalculate
    client_a.post(
        reverse("bi:text_sentiment_analysis_recalculate", args=[text_sentiment_analysis_a.pk])
    )
    log_recalc = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="recalc",
    ).first()
    assert log_recalc is not None

    # 4. Recommendation interact
    client_a.post(
        reverse("bi:analytics_recommendation_interact", args=[analytics_recommendation_a.pk]),
        {"interaction_type": "click"},
    )
    log_interact = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="click",
    ).first()
    assert log_interact is not None
    assert log_interact.changes.get("status") == "clicked"

    # 5. Delete augmented insight
    client_a.post(
        reverse("bi:augmented_insight_delete", args=[augmented_insight_a.pk])
    )
    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=augmented_insight_a.number,
    ).first()
    assert log_delete is not None
