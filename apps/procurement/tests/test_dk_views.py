"""Procurement 6.19 - Document & Knowledge Management VIEW tests.

The HTTP layer of the sub-module: 33 routes, their templates, **every context key the contract
pins**, the filters, the pagination, the verbs' state machines and the measured query budgets.
Model invariants belong to ``test_dk_models.py`` and form validation to ``test_dk_forms.py``;
tenancy/IDOR, the classification read rule and the admin-gating matrix belong to
``test_dk_security.py``. Where a behaviour is genuinely both - a verb's happy path needs an
administrator - the FUNCTIONAL half is here and the authorization half is there.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success (L8), so every page here asserts CONTENT - the seeded row's own ``PDOC-``/``PPOL-``/
  ``PKR-`` number in the body - and then asserts the context key by name. The keys three Phase 5
  fixes changed are pinned explicitly: ``classification_note`` on all four document views,
  ``can_release`` on ``pdocument_detail``, and the ABSENCE of ``is_review_due`` from
  ``ppolicy_detail`` and ``knowledgeresource_detail`` (M15).
* **A filter that silently empties a register.** Every filter control on all four registers is
  compared against the ORM's own answer for the same narrowing, so a control that does nothing
  and a control that returns everything both fail. Junk values (``?page=abc``, ``?page=-1``,
  ``?supplier=NaN``, ``?status=<script>``) must return the FULL register at 200, never a 500 and
  never an empty page (L9/L11).
* **A verb that writes when it should refuse.** Each POST verb is exercised on both sides: the
  happy path changes exactly what it should, and every refusal path returns a message and leaves
  the row byte-for-byte as it was. The three that matter most are the chain rules - upload never
  moves the pointer, approve refuses ``revision_no <= current_revision_no``, delete refuses an
  approved or current revision.
* **An N+1 that comes back.** The measured budgets from the test contract are asserted as
  ``django_assert_max_num_queries`` ceilings, and each register additionally proves its cost is
  FLAT in the row count - ten more rows, same query count. The chained ``__str__`` FK hops
  (``revision.document.number``, ``policy.threshold_currency.code``) are exactly what the
  ``select_related`` calls are there to absorb.

Determinism (L16): every date basis is ``timezone.localdate()`` and every datetime basis is
``timezone.now()`` - the same bases the view code uses. ``datetime.date.today()`` never appears.
Every stored byte lands under ``dk_media_root`` (pytest's ``tmp_path``); nothing touches the
network.
"""
import datetime

import pytest
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.procurement.models import (
    KnowledgeResource,
    ProcurementAlert,
    ProcurementDocument,
    ProcurementDocumentRevision,
    ProcurementPolicy,
)
from apps.procurement.models.DocumentKnowledgeManagement.Documents import (
    EXPIRY_FILTER_CHOICES, REINDEX_ROW_CAP)
from apps.procurement.models.DocumentKnowledgeManagement.KnowledgeResources import (
    FEATURED_CAP, LIBRARY_NOTE)
from apps.procurement.models.DocumentKnowledgeManagement.Policies import ADVISORY_NOTE
from apps.procurement.tests.conftest import (
    _dk_approve, _dk_document, _dk_documents, _dk_policy, _dk_resource, _dk_revision)
from apps.procurement.views.DocumentKnowledgeManagement.Documents import (
    DETAIL_FAN_OUT_CAP, FILE_TEXT_SEARCH_MIN_CHARS, REINDEX_TIME_BUDGET_SECONDS, SEARCH_NOTE)
from apps.procurement.views.DocumentKnowledgeManagement.KnowledgeResources import (
    FEATURED_CHOICES, USAGE_COUNT_CEILING)
from apps.procurement.views.DocumentKnowledgeManagement.Policies import (
    REVIEW_CHOICES, SUPERSEDED_BY_CAP)
from apps.procurement.views.DocumentKnowledgeManagement.Revisions import (
    APPROVAL_CHOICES, DOCUMENT_FACET_CAP, REVISION_NOTE, UPLOAD_NOTE)
from apps.procurement.views._helpers import CLASSIFICATION_NOTE

pytestmark = pytest.mark.django_db


# =================================================================================================
# Module-level helpers - all ``_dk_*`` / ``_DK_*`` so the next sub-module appending near this file
# cannot shadow them and so a failure names its own lane (L47). Record factories come from
# conftest, which OWNS them; only what conftest does not provide is built here.
# =================================================================================================

#: Every url name this sub-module owns, grouped by entity. The count is the contract's headline
#: number and ``pdocrevision_download`` is the route C1 added - a stale build contract lists 32.
_DK_LIST_ROUTES = ("pdocument_list", "pdocrevision_list", "ppolicy_list",
                   "knowledgeresource_list")
_DK_DOCUMENT_ROUTES = (
    "pdocument_list", "pdocument_create", "pdocument_reindex", "pdocument_run_reminders",
    "pdocument_detail", "pdocument_edit", "pdocument_delete", "pdocument_checkout",
    "pdocument_release", "pdocument_activate", "pdocument_supersede", "pdocument_archive",
    "pdocument_revision_upload")
_DK_REVISION_ROUTES = ("pdocrevision_list", "pdocrevision_detail", "pdocrevision_download",
                       "pdocrevision_approve", "pdocrevision_delete")
_DK_POLICY_ROUTES = ("ppolicy_list", "ppolicy_create", "ppolicy_detail", "ppolicy_edit",
                     "ppolicy_delete", "ppolicy_publish", "ppolicy_archive")
_DK_RESOURCE_ROUTES = ("knowledgeresource_list", "knowledgeresource_create",
                       "knowledgeresource_detail", "knowledgeresource_edit",
                       "knowledgeresource_delete", "knowledgeresource_publish",
                       "knowledgeresource_archive", "knowledgeresource_use")
_DK_ALL_ROUTES = (_DK_DOCUMENT_ROUTES + _DK_REVISION_ROUTES + _DK_POLICY_ROUTES
                  + _DK_RESOURCE_ROUTES)

#: The POST-only verbs. A GET on any of these is 405 for a user who passes the decorators above
#: ``@require_POST`` - which for the five admin-gated document verbs means an ADMIN GET.
_DK_POST_ONLY_PK_VERBS = (
    "pdocument_delete", "pdocument_checkout", "pdocument_release", "pdocument_activate",
    "pdocument_supersede", "pdocument_archive", "pdocrevision_approve", "pdocrevision_delete",
    "ppolicy_delete", "ppolicy_publish", "ppolicy_archive", "knowledgeresource_delete",
    "knowledgeresource_publish", "knowledgeresource_archive", "knowledgeresource_use")

#: ``crud_list``'s page size. Pinned here so a change to the helper fails the pagination tests
#: rather than quietly re-shaping every register in the app.
_DK_PER_PAGE = 15


def _dk_url(name, *args):
    return reverse(f"procurement:{name}", args=args)


def _dk_get(client, name, *args, **params):
    """GET one 6.19 route with an optional query string."""
    return client.get(_dk_url(name, *args), params)


def _dk_post(client, name, *args, data=None, follow=False):
    """POST one 6.19 route. CSRF is off on the ordinary test client - the enforced-CSRF pair
    lives in the security lane."""
    return client.post(_dk_url(name, *args), data or {}, follow=follow)


def _dk_messages(response):
    """Every message queued on the request that produced ``response``, as plain strings.

    Read off the request rather than the rendered page: the verbs redirect, so nothing has
    rendered - and therefore consumed - the storage yet.
    """
    return [str(message) for message in get_messages(response.wsgi_request)]


def _dk_said(response, fragment):
    """True when any queued message contains ``fragment``.

    Assert SUBSTRINGS without the em dash: several 6.19 messages carry U+2014, and matching a
    whole sentence turns a copy edit into a failing test.
    """
    return any(fragment in message for message in _dk_messages(response))


def _dk_pks(response, key="object_list"):
    """The primary keys the page actually rendered, in order."""
    return [row.pk for row in response.context[key]]


def _dk_body(response):
    return response.content.decode()


def _dk_second_member(tenant, django_user_model, username="member2_acme"):
    """A SECOND non-administrator in the workspace.

    The root conftest offers one member (``member_user``), and the release refusal needs somebody
    who is neither the holder nor an administrator - the only party the verb turns away.
    """
    return django_user_model.objects.create_user(
        email=f"{username}@acme.com", username=username, password="TestPass123!",
        tenant=tenant, is_tenant_admin=False)


def _dk_txt(name="revision.txt", body=b"Uploaded revision body with a beacontoken inside."):
    return SimpleUploadedFile(name, body, content_type="text/plain")


def _dk_reset_pointer(document, revision_no):
    """Move ``current_revision_no`` with a queryset UPDATE - never a model save.

    The pointer is ``editable=False`` and is moved by exactly one production path (approve). A
    test that needs a particular pointer state builds it in SQL so nothing here can be mistaken
    for a supported write.
    """
    ProcurementDocument.objects.filter(pk=document.pk).update(current_revision_no=revision_no)
    document.refresh_from_db()
    return document


# =================================================================================================
# 1. Every route resolves, renders and answers
# =================================================================================================

def test_dk_the_sub_module_owns_exactly_thirty_three_routes():
    """33, not the stale build contract's 32 - ``pdocrevision_download`` is C1's addition."""
    assert len(set(_DK_ALL_ROUTES)) == 33
    for name in _DK_ALL_ROUTES:
        # Every one reverses; the pk-taking ones with an arg, the rest without.
        try:
            reverse(f"procurement:{name}")
        except NoReverseMatch:
            reverse(f"procurement:{name}", args=[1])


def test_dk_there_is_no_revision_edit_route():
    """A revision is immutable: no url, no view, no template. Asserting the absence is the test."""
    with pytest.raises(NoReverseMatch):
        reverse("procurement:pdocrevision_edit", args=[1])


@pytest.mark.parametrize("name,path", [
    ("pdocument_list", "/procurement/documents/"),
    ("pdocument_create", "/procurement/documents/add/"),
    ("pdocument_reindex", "/procurement/documents/reindex/"),
    ("pdocument_run_reminders", "/procurement/documents/run-reminders/"),
    ("pdocrevision_list", "/procurement/document-revisions/"),
    ("ppolicy_list", "/procurement/procurement-policies/"),
    ("ppolicy_create", "/procurement/procurement-policies/add/"),
    ("knowledgeresource_list", "/procurement/knowledge/"),
    ("knowledgeresource_create", "/procurement/knowledge/add/"),
])
def test_dk_literal_routes_keep_their_published_paths(name, path):
    """These are bookmarked and linked from the sidebar; the literal path is part of the contract
    and must stay ahead of the ``<int:pk>`` routes in the concatenated urlpatterns."""
    assert _dk_url(name) == path


@pytest.mark.parametrize("name,suffix", [
    ("pdocument_detail", "/procurement/documents/7/"),
    ("pdocument_edit", "/procurement/documents/7/edit/"),
    ("pdocument_delete", "/procurement/documents/7/delete/"),
    ("pdocument_checkout", "/procurement/documents/7/checkout/"),
    ("pdocument_release", "/procurement/documents/7/release/"),
    ("pdocument_activate", "/procurement/documents/7/activate/"),
    ("pdocument_supersede", "/procurement/documents/7/supersede/"),
    ("pdocument_archive", "/procurement/documents/7/archive/"),
    ("pdocument_revision_upload", "/procurement/documents/7/revisions/add/"),
    ("pdocrevision_detail", "/procurement/document-revisions/7/"),
    ("pdocrevision_download", "/procurement/document-revisions/7/download/"),
    ("pdocrevision_approve", "/procurement/document-revisions/7/approve/"),
    ("pdocrevision_delete", "/procurement/document-revisions/7/delete/"),
    ("ppolicy_detail", "/procurement/procurement-policies/7/"),
    ("ppolicy_edit", "/procurement/procurement-policies/7/edit/"),
    ("ppolicy_delete", "/procurement/procurement-policies/7/delete/"),
    ("ppolicy_publish", "/procurement/procurement-policies/7/publish/"),
    ("ppolicy_archive", "/procurement/procurement-policies/7/archive/"),
    ("knowledgeresource_detail", "/procurement/knowledge/7/"),
    ("knowledgeresource_edit", "/procurement/knowledge/7/edit/"),
    ("knowledgeresource_delete", "/procurement/knowledge/7/delete/"),
    ("knowledgeresource_publish", "/procurement/knowledge/7/publish/"),
    ("knowledgeresource_archive", "/procurement/knowledge/7/archive/"),
    ("knowledgeresource_use", "/procurement/knowledge/7/use/"),
])
def test_dk_pk_routes_keep_their_published_paths(name, suffix):
    assert _dk_url(name, 7) == suffix


# =================================================================================================
# 2. The four registers render their rows - CONTENT, not status
# =================================================================================================

def test_dk_document_register_renders_every_seeded_row_by_number(
        client_a, dk_document_draft_a, dk_document_active_a, dk_document_superseded_a,
        dk_document_archived_a, dk_document_public_a):
    resp = _dk_get(client_a, "pdocument_list")
    assert resp.status_code == 200
    body = _dk_body(resp)
    for document in (dk_document_draft_a, dk_document_active_a, dk_document_superseded_a,
                     dk_document_archived_a, dk_document_public_a):
        assert document.number in body, f"{document.number} missing from the register"
        assert document.title in body
    # A half-rendered template is the failure mode a status-only sweep reads as success.
    assert "{%" not in body and "{{" not in body


@pytest.mark.parametrize("route,pk_fixture,template", [
    ("pdocument_list", None, "procurement/documentknowledge/document/list.html"),
    ("pdocument_create", None, "procurement/documentknowledge/document/form.html"),
    ("pdocument_detail", "dk_document_chain_a",
     "procurement/documentknowledge/document/detail.html"),
    ("pdocument_edit", "dk_document_chain_a",
     "procurement/documentknowledge/document/form.html"),
    ("pdocument_revision_upload", "dk_document_chain_a",
     "procurement/documentknowledge/revision/form.html"),
    ("pdocrevision_list", None, "procurement/documentknowledge/revision/list.html"),
    ("pdocrevision_detail", "dk_revision_approved_a",
     "procurement/documentknowledge/revision/detail.html"),
    ("ppolicy_list", None, "procurement/documentknowledge/policy/list.html"),
    ("ppolicy_create", None, "procurement/documentknowledge/policy/form.html"),
    ("ppolicy_detail", "dk_policy_published_a",
     "procurement/documentknowledge/policy/detail.html"),
    ("ppolicy_edit", "dk_policy_published_a",
     "procurement/documentknowledge/policy/form.html"),
    ("knowledgeresource_list", None,
     "procurement/documentknowledge/knowledgeresource/list.html"),
    ("knowledgeresource_create", None,
     "procurement/documentknowledge/knowledgeresource/form.html"),
    ("knowledgeresource_detail", "dk_resource_featured_a",
     "procurement/documentknowledge/knowledgeresource/detail.html"),
    ("knowledgeresource_edit", "dk_resource_featured_a",
     "procurement/documentknowledge/knowledgeresource/form.html"),
])
def test_dk_every_rendering_route_uses_its_contracted_template(
        client_a, request, route, pk_fixture, template):
    """Two folder levels, page as the bare filename - and a form page shared by create and edit."""
    args = [request.getfixturevalue(pk_fixture).pk] if pk_fixture else []
    resp = _dk_get(client_a, route, *args)
    assert resp.status_code == 200
    assert template in [rendered.name for rendered in resp.templates if rendered.name]
    assert "base.html" in [rendered.name for rendered in resp.templates if rendered.name]


def test_dk_document_register_stat_tiles_count_the_workspace(
        client_a, dk_document_draft_a, dk_document_active_a, dk_document_expiring_a,
        dk_document_expired_a):
    resp = _dk_get(client_a, "pdocument_list")
    stats = resp.context["stats"]
    assert set(stats) == {"total", "active", "expiring", "expired", "unapproved"}
    assert stats["total"] == 4
    assert stats["active"] == 3
    assert stats["expiring"] == 1
    assert stats["expired"] == 1
    # No revision has ever been approved on any of the four.
    assert stats["unapproved"] == 4


def test_dk_revision_register_renders_the_chain_rows(
        client_a, dk_document_chain_a, dk_revision_approved_a, dk_revision_pending_a):
    resp = _dk_get(client_a, "pdocrevision_list")
    assert resp.status_code == 200
    body = _dk_body(resp)
    assert dk_document_chain_a.number in body
    assert "r1" in body and "r2" in body
    assert dk_revision_pending_a.change_note in body
    assert dk_revision_approved_a.sha256[:16] in body


def test_dk_revision_register_stat_tiles_split_approved_from_pending(
        client_a, dk_document_chain_a):
    resp = _dk_get(client_a, "pdocrevision_list")
    stats = resp.context["stats"]
    assert set(stats) == {"total", "approved", "pending"}
    assert stats == {"total": 2, "approved": 1, "pending": 1}


def test_dk_policy_register_renders_the_version_chain(
        client_a, dk_policy_v1_archived_a, dk_policy_published_a, dk_policy_draft_a):
    resp = _dk_get(client_a, "ppolicy_list")
    assert resp.status_code == 200
    body = _dk_body(resp)
    for policy in (dk_policy_v1_archived_a, dk_policy_published_a, dk_policy_draft_a):
        assert policy.number in body
        assert f"v{policy.version_number}" in body
    # threshold_label reads through the currency FK - the join _ROW_RELATIONS exists for.
    assert "USD 25,000.00" in body


def test_dk_policy_register_stat_tiles_count_the_workspace(
        client_a, dk_policy_v1_archived_a, dk_policy_published_a, dk_policy_draft_a,
        dk_policy_review_due_a):
    resp = _dk_get(client_a, "ppolicy_list")
    stats = resp.context["stats"]
    assert set(stats) == {"total", "published", "draft", "review_due"}
    assert stats["total"] == 4
    assert stats["published"] == 2
    assert stats["draft"] == 1
    assert stats["review_due"] == 1


def test_dk_knowledge_register_renders_every_seeded_row_by_number(
        client_a, dk_resource_featured_a, dk_resource_published_a, dk_resource_draft_a,
        dk_resource_archived_a):
    resp = _dk_get(client_a, "knowledgeresource_list")
    assert resp.status_code == 200
    body = _dk_body(resp)
    for resource in (dk_resource_featured_a, dk_resource_published_a, dk_resource_draft_a,
                     dk_resource_archived_a):
        assert resource.number in body
        assert resource.title in body


def test_dk_knowledge_register_stat_tiles_count_rows_with_a_press_not_presses(
        client_a, dk_resource_featured_a, dk_resource_published_a, dk_resource_used_a,
        dk_resource_draft_a):
    resp = _dk_get(client_a, "knowledgeresource_list")
    stats = resp.context["stats"]
    assert set(stats) == {"total", "published", "featured", "used"}
    assert stats["total"] == 4
    assert stats["published"] == 3
    assert stats["featured"] == 1
    # dk_resource_used_a is the only row with usage_count > 0; its SEVEN presses count once.
    assert stats["used"] == 1


def test_dk_knowledge_register_featured_shelf_is_published_featured_and_capped(
        client_a, dk_resource_featured_a, dk_resource_published_a, dk_resource_archived_a):
    resp = _dk_get(client_a, "knowledgeresource_list")
    shelf = list(resp.context["featured"])
    assert [row.pk for row in shelf] == [dk_resource_featured_a.pk]
    assert len(shelf) <= FEATURED_CAP


def test_dk_knowledge_featured_shelf_is_not_a_slice_of_the_paginated_page(
        client_a, tenant_a, dk_resource_featured_a):
    """The shelf answers "where do I start?" and must read the same on page 2 as on page 1."""
    _dk_bulk = [_dk_resource(tenant_a, title=f"Library filler {i:02d}", status="published")
                for i in range(1, 18)]
    assert len(_dk_bulk) == 17
    page2 = _dk_get(client_a, "knowledgeresource_list", page="2")
    assert page2.status_code == 200
    assert [row.pk for row in page2.context["featured"]] == [dk_resource_featured_a.pk]


# =================================================================================================
# 3. Context keys - every name the contract pins, per view (L7/L8)
# =================================================================================================

def test_dk_document_register_context_carries_every_pinned_key(
        client_a, dk_document_active_a, dk_supplier_a):
    resp = _dk_get(client_a, "pdocument_list")
    for key in ("object_list", "page_obj", "q", "doc_type_choices", "status_choices",
                "classification_choices", "expiry_choices", "suppliers", "owners", "stats",
                "search_note", "classification_note"):
        assert key in resp.context, f"pdocument_list lost its {key!r} context key"
    assert resp.context["expiry_choices"] == EXPIRY_FILTER_CHOICES
    assert resp.context["search_note"] == SEARCH_NOTE
    assert resp.context["classification_note"] == CLASSIFICATION_NOTE
    assert dk_supplier_a in list(resp.context["suppliers"])


def test_dk_document_register_search_note_states_the_four_character_rule(client_a):
    """I15 rewrote this note. The register may not promise a sweep it does not perform."""
    resp = _dk_get(client_a, "pdocument_list")
    note = resp.context["search_note"]
    assert "four characters or more" in note
    assert note in _dk_body(resp)


def test_dk_document_detail_context_carries_every_pinned_key(
        client_a, dk_document_chain_a, dk_policy_published_a, dk_resource_featured_a):
    resp = _dk_get(client_a, "pdocument_detail", dk_document_chain_a.pk)
    assert resp.status_code == 200
    for key in ("obj", "revisions", "current_revision", "policies", "knowledge_resources",
                "can_upload", "can_release", "lock_holder", "search_note",
                "classification_note"):
        assert key in resp.context, f"pdocument_detail lost its {key!r} context key"
    assert resp.context["obj"].pk == dk_document_chain_a.pk
    assert [r.revision_no for r in resp.context["revisions"]] == [2, 1]
    assert resp.context["current_revision"].revision_no == 1
    assert dk_document_chain_a.number in _dk_body(resp)


def test_dk_document_detail_current_revision_ignores_an_unapproved_pointer(
        client_a, dk_document_chain_a, dk_revision_pending_a):
    """I1 through the page: the pointer forced onto a PENDING r2 presents nothing as current."""
    _dk_reset_pointer(dk_document_chain_a, 2)
    resp = _dk_get(client_a, "pdocument_detail", dk_document_chain_a.pk)
    assert resp.status_code == 200
    assert resp.context["current_revision"] is None


def test_dk_document_detail_lists_the_policies_and_resources_that_point_at_it(
        client_a, dk_document_active_a, dk_policy_published_a, dk_resource_featured_a):
    resp = _dk_get(client_a, "pdocument_detail", dk_document_active_a.pk)
    assert [p.pk for p in resp.context["policies"]] == [dk_policy_published_a.pk]
    assert [r.pk for r in resp.context["knowledge_resources"]] == [dk_resource_featured_a.pk]


def test_dk_document_detail_caps_its_reverse_panels_at_fifty(
        client_a, tenant_a, admin_user, dk_media_root):
    """M22: the busiest row is exactly the one people open. 52 revisions, 50 rendered."""
    document = _dk_document(tenant_a, title="Heavily revised drawing", created_by=admin_user)
    for index in range(52):
        _dk_revision(document, filename=f"rev-{index:02d}.txt", uploaded_by=admin_user,
                     body=f"Revision {index} body text.".encode("utf-8"))
    assert document.revisions.count() == 52
    resp = _dk_get(client_a, "pdocument_detail", document.pk)
    assert DETAIL_FAN_OUT_CAP == 50
    assert len(resp.context["revisions"]) == DETAIL_FAN_OUT_CAP


def test_dk_document_detail_computes_can_release_and_can_upload_for_the_holder(
        member_client, member_user, dk_document_locked_a):
    """I11, holder half: ``member_user`` holds this checkout, so both buttons are offered."""
    resp = _dk_get(member_client, "pdocument_detail", dk_document_locked_a.pk)
    assert resp.status_code == 200
    assert resp.context["can_release"] is True
    assert resp.context["can_upload"] is True
    assert resp.context["lock_holder"] == member_user


def test_dk_document_detail_offers_an_admin_the_force_release_but_not_the_upload(
        client_a, member_user, dk_document_locked_a):
    """I11, administrator half: they may FORCE the release, they may not add to the chain."""
    resp = _dk_get(client_a, "pdocument_detail", dk_document_locked_a.pk)
    assert resp.context["can_release"] is True
    assert resp.context["can_upload"] is False
    assert resp.context["lock_holder"] == member_user


def test_dk_document_detail_on_an_unlocked_row_offers_upload_and_no_release(
        client_a, dk_document_active_a):
    resp = _dk_get(client_a, "pdocument_detail", dk_document_active_a.pk)
    assert resp.context["can_release"] is False
    assert resp.context["can_upload"] is True
    assert resp.context["lock_holder"] is None


def test_dk_document_detail_refuses_upload_on_an_archived_row(
        client_a, dk_document_archived_a):
    resp = _dk_get(client_a, "pdocument_detail", dk_document_archived_a.pk)
    assert resp.context["can_upload"] is False


def test_dk_document_create_form_context_carries_its_notes(client_a):
    resp = _dk_get(client_a, "pdocument_create")
    assert resp.status_code == 200
    assert resp.context["is_edit"] is False
    assert resp.context["form"] is not None
    assert resp.context["search_note"] == SEARCH_NOTE
    assert resp.context["classification_note"] == CLASSIFICATION_NOTE


def test_dk_document_edit_form_context_carries_obj_and_its_notes(
        client_a, dk_document_draft_a):
    resp = _dk_get(client_a, "pdocument_edit", dk_document_draft_a.pk)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["obj"].pk == dk_document_draft_a.pk
    assert resp.context["classification_note"] == CLASSIFICATION_NOTE
    assert dk_document_draft_a.title in _dk_body(resp)


def test_dk_revision_register_context_carries_every_pinned_key(
        client_a, dk_document_chain_a):
    resp = _dk_get(client_a, "pdocrevision_list")
    for key in ("object_list", "page_obj", "q", "documents", "approval_choices", "stats",
                "revision_note"):
        assert key in resp.context, f"pdocrevision_list lost its {key!r} context key"
    assert resp.context["approval_choices"] == APPROVAL_CHOICES
    assert resp.context["revision_note"] == REVISION_NOTE
    assert [d.pk for d in resp.context["documents"]] == [dk_document_chain_a.pk]


def test_dk_revision_register_document_facet_is_capped_and_three_columns(
        client_a, dk_document_chain_a):
    """C2: the facet is a navigation aid, not an export of the workspace's search corpus."""
    resp = _dk_get(client_a, "pdocrevision_list")
    facet = list(resp.context["documents"])
    assert len(facet) <= DOCUMENT_FACET_CAP
    assert DOCUMENT_FACET_CAP == 200
    # ``.only("pk", "number", "title")`` - the <select> renders exactly those three, and a plain
    # queryset would haul the workspace's whole 200,000-character search corpus down to draw it.
    deferred = facet[0].get_deferred_fields()
    assert {"extracted_text", "description", "tags"} <= deferred
    assert not {"number", "title"} & deferred


def test_dk_revision_detail_context_carries_every_pinned_key(
        client_a, dk_document_chain_a, dk_revision_approved_a):
    resp = _dk_get(client_a, "pdocrevision_detail", dk_revision_approved_a.pk)
    assert resp.status_code == 200
    for key in ("obj", "document", "is_current", "revision_note"):
        assert key in resp.context, f"pdocrevision_detail lost its {key!r} context key"
    assert resp.context["obj"].pk == dk_revision_approved_a.pk
    assert resp.context["document"].pk == dk_document_chain_a.pk
    assert resp.context["is_current"] is True
    assert dk_document_chain_a.number in _dk_body(resp)


def test_dk_revision_detail_is_current_is_false_behind_the_pointer(
        client_a, dk_revision_pending_a):
    resp = _dk_get(client_a, "pdocrevision_detail", dk_revision_pending_a.pk)
    assert resp.context["is_current"] is False


def test_dk_revision_upload_page_context_carries_every_pinned_key(
        client_a, dk_document_draft_a):
    resp = _dk_get(client_a, "pdocument_revision_upload", dk_document_draft_a.pk)
    assert resp.status_code == 200
    for key in ("form", "is_edit", "document", "upload_note"):
        assert key in resp.context, f"pdocument_revision_upload lost its {key!r} context key"
    assert resp.context["is_edit"] is False
    assert resp.context["document"].pk == dk_document_draft_a.pk
    assert resp.context["upload_note"] == UPLOAD_NOTE
    assert "20 MB" in resp.context["upload_note"]


def test_dk_policy_register_context_carries_every_pinned_key(
        client_a, dk_policy_published_a, org_unit_a):
    resp = _dk_get(client_a, "ppolicy_list")
    for key in ("object_list", "page_obj", "q", "policy_type_choices", "status_choices",
                "org_units", "review_choices", "stats", "advisory_note"):
        assert key in resp.context, f"ppolicy_list lost its {key!r} context key"
    assert resp.context["review_choices"] == REVIEW_CHOICES
    assert resp.context["advisory_note"] == ADVISORY_NOTE
    assert org_unit_a in list(resp.context["org_units"])


def test_dk_policy_review_facet_label_reads_review_due(client_a):
    """M13: one concept, one wording. "Review overdue" in red taught users it was worse."""
    resp = _dk_get(client_a, "ppolicy_list")
    assert resp.context["review_choices"] == [("due", "Review due")]
    assert "Review overdue" not in _dk_body(resp)


def test_dk_policy_detail_context_carries_every_pinned_key(
        client_a, dk_policy_published_a, dk_policy_v1_archived_a, dk_policy_draft_a):
    resp = _dk_get(client_a, "ppolicy_detail", dk_policy_published_a.pk)
    assert resp.status_code == 200
    for key in ("obj", "advisory_note", "supersedes", "superseded_by_rows"):
        assert key in resp.context, f"ppolicy_detail lost its {key!r} context key"
    assert resp.context["obj"].pk == dk_policy_published_a.pk
    assert resp.context["supersedes"].pk == dk_policy_v1_archived_a.pk
    assert [row.pk for row in resp.context["superseded_by_rows"]] == [dk_policy_draft_a.pk]
    assert len(resp.context["superseded_by_rows"]) <= SUPERSEDED_BY_CAP


def test_dk_policy_and_resource_detail_expose_no_is_review_due_context_key(
        client_a, dk_policy_review_due_a, dk_resource_review_due_a):
    """M15: one fact reachable by two names inside one sub-module was the defect."""
    policy_page = _dk_get(client_a, "ppolicy_detail", dk_policy_review_due_a.pk)
    assert "is_review_due" not in policy_page.context
    assert policy_page.context["obj"].is_review_due is True

    resource_page = _dk_get(client_a, "knowledgeresource_detail", dk_resource_review_due_a.pk)
    assert "is_review_due" not in resource_page.context
    assert resource_page.context["obj"].is_review_due is True


def test_dk_policy_form_pages_carry_the_advisory_note(client_a, dk_policy_draft_a):
    create = _dk_get(client_a, "ppolicy_create")
    assert create.context["is_edit"] is False
    assert create.context["advisory_note"] == ADVISORY_NOTE

    edit = _dk_get(client_a, "ppolicy_edit", dk_policy_draft_a.pk)
    assert edit.context["is_edit"] is True
    assert edit.context["obj"].pk == dk_policy_draft_a.pk
    assert edit.context["advisory_note"] == ADVISORY_NOTE


def test_dk_knowledge_register_context_carries_every_pinned_key(
        client_a, dk_resource_featured_a):
    resp = _dk_get(client_a, "knowledgeresource_list")
    for key in ("object_list", "page_obj", "q", "resource_type_choices", "category_choices",
                "audience_choices", "status_choices", "featured_choices", "featured", "stats",
                "library_note"):
        assert key in resp.context, f"knowledgeresource_list lost its {key!r} context key"
    assert resp.context["featured_choices"] == FEATURED_CHOICES
    assert resp.context["library_note"] == LIBRARY_NOTE


def test_dk_knowledge_detail_context_carries_every_pinned_key(
        client_a, dk_resource_featured_a, dk_document_active_a):
    resp = _dk_get(client_a, "knowledgeresource_detail", dk_resource_featured_a.pk)
    assert resp.status_code == 200
    for key in ("obj", "library_note", "document"):
        assert key in resp.context, f"knowledgeresource_detail lost its {key!r} context key"
    assert resp.context["obj"].pk == dk_resource_featured_a.pk
    assert resp.context["document"].pk == dk_document_active_a.pk
    assert dk_resource_featured_a.number in _dk_body(resp)


def test_dk_knowledge_form_pages_carry_the_library_note(client_a, dk_resource_draft_a):
    create = _dk_get(client_a, "knowledgeresource_create")
    assert create.context["is_edit"] is False
    assert create.context["library_note"] == LIBRARY_NOTE

    edit = _dk_get(client_a, "knowledgeresource_edit", dk_resource_draft_a.pk)
    assert edit.context["is_edit"] is True
    assert edit.context["obj"].pk == dk_resource_draft_a.pk
    assert edit.context["library_note"] == LIBRARY_NOTE


# =================================================================================================
# 4. Create / edit / delete through the form pages
# =================================================================================================

def test_dk_document_create_saves_into_the_request_tenant(client_a, tenant_a, admin_user):
    resp = client_a.post(_dk_url("pdocument_create"), {
        "title": "Fire alarm service certificate",
        "doc_type": "certificate",
        "classification": "internal",
        "description": "Annual inspection certificate.",
        "tags": "Certificate, Fire ",
    })
    assert resp.status_code == 302
    document = ProcurementDocument.objects.get(title="Fire alarm service certificate")
    assert document.tenant_id == tenant_a.pk
    # The system columns the form does not offer come back at their defaults, not from the POST.
    assert document.number.startswith("PDOC-")
    assert document.status == "draft"
    assert document.current_revision_no == 0
    assert document.tags == "certificate, fire"


def test_dk_document_create_rejects_a_blank_title_without_saving(client_a):
    resp = client_a.post(_dk_url("pdocument_create"), {"doc_type": "other",
                                                       "classification": "internal"})
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert not ProcurementDocument.objects.exists()


def test_dk_document_edit_updates_the_row(client_a, dk_document_draft_a):
    resp = client_a.post(_dk_url("pdocument_edit", dk_document_draft_a.pk), {
        "title": "Draft specification - server rack (rev B)",
        "doc_type": "specification",
        "classification": "internal",
    })
    assert resp.status_code == 302
    dk_document_draft_a.refresh_from_db()
    assert dk_document_draft_a.title.endswith("(rev B)")
    # Editing never touches the workflow columns the form does not carry.
    assert dk_document_draft_a.status == "draft"


def test_dk_document_delete_removes_a_document_with_no_approved_chain(
        client_a, dk_document_draft_a):
    resp = _dk_post(client_a, "pdocument_delete", dk_document_draft_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_list")
    assert not ProcurementDocument.objects.filter(pk=dk_document_draft_a.pk).exists()


def test_dk_document_delete_refuses_while_the_pointer_has_moved(
        client_a, dk_document_chain_a):
    resp = _dk_post(client_a, "pdocument_delete", dk_document_chain_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_chain_a.pk)
    assert _dk_said(resp, "approved revision chain")
    assert ProcurementDocument.objects.filter(pk=dk_document_chain_a.pk).exists()
    assert dk_document_chain_a.revisions.count() == 2


def test_dk_policy_create_saves_into_the_request_tenant(client_a, tenant_a):
    resp = client_a.post(_dk_url("ppolicy_create"), {
        "title": "Sole Source Justification Rule",
        "policy_type": "sole_source",
        "version_number": "1.0",
        "summary": "A single-source award needs a written justification.",
        "body": "State why no competitive process was run.",
    })
    assert resp.status_code == 302
    policy = ProcurementPolicy.objects.get(title="Sole Source Justification Rule")
    assert policy.tenant_id == tenant_a.pk
    assert policy.number.startswith("PPOL-")
    assert policy.status == "draft"
    assert policy.published_at is None


def test_dk_policy_delete_removes_a_policy_nobody_signed(client_a, dk_policy_review_due_a):
    resp = _dk_post(client_a, "ppolicy_delete", dk_policy_review_due_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("ppolicy_list")
    assert not ProcurementPolicy.objects.filter(pk=dk_policy_review_due_a.pk).exists()


def test_dk_policy_delete_refuses_while_an_acknowledgement_exists(
        client_a, dk_policy_published_a, dk_attestation_a):
    resp = _dk_post(client_a, "ppolicy_delete", dk_policy_published_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("ppolicy_detail", dk_policy_published_a.pk)
    assert _dk_said(resp, "acknowledgement record")
    assert ProcurementPolicy.objects.filter(pk=dk_policy_published_a.pk).exists()


def test_dk_knowledge_create_saves_into_the_request_tenant(client_a, tenant_a):
    resp = client_a.post(_dk_url("knowledgeresource_create"), {
        "title": "Tender evaluation scorecard",
        "resource_type": "evaluation_scorecard",
        "category": "general",
        "audience": "approver",
        "summary": "Weighted grid with the standard five criteria.",
        "body": "Score each criterion out of ten.",
        "tags": "Scorecard, Tender ",
    })
    assert resp.status_code == 302
    resource = KnowledgeResource.objects.get(title="Tender evaluation scorecard")
    assert resource.tenant_id == tenant_a.pk
    assert resource.number.startswith("PKR-")
    assert resource.status == "draft"
    assert resource.usage_count == 0
    assert resource.last_used_at is None
    assert resource.tags == "scorecard, tender"


def test_dk_knowledge_delete_removes_the_row_and_leaves_its_document(
        client_a, dk_resource_featured_a, dk_document_active_a):
    resp = _dk_post(client_a, "knowledgeresource_delete", dk_resource_featured_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("knowledgeresource_list")
    assert not KnowledgeResource.objects.filter(pk=dk_resource_featured_a.pk).exists()
    assert ProcurementDocument.objects.filter(pk=dk_document_active_a.pk).exists()


@pytest.mark.parametrize("name", ["pdocument_delete", "ppolicy_delete",
                                  "knowledgeresource_delete"])
def test_dk_a_get_never_deletes(client_a, name, dk_document_draft_a, dk_policy_review_due_a,
                                dk_resource_draft_a):
    """The self-defending half of the delete contract: only POST mutates."""
    target = {"pdocument_delete": dk_document_draft_a,
              "ppolicy_delete": dk_policy_review_due_a,
              "knowledgeresource_delete": dk_resource_draft_a}[name]
    model = type(target)
    resp = _dk_get(client_a, name, target.pk)
    assert resp.status_code == 405
    assert model.objects.filter(pk=target.pk).exists()


@pytest.mark.parametrize("name", _DK_POST_ONLY_PK_VERBS)
def test_dk_a_get_on_a_post_only_verb_is_405(client_a, name, dk_document_chain_a,
                                             dk_revision_pending_a, dk_policy_draft_a,
                                             dk_resource_draft_a):
    """Decorator order is login -> admin -> require_POST, so an ADMIN GET reaches the 405."""
    pk = {"pdocument": dk_document_chain_a.pk, "pdocrevision": dk_revision_pending_a.pk,
          "ppolicy": dk_policy_draft_a.pk,
          "knowledgeresource": dk_resource_draft_a.pk}[name.split("_")[0]]
    assert _dk_get(client_a, name, pk).status_code == 405


@pytest.mark.parametrize("name", ["pdocument_reindex", "pdocument_run_reminders"])
def test_dk_a_get_on_a_pk_less_verb_is_405(client_a, name):
    assert _dk_get(client_a, name).status_code == 405


# =================================================================================================
# 5. The document verbs' state machines
# =================================================================================================

def test_dk_checkout_takes_the_advisory_lock(client_a, admin_user, dk_document_active_a):
    resp = _dk_post(client_a, "pdocument_checkout", dk_document_active_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_active_a.pk)
    dk_document_active_a.refresh_from_db()
    assert dk_document_active_a.checked_out_by_id == admin_user.pk
    assert dk_document_active_a.checked_out_at is not None
    assert dk_document_active_a.is_checked_out is True


def test_dk_checkout_a_second_time_reports_and_does_not_re_stamp(
        client_a, dk_document_active_a):
    _dk_post(client_a, "pdocument_checkout", dk_document_active_a.pk)
    dk_document_active_a.refresh_from_db()
    stamped = dk_document_active_a.checked_out_at

    resp = _dk_post(client_a, "pdocument_checkout", dk_document_active_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "already have this document checked out")
    dk_document_active_a.refresh_from_db()
    assert dk_document_active_a.checked_out_at == stamped


def test_dk_checkout_is_refused_while_somebody_else_holds_it(
        client_a, member_user, dk_document_locked_a):
    resp = _dk_post(client_a, "pdocument_checkout", dk_document_locked_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "has this document checked out")
    assert _dk_said(resp, member_user.username) or _dk_said(resp, member_user.get_full_name())
    dk_document_locked_a.refresh_from_db()
    assert dk_document_locked_a.checked_out_by_id == member_user.pk


def test_dk_checkout_is_refused_on_an_archived_document(client_a, dk_document_archived_a):
    resp = _dk_post(client_a, "pdocument_checkout", dk_document_archived_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "archived document cannot be checked out")
    dk_document_archived_a.refresh_from_db()
    assert dk_document_archived_a.checked_out_by_id is None


def test_dk_release_clears_the_lock_for_its_holder(
        member_client, dk_document_locked_a):
    resp = _dk_post(member_client, "pdocument_release", dk_document_locked_a.pk)
    assert resp.status_code == 302
    dk_document_locked_a.refresh_from_db()
    assert dk_document_locked_a.checked_out_by_id is None
    assert dk_document_locked_a.checked_out_at is None


def test_dk_release_is_refused_for_a_non_holder_who_is_not_an_administrator(
        db, tenant_a, django_user_model, member_user, dk_document_locked_a):
    """The advisory lock's only refusal: neither the holder nor a workspace administrator."""
    from django.test import Client

    bystander = _dk_second_member(tenant_a, django_user_model)
    client = Client()
    client.force_login(bystander)

    resp = _dk_post(client, "pdocument_release", dk_document_locked_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "holds this checkout")
    dk_document_locked_a.refresh_from_db()
    assert dk_document_locked_a.checked_out_by_id == member_user.pk


def test_dk_release_by_an_administrator_is_a_forced_release(
        client_a, member_user, dk_document_locked_a):
    resp = _dk_post(client_a, "pdocument_release", dk_document_locked_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "released")
    dk_document_locked_a.refresh_from_db()
    assert dk_document_locked_a.checked_out_by_id is None


def test_dk_release_on_an_unlocked_document_reports_and_writes_nothing(
        client_a, dk_document_active_a):
    resp = _dk_post(client_a, "pdocument_release", dk_document_active_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "not checked out")
    dk_document_active_a.refresh_from_db()
    assert dk_document_active_a.checked_out_by_id is None


@pytest.mark.parametrize("fixture_name", ["dk_document_draft_a", "dk_document_superseded_a",
                                          "dk_document_archived_a"])
def test_dk_activate_puts_a_document_back_in_force_from_any_state(
        client_a, request, fixture_name):
    document = request.getfixturevalue(fixture_name)
    resp = _dk_post(client_a, "pdocument_activate", document.pk)
    assert resp.status_code == 302
    document.refresh_from_db()
    assert document.status == "active"


def test_dk_activate_on_an_active_document_reports_and_writes_nothing(
        client_a, dk_document_active_a):
    before = dk_document_active_a.updated_at
    resp = _dk_post(client_a, "pdocument_activate", dk_document_active_a.pk)
    assert _dk_said(resp, "already active")
    dk_document_active_a.refresh_from_db()
    assert dk_document_active_a.status == "active"
    assert dk_document_active_a.updated_at == before


def test_dk_supersede_retires_an_active_document(client_a, dk_document_active_a):
    resp = _dk_post(client_a, "pdocument_supersede", dk_document_active_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "marked superseded")
    dk_document_active_a.refresh_from_db()
    assert dk_document_active_a.status == "superseded"


def test_dk_supersede_is_refused_on_a_draft(client_a, dk_document_draft_a):
    """A draft was never in force, so superseding it says nothing (L35: refuse, do not fall
    through to the transition)."""
    resp = _dk_post(client_a, "pdocument_supersede", dk_document_draft_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "Only an active document can be superseded")
    dk_document_draft_a.refresh_from_db()
    assert dk_document_draft_a.status == "draft"


def test_dk_supersede_is_refused_on_an_archived_document(client_a, dk_document_archived_a):
    resp = _dk_post(client_a, "pdocument_supersede", dk_document_archived_a.pk)
    assert _dk_said(resp, "Only an active document can be superseded")
    dk_document_archived_a.refresh_from_db()
    assert dk_document_archived_a.status == "archived"


def test_dk_supersede_on_a_superseded_document_reports_and_writes_nothing(
        client_a, dk_document_superseded_a):
    before = dk_document_superseded_a.updated_at
    resp = _dk_post(client_a, "pdocument_supersede", dk_document_superseded_a.pk)
    assert _dk_said(resp, "already superseded")
    dk_document_superseded_a.refresh_from_db()
    assert dk_document_superseded_a.updated_at == before


@pytest.mark.parametrize("fixture_name", ["dk_document_draft_a", "dk_document_active_a",
                                          "dk_document_superseded_a"])
def test_dk_archive_takes_a_document_out_of_use_from_any_state(
        client_a, request, fixture_name):
    document = request.getfixturevalue(fixture_name)
    resp = _dk_post(client_a, "pdocument_archive", document.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "Nothing was deleted")
    document.refresh_from_db()
    assert document.status == "archived"


def test_dk_archive_keeps_every_revision(client_a, dk_document_chain_a):
    _dk_post(client_a, "pdocument_archive", dk_document_chain_a.pk)
    dk_document_chain_a.refresh_from_db()
    assert dk_document_chain_a.status == "archived"
    assert dk_document_chain_a.revisions.count() == 2
    assert dk_document_chain_a.current_revision_no == 1


def test_dk_archive_on_an_archived_document_reports_and_writes_nothing(
        client_a, dk_document_archived_a):
    before = dk_document_archived_a.updated_at
    resp = _dk_post(client_a, "pdocument_archive", dk_document_archived_a.pk)
    assert _dk_said(resp, "already archived")
    dk_document_archived_a.refresh_from_db()
    assert dk_document_archived_a.updated_at == before


# =================================================================================================
# 6. Re-index and the reminder Run
# =================================================================================================

def test_dk_reindex_fills_an_empty_search_copy_from_the_approved_revision(
        client_a, dk_document_chain_a):
    """The Run's reason to exist: a document approved before extraction worked here."""
    ProcurementDocument.objects.filter(pk=dk_document_chain_a.pk).update(extracted_text="")

    resp = _dk_post(client_a, "pdocument_reindex")
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_list")
    assert _dk_said(resp, "Re-indexed 1 document(s)")
    dk_document_chain_a.refresh_from_db()
    assert "soleplate" in dk_document_chain_a.extracted_text


def test_dk_reindex_with_nothing_to_do_reports_zero_and_writes_nothing(
        client_a, dk_document_chain_a):
    resp = _dk_post(client_a, "pdocument_reindex")
    assert _dk_said(resp, "Re-indexed 0 document(s)")
    assert not _dk_said(resp, "press Re-index again")
    dk_document_chain_a.refresh_from_db()
    assert "soleplate" in dk_document_chain_a.extracted_text


def test_dk_reindex_skips_a_revision_that_already_carries_an_extraction_note(
        client_a, tenant_a, admin_user, dk_media_root):
    """M2: a file with no text layer can never be filled in, so it must not hold a cap slot."""
    document = _dk_document(tenant_a, title="Scanned drawing pack", created_by=admin_user)
    revision = _dk_revision(document, filename="scan.txt", uploaded_by=admin_user, body=b"   ")
    _dk_approve(revision, admin_user)
    assert revision.extraction_note != ""
    ProcurementDocument.objects.filter(pk=document.pk).update(extracted_text="")

    resp = _dk_post(client_a, "pdocument_reindex")
    assert _dk_said(resp, "Re-indexed 0 document(s)")
    document.refresh_from_db()
    assert document.extracted_text == ""


def test_dk_reindex_writes_only_while_the_pointer_is_unchanged(
        client_a, tenant_a, admin_user, dk_media_root, monkeypatch):
    """I4: the UPDATE is CONDITIONAL on the row still being the row the text was read for.

    The loop spends seconds in a file read between choosing a document and writing to it, and an
    approval can land in exactly that window. A blind ``save(update_fields=["extracted_text"])``
    would then install the superseded revision's wording over the newly-approved one PERMANENTLY
    - the row is no longer a candidate, so search would match the old text for ever. The race is
    reproduced here by moving the row from inside the extraction call the verb makes.
    """
    from apps.procurement.models.DocumentKnowledgeManagement import Revisions as _dk_rev_module

    document = _dk_document(tenant_a, title="Racing contract", created_by=admin_user)
    revision = _dk_revision(document, filename="race-r1.txt", uploaded_by=admin_user,
                            body=b"First issue carrying the stalebeacon phrase.")
    _dk_approve(revision, admin_user)
    ProcurementDocument.objects.filter(pk=document.pk).update(extracted_text="")

    real_extract = _dk_rev_module.extract_document_text

    def _dk_racing_extract(row):
        result = real_extract(row)
        # An administrator approves r2 while this file is being read.
        ProcurementDocument.objects.filter(pk=document.pk).update(
            current_revision_no=2, extracted_text="freshly approved wording")
        return result

    monkeypatch.setattr(_dk_rev_module, "extract_document_text", _dk_racing_extract)

    resp = _dk_post(client_a, "pdocument_reindex")
    assert resp.status_code == 302
    assert _dk_said(resp, "Re-indexed 0 document(s)")
    document.refresh_from_db()
    assert document.extracted_text == "freshly approved wording"
    assert "stalebeacon" not in document.extracted_text


def test_dk_reindex_never_selects_a_document_that_already_has_a_search_copy(
        client_a, tenant_a, admin_user, dk_media_root):
    """The candidate set is ``extracted_text=""``: a filled copy is left exactly as it is."""
    document = _dk_document(tenant_a, title="Already indexed contract", created_by=admin_user)
    revision = _dk_revision(document, filename="ai-r1.txt", uploaded_by=admin_user,
                            body=b"Body carrying the presentbeacon phrase.")
    _dk_approve(revision, admin_user)
    ProcurementDocument.objects.filter(pk=document.pk).update(
        extracted_text="a curated summary nobody wants overwritten")

    resp = _dk_post(client_a, "pdocument_reindex")
    assert _dk_said(resp, "Re-indexed 0 document(s)")
    document.refresh_from_db()
    assert document.extracted_text == "a curated summary nobody wants overwritten"


def test_dk_reindex_is_capped_at_twenty_five_rows_and_says_more_remain(
        client_a, tenant_a, admin_user, dk_media_root):
    """I12: 26 candidates, 25 indexed, and the message tells you to press it again."""
    assert REINDEX_ROW_CAP == 25
    assert REINDEX_TIME_BUDGET_SECONDS == 20
    for index in range(26):
        document = _dk_document(tenant_a, title=f"Unindexed contract {index:02d}",
                                created_by=admin_user)
        revision = _dk_revision(document, filename=f"c{index:02d}.txt", uploaded_by=admin_user,
                                body=f"Contract {index} carries the word cappedbeacon.".encode())
        _dk_approve(revision, admin_user)
        ProcurementDocument.objects.filter(pk=document.pk).update(extracted_text="")

    resp = _dk_post(client_a, "pdocument_reindex")
    assert _dk_said(resp, f"Re-indexed {REINDEX_ROW_CAP} document(s)")
    assert _dk_said(resp, "press Re-index again to continue")
    assert ProcurementDocument.objects.filter(tenant=tenant_a, extracted_text="").count() == 1

    # The second press picks up exactly where the first stopped.
    again = _dk_post(client_a, "pdocument_reindex")
    assert _dk_said(again, "Re-indexed 1 document(s)")
    assert not ProcurementDocument.objects.filter(tenant=tenant_a, extracted_text="").exists()


def test_dk_reindex_counts_a_file_it_cannot_read_as_skipped(
        client_a, tenant_a, admin_user, dk_media_root):
    """A candidate whose bytes vanished from storage is reported, never 500ed over."""
    import os

    document = _dk_document(tenant_a, title="Vanished bytes contract", created_by=admin_user)
    revision = _dk_revision(document, filename="gone-r1.txt", uploaded_by=admin_user,
                            body=b"Body that will not be there at re-index time.")
    _dk_approve(revision, admin_user)
    ProcurementDocument.objects.filter(pk=document.pk).update(extracted_text="")
    os.remove(revision.file.path)

    resp = _dk_post(client_a, "pdocument_reindex")
    assert resp.status_code == 302
    assert _dk_said(resp, "Re-indexed 0 document(s); 1 could not be read")
    document.refresh_from_db()
    assert document.extracted_text == ""


def test_dk_reindex_abandons_the_run_at_its_wall_clock_budget(
        client_a, tenant_a, admin_user, dk_media_root, monkeypatch):
    """The budget is checked BETWEEN documents, so a slow batch returns inside the request.

    Everything already re-indexed is kept (each write autocommits) and the message tells the
    user to press Run again - which is exactly what the row cap promises too.
    """
    from apps.procurement.views.DocumentKnowledgeManagement import Documents as _dk_doc_view

    document = _dk_document(tenant_a, title="Slow contract", created_by=admin_user)
    revision = _dk_revision(document, filename="slow-r1.txt", uploaded_by=admin_user,
                            body=b"Body carrying the slowbeacon phrase.")
    _dk_approve(revision, admin_user)
    ProcurementDocument.objects.filter(pk=document.pk).update(extracted_text="")

    class _DkExhaustedClock:
        """First reading sets the deadline; the next is already past it."""

        def __init__(self):
            self._readings = iter([0.0, float(REINDEX_TIME_BUDGET_SECONDS) + 1.0])

        def monotonic(self):
            return next(self._readings, 10.0 ** 9)

    monkeypatch.setattr(_dk_doc_view, "time", _DkExhaustedClock())

    resp = _dk_post(client_a, "pdocument_reindex")
    assert resp.status_code == 302
    assert _dk_said(resp, "Re-indexed 0 document(s)")
    assert _dk_said(resp, "press Re-index again to continue")
    document.refresh_from_db()
    assert document.extracted_text == ""


def test_dk_run_reminders_raises_one_alert_per_document_in_the_window(
        client_a, tenant_a, dk_document_expiring_a, dk_document_expired_a,
        dk_document_review_due_a):
    resp = _dk_post(client_a, "pdocument_run_reminders")
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_list")
    assert _dk_said(resp, "Reminder run complete")
    alerts = ProcurementAlert.objects.filter(tenant=tenant_a, kind="deadline")
    assert alerts.count() == 3
    assert set(alerts.values_list("link_url", flat=True)) == {
        f"/procurement/documents/{dk_document_expiring_a.pk}/",
        f"/procurement/documents/{dk_document_expired_a.pk}/",
        f"/procurement/documents/{dk_document_review_due_a.pk}/",
    }


def test_dk_run_reminders_pressed_twice_raises_nothing_new(
        client_a, tenant_a, dk_document_expiring_a, dk_document_expired_a,
        dk_document_review_due_a):
    _dk_post(client_a, "pdocument_run_reminders")
    first = ProcurementAlert.objects.filter(tenant=tenant_a).count()

    resp = _dk_post(client_a, "pdocument_run_reminders")
    assert _dk_said(resp, "0 alert(s) raised, 3 skipped")
    assert ProcurementAlert.objects.filter(tenant=tenant_a).count() == first


def test_dk_run_reminders_raises_nothing_for_an_archived_document(
        client_a, tenant_a, dk_document_archived_a):
    """The scan is ``status__in=("draft", "active")`` - a retired record raises no deadline."""
    ProcurementDocument.objects.filter(pk=dk_document_archived_a.pk).update(
        expires_on=timezone.localdate() + datetime.timedelta(days=3))
    resp = _dk_post(client_a, "pdocument_run_reminders")
    assert _dk_said(resp, "0 alert(s) raised")
    assert not ProcurementAlert.objects.filter(tenant=tenant_a).exists()


# -- the tenant guard on the three hand-rolled write paths ---------------------------------------

@pytest.fixture
def _dk_tenantless_client(db, django_user_model):
    """The superuser: ``is_superuser`` (so every decorator passes) and ``tenant=None`` by design.

    Every 6.19 queryset is ``filter(tenant=request.tenant)``, so a workspace-less session must be
    turned away BEFORE any write rather than left to mint orphan rows.
    """
    from django.test import Client

    user = django_user_model.objects.create_superuser(
        email="root@naverp.test", username="root", password="TestPass123!")
    assert user.tenant_id is None
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.parametrize("route", ["pdocument_reindex", "pdocument_run_reminders"])
def test_dk_a_workspace_less_session_is_turned_away_before_the_run(
        _dk_tenantless_client, tenant_a, route, dk_document_expiring_a):
    resp = _dk_post(_dk_tenantless_client, route)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("dashboard:home")
    assert _dk_said(resp, "Select a tenant workspace")
    assert not ProcurementAlert.objects.filter(tenant=tenant_a).exists()


def test_dk_a_workspace_less_session_cannot_reach_the_upload_page(
        _dk_tenantless_client, dk_document_draft_a):
    resp = _dk_get(_dk_tenantless_client, "pdocument_revision_upload", dk_document_draft_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("dashboard:home")
    assert dk_document_draft_a.revisions.count() == 0


@pytest.mark.parametrize("route,facets", [
    ("pdocument_list", ("suppliers", "owners")),
    ("pdocrevision_list", ("documents",)),
    ("ppolicy_list", ("org_units",)),
    ("knowledgeresource_list", ("featured",)),
])
def test_dk_a_workspace_less_session_sees_an_empty_register_and_empty_facets(
        _dk_tenantless_client, route, facets, dk_document_chain_a, dk_supplier_a,
        dk_policy_published_a, dk_resource_featured_a, org_unit_a):
    """``request.tenant is None`` returns nothing BY DESIGN - and the facets must agree.

    A ``<select>`` built off an unscoped queryset is the classic leak: the table renders empty
    while the dropdown above it enumerates every workspace's suppliers, documents and org units.
    """
    resp = _dk_get(_dk_tenantless_client, route)
    assert resp.status_code == 200
    assert _dk_pks(resp) == []
    for facet in facets:
        assert list(resp.context[facet]) == [], f"{route} leaked rows through its {facet} facet"


# =================================================================================================
# 7. The revision chain through HTTP - upload, approve, delete
# =================================================================================================

def test_dk_revision_upload_mints_r1_without_moving_the_pointer(
        client_a, admin_user, dk_document_draft_a, dk_media_root):
    payload = b"Server rack specification, first issue. Rails are uprightbeacon standard."
    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_draft_a.pk),
                         {"file": _dk_txt("rack-r1.txt", payload),
                          "change_note": "First issue"})
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_draft_a.pk)

    revision = dk_document_draft_a.revisions.get()
    assert revision.revision_no == 1
    assert revision.is_approved is False
    assert revision.uploaded_by_id == admin_user.pk
    assert revision.original_filename == "rack-r1.txt"
    assert revision.file_size == len(payload)
    assert len(revision.sha256) == 64
    assert "uprightbeacon" in revision.extracted_text
    assert revision.extraction_note == ""

    dk_document_draft_a.refresh_from_db()
    assert dk_document_draft_a.current_revision_no == 0
    assert dk_document_draft_a.status == "draft"
    assert dk_document_draft_a.extracted_text == ""


def test_dk_revision_upload_mints_the_next_number_on_the_chain(
        client_a, dk_document_chain_a, dk_media_root):
    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_chain_a.pk),
                         {"file": _dk_txt("boiler-r3.txt", b"Third issue of the boiler contract."),
                          "change_note": "Section 6 added"})
    assert resp.status_code == 302
    assert sorted(dk_document_chain_a.revisions.values_list("revision_no", flat=True)) == [1, 2, 3]
    assert dk_document_chain_a.revisions.get(revision_no=3).is_approved is False


def test_dk_revision_upload_is_refused_on_an_archived_document(
        client_a, dk_document_archived_a, dk_media_root):
    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_archived_a.pk),
                         {"file": _dk_txt(), "change_note": "Attempted"})
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_archived_a.pk)
    assert _dk_said(resp, "is archived, so it does not take new revisions")
    assert dk_document_archived_a.revisions.count() == 0


def test_dk_revision_upload_page_is_refused_on_an_archived_document_on_GET(
        client_a, dk_document_archived_a):
    """The page must not offer what the POST would refuse."""
    resp = _dk_get(client_a, "pdocument_revision_upload", dk_document_archived_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "is archived, so it does not take new revisions")


def test_dk_revision_upload_is_refused_while_somebody_else_holds_the_checkout(
        client_a, member_user, dk_document_locked_a, dk_media_root):
    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_locked_a.pk),
                         {"file": _dk_txt(), "change_note": "Attempted"})
    assert resp.status_code == 302
    assert _dk_said(resp, "checked out")
    assert dk_document_locked_a.revisions.count() == 0


def test_dk_revision_upload_refuses_a_disallowed_extension_on_the_page(
        client_a, dk_document_draft_a, dk_media_root):
    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_draft_a.pk),
                         {"file": SimpleUploadedFile("payload.php", b"<?php echo 1; ?>",
                                                     content_type="text/plain"),
                          "change_note": "Attempted"})
    assert resp.status_code == 200
    # Read the error LIST, never str(form.errors) - that renders escaped HTML.
    assert resp.context["form"].errors["file"] == ["File type '.php' is not allowed."]
    assert dk_document_draft_a.revisions.count() == 0


def test_dk_revision_upload_reports_a_doubly_failing_allocation_instead_of_500ing(
        client_a, dk_document_chain_a, dk_media_root, monkeypatch):
    """``unique_together (tenant, document, revision_no)`` is the backstop; ONE retry, then a
    message. A second collision is reported honestly rather than retried for ever."""
    from apps.procurement.views.DocumentKnowledgeManagement import Revisions as _dk_rev_view

    # Allocation always returns a number that is already taken, so both attempts collide.
    monkeypatch.setattr(_dk_rev_view, "next_revision_no", lambda locked: 1)

    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_chain_a.pk),
                         {"file": _dk_txt("collide.txt", b"Colliding upload."),
                          "change_note": "Collides with r1"})
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_chain_a.pk)
    assert _dk_said(resp, "Nothing was saved")
    assert dk_document_chain_a.revisions.count() == 2


def test_dk_revision_approve_moves_the_pointer_and_copies_the_text_up(
        client_a, admin_user, dk_document_chain_a, dk_revision_pending_a):
    resp = _dk_post(client_a, "pdocrevision_approve", dk_revision_pending_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_chain_a.pk)

    dk_revision_pending_a.refresh_from_db()
    assert dk_revision_pending_a.is_approved is True
    assert dk_revision_pending_a.approved_by_id == admin_user.pk
    assert dk_revision_pending_a.approved_at is not None

    dk_document_chain_a.refresh_from_db()
    assert dk_document_chain_a.current_revision_no == 2
    assert "out-of-hours" in dk_document_chain_a.extracted_text
    assert "soleplate" not in dk_document_chain_a.extracted_text


def test_dk_revision_approve_lifts_a_draft_document_to_active(
        client_a, tenant_a, admin_user, dk_media_root):
    document = _dk_document(tenant_a, title="Fresh sow", created_by=admin_user)
    revision = _dk_revision(document, filename="sow-r1.txt", uploaded_by=admin_user,
                            body=b"Statement of work, first issue.")
    assert document.status == "draft"

    resp = _dk_post(client_a, "pdocrevision_approve", revision.pk)
    assert resp.status_code == 302
    document.refresh_from_db()
    assert document.status == "active"
    assert document.current_revision_no == 1


def test_dk_revision_approve_leaves_earlier_approved_revisions_on_the_record(
        client_a, dk_document_chain_a, dk_revision_approved_a, dk_revision_pending_a):
    _dk_post(client_a, "pdocrevision_approve", dk_revision_pending_a.pk)
    dk_revision_approved_a.refresh_from_db()
    assert dk_revision_approved_a.is_approved is True
    assert dk_revision_approved_a.is_current is False


def test_dk_revision_approve_on_an_approved_revision_reports_and_writes_nothing(
        client_a, dk_document_chain_a, dk_revision_approved_a):
    stamped = dk_revision_approved_a.approved_at
    resp = _dk_post(client_a, "pdocrevision_approve", dk_revision_approved_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "is already approved")
    dk_revision_approved_a.refresh_from_db()
    assert dk_revision_approved_a.approved_at == stamped
    dk_document_chain_a.refresh_from_db()
    assert dk_document_chain_a.current_revision_no == 1


def test_dk_revision_approve_refuses_a_revision_at_or_behind_the_pointer(
        client_a, tenant_a, admin_user, dk_media_root):
    """The rule that makes the pointer mean something: the chain only moves FORWARD.

    Two pending revisions; r2 is approved first, so the pointer is on 2. r1 - still pending, so
    the idempotent branch above cannot absorb it - must then be refused rather than walking the
    pointer backwards.
    """
    document = _dk_document(tenant_a, title="Two pending issues", created_by=admin_user)
    first = _dk_revision(document, filename="tp-r1.txt", uploaded_by=admin_user,
                         body=b"First issue with the backwardbeacon phrase.")
    second = _dk_revision(document, filename="tp-r2.txt", uploaded_by=admin_user,
                          body=b"Second issue with the forwardbeacon phrase.")

    assert _dk_post(client_a, "pdocrevision_approve", second.pk).status_code == 302
    document.refresh_from_db()
    assert document.current_revision_no == 2

    resp = _dk_post(client_a, "pdocrevision_approve", first.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "only moves forward")
    first.refresh_from_db()
    assert first.is_approved is False
    document.refresh_from_db()
    assert document.current_revision_no == 2
    assert "forwardbeacon" in document.extracted_text


def test_dk_revision_delete_removes_a_pending_non_current_revision(
        client_a, dk_document_chain_a, dk_revision_pending_a):
    resp = _dk_post(client_a, "pdocrevision_delete", dk_revision_pending_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_chain_a.pk)
    assert not ProcurementDocumentRevision.objects.filter(pk=dk_revision_pending_a.pk).exists()
    dk_document_chain_a.refresh_from_db()
    assert dk_document_chain_a.current_revision_no == 1


def test_dk_revision_delete_refuses_an_approved_revision(
        client_a, dk_revision_approved_a):
    """I3, guard one: approved history is never rewritten here."""
    resp = _dk_post(client_a, "pdocrevision_delete", dk_revision_approved_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "is approved, so it stays on the record")
    assert ProcurementDocumentRevision.objects.filter(pk=dk_revision_approved_a.pk).exists()


def test_dk_revision_delete_refuses_the_revision_the_pointer_names(
        client_a, dk_document_chain_a, dk_revision_pending_a):
    """I3, guard two: a pending row the pointer happens to name is still off limits."""
    _dk_reset_pointer(dk_document_chain_a, 2)
    resp = _dk_post(client_a, "pdocrevision_delete", dk_revision_pending_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "currently points at")
    assert ProcurementDocumentRevision.objects.filter(pk=dk_revision_pending_a.pk).exists()


def test_dk_revision_delete_is_not_administrator_gated(
        member_client, dk_document_chain_a, dk_revision_pending_a):
    """Removing a mis-upload of your own is ordinary work; only APPROVAL needs an administrator."""
    resp = _dk_post(member_client, "pdocrevision_delete", dk_revision_pending_a.pk)
    assert resp.status_code == 302
    assert not ProcurementDocumentRevision.objects.filter(pk=dk_revision_pending_a.pk).exists()


# =================================================================================================
# 8. The download route (C1)
# =================================================================================================

def test_dk_revision_download_hands_back_the_bytes_as_an_attachment(
        client_a, dk_document_chain_a, dk_revision_approved_a):
    resp = _dk_get(client_a, "pdocrevision_download", dk_revision_approved_a.pk)
    try:
        assert resp.status_code == 200
        assert "attachment" in resp["Content-Disposition"]
        assert dk_revision_approved_a.original_filename in resp["Content-Disposition"]
        # WARNING territory: an uploaded .html or .svg served INLINE would be stored XSS against
        # every logged-in member, and a sniffing browser can undo a declared type.
        assert resp["X-Content-Type-Options"] == "nosniff"
        body = b"".join(resp.streaming_content)
        assert b"soleplate" in body
        assert len(body) == dk_revision_approved_a.file_size
    finally:
        resp.close()


def test_dk_revision_download_of_a_row_with_no_stored_file_redirects_with_a_message(
        client_a, dk_revision_no_file_a):
    """The row can outlive its bytes; that is a message on the page, never a 500."""
    resp = _dk_get(client_a, "pdocrevision_download", dk_revision_no_file_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocrevision_detail", dk_revision_no_file_a.pk)
    assert _dk_said(resp, "has no stored file")


def test_dk_revision_download_survives_bytes_removed_behind_djangos_back(
        client_a, dk_revision_approved_a):
    import os

    path = dk_revision_approved_a.file.path
    os.remove(path)
    resp = _dk_get(client_a, "pdocrevision_download", dk_revision_approved_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "could not be read back from storage")


def test_dk_revision_register_links_the_download_route_not_the_media_url(
        client_a, dk_document_chain_a, dk_revision_approved_a):
    """``file.url`` is a raw MEDIA_URL path with no login, no session and no tenant."""
    resp = _dk_get(client_a, "pdocrevision_list")
    body = _dk_body(resp)
    assert _dk_url("pdocrevision_download", dk_revision_approved_a.pk) in body
    assert dk_revision_approved_a.file.url not in body


# =================================================================================================
# 9. The policy verbs' state machines
# =================================================================================================

def test_dk_policy_publish_puts_a_draft_in_force_and_archives_its_predecessor(
        client_a, dk_policy_published_a, dk_policy_draft_a):
    resp = _dk_post(client_a, "ppolicy_publish", dk_policy_draft_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("ppolicy_detail", dk_policy_draft_a.pk)
    assert _dk_said(resp, "is now published")

    dk_policy_draft_a.refresh_from_db()
    assert dk_policy_draft_a.status == "published"
    assert dk_policy_draft_a.published_at is not None

    dk_policy_published_a.refresh_from_db()
    assert dk_policy_published_a.status == "archived"


def test_dk_policy_publish_leaves_a_draft_predecessor_alone(
        client_a, tenant_a, admin_user):
    """Archiving somebody's work in progress is destructive - only a PUBLISHED one is retired."""
    first = _dk_policy(tenant_a, title="Ethics and Conflict of Interest", version_number="1.0",
                       policy_type="ethics_conflict", created_by=admin_user)
    second = _dk_policy(tenant_a, title="Ethics and Conflict of Interest", version_number="2.0",
                        policy_type="ethics_conflict", previous_version=first,
                        created_by=admin_user)
    _dk_post(client_a, "ppolicy_publish", second.pk)
    first.refresh_from_db()
    assert first.status == "draft"


def test_dk_policy_publish_on_a_published_policy_reports_and_writes_nothing(
        client_a, dk_policy_published_a):
    stamped = dk_policy_published_a.published_at
    resp = _dk_post(client_a, "ppolicy_publish", dk_policy_published_a.pk)
    assert _dk_said(resp, "is already published")
    dk_policy_published_a.refresh_from_db()
    assert dk_policy_published_a.published_at == stamped


def test_dk_policy_publish_is_refused_on_an_archived_policy(
        client_a, dk_policy_v1_archived_a):
    resp = _dk_post(client_a, "ppolicy_publish", dk_policy_v1_archived_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "is archived and cannot be published again")
    dk_policy_v1_archived_a.refresh_from_db()
    assert dk_policy_v1_archived_a.status == "archived"


def test_dk_policy_archive_retires_a_policy_without_clearing_published_at(
        client_a, dk_policy_published_a):
    stamped = dk_policy_published_a.published_at
    resp = _dk_post(client_a, "ppolicy_archive", dk_policy_published_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "Nothing was deleted")
    dk_policy_published_a.refresh_from_db()
    assert dk_policy_published_a.status == "archived"
    # The stamp is the only evidence of the period the rule was in force.
    assert dk_policy_published_a.published_at == stamped


def test_dk_policy_archive_on_an_archived_policy_reports_and_writes_nothing(
        client_a, dk_policy_v1_archived_a):
    before = dk_policy_v1_archived_a.updated_at
    resp = _dk_post(client_a, "ppolicy_archive", dk_policy_v1_archived_a.pk)
    assert _dk_said(resp, "is already archived")
    dk_policy_v1_archived_a.refresh_from_db()
    assert dk_policy_v1_archived_a.updated_at == before


# =================================================================================================
# 10. The knowledge-resource verbs' state machines
# =================================================================================================

def test_dk_resource_publish_puts_a_draft_on_the_shelf(client_a, dk_resource_draft_a):
    resp = _dk_post(client_a, "knowledgeresource_publish", dk_resource_draft_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("knowledgeresource_detail", dk_resource_draft_a.pk)
    dk_resource_draft_a.refresh_from_db()
    assert dk_resource_draft_a.status == "published"


def test_dk_resource_publish_brings_an_archived_resource_back(
        client_a, dk_resource_archived_a):
    """Unlike a policy: guidance comes back into use, and there is no "in force when" to
    rewrite by doing so."""
    resp = _dk_post(client_a, "knowledgeresource_publish", dk_resource_archived_a.pk)
    assert resp.status_code == 302
    dk_resource_archived_a.refresh_from_db()
    assert dk_resource_archived_a.status == "published"


def test_dk_resource_publish_on_a_published_resource_reports_and_writes_nothing(
        client_a, dk_resource_published_a):
    before = dk_resource_published_a.updated_at
    resp = _dk_post(client_a, "knowledgeresource_publish", dk_resource_published_a.pk)
    assert _dk_said(resp, "is already published")
    dk_resource_published_a.refresh_from_db()
    assert dk_resource_published_a.updated_at == before


def test_dk_resource_archive_keeps_the_star_and_the_counter(
        client_a, dk_resource_featured_a):
    resp = _dk_post(client_a, "knowledgeresource_archive", dk_resource_featured_a.pk)
    assert resp.status_code == 302
    dk_resource_featured_a.refresh_from_db()
    assert dk_resource_featured_a.status == "archived"
    # The shelf query already requires published, so clearing the star would only lose a choice.
    assert dk_resource_featured_a.is_featured is True


def test_dk_resource_archive_on_an_archived_resource_reports_and_writes_nothing(
        client_a, dk_resource_archived_a):
    before = dk_resource_archived_a.updated_at
    resp = _dk_post(client_a, "knowledgeresource_archive", dk_resource_archived_a.pk)
    assert _dk_said(resp, "is already archived")
    dk_resource_archived_a.refresh_from_db()
    assert dk_resource_archived_a.updated_at == before


def test_dk_resource_use_increments_the_counter_atomically(
        client_a, dk_resource_used_a):
    """``F("usage_count") + 1`` is evaluated by the database - the counter really moves 7 -> 8."""
    before_used_at = dk_resource_used_a.last_used_at
    resp = _dk_post(client_a, "knowledgeresource_use", dk_resource_used_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("knowledgeresource_detail", dk_resource_used_a.pk)
    dk_resource_used_a.refresh_from_db()
    assert dk_resource_used_a.usage_count == 8
    assert dk_resource_used_a.last_used_at > before_used_at
    assert _dk_said(resp, "used 8 time(s)")


def test_dk_resource_use_pressed_twice_lands_on_nine(client_a, dk_resource_used_a):
    _dk_post(client_a, "knowledgeresource_use", dk_resource_used_a.pk)
    _dk_post(client_a, "knowledgeresource_use", dk_resource_used_a.pk)
    dk_resource_used_a.refresh_from_db()
    assert dk_resource_used_a.usage_count == 9


def test_dk_resource_use_is_refused_on_an_archived_resource(
        client_a, dk_resource_archived_a):
    resp = _dk_post(client_a, "knowledgeresource_use", dk_resource_archived_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "is archived, so it is not counted as in use")
    dk_resource_archived_a.refresh_from_db()
    assert dk_resource_archived_a.usage_count == 0
    assert dk_resource_archived_a.last_used_at is None


def test_dk_resource_use_refuses_at_the_usage_count_ceiling(client_a, dk_resource_used_a):
    """M24/Q2: the tally has run out of room; the fact that it was used has not."""
    KnowledgeResource.objects.filter(pk=dk_resource_used_a.pk).update(
        usage_count=USAGE_COUNT_CEILING)
    dk_resource_used_a.refresh_from_db()
    before_used_at = dk_resource_used_a.last_used_at

    resp = _dk_post(client_a, "knowledgeresource_use", dk_resource_used_a.pk)
    assert resp.status_code == 302
    assert _dk_said(resp, "reached the maximum")
    dk_resource_used_a.refresh_from_db()
    assert dk_resource_used_a.usage_count == USAGE_COUNT_CEILING
    assert dk_resource_used_a.last_used_at > before_used_at


def test_dk_resource_use_redirects_to_the_resource_not_to_a_file_url(
        client_a, dk_resource_featured_a, dk_document_active_a):
    """An open-redirect hop derived from stored data is what this deliberately does not do."""
    resp = _dk_post(client_a, "knowledgeresource_use", dk_resource_featured_a.pk)
    assert resp["Location"] == _dk_url("knowledgeresource_detail", dk_resource_featured_a.pk)


def test_dk_resource_verbs_are_not_administrator_gated(
        member_client, dk_resource_draft_a, dk_resource_published_a, dk_resource_used_a):
    """Guidance is not a control: none of the four library verbs needs an administrator."""
    assert _dk_post(member_client, "knowledgeresource_publish",
                    dk_resource_draft_a.pk).status_code == 302
    assert _dk_post(member_client, "knowledgeresource_use",
                    dk_resource_used_a.pk).status_code == 302
    assert _dk_post(member_client, "knowledgeresource_archive",
                    dk_resource_published_a.pk).status_code == 302
    assert _dk_post(member_client, "knowledgeresource_delete",
                    dk_resource_draft_a.pk).status_code == 302


# =================================================================================================
# 11. Search and filters - the rendered rows against the ORM's own answer
# =================================================================================================

def _dk_document_filter_case(client, tenant, params, orm_kwargs):
    """Assert the register's rows are exactly the ORM's answer for the same narrowing."""
    resp = client.get(_dk_url("pdocument_list"), params)
    assert resp.status_code == 200
    expected = set(ProcurementDocument.objects
                   .filter(tenant=tenant, **orm_kwargs)
                   .values_list("pk", flat=True))
    assert set(_dk_pks(resp)) == expected
    assert expected, "the fixture set made this filter vacuous"
    return resp


def test_dk_document_filter_doc_type(client_a, tenant_a, dk_document_active_a,
                                     dk_document_draft_a, dk_document_archived_a):
    _dk_document_filter_case(client_a, tenant_a, {"doc_type": "sow"}, {"doc_type": "sow"})


def test_dk_document_filter_status(client_a, tenant_a, dk_document_active_a,
                                   dk_document_draft_a, dk_document_superseded_a):
    _dk_document_filter_case(client_a, tenant_a, {"status": "active"}, {"status": "active"})


def test_dk_document_filter_classification(client_a, tenant_a, dk_document_public_a,
                                           dk_document_confidential_a, dk_document_draft_a):
    _dk_document_filter_case(client_a, tenant_a, {"classification": "public"},
                             {"classification": "public"})


def test_dk_document_filter_supplier(client_a, tenant_a, dk_supplier_a, dk_document_active_a,
                                     dk_document_draft_a):
    _dk_document_filter_case(client_a, tenant_a, {"supplier": str(dk_supplier_a.pk)},
                             {"supplier": dk_supplier_a})


def test_dk_document_filter_owner(client_a, tenant_a, admin_user, member_user,
                                  dk_document_draft_a, dk_document_confidential_member_a):
    _dk_document_filter_case(client_a, tenant_a, {"owner": str(member_user.pk)},
                             {"owner": member_user})


@pytest.mark.parametrize("value,fixture_name", [
    ("expiring", "dk_document_expiring_a"),
    ("expired", "dk_document_expired_a"),
    ("review_due", "dk_document_review_due_a"),
    ("over_retention", "dk_document_over_retention_a"),
])
def test_dk_document_expiry_facet_matches_exactly_its_row(
        client_a, request, value, fixture_name, dk_document_draft_a):
    """Each of the four ``EXPIRY_FILTER_CHOICES`` values is a date comparison against today."""
    target = request.getfixturevalue(fixture_name)
    resp = _dk_get(client_a, "pdocument_list", expiry=value)
    assert resp.status_code == 200
    assert _dk_pks(resp) == [target.pk]
    assert value in dict(EXPIRY_FILTER_CHOICES)


def test_dk_document_tag_facet_is_a_substring_match(
        client_a, tenant_a, dk_document_active_a, dk_document_chain_a, dk_document_draft_a):
    resp = _dk_get(client_a, "pdocument_list", tag="facilities")
    expected = set(ProcurementDocument.objects
                   .filter(tenant=tenant_a, tags__icontains="facilities")
                   .values_list("pk", flat=True))
    assert set(_dk_pks(resp)) == expected
    assert dk_document_draft_a.pk not in expected


def test_dk_document_search_matches_the_number_title_description_and_tags(
        client_a, dk_document_active_a, dk_document_draft_a):
    by_number = _dk_get(client_a, "pdocument_list", q=dk_document_active_a.number)
    assert _dk_pks(by_number) == [dk_document_active_a.pk]

    by_title = _dk_get(client_a, "pdocument_list", q="Grounds maintenance")
    assert _dk_pks(by_title) == [dk_document_active_a.pk]

    by_tag = _dk_get(client_a, "pdocument_list", q="specification")
    assert dk_document_draft_a.pk in _dk_pks(by_tag)


def test_dk_file_text_is_searched_only_from_four_characters(
        client_a, dk_document_public_a, dk_document_draft_a):
    """I15: ``?q=har`` finds nothing, ``?q=harb`` matches the file text. The boundary IS 4."""
    assert FILE_TEXT_SEARCH_MIN_CHARS == 4
    short = _dk_get(client_a, "pdocument_list", q="har")
    assert short.status_code == 200
    assert _dk_pks(short) == []

    long_enough = _dk_get(client_a, "pdocument_list", q="harb")
    assert _dk_pks(long_enough) == [dk_document_public_a.pk]

    whole = _dk_get(client_a, "pdocument_list", q="harborcoverage")
    assert _dk_pks(whole) == [dk_document_public_a.pk]


def test_dk_document_search_is_trimmed_before_the_length_test(
        client_a, dk_document_public_a):
    """``len(q.strip())`` - three characters padded to five is still three characters."""
    resp = _dk_get(client_a, "pdocument_list", q="  har  ")
    assert resp.context["q"] == "har"
    assert _dk_pks(resp) == []


def test_dk_document_filters_combine_rather_than_replace_one_another(
        client_a, tenant_a, dk_document_active_a, dk_document_public_a, dk_document_draft_a):
    resp = _dk_get(client_a, "pdocument_list", status="active", classification="internal")
    expected = set(ProcurementDocument.objects
                   .filter(tenant=tenant_a, status="active", classification="internal")
                   .values_list("pk", flat=True))
    assert set(_dk_pks(resp)) == expected
    assert dk_document_public_a.pk not in expected


def test_dk_document_search_and_a_facet_narrow_together(
        client_a, dk_document_active_a, dk_document_chain_a, dk_document_draft_a):
    """``?q=`` is applied by ``crud_list`` on top of the pre-narrowed facet queryset."""
    both = _dk_get(client_a, "pdocument_list", q="maintenance", doc_type="sow")
    assert set(_dk_pks(both)) == {dk_document_active_a.pk, dk_document_chain_a.pk}

    narrowed = _dk_get(client_a, "pdocument_list", q="maintenance", tag="facilities")
    assert set(_dk_pks(narrowed)) == {dk_document_active_a.pk, dk_document_chain_a.pk}

    contradictory = _dk_get(client_a, "pdocument_list", q="maintenance", status="archived")
    assert _dk_pks(contradictory) == []


def test_dk_revision_register_document_filter(
        client_a, dk_document_chain_a, dk_document_superseded_a, dk_revision_no_file_a):
    resp = _dk_get(client_a, "pdocrevision_list", document=str(dk_document_chain_a.pk))
    assert resp.status_code == 200
    assert set(_dk_pks(resp)) == set(
        dk_document_chain_a.revisions.values_list("pk", flat=True))
    assert dk_revision_no_file_a.pk not in _dk_pks(resp)


@pytest.mark.parametrize("value,is_approved", [("True", True), ("False", False)])
def test_dk_revision_register_approval_filter(
        client_a, tenant_a, value, is_approved, dk_document_chain_a):
    resp = _dk_get(client_a, "pdocrevision_list", approved=value)
    expected = set(ProcurementDocumentRevision.objects
                   .filter(tenant=tenant_a, is_approved=is_approved)
                   .values_list("pk", flat=True))
    assert set(_dk_pks(resp)) == expected
    assert expected


def test_dk_revision_register_search_matches_the_checksum_and_the_change_note(
        client_a, dk_revision_approved_a, dk_revision_pending_a):
    by_sha = _dk_get(client_a, "pdocrevision_list", q=dk_revision_approved_a.sha256)
    assert _dk_pks(by_sha) == [dk_revision_approved_a.pk]

    by_note = _dk_get(client_a, "pdocrevision_list", q="Section 4 rewritten")
    assert _dk_pks(by_note) == [dk_revision_pending_a.pk]


def test_dk_revision_register_search_reaches_through_the_parent(
        client_a, dk_document_chain_a, dk_revision_no_file_a):
    resp = _dk_get(client_a, "pdocrevision_list", q=dk_document_chain_a.number)
    assert set(_dk_pks(resp)) == set(dk_document_chain_a.revisions.values_list("pk", flat=True))


def test_dk_policy_filter_policy_type(client_a, tenant_a, dk_policy_published_a,
                                      dk_policy_review_due_a):
    resp = _dk_get(client_a, "ppolicy_list", policy_type="supplier_code_of_conduct")
    assert _dk_pks(resp) == [dk_policy_review_due_a.pk]


def test_dk_policy_filter_status(client_a, tenant_a, dk_policy_published_a, dk_policy_draft_a,
                                 dk_policy_v1_archived_a):
    resp = _dk_get(client_a, "ppolicy_list", status="published")
    expected = set(ProcurementPolicy.objects
                   .filter(tenant=tenant_a, status="published").values_list("pk", flat=True))
    assert set(_dk_pks(resp)) == expected
    assert dk_policy_draft_a.pk not in expected


def test_dk_policy_filter_org_unit(client_a, org_unit_a, dk_policy_published_a,
                                   dk_policy_review_due_a):
    resp = _dk_get(client_a, "ppolicy_list", org_unit=str(org_unit_a.pk))
    assert _dk_pks(resp) == [dk_policy_published_a.pk]


def test_dk_policy_review_facet_matches_the_badge_and_the_tile(
        client_a, dk_policy_published_a, dk_policy_review_due_a):
    resp = _dk_get(client_a, "ppolicy_list", review="due")
    assert _dk_pks(resp) == [dk_policy_review_due_a.pk]
    assert resp.context["stats"]["review_due"] == 1


def test_dk_policy_search_reaches_the_rule_as_written(
        client_a, tenant_a, admin_user, dk_policy_published_a):
    """A buyer looks for "three quotes", not for PPOL-00007 - so ``body`` is a search field."""
    unique = _dk_policy(tenant_a, title="Sustainability Sourcing Rule",
                        policy_type="sustainability", version_number="1.0",
                        created_by=admin_user,
                        body="Ties are broken by the lower embodied carbonbeacon figure.")
    by_body = _dk_get(client_a, "ppolicy_list", q="carbonbeacon")
    assert _dk_pks(by_body) == [unique.pk]

    by_title = _dk_get(client_a, "ppolicy_list", q="Competitive Bidding")
    assert dk_policy_published_a.pk in _dk_pks(by_title)
    assert unique.pk not in _dk_pks(by_title)


@pytest.mark.parametrize("param,value,orm", [
    ("resource_type", "checklist", {"resource_type": "checklist"}),
    ("category", "it_software", {"category": "it_software"}),
    ("audience", "approver", {"audience": "approver"}),
    ("status", "published", {"status": "published"}),
    ("featured", "True", {"is_featured": True}),
    ("featured", "False", {"is_featured": False}),
])
def test_dk_knowledge_filters_match_the_orms_own_answer(
        client_a, tenant_a, param, value, orm, dk_resource_featured_a, dk_resource_published_a,
        dk_resource_draft_a, dk_resource_archived_a):
    resp = _dk_get(client_a, "knowledgeresource_list", **{param: value})
    assert resp.status_code == 200
    expected = set(KnowledgeResource.objects
                   .filter(tenant=tenant_a, **orm).values_list("pk", flat=True))
    assert set(_dk_pks(resp)) == expected
    assert expected


def test_dk_knowledge_search_matches_the_guidance_body_and_the_tags(
        client_a, dk_resource_featured_a, dk_resource_published_a):
    by_tag = _dk_get(client_a, "knowledgeresource_list", q="checklist")
    assert dk_resource_published_a.pk in _dk_pks(by_tag)

    by_body = _dk_get(client_a, "knowledgeresource_list", q="evaluation grid")
    assert set(_dk_pks(by_body)) == {dk_resource_featured_a.pk, dk_resource_published_a.pk}


# =================================================================================================
# 12. Junk parameters - 200 with the FULL register, never a 500 and never an empty page (L9/L11)
# =================================================================================================

_DK_JUNK_PAGES = ["abc", "-1", "0", "99999", "", "1e5", "NaN", "9" * 25]


@pytest.mark.parametrize("route", _DK_LIST_ROUTES)
@pytest.mark.parametrize("page", _DK_JUNK_PAGES)
def test_dk_a_junk_page_parameter_never_500s_any_register(
        client_a, route, page, dk_document_chain_a, dk_policy_published_a,
        dk_resource_featured_a):
    resp = _dk_get(client_a, route, page=page)
    assert resp.status_code == 200
    assert resp.context["page_obj"] is not None


@pytest.mark.parametrize("params", [
    {"supplier": "abc"}, {"supplier": "0"}, {"supplier": "9" * 25}, {"supplier": "NaN"},
    {"supplier": "-1"}, {"owner": "abc"}, {"owner": "NaN"},
    {"doc_type": "nope"}, {"status": "nope"}, {"status": "<script>alert(1)</script>"},
    {"classification": "nope"}, {"expiry": "nope"}, {"expiry": ""}, {"tag": ""},
])
def test_dk_junk_document_filters_return_the_full_register(
        client_a, params, dk_document_active_a, dk_document_draft_a, dk_document_public_a):
    resp = _dk_get(client_a, "pdocument_list", **params)
    assert resp.status_code == 200
    assert len(_dk_pks(resp)) == 3, f"{params} narrowed the register instead of being skipped"
    assert "<script>alert(1)</script>" not in _dk_body(resp)


@pytest.mark.parametrize("params", [
    {"document": "abc"}, {"document": "0"}, {"document": "NaN"}, {"document": "9" * 25},
    {"approved": "maybe"}, {"approved": "<script>"},
])
def test_dk_junk_revision_filters_return_the_full_register(
        client_a, params, dk_document_chain_a):
    resp = _dk_get(client_a, "pdocrevision_list", **params)
    assert resp.status_code == 200
    assert len(_dk_pks(resp)) == 2


@pytest.mark.parametrize("params", [
    {"org_unit": "abc"}, {"org_unit": "0"}, {"org_unit": "NaN"}, {"review": "nope"},
    {"policy_type": "nope"}, {"status": "nope"},
])
def test_dk_junk_policy_filters_return_the_full_register(
        client_a, params, dk_policy_published_a, dk_policy_draft_a, dk_policy_v1_archived_a):
    resp = _dk_get(client_a, "ppolicy_list", **params)
    assert resp.status_code == 200
    assert len(_dk_pks(resp)) == 3


@pytest.mark.parametrize("params", [
    {"featured": "maybe"}, {"featured": "NaN"}, {"category": "nope"}, {"audience": "nope"},
    {"resource_type": "nope"}, {"status": "nope"},
])
def test_dk_junk_knowledge_filters_return_the_full_register(
        client_a, params, dk_resource_featured_a, dk_resource_published_a, dk_resource_draft_a):
    resp = _dk_get(client_a, "knowledgeresource_list", **params)
    assert resp.status_code == 200
    assert len(_dk_pks(resp)) == 3


@pytest.mark.parametrize("route", _DK_LIST_ROUTES)
def test_dk_an_unknown_parameter_is_simply_ignored(
        client_a, route, dk_document_chain_a, dk_policy_published_a, dk_resource_featured_a):
    baseline = len(_dk_pks(_dk_get(client_a, route)))
    resp = _dk_get(client_a, route, wibble="1", order_by="password")
    assert resp.status_code == 200
    assert len(_dk_pks(resp)) == baseline


# =================================================================================================
# 13. Pagination (L9)
# =================================================================================================

def test_dk_document_register_paginates_at_fifteen_with_a_real_page_two(
        client_a, dk_documents_page2_a):
    assert len(dk_documents_page2_a) == 16
    page1 = _dk_get(client_a, "pdocument_list")
    page2 = _dk_get(client_a, "pdocument_list", page="2")
    assert page1.status_code == page2.status_code == 200

    first = _dk_pks(page1)
    second = _dk_pks(page2)
    assert len(first) == _DK_PER_PAGE
    assert len(second) == 1
    assert not set(first) & set(second), "page 2 repeated a row from page 1"
    assert set(first) | set(second) == {row.pk for row in dk_documents_page2_a}
    assert page1.context["page_obj"].paginator.num_pages == 2


def test_dk_document_register_page_window_carries_the_ellipsis_list(
        client_a, dk_documents_page2_a):
    resp = _dk_get(client_a, "pdocument_list")
    assert resp.context["page_obj"].window == [1, 2]


@pytest.mark.parametrize("page,expected_number", [
    ("1", 1), ("2", 2), ("999", 2), ("-1", 2), ("0", 2), ("abc", 1),
])
def test_dk_document_register_page_guards_land_on_a_real_page(
        client_a, dk_documents_page2_a, page, expected_number):
    """Past the end -> the LAST page; unparseable -> page 1. Never a 404 and never a 500."""
    resp = _dk_get(client_a, "pdocument_list", page=page)
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == expected_number


def test_dk_knowledge_register_pages_are_disjoint_under_its_featured_first_ordering(
        client_a, tenant_a, dk_resource_featured_a):
    """``-is_featured, -created_at, -id`` - the unique id tiebreak is a PAGINATION invariant.

    Rows created inside the same clock tick tie on ``created_at``; without the id the paginator
    can repeat one row on page 2 while dropping another.
    """
    rows = [_dk_resource(tenant_a, title=f"Filler guide {i:02d}") for i in range(1, 20)]
    assert len(rows) == 19
    first = _dk_pks(_dk_get(client_a, "knowledgeresource_list"))
    second = _dk_pks(_dk_get(client_a, "knowledgeresource_list", page="2"))
    assert len(first) == _DK_PER_PAGE
    assert len(second) == 5
    assert not set(first) & set(second)
    # The featured row sorts first whatever page it would otherwise have landed on.
    assert first[0] == dk_resource_featured_a.pk


def test_dk_filters_survive_pagination(client_a, tenant_a, dk_documents_page2_a):
    """A facet applied BEFORE pagination is the only ordering that gives honest page counts."""
    resp = _dk_get(client_a, "pdocument_list", status="active", page="2")
    assert resp.status_code == 200
    assert resp.context["page_obj"].paginator.count == 16


# =================================================================================================
# 14. Query budgets (the contract's measured numbers) and the flat-in-row-count proof
# =================================================================================================

def test_dk_document_register_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_document_active_a, dk_document_chain_a,
        dk_documents_page2_a):
    _dk_get(client_a, "pdocument_list")  # warm the session / content-type caches
    with django_assert_max_num_queries(14):
        assert _dk_get(client_a, "pdocument_list").status_code == 200


def test_dk_document_register_page_two_costs_the_same_as_page_one(
        client_a, django_assert_max_num_queries, dk_documents_page2_a):
    _dk_get(client_a, "pdocument_list")
    with django_assert_max_num_queries(14):
        assert _dk_get(client_a, "pdocument_list", page="2").status_code == 200


def test_dk_document_register_cost_is_flat_in_the_row_count(
        client_a, tenant_a, admin_user, dk_supplier_a, django_assert_max_num_queries):
    """The N+1 that matters: ``supplier.name`` and ``owner.username`` on every row."""
    _dk_documents(tenant_a, 3, supplier=dk_supplier_a, owner=admin_user)
    _dk_get(client_a, "pdocument_list")
    with django_assert_max_num_queries(14):
        _dk_get(client_a, "pdocument_list")

    _dk_documents(tenant_a, 10, supplier=dk_supplier_a, owner=admin_user)
    with django_assert_max_num_queries(14):
        resp = _dk_get(client_a, "pdocument_list")
    assert len(_dk_pks(resp)) == 13


def test_dk_document_detail_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_document_chain_a, dk_policy_published_a,
        dk_resource_featured_a):
    _dk_get(client_a, "pdocument_detail", dk_document_chain_a.pk)
    with django_assert_max_num_queries(13):
        assert _dk_get(client_a, "pdocument_detail",
                       dk_document_chain_a.pk).status_code == 200


def test_dk_revision_register_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_document_chain_a):
    _dk_get(client_a, "pdocrevision_list")
    with django_assert_max_num_queries(13):
        assert _dk_get(client_a, "pdocrevision_list").status_code == 200


def test_dk_revision_register_cost_is_flat_in_the_row_count(
        client_a, tenant_a, admin_user, dk_document_chain_a, dk_media_root,
        django_assert_max_num_queries):
    """Every row prints ``r.document.number`` and ``r.uploaded_by.username`` - three FK hops."""
    _dk_get(client_a, "pdocrevision_list")
    with django_assert_max_num_queries(13):
        _dk_get(client_a, "pdocrevision_list")

    for index in range(10):
        document = _dk_document(tenant_a, title=f"Extra chain {index:02d}",
                                created_by=admin_user)
        _dk_revision(document, filename=f"x{index:02d}.txt", uploaded_by=admin_user,
                     body=b"Extra body text.")
    with django_assert_max_num_queries(13):
        resp = _dk_get(client_a, "pdocrevision_list")
    assert len(_dk_pks(resp)) == 12


def test_dk_revision_detail_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_revision_approved_a):
    _dk_get(client_a, "pdocrevision_detail", dk_revision_approved_a.pk)
    with django_assert_max_num_queries(10):
        assert _dk_get(client_a, "pdocrevision_detail",
                       dk_revision_approved_a.pk).status_code == 200


def test_dk_policy_register_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_policy_published_a, dk_policy_draft_a,
        dk_policy_review_due_a):
    _dk_get(client_a, "ppolicy_list")
    with django_assert_max_num_queries(13):
        assert _dk_get(client_a, "ppolicy_list").status_code == 200


def test_dk_policy_register_cost_is_flat_in_the_row_count(
        client_a, tenant_a, admin_user, usd, org_unit_a, django_assert_max_num_queries):
    """``threshold_label`` reads ``threshold_currency.code`` on every row that carries one."""
    from decimal import Decimal

    for index in range(2):
        _dk_policy(tenant_a, title=f"Warm-up rule {index}", version_number="1.0",
                   owner=admin_user, applies_to=org_unit_a, threshold_currency=usd,
                   threshold_amount=Decimal("100.00"), threshold_basis="per_line")
    _dk_get(client_a, "ppolicy_list")
    with django_assert_max_num_queries(13):
        _dk_get(client_a, "ppolicy_list")

    for index in range(10):
        _dk_policy(tenant_a, title=f"Priced rule {index:02d}", version_number="1.0",
                   owner=admin_user, applies_to=org_unit_a, threshold_currency=usd,
                   threshold_amount=Decimal("250.00"), threshold_basis="per_purchase_order")
    with django_assert_max_num_queries(13):
        resp = _dk_get(client_a, "ppolicy_list")
    assert len(_dk_pks(resp)) == 12


def test_dk_policy_detail_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_policy_published_a, dk_policy_draft_a):
    _dk_get(client_a, "ppolicy_detail", dk_policy_published_a.pk)
    with django_assert_max_num_queries(11):
        assert _dk_get(client_a, "ppolicy_detail",
                       dk_policy_published_a.pk).status_code == 200


def test_dk_knowledge_register_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_resource_featured_a,
        dk_resource_published_a, dk_resource_used_a):
    _dk_get(client_a, "knowledgeresource_list")
    with django_assert_max_num_queries(13):
        assert _dk_get(client_a, "knowledgeresource_list").status_code == 200


def test_dk_knowledge_register_cost_is_flat_in_the_row_count(
        client_a, tenant_a, admin_user, dk_document_active_a, django_assert_max_num_queries):
    for index in range(2):
        _dk_resource(tenant_a, title=f"Warm-up guide {index}", owner=admin_user,
                     document=dk_document_active_a)
    _dk_get(client_a, "knowledgeresource_list")
    with django_assert_max_num_queries(13):
        _dk_get(client_a, "knowledgeresource_list")

    for index in range(10):
        _dk_resource(tenant_a, title=f"Extra guide {index:02d}", owner=admin_user,
                     document=dk_document_active_a)
    with django_assert_max_num_queries(13):
        resp = _dk_get(client_a, "knowledgeresource_list")
    assert len(_dk_pks(resp)) == 12


def test_dk_knowledge_detail_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_resource_featured_a):
    _dk_get(client_a, "knowledgeresource_detail", dk_resource_featured_a.pk)
    with django_assert_max_num_queries(10):
        assert _dk_get(client_a, "knowledgeresource_detail",
                       dk_resource_featured_a.pk).status_code == 200


@pytest.mark.parametrize("route,ceiling", [("pdocument_create", 14), ("ppolicy_create", 14),
                                           ("knowledgeresource_create", 11)])
def test_dk_create_forms_stay_inside_their_query_budget(
        client_a, django_assert_max_num_queries, route, ceiling, dk_document_active_a,
        dk_supplier_a, usd, org_unit_a):
    _dk_get(client_a, route)
    with django_assert_max_num_queries(ceiling):
        assert _dk_get(client_a, route).status_code == 200


def test_dk_revision_upload_page_stays_inside_its_query_budget(
        client_a, django_assert_max_num_queries, dk_document_draft_a):
    _dk_get(client_a, "pdocument_revision_upload", dk_document_draft_a.pk)
    with django_assert_max_num_queries(10):
        assert _dk_get(client_a, "pdocument_revision_upload",
                       dk_document_draft_a.pk).status_code == 200


def test_dk_registers_defer_the_text_columns_they_never_render(
        client_a, dk_document_chain_a, dk_resource_featured_a):
    """I14, measured off the queryset the page actually built."""
    documents = _dk_get(client_a, "pdocument_list").context["object_list"].query
    assert documents.deferred_loading == (frozenset({"extracted_text"}), True)
    assert set(documents.select_related) == {"supplier", "owner"}

    revisions = _dk_get(client_a, "pdocrevision_list").context["object_list"].query
    assert revisions.deferred_loading == (
        frozenset({"extracted_text", "document__extracted_text"}), True)

    resources = _dk_get(client_a, "knowledgeresource_list").context["object_list"].query
    assert resources.select_related is False


# =================================================================================================
# 15. Boundary notes rendered where they are read
# =================================================================================================

@pytest.mark.parametrize("route,args_fixture", [
    ("pdocument_list", None), ("pdocument_create", None), ("pdocument_detail", "document"),
    ("pdocument_edit", "document"),
])
def test_dk_the_classification_note_is_on_all_four_document_surfaces(
        client_a, route, args_fixture, dk_document_active_a):
    """The tier is ENFORCED (I5), so the four places somebody learns what it does must say so."""
    args = [dk_document_active_a.pk] if args_fixture else []
    resp = _dk_get(client_a, route, *args)
    assert resp.status_code == 200
    assert resp.context["classification_note"] == CLASSIFICATION_NOTE
    assert "Confidential and Restricted" in _dk_body(resp)


def test_dk_the_advisory_note_says_a_policy_threshold_routes_nothing(
        client_a, dk_policy_published_a):
    resp = _dk_get(client_a, "ppolicy_detail", dk_policy_published_a.pk)
    assert resp.context["advisory_note"] == ADVISORY_NOTE
    # An apostrophe-free fragment: Django escapes "Engine's" on the way out.
    assert "It enforces nothing on its own" in _dk_body(resp)


def test_dk_the_revision_note_says_there_is_no_edit(client_a, dk_revision_approved_a):
    resp = _dk_get(client_a, "pdocrevision_detail", dk_revision_approved_a.pk)
    assert "There is no edit." in resp.context["revision_note"]
    assert "A revision is immutable." in _dk_body(resp)
    assert "There is no edit." in _dk_body(resp)


def test_dk_the_library_note_is_on_the_register_and_the_detail_page(
        client_a, dk_resource_featured_a):
    register = _dk_get(client_a, "knowledgeresource_list")
    detail = _dk_get(client_a, "knowledgeresource_detail", dk_resource_featured_a.pk)
    assert register.context["library_note"] == LIBRARY_NOTE
    assert detail.context["library_note"] == LIBRARY_NOTE


# =================================================================================================
# 16. Empty-state pages - a register with nothing in it still renders
# =================================================================================================

@pytest.mark.parametrize("route", _DK_LIST_ROUTES)
def test_dk_an_empty_register_renders_its_empty_state(client_a, route):
    resp = _dk_get(client_a, route)
    assert resp.status_code == 200
    assert _dk_pks(resp) == []
    assert resp.context["page_obj"].paginator.count == 0
    assert resp.context["stats"]["total"] == 0


def test_dk_an_empty_document_register_still_offers_its_facets(client_a):
    resp = _dk_get(client_a, "pdocument_list")
    assert list(resp.context["doc_type_choices"])
    assert list(resp.context["status_choices"])
    assert list(resp.context["classification_choices"])
    assert list(resp.context["expiry_choices"])


def test_dk_a_search_that_matches_nothing_is_an_empty_page_not_an_error(
        client_a, dk_document_active_a):
    resp = _dk_get(client_a, "pdocument_list", q="zzzznothingmatchesthis")
    assert resp.status_code == 200
    assert _dk_pks(resp) == []
    assert resp.context["q"] == "zzzznothingmatchesthis"
    # The tiles count the workspace, not the filtered page, so they keep meaning something.
    assert resp.context["stats"]["total"] == 1


# =================================================================================================
# 17. Determinism of the date-driven facets (L16)
# =================================================================================================

def test_dk_the_expiry_facets_use_the_same_date_basis_as_the_model(
        client_a, tenant_a, admin_user):
    """Both sides derive from ``timezone.localdate()``; a row on today's boundary must agree."""
    today = timezone.localdate()
    edge = _dk_document(tenant_a, title="Cover expiring today", status="active",
                        owner=admin_user, created_by=admin_user, expires_on=today)
    assert edge.is_expiring is True
    assert edge.is_expired is False

    expiring = _dk_get(client_a, "pdocument_list", expiry="expiring")
    expired = _dk_get(client_a, "pdocument_list", expiry="expired")
    assert _dk_pks(expiring) == [edge.pk]
    assert _dk_pks(expired) == []


def test_dk_the_review_facet_includes_the_day_itself(client_a, tenant_a, admin_user):
    today = timezone.localdate()
    due = _dk_policy(tenant_a, title="Reviewed today", version_number="1.0",
                     created_by=admin_user, next_review_on=today)
    later = _dk_policy(tenant_a, title="Reviewed later", version_number="1.0",
                       created_by=admin_user,
                       next_review_on=today + datetime.timedelta(days=1))
    resp = _dk_get(client_a, "ppolicy_list", review="due")
    assert _dk_pks(resp) == [due.pk]
    assert later.pk not in _dk_pks(resp)
