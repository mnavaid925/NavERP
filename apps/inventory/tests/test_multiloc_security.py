"""Inventory 5.12 Multi-Location Management — security.

Adversarial multi-tenancy around the org-tree CRUD and the computed Global Stock
page: cross-tenant IDOR on every route shape (GET pages, edit/delete POSTs),
crafted-POST FK injection against EACH foreign pointer (parent — a SELF-FK — and
warehouse), the privilege-escalation regression (a plain member must never reach
the tenant-admin-only writes — the decorator checks ROLE before require_POST so
the answer is a 403, never a misleading 405) with reads left open and ``is_admin``
False, the anonymous wall over ALL SIX routes, tenant-less superuser isolation
(no 500, no orphan tenant=NULL nodes), escaping of attacker-controlled node text,
method discipline (delete POST-only; the read-only Global Stock page answers a
POST harmlessly), the mass-assignment contract (``number``/``tenant`` are
system-set and stay off the form entirely, so a crafted POST cannot forge them),
and cycle-injection abuse: an ORM-crafted looping parent chain degrades to a
field error through the model's bounded seen-set walk — never an infinite loop.

House note: ``base.html`` ships legit ``<script>`` tags, so escape probes assert
the FULL payload (``<script>alert(1)</script>``) is absent — never the bare
``<script>`` prefix (same idiom as 5.2/5.4/5.9).
"""
import time
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

# Through the leaf modules, not the package roots — same import shape the views
# and the conftest helpers use for this sub-module.
from apps.inventory.forms.MultiLocationManagement.LocationNetworks import (
    LocationNetworkForm,
)
from apps.inventory.models.MultiLocationManagement.LocationNetworks import (
    LocationNetwork,
)

pytestmark = pytest.mark.django_db

_XSS_SCRIPT = "<script>alert(1)</script>"

#: A form edit must complete well inside this budget even against a malformed
#: looping tree — the property under test is the BOUNDED walk, not raw speed.
_CYCLE_BUDGET_SECONDS = 10.0


# ---- module-level helpers ------------------------------------------------------------------------

def _multiloc_assert_login_redirect(response):
    assert response.status_code == 302
    assert "/login" in response.url or response.url.endswith("login")


def _multiloc_node_payload(**overrides):
    """A minimal VALID node POST body — code/name are the only required fields
    (both FKs nullable, node_type defaults to store); overrides carry the
    adversarial bits."""
    data = {"code": "", "name": "", "node_type": "store", "parent": "",
            "warehouse": "", "is_active": "on", "notes": ""}
    data.update(overrides)
    return data


def _multiloc_assert_foreign_fk_error(html):
    """The scoped <select> usually refuses first ("valid choice"); the form's
    ``_reject_foreign`` wording is the fallback when a stale pk still parses."""
    assert ("not one of the available choices" in html
            or "That record belongs to another workspace." in html)


def _multiloc_stock_warehouse(item, location, *, quantity="6"):
    """One receipt move against a site so Global Stock's grouped ledger map covers
    it — that map is keyed by MOVED locations only, and every warehouse id under a
    rendered node is indexed into it directly."""
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=location.tenant, item=item, location=location,
        quantity=Decimal(quantity), unit_cost=Decimal("2"), move_type="receipt",
        moved_at=timezone.now())


# ---- local fixtures ------------------------------------------------------------------------------

@pytest.fixture
def _multiloc_tenantless_superuser(db):
    """The platform superuser: tenant=None BY DESIGN — it owns no workspace at all."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="sec-super@naverp.test", username="sec_superuser_multiloc",
        password="TestPass123!", tenant=None, is_superuser=True, is_staff=True)


@pytest.fixture
def _multiloc_super_client(_multiloc_tenantless_superuser):
    c = Client()
    c.force_login(_multiloc_tenantless_superuser)
    return c


# ---- IDOR ----------------------------------------------------------------------------------------

def test_multiloc_idor_get_detail_and_edit_404(client_a, multiloc_foreign_node_b):
    """A foreign node pk must read as nonexistent to another workspace's admin."""
    for name in ["locationnetwork_detail", "locationnetwork_edit"]:
        url = reverse(f"inventory:{name}", args=[multiloc_foreign_node_b.pk])
        assert client_a.get(url).status_code == 404


def test_multiloc_idor_write_posts_404_and_foreign_node_intact(
        client_a, multiloc_foreign_node_b, multiloc_wh_b):
    """The write shapes are where an IDOR would do damage: an edit POST carrying a
    hijacking body and the destructive delete POST must both 404 on a foreign pk
    and leave Globex's node exactly where it was."""
    response = client_a.post(
        reverse("inventory:locationnetwork_edit", args=[multiloc_foreign_node_b.pk]),
        data=_multiloc_node_payload(code="HIJACKED", name="Hijacked Holding",
                                    node_type="company", warehouse=multiloc_wh_b.pk))
    assert response.status_code == 404

    total_before = LocationNetwork.objects.count()
    assert client_a.post(
        reverse("inventory:locationnetwork_delete", args=[multiloc_foreign_node_b.pk])
    ).status_code == 404
    assert LocationNetwork.objects.count() == total_before

    multiloc_foreign_node_b.refresh_from_db()  # raises if deleted — the real assertions
    assert multiloc_foreign_node_b.code == "NW-B"
    assert multiloc_foreign_node_b.name == "Globex Holding Co"


# ---- crafted-POST cross-tenant FK injection ---------------------------------------------------------

@pytest.mark.parametrize("field_name,foreign_fixture", [
    ("parent", "multiloc_foreign_node_b"),
    ("warehouse", "multiloc_wh_b"),
])
def test_multiloc_create_rejects_each_foreign_fk(client_a, field_name, foreign_fixture,
                                                 request):
    """Each tenant-scoped pointer, aimed at Globex one at a time: the create form
    re-renders with THAT field's error and not one node appears anywhere."""
    foreign = request.getfixturevalue(foreign_fixture)
    data = _multiloc_node_payload(code="NW-EVIL", name="Injected Node",
                                  **{field_name: foreign.pk})

    total_before = LocationNetwork.objects.count()
    response = client_a.post(reverse("inventory:locationnetwork_create"), data=data)
    assert response.status_code == 200
    _multiloc_assert_foreign_fk_error(response.content.decode())
    assert LocationNetwork.objects.count() == total_before
    assert not LocationNetwork.objects.filter(code="NW-EVIL").exists()


def test_multiloc_edit_cannot_swap_own_parent_to_foreign(
        client_a, multiloc_store_a, multiloc_region_a, multiloc_foreign_node_b):
    """The crafted-POST vector on EDIT: swapping an OWN node's parent to a foreign
    node must fail as a form error and leave the stored FK untouched."""
    response = client_a.post(
        reverse("inventory:locationnetwork_edit", args=[multiloc_store_a.pk]),
        data=_multiloc_node_payload(code="NW-ST-A", name="Downtown Store",
                                    node_type="store",
                                    parent=multiloc_foreign_node_b.pk))
    assert response.status_code == 200
    _multiloc_assert_foreign_fk_error(response.content.decode())
    multiloc_store_a.refresh_from_db()
    assert multiloc_store_a.parent_id == multiloc_region_a.pk


# ---- privilege escalation (C2): member vs the tenant-admin-only writes ------------------------------

def test_multiloc_member_writes_are_tenant_admin_gated(member_client, multiloc_store_a):
    """Node config is workspace-admin territory: the decorator chain checks the ROLE
    before require_POST, so a member's GET *and* POST on create/edit/delete get a
    403 (never a misleading 405) and nothing is written or deleted behind them."""
    total_before = LocationNetwork.objects.count()

    assert member_client.get(reverse("inventory:locationnetwork_create")).status_code == 403
    assert member_client.post(
        reverse("inventory:locationnetwork_create"),
        data=_multiloc_node_payload(code="NW-SNEAK", name="Sneaky Node")
    ).status_code == 403
    edit_url = reverse("inventory:locationnetwork_edit", args=[multiloc_store_a.pk])
    assert member_client.get(edit_url).status_code == 403
    assert member_client.post(edit_url).status_code == 403
    delete_url = reverse("inventory:locationnetwork_delete", args=[multiloc_store_a.pk])
    assert member_client.get(delete_url).status_code == 403   # role checked BEFORE require_POST
    assert member_client.post(delete_url).status_code == 403

    assert LocationNetwork.objects.count() == total_before
    assert not LocationNetwork.objects.filter(code="NW-SNEAK").exists()
    multiloc_store_a.refresh_from_db()  # nothing was deleted despite the POSTs


def test_multiloc_member_reads_open_with_is_admin_false(member_client, multiloc_dc_a,
                                                        multiloc_wh_a, item_a):
    """Reads stay open to every signed-in member — list, detail AND the computed
    Global Stock roll-up — with ``is_admin`` False so no write affordance renders."""
    _multiloc_stock_warehouse(item_a, multiloc_wh_a)

    listing = member_client.get(reverse("inventory:locationnetwork_list"))
    assert listing.status_code == 200
    assert listing.context["is_admin"] is False

    detail = member_client.get(
        reverse("inventory:locationnetwork_detail", args=[multiloc_dc_a.pk]))
    assert detail.status_code == 200
    assert detail.context["is_admin"] is False

    stock = member_client.get(reverse("inventory:global_stock"))
    assert stock.status_code == 200
    assert stock.context["is_admin"] is False
    dc_row = next(row for row in stock.context["rows"]
                  if row["node"] is not None and row["node"].pk == multiloc_dc_a.pk)
    assert dc_row["stock_total"] == Decimal("6")  # the roll-up really computed


# ---- auth walls ---------------------------------------------------------------------------------------

def test_multiloc_anonymous_redirected_on_all_six_routes(client, multiloc_company_a):
    """Every 5.12 route sits behind @login_required — the three plain pages and the
    three detail-shaped routes. No exception, no leak on the redirect page."""
    plain_routes = ["locationnetwork_list", "locationnetwork_create", "global_stock"]
    argged_routes = ["locationnetwork_detail", "locationnetwork_edit",
                     "locationnetwork_delete"]
    for name in plain_routes:
        _multiloc_assert_login_redirect(client.get(reverse(f"inventory:{name}")))
    for name in argged_routes:
        url = reverse(f"inventory:{name}", args=[multiloc_company_a.pk])
        _multiloc_assert_login_redirect(client.get(url))


# ---- tenant-less superuser isolation ---------------------------------------------------------------------

def test_multiloc_tenantless_superuser_no_500_no_orphan_rows(
        _multiloc_super_client, multiloc_foreign_node_b, multiloc_wh_a):
    """tenant=None means NO workspace: list and Global Stock render their empty
    states with zero tenant data, create is bounced BEFORE the form runs (GET and
    POST alike), and no node may ever exist with a NULL tenant afterwards."""
    listing = _multiloc_super_client.get(reverse("inventory:locationnetwork_list"))
    assert listing.status_code == 200
    assert "No network nodes found" in listing.content.decode()
    assert "Globex Holding Co" not in listing.content.decode()

    stock = _multiloc_super_client.get(reverse("inventory:global_stock"))
    assert stock.status_code == 200
    assert stock.context["rows"] == []
    assert stock.context["stats"]["sites_attached"] == 0
    assert stock.context["stats"]["network_stock_total"] == 0

    total_before = LocationNetwork.objects.count()
    create_url = reverse("inventory:locationnetwork_create")
    assert _multiloc_super_client.get(create_url).status_code == 302
    assert _multiloc_super_client.post(
        create_url,
        data=_multiloc_node_payload(code="NW-ORPHAN", name="Orphan Node",
                                    warehouse=multiloc_wh_a.pk)
    ).status_code == 302

    assert LocationNetwork.objects.filter(tenant__isnull=True).count() == 0
    assert LocationNetwork.objects.count() == total_before


# ---- XSS -------------------------------------------------------------------------------------------------

def test_multiloc_node_text_renders_escaped_on_list_detail_global_stock(
        client_a, tenant_a):
    """Node name and notes are attacker-controlled free text rendered on all three
    pages — autoescape is the only sanitizer any of them may rely on. The name
    carries the probe too because list/Global Stock surface the NAME (only the
    detail page prints notes)."""
    node = LocationNetwork.objects.create(
        tenant=tenant_a, code="NW-XSS", name=_XSS_SCRIPT, node_type="store",
        notes=_XSS_SCRIPT)

    listing = client_a.get(reverse("inventory:locationnetwork_list")).content.decode()
    assert _XSS_SCRIPT not in listing
    assert "&lt;script&gt;" in listing

    detail = client_a.get(
        reverse("inventory:locationnetwork_detail", args=[node.pk])).content.decode()
    assert _XSS_SCRIPT not in detail
    assert "&lt;script&gt;" in detail  # notes render escaped on the detail page

    stock = client_a.get(reverse("inventory:global_stock")).content.decode()
    assert _XSS_SCRIPT not in stock
    assert "&lt;script&gt;" in stock  # the roll-up row prints the node's name too


def test_multiloc_q_echo_rendered_escaped(client_a):
    """Both search boxes echo ?q straight back into the page (input value, and the
    Global Stock no-match message) — reflected-input hygiene."""
    for name in ["locationnetwork_list", "global_stock"]:
        response = client_a.get(reverse(f"inventory:{name}"), {"q": _XSS_SCRIPT})
        assert response.status_code == 200
        html = response.content.decode()
        assert _XSS_SCRIPT not in html
        assert "&lt;script&gt;" in html


# ---- method discipline -------------------------------------------------------------------------------------

def test_multiloc_delete_rejects_get(client_a, multiloc_company_a):
    assert client_a.get(
        reverse("inventory:locationnetwork_delete", args=[multiloc_company_a.pk])
    ).status_code == 405
    multiloc_company_a.refresh_from_db()  # the GET probe removed nothing


def test_multiloc_global_stock_post_is_read_only_consistent(client_a, multiloc_company_a,
                                                            multiloc_dc_a, item_a,
                                                            multiloc_wh_a):
    """As-built Global Stock is read-only BY CONSTRUCTION (it owns zero writes)
    rather than require_POST-wrapped, so a mutation attempt answers the ordinary
    200 page — the property locked here is harmlessness: identical stats, same
    rows, zero state movement behind it."""
    _multiloc_stock_warehouse(item_a, multiloc_wh_a)

    get_response = client_a.get(reverse("inventory:global_stock"))
    assert get_response.status_code == 200
    get_rows = [row["path_label"] for row in get_response.context["rows"]]

    total_before = LocationNetwork.objects.count()
    post_response = client_a.post(reverse("inventory:global_stock"), data={})
    assert post_response.status_code == 200  # actual behaviour: plain re-render
    assert post_response.context["stats"] == get_response.context["stats"]
    assert ([row["path_label"] for row in post_response.context["rows"]] == get_rows)

    multiloc_company_a.refresh_from_db()
    multiloc_dc_a.refresh_from_db()
    assert LocationNetwork.objects.count() == total_before


# ---- mass assignment ----------------------------------------------------------------------------------------

def test_multiloc_form_drops_injected_keys_from_cleaned_data(tenant_a):
    """Unit-level contract: number/tenant are system-set (TenantNumbered save() /
    the CRUD helper) and are NOT form fields, so a bound payload carrying them
    loses them silently — they never reach cleaned_data and can never be written
    by a save() from this form."""
    data = _multiloc_node_payload(code="NW-MAS", name="Mass Node",
                                  number="LNW-99999", tenant=str(tenant_a.pk))
    form = LocationNetworkForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    for key in ["number", "tenant"]:
        assert key not in form.fields
        assert key not in form.cleaned_data


def test_multiloc_crafted_edit_post_cannot_forge_number_or_tenant(
        client_a, tenant_a, tenant_b, multiloc_company_a):
    """View-level regression: a crafted edit POST injecting number=LNW-99999 plus a
    hijacked tenant= saves its LEGITIMATE fields (302) but leaves the system-set
    columns strictly alone — numbering stays per-workspace and owned."""
    original_number = multiloc_company_a.number
    response = client_a.post(
        reverse("inventory:locationnetwork_edit", args=[multiloc_company_a.pk]),
        data=_multiloc_node_payload(code="NW-CO-A", name="Renamed Holding Co",
                                    node_type="company",
                                    number="LNW-99999", tenant=str(tenant_b.pk)))
    assert response.status_code == 302  # the edit itself succeeded...

    multiloc_company_a.refresh_from_db()
    assert multiloc_company_a.name == "Renamed Holding Co"  # ...and really saved
    assert multiloc_company_a.number == original_number
    assert multiloc_company_a.tenant_id == tenant_a.pk


# ---- cycle injection abuse -----------------------------------------------------------------------------------

def test_multiloc_cycle_chain_form_edit_refused_fast(client_a, tenant_a):
    """Loop injection cannot hang anything. TWO shapes:

    1. A crafted ORM parent CHAIN (root ← child), then a FORM edit aiming the root
       back at its own descendant: the model's bounded seen-set walk refuses it as
       a plain field error — never a hang, never a 500, no rows moved.
    2. The STRONGER malformed row — a SELF-PARENT forced past validation via a bare
       queryset update — must still render detail and Global Stock promptly (the
       bounded walk completing IS the proof) and a further form edit on it dies as
       the explicit self-parent field error.
    """
    chain_root = LocationNetwork.objects.create(
        tenant=tenant_a, code="NW-L1", name="Chain Root", node_type="region")
    chain_child = LocationNetwork.objects.create(
        tenant=tenant_a, code="NW-L2", name="Chain Child", node_type="store",
        parent=chain_root)
    total_before = LocationNetwork.objects.count()

    # Shape 1: form edit forging the loop root -> child -> root.
    started = time.monotonic()
    response = client_a.post(
        reverse("inventory:locationnetwork_edit", args=[chain_root.pk]),
        data=_multiloc_node_payload(code="NW-L1", name="Chain Root",
                                    node_type="region", parent=chain_child.pk))
    elapsed = time.monotonic() - started
    assert response.status_code == 200
    assert "loop" in response.content.decode()
    assert elapsed < _CYCLE_BUDGET_SECONDS

    # Shape 2: the malformed self-parent row, crafted BELOW the validation layer.
    loopy = LocationNetwork.objects.create(
        tenant=tenant_a, code="NW-LOOP", name="Loopy Node", node_type="store")
    LocationNetwork.objects.filter(pk=loopy.pk).update(parent=loopy.pk)
    loopy.refresh_from_db()
    assert loopy.parent_id == loopy.pk

    started = time.monotonic()
    detail = client_a.get(
        reverse("inventory:locationnetwork_detail", args=[loopy.pk]))
    stock = client_a.get(reverse("inventory:global_stock"))
    assert detail.status_code == 200 and stock.status_code == 200
    elapsed = time.monotonic() - started
    assert elapsed < _CYCLE_BUDGET_SECONDS  # the bounded walks completed — no hang

    edit_again = client_a.post(
        reverse("inventory:locationnetwork_edit", args=[loopy.pk]),
        data=_multiloc_node_payload(code="NW-LOOP", name="Loopy Node",
                                    node_type="store", parent=loopy.pk))
    assert edit_again.status_code == 200
    assert "cannot be its own parent" in edit_again.content.decode()

    assert LocationNetwork.objects.count() == total_before + 1  # only `loopy` was added
    chain_root.refresh_from_db()
    assert chain_root.parent_id is None          # the forged loop never landed
    chain_child.refresh_from_db()
    assert chain_child.parent_id == chain_root.pk  # original placement intact
