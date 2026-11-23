"""Security, multi-tenancy, authorization, and IDOR tests for Sub-module 13.6: Search & Discovery.

Covers:
1. Multi-Tenant Data Isolation & IDOR (Assert 404):
   - Cross-tenant object access attempts by PK return 404 Not Found:
     - saved_search_detail, saved_search_edit, saved_search_delete, saved_search_run, saved_search_toggle_pin
     - search_alert_detail, search_alert_edit, search_alert_delete, search_alert_toggle_active, search_alert_run_check
     - search_synonym_detail, search_synonym_edit, search_synonym_delete, search_synonym_toggle_active
     - search_query_log_detail, search_query_log_delete
     - search_click_track with Tenant B doc PK -> 404
   - SearchHub document isolation: Querying in Tenant A never returns documents belonging to Tenant B.
   - SearchHub synonym isolation: Synonyms configured in Tenant B are never applied to searches in Tenant A.
   - List views tenant isolation: Saved search list, alert list, synonym list, query log list do not leak cross-tenant rows.
2. Cross-Tenant Foreign Key Injection:
   - Submitting a POST with foreign FKs (Tenant B saved search in Tenant A alert form) is rejected and never saved.
3. RBAC & Object-Level Visibility (Assert 403):
   - Query logs list, detail, delete, and analytics require @tenant_admin_required (member_client -> 403).
   - Saved search visibility: private saved search of user 1 cannot be viewed, edited, deleted, or executed by user 2 -> 403.
   - Search alert authorization: member user cannot view, edit, delete, toggle, or check another user's alert -> 403.
   - Search synonym authorization: non-creator member user cannot edit, delete, or toggle synonym rules created by another user -> 403.
4. Open Redirect Protection:
   - saved_search_toggle_pin, search_alert_toggle_active, and search_synonym_toggle_active given an untrusted external
     HTTP_REFERER safely reject external target and redirect to internal list view.
5. Session Token Security:
   - Telemetry query logs do not store or expose unmasked active session tokens (SHA-256 masked hash used).
6. POST-Only Mutating Guards (Assert 405):
   - Delete and toggle mutating endpoints reject GET requests with 405 Method Not Allowed.
7. Unauthenticated Access Redirects (Defense-in-depth):
   - Unauthenticated requests are redirected (302) to login.
"""
import pytest
from django.urls import reverse

from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


# ============================================================================
# Helpers
# ============================================================================

def _search_discovery_create_doc(
    tenant,
    owner,
    title="Test Document",
    doc_type="sop",
    classification="internal",
    status="published",
    extracted_text="Default procedure text and safety rules.",
):
    """Helper to create a tenant-scoped Document with an official DocumentVersion."""
    doc = Document.objects.create(
        tenant=tenant,
        owner=owner,
        title=title,
        document_type=doc_type,
        classification=classification,
        status=status,
        description=f"Description for {title}",
    )
    if extracted_text:
        DocumentVersion.objects.create(
            tenant=tenant,
            document=doc,
            version_label="1.0.0",
            major_number=1,
            minor_number=0,
            patch_number=0,
            version_type="major",
            status="approved",
            is_official=True,
            author=owner,
            extracted_text=extracted_text,
        )
    return doc


def _search_discovery_create_saved_search(
    tenant,
    owner,
    name="Private Operations Query",
    query_text="operations",
    visibility="private",
    department=None,
    is_pinned=False,
):
    """Helper to create a tenant-scoped DocumentSavedSearch."""
    return DocumentSavedSearch.objects.create(
        tenant=tenant,
        owner=owner,
        name=name,
        query_text=query_text,
        filters_json={"status": "published"},
        facet_filters_json={},
        sort_by="-updated_at",
        visibility=visibility,
        department=department,
        is_pinned=is_pinned,
        is_active=True,
    )


def _search_discovery_create_search_alert(
    tenant,
    subscriber,
    saved_search,
    delivery_channel="in_app",
    frequency="daily",
    is_active=True,
    notes="",
):
    """Helper to create a tenant-scoped DocumentSearchAlert."""
    return DocumentSearchAlert.objects.create(
        tenant=tenant,
        subscriber=subscriber,
        saved_search=saved_search,
        delivery_channel=delivery_channel,
        frequency=frequency,
        is_active=is_active,
        notes=notes,
    )


def _search_discovery_create_search_synonym(
    tenant,
    created_by,
    term="agreement",
    synonyms="contract, deal, accord",
    category="domain",
    language="en",
    is_bidirectional=True,
    is_active=True,
):
    """Helper to create a tenant-scoped DocumentSearchSynonym."""
    return DocumentSearchSynonym.objects.create(
        tenant=tenant,
        created_by=created_by,
        term=term,
        synonyms=synonyms,
        category=category,
        language=language,
        is_bidirectional=is_bidirectional,
        is_active=is_active,
    )


def _search_discovery_create_query_log(
    tenant,
    user,
    query_text="sensitive audit records",
    search_source="search_hub",
    results_count=3,
    is_zero_result=False,
):
    """Helper to create a tenant-scoped DocumentSearchQueryLog."""
    return DocumentSearchQueryLog.objects.create(
        tenant=tenant,
        user=user,
        query_text=query_text,
        search_source=search_source,
        filters_applied_json='{"status": "published"}',
        results_count=results_count,
        is_zero_result=is_zero_result,
        execution_time_ms=32.5,
    )


# ============================================================================
# 1. Multi-Tenant Data Isolation & IDOR (Assert 404)
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_saved_search_idor_returns_404(
    client_a, tenant_b, admin_b
):
    """Tenant A client accessing Tenant B saved search by PK must return 404."""
    saved_search_b = _search_discovery_create_saved_search(
        tenant=tenant_b,
        owner=admin_b,
        name="Globex Financials",
        query_text="financials",
        visibility="public",
    )
    pk = saved_search_b.pk

    # Detail
    assert client_a.get(reverse("documents:document_saved_search_detail", args=[pk])).status_code == 404
    # Edit (GET and POST)
    assert client_a.get(reverse("documents:document_saved_search_edit", args=[pk])).status_code == 404
    assert client_a.post(
        reverse("documents:document_saved_search_edit", args=[pk]),
        data={"name": "Hacked Name", "query_text": "hacked", "visibility": "public", "sort_by": "relevance", "is_active": True},
    ).status_code == 404
    # Delete (POST)
    assert client_a.post(reverse("documents:document_saved_search_delete", args=[pk])).status_code == 404
    # Run
    assert client_a.get(reverse("documents:document_saved_search_run", args=[pk])).status_code == 404
    # Toggle pin
    assert client_a.post(reverse("documents:document_saved_search_toggle_pin", args=[pk])).status_code == 404

    # Verify object in Tenant B was not modified or deleted
    saved_search_b.refresh_from_db()
    assert saved_search_b.name == "Globex Financials"


@pytest.mark.django_db
def test_search_discovery_search_alert_idor_returns_404(
    client_a, tenant_b, admin_b
):
    """Tenant A client accessing Tenant B search alert by PK must return 404."""
    saved_search_b = _search_discovery_create_saved_search(tenant=tenant_b, owner=admin_b)
    alert_b = _search_discovery_create_search_alert(
        tenant=tenant_b,
        subscriber=admin_b,
        saved_search=saved_search_b,
    )
    pk = alert_b.pk

    # Detail
    assert client_a.get(reverse("documents:document_search_alert_detail", args=[pk])).status_code == 404
    # Edit (GET and POST)
    assert client_a.get(reverse("documents:document_search_alert_edit", args=[pk])).status_code == 404
    assert client_a.post(
        reverse("documents:document_search_alert_edit", args=[pk]),
        data={"saved_search": saved_search_b.pk, "frequency": "weekly", "delivery_channel": "email", "status": "active"},
    ).status_code == 404
    # Delete (POST)
    assert client_a.post(reverse("documents:document_search_alert_delete", args=[pk])).status_code == 404
    # Toggle active
    assert client_a.post(reverse("documents:document_search_alert_toggle_active", args=[pk])).status_code == 404
    # Run check
    assert client_a.post(reverse("documents:document_search_alert_run_check", args=[pk])).status_code == 404

    # Verify alert still intact in Tenant B
    assert DocumentSearchAlert.objects.filter(pk=pk, tenant=tenant_b).exists()


@pytest.mark.django_db
def test_search_discovery_search_synonym_idor_returns_404(
    client_a, tenant_b, admin_b
):
    """Tenant A client accessing Tenant B synonym by PK must return 404."""
    synonym_b = _search_discovery_create_search_synonym(
        tenant=tenant_b,
        created_by=admin_b,
        term="quantum",
        synonyms="hyperdrive, warp",
    )
    pk = synonym_b.pk

    # Detail
    assert client_a.get(reverse("documents:document_search_synonym_detail", args=[pk])).status_code == 404
    # Edit (GET and POST)
    assert client_a.get(reverse("documents:document_search_synonym_edit", args=[pk])).status_code == 404
    assert client_a.post(
        reverse("documents:document_search_synonym_edit", args=[pk]),
        data={"term": "tampered", "synonyms": "tampered", "category": "domain", "language": "en", "is_bidirectional": True, "is_active": True},
    ).status_code == 404
    # Delete (POST)
    assert client_a.post(reverse("documents:document_search_synonym_delete", args=[pk])).status_code == 404
    # Toggle active
    assert client_a.post(reverse("documents:document_search_synonym_toggle_active", args=[pk])).status_code == 404

    # Verify synonym still intact in Tenant B
    synonym_b.refresh_from_db()
    assert synonym_b.term == "quantum"


@pytest.mark.django_db
def test_search_discovery_query_log_idor_returns_404(
    client_a, tenant_b, admin_b
):
    """Tenant A client accessing Tenant B query log by PK must return 404."""
    log_b = _search_discovery_create_query_log(
        tenant=tenant_b,
        user=admin_b,
        query_text="merger secrets globex",
    )
    pk = log_b.pk

    # Detail
    assert client_a.get(reverse("documents:document_search_query_log_detail", args=[pk])).status_code == 404
    # Delete (POST)
    assert client_a.post(reverse("documents:document_search_query_log_delete", args=[pk])).status_code == 404

    # Verify query log still exists in Tenant B
    assert DocumentSearchQueryLog.objects.filter(pk=pk, tenant=tenant_b).exists()


@pytest.mark.django_db
def test_search_discovery_click_track_cross_tenant_document_returns_404(
    client_a, tenant_b, admin_b
):
    """search_click_track with Tenant B document PK must return 404."""
    doc_b = _search_discovery_create_doc(
        tenant=tenant_b,
        owner=admin_b,
        title="Globex Confidential Blueprints",
    )
    url = reverse("documents:search_click_track", args=[doc_b.pk])
    resp = client_a.get(url, {"rank": 1})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_search_discovery_search_hub_document_tenant_isolation(
    client_a, client_b, tenant_a, tenant_b, admin_user, admin_b
):
    """SearchHub never returns documents belonging to another tenant under any search query."""
    doc_a = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Acme SuperSecret Prototype",
        extracted_text="Proprietary Acme formula and operational protocol.",
    )
    doc_b = _search_discovery_create_doc(
        tenant=tenant_b,
        owner=admin_b,
        title="Globex SuperSecret Formula",
        extracted_text="Proprietary Globex chemical manufacturing steps.",
    )
    shared_keyword_doc_a = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Standard Incident Response",
        extracted_text="Critical incident escalation procedure for team alpha.",
    )
    shared_keyword_doc_b = _search_discovery_create_doc(
        tenant=tenant_b,
        owner=admin_b,
        title="Standard Incident Response",
        extracted_text="Critical incident escalation procedure for team beta.",
    )

    search_url = reverse("documents:search_hub")

    # 1. Search in Tenant A for Tenant B's unique keyword -> 0 results
    resp_a1 = client_a.get(search_url, {"q": "Globex"})
    assert resp_a1.status_code == 200
    assert doc_b.title not in resp_a1.content.decode()
    assert resp_a1.context["total_count"] == 0

    # 2. Search in Tenant A for shared keyword -> only Tenant A document returned
    resp_a2 = client_a.get(search_url, {"q": "Incident Response"})
    assert resp_a2.status_code == 200
    results_a_ids = [d.pk for d in resp_a2.context["results"]]
    assert shared_keyword_doc_a.pk in results_a_ids
    assert shared_keyword_doc_b.pk not in results_a_ids

    # 3. Search in Tenant B for Tenant A's unique keyword -> 0 results
    resp_b1 = client_b.get(search_url, {"q": "Acme"})
    assert resp_b1.status_code == 200
    assert doc_a.title not in resp_b1.content.decode()
    assert resp_b1.context["total_count"] == 0

    # 4. Search in Tenant B for shared keyword -> only Tenant B document returned
    resp_b2 = client_b.get(search_url, {"q": "Incident Response"})
    assert resp_b2.status_code == 200
    results_b_ids = [d.pk for d in resp_b2.context["results"]]
    assert shared_keyword_doc_b.pk in results_b_ids
    assert shared_keyword_doc_a.pk not in results_b_ids


@pytest.mark.django_db
def test_search_discovery_search_hub_synonym_tenant_isolation(
    client_a, tenant_a, tenant_b, admin_user, admin_b
):
    """Synonyms configured in Tenant B are never applied to searches in Tenant A."""
    # Tenant B defines synonym: "warp" <-> "hyperdrive"
    syn_b = _search_discovery_create_search_synonym(
        tenant=tenant_b,
        created_by=admin_b,
        term="warp",
        synonyms="hyperdrive, ftl",
        is_bidirectional=True,
    )
    initial_hit_count = syn_b.hit_count

    # Tenant A has a document with "hyperdrive" in the text
    doc_a = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Interstellar Propulsion Guide",
        extracted_text="The core hyperdrive mechanism requires cooling.",
    )

    # Tenant A user searches for "warp"
    resp = client_a.get(reverse("documents:search_hub"), {"q": "warp"})
    assert resp.status_code == 200

    # Because Tenant B's synonym must NOT be applied to Tenant A,
    # the search for "warp" in Tenant A does not expand to "hyperdrive" and finds nothing.
    assert resp.context["total_count"] == 0
    assert doc_a.title not in resp.content.decode()

    # Hit count in Tenant B's synonym must remain untouched
    syn_b.refresh_from_db()
    assert syn_b.hit_count == initial_hit_count


@pytest.mark.django_db
def test_search_discovery_list_views_tenant_isolation(
    client_a, client_b, tenant_a, tenant_b, admin_user, admin_b
):
    """Saved searches, alerts, synonyms, and query logs in Tenant B never appear in Tenant A list views."""
    # Create distinct records in Tenant B
    saved_b = _search_discovery_create_saved_search(tenant=tenant_b, owner=admin_b, name="Globex Unique Search")
    alert_b = _search_discovery_create_search_alert(
        tenant=tenant_b,
        subscriber=admin_b,
        saved_search=saved_b,
        notes="Globex Alert Specific Notes",
    )
    synonym_b = _search_discovery_create_search_synonym(tenant=tenant_b, created_by=admin_b, term="globexterm")
    log_b = _search_discovery_create_query_log(tenant=tenant_b, user=admin_b, query_text="globex query log")

    # Create distinct records in Tenant A
    saved_a = _search_discovery_create_saved_search(tenant=tenant_a, owner=admin_user, name="Acme Unique Search")
    alert_a = _search_discovery_create_search_alert(
        tenant=tenant_a,
        subscriber=admin_user,
        saved_search=saved_a,
        notes="Acme Alert Specific Notes",
    )
    synonym_a = _search_discovery_create_search_synonym(tenant=tenant_a, created_by=admin_user, term="acmeterm")
    log_a = _search_discovery_create_query_log(tenant=tenant_a, user=admin_user, query_text="acme query log")

    # 1. Saved Searches list
    resp_saved_a = client_a.get(reverse("documents:document_saved_search_list"))
    assert resp_saved_a.status_code == 200
    assert saved_a.pk in [s.pk for s in resp_saved_a.context["saved_searches"]]
    assert saved_b.pk not in [s.pk for s in resp_saved_a.context["saved_searches"]]
    assert saved_a.name in resp_saved_a.content.decode()
    assert saved_b.name not in resp_saved_a.content.decode()

    # 2. Alerts list
    resp_alert_a = client_a.get(reverse("documents:document_search_alert_list"))
    assert resp_alert_a.status_code == 200
    assert alert_a.pk in [a.pk for a in resp_alert_a.context["search_alerts"]]
    assert alert_b.pk not in [a.pk for a in resp_alert_a.context["search_alerts"]]
    assert saved_a.name in resp_alert_a.content.decode()
    assert saved_b.name not in resp_alert_a.content.decode()

    # 3. Synonyms list
    resp_syn_a = client_a.get(reverse("documents:document_search_synonym_list"))
    assert resp_syn_a.status_code == 200
    assert synonym_a.pk in [s.pk for s in resp_syn_a.context["search_synonyms"]]
    assert synonym_b.pk not in [s.pk for s in resp_syn_a.context["search_synonyms"]]
    assert synonym_a.term in resp_syn_a.content.decode()
    assert synonym_b.term not in resp_syn_a.content.decode()

    # 4. Query Logs list
    resp_log_a = client_a.get(reverse("documents:document_search_query_log_list"))
    assert resp_log_a.status_code == 200
    assert log_a.pk in [l.pk for l in resp_log_a.context["query_logs"]]
    assert log_b.pk not in [l.pk for l in resp_log_a.context["query_logs"]]
    assert log_a.query_text in resp_log_a.content.decode()
    assert log_b.query_text not in resp_log_a.content.decode()


# ============================================================================
# 2. Cross-Tenant Foreign Key Injection
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_cross_tenant_fk_injection_rejected_on_create(
    client_a, tenant_a, tenant_b, admin_b
):
    """Submitting a POST with foreign FK (Tenant B saved search in Tenant A alert) must be rejected."""
    saved_search_b = _search_discovery_create_saved_search(
        tenant=tenant_b,
        owner=admin_b,
        name="Foreign Globex Saved Search",
    )

    initial_alert_count = DocumentSearchAlert.objects.filter(tenant=tenant_a).count()
    create_url = reverse("documents:document_search_alert_create")

    resp = client_a.post(
        create_url,
        data={
            "saved_search": saved_search_b.pk,
            "frequency": "daily",
            "delivery_channel": "in_app",
            "status": "active",
            "is_active": True,
        },
    )

    # Must not redirect on success; form error must be returned (status 200)
    assert resp.status_code == 200
    # No alert created
    assert DocumentSearchAlert.objects.filter(tenant=tenant_a).count() == initial_alert_count
    # Form validation error present
    form = resp.context.get("form")
    assert form is not None
    assert "saved_search" in form.errors


@pytest.mark.django_db
def test_search_discovery_cross_tenant_fk_injection_rejected_on_edit(
    client_a, tenant_a, tenant_b, admin_user, admin_b
):
    """Submitting an edit POST pointing saved_search to a foreign tenant's record must be rejected."""
    saved_search_a = _search_discovery_create_saved_search(
        tenant=tenant_a,
        owner=admin_user,
        name="Tenant A Query",
    )
    alert_a = _search_discovery_create_search_alert(
        tenant=tenant_a,
        subscriber=admin_user,
        saved_search=saved_search_a,
    )
    saved_search_b = _search_discovery_create_saved_search(
        tenant=tenant_b,
        owner=admin_b,
        name="Tenant B Query",
    )

    edit_url = reverse("documents:document_search_alert_edit", args=[alert_a.pk])
    resp = client_a.post(
        edit_url,
        data={
            "saved_search": saved_search_b.pk,
            "frequency": "weekly",
            "delivery_channel": "email",
            "status": "active",
            "is_active": True,
        },
    )

    assert resp.status_code == 200
    alert_a.refresh_from_db()
    assert alert_a.saved_search_id == saved_search_a.pk
    assert alert_a.saved_search_id != saved_search_b.pk


# ============================================================================
# 3. RBAC & Object-Level Visibility (Assert 403)
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_query_logs_tenant_admin_gate(
    member_client, tenant_a, admin_user
):
    """Standard non-admin member receives 403 Forbidden on query log list, detail, delete, and analytics."""
    log = _search_discovery_create_query_log(tenant=tenant_a, user=admin_user)

    # 1. List
    resp_list = member_client.get(reverse("documents:document_search_query_log_list"))
    assert resp_list.status_code == 403

    # 2. Detail
    resp_detail = member_client.get(reverse("documents:document_search_query_log_detail", args=[log.pk]))
    assert resp_detail.status_code == 403

    # 3. Delete (POST)
    resp_delete = member_client.post(reverse("documents:document_search_query_log_delete", args=[log.pk]))
    assert resp_delete.status_code == 403

    # 4. Analytics
    resp_analytics = member_client.get(reverse("documents:document_search_analytics"))
    assert resp_analytics.status_code == 403

    # Ensure log record was not deleted
    assert DocumentSearchQueryLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_search_discovery_private_saved_search_visibility_guard(
    member_client, tenant_a, admin_user
):
    """Private saved search owned by admin_user cannot be viewed, edited, deleted, or run by member_user."""
    private_search = _search_discovery_create_saved_search(
        tenant=tenant_a,
        owner=admin_user,
        name="Confidential Executive Audit Query",
        visibility="private",
    )
    pk = private_search.pk

    # 1. Detail -> 403
    assert member_client.get(reverse("documents:document_saved_search_detail", args=[pk])).status_code == 403

    # 2. Edit (GET & POST) -> 403
    assert member_client.get(reverse("documents:document_saved_search_edit", args=[pk])).status_code == 403
    assert member_client.post(
        reverse("documents:document_saved_search_edit", args=[pk]),
        data={"name": "Hacked Name", "query_text": "hacked", "visibility": "private", "sort_by": "relevance"},
    ).status_code == 403

    # 3. Delete -> 403
    assert member_client.post(reverse("documents:document_saved_search_delete", args=[pk])).status_code == 403

    # 4. Run -> 403
    assert member_client.get(reverse("documents:document_saved_search_run", args=[pk])).status_code == 403

    # 5. Toggle pin -> 403
    assert member_client.post(reverse("documents:document_saved_search_toggle_pin", args=[pk])).status_code == 403

    # 6. List view scoping: private search does not appear in member's list
    resp_list = member_client.get(reverse("documents:document_saved_search_list"))
    assert resp_list.status_code == 200
    listed_ids = [s.pk for s in resp_list.context["saved_searches"]]
    assert pk not in listed_ids
    assert private_search.name not in resp_list.content.decode()


@pytest.mark.django_db
def test_search_discovery_search_alert_authorization_guard(
    member_client, tenant_a, admin_user
):
    """Member user cannot view, edit, delete, toggle, or check another user's alert -> 403."""
    saved_search = _search_discovery_create_saved_search(
        tenant=tenant_a,
        owner=admin_user,
        visibility="public",
    )
    alert = _search_discovery_create_search_alert(
        tenant=tenant_a,
        subscriber=admin_user,
        saved_search=saved_search,
    )
    pk = alert.pk

    # 1. Detail -> 403
    assert member_client.get(reverse("documents:document_search_alert_detail", args=[pk])).status_code == 403

    # 2. Edit (GET & POST) -> 403
    assert member_client.get(reverse("documents:document_search_alert_edit", args=[pk])).status_code == 403
    assert member_client.post(
        reverse("documents:document_search_alert_edit", args=[pk]),
        data={"saved_search": saved_search.pk, "frequency": "weekly", "delivery_channel": "email", "status": "active"},
    ).status_code == 403

    # 3. Delete -> 403
    assert member_client.post(reverse("documents:document_search_alert_delete", args=[pk])).status_code == 403

    # 4. Toggle active -> 403
    assert member_client.post(reverse("documents:document_search_alert_toggle_active", args=[pk])).status_code == 403

    # 5. Run check -> 403
    assert member_client.post(reverse("documents:document_search_alert_run_check", args=[pk])).status_code == 403

    # Verify alert was neither deleted nor modified
    alert.refresh_from_db()
    assert alert.subscriber == admin_user


@pytest.mark.django_db
def test_search_discovery_search_synonym_authorization_guard(
    member_client, tenant_a, admin_user
):
    """Non-creator member user cannot edit, delete, or toggle synonym rules created by another user -> 403."""
    synonym = _search_discovery_create_search_synonym(
        tenant=tenant_a,
        created_by=admin_user,
        term="protocol",
        synonyms="standard, guideline",
    )
    pk = synonym.pk

    # 1. Edit (GET & POST) -> 403
    assert member_client.get(reverse("documents:document_search_synonym_edit", args=[pk])).status_code == 403
    assert member_client.post(
        reverse("documents:document_search_synonym_edit", args=[pk]),
        data={"term": "tampered", "synonyms": "tampered", "category": "domain", "language": "en", "is_bidirectional": True, "is_active": True},
    ).status_code == 403

    # 2. Delete -> 403
    assert member_client.post(reverse("documents:document_search_synonym_delete", args=[pk])).status_code == 403

    # 3. Toggle active -> 403
    assert member_client.post(reverse("documents:document_search_synonym_toggle_active", args=[pk])).status_code == 403

    # Verify synonym was not modified
    synonym.refresh_from_db()
    assert synonym.term == "protocol"


# ============================================================================
# 4. Open Redirect Protection
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_open_redirect_protection_saved_search_toggle_pin(
    client_a, tenant_a, admin_user
):
    """saved_search_toggle_pin safely rejects external referer and redirects to internal list."""
    saved_search = _search_discovery_create_saved_search(tenant=tenant_a, owner=admin_user)
    toggle_url = reverse("documents:document_saved_search_toggle_pin", args=[saved_search.pk])

    # Untrusted external referer
    resp = client_a.post(toggle_url, HTTP_REFERER="https://attacker.evil.com/phish")
    assert resp.status_code == 302
    assert resp.url == reverse("documents:document_saved_search_list")

    # Valid internal referer
    valid_internal = reverse("documents:document_saved_search_list")
    resp_valid = client_a.post(toggle_url, HTTP_REFERER=valid_internal)
    assert resp_valid.status_code == 302
    assert resp_valid.url == valid_internal


@pytest.mark.django_db
def test_search_discovery_open_redirect_protection_search_alert_toggle_active(
    client_a, tenant_a, admin_user
):
    """search_alert_toggle_active safely rejects external referer and redirects to internal list."""
    saved_search = _search_discovery_create_saved_search(tenant=tenant_a, owner=admin_user)
    alert = _search_discovery_create_search_alert(tenant=tenant_a, subscriber=admin_user, saved_search=saved_search)
    toggle_url = reverse("documents:document_search_alert_toggle_active", args=[alert.pk])

    # Untrusted external referer
    resp = client_a.post(toggle_url, HTTP_REFERER="https://malicious.example.com/exploit")
    assert resp.status_code == 302
    assert resp.url == reverse("documents:document_search_alert_list")

    # Valid internal referer
    valid_internal = reverse("documents:document_search_alert_list")
    resp_valid = client_a.post(toggle_url, HTTP_REFERER=valid_internal)
    assert resp_valid.status_code == 302
    assert resp_valid.url == valid_internal


@pytest.mark.django_db
def test_search_discovery_open_redirect_protection_search_synonym_toggle_active(
    client_a, tenant_a, admin_user
):
    """search_synonym_toggle_active safely rejects external referer and redirects to internal list."""
    synonym = _search_discovery_create_search_synonym(tenant=tenant_a, created_by=admin_user)
    toggle_url = reverse("documents:document_search_synonym_toggle_active", args=[synonym.pk])

    # Untrusted external referer
    resp = client_a.post(toggle_url, HTTP_REFERER="https://phishing.badguy.org/login")
    assert resp.status_code == 302
    assert resp.url == reverse("documents:document_search_synonym_list")

    # Valid internal referer
    valid_internal = reverse("documents:document_search_synonym_list")
    resp_valid = client_a.post(toggle_url, HTTP_REFERER=valid_internal)
    assert resp_valid.status_code == 302
    assert resp_valid.url == valid_internal


# ============================================================================
# 5. Session Token Security
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_session_token_telemetry_masking(client_a, tenant_a):
    """Telemetry query logs do not store or expose raw unmasked active session tokens."""
    # Execute a search on search_hub with the logged in client
    search_url = reverse("documents:search_hub")
    resp = client_a.get(search_url, {"q": "financial audit protocol"})
    assert resp.status_code == 200

    raw_session_key = client_a.session.session_key
    assert raw_session_key, "Test client session must have an active session_key"

    # Fetch the newly created telemetry log
    log = DocumentSearchQueryLog.objects.filter(
        tenant=tenant_a,
        query_text="financial audit protocol",
    ).first()
    assert log is not None

    # 1. Active raw session key is NOT stored verbatim in the DB
    assert log.session_key != raw_session_key
    assert raw_session_key not in log.session_key

    # 2. The masked session key is a truncated hash (16 chars)
    assert len(log.session_key) <= 16

    # 3. Viewing the log detail view does NOT leak the active raw session token
    detail_url = reverse("documents:document_search_query_log_detail", args=[log.pk])
    detail_resp = client_a.get(detail_url)
    assert detail_resp.status_code == 200
    assert raw_session_key not in detail_resp.content.decode()


# ============================================================================
# 6. POST-Only Mutating Guards (Assert 405)
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_mutating_endpoints_reject_get_with_405(
    client_a, tenant_a, admin_user
):
    """All state-mutating endpoints reject GET requests with 405 Method Not Allowed."""
    saved_search = _search_discovery_create_saved_search(tenant=tenant_a, owner=admin_user)
    alert = _search_discovery_create_search_alert(tenant=tenant_a, subscriber=admin_user, saved_search=saved_search)
    synonym = _search_discovery_create_search_synonym(tenant=tenant_a, created_by=admin_user)
    log = _search_discovery_create_query_log(tenant=tenant_a, user=admin_user)

    mutating_endpoints = [
        # Saved search
        reverse("documents:document_saved_search_delete", args=[saved_search.pk]),
        reverse("documents:document_saved_search_toggle_pin", args=[saved_search.pk]),
        # Search alert
        reverse("documents:document_search_alert_delete", args=[alert.pk]),
        reverse("documents:document_search_alert_toggle_active", args=[alert.pk]),
        reverse("documents:document_search_alert_run_check", args=[alert.pk]),
        # Search synonym
        reverse("documents:document_search_synonym_delete", args=[synonym.pk]),
        reverse("documents:document_search_synonym_toggle_active", args=[synonym.pk]),
        # Query log
        reverse("documents:document_search_query_log_delete", args=[log.pk]),
    ]

    for url in mutating_endpoints:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {res.status_code}"


# ============================================================================
# 7. Unauthenticated Access Redirects (Defense-in-depth)
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_unauthenticated_access_redirects(
    client, tenant_a, admin_user
):
    """Unauthenticated requests to Search & Discovery endpoints redirect to login."""
    saved_search = _search_discovery_create_saved_search(tenant=tenant_a, owner=admin_user)
    alert = _search_discovery_create_search_alert(tenant=tenant_a, subscriber=admin_user, saved_search=saved_search)
    synonym = _search_discovery_create_search_synonym(tenant=tenant_a, created_by=admin_user)
    log = _search_discovery_create_query_log(tenant=tenant_a, user=admin_user)

    endpoints = [
        reverse("documents:search_hub"),
        reverse("documents:search_export_csv"),
        reverse("documents:document_saved_search_list"),
        reverse("documents:document_saved_search_create"),
        reverse("documents:document_saved_search_detail", args=[saved_search.pk]),
        reverse("documents:document_saved_search_edit", args=[saved_search.pk]),
        reverse("documents:document_search_alert_list"),
        reverse("documents:document_search_alert_create"),
        reverse("documents:document_search_alert_detail", args=[alert.pk]),
        reverse("documents:document_search_alert_edit", args=[alert.pk]),
        reverse("documents:document_search_synonym_list"),
        reverse("documents:document_search_synonym_create"),
        reverse("documents:document_search_synonym_detail", args=[synonym.pk]),
        reverse("documents:document_search_synonym_edit", args=[synonym.pk]),
        reverse("documents:document_search_query_log_list"),
        reverse("documents:document_search_analytics"),
        reverse("documents:document_search_query_log_detail", args=[log.pk]),
    ]

    for url in endpoints:
        res = client.get(url)
        assert res.status_code == 302, f"Expected 302 for unauthenticated GET {url}, got {res.status_code}"
        assert "/login/" in res.headers["Location"]
