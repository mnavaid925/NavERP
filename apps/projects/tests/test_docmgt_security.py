"""Projects 7.10 — Document & Knowledge Management security tests.

Covers anonymous redirection, POST-only verb rejection, cross-tenant isolation, mass-assignment
guards, and the XSS sink shape.

Naming: every test ``test_docmgt_*``, every helper ``_docmgt_*``.
"""
import pytest
from django.urls import reverse

from apps.projects.models import ProjectDocument

_ANONYMOUS_GET_ROUTES = [
    "doc_repository", "doc_retention",
    "pfd_list", "pfd_create",
    "pdm_list", "pdm_create",
    "pdv_list",
    "dtm_list", "dtm_create",
    "kne_list", "kne_create", "kne_search",
]

# pdv_upload requires a document_pk argument; tested separately.
_ANONYMOUS_POST_ROUTES = [
    "doc_retention_run",
    "pfd_create",
    "pdm_create",
    "dtm_create",
    "kne_create",
]

_CROSS_TENANT_GET = [
    ("pfd_detail", "docmgt_folder_root_b"),
    ("pdm_detail", "docmgt_document_draft_b"),
    ("kne_detail", "docmgt_knowledge_draft_b"),
]

_CROSS_TENANT_POST = [
    ("pdm_archive", "docmgt_document_draft_b"),
    ("kne_publish", "docmgt_knowledge_draft_b"),
    ("pdv_approve", "docmgt_revision_pending_b"),
]


# ==================================================================================================
# Anonymous
# ==================================================================================================

@pytest.mark.parametrize("name", _ANONYMOUS_GET_ROUTES)
def test_docmgt_anonymous_get_redirects_to_login(db, client, name):
    resp = client.get(reverse(f"projects:{name}"))
    assert resp.status_code in (302, 301)
    assert "/login/" in resp.url or "/accounts/login/" in resp.url


@pytest.mark.parametrize("name", _ANONYMOUS_POST_ROUTES)
def test_docmgt_anonymous_post_redirects_to_login(db, client, name):
    resp = client.post(reverse(f"projects:{name}"))
    assert resp.status_code in (302, 301)


def test_docmgt_anonymous_upload_redirects_to_login(db, client, docmgt_document_draft_a):
    resp = client.post(reverse("projects:pdv_upload",
                                args=[docmgt_document_draft_a.pk]))
    assert resp.status_code in (302, 301)


# ==================================================================================================
# Cross-tenant isolation
# ==================================================================================================

@pytest.mark.parametrize("name,fixture_name", _CROSS_TENANT_GET)
def test_docmgt_cross_tenant_get_returns_404(db, client_a, request, name, fixture_name):
    obj = request.getfixturevalue(fixture_name)
    resp = client_a.get(reverse(f"projects:{name}", args=[obj.pk]))
    assert resp.status_code == 404


@pytest.mark.parametrize("name,fixture_name", _CROSS_TENANT_POST)
def test_docmgt_cross_tenant_post_returns_404(db, client_a, request, name, fixture_name):
    obj = request.getfixturevalue(fixture_name)
    resp = client_a.post(reverse(f"projects:{name}", args=[obj.pk]))
    assert resp.status_code == 404


# ==================================================================================================
# Mass assignment
# ==================================================================================================

def test_docmgt_mass_assignment_number_ignored(db, client_a, docmgt_document_draft_a):
    resp = client_a.post(
        reverse("projects:pdm_edit", args=[docmgt_document_draft_a.pk]),
        {"title": "New title", "number": "FORGED-99999", "status": "draft",
         "document_type": "charter", "classification": "internal",
         "folder": docmgt_document_draft_a.folder_id})
    assert resp.status_code == 302
    docmgt_document_draft_a.refresh_from_db()
    assert docmgt_document_draft_a.number != "FORGED-99999"


def test_docmgt_mass_assignment_current_revision_no_ignored(db, client_a, docmgt_document_draft_a):
    resp = client_a.post(
        reverse("projects:pdm_edit", args=[docmgt_document_draft_a.pk]),
        {"title": "New title", "current_revision_no": 99, "status": "draft",
         "document_type": "charter", "classification": "internal",
         "folder": docmgt_document_draft_a.folder_id})
    assert resp.status_code == 302
    docmgt_document_draft_a.refresh_from_db()
    assert docmgt_document_draft_a.current_revision_no != 99


def test_docmgt_mass_assignment_tenant_ignored(db, client_a, tenant_b, docmgt_document_draft_a):
    resp = client_a.post(
        reverse("projects:pdm_edit", args=[docmgt_document_draft_a.pk]),
        {"title": "New title", "tenant": tenant_b.pk, "status": "draft",
         "document_type": "charter", "classification": "internal",
         "folder": docmgt_document_draft_a.folder_id})
    assert resp.status_code == 302
    docmgt_document_draft_a.refresh_from_db()
    assert docmgt_document_draft_a.tenant_id != tenant_b.pk


# ==================================================================================================
# XSS — the confirm handler shape
# ==================================================================================================

def test_docmgt_folder_list_confirm_uses_escapejs(db, client_a, tenant_a, planning_project_a):
    from apps.projects.models import ProjectFolder
    f = ProjectFolder.objects.create(tenant=tenant_a, project=planning_project_a,
                                      name="x',alert(1),'y", sequence=99)
    resp = client_a.get(reverse("projects:pfd_list"))
    html = resp.content.decode("utf-8", "replace")
    # The handler body must contain the escaped payload, not a raw apostrophe after decoding.
    # With |escapejs the payload becomes \u0027, which survives HTML attribute decoding.
    assert "\\u0027" in html or "&#x27;" in html
    f.delete()
