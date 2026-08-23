"""Inventory 5.4 Receiving & Putaway — security.

Adversarial multi-tenancy around the putaway-rule CRUD and the computed suggestions
queue: cross-tenant IDOR on every route shape (GET pages, edit POSTs, delete POSTs),
crafted-POST FK injection against EACH foreign pointer (item / source dock / destination
bin), missing-required-field degradation (no 500), anonymous walls, the tenant-admin
gate on writes with reads left open, resolver containment (an injected foreign rule can
never smuggle another workspace's bin past the by_pk tenant map), tenant-less superuser
isolation, escaping of notes/item names, and method discipline.

House note: ``base.html`` ships legit ``<script>`` tags, so escape probes assert the FULL
payload (e.g. ``<script>alert(1)</script>``) is absent — never the bare ``<script>``
prefix (same idiom as 5.2's escaping test).
"""
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory.models import PutawayRule, resolve_putaway_suggestion
from apps.scm.models import Location

pytestmark = pytest.mark.django_db

#: Strings unique PER ROW to Globex's workspace. Both workspaces' items share the SKU
#: "CAT-1" (see tests/conftest), so isolation is asserted ONLY on markers these fixtures
#: mint exclusively for tenant_b.
_FOREIGN_MARKERS = ["RB-01", "RDOCK-B", "RWH-B", "Globex-side routing",
                    "Globex Catalog Widget"]

_XSS_SCRIPT = "<script>alert(1)</script>"
_XSS_BOLD = "<b>Evil Widget</b>"


# ---- module-level helpers ----------------------------------------------------------------------

def _receiving_assert_login_redirect(response):
    assert response.status_code == 302
    assert "/login" in response.url or response.url.endswith("login")


def _receiving_assert_no_foreign_marker(content):
    html = content.decode() if isinstance(content, bytes) else content
    for marker in _FOREIGN_MARKERS:
        assert marker not in html


def _receiving_rule_payload(**overrides):
    """A minimal VALID rule POST body — destination + priority are the only required
    fields (every FK else is nullable); overrides carry the adversarial bits."""
    data = {"item": "", "category": "", "source_location": "", "destination": "",
            "priority": "50", "is_active": "on", "notes": ""}
    data.update(overrides)
    return data


# ---- local fixtures -----------------------------------------------------------------------------

@pytest.fixture
def _receiving_tenantless_superuser(db):
    """The platform superuser: tenant=None BY DESIGN — it owns no workspace at all."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="sec-super@naverp.test", username="sec_superuser_admin",
        password="TestPass123!", tenant=None, is_superuser=True, is_staff=True)


@pytest.fixture
def _receiving_super_client(_receiving_tenantless_superuser):
    c = Client()
    c.force_login(_receiving_tenantless_superuser)
    return c


# ---- IDOR ----------------------------------------------------------------------------------------

def test_receiving_idor_detail_and_edit_get_404(client_a, receiving_foreign_rule_b):
    """A foreign rule pk must read as nonexistent to another workspace's admin."""
    for name in ["putawayrule_detail", "putawayrule_edit"]:
        url = reverse(f"inventory:{name}", args=[receiving_foreign_rule_b.pk])
        assert client_a.get(url).status_code == 404


def test_receiving_idor_edit_post_404_and_row_untouched(client_a, receiving_foreign_rule_b,
                                                        receiving_loc_bin_b):
    response = client_a.post(
        reverse("inventory:putawayrule_edit", args=[receiving_foreign_rule_b.pk]),
        data=_receiving_rule_payload(destination=receiving_loc_bin_b.pk, priority="1"))
    assert response.status_code == 404
    receiving_foreign_rule_b.refresh_from_db()
    assert receiving_foreign_rule_b.priority == 10  # hijack never landed


def test_receiving_idor_delete_post_404_and_count_unchanged(client_a, receiving_foreign_rule_b):
    """The destructive verb is where an IDOR would do damage: a foreign pk must 404 on
    POST and leave the row — and every other row — exactly where it was."""
    total_before = PutawayRule.objects.count()
    response = client_a.post(reverse("inventory:putawayrule_delete",
                                     args=[receiving_foreign_rule_b.pk]))
    assert response.status_code == 404
    receiving_foreign_rule_b.refresh_from_db()  # raises if deleted — the real assertion
    assert PutawayRule.objects.count() == total_before


# ---- crafted-POST cross-tenant FK injection ---------------------------------------------------------

@pytest.mark.parametrize("field_name,foreign_fixture", [
    ("item", "item_b"),
    ("source_location", "receiving_loc_dock_b"),
    ("destination", "receiving_loc_bin_b"),
])
def test_receiving_create_rejects_each_foreign_fk(client_a, field_name, foreign_fixture,
                                                  request):
    """Each of the three tenant-scoped pointers, pointed at Globex one at a time: the form
    re-renders with THAT field's error and not one row appears anywhere."""
    foreign = request.getfixturevalue(foreign_fixture)
    own_bin = request.getfixturevalue("receiving_loc_bin_a")
    data = _receiving_rule_payload(destination=own_bin.pk)
    data[field_name] = foreign.pk

    total_before = PutawayRule.objects.count()
    response = client_a.post(reverse("inventory:putawayrule_create"), data=data)
    assert response.status_code == 200
    html = response.content.decode()
    assert ("not one of the available choices" in html
            or "That record belongs to another workspace." in html)
    assert PutawayRule.objects.count() == total_before


def test_receiving_edit_cannot_swap_own_destination_to_foreign_bin(
        client_a, receiving_rule_a, receiving_loc_bin_a, receiving_loc_bin_b):
    """The crafted-POST vector on EDIT: swapping an OWN rule's destination to a foreign
    bin must fail as a form error and leave the stored FK untouched."""
    response = client_a.post(
        reverse("inventory:putawayrule_edit", args=[receiving_rule_a.pk]),
        data=_receiving_rule_payload(destination=receiving_loc_bin_b.pk,
                                     priority="10", notes=receiving_rule_a.notes))
    assert response.status_code == 200
    html = response.content.decode()
    assert ("not one of the available choices" in html
            or "That record belongs to another workspace." in html)
    receiving_rule_a.refresh_from_db()
    assert receiving_rule_a.destination_id == receiving_loc_bin_a.pk


def test_receiving_missing_destination_post_is_form_error_not_500(client_a):
    """[C1] Dropping the one required field degrades to a re-rendered form, never a 500."""
    total_before = PutawayRule.objects.count()
    response = client_a.post(reverse("inventory:putawayrule_create"),
                             data=_receiving_rule_payload(priority="5"))
    assert response.status_code == 200
    assert "This field is required" in response.content.decode()
    assert PutawayRule.objects.count() == total_before


# ---- auth walls ------------------------------------------------------------------------------------

def test_receiving_anonymous_redirected_on_all_six_routes_without_leaks(client,
                                                                        receiving_rule_a):
    plain_routes = ["putawayrule_list", "putawayrule_create", "putaway_suggestions"]
    argged_routes = ["putawayrule_detail", "putawayrule_edit", "putawayrule_delete"]
    for name in plain_routes:
        response = client.get(reverse(f"inventory:{name}"))
        _receiving_assert_login_redirect(response)
        _receiving_assert_no_foreign_marker(response.content)
    for name in argged_routes:
        response = client.get(reverse(f"inventory:{name}", args=[receiving_rule_a.pk]))
        _receiving_assert_login_redirect(response)
        _receiving_assert_no_foreign_marker(response.content)


def test_receiving_writes_admin_gated_reads_open_to_members(member_client, receiving_rule_a):
    """Reads stay open to every signed-in member; create/edit/delete carry
    tenant_admin_required (PermissionDenied → 403 under the test runner), and the ROLE is
    checked before require_POST — a member gets 403, never a misleading 405."""
    assert member_client.get(reverse("inventory:putawayrule_list")).status_code == 200
    assert member_client.get(reverse("inventory:putawayrule_detail",
                                     args=[receiving_rule_a.pk])).status_code == 200

    assert member_client.get(reverse("inventory:putawayrule_create")).status_code == 403
    assert member_client.post(reverse("inventory:putawayrule_create")).status_code == 403
    assert member_client.get(reverse("inventory:putawayrule_edit",
                                     args=[receiving_rule_a.pk])).status_code == 403
    assert member_client.post(reverse("inventory:putawayrule_edit",
                                      args=[receiving_rule_a.pk])).status_code == 403
    assert member_client.get(reverse("inventory:putawayrule_delete",
                                     args=[receiving_rule_a.pk])).status_code == 403
    assert member_client.post(reverse("inventory:putawayrule_delete",
                                      args=[receiving_rule_a.pk])).status_code == 403
    receiving_rule_a.refresh_from_db()  # nothing was deleted despite the POST


# ---- resolver containment ---------------------------------------------------------------------------

def test_receiving_resolver_cannot_smuggle_foreign_bins(tenant_a, tenant_b, item_a,
                                                        receiving_loc_dock_a,
                                                        receiving_loc_bin_a,
                                                        receiving_loc_bin_b,
                                                        receiving_foreign_rule_b):
    """Kwargs injection cannot smuggle another workspace's bin past tenant filtering.
    TWO adversarial shapes against the same acme task:

    1. The LITERAL smuggle attempt — Globex's own mirror rule plus a ``by_pk`` map of
       GLOBEX locations and an empty ledger, i.e. every batch kwarg hostile. The
       source-scoped rule cannot even fire for a dock_a arrival, and nothing else in a
       foreign-only map may answer either: the honest outcome is the refusal.
    2. The STRONGER shape — a tenant_b CATCH-ALL (matches ANY arrival) handed through the
       same ``rules=`` kwarg the queue page preloads, but ``by_pk`` kept the way the page
       really builds it (the task tenant's map). Matching must not be enough: the by_pk
       guard walls the destination off, so no candidate leaves acme's workspace and the
       injected rule never produces a "Rule:" answer."""
    foreign_catchall = PutawayRule.objects.create(
        tenant=tenant_b, destination=receiving_loc_bin_b, priority=1,
        notes="injected catch-all — fires on ANY task if tenancy were ignored")

    stub = SimpleNamespace(tenant_id=item_a.tenant_id, item=item_a,
                           from_location=receiving_loc_dock_a,
                           from_location_id=receiving_loc_dock_a.pk)

    # Shape 1: hostile batch kwargs — foreign rule, foreign by_pk, empty on_hand.
    by_pk_b = {loc.pk: loc for loc in Location.objects.filter(tenant=tenant_b)}
    sugg1, reason1, cands1 = resolve_putaway_suggestion(
        stub, rules=[receiving_foreign_rule_b], by_pk=by_pk_b, on_hand={})
    assert sugg1 is None
    assert reason1.startswith("No Suggestion Found")
    assert all(loc.tenant_id == tenant_a.pk for loc, _r in cands1)  # vacuous-but-shaped

    # Shape 2: matching foreign catch-all against the page's real own-tenant map.
    by_pk_a = {loc.pk: loc for loc in Location.objects.filter(tenant=item_a.tenant_id)}
    suggestion, reason, candidates = resolve_putaway_suggestion(
        stub, rules=[foreign_catchall], by_pk=by_pk_a)

    candidate_pks = {loc.pk for loc, _reason in candidates}
    assert receiving_loc_bin_b.pk not in candidate_pks
    assert all(loc.tenant_id == tenant_a.pk for loc, _reason in candidates)
    assert suggestion is None or suggestion.tenant_id == tenant_a.pk
    assert not reason.startswith("Rule:")  # the injected foreign rule never fired


# ---- superuser isolation ------------------------------------------------------------------------------

def test_receiving_superuser_sees_empty_pages_and_foreign_detail_404(
        _receiving_super_client, receiving_foreign_rule_b):
    """tenant=None means NO workspace: list and queue render their empty states with zero
    tenant data, and even a foreign pk stays unreadable (the tenant filter refuses it)."""
    listing = _receiving_super_client.get(reverse("inventory:putawayrule_list"))
    assert listing.status_code == 200
    assert "No putaway rules yet" in listing.content.decode()
    _receiving_assert_no_foreign_marker(listing.content)

    queue = _receiving_super_client.get(reverse("inventory:putaway_suggestions"))
    assert queue.status_code == 200
    assert queue.context["stats"]["open_tasks"] == 0
    _receiving_assert_no_foreign_marker(queue.content)

    assert _receiving_super_client.get(
        reverse("inventory:putawayrule_detail",
                args=[receiving_foreign_rule_b.pk])).status_code == 404


def test_receiving_superuser_create_attempt_writes_no_orphan_row(
        _receiving_super_client, receiving_loc_bin_a, receiving_rule_a):
    """A workspace-less user is bounced off create BEFORE the form runs — no orphan
    tenant=NULL rule may ever exist, and the total row count is untouched."""
    total_before = PutawayRule.objects.count()
    response = _receiving_super_client.post(
        reverse("inventory:putawayrule_create"),
        data=_receiving_rule_payload(destination=receiving_loc_bin_a.pk))
    assert response.status_code == 302
    assert PutawayRule.objects.filter(tenant__isnull=True).count() == 0
    assert PutawayRule.objects.count() == total_before


# ---- XSS -----------------------------------------------------------------------------------------------

def test_receiving_notes_and_item_name_render_escaped(client_a, tenant_a, item_a,
                                                      receiving_loc_bin_a, receiving_task_a):
    """Notes and item names are attacker-controlled free text rendered on three pages —
    autoescape is the only sanitizer any of them may rely on."""
    item_a.name = f"Widget {_XSS_BOLD}"
    item_a.save(update_fields=["name"])
    rule = PutawayRule.objects.create(tenant=tenant_a, item=item_a,
                                      destination=receiving_loc_bin_a, notes=_XSS_SCRIPT)

    listing = client_a.get(reverse("inventory:putawayrule_list")).content.decode()
    assert _XSS_SCRIPT not in listing and _XSS_BOLD not in listing
    assert "&lt;b&gt;" in listing  # the name column renders escaped

    detail = client_a.get(reverse("inventory:putawayrule_detail",
                                  args=[rule.pk])).content.decode()
    assert _XSS_SCRIPT not in detail
    assert "&lt;script&gt;" in detail  # notes render escaped
    assert "&lt;b&gt;" in detail

    queue = client_a.get(reverse("inventory:putaway_suggestions")).content.decode()
    assert _XSS_SCRIPT not in queue and _XSS_BOLD not in queue
    assert "&lt;b&gt;" in queue  # the queue renders the item's name too


# ---- method discipline -----------------------------------------------------------------------------------

def test_receiving_delete_rejects_get(client_a, receiving_rule_a):
    assert client_a.get(reverse("inventory:putawayrule_delete",
                                args=[receiving_rule_a.pk])).status_code == 405


def test_receiving_suggestions_post_is_read_only(client_a, receiving_task_a):
    """As-built the queue is read-only BY CONSTRUCTION (it owns no table) rather than
    require_POST-wrapped — so the security property locked here is harmlessness: a POST
    renders the identical computed page and mutates nothing behind it."""
    get_response = client_a.get(reverse("inventory:putaway_suggestions"))
    assert get_response.status_code == 200
    post_response = client_a.post(reverse("inventory:putaway_suggestions"), data={})
    assert post_response.status_code == 200
    assert post_response.context["stats"] == get_response.context["stats"]
    assert len(post_response.context["rows"]) == 1
    receiving_task_a.refresh_from_db()
    assert receiving_task_a.status == "pending"
