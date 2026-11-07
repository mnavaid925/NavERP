"""View and flow unit tests for Sub-module 10.15 Natural Language & Conversational BI (apps/bi).

Views covered:
1. NaturalLanguageQueries:
   - natural_language_query_list (GET, context, search, filters)
   - natural_language_query_detail (GET, context, parsed measures/dimensions/filters, rating choices)
   - natural_language_query_create (GET, POST valid -> 302 with auto-SQL/chart generation, POST invalid -> 200)
   - natural_language_query_edit (GET, POST valid -> 302)
   - natural_language_query_delete (POST admin -> 302, GET -> 405, non-admin -> 403)
   - natural_language_query_rate (POST valid -> 302, open redirect defense, invalid rating, GET -> 405)

2. BiConversationSessions:
   - bi_conversation_session_list (GET, context, search, filters)
   - bi_conversation_session_detail (GET, context, turns, suggested prompts)
   - bi_conversation_session_create (GET, POST valid -> 302, POST invalid -> 200)
   - bi_conversation_session_edit (GET, POST valid -> 302)
   - bi_conversation_session_delete (POST admin -> 302, GET -> 405, non-admin -> 403)
   - bi_conversation_session_toggle_pin (POST action -> 302, next redirect, GET -> 405)
   - bi_conversation_session_close (POST action -> 302, GET -> 405)
   - bi_conversation_session_ask (POST turn -> 302, message count increment, next redirect, empty query guard, GET -> 405)
   - bi_chat_workspace (GET hub, session selection via query param, invalid session 404)

3. NarrativeExplanations:
   - narrative_explanation_list (GET, context, search, filters including legacy artifact param)
   - narrative_explanation_detail (GET, context, key takeaways)
   - narrative_explanation_create (GET, POST valid -> 302 with auto-takeaways and audio script, POST invalid -> 200)
   - narrative_explanation_edit (GET, POST valid -> 302)
   - narrative_explanation_delete (POST admin -> 302, GET -> 405, non-admin -> 403)
   - narrative_explanation_publish (POST action -> 302, status=published, next redirect, GET -> 405)
   - narrative_explanation_regenerate (POST action -> 302, recomputed body/takeaways/audio script, GET -> 405)

4. SearchDiscoveryIndexes:
   - search_discovery_index_list (GET, context, search, filters)
   - search_discovery_index_detail (GET, context, synonyms list)
   - search_discovery_index_create (GET, POST valid -> 302, POST invalid -> 200)
   - search_discovery_index_edit (GET, POST valid -> 302)
   - search_discovery_index_delete (POST admin -> 302, GET -> 405, non-admin -> 403)
   - search_discovery_index_reweight (POST decimal -> 302, non-finite NaN/Infinity fallback, GET -> 405)
   - search_discovery_hub (GET hub, search match, category filter list, telemetry hit count increment)
"""
from decimal import Decimal
import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.bi.models.ConversationalBi.BiConversationSessions import BiConversationSession
from apps.bi.models.ConversationalBi.NarrativeExplanations import NarrativeExplanation
from apps.bi.models.ConversationalBi.NaturalLanguageQueries import NaturalLanguageQuery
from apps.bi.models.ConversationalBi.SearchDiscoveryIndexes import SearchDiscoveryIndex
from apps.core.models import AuditLog

User = get_user_model()


# ==============================================================================
# Module Helpers (strictly prefixed with _conversationalbi_*)
# ==============================================================================


def _conversationalbi_create_session(tenant, user, **kwargs):
    """Helper to create a tenant-scoped BiConversationSession."""
    defaults = {
        "title": "Helper Conversation Thread",
        "session_status": "active",
        "is_pinned": False,
        "suggested_prompts": ["What is Q3 Revenue?", "Show regional variance"],
    }
    defaults.update(kwargs)
    return BiConversationSession.objects.create(tenant=tenant, user=user, **defaults)


def _conversationalbi_create_nlq(tenant, user=None, session=None, **kwargs):
    """Helper to create a tenant-scoped NaturalLanguageQuery."""
    defaults = {
        "query_text": "What was total revenue by region in Q3?",
        "input_modality": "text",
        "intent_type": "metric_lookup",
        "chart_type": "bar_chart",
        "user": user,
        "conversation_session": session,
        "execution_status": "completed",
        "user_rating": "helpful",
        "parsed_measures": ["Revenue"],
        "parsed_dimensions": ["Region"],
        "parsed_filters": {"quarter": "Q3"},
    }
    defaults.update(kwargs)
    return NaturalLanguageQuery.objects.create(tenant=tenant, **defaults)


def _conversationalbi_create_narrative(tenant, created_by=None, **kwargs):
    """Helper to create a tenant-scoped NarrativeExplanation."""
    defaults = {
        "title": "Helper Executive Briefing",
        "headline": "Revenue grew 14% quarter-over-quarter led by enterprise renewals.",
        "target_artifact_type": "dashboard",
        "narrative_style": "executive_briefing",
        "narrative_body": "Total revenue reached 12.8M against plan.",
        "key_takeaways": ["QoQ revenue grew 14%", "Enterprise renewals +8%"],
        "top_positive_driver": "Enterprise SaaS renewals",
        "top_negative_driver": "Supply chain freight surcharges",
        "audio_ready_script": "Executive briefing audio script for revenue analysis.",
        "status": "published",
        "created_by": created_by,
    }
    defaults.update(kwargs)
    return NarrativeExplanation.objects.create(tenant=tenant, **defaults)


def _conversationalbi_create_search_index(tenant, **kwargs):
    """Helper to create a tenant-scoped SearchDiscoveryIndex."""
    defaults = {
        "asset_name": "Executive Profitability Overview Dashboard",
        "asset_type": "dashboard",
        "target_url": "/bi/dashboards/1/",
        "category": "Finance",
        "search_keywords": "revenue margin profit sales cfo",
        "synonyms": ["income", "margin", "topline"],
        "relevance_weight": Decimal("1.25"),
        "search_hit_count": 10,
        "is_featured": True,
        "is_verified": True,
    }
    defaults.update(kwargs)
    return SearchDiscoveryIndex.objects.create(tenant=tenant, **defaults)


def _conversationalbi_valid_nlq_post_data(**kwargs):
    """Return a valid dictionary payload for NaturalLanguageQuery creation."""
    data = {
        "query_text": "Show gross profit margin by customer segment for 2026",
        "input_modality": "text",
        "intent_type": "metric_lookup",
        "chart_type": "bar_chart",
        "user_rating": "helpful",
        "user_feedback_notes": "Well structured query response",
    }
    data.update(kwargs)
    return data


def _conversationalbi_valid_session_post_data(**kwargs):
    """Return a valid dictionary payload for BiConversationSession creation."""
    data = {
        "title": "Quarterly Sales Pipeline & Forecast Thread",
        "session_status": "active",
        "is_pinned": True,
    }
    data.update(kwargs)
    return data


def _conversationalbi_valid_narrative_post_data(**kwargs):
    """Return a valid dictionary payload for NarrativeExplanation creation."""
    data = {
        "title": "Fiscal 2026 Strategy Briefing",
        "headline": "EBITDA margin reached 28.4% outperforming consensus targets",
        "target_artifact_type": "dashboard",
        "narrative_style": "executive_briefing",
        "narrative_body": "Detailed executive analysis for fiscal 2026 operations.",
        "top_positive_driver": "Product volume expansion",
        "top_negative_driver": "Raw material inflation",
        "language": "en",
        "status": "generated",
    }
    data.update(kwargs)
    return data


def _conversationalbi_valid_search_index_post_data(**kwargs):
    """Return a valid dictionary payload for SearchDiscoveryIndex creation."""
    data = {
        "asset_name": "Customer Lifetime Value Analytics Cube",
        "asset_type": "semantic_model",
        "target_url": "/bi/semantic-layer/models/1/",
        "description": "Multi-dimensional customer CLV and cohort retention model.",
        "category": "Marketing and Sales",
        "search_keywords": "clv cohort retention customer churn",
        "synonyms": json.dumps(["ltv", "customer value", "cohort"]),
        "relevance_weight": "1.50",
        "is_featured": True,
        "is_verified": True,
    }
    data.update(kwargs)
    return data


# ==============================================================================
# 1. List Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_views_nlq_list_context_and_render(client_a, natural_language_query_a):
    """Test natural language query list view returns 200, context contract, and rendered content."""
    url = reverse("bi:natural_language_query_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert "queries" in resp.context
    assert "natural_language_queries" in resp.context
    assert natural_language_query_a in resp.context["queries"]
    assert "total_count" in resp.context
    assert "completed_count" in resp.context
    assert "voice_count" in resp.context
    assert "helpful_count" in resp.context
    assert "status_choices" in resp.context
    assert "modality_choices" in resp.context
    assert "intent_choices" in resp.context
    assert "semantic_models" in resp.context

    content = resp.content.decode()
    assert natural_language_query_a.number in content
    assert natural_language_query_a.query_text in content


@pytest.mark.django_db
def test_conversationalbi_views_nlq_list_search_and_filters(
    client_a, tenant_a, admin_user, natural_language_query_a
):
    """Test natural language query list filters by status, modality, intent, q, rating, and semantic model."""
    url = reverse("bi:natural_language_query_list")

    # Second query with different parameters for filter discrimination
    query_voice = _conversationalbi_create_nlq(
        tenant=tenant_a,
        user=admin_user,
        query_text="Voice prompt regarding warehouse inventory replenishment",
        input_modality="voice",
        intent_type="anomaly_investigation",
        execution_status="in_progress",
        user_rating="unrated",
    )

    # Filter ?status=completed&modality=text&intent=metric_lookup&q=revenue
    resp = client_a.get(f"{url}?status=completed&modality=text&intent=metric_lookup&q=revenue")
    assert resp.status_code == 200
    queries = list(resp.context["queries"])
    assert natural_language_query_a in queries
    assert query_voice not in queries

    # Filter ?modality=voice
    resp_voice = client_a.get(f"{url}?modality=voice")
    assert resp_voice.status_code == 200
    assert query_voice in resp_voice.context["queries"]
    assert natural_language_query_a not in resp_voice.context["queries"]

    # Filter ?rating=helpful
    resp_rating = client_a.get(f"{url}?rating=helpful")
    assert resp_rating.status_code == 200
    assert natural_language_query_a in resp_rating.context["queries"]
    assert query_voice not in resp_rating.context["queries"]

    # Filter ?semantic_model=<id>
    if natural_language_query_a.semantic_model_id:
        resp_sm = client_a.get(f"{url}?semantic_model={natural_language_query_a.semantic_model_id}")
        assert resp_sm.status_code == 200
        assert natural_language_query_a in resp_sm.context["queries"]


@pytest.mark.django_db
def test_conversationalbi_views_session_list_context_and_render(client_a, conversation_session_a):
    """Test conversation session list view returns 200, context contract, and rendered content."""
    url = reverse("bi:bi_conversation_session_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert "sessions" in resp.context
    assert "conversation_sessions" in resp.context
    assert conversation_session_a in resp.context["sessions"]
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "pinned_count" in resp.context
    assert "status_choices" in resp.context
    assert "semantic_models" in resp.context
    assert "dashboards" in resp.context

    content = resp.content.decode()
    assert conversation_session_a.number in content
    assert conversation_session_a.title in content


@pytest.mark.django_db
def test_conversationalbi_views_session_list_search_and_filters(
    client_a, tenant_a, admin_user, conversation_session_a
):
    """Test conversation session list filters by status, pinned, q, and primary semantic model."""
    url = reverse("bi:bi_conversation_session_list")

    # Second unpinned and closed session
    closed_session = _conversationalbi_create_session(
        tenant=tenant_a,
        user=admin_user,
        title="Archived Logistics Incident Review",
        session_status="closed",
        is_pinned=False,
    )

    # Filter ?status=active&pinned=1&q=revenue
    resp = client_a.get(f"{url}?status=active&pinned=1&q=revenue")
    assert resp.status_code == 200
    sessions = list(resp.context["sessions"])
    assert conversation_session_a in sessions
    assert closed_session not in sessions

    # Filter ?status=closed
    resp_closed = client_a.get(f"{url}?status=closed")
    assert resp_closed.status_code == 200
    assert closed_session in resp_closed.context["sessions"]
    assert conversation_session_a not in resp_closed.context["sessions"]


@pytest.mark.django_db
def test_conversationalbi_views_narrative_list_context_and_render(client_a, narrative_explanation_a):
    """Test narrative explanation list view returns 200, context contract, and rendered content."""
    url = reverse("bi:narrative_explanation_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert "narratives" in resp.context
    assert "narrative_explanations" in resp.context
    assert narrative_explanation_a in resp.context["narratives"]
    assert "total_count" in resp.context
    assert "published_count" in resp.context
    assert "executive_count" in resp.context
    assert "audio_script_count" in resp.context
    assert "style_choices" in resp.context
    assert "status_choices" in resp.context
    assert "artifact_choices" in resp.context

    content = resp.content.decode()
    assert narrative_explanation_a.number in content
    assert narrative_explanation_a.title in content


@pytest.mark.django_db
def test_conversationalbi_views_narrative_list_search_and_filters(
    client_a, tenant_a, admin_user, narrative_explanation_a
):
    """Test narrative explanation list filters by status, style, artifact_type (and legacy artifact), and search query."""
    url = reverse("bi:narrative_explanation_list")

    # Second draft operational summary narrative
    draft_narrative = _conversationalbi_create_narrative(
        tenant=tenant_a,
        created_by=admin_user,
        title="Warehouse Inventory Operations Summary",
        target_artifact_type="report",
        narrative_style="operational_summary",
        status="draft",
        narrative_body="Monthly warehouse throughput variance assessment.",
    )

    # Filter ?status=published&style=executive_briefing&artifact_type=dashboard
    resp = client_a.get(f"{url}?status=published&style=executive_briefing&artifact_type=dashboard")
    assert resp.status_code == 200
    narratives = list(resp.context["narratives"])
    assert narrative_explanation_a in narratives
    assert draft_narrative not in narratives

    # Test legacy ?artifact=dashboard parameter compatibility
    resp_legacy = client_a.get(f"{url}?artifact=dashboard")
    assert resp_legacy.status_code == 200
    assert narrative_explanation_a in resp_legacy.context["narratives"]
    assert draft_narrative not in resp_legacy.context["narratives"]

    # Filter ?q=Inventory
    resp_q = client_a.get(f"{url}?q=Inventory")
    assert resp_q.status_code == 200
    assert draft_narrative in resp_q.context["narratives"]
    assert narrative_explanation_a not in resp_q.context["narratives"]


@pytest.mark.django_db
def test_conversationalbi_views_search_index_list_context_and_render(client_a, search_discovery_index_a):
    """Test search discovery index list view returns 200, context contract, and rendered content."""
    url = reverse("bi:search_discovery_index_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert "indexes" in resp.context
    assert "search_discovery_indexes" in resp.context
    assert search_discovery_index_a in resp.context["indexes"]
    assert "total_count" in resp.context
    assert "verified_count" in resp.context
    assert "featured_count" in resp.context
    assert "type_choices" in resp.context

    content = resp.content.decode()
    assert search_discovery_index_a.number in content
    assert search_discovery_index_a.asset_name in content


@pytest.mark.django_db
def test_conversationalbi_views_search_index_list_search_and_filters(
    client_a, tenant_a, search_discovery_index_a
):
    """Test search discovery index list filters by type, verified, featured, and search q."""
    url = reverse("bi:search_discovery_index_list")

    # Second unverified and unfeatured index
    unverified_index = _conversationalbi_create_search_index(
        tenant=tenant_a,
        asset_name="Raw Procurement Log Table",
        asset_type="warehouse_table",
        category="Operations",
        is_verified=False,
        is_featured=False,
    )

    # Filter ?type=dashboard&verified=1&featured=1&category=Finance&q=revenue
    resp = client_a.get(f"{url}?type=dashboard&verified=1&featured=1&category=Finance&q=revenue")
    assert resp.status_code == 200
    indexes = list(resp.context["indexes"])
    assert search_discovery_index_a in indexes
    assert unverified_index not in indexes

    # Filter ?verified=0
    resp_unverified = client_a.get(f"{url}?verified=0")
    assert resp_unverified.status_code == 200
    assert unverified_index in resp_unverified.context["indexes"]
    assert search_discovery_index_a not in resp_unverified.context["indexes"]


# ==============================================================================
# 2. Detail Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_views_nlq_detail_context_and_render(client_a, natural_language_query_a):
    """Test natural language query detail view returns 200 and pinned context variables."""
    url = reverse("bi:natural_language_query_detail", kwargs={"pk": natural_language_query_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert resp.context["query"] == natural_language_query_a
    assert "parsed_measures" in resp.context
    assert "parsed_dimensions" in resp.context
    assert "parsed_filters" in resp.context
    assert "rating_choices" in resp.context

    assert isinstance(resp.context["parsed_measures"], list)
    assert isinstance(resp.context["parsed_dimensions"], list)
    assert isinstance(resp.context["parsed_filters"], dict)

    content = resp.content.decode()
    assert natural_language_query_a.number in content
    assert natural_language_query_a.query_text in content


@pytest.mark.django_db
def test_conversationalbi_views_session_detail_context_and_render(
    client_a, conversation_session_a, natural_language_query_a
):
    """Test conversation session detail view returns 200, turns, and suggested prompts."""
    url = reverse("bi:bi_conversation_session_detail", kwargs={"pk": conversation_session_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert resp.context["session"] == conversation_session_a
    assert "turns" in resp.context
    assert natural_language_query_a in list(resp.context["turns"])
    assert "suggested_prompts" in resp.context
    assert isinstance(resp.context["suggested_prompts"], list)

    content = resp.content.decode()
    assert conversation_session_a.title in content
    assert conversation_session_a.number in content


@pytest.mark.django_db
def test_conversationalbi_views_narrative_detail_context_and_render(client_a, narrative_explanation_a):
    """Test narrative explanation detail view returns 200 and key takeaways in context."""
    url = reverse("bi:narrative_explanation_detail", kwargs={"pk": narrative_explanation_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert resp.context["narrative"] == narrative_explanation_a
    assert "key_takeaways" in resp.context
    assert isinstance(resp.context["key_takeaways"], list)

    content = resp.content.decode()
    assert narrative_explanation_a.title in content
    assert narrative_explanation_a.headline in content


@pytest.mark.django_db
def test_conversationalbi_views_search_index_detail_context_and_render(client_a, search_discovery_index_a):
    """Test search discovery index detail view returns 200 and synonyms in context."""
    url = reverse("bi:search_discovery_index_detail", kwargs={"pk": search_discovery_index_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert resp.context["index"] == search_discovery_index_a
    assert "synonyms_list" in resp.context
    assert isinstance(resp.context["synonyms_list"], list)

    content = resp.content.decode()
    assert search_discovery_index_a.asset_name in content
    assert search_discovery_index_a.number in content


# ==============================================================================
# 3. Create & Edit Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_views_nlq_create_get_form(client_a, conversation_session_a):
    """Test GET NLQ create page renders form and pre-populates session param when present."""
    url = reverse("bi:natural_language_query_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False

    # Test with ?session=<id> pre-population
    resp_session = client_a.get(f"{url}?session={conversation_session_a.pk}")
    assert resp_session.status_code == 200
    assert resp_session.context["form"].initial.get("conversation_session") == conversation_session_a.pk


@pytest.mark.django_db
def test_conversationalbi_views_nlq_create_post_success_and_defaults(client_a, tenant_a, admin_user):
    """Test POST valid NLQ creates instance with tenant, auto-number, simulated SQL/charts, and audit log."""
    url = reverse("bi:natural_language_query_create")
    payload = _conversationalbi_valid_nlq_post_data()

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created_nlq = NaturalLanguageQuery.objects.filter(
        tenant=tenant_a, query_text=payload["query_text"]
    ).first()
    assert created_nlq is not None
    assert created_nlq.number.startswith("BNLQ-")
    assert created_nlq.user == admin_user
    assert resp.url == reverse("bi:natural_language_query_detail", kwargs={"pk": created_nlq.pk})

    # Auto-generation simulation fields
    assert created_nlq.parsed_measures == ["Revenue", "Margin"]
    assert created_nlq.parsed_dimensions == ["Fiscal Quarter", "Region"]
    assert "SELECT" in created_nlq.generated_sql
    assert "chart_config" in dir(created_nlq) and created_nlq.chart_config.get("type") == "bar"

    # Audit log check
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_nlq_create_post_invalid(client_a):
    """Test POST invalid NLQ payload returns 200 with form errors."""
    url = reverse("bi:natural_language_query_create")
    resp = client_a.post(url, data={"query_text": ""})  # query_text is required
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_conversationalbi_views_nlq_edit_get_and_post_success(
    client_a, tenant_a, natural_language_query_a
):
    """Test GET and POST edit for NLQ updates instance and logs audit."""
    url = reverse("bi:natural_language_query_edit", kwargs={"pk": natural_language_query_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["query"] == natural_language_query_a

    # POST valid update
    payload = _conversationalbi_valid_nlq_post_data(
        query_text="Updated query text for revenue trends 2026",
        user_feedback_notes="Updated notes by analyst",
    )
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:natural_language_query_detail", kwargs={"pk": natural_language_query_a.pk}
    )

    natural_language_query_a.refresh_from_db()
    assert natural_language_query_a.query_text == "Updated query text for revenue trends 2026"
    assert natural_language_query_a.user_feedback_notes == "Updated notes by analyst"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_session_create_get_and_post_success(client_a, tenant_a, admin_user):
    """Test GET and POST create for conversation session creates record with tenant, defaults, and audit."""
    url = reverse("bi:bi_conversation_session_create")

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    payload = _conversationalbi_valid_session_post_data()
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302

    created_session = BiConversationSession.objects.filter(
        tenant=tenant_a, title=payload["title"]
    ).first()
    assert created_session is not None
    assert created_session.number.startswith("BCON-")
    assert created_session.user == admin_user
    assert len(created_session.suggested_prompts) > 0
    assert resp_post.url == reverse("bi:bi_conversation_session_detail", kwargs={"pk": created_session.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_session_create_post_invalid(client_a):
    """Test POST invalid session payload returns 200 with form errors."""
    url = reverse("bi:bi_conversation_session_create")
    resp = client_a.post(url, data={"title": ""})  # title is required
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_conversationalbi_views_session_edit_get_and_post_success(
    client_a, tenant_a, conversation_session_a
):
    """Test GET and POST edit for conversation session updates title and logs audit."""
    url = reverse("bi:bi_conversation_session_edit", kwargs={"pk": conversation_session_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["session"] == conversation_session_a

    payload = _conversationalbi_valid_session_post_data(title="Updated Executive Thread Title Q3-Q4")
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:bi_conversation_session_detail", kwargs={"pk": conversation_session_a.pk}
    )

    conversation_session_a.refresh_from_db()
    assert conversation_session_a.title == "Updated Executive Thread Title Q3-Q4"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_narrative_create_get_and_post_success(client_a, tenant_a, admin_user):
    """Test GET and POST create for narrative explanation creates object with auto-takeaways and audio script."""
    url = reverse("bi:narrative_explanation_create")

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    payload = _conversationalbi_valid_narrative_post_data()
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302

    created_narrative = NarrativeExplanation.objects.filter(
        tenant=tenant_a, title=payload["title"]
    ).first()
    assert created_narrative is not None
    assert created_narrative.number.startswith("BNLG-")
    assert created_narrative.created_by == admin_user
    assert isinstance(created_narrative.key_takeaways, list) and len(created_narrative.key_takeaways) > 0
    assert created_narrative.audio_ready_script != ""
    assert resp_post.url == reverse(
        "bi:narrative_explanation_detail", kwargs={"pk": created_narrative.pk}
    )

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_narrative_create_post_invalid(client_a):
    """Test POST invalid narrative payload returns 200 with form errors."""
    url = reverse("bi:narrative_explanation_create")
    resp = client_a.post(url, data={"title": ""})  # title and headline are required
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_conversationalbi_views_narrative_edit_get_and_post_success(
    client_a, tenant_a, narrative_explanation_a
):
    """Test GET and POST edit for narrative explanation updates instance and logs audit."""
    url = reverse("bi:narrative_explanation_edit", kwargs={"pk": narrative_explanation_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["narrative"] == narrative_explanation_a

    payload = _conversationalbi_valid_narrative_post_data(
        title="Updated Narrative Title 2026",
        headline="Updated Headline: Gross margins reached 32.1%",
    )
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:narrative_explanation_detail", kwargs={"pk": narrative_explanation_a.pk}
    )

    narrative_explanation_a.refresh_from_db()
    assert narrative_explanation_a.title == "Updated Narrative Title 2026"
    assert narrative_explanation_a.headline == "Updated Headline: Gross margins reached 32.1%"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_search_index_create_get_and_post_success(client_a, tenant_a):
    """Test GET and POST create for search discovery index creates record with tenant and audit log."""
    url = reverse("bi:search_discovery_index_create")

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    payload = _conversationalbi_valid_search_index_post_data()
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302

    created_index = SearchDiscoveryIndex.objects.filter(
        tenant=tenant_a, asset_name=payload["asset_name"]
    ).first()
    assert created_index is not None
    assert created_index.number.startswith("BSDI-")
    assert created_index.tenant == tenant_a
    assert resp_post.url == reverse(
        "bi:search_discovery_index_detail", kwargs={"pk": created_index.pk}
    )

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_search_index_create_post_invalid(client_a):
    """Test POST invalid search index payload returns 200 with form errors."""
    url = reverse("bi:search_discovery_index_create")
    resp = client_a.post(url, data={"asset_name": ""})  # asset_name and asset_type are required
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_conversationalbi_views_search_index_edit_get_and_post_success(
    client_a, tenant_a, search_discovery_index_a
):
    """Test GET and POST edit for search discovery index updates instance and logs audit."""
    url = reverse("bi:search_discovery_index_edit", kwargs={"pk": search_discovery_index_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["index"] == search_discovery_index_a

    payload = _conversationalbi_valid_search_index_post_data(
        asset_name="Updated Executive Profitability Cube",
        relevance_weight="1.85",
    )
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:search_discovery_index_detail", kwargs={"pk": search_discovery_index_a.pk}
    )

    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.asset_name == "Updated Executive Profitability Cube"
    assert search_discovery_index_a.relevance_weight == Decimal("1.85")

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-id").first()
    assert audit is not None


# ==============================================================================
# 4. Action Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_views_nlq_rate_success_and_audit(client_a, tenant_a, natural_language_query_a):
    """Test natural_language_query_rate updates rating, logs audit, and guards against open redirects."""
    url = reverse("bi:natural_language_query_rate", kwargs={"pk": natural_language_query_a.pk})

    # GET returns 405 Method Not Allowed
    assert client_a.get(url).status_code == 405

    # POST valid rating and notes
    resp = client_a.post(
        url,
        data={
            "rating": "unhelpful",
            "notes": "Query results were accurate but did not include sub-territories.",
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse(
        "bi:natural_language_query_detail", kwargs={"pk": natural_language_query_a.pk}
    )

    natural_language_query_a.refresh_from_db()
    assert natural_language_query_a.user_rating == "unhelpful"
    assert "sub-territories" in natural_language_query_a.user_feedback_notes

    audit = AuditLog.objects.filter(tenant=tenant_a, action="rate").order_by("-id").first()
    assert audit is not None

    # Test open redirect defense
    resp_redirect = client_a.post(
        url,
        data={
            "rating": "helpful",
            "next": "https://malicious.example.com/steal-session",
        },
    )
    assert resp_redirect.status_code == 302
    assert resp_redirect.url != "https://malicious.example.com/steal-session"
    assert resp_redirect.url == reverse(
        "bi:natural_language_query_detail", kwargs={"pk": natural_language_query_a.pk}
    )

    # Test invalid rating does not change existing valid rating
    resp_inv = client_a.post(url, data={"rating": "invalid_rating_value"})
    assert resp_inv.status_code == 302
    natural_language_query_a.refresh_from_db()
    assert natural_language_query_a.user_rating == "helpful"


@pytest.mark.django_db
def test_conversationalbi_views_session_toggle_pin(client_a, tenant_a, conversation_session_a):
    """Test bi_conversation_session_toggle_pin toggles is_pinned and handles open redirect defense."""
    url = reverse("bi:bi_conversation_session_toggle_pin", kwargs={"pk": conversation_session_a.pk})

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # Initial state is True (pinned)
    assert conversation_session_a.is_pinned is True

    # POST toggles to False
    resp = client_a.post(url)
    assert resp.status_code == 302
    conversation_session_a.refresh_from_db()
    assert conversation_session_a.is_pinned is False

    audit_unpin = AuditLog.objects.filter(tenant=tenant_a, action="unpin").first()
    assert audit_unpin is not None

    # POST toggles back to True with next url preservation
    target_next = reverse("bi:bi_conversation_session_list")
    resp_pin = client_a.post(url, data={"next": target_next})
    assert resp_pin.status_code == 302
    assert resp_pin.url == target_next
    conversation_session_a.refresh_from_db()
    assert conversation_session_a.is_pinned is True

    audit_pin = AuditLog.objects.filter(tenant=tenant_a, action="pin").first()
    assert audit_pin is not None

    # Open redirect defense
    resp_bad = client_a.post(url, data={"next": "http://evil.com/phish"})
    assert resp_bad.status_code == 302
    assert resp_bad.url != "http://evil.com/phish"


@pytest.mark.django_db
def test_conversationalbi_views_session_close(client_a, tenant_a, conversation_session_a):
    """Test bi_conversation_session_close marks session as closed and logs audit."""
    url = reverse("bi:bi_conversation_session_close", kwargs={"pk": conversation_session_a.pk})

    # GET returns 405
    assert client_a.get(url).status_code == 405

    assert conversation_session_a.session_status == "active"
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse(
        "bi:bi_conversation_session_detail", kwargs={"pk": conversation_session_a.pk}
    )

    conversation_session_a.refresh_from_db()
    assert conversation_session_a.session_status == "closed"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="close").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_session_ask_action_and_next_target(
    client_a, tenant_a, admin_user, conversation_session_a
):
    """Test bi_conversation_session_ask creates query turn, increments message count, and preserves next redirect (I6)."""
    url = reverse("bi:bi_conversation_session_ask", kwargs={"pk": conversation_session_a.pk})

    # GET returns 405
    assert client_a.get(url).status_code == 405

    initial_count = conversation_session_a.message_count

    # Empty question guard
    resp_empty = client_a.post(url, data={"query_text": ""})
    assert resp_empty.status_code == 302
    conversation_session_a.refresh_from_db()
    assert conversation_session_a.message_count == initial_count

    # Valid ask POST with next URL preservation (I6)
    workspace_url = reverse("bi:bi_chat_workspace") + f"?session={conversation_session_a.pk}"
    resp_ask = client_a.post(
        url,
        data={
            "query_text": "What are our top 3 gross margin drivers in North America?",
            "next": workspace_url,
        },
    )
    assert resp_ask.status_code == 302
    assert resp_ask.url == workspace_url

    conversation_session_a.refresh_from_db()
    assert conversation_session_a.message_count == initial_count + 1

    created_query = NaturalLanguageQuery.objects.filter(
        tenant=tenant_a,
        conversation_session=conversation_session_a,
        query_text="What are our top 3 gross margin drivers in North America?",
    ).first()
    assert created_query is not None
    assert created_query.user == admin_user
    assert created_query.execution_status == "completed"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-id").first()
    assert audit is not None

    # Open redirect defense
    resp_evil = client_a.post(
        url,
        data={
            "query_text": "Another question turn",
            "next": "https://malicious.example.com/exploit",
        },
    )
    assert resp_evil.status_code == 302
    assert resp_evil.url != "https://malicious.example.com/exploit"
    assert resp_evil.url == reverse(
        "bi:bi_conversation_session_detail", kwargs={"pk": conversation_session_a.pk}
    )


@pytest.mark.django_db
def test_conversationalbi_views_narrative_publish_action(client_a, tenant_a, narrative_explanation_b):
    """Test narrative_explanation_publish sets status to published (I15) and logs audit."""
    # Start with narrative_b which is generated/draft
    narrative_explanation_b.tenant = tenant_a
    narrative_explanation_b.status = "generated"
    narrative_explanation_b.save()

    url = reverse("bi:narrative_explanation_publish", kwargs={"pk": narrative_explanation_b.pk})

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # POST with next parameter
    list_url = reverse("bi:narrative_explanation_list")
    resp = client_a.post(url, data={"next": list_url})
    assert resp.status_code == 302
    assert resp.url == list_url

    narrative_explanation_b.refresh_from_db()
    assert narrative_explanation_b.status == "published"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-id").first()
    assert audit is not None

    # Open redirect defense
    resp_bad = client_a.post(url, data={"next": "https://badsite.com"})
    assert resp_bad.status_code == 302
    assert resp_bad.url != "https://badsite.com"


@pytest.mark.django_db
def test_conversationalbi_views_narrative_regenerate_action(client_a, tenant_a, narrative_explanation_a):
    """Test narrative_explanation_regenerate recomputes body, takeaways, and audio script."""
    url = reverse("bi:narrative_explanation_regenerate", kwargs={"pk": narrative_explanation_a.pk})

    # GET returns 405
    assert client_a.get(url).status_code == 405

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse(
        "bi:narrative_explanation_detail", kwargs={"pk": narrative_explanation_a.pk}
    )

    narrative_explanation_a.refresh_from_db()
    assert "Executive Overview" in narrative_explanation_a.narrative_body
    assert len(narrative_explanation_a.key_takeaways) >= 4
    assert "Executive audio briefing" in narrative_explanation_a.audio_ready_script
    assert narrative_explanation_a.status == "generated"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-id").first()
    assert audit is not None


@pytest.mark.django_db
def test_conversationalbi_views_search_index_reweight_action(client_a, tenant_a, search_discovery_index_a):
    """Test search_discovery_index_reweight handles valid decimals and non-finite NaN/Infinity fallback (I1)."""
    url = reverse("bi:search_discovery_index_reweight", kwargs={"pk": search_discovery_index_a.pk})

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # 1. Valid decimal weight
    resp_valid = client_a.post(url, data={"weight": "3.75"})
    assert resp_valid.status_code == 302
    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.relevance_weight == Decimal("3.75")

    # 2. Non-finite "NaN" fallback: increments weight by 0.50 (I1)
    resp_nan = client_a.post(url, data={"weight": "NaN"})
    assert resp_nan.status_code == 302
    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.relevance_weight == Decimal("4.25")

    # 3. Non-finite "Infinity" fallback: increments weight by 0.50 (I1)
    resp_inf = client_a.post(url, data={"weight": "Infinity"})
    assert resp_inf.status_code == 302
    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.relevance_weight == Decimal("4.75")

    # 4. Empty weight: increments weight by 0.50
    resp_empty = client_a.post(url, data={"weight": ""})
    assert resp_empty.status_code == 302
    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.relevance_weight == Decimal("5.25")

    # 5. Clamping bounds check: exceeding max 99.99 clamps to 99.99
    resp_max = client_a.post(url, data={"weight": "150.00"})
    assert resp_max.status_code == 302
    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.relevance_weight == Decimal("99.99")

    # 6. Clamping bounds check: below min 0.10 clamps to 0.10
    resp_min = client_a.post(url, data={"weight": "0.01"})
    assert resp_min.status_code == 302
    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.relevance_weight == Decimal("0.10")

    audit = AuditLog.objects.filter(tenant=tenant_a, action="reweight").order_by("-id").first()
    assert audit is not None


# ==============================================================================
# 5. Hub & Workspace Views Tests
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_views_chat_workspace_get_and_session_param(
    client_a, conversation_session_a, natural_language_query_a
):
    """Test bi_chat_workspace renders active session, turns, suggested prompts, and validates session param."""
    url = reverse("bi:bi_chat_workspace")

    # Default workspace without session param loads first session
    resp_default = client_a.get(url)
    assert resp_default.status_code == 200
    assert "sessions" in resp_default.context
    assert "active_session" in resp_default.context
    assert "turns" in resp_default.context
    assert "suggested_prompts" in resp_default.context

    # Workspace with ?session=<id>
    resp_session = client_a.get(f"{url}?session={conversation_session_a.pk}")
    assert resp_session.status_code == 200
    assert resp_session.context["active_session"] == conversation_session_a
    assert natural_language_query_a in list(resp_session.context["turns"])

    # Non-digit session param raises 404
    resp_404 = client_a.get(f"{url}?session=not_a_number")
    assert resp_404.status_code == 404


@pytest.mark.django_db
def test_conversationalbi_views_search_discovery_hub_and_telemetry(
    client_a, tenant_a, search_discovery_index_a
):
    """Test search_discovery_hub matches search queries, returns categories, and increments search hit telemetry."""
    url = reverse("bi:search_discovery_hub")

    # Initial hub load without search query
    resp_init = client_a.get(url)
    assert resp_init.status_code == 200
    assert "search_query" in resp_init.context
    assert "results" in resp_init.context
    assert "result_count" in resp_init.context
    assert "categories" in resp_init.context
    assert "featured_assets" in resp_init.context

    initial_hits = search_discovery_index_a.search_hit_count

    # Search with match on keywords/name: ?q=revenue
    resp_search = client_a.get(f"{url}?q=revenue")
    assert resp_search.status_code == 200
    assert resp_search.context["result_count"] >= 1
    assert search_discovery_index_a in resp_search.context["results"]

    # Telemetry verification: search_hit_count incremented by 1
    search_discovery_index_a.refresh_from_db()
    assert search_discovery_index_a.search_hit_count == initial_hits + 1

    # Search query with match on margin
    resp_margin = client_a.get(f"{url}?q=margin")
    assert resp_margin.status_code == 200
    assert search_discovery_index_a in resp_margin.context["results"]


# ==============================================================================
# 6. Delete Views & Permission Guards
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_views_delete_admin_post_and_guard(
    client_a, tenant_a, admin_user
):
    """Test all 4 delete views: GET returns 405, POST by admin deletes instance and logs audit."""
    # 1. NaturalLanguageQuery delete
    nlq = _conversationalbi_create_nlq(tenant=tenant_a, user=admin_user, query_text="To be deleted NLQ")
    url_nlq = reverse("bi:natural_language_query_delete", kwargs={"pk": nlq.pk})
    assert client_a.get(url_nlq).status_code == 405
    resp_post_nlq = client_a.post(url_nlq)
    assert resp_post_nlq.status_code == 302
    assert resp_post_nlq.url == reverse("bi:natural_language_query_list")
    assert not NaturalLanguageQuery.objects.filter(pk=nlq.pk).exists()

    # 2. BiConversationSession delete
    session = _conversationalbi_create_session(tenant=tenant_a, user=admin_user, title="To be deleted session")
    url_session = reverse("bi:bi_conversation_session_delete", kwargs={"pk": session.pk})
    assert client_a.get(url_session).status_code == 405
    resp_post_session = client_a.post(url_session)
    assert resp_post_session.status_code == 302
    assert resp_post_session.url == reverse("bi:bi_conversation_session_list")
    assert not BiConversationSession.objects.filter(pk=session.pk).exists()

    # 3. NarrativeExplanation delete
    narrative = _conversationalbi_create_narrative(tenant=tenant_a, created_by=admin_user, title="To be deleted narrative")
    url_narrative = reverse("bi:narrative_explanation_delete", kwargs={"pk": narrative.pk})
    assert client_a.get(url_narrative).status_code == 405
    resp_post_narrative = client_a.post(url_narrative)
    assert resp_post_narrative.status_code == 302
    assert resp_post_narrative.url == reverse("bi:narrative_explanation_list")
    assert not NarrativeExplanation.objects.filter(pk=narrative.pk).exists()

    # 4. SearchDiscoveryIndex delete
    search_idx = _conversationalbi_create_search_index(tenant=tenant_a, asset_name="To be deleted index")
    url_idx = reverse("bi:search_discovery_index_delete", kwargs={"pk": search_idx.pk})
    assert client_a.get(url_idx).status_code == 405
    resp_post_idx = client_a.post(url_idx)
    assert resp_post_idx.status_code == 302
    assert resp_post_idx.url == reverse("bi:search_discovery_index_list")
    assert not SearchDiscoveryIndex.objects.filter(pk=search_idx.pk).exists()

    # Audit logs for all 4 deletions
    delete_audits = AuditLog.objects.filter(tenant=tenant_a, action="delete")
    assert delete_audits.count() >= 4


@pytest.mark.django_db
def test_conversationalbi_views_delete_non_admin_403_forbidden(
    member_client,
    natural_language_query_a,
    conversation_session_a,
    narrative_explanation_a,
    search_discovery_index_a,
):
    """Test all 4 delete views return HTTP 403 Forbidden when invoked by non-admin member."""
    delete_urls = [
        reverse("bi:natural_language_query_delete", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:bi_conversation_session_delete", kwargs={"pk": conversation_session_a.pk}),
        reverse("bi:narrative_explanation_delete", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:search_discovery_index_delete", kwargs={"pk": search_discovery_index_a.pk}),
    ]

    for url in delete_urls:
        resp = member_client.post(url)
        assert resp.status_code == 403

    # Ensure none were actually deleted
    assert NaturalLanguageQuery.objects.filter(pk=natural_language_query_a.pk).exists()
    assert BiConversationSession.objects.filter(pk=conversation_session_a.pk).exists()
    assert NarrativeExplanation.objects.filter(pk=narrative_explanation_a.pk).exists()
    assert SearchDiscoveryIndex.objects.filter(pk=search_discovery_index_a.pk).exists()


# ==============================================================================
# 7. Multi-Tenancy Cross-Tenant IDOR
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_views_cross_tenant_isolation_idor(
    client_a,
    natural_language_query_b,
    conversation_session_b,
    narrative_explanation_b,
    search_discovery_index_b,
):
    """Test client from Tenant A cannot access, edit, delete, or perform actions on Tenant B entities (returns 404)."""
    # NLQ tenant isolation
    assert client_a.get(reverse("bi:natural_language_query_detail", kwargs={"pk": natural_language_query_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:natural_language_query_edit", kwargs={"pk": natural_language_query_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:natural_language_query_delete", kwargs={"pk": natural_language_query_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:natural_language_query_rate", kwargs={"pk": natural_language_query_b.pk}), data={"rating": "helpful"}).status_code == 404

    # Conversation Session tenant isolation
    assert client_a.get(reverse("bi:bi_conversation_session_detail", kwargs={"pk": conversation_session_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:bi_conversation_session_edit", kwargs={"pk": conversation_session_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:bi_conversation_session_delete", kwargs={"pk": conversation_session_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:bi_conversation_session_toggle_pin", kwargs={"pk": conversation_session_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:bi_conversation_session_close", kwargs={"pk": conversation_session_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:bi_conversation_session_ask", kwargs={"pk": conversation_session_b.pk}), data={"query_text": "Cross tenant probe"}).status_code == 404

    # Narrative Explanation tenant isolation
    assert client_a.get(reverse("bi:narrative_explanation_detail", kwargs={"pk": narrative_explanation_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:narrative_explanation_edit", kwargs={"pk": narrative_explanation_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:narrative_explanation_delete", kwargs={"pk": narrative_explanation_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:narrative_explanation_publish", kwargs={"pk": narrative_explanation_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:narrative_explanation_regenerate", kwargs={"pk": narrative_explanation_b.pk})).status_code == 404

    # Search Discovery Index tenant isolation
    assert client_a.get(reverse("bi:search_discovery_index_detail", kwargs={"pk": search_discovery_index_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:search_discovery_index_edit", kwargs={"pk": search_discovery_index_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:search_discovery_index_delete", kwargs={"pk": search_discovery_index_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:search_discovery_index_reweight", kwargs={"pk": search_discovery_index_b.pk}), data={"weight": "2.00"}).status_code == 404
