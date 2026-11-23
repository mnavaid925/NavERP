"""View and CRUD integration tests for Sub-module 13.6 Search & Discovery.

Covers:
- SearchHub views (search_hub, search_export_csv, search_click_track)
- DocumentSavedSearch views (list, detail, create, edit, delete, run, toggle_pin)
- DocumentSearchAlert views (list, detail, create, edit, delete, toggle_active, run_check)
- DocumentSearchSynonym views (list, detail, create, edit, delete, toggle_active)
- DocumentSearchQueryLog views (list, detail, delete, analytics)
- Edge cases, security/permissions, negative parameters, and pagination guards.
"""
import csv
import io
import json
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


# ============================================================================
# Helpers
# ============================================================================

def _search_discovery_create_dept(tenant, name="Engineering"):
    """Helper to create an OrgUnit department for tenant."""
    return OrgUnit.objects.create(
        tenant=tenant,
        name=name,
        kind="department",
    )


def _search_discovery_create_doc(
    tenant,
    owner,
    title="Test Document",
    doc_type="sop",
    classification="internal",
    status="published",
    department=None,
    extracted_text="Sample operating procedures and safety standards.",
):
    """Helper to create a Document and associated official DocumentVersion."""
    doc = Document.objects.create(
        tenant=tenant,
        owner=owner,
        title=title,
        document_type=doc_type,
        classification=classification,
        status=status,
        department=department,
        description=f"Description for {title}",
    )
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


# ============================================================================
# 1. SearchHub View Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_search_hub_rendering(client_a, tenant_a, document):
    """Test search_hub renders 200 OK with expected context keys."""
    url = reverse("documents:search_hub")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert "results" in resp.context
    assert "facets" in resp.context
    assert "folders" in resp.context
    assert "saved_searches" in resp.context
    assert "popular_searches" in resp.context
    assert "total_count" in resp.context
    assert resp.context["total_count"] >= 1
    assert document.title in resp.content.decode()


@pytest.mark.django_db
def test_search_discovery_search_hub_synonym_expansion(client_a, tenant_a, admin_user):
    """Test search query applies synonym expansion and increments synonym hit_count."""
    doc = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Centrifuge Calibration Protocol",
        doc_type="sop",
        extracted_text="Perform routine maintenance and verify rotational speed.",
    )
    synonym = DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="maintenance",
        synonyms="servicing, calibration, overhaul",
        category="domain",
        is_bidirectional=True,
        is_active=True,
        created_by=admin_user,
    )

    url = reverse("documents:search_hub")
    # Search using a synonym term that is not in the document title
    resp = client_a.get(url, {"q": "servicing"})
    assert resp.status_code == 200
    assert doc in resp.context["results"]
    assert len(resp.context["synonyms_applied"]) >= 1

    synonym.refresh_from_db()
    assert synonym.hit_count >= 1


@pytest.mark.django_db
def test_search_discovery_search_hub_nlp_tokens(client_a, tenant_a, admin_user):
    """Test natural language token parsing (type:sop status:published)."""
    match_doc = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Fire Evacuation Standard",
        doc_type="sop",
        status="published",
    )
    non_match_doc = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Fire Safety Guidelines",
        doc_type="policy",
        status="published",
    )

    url = reverse("documents:search_hub")
    resp = client_a.get(url, {"q": "type:sop status:published Fire"})
    assert resp.status_code == 200

    intent_chips = resp.context["intent_chips"]
    chip_keys = [c["key"] for c in intent_chips]
    assert "document_type" in chip_keys
    assert "status" in chip_keys

    results = resp.context["results"]
    assert match_doc in results
    assert non_match_doc not in results


@pytest.mark.django_db
def test_search_discovery_search_hub_facet_filtering(client_a, tenant_a, admin_user, document_folder):
    """Test facet filtering by doc_type, classification, status, folder, author, and date range."""
    dept = _search_discovery_create_dept(tenant_a, name="Quality Dept")
    document_folder.department = dept
    document_folder.save(update_fields=["department"])

    target_doc = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Quality Assurance Policy Doc",
        doc_type="policy",
        classification="internal",
        status="published",
        department=dept,
    )
    other_doc = _search_discovery_create_doc(
        tenant=tenant_a,
        owner=admin_user,
        title="Confidential Marketing Deck",
        doc_type="presentation",
        classification="confidential",
        status="draft",
    )

    url = reverse("documents:search_hub")
    filter_params = {
        "doc_type": "policy",
        "classification": "internal",
        "status": "published",
        "folder": str(document_folder.pk),
        "author": str(admin_user.pk),
        "date_from": (timezone.now() - timezone.timedelta(days=1)).strftime("%Y-%m-%d"),
        "date_to": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%d"),
    }
    resp = client_a.get(url, filter_params)
    assert resp.status_code == 200
    assert target_doc in resp.context["results"]
    assert other_doc not in resp.context["results"]


@pytest.mark.django_db
def test_search_discovery_search_hub_sorting(client_a, tenant_a, admin_user):
    """Test search_hub ordering by updated_at_desc, created_at_desc, and title_asc."""
    doc_b = _search_discovery_create_doc(tenant_a, admin_user, title="Beta Operating Manual")
    doc_a = _search_discovery_create_doc(tenant_a, admin_user, title="Alpha Operating Manual")

    url = reverse("documents:search_hub")
    # Title ascending
    resp_alpha = client_a.get(url, {"q": "Operating", "sort_by": "title_asc"})
    assert resp_alpha.status_code == 200
    results = list(resp_alpha.context["results"])
    assert results[0].title == doc_a.title
    assert results[1].title == doc_b.title

    # Updated at desc
    resp_updated = client_a.get(url, {"q": "Operating", "sort_by": "updated_at_desc"})
    assert resp_updated.status_code == 200


@pytest.mark.django_db
def test_search_discovery_search_hub_zero_results_and_telemetry(client_a, tenant_a, admin_user):
    """Test search with no matches yields zero-result suggestions and logs telemetry."""
    url = reverse("documents:search_hub")
    resp = client_a.get(url, {"q": "nonexistenttermxyz999"})
    assert resp.status_code == 200
    assert resp.context["total_count"] == 0
    assert len(resp.context["zero_result_suggestions"]) > 0

    # Query log was created for telemetry
    log = DocumentSearchQueryLog.objects.filter(
        tenant=tenant_a,
        query_text="nonexistenttermxyz999",
    ).first()
    assert log is not None
    assert log.is_zero_result is True
    assert log.results_count == 0


@pytest.mark.django_db
def test_search_discovery_search_export_csv(client_a, tenant_a, document):
    """Test search_export_csv returns 200 text/csv with header row and audit log."""
    url = reverse("documents:search_export_csv")
    resp = client_a.get(url, {"q": document.title[:10]})
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'filename="search_results.csv"' in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) >= 2  # header + at least 1 document row
    assert rows[0] == ["Number", "Title", "Document Type", "Classification", "Status", "Department", "Owner", "Created At"]
    assert any(document.title in row[1] for row in rows[1:])

    # Audit log verification
    audit = AuditLog.objects.filter(tenant=tenant_a, action="export").first()
    assert audit is not None


@pytest.mark.django_db
def test_search_discovery_search_click_track(client_a, tenant_a, admin_user, document):
    """Test search_click_track updates query log telemetry and redirects 302 to document detail."""
    query_log = DocumentSearchQueryLog.objects.create(
        tenant=tenant_a,
        query_text="operational procedure",
        search_source="search_hub",
        results_count=1,
        user=admin_user,
    )

    url = reverse("documents:search_click_track", args=[document.pk])
    resp = client_a.get(url, {"rank": "1"})
    assert resp.status_code == 302
    assert resp.url == reverse("documents:document_detail", args=[document.pk])

    query_log.refresh_from_db()
    assert query_log.clicked_document == document
    assert query_log.click_rank == 1


# ============================================================================
# 2. DocumentSavedSearch View Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_saved_search_list_and_filters(
    client_a, member_client, tenant_a, admin_user, member_user, document_saved_search
):
    """Test document_saved_search_list rendering, scoping, and filter parameters."""
    dept = _search_discovery_create_dept(tenant_a, name="Research")
    private_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        owner=admin_user,
        name="Private Admin Filter",
        visibility="private",
        department=dept,
        is_active=False,
    )

    url = reverse("documents:document_saved_search_list")

    # Admin sees both
    resp_admin = client_a.get(url)
    assert resp_admin.status_code == 200
    assert document_saved_search.name in resp_admin.content.decode()
    assert private_search.name in resp_admin.content.decode()

    # Member user does not see admin's private search
    resp_member = member_client.get(url)
    assert resp_member.status_code == 200
    assert document_saved_search.name in resp_member.content.decode()
    assert private_search.name not in resp_member.content.decode()

    # Filter by visibility
    resp_vis = client_a.get(url, {"visibility": "public"})
    assert resp_vis.status_code == 200
    assert document_saved_search.name in resp_vis.content.decode()

    # Filter by department
    resp_dept = client_a.get(url, {"department": str(dept.pk)})
    assert resp_dept.status_code == 200
    assert private_search.name in resp_dept.content.decode()

    # Filter by status
    resp_status = client_a.get(url, {"status": "inactive"})
    assert resp_status.status_code == 200
    assert private_search.name in resp_status.content.decode()

    # Filter by pinned
    resp_pinned = client_a.get(url, {"is_pinned": "1"})
    assert resp_pinned.status_code == 200
    assert document_saved_search.name in resp_pinned.content.decode()


@pytest.mark.django_db
def test_search_discovery_saved_search_create_flow(client_a, tenant_a, admin_user):
    """Test document_saved_search_create GET and POST flows."""
    url = reverse("documents:document_saved_search_create")

    # GET
    resp_get = client_a.get(url, {"query_text": "audit compliance"})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # POST valid
    post_data = {
        "name": "Audit Compliance Search",
        "description": "Monitors all compliance documents",
        "visibility": "public",
        "query_text": "compliance",
        "filters_json": '{"status": "published"}',
        "facet_filters_json": '{"classification": ["internal"]}',
        "sort_by": "updated_at_desc",
        "sort_order": "desc",
        "is_pinned": True,
        "is_active": True,
    }
    resp_post = client_a.post(url, data=post_data)
    assert resp_post.status_code == 302

    created = DocumentSavedSearch.objects.filter(tenant=tenant_a, name="Audit Compliance Search").first()
    assert created is not None
    assert created.owner == admin_user
    assert created.is_pinned is True
    assert resp_post.url == reverse("documents:document_saved_search_detail", args=[created.pk])

    # Verify audit log
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_search_discovery_saved_search_create_post_invalid(client_a):
    """Test document_saved_search_create with missing name returns 200 with form errors."""
    url = reverse("documents:document_saved_search_create")
    resp = client_a.post(url, data={"name": "", "visibility": "public"})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_search_discovery_saved_search_detail_views(
    client_a, member_client, tenant_a, admin_user, member_user, document_saved_search
):
    """Test document_saved_search_detail rendering and permission enforcement."""
    url = reverse("documents:document_saved_search_detail", args=[document_saved_search.pk])

    # Owner / Admin can view public saved search
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["saved_search"] == document_saved_search
    assert "parsed_filters" in resp.context
    assert "parsed_facet_filters" in resp.context

    # Private saved search permissions
    private_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        owner=admin_user,
        name="Private Executive Inquiries",
        visibility="private",
    )
    priv_url = reverse("documents:document_saved_search_detail", args=[private_search.pk])

    # Non-owner non-admin member is forbidden (403)
    resp_member = member_client.get(priv_url)
    assert resp_member.status_code == 403

    # Admin can view
    resp_priv_admin = client_a.get(priv_url)
    assert resp_priv_admin.status_code == 200


@pytest.mark.django_db
def test_search_discovery_saved_search_edit_views(
    client_a, member_client, tenant_a, admin_user, member_user, document_saved_search
):
    """Test document_saved_search_edit GET, POST, and permission boundaries."""
    url = reverse("documents:document_saved_search_edit", args=[document_saved_search.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    # POST valid update
    update_data = {
        "name": "Updated Search Name",
        "description": "Refreshed description",
        "visibility": "public",
        "query_text": "updated query",
        "filters_json": '{"status": "approved"}',
        "sort_by": "updated_at_desc",
        "sort_order": "desc",
        "is_active": True,
    }
    resp_post = client_a.post(url, data=update_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("documents:document_saved_search_detail", args=[document_saved_search.pk])

    document_saved_search.refresh_from_db()
    assert document_saved_search.name == "Updated Search Name"

    # Non-owner non-admin attempting edit returns 403
    resp_member = member_client.post(url, data=update_data)
    assert resp_member.status_code == 403


@pytest.mark.django_db
def test_search_discovery_saved_search_delete_views(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Test document_saved_search_delete POST-only enforcement and permission check."""
    saved_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        owner=admin_user,
        name="Temporary Saved Search",
        visibility="public",
    )
    url = reverse("documents:document_saved_search_delete", args=[saved_search.pk])

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # Non-owner non-admin returns 403
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert DocumentSavedSearch.objects.filter(pk=saved_search.pk).exists()

    # Owner / Admin POST deletes
    resp_del = client_a.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("documents:document_saved_search_list")
    assert not DocumentSavedSearch.objects.filter(pk=saved_search.pk).exists()


@pytest.mark.django_db
def test_search_discovery_saved_search_run_view(client_a, member_client, tenant_a, admin_user, member_user):
    """Test document_saved_search_run increments metrics and redirects to search_hub."""
    saved_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        owner=admin_user,
        name="Executable Saved Search",
        query_text="safety",
        filters_json=json.dumps({"document_type": "sop", "status": "published"}),
        visibility="public",
        run_count=0,
    )
    url = reverse("documents:document_saved_search_run", args=[saved_search.pk])

    resp = client_a.get(url)
    assert resp.status_code == 302
    assert reverse("documents:search_hub") in resp.url
    assert "q=safety" in resp.url
    assert "document_type=sop" in resp.url

    saved_search.refresh_from_db()
    assert saved_search.run_count == 1
    assert saved_search.last_run_at is not None

    # Forbidden for unauthorized user on private saved search
    saved_search.visibility = "private"
    saved_search.save(update_fields=["visibility"])
    resp_forbidden = member_client.get(url)
    assert resp_forbidden.status_code == 403


@pytest.mark.django_db
def test_search_discovery_saved_search_toggle_pin(client_a, member_client, tenant_a, admin_user, member_user, document_saved_search):
    """Test document_saved_search_toggle_pin POST-only and referer handling."""
    url = reverse("documents:document_saved_search_toggle_pin", args=[document_saved_search.pk])

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # Non-owner non-admin returns 403
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403

    # Toggle from True to False with valid referer
    initial_pin = document_saved_search.is_pinned
    referer = "http://testserver" + reverse("documents:document_saved_search_list")
    resp_post = client_a.post(url, HTTP_REFERER=referer)
    assert resp_post.status_code == 302
    assert resp_post.url == referer

    document_saved_search.refresh_from_db()
    assert document_saved_search.is_pinned != initial_pin


# ============================================================================
# 3. DocumentSearchAlert View Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_search_alert_list_views(
    client_a, member_client, tenant_a, admin_user, member_user, document_search_alert
):
    """Test document_search_alert_list rendering and user scoping."""
    member_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        owner=member_user,
        name="Member Search",
        visibility="public",
    )
    member_alert = DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=member_search,
        subscriber=member_user,
        frequency="weekly",
        delivery_channel="email",
        status="active",
    )

    url = reverse("documents:document_search_alert_list")

    # Admin sees both alerts
    resp_admin = client_a.get(url)
    assert resp_admin.status_code == 200
    assert "search_alerts" in resp_admin.context
    assert document_search_alert.number in resp_admin.content.decode()
    assert member_alert.number in resp_admin.content.decode()

    # Member user only sees their own alert
    resp_member = member_client.get(url)
    assert resp_member.status_code == 200
    assert member_alert.number in resp_member.content.decode()
    assert document_search_alert.number not in resp_member.content.decode()

    # Filter by frequency and delivery channel
    resp_filtered = client_a.get(url, {"frequency": "weekly", "delivery_channel": "email"})
    assert resp_filtered.status_code == 200
    assert member_alert.number in resp_filtered.content.decode()


@pytest.mark.django_db
def test_search_discovery_search_alert_create_flow(client_a, tenant_a, admin_user, document_saved_search):
    """Test document_search_alert_create GET and POST flows."""
    # Create an un-subscribed saved search
    new_saved_search = DocumentSavedSearch.objects.create(
        tenant=tenant_a,
        owner=admin_user,
        name="Unsubscribed Saved Search",
        visibility="public",
    )
    url = reverse("documents:document_search_alert_create")

    # GET with prefilled saved_search query param
    resp_get = client_a.get(url, {"saved_search": str(new_saved_search.pk)})
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    # POST valid
    post_data = {
        "saved_search": str(new_saved_search.pk),
        "frequency": "weekly",
        "delivery_channel": "email",
        "status": "active",
        "notes": "Notify me for critical updates",
        "is_active": True,
    }
    resp_post = client_a.post(url, data=post_data)
    assert resp_post.status_code == 302

    created = DocumentSearchAlert.objects.filter(tenant=tenant_a, saved_search=new_saved_search).first()
    assert created is not None
    assert created.subscriber == admin_user
    assert resp_post.url == reverse("documents:document_search_alert_detail", args=[created.pk])


@pytest.mark.django_db
def test_search_discovery_search_alert_detail_views(
    client_a, member_client, tenant_a, admin_user, member_user, document_search_alert, document
):
    """Test document_search_alert_detail rendering, matched docs, and permission check."""
    document_search_alert.last_result_ids = json.dumps([document.pk])
    document_search_alert.save(update_fields=["last_result_ids"])

    url = reverse("documents:document_search_alert_detail", args=[document_search_alert.pk])

    # Subscriber / Admin can view
    resp_admin = client_a.get(url)
    assert resp_admin.status_code == 200
    assert resp_admin.context["search_alert"] == document_search_alert
    assert document in resp_admin.context["matched_documents"]

    # Other member cannot view
    resp_member = member_client.get(url)
    assert resp_member.status_code == 403


@pytest.mark.django_db
def test_search_discovery_search_alert_edit_views(
    client_a, member_client, tenant_a, admin_user, member_user, document_search_alert
):
    """Test document_search_alert_edit GET, POST, and permission boundaries."""
    url = reverse("documents:document_search_alert_edit", args=[document_search_alert.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    # POST valid
    post_data = {
        "saved_search": str(document_search_alert.saved_search.pk),
        "frequency": "weekly",
        "delivery_channel": "in_app",
        "status": "active",
        "notes": "Updated alert notes",
        "is_active": True,
    }
    resp_post = client_a.post(url, data=post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("documents:document_search_alert_detail", args=[document_search_alert.pk])

    document_search_alert.refresh_from_db()
    assert document_search_alert.frequency == "weekly"

    # Non-subscriber member returns 403
    resp_member = member_client.post(url, data=post_data)
    assert resp_member.status_code == 403


@pytest.mark.django_db
def test_search_discovery_search_alert_delete_views(
    client_a, member_client, tenant_a, admin_user, member_user, document_saved_search
):
    """Test document_search_alert_delete POST-only and permission check."""
    alert = DocumentSearchAlert.objects.create(
        tenant=tenant_a,
        saved_search=document_saved_search,
        subscriber=admin_user,
        frequency="real_time",
    )
    url = reverse("documents:document_search_alert_delete", args=[alert.pk])

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # Non-subscriber member returns 403
    assert member_client.post(url).status_code == 403
    assert DocumentSearchAlert.objects.filter(pk=alert.pk).exists()

    # Subscriber / Admin deletes
    resp_del = client_a.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("documents:document_search_alert_list")
    assert not DocumentSearchAlert.objects.filter(pk=alert.pk).exists()


@pytest.mark.django_db
def test_search_discovery_search_alert_toggle_active(
    client_a, member_client, tenant_a, admin_user, member_user, document_search_alert
):
    """Test document_search_alert_toggle_active toggles state and updates status."""
    url = reverse("documents:document_search_alert_toggle_active", args=[document_search_alert.pk])

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # Non-subscriber returns 403
    assert member_client.post(url).status_code == 403

    # Toggle from active (True) to paused (False)
    resp = client_a.post(url)
    assert resp.status_code == 302
    document_search_alert.refresh_from_db()
    assert document_search_alert.is_active is False
    assert document_search_alert.status == "paused"

    # Toggle back to active
    client_a.post(url)
    document_search_alert.refresh_from_db()
    assert document_search_alert.is_active is True
    assert document_search_alert.status == "active"


@pytest.mark.django_db
def test_search_discovery_search_alert_run_check(
    client_a, member_client, tenant_a, admin_user, member_user, document_search_alert, document
):
    """Test document_search_alert_run_check executes match query and updates metadata."""
    url = reverse("documents:document_search_alert_run_check", args=[document_search_alert.pk])

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # Non-subscriber returns 403
    assert member_client.post(url).status_code == 403

    # Run check
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("documents:document_search_alert_detail", args=[document_search_alert.pk])

    document_search_alert.refresh_from_db()
    assert document_search_alert.last_checked_at is not None
    assert isinstance(document_search_alert.get_last_result_ids_list(), list)


# ============================================================================
# 4. DocumentSearchSynonym View Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_search_synonym_list_and_filters(client_a, tenant_a, document_search_synonym):
    """Test document_search_synonym_list rendering and filter options."""
    url = reverse("documents:document_search_synonym_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "search_synonyms" in resp.context
    assert document_search_synonym.term in resp.content.decode()

    # Filter by category
    resp_cat = client_a.get(url, {"category": "domain"})
    assert resp_cat.status_code == 200
    assert document_search_synonym.term in resp_cat.content.decode()

    # Filter by search term q
    resp_q = client_a.get(url, {"q": "agreement"})
    assert resp_q.status_code == 200
    assert document_search_synonym.term in resp_q.content.decode()


@pytest.mark.django_db
def test_search_discovery_search_synonym_create_flow(client_a, tenant_a, admin_user):
    """Test document_search_synonym_create GET and POST flows."""
    url = reverse("documents:document_search_synonym_create")

    # GET
    resp_get = client_a.get(url, {"term": "protocol"})
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    # POST valid
    post_data = {
        "term": "protocol",
        "synonyms": "procedure, standard, method",
        "category": "domain",
        "is_bidirectional": True,
        "language": "en",
        "is_active": True,
    }
    resp_post = client_a.post(url, data=post_data)
    assert resp_post.status_code == 302

    created = DocumentSearchSynonym.objects.filter(tenant=tenant_a, term="protocol").first()
    assert created is not None
    assert created.created_by == admin_user
    assert resp_post.url == reverse("documents:document_search_synonym_detail", args=[created.pk])


@pytest.mark.django_db
def test_search_discovery_search_synonym_create_invalid(client_a):
    """Test document_search_synonym_create with invalid data returns 200 with form errors."""
    url = reverse("documents:document_search_synonym_create")
    resp = client_a.post(url, data={"term": "", "synonyms": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_search_discovery_search_synonym_detail_views(client_a, document_search_synonym):
    """Test document_search_synonym_detail renders expanded terms list."""
    url = reverse("documents:document_search_synonym_detail", args=[document_search_synonym.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["search_synonym"] == document_search_synonym
    assert "expanded_terms_list" in resp.context
    assert "contract" in resp.context["expanded_terms_list"]


@pytest.mark.django_db
def test_search_discovery_search_synonym_edit_views(
    client_a, member_client, tenant_a, admin_user, member_user, document_search_synonym
):
    """Test document_search_synonym_edit GET, POST, and permission boundaries."""
    url = reverse("documents:document_search_synonym_edit", args=[document_search_synonym.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    # POST valid
    post_data = {
        "term": "agreement",
        "synonyms": "contract, deal, compact, pact",
        "category": "domain",
        "is_bidirectional": True,
        "language": "en",
        "is_active": True,
    }
    resp_post = client_a.post(url, data=post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("documents:document_search_synonym_detail", args=[document_search_synonym.pk])

    document_search_synonym.refresh_from_db()
    assert "compact" in document_search_synonym.synonyms

    # Non-creator non-admin member returns 403
    resp_member = member_client.post(url, data=post_data)
    assert resp_member.status_code == 403


@pytest.mark.django_db
def test_search_discovery_search_synonym_delete_views(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Test document_search_synonym_delete POST-only and permission check."""
    synonym = DocumentSearchSynonym.objects.create(
        tenant=tenant_a,
        term="brief",
        synonyms="summary, outline",
        created_by=admin_user,
    )
    url = reverse("documents:document_search_synonym_delete", args=[synonym.pk])

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # Non-creator non-admin member returns 403
    assert member_client.post(url).status_code == 403
    assert DocumentSearchSynonym.objects.filter(pk=synonym.pk).exists()

    # Creator / Admin deletes
    resp_del = client_a.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("documents:document_search_synonym_list")
    assert not DocumentSearchSynonym.objects.filter(pk=synonym.pk).exists()


@pytest.mark.django_db
def test_search_discovery_search_synonym_toggle_active(
    client_a, member_client, tenant_a, admin_user, member_user, document_search_synonym
):
    """Test document_search_synonym_toggle_active toggles active status."""
    url = reverse("documents:document_search_synonym_toggle_active", args=[document_search_synonym.pk])

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # Non-creator returns 403
    assert member_client.post(url).status_code == 403

    # Toggle active
    initial_status = document_search_synonym.is_active
    resp = client_a.post(url)
    assert resp.status_code == 302

    document_search_synonym.refresh_from_db()
    assert document_search_synonym.is_active != initial_status


# ============================================================================
# 5. DocumentSearchQueryLog View Tests
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_query_log_list_admin_access(client_a, tenant_a, document_search_query_log):
    """Test document_search_query_log_list renders 200 OK for tenant admin with stats."""
    url = reverse("documents:document_search_query_log_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "query_logs" in resp.context
    assert "total_count" in resp.context
    assert "zero_result_count" in resp.context
    assert document_search_query_log.query_text in resp.content.decode()

    # Filters
    resp_source = client_a.get(url, {"search_source": "search_hub"})
    assert resp_source.status_code == 200

    resp_zero = client_a.get(url, {"zero_result": "0"})
    assert resp_zero.status_code == 200


@pytest.mark.django_db
def test_search_discovery_query_log_list_non_admin_forbidden(member_client):
    """Test non-admin member is forbidden (403) from accessing query logs."""
    url = reverse("documents:document_search_query_log_list")
    resp = member_client.get(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_search_discovery_query_log_detail_views(client_a, member_client, document_search_query_log):
    """Test document_search_query_log_detail renders for admin and forbids non-admin."""
    url = reverse("documents:document_search_query_log_detail", args=[document_search_query_log.pk])

    # Admin access
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["query_log"] == document_search_query_log
    assert "parsed_filters" in resp.context

    # Non-admin access
    assert member_client.get(url).status_code == 403


@pytest.mark.django_db
def test_search_discovery_query_log_delete_views(client_a, member_client, tenant_a, admin_user):
    """Test document_search_query_log_delete POST-only and admin restriction."""
    log = DocumentSearchQueryLog.objects.create(
        tenant=tenant_a,
        query_text="obsolete query",
        user=admin_user,
    )
    url = reverse("documents:document_search_query_log_delete", args=[log.pk])

    # GET returns 405
    assert client_a.get(url).status_code == 405

    # Non-admin member returns 403
    assert member_client.post(url).status_code == 403
    assert DocumentSearchQueryLog.objects.filter(pk=log.pk).exists()

    # Admin deletes
    resp_del = client_a.post(url)
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("documents:document_search_query_log_list")
    assert not DocumentSearchQueryLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_search_discovery_analytics_dashboard_admin_access(
    client_a, member_client, tenant_a, admin_user, document_search_query_log
):
    """Test document_search_analytics aggregates KPIs, popular queries, and zero-result queries."""
    # Create an additional zero result query log
    DocumentSearchQueryLog.objects.create(
        tenant=tenant_a,
        query_text="missing technical spec",
        is_zero_result=True,
        results_count=0,
        execution_time_ms=25.0,
        user=admin_user,
    )

    url = reverse("documents:document_search_analytics")

    # Non-admin member access returns 403
    assert member_client.get(url).status_code == 403

    # Admin access
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "total_searches" in resp.context
    assert resp.context["total_searches"] >= 2
    assert "zero_result_searches" in resp.context
    assert "zero_result_rate" in resp.context
    assert "avg_latency_ms" in resp.context
    assert "top_queries" in resp.context
    assert "zero_result_queries" in resp.context
    assert "source_breakdown" in resp.context


# ============================================================================
# 6. Edge Cases, Negative Parameters & Pagination Guards
# ============================================================================

@pytest.mark.django_db
def test_search_discovery_pagination_out_of_bounds(client_a, tenant_a, document):
    """Test out of bounds page numbers return the last valid page without 500 error."""
    endpoints = [
        reverse("documents:search_hub"),
        reverse("documents:document_saved_search_list"),
        reverse("documents:document_search_alert_list"),
        reverse("documents:document_search_synonym_list"),
        reverse("documents:document_search_query_log_list"),
    ]
    for url in endpoints:
        resp = client_a.get(url, {"page": "99999"})
        assert resp.status_code == 200, f"Failed on {url} with page=99999"


@pytest.mark.django_db
def test_search_discovery_negative_and_junk_parameters_graceful(client_a, tenant_a):
    """Test junk parameters and corrupted filters do not cause 500 crashes."""
    # SearchHub with junk parameters
    junk_search_params = {
        "folder": "invalid_folder_pk",
        "author": "not_an_id",
        "date_from": "not-a-valid-date",
        "date_to": "garbage-date",
        "classification": "unknown_class",
        "status": "corrupt_status",
        "sort_by": "unsupported_sort_order",
    }
    resp = client_a.get(reverse("documents:search_hub"), junk_search_params)
    assert resp.status_code == 200

    # Saved searches with non-numeric department
    resp_saved = client_a.get(
        reverse("documents:document_saved_search_list"),
        {"department": "bad_pk", "visibility": "illegal_vis", "status": "junk"},
    )
    assert resp_saved.status_code == 200

    # Alerts with junk filter
    resp_alerts = client_a.get(
        reverse("documents:document_search_alert_list"),
        {"frequency": "hourly", "delivery_channel": "satellite"},
    )
    assert resp_alerts.status_code == 200

    # Synonyms with junk filter
    resp_synonyms = client_a.get(
        reverse("documents:document_search_synonym_list"),
        {"category": "fantasy", "language": "elvish"},
    )
    assert resp_synonyms.status_code == 200

    # Query logs with junk user id
    resp_logs = client_a.get(
        reverse("documents:document_search_query_log_list"),
        {"user": "non_numeric_user_id", "zero_result": "maybe"},
    )
    assert resp_logs.status_code == 200


@pytest.mark.django_db
def test_search_discovery_unauthenticated_requests_redirect(
    client, document_saved_search, document_search_alert, document_search_synonym, document_search_query_log, document
):
    """Test that all search & discovery views redirect unauthenticated requests to login."""
    endpoints = [
        reverse("documents:search_hub"),
        reverse("documents:search_export_csv"),
        reverse("documents:search_click_track", args=[document.pk]),
        reverse("documents:document_saved_search_list"),
        reverse("documents:document_saved_search_create"),
        reverse("documents:document_saved_search_detail", args=[document_saved_search.pk]),
        reverse("documents:document_saved_search_edit", args=[document_saved_search.pk]),
        reverse("documents:document_search_alert_list"),
        reverse("documents:document_search_alert_create"),
        reverse("documents:document_search_alert_detail", args=[document_search_alert.pk]),
        reverse("documents:document_search_alert_edit", args=[document_search_alert.pk]),
        reverse("documents:document_search_synonym_list"),
        reverse("documents:document_search_synonym_create"),
        reverse("documents:document_search_synonym_detail", args=[document_search_synonym.pk]),
        reverse("documents:document_search_synonym_edit", args=[document_search_synonym.pk]),
        reverse("documents:document_search_query_log_list"),
        reverse("documents:document_search_query_log_detail", args=[document_search_query_log.pk]),
        reverse("documents:document_search_analytics"),
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"URL {url} did not redirect (status {resp.status_code})"
        assert "/login/" in resp.url or "/login/" in resp.headers.get("Location", "")
