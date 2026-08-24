"""Inventory 5.12 — views.

Five thin CRUD wrappers plus ONE computed page (the Global Stock Visibility roll-up).
Everything here pins the view-level contract: tenant scoping on the list, the filter
and search grammar (junk GET params are harmless), the admin gate on every write,
the frozen eight-key row dicts and four-key stats on the computed page, the
orphan-honest "Unassigned sites" pseudo-row that must appear ONLY on the unfiltered
page, and two regressions: M7 (a padded code saves trimmed) and C4 (a move-less
warehouse must render an honest zero — .get, never a KeyError 500).
"""
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

# Through the leaf module, not the package root — same import shape the views use.
from apps.inventory.models.MultiLocationManagement.LocationNetworks import (
    LocationNetwork,
)

pytestmark = pytest.mark.django_db

_ROW_KEYS = {"node", "path_label", "depth", "own_warehouses",
             "stock_total", "stock_value", "in_transit_in", "in_transit_out"}
_STAT_KEYS = {"sites_attached", "sites_unassigned", "network_stock_total",
              "in_transit_total"}


# ---- module-level helpers -------------------------------------------------------------------------

def _multiloc_node_payload(**overrides):
    """A complete, valid LocationNetworkForm POST body — both FKs blank = root grouping."""
    data = {"code": "", "name": "", "node_type": "store", "parent": "",
            "warehouse": "", "is_active": "on", "notes": ""}
    data.update(overrides)
    return data


def _multiloc_warehouse(tenant, code):
    """A fresh warehouse-typed scm.Location — get_or_create-safe by (tenant, code)."""
    from apps.scm.models import Location
    loc, _created = Location.objects.get_or_create(
        tenant=tenant, code=code,
        defaults={"name": f"Site {code}", "location_type": "warehouse"})
    return loc


def _multiloc_post_stock(item, location, quantity, unit_cost="1"):
    """One receipt move against a site so the grouped ledger map covers it."""
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=location.tenant, item=item, location=location,
        quantity=Decimal(quantity), unit_cost=Decimal(unit_cost),
        move_type="receipt", moved_at=timezone.now())


def _multiloc_row_by_pk(response, node_pk):
    return next(row for row in response.context["rows"]
                if row["node"] is not None and row["node"].pk == node_pk)


# ---- reads ----------------------------------------------------------------------------------------

def test_multiloc_five_pages_render_200(client_a, multiloc_company_a, multiloc_dc_a):
    urls = [
        reverse("inventory:locationnetwork_list"),
        reverse("inventory:locationnetwork_create"),
        reverse("inventory:locationnetwork_detail", args=[multiloc_company_a.pk]),
        reverse("inventory:locationnetwork_edit", args=[multiloc_company_a.pk]),
        reverse("inventory:global_stock"),
    ]
    for url in urls:
        assert client_a.get(url).status_code == 200, url


def test_multiloc_list_shows_seeded_codes_and_scopes_tenant(
        client_a, tenant_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a, multiloc_foreign_node_b):
    hit = client_a.get(reverse("inventory:locationnetwork_list"))
    assert hit.status_code == 200
    # Meta ordering is by CODE (NW-CO-A, NW-DC-A, NW-RG-A, NW-ST-A).
    expected = sorted([multiloc_company_a, multiloc_region_a,
                       multiloc_dc_a, multiloc_store_a], key=lambda n: n.code)
    assert [n.pk for n in hit.context["object_list"]] == [n.pk for n in expected]
    assert multiloc_company_a.code.encode() in hit.content
    assert multiloc_store_a.number.encode() in hit.content
    # The foreign workspace's node never surfaces on acme's list.
    assert multiloc_foreign_node_b.code.encode() not in hit.content


def test_multiloc_list_node_type_filter_counts_sum_to_total(
        client_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a):
    base = reverse("inventory:locationnetwork_list")
    total = len(client_a.get(base).context["object_list"])
    counts = {}
    for node_type in ("company", "region", "dc", "store"):
        hit = client_a.get(base + f"?node_type={node_type}")
        assert hit.status_code == 200
        counts[node_type] = len(hit.context["object_list"])
    assert sum(counts.values()) == total
    assert [n.pk for n in client_a.get(
        base + "?node_type=company").context["object_list"]] == [
        multiloc_company_a.pk]


def test_multiloc_list_is_active_filter_splits_active_inactive(
        client_a, tenant_a, multiloc_company_a, multiloc_store_a):
    retired = LocationNetwork.objects.create(
        tenant=tenant_a, code="NW-OFF", name="Retired Node", is_active=False)
    base = reverse("inventory:locationnetwork_list")
    total = len(client_a.get(base).context["object_list"])
    active = client_a.get(base + "?is_active=active")
    inactive = client_a.get(base + "?is_active=inactive")
    assert active.status_code == inactive.status_code == 200
    assert len(active.context["object_list"]) + \
        len(inactive.context["object_list"]) == total
    assert [n.pk for n in inactive.context["object_list"]] == [retired.pk]
    assert all(n.is_active for n in active.context["object_list"])


def test_multiloc_list_search_matches_code_or_name(
        client_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a):
    base = reverse("inventory:locationnetwork_list")
    by_code = client_a.get(base + "?q=NW-CO")
    assert [n.pk for n in by_code.context["object_list"]] == [multiloc_company_a.pk]
    by_name = client_a.get(base + "?q=downtown")
    assert [n.pk for n in by_name.context["object_list"]] == [multiloc_store_a.pk]
    miss = client_a.get(base + "?q=zzznope")
    assert miss.status_code == 200
    assert len(miss.context["object_list"]) == 0
    assert b"No network nodes found" in miss.content


def test_multiloc_list_junk_params_harmless_and_page_two_renders(
        client_a, tenant_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a):
    # Sixteen rows > per_page 15, so a real page 2 exists.
    for i in range(1, 13):
        LocationNetwork.objects.create(
            tenant=tenant_a, code=f"NW-X{i:02d}", name=f"Extra Node {i}")
    base = reverse("inventory:locationnetwork_list")

    junk = client_a.get(base + "?node_type=junk&is_active=abc&page=999")
    assert junk.status_code == 200
    page_obj = junk.context["page_obj"]
    assert page_obj.number == page_obj.paginator.num_pages == 2

    second = client_a.get(base + "?page=2")
    assert second.status_code == 200
    rows = list(second.context["object_list"])
    assert len(rows) == 1 and rows[0].code == "NW-X12"


def test_multiloc_detail_context_keys_complete(
        client_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a):
    hit = client_a.get(reverse("inventory:locationnetwork_detail",
                               args=[multiloc_region_a.pk]))
    assert hit.status_code == 200
    ctx = hit.context
    assert ctx["obj"].pk == multiloc_region_a.pk
    assert ctx["path_label"] == "NW-CO-A › NW-RG-A"
    assert [c.pk for c in ctx["children"]] == [multiloc_dc_a.pk, multiloc_store_a.pk]
    assert ctx["is_admin"] is True

    root = client_a.get(reverse("inventory:locationnetwork_detail",
                                args=[multiloc_company_a.pk]))
    assert root.context["path_label"] == "NW-CO-A"
    assert [c.pk for c in root.context["children"]] == [multiloc_region_a.pk]


# -- CRUD flows -------------------------------------------------------------------------------------

def test_multiloc_create_flow_posts_302_and_row_saved_active(client_a, tenant_a):
    url = reverse("inventory:locationnetwork_create")
    assert client_a.get(url).status_code == 200
    response = client_a.post(url, data=_multiloc_node_payload(
        code="NW-NEW", name="Probe Region", node_type="region"))
    assert response.status_code == 302
    assert response.url == reverse("inventory:locationnetwork_list")
    created = LocationNetwork.objects.get(tenant=tenant_a, code="NW-NEW")
    assert created.name == "Probe Region"
    assert created.node_type == "region"
    assert created.is_active is True
    assert created.number.startswith("LNW-")


def test_multiloc_create_duplicate_code_rerenders_error_without_row(
        client_a, tenant_a, multiloc_company_a):
    before = LocationNetwork.objects.count()
    response = client_a.post(reverse("inventory:locationnetwork_create"),
                             data=_multiloc_node_payload(
                                 code=multiloc_company_a.code, name="Impostor Co"))
    assert response.status_code == 200
    assert b"already exists" in response.content
    assert not LocationNetwork.objects.filter(name="Impostor Co").exists()
    assert LocationNetwork.objects.count() == before


def test_multiloc_create_padded_code_saved_trimmed_m7_regression(client_a, tenant_a):
    response = client_a.post(reverse("inventory:locationnetwork_create"),
                             data=_multiloc_node_payload(code="  MX-9  ",
                                                         name="Padded Probe"))
    assert response.status_code == 302
    created = LocationNetwork.objects.get(tenant=tenant_a, name="Padded Probe")
    assert created.code == "MX-9"
    assert not LocationNetwork.objects.filter(code="  MX-9  ").exists()


def test_multiloc_edit_persists_changes(client_a, tenant_a, multiloc_region_a,
                                        multiloc_store_a):
    url = reverse("inventory:locationnetwork_edit", args=[multiloc_store_a.pk])
    assert client_a.get(url).status_code == 200
    response = client_a.post(url, data=_multiloc_node_payload(
        code="NW-ST-A", name="Harbor Store", node_type="store",
        parent=multiloc_region_a.pk, notes="Renovated"))
    assert response.status_code == 302
    refreshed = LocationNetwork.objects.get(pk=multiloc_store_a.pk)
    assert refreshed.name == "Harbor Store"
    assert refreshed.notes == "Renovated"
    assert refreshed.parent_id == multiloc_region_a.pk
    assert refreshed.node_type == "store"


def test_multiloc_delete_post_removes_and_get_is_405(client_a, tenant_a):
    doomed = LocationNetwork.objects.create(
        tenant=tenant_a, code="NW-GONE", name="Doomed Node")
    delete_url = reverse("inventory:locationnetwork_delete", args=[doomed.pk])
    assert client_a.get(delete_url).status_code == 405
    response = client_a.post(delete_url)
    assert response.status_code == 302
    assert response.url == reverse("inventory:locationnetwork_list")
    assert not LocationNetwork.objects.filter(pk=doomed.pk).exists()


# ---- the Global Stock Visibility computed page ------------------------------------------------------

def test_multiloc_global_stock_rows_carry_frozen_dict_keys(
        client_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a, multiloc_wh_a):
    hit = client_a.get(reverse("inventory:global_stock"))
    assert hit.status_code == 200
    rows = list(hit.context["rows"])
    assert len(rows) == 4
    for row in rows:
        assert set(row.keys()) == _ROW_KEYS
    assert [row["depth"] for row in rows] == [0, 1, 2, 2]  # pre-order over the tree
    assert hit.context["q"] == ""
    assert hit.context["is_admin"] is True
    stats = hit.context["stats"]
    assert set(stats.keys()) == _STAT_KEYS


def test_multiloc_global_stock_stats_sites_attached_matches_orm(
        client_a, tenant_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_wh_a):

    def _expected():
        attached = (LocationNetwork.objects.filter(tenant=tenant_a)
                    .exclude(warehouse=None).values("warehouse_id"))
        return attached.distinct().count()

    def _unassigned_expected():
        attached = (LocationNetwork.objects.filter(tenant=tenant_a)
                    .exclude(warehouse=None).values("warehouse_id"))
        from apps.scm.models import Location
        return (Location.objects.filter(tenant=tenant_a,
                                        location_type="warehouse")
                .exclude(pk__in=attached).count())

    hit = client_a.get(reverse("inventory:global_stock"))
    assert hit.context["stats"]["sites_attached"] == _expected() == 1
    assert hit.context["stats"]["sites_unassigned"] == _unassigned_expected() == 0

    bare = _multiloc_warehouse(tenant_a, "MWH-U")  # warehouse-typed, NO node yet
    hit = client_a.get(reverse("inventory:global_stock"))
    assert hit.context["stats"]["sites_attached"] == _expected() == 1
    assert hit.context["stats"]["sites_unassigned"] == _unassigned_expected() == 1

    LocationNetwork.objects.create(
        tenant=tenant_a, code="NW-U", name="Attached Bare Site",
        node_type="store", warehouse=bare)
    hit = client_a.get(reverse("inventory:global_stock"))
    assert hit.context["stats"]["sites_attached"] == _expected() == 2
    assert hit.context["stats"]["sites_unassigned"] == _unassigned_expected() == 0


def test_multiloc_global_stock_unassigned_pseudo_row_only_without_q(
        client_a, tenant_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_wh_a, multiloc_store_a):
    _multiloc_warehouse(tenant_a, "MWH-U")  # unattached stocked site -> orphan group

    hit = client_a.get(reverse("inventory:global_stock"))
    pseudo = [row for row in hit.context["rows"] if row["node"] is None]
    assert len(pseudo) == 1
    assert pseudo[0]["path_label"] == "Unassigned sites"
    assert [w.code for w in pseudo[0]["own_warehouses"]] == ["MWH-U"]

    # ?q= that matches nothing suppresses the pseudo-row: the honest empty state wins.
    miss = client_a.get(reverse("inventory:global_stock"), {"q": "zzz"})
    assert miss.status_code == 200
    assert miss.context["rows"] == []
    assert b"No nodes match your search" in miss.content
    assert miss.context["stats"]["sites_unassigned"] == 1  # still counted honestly


def test_multiloc_global_stock_rollup_computes_from_ledger(
        client_a, item_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a, multiloc_wh_a):
    _multiloc_post_stock(item_a, multiloc_wh_a, "6", "2.00")
    _multiloc_post_stock(item_a, multiloc_wh_a, "4", "1.00")

    hit = client_a.get(reverse("inventory:global_stock"))
    assert hit.status_code == 200
    by_label = {row["path_label"]: row for row in hit.context["rows"]}

    company = by_label["NW-CO-A"]
    assert company["own_warehouses"] == []          # pure grouping at the root
    assert company["stock_total"] == Decimal("10")  # whole subtree rolls up...
    assert company["stock_value"] == Decimal("16")

    dc = by_label["NW-CO-A › NW-RG-A › NW-DC-A"]
    assert [w.code for w in dc["own_warehouses"]] == ["MWH-A"]  # the DC IS its site
    assert dc["stock_total"] == Decimal("10")

    store = by_label["NW-CO-A › NW-RG-A › NW-ST-A"]
    assert store["stock_total"] == Decimal("0")     # zeros are real zeros
    assert store["stock_value"] == Decimal("0")

    stats = hit.context["stats"]
    assert stats["network_stock_total"] == Decimal("10")
    assert stats["in_transit_total"] == Decimal("0")


def test_multiloc_c4_regression_moveless_warehouse_renders_zero_not_500(
        client_a, item_a, multiloc_region_a, multiloc_dc_a, multiloc_wh_a):
    """C4 regression: the ledger maps are keyed by MOVED locations only, so any
    subtree containing a move-less site must read .get defaults — before the fix a
    bare [pk] lookup KeyError'd the whole page into a 500."""
    _multiloc_post_stock(item_a, multiloc_wh_a, "7", "3.00")  # maps exist, key MWH-A only

    fresh = _multiloc_warehouse(multiloc_region_a.tenant, "MWH-FRESH")  # NO moves ever
    node = LocationNetwork.objects.create(
        tenant=multiloc_region_a.tenant, code="NW-FRESH", name="Fresh Site",
        node_type="dc", parent=multiloc_region_a, warehouse=fresh)

    hit = client_a.get(reverse("inventory:global_stock"))
    assert hit.status_code == 200  # the KeyError would have blown up right here

    row = _multiloc_row_by_pk(hit, node.pk)
    assert row["stock_total"] == Decimal("0")
    assert row["stock_value"] == Decimal("0")
    assert [w.code for w in row["own_warehouses"]] == ["MWH-FRESH"]
    assert hit.context["stats"]["network_stock_total"] == Decimal("7")  # fresh adds zero


def test_multiloc_global_stock_query_budget_within_twelve(
        client_a, item_a, multiloc_company_a, multiloc_region_a, multiloc_dc_a,
        multiloc_store_a, multiloc_wh_a):
    _multiloc_post_stock(item_a, multiloc_wh_a, "3", "1.00")
    url = reverse("inventory:global_stock")
    assert client_a.get(url).status_code == 200  # warm-up outside the capture

    with CaptureQueriesContext(connection) as ctx:
        response = client_a.get(url)
    assert response.status_code == 200
    issued = len(ctx.captured_queries)
    assert issued >= 4   # the view's own FOUR frozen reads really ran
    assert issued <= 12, f"global-stock issued {issued} queries (budget 12)"


# ---- gating ---------------------------------------------------------------------------------------

def test_multiloc_member_gating_writes_403_reads_open(
        member_client, multiloc_company_a, multiloc_store_a):
    writes = [
        ("get", reverse("inventory:locationnetwork_create"), None),
        ("post", reverse("inventory:locationnetwork_create"),
         _multiloc_node_payload(code="NW-SNEAK", name="Sneaky Node")),
        ("get", reverse("inventory:locationnetwork_edit",
                        args=[multiloc_store_a.pk]), None),
        ("post", reverse("inventory:locationnetwork_edit",
                         args=[multiloc_store_a.pk]), {}),
        ("post", reverse("inventory:locationnetwork_delete",
                         args=[multiloc_store_a.pk]), None),
    ]
    for method, url, data in writes:
        if method == "post":
            assert member_client.post(url, data).status_code == 403, url
        else:
            assert member_client.get(url).status_code == 403, url
    assert not LocationNetwork.objects.filter(code="NW-SNEAK").exists()

    for name in ["locationnetwork_list", "global_stock"]:
        hit = member_client.get(reverse(f"inventory:{name}"))
        assert hit.status_code == 200, name
        assert hit.context["is_admin"] is False
    detail = member_client.get(reverse("inventory:locationnetwork_detail",
                                       args=[multiloc_company_a.pk]))
    assert detail.status_code == 200
    assert detail.context["is_admin"] is False


# ---- rendered hygiene -----------------------------------------------------------------------------

def test_multiloc_pages_contain_no_template_comment_leaks(
        client_a, multiloc_company_a):
    pages = [
        reverse("inventory:locationnetwork_list"),
        reverse("inventory:locationnetwork_create"),
        reverse("inventory:locationnetwork_detail", args=[multiloc_company_a.pk]),
        reverse("inventory:locationnetwork_edit", args=[multiloc_company_a.pk]),
        reverse("inventory:global_stock"),
    ]
    for url in pages:
        content = client_a.get(url).content
        assert b"{#" not in content, url
