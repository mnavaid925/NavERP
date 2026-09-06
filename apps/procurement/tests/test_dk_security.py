"""Procurement 6.19 - Document & Knowledge Management SECURITY tests.

The fourth and last 6.19 lane. Models, forms and the functional half of the HTTP layer are owned
by ``test_dk_models.py`` / ``test_dk_forms.py`` / ``test_dk_views.py``; this file owns the three
questions those three do not ask: **who may reach it, whose workspace is it, and what does the
answer disclose.**

What it locks down, finding by finding:

* **C1 - the unauthenticated file read.** Before the fix every stored document was a raw
  ``MEDIA_URL`` path: no login, no session, no tenant, and ``Content-Disposition: attachment``
  documented in five places and implemented in none. ``pdocrevision_download`` is now the only
  way to the bytes, so this lane asserts the whole guard - anonymous is turned away, another
  workspace 404s, a member who may not read the parent 404s, and the two headers that keep an
  uploaded ``.html`` from being stored XSS are on the response. The regression that would
  silently reopen it is a template going back to ``file.url``, so every 6.19 template is scanned
  for one.
* **I5 - classification enforcement.** ``confidential`` / ``restricted`` used to be a badge and
  nothing else. The rule is owner-or-creator-or-administrator, so this lane asserts BOTH halves:
  a member is absent the rows, the stat tiles, the facets, the revision chain, the download and
  every verb - and the member who OWNS one can still read their own.
  The sharpest of these is the **search oracle**: a phrase that exists only inside a restricted
  document's extracted text must return nothing for the member and the row for an administrator.
  ``?q=`` reaching a document the register will not list is a read of the file's contents by
  binary search, which is why it is asserted on its own and not folded into the register test.
* **I6 / I7 / I8 - the administrator gate.** Nine verbs answer a non-administrator with 403.
  Two of them are destructive across a relation: ``pdocument_delete`` CASCADEs an approved
  revision chain and ``ppolicy_delete`` CASCADEs 6.17's attestation ledger. The gate is asserted
  as a MATRIX - member POSTs every one of the 26 verbs and the 403 set must be exactly those
  nine - so a peer session that gates or ungates a verb fails here rather than in production.
* **Tenancy.** Every tenant-B pk on all 9 cross-tenant GET routes and all 19 POST routes is 404
  (never 403, which confirms the row exists, and never 500), the row is byte-for-byte unchanged
  afterwards, A's registers never contain B's rows and A's search never matches B's text.
* **CSRF and method safety**, and **mass assignment at the route** - the forms lane pins the
  field lists, this lane proves the ROUTE ignores a smuggled ``tenant`` / ``status`` /
  ``is_approved`` / ``usage_count`` / ``number`` / ``extracted_text``.

Conventions: every test ``test_dk_*`` and every module-level helper ``_dk_*`` (L47). Dates derive
from ``timezone.localdate()`` / ``timezone.now()`` (L16). Stored bytes land under
``dk_media_root``; nothing touches the network.

ONE KNOWN DEFECT IS ENCODED HERE AS A STRICT XFAIL - see
``test_dk_member_cannot_open_the_edit_form_of_a_confidential_document``. It is reported to the
parent session as a finding; the marker is a tripwire, not an excuse. Delete the marker in the
same change that fixes the view.
"""
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models import (
    KnowledgeResource,
    PolicyAttestation,
    ProcurementDocument,
    ProcurementDocumentRevision,
    ProcurementPolicy,
)
from apps.procurement.tests.conftest import _dk_document, _dk_revision
from apps.procurement.views._helpers import OPEN_CLASSIFICATIONS, readable_document_q

pytestmark = pytest.mark.django_db


# =================================================================================================
# Module-level helpers and route tables - all ``_dk_*`` / ``_DK_*`` so the next sub-module
# appending near this file cannot shadow them and so a failure names its own lane (L47).
# =================================================================================================

#: The nine routes that take no pk.
_DK_PK_LESS_ROUTES = (
    "pdocument_list", "pdocument_create", "pdocument_reindex", "pdocument_run_reminders",
    "pdocrevision_list", "ppolicy_list", "ppolicy_create",
    "knowledgeresource_list", "knowledgeresource_create",
)

#: The twenty-four routes that take one pk. 9 + 24 = the 33 routes the sub-module owns.
_DK_PK_ROUTES = (
    "pdocument_detail", "pdocument_edit", "pdocument_delete", "pdocument_checkout",
    "pdocument_release", "pdocument_activate", "pdocument_supersede", "pdocument_archive",
    "pdocument_revision_upload",
    "pdocrevision_detail", "pdocrevision_download", "pdocrevision_approve",
    "pdocrevision_delete",
    "ppolicy_detail", "ppolicy_edit", "ppolicy_delete", "ppolicy_publish", "ppolicy_archive",
    "knowledgeresource_detail", "knowledgeresource_edit", "knowledgeresource_delete",
    "knowledgeresource_publish", "knowledgeresource_archive", "knowledgeresource_use",
)

_DK_ALL_ROUTES = _DK_PK_LESS_ROUTES + _DK_PK_ROUTES

#: The nine verbs that answer a non-administrator with 403. Six of them became administrator-only
#: in the Phase 5 fix pass (I6 / I8): the document delete and its three status transitions, the
#: policy delete and the policy archive. Three always were: re-index, revision approve and policy
#: publish. THIS TUPLE IS THE MATRIX - ``test_dk_the_administrator_gate_is_exactly_these_nine``
#: fails if a verb joins or leaves it.
_DK_ADMIN_GATED_VERBS = (
    "pdocument_delete", "pdocument_activate", "pdocument_supersede", "pdocument_archive",
    "pdocument_reindex", "pdocrevision_approve",
    "ppolicy_delete", "ppolicy_publish", "ppolicy_archive",
)

#: Every POST verb in the sub-module. The nine above must 403 for a member; these seventeen must
#: let the member through to the view's own rules (302, never 403).
_DK_OPEN_VERBS = (
    "pdocument_checkout", "pdocument_release", "pdocument_run_reminders", "pdocrevision_delete",
    "knowledgeresource_delete", "knowledgeresource_publish", "knowledgeresource_archive",
    "knowledgeresource_use",
)

#: Which fixture each verb acts on when the matrix is exercised. One row per verb so a verb that
#: deletes its target cannot disturb the next one, and so every refusal is a 302 rather than a
#: 404 that would make "not 403" vacuous.
_DK_VERB_TARGETS = {
    "pdocument_delete": "dk_document_draft_a",
    "pdocument_activate": "dk_document_draft_a",
    "pdocument_supersede": "dk_document_active_a",
    "pdocument_archive": "dk_document_active_a",
    "pdocument_checkout": "dk_document_active_a",
    "pdocument_release": "dk_document_locked_a",
    "pdocrevision_approve": "dk_revision_pending_a",
    "pdocrevision_delete": "dk_revision_pending_a",
    "ppolicy_delete": "dk_policy_review_due_a",
    "ppolicy_publish": "dk_policy_draft_a",
    "ppolicy_archive": "dk_policy_published_a",
    "knowledgeresource_delete": "dk_resource_archived_a",
    "knowledgeresource_publish": "dk_resource_draft_a",
    "knowledgeresource_archive": "dk_resource_published_a",
    "knowledgeresource_use": "dk_resource_used_a",
}

#: Cross-tenant GET probes: (url name, tenant-B fixture). Nine routes - every rendering route
#: that takes a pk, including C1's download.
_DK_FOREIGN_GET_ROUTES = (
    ("pdocument_detail", "dk_document_b"),
    ("pdocument_edit", "dk_document_b"),
    ("pdocument_revision_upload", "dk_document_b"),
    ("pdocrevision_detail", "dk_revision_b"),
    ("pdocrevision_download", "dk_revision_b"),
    ("ppolicy_detail", "dk_policy_b"),
    ("ppolicy_edit", "dk_policy_b"),
    ("knowledgeresource_detail", "dk_resource_b"),
    ("knowledgeresource_edit", "dk_resource_b"),
)

#: Cross-tenant POST probes: every route that takes a pk and writes - the three edit forms and
#: every verb. Nineteen in all.
_DK_FOREIGN_POST_ROUTES = (
    ("pdocument_edit", "dk_document_b"),
    ("pdocument_delete", "dk_document_b"),
    ("pdocument_checkout", "dk_document_b"),
    ("pdocument_release", "dk_document_b"),
    ("pdocument_activate", "dk_document_b"),
    ("pdocument_supersede", "dk_document_b"),
    ("pdocument_archive", "dk_document_b"),
    ("pdocument_revision_upload", "dk_document_b"),
    ("pdocrevision_approve", "dk_revision_b"),
    ("pdocrevision_delete", "dk_revision_b"),
    ("ppolicy_edit", "dk_policy_b"),
    ("ppolicy_delete", "dk_policy_b"),
    ("ppolicy_publish", "dk_policy_b"),
    ("ppolicy_archive", "dk_policy_b"),
    ("knowledgeresource_edit", "dk_resource_b"),
    ("knowledgeresource_delete", "dk_resource_b"),
    ("knowledgeresource_publish", "dk_resource_b"),
    ("knowledgeresource_archive", "dk_resource_b"),
    ("knowledgeresource_use", "dk_resource_b"),
)

#: Where the 6.19 templates live. Scanned as FILES, not through a render, so a page nobody wrote
#: a test for is covered too.
_DK_TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates" / "procurement" / "documentknowledge"

#: A ``file.url`` USED as a template expression - ``{{ obj.file.url }}``, ``{{ r.file.url|... }}``.
#: Deliberately not a bare substring: ``document/detail.html`` names ``file.url`` inside a
#: ``{% comment %}`` that explains why it must never be linked, and that comment is the STATEMENT
#: of the rule, not a violation of it.
_DK_RAW_FILE_URL = re.compile(r"file\.url\s*(?:\||\}\})")


def _dk_url(name, *args):
    return reverse(f"procurement:{name}", args=args)


def _dk_get(client, name, *args, **params):
    return client.get(_dk_url(name, *args), params)


def _dk_messages(response):
    """Every message queued on the request that produced ``response``, as plain strings."""
    return [str(message) for message in get_messages(response.wsgi_request)]


def _dk_said(response, fragment):
    """True when any queued message contains ``fragment`` (substrings only - several 6.19
    messages carry an em dash, and matching a whole sentence turns a copy edit into a failure)."""
    return any(fragment in message for message in _dk_messages(response))


def _dk_pks(response, key="object_list"):
    return [row.pk for row in response.context[key]]


def _dk_body(response):
    return response.content.decode()


def _dk_snapshot(obj):
    """Every stored column of one row, read back from the database.

    A cross-tenant POST has to leave the row byte-for-byte as it was, and a status comparison
    would miss a stamped ``checked_out_by`` or a moved pointer. Comparing the whole row is what
    makes "nothing changed" mean nothing at all.
    """
    return type(obj).objects.filter(pk=obj.pk).values().first()


def _dk_target(request, verb):
    """The fixture row a verb acts on, resolved lazily so only what a test needs is built."""
    return request.getfixturevalue(_DK_VERB_TARGETS[verb])


def _dk_verb_args(verb, target):
    return () if verb in ("pdocument_reindex", "pdocument_run_reminders") else (target.pk,)


def _dk_login_url():
    return reverse("accounts:login")


def _dk_third_party(tenant, username="member3_acme"):
    """A member who is neither the holder nor an administrator - the only party release refuses."""
    from apps.accounts.models import User
    return User.objects.create_user(email=f"{username}@acme.com", username=username,
                                    password="TestPass123!", tenant=tenant,
                                    is_tenant_admin=False)


def _dk_txt(name="revision.txt", body=b"Smuggled revision body with a beacontoken inside."):
    return SimpleUploadedFile(name, body, content_type="text/plain")


def _dk_document_payload(**overrides):
    """The minimum valid ``ProcurementDocumentForm`` POST - title, doc_type, classification."""
    data = {"title": "Posted through the route", "doc_type": "other",
            "classification": "internal"}
    data.update(overrides)
    return data


def _dk_policy_payload(**overrides):
    data = {"title": "Posted policy", "policy_type": "purchasing_rule", "version_number": "1.0"}
    data.update(overrides)
    return data


def _dk_resource_payload(**overrides):
    data = {"title": "Posted resource", "resource_type": "guide", "category": "general",
            "audience": "all"}
    data.update(overrides)
    return data


# =================================================================================================
# 1. The login wall - anonymous reaches nothing and mutates nothing
# =================================================================================================

@pytest.mark.parametrize("name", _DK_ALL_ROUTES)
def test_dk_anonymous_get_is_redirected_to_login_on_every_route(client, name):
    """All 33 routes, GET. ``login_required`` fires before any database work, so the pk need not
    exist - what is being asserted is that no route in this sub-module is reachable logged out."""
    args = () if name in _DK_PK_LESS_ROUTES else (1,)
    resp = client.get(_dk_url(name, *args))
    assert resp.status_code == 302, name
    assert resp["Location"].startswith(_dk_login_url()), name


@pytest.mark.parametrize("name", _DK_ALL_ROUTES)
def test_dk_anonymous_post_is_redirected_to_login_on_every_route(client, name):
    """All 33 routes, POST. A verb must not answer 405 (which would prove it exists and is
    POST-only) or 403 before the login wall - the redirect comes first, every time."""
    args = () if name in _DK_PK_LESS_ROUTES else (1,)
    resp = client.post(_dk_url(name, *args), {})
    assert resp.status_code == 302, name
    assert resp["Location"].startswith(_dk_login_url()), name


@pytest.mark.parametrize("verb", _DK_ADMIN_GATED_VERBS + _DK_OPEN_VERBS)
def test_dk_anonymous_cannot_mutate_a_real_row(client, request, verb):
    """The same POSTs against REAL tenant-A rows: redirected, and the row is untouched.

    The route-table test above proves the redirect; this one proves the redirect happens BEFORE
    the write, which is the property that matters.
    """
    if verb in ("pdocument_reindex", "pdocument_run_reminders"):
        target = request.getfixturevalue("dk_document_chain_a")
    else:
        target = _dk_target(request, verb)
    before = _dk_snapshot(target)

    resp = client.post(_dk_url(verb, *_dk_verb_args(verb, target)), {})

    assert resp.status_code == 302
    assert resp["Location"].startswith(_dk_login_url())
    assert _dk_snapshot(target) == before


def test_dk_anonymous_cannot_download_a_stored_file(client, dk_revision_approved_a):
    """C1's headline: the bytes are behind the login wall, not behind a guessable filename."""
    resp = client.get(_dk_url("pdocrevision_download", dk_revision_approved_a.pk))
    try:
        assert resp.status_code == 302
        assert resp["Location"].startswith(_dk_login_url())
        assert "Content-Disposition" not in resp
        assert b"soleplate" not in resp.content
    finally:
        resp.close()


# =================================================================================================
# 2. C1 - the download route is authenticated, tenant-scoped and an attachment
# =================================================================================================

def test_dk_revision_download_is_authenticated_tenant_scoped_and_an_attachment(
        client, client_a, dk_document_chain_a, dk_revision_approved_a, dk_revision_b,
        dk_revision_no_file_a):
    """The whole C1 guard in one place: login, tenancy, the two headers and the file-less row.

    ``Content-Disposition: attachment`` keeps an uploaded ``.html`` or ``.svg`` from rendering on
    this origin (stored XSS against every logged-in member), and ``nosniff`` stops a browser
    second-guessing the declared type - ``SECURE_CONTENT_TYPE_NOSNIFF`` only applies outside
    DEBUG, so the view sets it itself.
    """
    anonymous = client.get(_dk_url("pdocrevision_download", dk_revision_approved_a.pk))
    try:
        assert anonymous.status_code == 302
        assert anonymous["Location"].startswith(_dk_login_url())
    finally:
        anonymous.close()

    ok = _dk_get(client_a, "pdocrevision_download", dk_revision_approved_a.pk)
    try:
        assert ok.status_code == 200
        assert "attachment" in ok["Content-Disposition"]
        assert ok["X-Content-Type-Options"] == "nosniff"
    finally:
        ok.close()

    foreign = _dk_get(client_a, "pdocrevision_download", dk_revision_b.pk)
    try:
        assert foreign.status_code == 404
    finally:
        foreign.close()

    fileless = _dk_get(client_a, "pdocrevision_download", dk_revision_no_file_a.pk)
    assert fileless.status_code == 302
    assert fileless["Location"] == _dk_url("pdocrevision_detail", dk_revision_no_file_a.pk)
    assert _dk_said(fileless, "has no stored file")


def test_dk_revision_download_of_another_workspace_serves_no_bytes(client_a, dk_revision_b):
    """404 AND no payload: a 200 with an empty body would still confirm the row exists."""
    resp = _dk_get(client_a, "pdocrevision_download", dk_revision_b.pk)
    try:
        assert resp.status_code == 404
        assert b"Globex master agreement" not in resp.content
    finally:
        resp.close()


def test_dk_revision_download_is_refused_to_a_member_on_a_confidential_parent(
        member_client, dk_revision_confidential_a):
    """The parent's classification governs the child - the read rule reaches the bytes."""
    resp = member_client.get(_dk_url("pdocrevision_download", dk_revision_confidential_a.pk))
    try:
        assert resp.status_code == 404
        assert b"zephyrindemnity" not in resp.content
    finally:
        resp.close()


def test_dk_no_six_nineteen_template_links_a_raw_media_url():
    """The regression that would silently reopen C1.

    Every stored file in 6.19 must be linked through ``pdocrevision_download``. A template that
    goes back to ``{{ obj.file.url }}`` hands the bytes to the web server, which serves them off
    MEDIA_ROOT with no login, no session and no tenant - and nothing else in the suite would
    notice, because the page would still render and still download.
    """
    templates = sorted(_DK_TEMPLATE_DIR.rglob("*.html"))
    assert templates, "6.19 templates not found - has the tree moved?"
    offenders = [str(path) for path in templates
                 if _DK_RAW_FILE_URL.search(path.read_text(encoding="utf-8"))]
    assert offenders == []


@pytest.mark.parametrize("page", ["document/detail.html", "revision/detail.html",
                                  "revision/list.html"])
def test_dk_every_template_that_shows_a_file_links_the_download_route(page):
    """...and the three that DO offer the file name the authenticated route by url tag."""
    text = (_DK_TEMPLATE_DIR / page).read_text(encoding="utf-8")
    assert "procurement:pdocrevision_download" in text


def test_dk_the_document_detail_page_links_the_download_route_for_its_chain(
        client_a, dk_document_chain_a, dk_revision_approved_a):
    """Rendered, not just present in the file: the link the page actually emits."""
    resp = _dk_get(client_a, "pdocument_detail", dk_document_chain_a.pk)
    body = _dk_body(resp)
    assert _dk_url("pdocrevision_download", dk_revision_approved_a.pk) in body
    assert dk_revision_approved_a.file.url not in body


def test_dk_the_revision_detail_page_links_the_download_route(
        client_a, dk_revision_approved_a):
    resp = _dk_get(client_a, "pdocrevision_detail", dk_revision_approved_a.pk)
    body = _dk_body(resp)
    assert _dk_url("pdocrevision_download", dk_revision_approved_a.pk) in body
    assert dk_revision_approved_a.file.url not in body


# =================================================================================================
# 3. Cross-tenant isolation - every tenant-B pk is 404, and nothing of B's leaks into A
# =================================================================================================

@pytest.mark.parametrize("name,fixture", _DK_FOREIGN_GET_ROUTES)
def test_dk_cross_tenant_get_is_404(client_a, request, name, fixture):
    """404, never 403 and never a redirect - a 403 confirms the row exists, which is itself a
    disclosure, and a 500 would say more still."""
    obj = request.getfixturevalue(fixture)
    resp = client_a.get(_dk_url(name, obj.pk))
    try:
        assert resp.status_code == 404
    finally:
        resp.close()


@pytest.mark.parametrize("name,fixture", _DK_FOREIGN_POST_ROUTES)
def test_dk_cross_tenant_post_is_404_and_changes_nothing(client_a, request, name, fixture):
    """Every writing route that takes a pk. ``client_a`` is a tenant ADMINISTRATOR, so the
    administrator gate lets them through and what refuses them is the tenant scope alone."""
    obj = request.getfixturevalue(fixture)
    before = _dk_snapshot(obj)

    resp = client_a.post(_dk_url(name, obj.pk), {})

    assert resp.status_code == 404, name
    assert type(obj).objects.filter(pk=obj.pk).exists(), name
    assert _dk_snapshot(obj) == before, name


def test_dk_cross_tenant_document_edit_post_cannot_rewrite_the_row(client_a, dk_document_b):
    """A full, VALID form payload against another workspace's pk - refused before it is read."""
    before = _dk_snapshot(dk_document_b)
    resp = client_a.post(_dk_url("pdocument_edit", dk_document_b.pk),
                         _dk_document_payload(title="Rewritten by Acme"))
    assert resp.status_code == 404
    assert _dk_snapshot(dk_document_b) == before


def test_dk_cross_tenant_revision_upload_post_mints_nothing(
        client_a, dk_document_b, dk_media_root):
    """The upload page resolves its parent through the tenant AND the read rule, so a foreign
    document pk cannot be used to mint a revision into another workspace's chain."""
    before = ProcurementDocumentRevision.objects.count()
    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_b.pk),
                         {"file": _dk_txt(), "change_note": "smuggled"})
    assert resp.status_code == 404
    assert ProcurementDocumentRevision.objects.count() == before


@pytest.mark.parametrize("route,foreign", [
    ("pdocument_list", "dk_document_b"),
    ("pdocrevision_list", "dk_revision_b"),
    ("ppolicy_list", "dk_policy_b"),
    ("knowledgeresource_list", "dk_resource_b"),
])
def test_dk_a_register_never_contains_another_workspaces_row(client_a, request, route, foreign):
    obj = request.getfixturevalue(foreign)
    resp = _dk_get(client_a, route)
    assert resp.status_code == 200
    assert obj.pk not in _dk_pks(resp)


@pytest.mark.parametrize("route,term", [
    ("pdocument_list", "Globex-only master agreement"),
    ("pdocrevision_list", "Globex first issue"),
    ("ppolicy_list", "Globex Purchasing Rule"),
    ("knowledgeresource_list", "Globex sourcing guide"),
])
def test_dk_a_search_never_reaches_another_workspaces_text(
        client_a, client_b, dk_document_b, dk_revision_b, dk_policy_b, dk_resource_b,
        route, term):
    """``?q=`` runs after the tenant filter, not instead of it.

    ``client_b`` searching the same term is the control: the empty result for A is the tenant
    scope and not a search that matches nothing.
    """
    resp = _dk_get(client_a, route, q=term)
    assert resp.status_code == 200
    assert _dk_pks(resp) == []

    owner = _dk_get(client_b, route, q=term)
    assert len(_dk_pks(owner)) == 1


def test_dk_a_document_search_never_reads_another_workspaces_file_text(
        client_a, client_b, dk_document_b, dk_revision_b):
    """The denormalized search copy is the one column that carries file CONTENTS - the tenant
    filter has to cover it too, or ``?q=`` is a read of every workspace's documents."""
    dk_document_b.refresh_from_db()
    assert "Globex master agreement" in dk_document_b.extracted_text

    resp = _dk_get(client_a, "pdocument_list", q="Globex master agreement")
    assert resp.status_code == 200
    assert _dk_pks(resp) == []

    owner = _dk_get(client_b, "pdocument_list", q="Globex master agreement")
    assert _dk_pks(owner) == [dk_document_b.pk]


def test_dk_the_revision_register_document_facet_is_this_workspace_only(
        client_a, dk_document_chain_a, dk_document_b):
    """A ``<select>`` of every document number in every workspace is an enumeration even when no
    row renders."""
    resp = _dk_get(client_a, "pdocrevision_list")
    facet_pks = [row.pk for row in resp.context["documents"]]
    assert dk_document_chain_a.pk in facet_pks
    assert dk_document_b.pk not in facet_pks


def test_dk_a_foreign_document_pk_in_the_revision_filter_returns_nothing_not_everything(
        client_a, dk_document_chain_a, dk_revision_approved_a, dk_document_b, dk_revision_b):
    """A real pk from another workspace is a valid integer, so the L11 guard passes it through -
    the tenant scope is what has to make it match nothing."""
    resp = _dk_get(client_a, "pdocrevision_list", document=str(dk_document_b.pk))
    assert resp.status_code == 200
    assert _dk_pks(resp) == []


def test_dk_a_crafted_supplier_pk_from_another_workspace_is_not_saved(
        client_a, tenant_a, dk_supplier_b):
    """The crafted-FK POST at the ROUTE (the forms lane pins the same rule at the form layer)."""
    resp = client_a.post(_dk_url("pdocument_create"),
                         _dk_document_payload(title="Crafted supplier",
                                              supplier=str(dk_supplier_b.pk)))
    assert resp.status_code == 200
    assert not ProcurementDocument.objects.filter(title="Crafted supplier").exists()
    assert "supplier" in resp.context["form"].errors


def test_dk_a_crafted_predecessor_pk_from_another_workspace_is_not_saved(
        client_a, dk_policy_b):
    resp = client_a.post(_dk_url("ppolicy_create"),
                         _dk_policy_payload(title="Crafted predecessor",
                                            previous_version=str(dk_policy_b.pk)))
    assert resp.status_code == 200
    assert not ProcurementPolicy.objects.filter(title="Crafted predecessor").exists()
    assert "previous_version" in resp.context["form"].errors


def test_dk_a_crafted_document_pk_from_another_workspace_is_not_saved_on_a_resource(
        client_a, dk_document_b):
    resp = client_a.post(_dk_url("knowledgeresource_create"),
                         _dk_resource_payload(title="Crafted link",
                                              document=str(dk_document_b.pk)))
    assert resp.status_code == 200
    assert not KnowledgeResource.objects.filter(title="Crafted link").exists()
    assert "document" in resp.context["form"].errors


# =================================================================================================
# 4. I5 - classification is enforced, not decorated
# =================================================================================================

def test_dk_the_read_rule_opens_only_public_and_internal_to_a_member(member_user, admin_user):
    """The rule itself, stated once: open tiers for everyone, the two closed tiers by identity.

    A ``Q()`` for an administrator means "no narrowing at all", which is why the register test
    below can use the same code path for both roles.
    """
    assert OPEN_CLASSIFICATIONS == ("public", "internal")
    # An administrator is narrowed by nothing at all - an empty Q, not a wider allow-list.
    assert readable_document_q(admin_user) == Q()
    # An anonymous or absent user matches no row rather than every row (fail closed).
    assert readable_document_q(None).children == [("pk__in", [])]
    member_q = readable_document_q(member_user)
    assert member_q.children  # a real narrowing, not an empty pass-through
    prefixed = readable_document_q(member_user, "document__")
    assert all(str(child[0]).startswith("document__") for child in prefixed.children)


def test_dk_member_register_shows_only_what_they_may_read(
        member_client, dk_document_public_a, dk_document_confidential_member_a,
        dk_document_confidential_a, dk_document_restricted_a):
    """Rows AND tiles. "7 documents / 5 rows" is exactly the discrepancy that turns a deliberate
    rule into a suspected bug, so the stat base is narrowed with the row base."""
    resp = _dk_get(member_client, "pdocument_list")

    assert resp.status_code == 200
    assert set(_dk_pks(resp)) == {dk_document_public_a.pk, dk_document_confidential_member_a.pk}
    assert resp.context["stats"]["total"] == 2
    body = _dk_body(resp)
    assert dk_document_confidential_a.number not in body
    assert dk_document_restricted_a.number not in body
    assert dk_document_confidential_a.title not in body
    assert dk_document_restricted_a.title not in body


def test_dk_an_administrator_sees_every_classification(
        client_a, dk_document_public_a, dk_document_confidential_member_a,
        dk_document_confidential_a, dk_document_restricted_a):
    """The control: the member's empty result is the RULE, not an empty database."""
    resp = _dk_get(client_a, "pdocument_list")
    assert set(_dk_pks(resp)) == {dk_document_public_a.pk, dk_document_confidential_member_a.pk,
                                  dk_document_confidential_a.pk, dk_document_restricted_a.pk}
    assert resp.context["stats"]["total"] == 4


def test_dk_member_cannot_search_inside_a_confidential_document(
        member_client, client_a, dk_document_public_a, dk_document_confidential_a):
    """THE SEARCH ORACLE. ``zephyrindemnity`` exists only inside the confidential document's
    extracted text; a register that answers "1 result" to it has read the file out loud."""
    member = _dk_get(member_client, "pdocument_list", q="zephyrindemnity")
    assert member.status_code == 200
    assert _dk_pks(member) == []

    admin = _dk_get(client_a, "pdocument_list", q="zephyrindemnity")
    assert _dk_pks(admin) == [dk_document_confidential_a.pk]


def test_dk_member_cannot_search_inside_a_restricted_document(
        member_client, client_a, dk_document_public_a, dk_document_restricted_a):
    member = _dk_get(member_client, "pdocument_list", q="quillbaseline")
    assert _dk_pks(member) == []
    admin = _dk_get(client_a, "pdocument_list", q="quillbaseline")
    assert _dk_pks(admin) == [dk_document_restricted_a.pk]


def test_dk_the_search_oracle_control_matches_the_public_document(
        member_client, dk_document_public_a, dk_document_restricted_a):
    """Same query shape, same length, open tier: the member DOES get this one. Without this the
    two tests above would pass against a search that is simply broken."""
    resp = _dk_get(member_client, "pdocument_list", q="harborcoverage")
    assert _dk_pks(resp) == [dk_document_public_a.pk]


def test_dk_member_cannot_enumerate_the_closed_tiers_through_the_classification_facet(
        member_client, client_a, dk_document_confidential_a, dk_document_restricted_a):
    """``?classification=restricted`` was an enumeration of exactly the need-to-know set."""
    for tier in ("confidential", "restricted"):
        member = _dk_get(member_client, "pdocument_list", classification=tier)
        assert member.status_code == 200
        assert _dk_pks(member) == [], tier
    admin = _dk_get(client_a, "pdocument_list", classification="restricted")
    assert _dk_pks(admin) == [dk_document_restricted_a.pk]


def test_dk_member_cannot_enumerate_a_colleagues_documents_through_the_owner_facet(
        member_client, client_a, admin_user, dk_document_confidential_a,
        dk_document_restricted_a):
    """The owner facet is a pk filter, so it applies AFTER the read rule, not instead of it.
    The administrator's own two rows are the control."""
    resp = _dk_get(member_client, "pdocument_list", owner=str(admin_user.pk))
    assert resp.status_code == 200
    assert _dk_pks(resp) == []

    control = _dk_get(client_a, "pdocument_list", owner=str(admin_user.pk))
    assert set(_dk_pks(control)) == {dk_document_confidential_a.pk, dk_document_restricted_a.pk}


def test_dk_member_cannot_enumerate_the_closed_tiers_through_the_tag_facet(
        member_client, client_a, dk_document_confidential_a, dk_document_restricted_a,
        dk_document_public_a):
    """``?tag=`` is a substring match applied to the pre-narrowed base - both closed-tier rows
    carry the ``legal`` tag, and an administrator gets both."""
    resp = _dk_get(member_client, "pdocument_list", tag="legal")
    assert _dk_pks(resp) == []

    control = _dk_get(client_a, "pdocument_list", tag="legal")
    assert set(_dk_pks(control)) == {dk_document_confidential_a.pk, dk_document_restricted_a.pk}


@pytest.mark.parametrize("fixture", ["dk_document_confidential_a", "dk_document_restricted_a"])
def test_dk_member_detail_on_a_closed_tier_document_is_404(member_client, request, fixture):
    obj = request.getfixturevalue(fixture)
    resp = member_client.get(_dk_url("pdocument_detail", obj.pk))
    assert resp.status_code == 404


def test_dk_member_may_read_their_own_confidential_document(
        member_client, dk_document_confidential_member_a):
    """The positive half of the rule: owner-or-creator-or-administrator, not administrator-only.
    A test suite that only proves the refusals would pass against a blanket ban on the tier."""
    resp = member_client.get(_dk_url("pdocument_detail", dk_document_confidential_member_a.pk))
    assert resp.status_code == 200
    assert dk_document_confidential_member_a.number in _dk_body(resp)


#: These two were STRICT xfails while ``pdocument_edit`` was the one surface the I5 fix pass
#: missed. It is fixed now (``Documents.py`` runs the read rule before delegating to
#: ``crud_edit``, which is tenant-scoped and nothing more), so they assert normally. The
#: strict marker is what forced the deletion to happen with the fix rather than outliving it.


def test_dk_member_cannot_open_the_edit_form_of_a_confidential_document(
        member_client, dk_document_confidential_a):
    """The READ half.

    Every other document surface resolves through ``readable_document_q``: the register, the
    stat tiles, every facet, ``?q=``, the detail page, the revision register, the download and
    all seven verbs. The edit form does not - and an edit form is a read of every field it
    prefills.
    """
    resp = member_client.get(_dk_url("pdocument_edit", dk_document_confidential_a.pk))
    assert resp.status_code == 404
    assert dk_document_confidential_a.title not in _dk_body(resp)
    assert dk_document_confidential_a.tags not in _dk_body(resp)


def test_dk_member_cannot_downgrade_the_classification_of_a_document_they_cannot_read(
        member_client, dk_document_confidential_a):
    """The WRITE half, and the reason this is not merely an information leak.

    ``classification`` is an ordinary form field, so the same unguarded edit route lets a member
    POST ``public`` onto a record they cannot open - after which the register, the facets and
    ``?q=`` over the extracted file text are open to the whole workspace. That is the I5 rule
    being revoked by somebody the rule exists to exclude, which makes the edit route a
    privilege-escalation path around it and not just a prefilled form.
    """
    before = _dk_snapshot(dk_document_confidential_a)

    resp = member_client.post(_dk_url("pdocument_edit", dk_document_confidential_a.pk),
                              _dk_document_payload(title="Rewritten by a member",
                                                   classification="public"))

    assert resp.status_code == 404
    assert _dk_snapshot(dk_document_confidential_a) == before


def test_dk_member_may_read_a_closed_tier_document_they_created(
        member_client, member_user, admin_user, tenant_a):
    """The read rule's THIRD branch: owner, CREATOR, or administrator.

    Somebody who filed a restricted record and then handed ownership to a colleague still has to
    be able to open it - a rule that lost the creator half would lock people out of their own
    filings and would be indistinguishable, from the outside, from the rule working.
    """
    filed = _dk_document(tenant_a, title="Filed by the member, owned by the administrator",
                         classification="restricted", status="active",
                         owner=admin_user, created_by=member_user)

    detail = member_client.get(_dk_url("pdocument_detail", filed.pk))
    assert detail.status_code == 200
    register = _dk_get(member_client, "pdocument_list")
    assert filed.pk in _dk_pks(register)


@pytest.mark.parametrize("verb", ["pdocument_checkout", "pdocument_release"])
def test_dk_member_verbs_on_a_closed_tier_document_are_404(
        member_client, dk_document_confidential_a, verb):
    """A document somebody may not read is not a document they may act on. These two verbs are
    NOT administrator-gated, so a 404 here is the read rule speaking and not the gate."""
    before = _dk_snapshot(dk_document_confidential_a)
    resp = member_client.post(_dk_url(verb, dk_document_confidential_a.pk), {})
    assert resp.status_code == 404
    assert _dk_snapshot(dk_document_confidential_a) == before


def test_dk_member_cannot_upload_a_revision_onto_a_closed_tier_document(
        member_client, dk_document_confidential_a, dk_media_root):
    """Writing to a document is reading it first - the upload page narrows on the same rule."""
    before = ProcurementDocumentRevision.objects.count()
    page = member_client.get(_dk_url("pdocument_revision_upload", dk_document_confidential_a.pk))
    assert page.status_code == 404
    posted = member_client.post(_dk_url("pdocument_revision_upload",
                                        dk_document_confidential_a.pk),
                                {"file": _dk_txt(), "change_note": "smuggled"})
    assert posted.status_code == 404
    assert ProcurementDocumentRevision.objects.count() == before


def test_dk_member_revision_register_hides_a_closed_tier_chain_and_its_tiles(
        member_client, dk_revision_confidential_a):
    """The 40046997 fix: the tile base is narrowed with the row base.

    Before it, a member who may read nothing still saw "1 revision / 1 approved" over an empty
    table - a counting oracle that discloses that a confidential document exists and how far
    along its chain is. The register, the tiles and the facet now agree on zero.
    """
    resp = _dk_get(member_client, "pdocrevision_list")

    assert resp.status_code == 200
    assert _dk_pks(resp) == []
    assert resp.context["stats"] == {"total": 0, "approved": 0, "pending": 0}
    assert list(resp.context["documents"]) == []


def test_dk_an_administrator_sees_the_revision_tiles_the_member_cannot(
        client_a, dk_revision_confidential_a):
    """The control for the tile assertion above - the zeros are the rule, not an empty table."""
    resp = _dk_get(client_a, "pdocrevision_list")
    assert resp.context["stats"] == {"total": 1, "approved": 1, "pending": 0}
    assert [row.pk for row in resp.context["documents"]] != []


def test_dk_member_revision_register_shows_an_open_tier_chain(
        member_client, dk_document_chain_a, dk_revision_confidential_a):
    """...and the member still sees the internal document's chain beside it, so the empty result
    above is the classification rule and not a broken register."""
    resp = _dk_get(member_client, "pdocrevision_list")
    assert set(_dk_pks(resp)) == set(
        dk_document_chain_a.revisions.values_list("pk", flat=True))
    assert resp.context["stats"]["total"] == 2


def test_dk_member_revision_detail_on_a_closed_tier_parent_is_404(
        member_client, dk_revision_confidential_a):
    resp = member_client.get(_dk_url("pdocrevision_detail", dk_revision_confidential_a.pk))
    assert resp.status_code == 404
    assert b"zephyrindemnity" not in resp.content


def test_dk_member_cannot_delete_a_revision_of_a_closed_tier_document(
        member_client, dk_document_confidential_a, admin_user, dk_media_root):
    """``pdocrevision_delete`` is deliberately NOT administrator-gated, so the read rule is the
    only thing standing between a member and another person's confidential chain."""
    pending = _dk_revision(dk_document_confidential_a, filename="second.txt",
                           uploaded_by=admin_user, change_note="Pending second issue",
                           body=b"Second issue of the settlement schedule.")
    resp = member_client.post(_dk_url("pdocrevision_delete", pending.pk), {})
    assert resp.status_code == 404
    assert ProcurementDocumentRevision.objects.filter(pk=pending.pk).exists()


def test_dk_the_classification_note_states_the_rule_that_is_enforced(
        client_a, dk_document_public_a):
    """The tier documented as "only a named few may read" has to describe what the code does -
    a note that promises more than the queryset delivers is the defect I5 was."""
    resp = _dk_get(client_a, "pdocument_list")
    note = resp.context["classification_note"]
    assert "Confidential" in note and "Restricted" in note
    assert "owner" in note and "administrators" in note


# =================================================================================================
# 5. The administrator gate (I6 / I8) - nine verbs, and exactly nine
# =================================================================================================

def test_dk_the_administrator_gate_is_exactly_these_nine(member_client, request):
    """The whole matrix in one assertion.

    A member POSTs every verb in the sub-module; the set that answers 403 must be exactly
    ``_DK_ADMIN_GATED_VERBS``. Both directions matter: a verb that quietly loses its gate is the
    I6/I8 defect coming back, and a verb that quietly gains one locks members out of ordinary
    work (checkout, the reminder Run, using a knowledge resource). Each verb acts on its own
    target row so a verb that deletes cannot make the next one vacuous.
    """
    refused = set()
    for verb in _DK_ADMIN_GATED_VERBS + _DK_OPEN_VERBS:
        if verb in ("pdocument_reindex", "pdocument_run_reminders"):
            args = ()
        else:
            args = (_dk_target(request, verb).pk,)
        resp = member_client.post(_dk_url(verb, *args), {})
        assert resp.status_code in (302, 403), f"{verb} answered {resp.status_code}"
        if resp.status_code == 403:
            refused.add(verb)
    assert refused == set(_DK_ADMIN_GATED_VERBS)


@pytest.mark.parametrize("verb", _DK_ADMIN_GATED_VERBS)
def test_dk_a_member_post_on_an_administrator_gated_verb_changes_nothing(
        member_client, request, verb):
    """403 is only half the assertion - the row has to be byte-for-byte as it was."""
    if verb == "pdocument_reindex":
        target = request.getfixturevalue("dk_document_chain_a")
        ProcurementDocument.objects.filter(pk=target.pk).update(extracted_text="")
        target.refresh_from_db()
    else:
        target = _dk_target(request, verb)
    before = _dk_snapshot(target)

    resp = member_client.post(_dk_url(verb, *_dk_verb_args(verb, target)), {})

    assert resp.status_code == 403
    assert _dk_snapshot(target) == before
    if verb == "pdocument_reindex":
        target.refresh_from_db()
        assert target.extracted_text == ""


@pytest.mark.parametrize("verb", _DK_ADMIN_GATED_VERBS)
def test_dk_a_member_get_on_an_administrator_gated_verb_is_403_not_405(
        member_client, request, verb):
    """Decorator order is ``login_required`` -> ``tenant_admin_required`` -> ``require_POST``, so
    the gate answers before the method check: a member never learns the verb is POST-only."""
    args = () if verb == "pdocument_reindex" else _dk_verb_args(verb, _dk_target(request, verb))
    assert member_client.get(_dk_url(verb, *args)).status_code == 403


@pytest.mark.parametrize("verb", _DK_ADMIN_GATED_VERBS)
def test_dk_an_administrator_post_on_a_gated_verb_is_allowed_through(client_a, request, verb):
    """The other side of the gate: an administrator reaches the view and gets its redirect.
    Without this the 403 tests would pass against a verb that is broken for everybody."""
    if verb == "pdocument_reindex":
        target = request.getfixturevalue("dk_document_chain_a")
        args = ()
    else:
        target = _dk_target(request, verb)
        args = (target.pk,)

    resp = client_a.post(_dk_url(verb, *args), {})

    assert resp.status_code == 302
    assert not resp["Location"].startswith(_dk_login_url())


@pytest.mark.parametrize("verb", _DK_OPEN_VERBS)
def test_dk_an_ungated_verb_lets_an_ordinary_member_work(member_client, request, verb):
    """The eight verbs that are deliberately NOT administrator-only. Checkout, release, the
    reminder Run, deleting a mis-uploaded revision and the four knowledge-resource verbs are
    ordinary work - gating them would be its own defect."""
    args = () if verb == "pdocument_run_reminders" else (_dk_target(request, verb).pk,)
    resp = member_client.post(_dk_url(verb, *args), {})
    assert resp.status_code == 302
    assert not resp["Location"].startswith(_dk_login_url())


def test_dk_the_document_list_offers_the_delete_button_only_to_an_administrator(
        member_client, client_a, dk_document_draft_a):
    """A page must not offer a button the view will 403 (the I11 / M3 rule, applied to delete)."""
    member_body = _dk_body(_dk_get(member_client, "pdocument_list"))
    admin_body = _dk_body(_dk_get(client_a, "pdocument_list"))
    delete_url = _dk_url("pdocument_delete", dk_document_draft_a.pk)
    assert delete_url not in member_body
    assert delete_url in admin_body


def test_dk_the_policy_pages_offer_their_gated_verbs_only_to_an_administrator(
        member_client, client_a, dk_policy_draft_a):
    member_body = _dk_body(_dk_get(member_client, "ppolicy_detail", dk_policy_draft_a.pk))
    admin_body = _dk_body(_dk_get(client_a, "ppolicy_detail", dk_policy_draft_a.pk))
    for verb in ("ppolicy_publish", "ppolicy_delete", "ppolicy_archive"):
        assert _dk_url(verb, dk_policy_draft_a.pk) not in member_body, verb
    assert _dk_url("ppolicy_publish", dk_policy_draft_a.pk) in admin_body


def test_dk_the_revision_pages_offer_approve_only_to_an_administrator(
        member_client, client_a, dk_revision_pending_a):
    member_body = _dk_body(_dk_get(member_client, "pdocrevision_detail",
                                   dk_revision_pending_a.pk))
    admin_body = _dk_body(_dk_get(client_a, "pdocrevision_detail", dk_revision_pending_a.pk))
    approve_url = _dk_url("pdocrevision_approve", dk_revision_pending_a.pk)
    assert approve_url not in member_body
    assert approve_url in admin_body


def test_dk_the_detail_page_offers_release_only_to_somebody_release_would_allow(
        member_client, client_a, dk_document_locked_a, member_user):
    """I11: "Release checkout" was offered to every viewer and the view refused non-holders.
    ``can_release`` is the view's own rule, so the button and the POST cannot disagree."""
    holder = _dk_get(member_client, "pdocument_detail", dk_document_locked_a.pk)
    assert holder.context["can_release"] is True
    assert _dk_url("pdocument_release", dk_document_locked_a.pk) in _dk_body(holder)

    administrator = _dk_get(client_a, "pdocument_detail", dk_document_locked_a.pk)
    assert administrator.context["can_release"] is True  # a forced release is allowed

    second = Client()
    second.force_login(_dk_third_party(dk_document_locked_a.tenant))
    outsider = _dk_get(second, "pdocument_detail", dk_document_locked_a.pk)
    assert outsider.context["can_release"] is False
    assert _dk_url("pdocument_release", dk_document_locked_a.pk) not in _dk_body(outsider)


def test_dk_the_detail_page_does_not_offer_check_out_on_an_archived_document(
        client_a, dk_document_archived_a, dk_document_active_a):
    """M3: "Check out" was offered on an archived document and ``pdocument_checkout`` refused
    it. The control is the active row, where the same button IS offered."""
    archived = _dk_body(_dk_get(client_a, "pdocument_detail", dk_document_archived_a.pk))
    active = _dk_body(_dk_get(client_a, "pdocument_detail", dk_document_active_a.pk))
    assert _dk_url("pdocument_checkout", dk_document_archived_a.pk) not in archived
    assert _dk_url("pdocument_checkout", dk_document_active_a.pk) in active


# =================================================================================================
# 6. I6 / I7 - the two destructive guards, and the child rows that survive them
# =================================================================================================

def test_dk_a_member_cannot_cascade_an_approved_revision_chain(
        member_client, dk_document_chain_a, dk_revision_approved_a, dk_revision_pending_a):
    """I6. ``pdocument_delete`` CASCADEs the revisions - including the approved ones
    ``pdocrevision_delete`` refuses to touch one at a time. A verb that removes the whole chain
    in one POST cannot be less guarded than the verb that removes a single link of it."""
    resp = member_client.post(_dk_url("pdocument_delete", dk_document_chain_a.pk), {})

    assert resp.status_code == 403
    assert ProcurementDocument.objects.filter(pk=dk_document_chain_a.pk).exists()
    assert ProcurementDocumentRevision.objects.filter(pk=dk_revision_approved_a.pk).exists()
    assert ProcurementDocumentRevision.objects.filter(pk=dk_revision_pending_a.pk).exists()
    dk_revision_approved_a.refresh_from_db()
    assert dk_revision_approved_a.is_approved is True


def test_dk_even_an_administrator_cannot_delete_a_document_with_an_approved_chain(
        client_a, dk_document_chain_a, dk_revision_approved_a, dk_revision_pending_a):
    """The second half of I6: the gate is not the whole guard. Approved history is never
    rewritten here, so the row and BOTH revisions survive an administrator's POST too."""
    resp = client_a.post(_dk_url("pdocument_delete", dk_document_chain_a.pk), {})

    assert resp.status_code == 302
    assert resp["Location"] == _dk_url("pdocument_detail", dk_document_chain_a.pk)
    assert _dk_said(resp, "approved revision chain")
    assert ProcurementDocument.objects.filter(pk=dk_document_chain_a.pk).exists()
    assert dk_document_chain_a.revisions.count() == 2


def test_dk_policy_delete_is_administrator_only_and_refuses_while_attestations_exist(
        member_client, client_a, dk_policy_published_a, dk_attestation_a):
    """I7. ``PolicyAttestation.policy`` is ``on_delete=CASCADE``, so deleting a published policy
    destroys 6.17's signature and exemption ledger - the compliance evidence that sub-module
    exists to hold. Both halves are asserted: the member is gated out, and the administrator who
    passes the gate is still refused while a signature exists."""
    member = member_client.post(_dk_url("ppolicy_delete", dk_policy_published_a.pk), {})
    assert member.status_code == 403
    assert ProcurementPolicy.objects.filter(pk=dk_policy_published_a.pk).exists()
    assert PolicyAttestation.objects.filter(pk=dk_attestation_a.pk).exists()

    administrator = client_a.post(_dk_url("ppolicy_delete", dk_policy_published_a.pk), {})
    assert administrator.status_code == 302
    assert administrator["Location"] == _dk_url("ppolicy_detail", dk_policy_published_a.pk)
    assert _dk_said(administrator, "acknowledgement record")
    assert ProcurementPolicy.objects.filter(pk=dk_policy_published_a.pk).exists()
    assert PolicyAttestation.objects.filter(pk=dk_attestation_a.pk).exists()


def test_dk_a_member_cannot_archive_a_published_policy(
        member_client, dk_policy_published_a):
    """I8's own scenario: archiving is the mirror of publishing. A member who could archive a
    published rule could take it out of force, and only an administrator could put it back."""
    resp = member_client.post(_dk_url("ppolicy_archive", dk_policy_published_a.pk), {})
    assert resp.status_code == 403
    dk_policy_published_a.refresh_from_db()
    assert dk_policy_published_a.status == "published"
    assert dk_policy_published_a.published_at is not None


def test_dk_a_member_cannot_walk_a_document_through_its_status_transitions(
        member_client, dk_document_active_a):
    """The three transitions decide what the workspace treats as authoritative."""
    for verb in ("pdocument_activate", "pdocument_supersede", "pdocument_archive"):
        resp = member_client.post(_dk_url(verb, dk_document_active_a.pk), {})
        assert resp.status_code == 403, verb
        dk_document_active_a.refresh_from_db()
        assert dk_document_active_a.status == "active", verb


def test_dk_a_member_cannot_move_the_pointer_by_approving_a_revision(
        member_client, dk_document_chain_a, dk_revision_pending_a):
    """Approval decides which file the whole workspace treats as the truth."""
    resp = member_client.post(_dk_url("pdocrevision_approve", dk_revision_pending_a.pk), {})

    assert resp.status_code == 403
    dk_revision_pending_a.refresh_from_db()
    dk_document_chain_a.refresh_from_db()
    assert dk_revision_pending_a.is_approved is False
    assert dk_revision_pending_a.approved_by_id is None
    assert dk_document_chain_a.current_revision_no == 1


# =================================================================================================
# 7. CSRF and method safety
# =================================================================================================

@pytest.fixture
def _dk_csrf_admin(admin_user):
    """A logged-in tenant administrator whose client ENFORCES the CSRF token (L44)."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


@pytest.mark.parametrize("verb", _DK_ADMIN_GATED_VERBS + _DK_OPEN_VERBS)
def test_dk_a_post_without_a_csrf_token_is_refused(_dk_csrf_admin, request, verb):
    """Every POST verb, with a session and without a token: 403, and the row is untouched."""
    if verb in ("pdocument_reindex", "pdocument_run_reminders"):
        target = request.getfixturevalue("dk_document_chain_a")
    else:
        target = _dk_target(request, verb)
    before = _dk_snapshot(target)

    resp = _dk_csrf_admin.post(_dk_url(verb, *_dk_verb_args(verb, target)), {})

    assert resp.status_code == 403, verb
    assert _dk_snapshot(target) == before, verb


@pytest.mark.parametrize("name", ["pdocument_create", "ppolicy_create",
                                  "knowledgeresource_create"])
def test_dk_a_create_post_without_a_csrf_token_saves_nothing(_dk_csrf_admin, name):
    payload = {"pdocument_create": _dk_document_payload(title="No token here"),
               "ppolicy_create": _dk_policy_payload(title="No token here"),
               "knowledgeresource_create": _dk_resource_payload(title="No token here")}[name]
    model = {"pdocument_create": ProcurementDocument, "ppolicy_create": ProcurementPolicy,
             "knowledgeresource_create": KnowledgeResource}[name]

    resp = _dk_csrf_admin.post(_dk_url(name), payload)

    assert resp.status_code == 403
    assert not model.objects.filter(title="No token here").exists()


@pytest.mark.parametrize("name", ["pdocument_list", "pdocrevision_list", "ppolicy_list",
                                  "knowledgeresource_list"])
def test_dk_the_same_csrf_enforcing_client_still_reads_every_register(_dk_csrf_admin, name):
    """The L44 pair: CSRF enforcement must not be mistaken for a broken session. The same client
    that was refused the POST reads the page fine, which is what makes the 403 above a token
    failure and not a login failure."""
    assert _dk_csrf_admin.get(_dk_url(name)).status_code == 200


def test_dk_a_csrf_enforcing_post_that_carries_the_token_succeeds(
        _dk_csrf_admin, dk_document_active_a):
    """...and the completing half: with the token from the rendered page, the same POST works."""
    page = _dk_csrf_admin.get(_dk_url("pdocument_detail", dk_document_active_a.pk))
    token = page.context["csrf_token"]

    resp = _dk_csrf_admin.post(_dk_url("pdocument_checkout", dk_document_active_a.pk),
                               {"csrfmiddlewaretoken": str(token)})

    assert resp.status_code == 302
    dk_document_active_a.refresh_from_db()
    assert dk_document_active_a.checked_out_by_id is not None


@pytest.mark.parametrize("verb", _DK_OPEN_VERBS)
def test_dk_a_member_get_on_an_ungated_verb_is_405_and_writes_nothing(
        member_client, request, verb):
    """For the ungated verbs the method check is the outermost thing left, so a GET is 405 -
    and, more to the point, a link or a prefetch cannot mutate anything."""
    if verb == "pdocument_run_reminders":
        target = request.getfixturevalue("dk_document_expiring_a")
        args = ()
    else:
        target = _dk_target(request, verb)
        args = (target.pk,)
    before = _dk_snapshot(target)

    resp = member_client.get(_dk_url(verb, *args))

    assert resp.status_code == 405
    assert _dk_snapshot(target) == before


# =================================================================================================
# 8. Mass assignment at the HTTP layer
# =================================================================================================
#
# The forms lane pins this at the form layer (a smuggled column is not in ``Meta.fields``, so it
# is not bound). These four assert the same thing where an attacker actually stands: the ROUTE.

def test_dk_a_document_create_post_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, member_user):
    resp = client_a.post(_dk_url("pdocument_create"), _dk_document_payload(
        title="Smuggled document",
        tenant=str(tenant_b.pk),
        number="PDOC-99999",
        status="active",
        current_revision_no="7",
        extracted_text="injected search copy",
        checked_out_by=str(member_user.pk),
        supplier_visible="on"))

    assert resp.status_code == 302
    obj = ProcurementDocument.objects.get(title="Smuggled document")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PDOC-") and obj.number != "PDOC-99999"
    assert obj.status == "draft"
    assert obj.current_revision_no == 0
    assert obj.extracted_text == ""
    assert obj.checked_out_by_id is None
    assert obj.checked_out_at is None


def test_dk_a_document_edit_post_cannot_move_the_row_or_its_workflow(
        client_a, tenant_a, tenant_b, dk_document_chain_a):
    before = _dk_snapshot(dk_document_chain_a)

    resp = client_a.post(_dk_url("pdocument_edit", dk_document_chain_a.pk),
                         _dk_document_payload(title="Renamed but not moved",
                                              tenant=str(tenant_b.pk),
                                              status="archived",
                                              number="PDOC-00001",
                                              current_revision_no="9",
                                              extracted_text="injected"))

    assert resp.status_code == 302
    dk_document_chain_a.refresh_from_db()
    assert dk_document_chain_a.title == "Renamed but not moved"
    assert dk_document_chain_a.tenant_id == tenant_a.pk
    assert dk_document_chain_a.status == before["status"]
    assert dk_document_chain_a.number == before["number"]
    assert dk_document_chain_a.current_revision_no == before["current_revision_no"]
    assert dk_document_chain_a.extracted_text == before["extracted_text"]


def test_dk_a_policy_create_post_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b):
    resp = client_a.post(_dk_url("ppolicy_create"), _dk_policy_payload(
        title="Smuggled policy",
        tenant=str(tenant_b.pk),
        number="PPOL-99999",
        status="published",
        published_at=timezone.now().isoformat()))

    assert resp.status_code == 302
    obj = ProcurementPolicy.objects.get(title="Smuggled policy")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PPOL-") and obj.number != "PPOL-99999"
    assert obj.status == "draft"
    assert obj.published_at is None


def test_dk_a_resource_create_post_ignores_the_usage_counters(client_a, tenant_a, tenant_b):
    resp = client_a.post(_dk_url("knowledgeresource_create"), _dk_resource_payload(
        title="Smuggled resource",
        tenant=str(tenant_b.pk),
        number="PKR-99999",
        status="published",
        usage_count="4242",
        last_used_at=timezone.now().isoformat()))

    assert resp.status_code == 302
    obj = KnowledgeResource.objects.get(title="Smuggled resource")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PKR-") and obj.number != "PKR-99999"
    assert obj.status == "draft"
    assert obj.usage_count == 0
    assert obj.last_used_at is None


def test_dk_a_revision_upload_post_cannot_self_approve_or_choose_its_number(
        client_a, admin_user, tenant_a, tenant_b, dk_document_draft_a, dk_document_b,
        dk_media_root):
    """The upload page mints the revision itself: the parent comes from the URL, the number from
    ``next_revision_no``, the checksum from the bytes, and approval from an administrator's own
    POST to a different route."""
    resp = client_a.post(_dk_url("pdocument_revision_upload", dk_document_draft_a.pk), {
        "file": _dk_txt(),
        "change_note": "First issue",
        "tenant": str(tenant_b.pk),
        "document": str(dk_document_b.pk),
        "revision_no": "9",
        "is_approved": "True",
        "approved_by": str(admin_user.pk),
        "sha256": "deadbeef",
        "extracted_text": "injected",
        "extraction_note": "injected"})

    assert resp.status_code == 302
    revision = ProcurementDocumentRevision.objects.get(document=dk_document_draft_a)
    assert revision.tenant_id == tenant_a.pk
    assert revision.document_id == dk_document_draft_a.pk
    assert revision.revision_no == 1
    assert revision.is_approved is False
    assert revision.approved_by_id is None
    assert revision.approved_at is None
    assert revision.sha256 != "deadbeef" and len(revision.sha256) == 64
    assert "beacontoken" in revision.extracted_text
    dk_document_draft_a.refresh_from_db()
    assert dk_document_draft_a.current_revision_no == 0
    assert dk_document_draft_a.status == "draft"


def test_dk_a_document_create_post_cannot_plant_a_row_in_another_workspace(
        client_a, tenant_a, tenant_b, client_b):
    """The tenant stamp comes from the SESSION, never from the payload - so the row is visible
    to its author and absent from the other workspace's register."""
    client_a.post(_dk_url("pdocument_create"),
                  _dk_document_payload(title="Stamped by the session",
                                       tenant=str(tenant_b.pk)))

    obj = ProcurementDocument.objects.get(title="Stamped by the session")
    assert obj.tenant_id == tenant_a.pk
    assert obj.pk not in _dk_pks(_dk_get(client_b, "pdocument_list"))
    assert client_b.get(_dk_url("pdocument_detail", obj.pk)).status_code == 404


def test_dk_a_use_press_cannot_set_the_counter_it_only_increments(
        member_client, dk_resource_used_a):
    """``usage_count`` is written only by an atomic ``F("usage_count") + 1`` - a payload naming a
    value must not become the value."""
    resp = member_client.post(_dk_url("knowledgeresource_use", dk_resource_used_a.pk),
                              {"usage_count": "999999"})
    assert resp.status_code == 302
    dk_resource_used_a.refresh_from_db()
    assert dk_resource_used_a.usage_count == 8


def test_dk_a_junk_filter_value_is_not_an_error_and_not_an_empty_register(
        client_a, dk_document_public_a, dk_document_active_a):
    """L11 at the security boundary: a hand-edited query string must neither 500 (which leaks a
    stack trace) nor silently empty the register (which reads as "you have no documents")."""
    for params in ({"supplier": "abc"}, {"supplier": "0"}, {"supplier": "9" * 25},
                   {"owner": "NaN"}, {"classification": "restricted' OR '1'='1"},
                   {"status": "<script>alert(1)</script>"}, {"page": "-1"}):
        resp = _dk_get(client_a, "pdocument_list", **params)
        assert resp.status_code == 200, params
        assert dk_document_public_a.pk in _dk_pks(resp), params
