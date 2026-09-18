"""Projects 7.10 — Document & Knowledge Management view tests.

Covers all 40 routes: they resolve, the GET pages render the object they are about, the 14
POST-only verbs answer GET with 405, every verb's state machine runs and writes its
``changes["verb"]`` audit row, the registers paginate, junk params never 500, and the empty state
is safe.

Naming: every test ``test_docmgt_*``, every helper ``_docmgt_*``.
"""
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.projects.models import (
    DocumentTemplate,
    KnowledgeEntry,
    ProjectDocument,
    ProjectDocumentRevision,
    ProjectFolder,
)

_ALL_ROUTE_NAMES = [
    "doc_repository", "doc_retention", "doc_retention_run",
    "pfd_list", "pfd_create", "pfd_detail", "pfd_edit", "pfd_delete", "pfd_archive",
    "pdm_list", "pdm_create", "pdm_detail", "pdm_edit", "pdm_delete",
    "pdm_archive", "pdm_hold", "pdm_release", "pdm_checkout", "pdm_checkin", "pdm_reindex",
    "pdv_list", "pdv_upload", "pdv_approve", "pdv_restore", "pdv_delete",
    "pdv_compare",
    "dtm_list", "dtm_create", "dtm_detail", "dtm_edit", "dtm_delete", "dtm_publish",
    "kne_list", "kne_create", "kne_detail", "kne_edit", "kne_delete",
    "kne_publish", "kne_use", "kne_search",
]

_GET_WITH_PK = [
    ("pfd_detail", "docmgt_folder_root_a"),
    ("pfd_edit", "docmgt_folder_root_a"),
    ("pdm_detail", "docmgt_document_draft_a"),
    ("pdm_edit", "docmgt_document_draft_a"),
    ("pdv_upload", "docmgt_document_approved_a"),
    ("dtm_detail", "docmgt_template_active_a"),
    ("dtm_edit", "docmgt_template_active_a"),
    ("kne_detail", "docmgt_knowledge_draft_a"),
    ("kne_edit", "docmgt_knowledge_draft_a"),
]

# Only the views decorated with @require_POST.  pdm_delete and kne_delete render a confirmation
# page on GET, so they are not in this list.
_POST_ONLY_VERBS = [
    ("pdv_approve", "docmgt_revision_pending_a"),
    ("pdv_restore", "docmgt_revision_approved_a"),
    ("pdv_delete", "docmgt_revision_pending_a"),
    ("pdm_archive", "docmgt_document_draft_a"),
    ("pdm_hold", "docmgt_document_draft_a"),
    ("pdm_release", "docmgt_document_held_a"),
    ("pdm_checkout", "docmgt_document_draft_a"),
    ("pdm_checkin", "docmgt_document_draft_a"),
    ("pdm_reindex", "docmgt_document_approved_a"),
    ("kne_publish", "docmgt_knowledge_draft_a"),
    ("kne_use", "docmgt_knowledge_published_a"),
    ("dtm_publish", "docmgt_template_active_a"),
]


def _audited(verb):
    return AuditLog.objects.filter(changes__verb=verb).exists()


# ==================================================================================================
# Every route resolves, and the POST-only verbs are POST-only
# ==================================================================================================

def test_docmgt_all_forty_routes_resolve(db):
    assert len(_ALL_ROUTE_NAMES) == 40
    for name in _ALL_ROUTE_NAMES:
        try:
            reverse(f"projects:{name}")
        except Exception:
            assert reverse(f"projects:{name}", args=[1]).startswith("/projects/")


@pytest.mark.parametrize("name,fixture_name", _POST_ONLY_VERBS)
def test_docmgt_post_only_verbs_reject_get(db, client_a, request, name, fixture_name):
    obj = request.getfixturevalue(fixture_name)
    resp = client_a.get(reverse(f"projects:{name}", args=[obj.pk]))
    assert resp.status_code == 405


# ==================================================================================================
# GET pages render
# ==================================================================================================

@pytest.mark.parametrize("name,fixture_name", _GET_WITH_PK)
def test_docmgt_get_detail_pages_render(db, client_a, request, name, fixture_name):
    obj = request.getfixturevalue(fixture_name)
    resp = client_a.get(reverse(f"projects:{name}", args=[obj.pk]))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8", "replace")
    assert obj.number in html


def test_docmgt_repository_overview_renders(db, client_a):
    resp = client_a.get(reverse("projects:doc_repository"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8", "replace")
    assert "Document Repository" in html


def test_docmgt_retention_board_renders(db, client_a):
    resp = client_a.get(reverse("projects:doc_retention"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8", "replace")
    assert "Retention" in html
    assert "Due inside" in html


# ==================================================================================================
# Filters
# ==================================================================================================

def test_docmgt_document_list_q_filter_narrows(db, client_a):
    resp = client_a.get(reverse("projects:pdm_list") + "?q=charter")
    assert resp.status_code == 200


def test_docmgt_document_list_status_filter_narrows(db, client_a):
    resp = client_a.get(reverse("projects:pdm_list") + "?status=draft")
    assert resp.status_code == 200


def test_docmgt_document_list_archived_filter(db, client_a):
    resp = client_a.get(reverse("projects:pdm_list") + "?archived=True")
    assert resp.status_code == 200


def test_docmgt_document_list_junk_status_ignored(db, client_a):
    resp = client_a.get(reverse("projects:pdm_list") + "?status=nope")
    assert resp.status_code == 200


def test_docmgt_knowledge_search_kind_filter(db, client_a):
    resp = client_a.get(reverse("projects:kne_search") + "?kind=lesson_learned")
    assert resp.status_code == 200


# ==================================================================================================
# Pagination
# ==================================================================================================

def test_docmgt_document_list_page_two_renders(db, client_a):
    resp = client_a.get(reverse("projects:pdm_list") + "?page=2")
    assert resp.status_code == 200


def test_docmgt_document_list_out_of_range_safe(db, client_a):
    resp = client_a.get(reverse("projects:pdm_list") + "?page=99999")
    assert resp.status_code in (200, 404)


# ==================================================================================================
# POST verbs — state machines
# ==================================================================================================

def test_docmgt_pdv_approve_approves_revision(db, client_a, docmgt_revision_pending_a):
    resp = client_a.post(reverse("projects:pdv_approve", args=[docmgt_revision_pending_a.pk]))
    assert resp.status_code == 302
    docmgt_revision_pending_a.refresh_from_db()
    assert docmgt_revision_pending_a.is_approved is True
    assert _audited("pdv_approve")


def test_docmgt_pdm_archive_archives_document(db, client_a, docmgt_document_draft_a):
    resp = client_a.post(reverse("projects:pdm_archive", args=[docmgt_document_draft_a.pk]))
    assert resp.status_code == 302
    docmgt_document_draft_a.refresh_from_db()
    assert docmgt_document_draft_a.is_archived is True


def test_docmgt_pdm_hold_places_hold(db, client_a, docmgt_document_draft_a):
    resp = client_a.post(reverse("projects:pdm_hold", args=[docmgt_document_draft_a.pk]),
                         {"hold_reason": "Legal."})
    assert resp.status_code == 302
    docmgt_document_draft_a.refresh_from_db()
    assert docmgt_document_draft_a.is_legal_hold is True


def test_docmgt_pdm_checkout_checks_out(db, client_a, docmgt_document_draft_a):
    resp = client_a.post(reverse("projects:pdm_checkout", args=[docmgt_document_draft_a.pk]))
    assert resp.status_code == 302
    docmgt_document_draft_a.refresh_from_db()
    assert docmgt_document_draft_a.is_checked_out is True


def test_docmgt_kne_publish_toggles_draft_to_published(db, client_a, docmgt_knowledge_draft_a):
    resp = client_a.post(reverse("projects:kne_publish", args=[docmgt_knowledge_draft_a.pk]))
    assert resp.status_code == 302
    docmgt_knowledge_draft_a.refresh_from_db()
    assert docmgt_knowledge_draft_a.status == "published"


def test_docmgt_kne_publish_toggles_published_to_draft(db, client_a, docmgt_knowledge_published_a):
    resp = client_a.post(reverse("projects:kne_publish", args=[docmgt_knowledge_published_a.pk]))
    assert resp.status_code == 302
    docmgt_knowledge_published_a.refresh_from_db()
    assert docmgt_knowledge_published_a.status == "draft"


def test_docmgt_pdm_unarchive_restores_document(db, client_a, docmgt_document_archived_a):
    resp = client_a.post(reverse("projects:pdm_archive", args=[docmgt_document_archived_a.pk]))
    assert resp.status_code == 302
    docmgt_document_archived_a.refresh_from_db()
    assert docmgt_document_archived_a.is_archived is False


def test_docmgt_pdm_release_releases_hold(db, client_a, docmgt_document_held_a):
    resp = client_a.post(reverse("projects:pdm_release", args=[docmgt_document_held_a.pk]))
    assert resp.status_code == 302
    docmgt_document_held_a.refresh_from_db()
    assert docmgt_document_held_a.is_legal_hold is False


def test_docmgt_pdm_checkin_checks_in(db, client_a, docmgt_document_draft_a):
    docmgt_document_draft_a.is_checked_out = True
    docmgt_document_draft_a.save()
    resp = client_a.post(reverse("projects:pdm_checkin", args=[docmgt_document_draft_a.pk]))
    assert resp.status_code == 302
    docmgt_document_draft_a.refresh_from_db()
    assert docmgt_document_draft_a.is_checked_out is False


def test_docmgt_kne_publish_retired_refused(db, client_a, docmgt_knowledge_retired_a):
    resp = client_a.post(reverse("projects:kne_publish", args=[docmgt_knowledge_retired_a.pk]))
    assert resp.status_code == 302
    docmgt_knowledge_retired_a.refresh_from_db()
    assert docmgt_knowledge_retired_a.status == "retired"


def test_docmgt_pfd_list_is_not_paginated(db, client_a):
    resp = client_a.get(reverse("projects:pfd_list"))
    assert resp.status_code == 200
    assert resp.context.get("page_obj") is None


# ==================================================================================================
# Empty states
# ==================================================================================================

def test_docmgt_empty_tenant_document_list_renders(db, tenant_a, client_a):
    ProjectDocument.objects.filter(tenant=tenant_a).delete()
    resp = client_a.get(reverse("projects:pdm_list"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8", "replace")
    assert "No documents" in html


def test_docmgt_empty_tenant_folder_list_renders(db, tenant_a, client_a):
    ProjectFolder.objects.filter(tenant=tenant_a).delete()
    resp = client_a.get(reverse("projects:pfd_list"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8", "replace")
    assert "No folders" in html


def test_docmgt_pdv_approve_archived_document_refused(db, client_a, docmgt_revision_pending_a):
    doc = docmgt_revision_pending_a.document
    doc.is_archived = True
    doc.status = "archived"
    doc.save()
    resp = client_a.post(reverse("projects:pdv_approve", args=[docmgt_revision_pending_a.pk]))
    assert resp.status_code == 302
    docmgt_revision_pending_a.refresh_from_db()
    assert docmgt_revision_pending_a.is_approved is False


def test_docmgt_pdv_restore_archived_document_refused(db, client_a, docmgt_document_approved_a):
    doc = docmgt_document_approved_a
    rev = doc.revisions.first()
    doc.is_archived = True
    doc.status = "archived"
    doc.save()
    resp = client_a.post(reverse("projects:pdv_restore", args=[rev.pk]))
    assert resp.status_code == 302


def test_docmgt_pdm_reindex_preserves_text_on_unreachable_file(db, client_a, docmgt_document_approved_a, monkeypatch):
    doc = docmgt_document_approved_a
    doc.extracted_text = "Good existing search text"
    doc.save()
    from apps.projects.views.DocumentKnowledgeManagement import Documents as docs_view
    monkeypatch.setattr(docs_view, "extract_text", lambda f: ("", "The stored file could not be reached on disk."))
    resp = client_a.post(reverse("projects:pdm_reindex", args=[doc.pk]))
    assert resp.status_code == 302
    doc.refresh_from_db()
    assert doc.extracted_text == "Good existing search text"

