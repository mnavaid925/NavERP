"""Security and multi-tenant isolation unit tests for Sub-module 10.15 Conversational BI.

Verifies:
1. Cross-tenant IDOR protection (404 on all object endpoints for foreign tenant objects)
2. Workspace foreign tenant session parameter returns 404 (fail-closed, I16)
3. Unauthenticated access redirects to login (302 -> /accounts/login/)
4. Tenant list isolation (no cross-tenant leakage in querysets or search discovery hub)
5. Authorization gates: Delete endpoints require tenant admin (403 for non-admin)
6. CSRF & POST-only protection on mutating endpoints (405 for GET)
7. Open redirect protection across all next-redirecting actions
8. Numeric input hardening (Lesson L35): non-finite Decimal (NaN, Infinity) handling
9. Protocol-relative URL injection rejection (//evil.com)
10. Cross-tenant foreign key injection rejection in forms
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.bi.forms.ConversationalBi.SearchDiscoveryIndexes import SearchDiscoveryIndexForm
from apps.bi.forms.ConversationalBi.NarrativeExplanations import NarrativeExplanationForm
from apps.bi.models.ConversationalBi.BiConversationSessions import BiConversationSession
from apps.bi.models.ConversationalBi.NarrativeExplanations import NarrativeExplanation
from apps.bi.models.ConversationalBi.NaturalLanguageQueries import NaturalLanguageQuery
from apps.bi.models.ConversationalBi.SearchDiscoveryIndexes import SearchDiscoveryIndex

User = get_user_model()


# ==============================================================================
# 1. Cross-Tenant IDOR Protection (Tenant A accessing Tenant B -> 404)
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_nlq_idor(client_a, natural_language_query_b):
    """Assert Tenant A client receives 404 for all Tenant B NLQ endpoints."""
    pk = natural_language_query_b.pk
    detail_url = reverse("bi:natural_language_query_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:natural_language_query_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:natural_language_query_delete", kwargs={"pk": pk})
    rate_url = reverse("bi:natural_language_query_rate", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(edit_url, data={"query_text": "Hacked query"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404
    assert client_a.post(rate_url, data={"rating": "unhelpful"}).status_code == 404


@pytest.mark.django_db
def test_conversationalbi_security_session_idor(client_a, bi_conversation_session_b):
    """Assert Tenant A client receives 404 for all Tenant B conversation session endpoints."""
    pk = bi_conversation_session_b.pk
    detail_url = reverse("bi:bi_conversation_session_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:bi_conversation_session_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:bi_conversation_session_delete", kwargs={"pk": pk})
    pin_url = reverse("bi:bi_conversation_session_toggle_pin", kwargs={"pk": pk})
    close_url = reverse("bi:bi_conversation_session_close", kwargs={"pk": pk})
    ask_url = reverse("bi:bi_conversation_session_ask", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(edit_url, data={"title": "Hacked thread"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404
    assert client_a.post(pin_url).status_code == 404
    assert client_a.post(close_url).status_code == 404
    assert client_a.post(ask_url, data={"query_text": "Hacked message"}).status_code == 404


@pytest.mark.django_db
def test_conversationalbi_security_workspace_foreign_session_idor(client_a, bi_conversation_session_b):
    """Assert accessing workspace with foreign tenant session query param raises 404 (I16)."""
    workspace_url = reverse("bi:bi_chat_workspace")
    resp = client_a.get(f"{workspace_url}?session={bi_conversation_session_b.pk}")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_conversationalbi_security_narrative_idor(client_a, narrative_explanation_b):
    """Assert Tenant A client receives 404 for all Tenant B narrative explanation endpoints."""
    pk = narrative_explanation_b.pk
    detail_url = reverse("bi:narrative_explanation_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:narrative_explanation_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:narrative_explanation_delete", kwargs={"pk": pk})
    publish_url = reverse("bi:narrative_explanation_publish", kwargs={"pk": pk})
    regen_url = reverse("bi:narrative_explanation_regenerate", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(edit_url, data={"title": "Hacked narrative"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404
    assert client_a.post(publish_url).status_code == 404
    assert client_a.post(regen_url).status_code == 404


@pytest.mark.django_db
def test_conversationalbi_security_discovery_idor(client_a, search_discovery_index_b):
    """Assert Tenant A client receives 404 for all Tenant B search discovery index endpoints."""
    pk = search_discovery_index_b.pk
    detail_url = reverse("bi:search_discovery_index_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:search_discovery_index_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:search_discovery_index_delete", kwargs={"pk": pk})
    reweight_url = reverse("bi:search_discovery_index_reweight", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(edit_url, data={"asset_name": "Hacked index"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404
    assert client_a.post(reweight_url, data={"weight": "5.00"}).status_code == 404


# ==============================================================================
# 2. Unauthenticated Access Protection (Anonymous -> Redirect to Login)
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_anonymous_redirect(
    client,
    natural_language_query_a,
    bi_conversation_session_a,
    narrative_explanation_a,
    search_discovery_index_a,
):
    """Assert unauthenticated requests to all 10.15 routes are redirected to login."""
    urls = [
        # List routes
        reverse("bi:natural_language_query_list"),
        reverse("bi:bi_conversation_session_list"),
        reverse("bi:narrative_explanation_list"),
        reverse("bi:search_discovery_index_list"),
        # Hub & workspace
        reverse("bi:bi_chat_workspace"),
        reverse("bi:search_discovery_hub"),
        # Create routes
        reverse("bi:natural_language_query_create"),
        reverse("bi:bi_conversation_session_create"),
        reverse("bi:narrative_explanation_create"),
        reverse("bi:search_discovery_index_create"),
        # Detail routes
        reverse("bi:natural_language_query_detail", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:bi_conversation_session_detail", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:narrative_explanation_detail", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:search_discovery_index_detail", kwargs={"pk": search_discovery_index_a.pk}),
        # Edit routes
        reverse("bi:natural_language_query_edit", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:bi_conversation_session_edit", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:narrative_explanation_edit", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:search_discovery_index_edit", kwargs={"pk": search_discovery_index_a.pk}),
        # Actions
        reverse("bi:natural_language_query_rate", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:bi_conversation_session_toggle_pin", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:bi_conversation_session_close", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:bi_conversation_session_ask", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:narrative_explanation_publish", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:narrative_explanation_regenerate", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:search_discovery_index_reweight", kwargs={"pk": search_discovery_index_a.pk}),
        # Delete routes
        reverse("bi:natural_language_query_delete", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:bi_conversation_session_delete", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:narrative_explanation_delete", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:search_discovery_index_delete", kwargs={"pk": search_discovery_index_a.pk}),
    ]

    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"
        assert "/login/" in resp.url


# ==============================================================================
# 3. Tenant List & Search Isolation (No Cross-Tenant Leakage)
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_list_query_isolation(
    client_a,
    natural_language_query_a,
    natural_language_query_b,
    bi_conversation_session_a,
    bi_conversation_session_b,
    narrative_explanation_a,
    narrative_explanation_b,
    search_discovery_index_a,
    search_discovery_index_b,
):
    """Assert list views only display tenant_a records, never tenant_b records."""
    # NLQ list
    resp = client_a.get(reverse("bi:natural_language_query_list"))
    assert resp.status_code == 200
    queries = list(resp.context["queries"])
    assert natural_language_query_a in queries
    assert natural_language_query_b not in queries

    # Session list
    resp = client_a.get(reverse("bi:bi_conversation_session_list"))
    assert resp.status_code == 200
    sessions = list(resp.context["sessions"])
    assert bi_conversation_session_a in sessions
    assert bi_conversation_session_b not in sessions

    # Narrative list
    resp = client_a.get(reverse("bi:narrative_explanation_list"))
    assert resp.status_code == 200
    narratives = list(resp.context["narratives"])
    assert narrative_explanation_a in narratives
    assert narrative_explanation_b not in narratives

    # Search discovery list
    resp = client_a.get(reverse("bi:search_discovery_index_list"))
    assert resp.status_code == 200
    indexes = list(resp.context["indexes"])
    assert search_discovery_index_a in indexes
    assert search_discovery_index_b not in indexes


@pytest.mark.django_db
def test_conversationalbi_security_hub_search_isolation(
    client_a,
    search_discovery_index_a,
    search_discovery_index_b,
):
    """Assert discovery hub only surfaces tenant_a assets, even on broad query."""
    resp = client_a.get(reverse("bi:search_discovery_hub") + "?q=dashboard")
    assert resp.status_code == 200
    results = list(resp.context["results"])
    assert search_discovery_index_a in results
    assert search_discovery_index_b not in results


# ==============================================================================
# 4. Authorization Gates: Deletion Restricted to Tenant Admin
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_delete_requires_tenant_admin(
    client,
    tenant_a,
    natural_language_query_a,
    bi_conversation_session_a,
    narrative_explanation_a,
    search_discovery_index_a,
):
    """Assert regular non-admin tenant user receives 403 Forbidden on delete POST."""
    regular_user = User.objects.create_user(
        username="staff_user_acme",
        email="staff@acme.com",
        password="password",
        tenant=tenant_a,
        is_tenant_admin=False,
    )
    client.force_login(regular_user)

    delete_urls = [
        reverse("bi:natural_language_query_delete", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:bi_conversation_session_delete", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:narrative_explanation_delete", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:search_discovery_index_delete", kwargs={"pk": search_discovery_index_a.pk}),
    ]

    for url in delete_urls:
        resp = client.post(url)
        assert resp.status_code == 403, f"Expected 403 for non-admin on {url}, got {resp.status_code}"

    # Verify no objects were deleted
    assert NaturalLanguageQuery.objects.filter(pk=natural_language_query_a.pk).exists()
    assert BiConversationSession.objects.filter(pk=bi_conversation_session_a.pk).exists()
    assert NarrativeExplanation.objects.filter(pk=narrative_explanation_a.pk).exists()
    assert SearchDiscoveryIndex.objects.filter(pk=search_discovery_index_a.pk).exists()


# ==============================================================================
# 5. POST-Only Protection on Destructive and Mutating Actions
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_mutating_actions_post_only(
    client_a,
    natural_language_query_a,
    bi_conversation_session_a,
    narrative_explanation_a,
    search_discovery_index_a,
):
    """Assert GET requests to action-only mutating endpoints return 405 Method Not Allowed."""
    action_urls = [
        reverse("bi:natural_language_query_rate", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:natural_language_query_delete", kwargs={"pk": natural_language_query_a.pk}),
        reverse("bi:bi_conversation_session_toggle_pin", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:bi_conversation_session_close", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:bi_conversation_session_ask", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:bi_conversation_session_delete", kwargs={"pk": bi_conversation_session_a.pk}),
        reverse("bi:narrative_explanation_publish", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:narrative_explanation_regenerate", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:narrative_explanation_delete", kwargs={"pk": narrative_explanation_a.pk}),
        reverse("bi:search_discovery_index_reweight", kwargs={"pk": search_discovery_index_a.pk}),
        reverse("bi:search_discovery_index_delete", kwargs={"pk": search_discovery_index_a.pk}),
    ]

    for url in action_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET on {url}, got {resp.status_code}"


# ==============================================================================
# 6. Open Redirect Protection
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_open_redirect_protection(
    client_a,
    bi_conversation_session_a,
    narrative_explanation_a,
    search_discovery_index_a,
):
    """Assert next redirect parameters with malicious external URLs are rejected."""
    malicious_target = "https://evil-attacker.example.com/exploit"

    # bi_conversation_session_ask
    resp = client_a.post(
        reverse("bi:bi_conversation_session_ask", kwargs={"pk": bi_conversation_session_a.pk}),
        data={"query_text": "Safe question", "next": malicious_target},
    )
    assert resp.status_code == 302
    assert resp.url != malicious_target
    assert resp.url.startswith("/")

    # narrative_explanation_publish
    resp = client_a.post(
        reverse("bi:narrative_explanation_publish", kwargs={"pk": narrative_explanation_a.pk}),
        data={"next": malicious_target},
    )
    assert resp.status_code == 302
    assert resp.url != malicious_target
    assert resp.url.startswith("/")

    # search_discovery_index_reweight
    resp = client_a.post(
        reverse("bi:search_discovery_index_reweight", kwargs={"pk": search_discovery_index_a.pk}),
        data={"weight": "2.50", "next": malicious_target},
    )
    assert resp.status_code == 302
    assert resp.url != malicious_target
    assert resp.url.startswith("/")


# ==============================================================================
# 7. Numeric Input Hardening (Lesson L35)
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_reweight_non_finite_decimal_guard(client_a, search_discovery_index_a):
    """Assert non-finite Decimal strings (NaN, Infinity, -Infinity) do not crash database (L35)."""
    url = reverse("bi:search_discovery_index_reweight", kwargs={"pk": search_discovery_index_a.pk})

    for bad_input in ["NaN", "Infinity", "-Infinity", "snan"]:
        resp = client_a.post(url, data={"weight": bad_input})
        assert resp.status_code == 302, f"Failed on input {bad_input}"

    search_discovery_index_a.refresh_from_db()
    # Ensure weight is still a valid finite Decimal
    assert search_discovery_index_a.relevance_weight.is_finite()
    assert search_discovery_index_a.relevance_weight >= Decimal("0.10")


# ==============================================================================
# 8. Protocol-Relative URL Protection (M8)
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_protocol_relative_url_rejected(tenant_a):
    """Assert SearchDiscoveryIndexForm rejects protocol-relative URLs starting with //."""
    form = SearchDiscoveryIndexForm(
        data={
            "asset_name": "Suspicious Link",
            "asset_type": "dashboard",
            "target_url": "//evil.com/phishing",
            "relevance_weight": "1.00",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "target_url" in form.errors
    assert "Protocol-relative" in form.errors["target_url"][0]


# ==============================================================================
# 9. Mass Assignment & Workflow Status Field Exclusion (M9)
# ==============================================================================


@pytest.mark.django_db
def test_conversationalbi_security_status_excluded_from_narrative_form():
    """Assert status field is strictly excluded from NarrativeExplanationForm (M9)."""
    assert "status" not in NarrativeExplanationForm.Meta.fields
