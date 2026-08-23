"""Inventory 5.9 — views.

The wave pages are five thin CRUD wrappers plus three lifecycle verbs, two membership
verbs and ONE computed page (the Wave Planning board). Everything here pins the view-level
contract: tenant scoping, the admin gate on every write, the release lock on membership,
the server-side edit guard on non-planned waves, and the duplicate-add refusal that must
land as a flash instead of an IntegrityError 500.
"""
import datetime

import pytest
from django.urls import reverse

from apps.inventory.models import FulfillmentWave, FulfillmentWaveOrder

pytestmark = pytest.mark.django_db


def _fulfillment_wave_data(location, carrier, description="Probe wave"):
    """A complete, valid FulfillmentWaveForm payload."""
    return {
        "description": description,
        "location": location.pk if location else "",
        "carrier": carrier.pk if carrier else "",
        "ship_method": "standard",
        "planned_ship_date": "2026-09-01",
        "cutoff_at": "2026-08-31 18:00",
        "priority": "60",
        "criteria_text": "All submitted probe orders",
        "notes": "",
    }


def _fulfillment_open_so(customer_party, item):
    """A fresh open (submitted) scm.SalesOrder with one line — same shape as the seeder."""
    from decimal import Decimal

    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(
        tenant=customer_party.tenant, customer=customer_party, status="submitted",
        source_channel="manual", order_date=datetime.date(2026, 8, 21))
    SalesOrderLine.objects.create(
        sales_order=order, item=item, quantity_ordered=Decimal("4"),
        unit_price=Decimal("15.00"))
    order.recalc_totals()
    return order


def _fulfillment_flash(client, url):
    """GET a redirect target following the chain so stored messages render."""
    return client.get(url, follow=True)


# -- reads ---------------------------------------------------------------------------------------

def test_fulfillment_six_pages_render_200(client_a, tenant_a, fulfillment_wave_planned_a,
                                          fulfillment_wave_released_a):
    urls = [
        reverse("inventory:wave_list"),
        reverse("inventory:wave_create"),
        reverse("inventory:wave_detail", args=[fulfillment_wave_planned_a.pk]),
        reverse("inventory:wave_edit", args=[fulfillment_wave_planned_a.pk]),
        reverse("inventory:wave_board"),
    ]
    for url in urls:
        assert client_a.get(url).status_code == 200, url


def test_fulfillment_list_shows_seeded_numbers_and_member_count_annotation(
        client_a, fulfillment_wave_planned_a, fulfillment_wave_released_a):
    hit = client_a.get(reverse("inventory:wave_list"))
    assert hit.status_code == 200
    assert fulfillment_wave_planned_a.number.encode() in hit.content
    assert fulfillment_wave_released_a.number.encode() in hit.content
    rows = list(hit.context["object_list"])
    assert rows
    # The N+1 fix: member_count comes off the annotate() call, not a per-row query.
    for w in rows:
        assert w.member_count == FulfillmentWaveOrder.objects.filter(wave=w).count()


def test_fulfillment_list_status_filter_counts_sum_to_total(
        client_a, fulfillment_wave_planned_a, fulfillment_wave_released_a):
    base = reverse("inventory:wave_list")
    total = len(client_a.get(base).context["object_list"])
    planned = len(client_a.get(base + "?status=planned").context["object_list"])
    released = len(client_a.get(base + "?status=released").context["object_list"])
    closed = client_a.get(base + "?status=closed")
    assert closed.status_code == 200
    assert len(closed.context["object_list"]) == 0
    assert planned + released == total
    assert planned >= 1 and released >= 1


def test_fulfillment_list_search_matches_description_and_junk_page_clamps(
        client_a, fulfillment_wave_planned_a, fulfillment_wave_released_a):
    base = reverse("inventory:wave_list")
    hit = client_a.get(base + "?q=backlog")
    assert hit.status_code == 200
    assert [w.pk for w in hit.context["object_list"]] == [fulfillment_wave_planned_a.pk]
    miss = client_a.get(base + "?q=zzznope")
    assert miss.status_code == 200
    assert len(miss.context["object_list"]) == 0
    junk = client_a.get(base + "?page=999")
    assert junk.status_code == 200
    assert junk.context["page_obj"].number == junk.context["page_obj"].paginator.num_pages


def test_fulfillment_detail_context_keys_complete(
        client_a, fulfillment_wave_planned_a, fulfillment_member_a):
    hit = client_a.get(reverse("inventory:wave_detail",
                               args=[fulfillment_wave_planned_a.pk]))
    assert hit.status_code == 200
    ctx = hit.context
    assert ctx["obj"].pk == fulfillment_wave_planned_a.pk
    assert [m.pk for m in ctx["members"]] == [fulfillment_member_a.pk]
    assert ctx["linked_picks"] is not None
    assert ctx["is_admin"] is True
    # Honesty rule at the view boundary: no picks reference this number yet -> None.
    assert ctx["pick_pct"] is None
    assert ctx["add_form"] is not None


def test_fulfillment_detail_add_form_none_for_non_admin_or_non_planned(
        member_client, client_a, fulfillment_wave_planned_a, fulfillment_wave_released_a,
        fulfillment_member_a):
    plain = member_client.get(reverse("inventory:wave_detail",
                                      args=[fulfillment_wave_planned_a.pk]))
    assert plain.status_code == 200
    assert plain.context["add_form"] is None
    assert plain.context["is_admin"] is False
    released = client_a.get(reverse("inventory:wave_detail",
                                    args=[fulfillment_wave_released_a.pk]))
    assert released.status_code == 200
    assert released.context["is_admin"] is True
    assert released.context["add_form"] is None


# -- CRUD flows ----------------------------------------------------------------------------------

def test_fulfillment_create_flow_posts_302_and_row_is_planned(
        client_a, tenant_a, fulfillment_loc_wave_a, fulfillment_carrier_a):
    url = reverse("inventory:wave_create")
    assert client_a.get(url).status_code == 200
    response = client_a.post(url, _fulfillment_wave_data(
        fulfillment_loc_wave_a, fulfillment_carrier_a, description="Create probe"))
    assert response.status_code == 302
    assert response.url == reverse("inventory:wave_list")
    created = FulfillmentWave.objects.get(tenant=tenant_a, description="Create probe")
    assert created.status == "planned"
    assert created.number.startswith("WAV-")
    assert created.released_at is None


def test_fulfillment_create_with_foreign_location_rerenders_error(
        client_a, tenant_a, location_b, fulfillment_carrier_a):
    response = client_a.post(reverse("inventory:wave_create"), _fulfillment_wave_data(
        location_b, fulfillment_carrier_a, description="Cross-tenant probe"))
    assert response.status_code == 200
    assert not FulfillmentWave.objects.filter(
        tenant=tenant_a, description="Cross-tenant probe").exists()


def test_fulfillment_edit_on_planned_persists_changes(
        client_a, fulfillment_wave_planned_a, fulfillment_loc_wave_a,
        fulfillment_carrier_a):
    url = reverse("inventory:wave_edit", args=[fulfillment_wave_planned_a.pk])
    assert client_a.get(url).status_code == 200
    data = _fulfillment_wave_data(fulfillment_loc_wave_a, fulfillment_carrier_a,
                                  description="Rewritten backlog wave")
    data["priority"] = "10"
    response = client_a.post(url, data)
    assert response.status_code == 302
    refreshed = FulfillmentWave.objects.get(pk=fulfillment_wave_planned_a.pk)
    assert refreshed.description == "Rewritten backlog wave"
    assert refreshed.priority == 10


def test_fulfillment_edit_on_released_refuses_with_flash(
        client_a, fulfillment_wave_released_a, fulfillment_loc_wave_a,
        fulfillment_carrier_a):
    original = fulfillment_wave_released_a.description
    url = reverse("inventory:wave_edit", args=[fulfillment_wave_released_a.pk])
    response = client_a.post(url, _fulfillment_wave_data(
        fulfillment_loc_wave_a, fulfillment_carrier_a, description="Smuggled rewrite"))
    # The server guard fires BEFORE the form binds: redirect + flash, never a rewrite.
    assert response.status_code == 302
    assert response.url == reverse("inventory:wave_detail",
                                   args=[fulfillment_wave_released_a.pk])
    refreshed = FulfillmentWave.objects.get(pk=fulfillment_wave_released_a.pk)
    assert refreshed.description == original
    assert refreshed.status == "released"
    flashed = client_a.get(response.url, follow=True)
    assert b"no longer be edited" in flashed.content


def test_fulfillment_delete_post_cascades_memberships_and_get_is_405(
        client_a, fulfillment_wave_planned_a, fulfillment_member_a):
    delete_url = reverse("inventory:wave_delete", args=[fulfillment_wave_planned_a.pk])
    assert client_a.get(delete_url).status_code == 405
    response = client_a.post(delete_url)
    assert response.status_code == 302
    assert not FulfillmentWave.objects.filter(pk=fulfillment_wave_planned_a.pk).exists()
    assert not FulfillmentWaveOrder.objects.filter(pk=fulfillment_member_a.pk).exists()


# -- lifecycle verbs -----------------------------------------------------------------------------

def test_fulfillment_release_stamps_released_at(
        client_a, fulfillment_wave_planned_a, fulfillment_member_a):
    response = client_a.post(reverse("inventory:wave_release",
                                     args=[fulfillment_wave_planned_a.pk]))
    assert response.status_code == 302
    refreshed = FulfillmentWave.objects.get(pk=fulfillment_wave_planned_a.pk)
    assert refreshed.status == "released"
    assert refreshed.released_at is not None


def test_fulfillment_close_stamps_closed_at(
        client_a, fulfillment_wave_released_a):
    response = client_a.post(reverse("inventory:wave_close",
                                     args=[fulfillment_wave_released_a.pk]))
    assert response.status_code == 302
    refreshed = FulfillmentWave.objects.get(pk=fulfillment_wave_released_a.pk)
    assert refreshed.status == "closed"
    assert refreshed.closed_at is not None


def test_fulfillment_cancel_path_flips_to_cancelled(
        client_a, fulfillment_wave_planned_a):
    response = client_a.post(reverse("inventory:wave_cancel",
                                     args=[fulfillment_wave_planned_a.pk]))
    assert response.status_code == 302
    refreshed = FulfillmentWave.objects.get(pk=fulfillment_wave_planned_a.pk)
    assert refreshed.status == "cancelled"


def test_fulfillment_double_release_refused_via_flash_not_500(
        client_a, fulfillment_wave_planned_a, fulfillment_member_a):
    url = reverse("inventory:wave_release", args=[fulfillment_wave_planned_a.pk])
    first = client_a.post(url)
    assert first.status_code == 302
    second = client_a.post(url)
    assert second.status_code == 302  # EXPECTED traffic lands as a message, never a 500.
    flashed = client_a.get(second.url, follow=True)
    assert b"cannot be released" in flashed.content
    refreshed = FulfillmentWave.objects.get(pk=fulfillment_wave_planned_a.pk)
    assert refreshed.status == "released"
    assert not refreshed.is_editable


# -- the Wave Planning board ---------------------------------------------------------------------

def test_fulfillment_board_stats_keys_and_row_dicts(
        client_a, tenant_a, fulfillment_wave_planned_a, fulfillment_wave_released_a,
        fulfillment_member_a):
    hit = client_a.get(reverse("inventory:wave_board"))
    assert hit.status_code == 200
    stats = hit.context["stats"]
    assert set(stats.keys()) == {"open_waves", "released_today", "unassigned_orders"}
    # Stats describe the FULL tenant-scoped set: one planned + one released today.
    assert stats["open_waves"] == FulfillmentWave.objects.filter(
        tenant=tenant_a, status="planned").count()
    assert stats["released_today"] >= 1
    rows = list(hit.context["object_list"])
    assert len(rows) == 2
    for row in rows:
        assert set(row.keys()) == {"wave", "members", "fulfilled", "pick_pct"}
        assert isinstance(row["members"], int)
        assert isinstance(row["fulfilled"], int)
    by_pk = {row["wave"].pk: row for row in rows}
    assert by_pk[fulfillment_wave_planned_a.pk]["members"] == 1
    assert by_pk[fulfillment_wave_planned_a.pk]["fulfilled"] == 0


def test_fulfillment_board_unassigned_orders_matches_orm_count(
        client_a, tenant_a, customer_party_a, item_a, fulfillment_wave_planned_a,
        fulfillment_wave_released_a, fulfillment_member_a):
    from apps.scm.models import SalesOrder

    def _expected():
        return (SalesOrder.objects
                .filter(tenant=tenant_a, status__in=SalesOrder.ALLOCATABLE_STATUSES)
                .exclude(pk__in=FulfillmentWaveOrder.objects
                         .filter(tenant=tenant_a).values("sales_order_id"))
                .count())

    assert client_a.get(reverse("inventory:wave_board")).context[
        "stats"]["unassigned_orders"] == _expected()
    _fulfillment_open_so(customer_party_a, item_a)  # one more open, unwaved order
    assert client_a.get(reverse("inventory:wave_board")).context[
        "stats"]["unassigned_orders"] == _expected() == 1


def test_fulfillment_board_filters_status_location_q(
        client_a, tenant_a, fulfillment_wave_planned_a, fulfillment_wave_released_a,
        fulfillment_loc_wave_a):
    base = reverse("inventory:wave_board")

    status_hit = client_a.get(base + "?status=released")
    assert status_hit.status_code == 200
    assert [r["wave"].pk for r in status_hit.context["object_list"]] == [
        fulfillment_wave_released_a.pk]

    alt_warehouse = type(fulfillment_loc_wave_a).objects.create(
        tenant=tenant_a, code="FWH-A2", name="Second Acme warehouse",
        location_type="warehouse")
    FulfillmentWave.objects.create(
        tenant=tenant_a, description="North dock sweep", location=alt_warehouse,
        ship_method="economy")
    loc_hit = client_a.get(base + f"?location={alt_warehouse.pk}")
    assert loc_hit.status_code == 200
    rows = list(loc_hit.context["object_list"])
    assert len(rows) == 1
    assert rows[0]["wave"].location_id == alt_warehouse.pk
    junk_loc = client_a.get(base + "?location=abc")
    assert junk_loc.status_code == 200
    assert len(junk_loc.context["object_list"]) == 3  # unknown pk skips the filter

    # "sweep" would double-match ("Friday parcel sweep") — pin the search instead.
    q_hit = client_a.get(base + "?q=north dock")
    assert q_hit.status_code == 200
    assert [r["wave"].description for r in q_hit.context["object_list"]] == [
        "North dock sweep"]


# -- membership ----------------------------------------------------------------------------------

def test_fulfillment_membership_add_duplicate_remove_and_wrong_pair(
        client_a, fulfillment_wave_planned_a, fulfillment_member_a, fulfillment_so_second_a):
    wave = fulfillment_wave_planned_a
    add_url = reverse("inventory:waveorder_add", args=[wave.pk])

    added = client_a.post(add_url, {"sales_order": fulfillment_so_second_a.pk})
    assert added.status_code == 302
    assert FulfillmentWaveOrder.objects.filter(
        wave=wave, sales_order=fulfillment_so_second_a).exists()

    # C1 regression: the second identical POST flashes an error WITHOUT a 500.
    dup = client_a.post(add_url, {"sales_order": fulfillment_so_second_a.pk})
    assert dup.status_code == 302
    flashed = client_a.get(dup.url, follow=True)
    assert b"already in this wave" in flashed.content
    assert wave.orders.count() == 2

    member = FulfillmentWaveOrder.objects.get(wave=wave,
                                              sales_order=fulfillment_so_second_a)
    removed = client_a.post(reverse("inventory:waveorder_remove",
                                    args=[wave.pk, member.pk]))
    assert removed.status_code == 302
    assert not FulfillmentWaveOrder.objects.filter(pk=member.pk).exists()

    stranger = client_a.post(reverse("inventory:waveorder_remove",
                                     args=[wave.pk, member.pk]))  # already gone
    assert stranger.status_code == 302
    flashed_stranger = client_a.get(stranger.url, follow=True)
    assert b"not part of this wave" in flashed_stranger.content
    assert wave.orders.count() == 1  # the untouched member survived


# -- gating --------------------------------------------------------------------------------------

def test_fulfillment_gating_plain_member_read_only(
        member_client, tenant_a, fulfillment_wave_planned_a, fulfillment_member_a,
        fulfillment_loc_wave_a, fulfillment_carrier_a):
    detail_path = reverse("inventory:wave_detail", args=[fulfillment_wave_planned_a.pk])
    writes = [
        ("get", reverse("inventory:wave_create"), None),
        ("post", reverse("inventory:wave_create"),
         _fulfillment_wave_data(fulfillment_loc_wave_a, fulfillment_carrier_a)),
        ("post", reverse("inventory:wave_edit", args=[fulfillment_wave_planned_a.pk]), {}),
        ("post", reverse("inventory:wave_delete", args=[fulfillment_wave_planned_a.pk]), None),
        ("post", reverse("inventory:wave_release", args=[fulfillment_wave_planned_a.pk]), None),
        ("post", reverse("inventory:wave_close", args=[fulfillment_wave_planned_a.pk]), None),
        ("post", reverse("inventory:wave_cancel", args=[fulfillment_wave_planned_a.pk]), None),
        ("post", reverse("inventory:waveorder_add", args=[fulfillment_wave_planned_a.pk]),
         {"sales_order": ""}),
        ("post", reverse("inventory:waveorder_remove",
                         args=[fulfillment_wave_planned_a.pk, fulfillment_member_a.pk]), None),
    ]
    for method, url, data in writes:
        response = getattr(member_client, method)(url, data) if method == "post" \
            else member_client.get(url)
        assert response.status_code == 403, url
    assert not FulfillmentWave.objects.exclude(
        pk=fulfillment_wave_planned_a.pk).filter(tenant=tenant_a).exists()

    for url in (reverse("inventory:wave_list"), detail_path,
                reverse("inventory:wave_board")):
        hit = member_client.get(url)
        assert hit.status_code == 200, url
        assert hit.context["is_admin"] is False


# -- rendered hygiene ----------------------------------------------------------------------------

def test_fulfillment_pages_contain_no_template_comment_leaks(
        client_a, fulfillment_wave_planned_a, fulfillment_wave_released_a):
    pages = [
        reverse("inventory:wave_list"),
        reverse("inventory:wave_detail", args=[fulfillment_wave_planned_a.pk]),
        reverse("inventory:wave_board"),
    ]
    for url in pages:
        content = client_a.get(url).content
        assert b"{#" not in content, url
