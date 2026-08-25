"""Procurement 6.7 - E-Auction Management view flows (register/setup CRUD, guarded lifecycle
verbs, invites, floor/rules/console/board, live bidding, results/award).

Every surface is exercised through rendered bytes, context keys and real redirects. The
load-bearing contracts: staff_required gates every console verb (plain members admitted,
tenantless logins refused) while the bid screen stays open, lifecycle verbs are POST-only and
guarded (draft-only edits/deletes, publish needs an invitee + future close, GET mutates
nothing), duplicate invites refuse gracefully, removal is blocked once a supplier has bid, the
bid engine enforces ceiling/pace/window server-side with an audit row per landed bid, the bid
screen never leaks the internal reserve, and the award records once, only for the current
leader, with the decision note truncated to 500 characters.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, Party, PartyRole, Tenant
from apps.procurement.models import EaucBid, EaucInvite, Eauction

pytestmark = pytest.mark.django_db


DT_FMT = "%Y-%m-%dT%H:%M"


# -- local factories ---------------------------------------------------------------------------------


def _supplier(tenant, name):
    """A core.Party organization carrying the supplier role the invite form scopes against."""
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.get_or_create(party=party, role="supplier",
                                    defaults={"tenant": tenant})
    return party


def _auction(tenant, *, status="draft", title="View-flow auction", start="10000.00",
             reserve=None, decrement="100.00", opens=None, closes=None):
    now = timezone.now()
    return Eauction.objects.create(
        tenant=tenant, title=title, auction_type="reverse",
        start_price=Decimal(start), reserve_price=Decimal(reserve) if reserve else None,
        min_decrement=Decimal(decrement),
        extension_trigger_seconds=60, extension_seconds=120, max_extensions=3,
        opens_at=opens if opens is not None else now - timedelta(minutes=5),
        closes_at=closes if closes is not None else now + timedelta(hours=1),
        status=status,
    )


def _live(tenant, **over):
    """A scheduled auction whose bidding window is open right now."""
    return _auction(tenant, status="scheduled", **over)


def _invite(auction, supplier):
    return EaucInvite.objects.create(tenant=auction.tenant, auction=auction, supplier=supplier)


def _bid(auction, supplier, amount, placed_by=None):
    return EaucBid.objects.create(tenant=auction.tenant, auction=auction, supplier=supplier,
                                  amount=Decimal(amount), placed_by=placed_by)


def _payload(**over):
    now = timezone.now()
    fields = {
        "title": "Form-built auction", "description": "", "auction_type": "reverse",
        "currency": "", "requisition": "",
        "start_price": "10000.00", "reserve_price": "", "min_decrement": "100.00",
        "extension_trigger_seconds": "60", "extension_seconds": "120", "max_extensions": "3",
        "opens_at": (now + timedelta(hours=1)).strftime(DT_FMT),
        "closes_at": (now + timedelta(days=1)).strftime(DT_FMT),
    }
    fields.update(over)
    return fields


def _flash(resp):
    return [str(m) for m in get_messages(resp.wsgi_request)]


def _client_as(user):
    c = Client()
    c.force_login(user)
    return c


# -- register: rendering, deep-link states, search/filters, tenancy ----------------------------------


def test_eauction_view_list_renders_all_rows(client_a, tenant_a):
    draft = _auction(tenant_a, title="Draft gearbox event")
    live = _live(tenant_a, title="Live bearings event")
    body = client_a.get(reverse("procurement:eauc_list")).content.decode()
    assert "E-Auction Management" in body
    assert draft.title in body and live.title in body
    assert draft.number in body and live.number in body


def test_eauction_view_list_state_live_shows_only_live_window(client_a, tenant_a):
    live = _live(tenant_a, title="Open now")
    upcoming = _auction(tenant_a, status="scheduled", title="Opens tomorrow",
                        opens=timezone.now() + timedelta(days=1),
                        closes=timezone.now() + timedelta(days=2))
    closed = _auction(tenant_a, status="closed", title="Already shut")
    draft = _auction(tenant_a, title="Still drafting")
    body = client_a.get(reverse("procurement:eauc_list"), {"state": "live"}).content.decode()
    assert live.title in body
    for other in (upcoming, closed, draft):
        assert other.title not in body


def test_eauction_view_list_state_closed_shows_closed_and_awarded(client_a, tenant_a):
    closed = _auction(tenant_a, status="closed", title="Shut yesterday")
    winner = _supplier(tenant_a, "Winner Ltd")
    awarded = _auction(tenant_a, status="awarded", title="Given away")
    awarded.awarded_supplier = winner
    awarded.save(update_fields=["awarded_supplier"])
    live = _live(tenant_a, title="Still trading")
    draft = _auction(tenant_a, title="Unpublished")
    body = client_a.get(reverse("procurement:eauc_list"), {"state": "closed"}).content.decode()
    assert closed.title in body and awarded.title in body
    assert live.title not in body and draft.title not in body


def test_eauction_view_list_search_status_type_filters(client_a, tenant_a):
    gearbox = _auction(tenant_a, title="Gearbox reverse sale")
    bearings = _live(tenant_a, title="Bearings reverse sale")
    url = reverse("procurement:eauc_list")
    body = client_a.get(url, {"q": "Gearbox"}).content.decode()
    assert gearbox.title in body and bearings.title not in body
    body = client_a.get(url, {"status": "draft"}).content.decode()
    assert gearbox.title in body and bearings.title not in body
    body = client_a.get(url, {"status": "scheduled"}).content.decode()
    assert bearings.title in body and gearbox.title not in body
    body = client_a.get(url, {"auction_type": "reverse"}).content.decode()
    assert gearbox.title in body and bearings.title in body
    body = client_a.get(url, {"auction_type": "forward"}).content.decode()
    assert "No auctions yet" in body


def test_eauction_view_register_excludes_other_tenants_rows(client_a, admin_user):
    other_tenant = Tenant.objects.create(name="Beaumont Corp", slug="beaumont")
    other_admin = User.objects.create_user(email="admin@beaumont.com", username="admin_bmt",
                                           password="TestPass123!", tenant=other_tenant,
                                           is_tenant_admin=True)
    theirs = _auction(other_tenant, title="Beaumont secret sale")
    own = _auction(admin_user.tenant, title="Acme public sale")
    body = client_a.get(reverse("procurement:eauc_list")).content.decode()
    assert own.title in body
    assert theirs.title not in body
    r = _client_as(other_admin).get(reverse("procurement:eauc_detail", args=[own.pk]))
    assert r.status_code == 404


def test_eauction_view_staff_gate_and_member_access(client_a, member_client, tenant_a):
    live = _live(tenant_a)
    floater = User.objects.create_user(email="float@nomail.dev", username="floater",
                                       password="TestPass123!")
    gated = _client_as(floater)
    r = gated.get(reverse("procurement:eauc_console", args=[live.pk]), follow=True)
    assert r.redirect_chain and "restricted to procurement staff" in " ".join(_flash(r))
    assert member_client.get(reverse("procurement:eauc_console", args=[live.pk])).status_code == 200


# -- setup CRUD --------------------------------------------------------------------------------------


def test_eauction_view_create_post_happy_path_stamps_creator(client_a, admin_user, tenant_a):
    r = client_a.post(reverse("procurement:eauc_create"), _payload())
    assert r.status_code == 302
    obj = Eauction.objects.get()
    assert obj.tenant == tenant_a and obj.status == "draft"
    assert obj.created_by == admin_user and obj.number.startswith("EAUC-")
    assert reverse("procurement:eauc_detail", args=[obj.pk]) in r.url
    assert "saved" in " ".join(_flash(r))
    assert AuditLog.objects.filter(action="create", object_id=obj.pk).exists()


def test_eauction_view_create_bad_window_rerenders_with_error(client_a, tenant_a):
    r = client_a.post(reverse("procurement:eauc_create"),
                      _payload(opens_at=(timezone.now() + timedelta(days=2)).strftime(DT_FMT),
                               closes_at=(timezone.now() + timedelta(hours=1)).strftime(DT_FMT)))
    assert r.status_code == 200
    assert "after the opening" in r.content.decode()
    assert Eauction.objects.count() == 0


def test_eauction_view_edit_guard_issued_redirects_draft_edits_fine(client_a, tenant_a):
    issued = _live(tenant_a, title="Locked once issued")
    r = client_a.get(reverse("procurement:eauc_edit", args=[issued.pk]), follow=True)
    assert r.redirect_chain and "only drafts can be edited" in " ".join(_flash(r))
    r = client_a.post(reverse("procurement:eauc_edit", args=[issued.pk]),
                      _payload(title="Hacked title"))
    issued.refresh_from_db()
    assert issued.title == "Locked once issued"
    draft = _auction(tenant_a, title="Editable draft")
    r = client_a.post(reverse("procurement:eauc_edit", args=[draft.pk]),
                      _payload(title="Renamed draft"))
    assert r.status_code == 302
    draft.refresh_from_db()
    assert draft.title == "Renamed draft"


def test_eauction_view_delete_draft_deleted_scheduled_refused(client_a, tenant_a):
    draft = _auction(tenant_a, title="Disposable")
    r = client_a.post(reverse("procurement:eauc_delete", args=[draft.pk]))
    assert r.status_code == 302 and not Eauction.objects.filter(pk=draft.pk).exists()
    issued = _live(tenant_a, title="Protected")
    r = client_a.post(reverse("procurement:eauc_delete", args=[issued.pk]), follow=True)
    assert "Only draft auctions can be deleted." in " ".join(_flash(r))
    assert Eauction.objects.filter(pk=issued.pk).exists()


# -- lifecycle verbs ---------------------------------------------------------------------------------


def test_eauction_view_publish_without_invites_stays_draft(client_a, tenant_a):
    obj = _auction(tenant_a, title="Nobody invited",
                   closes=timezone.now() + timedelta(days=1))
    r = client_a.post(reverse("procurement:eauc_publish", args=[obj.pk]), follow=True)
    obj.refresh_from_db()
    assert obj.status == "draft"
    assert "Publishing needs a future close time and at least one" in " ".join(_flash(r))


def test_eauction_view_publish_schedules_and_get_is_inert(client_a, tenant_a):
    obj = _auction(tenant_a, title="Publishable",
                   opens=timezone.now() + timedelta(hours=1),
                   closes=timezone.now() + timedelta(days=1))
    _invite(obj, _supplier(tenant_a, "Eager Supplier Co"))
    r = client_a.post(reverse("procurement:eauc_publish", args=[obj.pk]), follow=True)
    obj.refresh_from_db()
    assert obj.status == "scheduled"
    assert "scheduled" in " ".join(_flash(r))
    r = client_a.get(reverse("procurement:eauc_publish", args=[obj.pk]))
    assert r.status_code == 405
    obj.refresh_from_db()
    assert obj.status == "scheduled"


# -- invites -----------------------------------------------------------------------------------------


def test_eauction_view_invite_add_ok_duplicate_refused(client_a, tenant_a):
    obj = _auction(tenant_a)
    vendor = _supplier(tenant_a, "Northwind Industrial Supply")
    url = reverse("procurement:eauc_invite_add", args=[obj.pk])
    r = client_a.post(url, {"supplier": str(vendor.pk), "contact_note": "primary contact"},
                      follow=True)
    obj.refresh_from_db()
    assert obj.invites.count() == 1
    assert "Invited Northwind Industrial Supply" in " ".join(_flash(r))
    r = client_a.post(url, {"supplier": str(vendor.pk)}, follow=True)
    obj.refresh_from_db()
    assert obj.invites.count() == 1
    assert any("valid choice" in msg.lower() for msg in _flash(r))


def test_eauction_view_invite_remove_bids_guard(client_a, tenant_a):
    obj = _auction(tenant_a)
    quiet = _supplier(tenant_a, "Quiet Bidders Ltd")
    active = _supplier(tenant_a, "Active Bidders Ltd")
    kept = _invite(obj, quiet)
    sticky = _invite(obj, active)
    _bid(obj, active, "9500.00")
    r = client_a.post(reverse("procurement:eauc_invite_remove", args=[obj.pk, kept.pk]),
                      follow=True)
    assert "Invite removed." in " ".join(_flash(r))
    assert not EaucInvite.objects.filter(pk=kept.pk).exists()
    r = client_a.post(reverse("procurement:eauc_invite_remove", args=[obj.pk, sticky.pk]),
                      follow=True)
    assert "cannot be removed" in " ".join(_flash(r))
    assert EaucInvite.objects.filter(pk=sticky.pk).exists()


# -- console / board / floor / rules -------------------------------------------------------------------


def test_eauction_view_console_participants_and_board_fragment(client_a, tenant_a):
    obj = _live(tenant_a)
    bidder = _supplier(tenant_a, "Fast Clicks Ltd")
    waiting = _supplier(tenant_a, "Slow Starter Ltd")
    _invite(obj, bidder)
    _invite(obj, waiting)
    _bid(obj, bidder, "9000.00")
    r = client_a.get(reverse("procurement:eauc_console", args=[obj.pk]))
    assert r.status_code == 200
    assert len(r.context["participants"]) == 2
    assert "Awaiting first bid" in r.content.decode()
    r = client_a.get(reverse("procurement:eauc_board", args=[obj.pk]))
    assert r.status_code == 200
    assert r.context["obj"].pk == obj.pk
    assert r.context["ranked"][0]["supplier_name"] == "Fast Clicks Ltd"
    assert len(r.context["recent_bids"]) == 1


def test_eauction_view_floor_lists_only_live_with_page_obj(client_a, tenant_a):
    live = _live(tenant_a, title="Trading now")
    upcoming = _auction(tenant_a, status="scheduled", title="Not yet opened",
                        opens=timezone.now() + timedelta(days=1),
                        closes=timezone.now() + timedelta(days=2))
    draft = _auction(tenant_a, title="Never opened")
    r = client_a.get(reverse("procurement:eauc_floor"))
    assert r.status_code == 200
    assert list(r.context["page_obj"].object_list) == [live.pk]
    body = r.content.decode()
    assert live.number in body and live.title in body
    assert upcoming.number not in body and draft.number not in body


def test_eauction_view_rules_page_recent_usage(client_a, tenant_a):
    published = _live(tenant_a, title="Published usage row")
    draft = _auction(tenant_a, title="Draft never published")
    r = client_a.get(reverse("procurement:eauc_rules"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Extension usage" in body and published.number in body
    assert draft.number not in body


# -- live bidding --------------------------------------------------------------------------------------


def test_eauction_view_bid_screen_pick_supplier_and_legal_bid_lands(client_a, admin_user,
                                                                    tenant_a):
    obj = _live(tenant_a)
    vendor = _supplier(tenant_a, "First Mover Ltd")
    _invite(obj, vendor)
    r = client_a.get(reverse("procurement:eauc_bid", args=[obj.pk]),
                     {"supplier": str(vendor.pk)})
    assert r.status_code == 200
    body = r.content.decode()
    assert "Recording bids for" in body and vendor.name in body
    assert "Next legal amount" in body
    r = client_a.post(reverse("procurement:eauc_bid", args=[obj.pk]),
                      {"supplier": str(vendor.pk), "amount": "9000.00", "note": "opener"},
                      follow=True)
    assert r.status_code == 200
    bid = EaucBid.objects.get()
    assert bid.supplier == vendor and bid.amount == Decimal("9000.00")
    assert bid.placed_by == admin_user
    assert AuditLog.objects.filter(action="create", object_id=bid.pk).exists()
    assert "recorded" in " ".join(_flash(r))


def test_eauction_view_bid_over_ceiling_refused(client_a, tenant_a):
    obj = _live(tenant_a, start="5000.00")
    vendor = _supplier(tenant_a, "Greedy Bidder Ltd")
    _invite(obj, vendor)
    r = client_a.post(reverse("procurement:eauc_bid", args=[obj.pk]),
                      {"supplier": str(vendor.pk), "amount": "5500.00"}, follow=True)
    assert "Bid too high" in " ".join(_flash(r))
    assert EaucBid.objects.count() == 0


def test_eauction_view_bid_slow_pace_refused(client_a, tenant_a):
    obj = _live(tenant_a, decrement="100.00")
    vendor = _supplier(tenant_a, "Nudge Bidder Ltd")
    _invite(obj, vendor)
    _bid(obj, vendor, "9000.00")
    r = client_a.post(reverse("procurement:eauc_bid", args=[obj.pk]),
                      {"supplier": str(vendor.pk), "amount": "8950.00"}, follow=True)
    assert "Bid too high" in " ".join(_flash(r))
    assert EaucBid.objects.count() == 1


def test_eauction_view_bid_on_closed_refused(client_a, tenant_a):
    obj = _auction(tenant_a, status="closed")
    vendor = _supplier(tenant_a, "Late Arrival Ltd")
    _invite(obj, vendor)
    r = client_a.post(reverse("procurement:eauc_bid", args=[obj.pk]),
                      {"supplier": str(vendor.pk), "amount": "9000.00"}, follow=True)
    assert "No legal bid is available" in " ".join(_flash(r))
    assert EaucBid.objects.count() == 0


def test_eauction_view_bid_unknown_supplier_message_redirect(client_a, tenant_a):
    obj = _live(tenant_a)
    insider = _supplier(tenant_a, "Invited Insider Ltd")
    outsider = _supplier(tenant_a, "Uninvited Outsider Ltd")
    _invite(obj, insider)
    r = client_a.post(reverse("procurement:eauc_bid", args=[obj.pk]),
                      {"supplier": str(outsider.pk), "amount": "9000.00"}, follow=True)
    assert "Pick which invited supplier" in " ".join(_flash(r))
    assert EaucBid.objects.count() == 0


def test_eauction_view_bid_screen_never_leaks_reserve(client_a, tenant_a):
    obj = _live(tenant_a, reserve="7777.77")
    vendor = _supplier(tenant_a, "Blindfolded Bidder Ltd")
    _invite(obj, vendor)
    body = client_a.get(reverse("procurement:eauc_bid", args=[obj.pk]),
                        {"supplier": str(vendor.pk)}).content.decode()
    assert "7777.77" not in body
    assert "Reserve" not in body


# -- post-auction results / award -----------------------------------------------------------------------


def _closed_with_bids(tenant):
    obj = _auction(tenant, status="closed")
    alpha = _supplier(tenant, "Alpha Bidding Ltd")
    beta = _supplier(tenant, "Beta Bidding Ltd")
    _invite(obj, alpha)
    _invite(obj, beta)
    _bid(obj, alpha, "9000.00")
    _bid(obj, beta, "9200.00")
    _bid(obj, alpha, "8500.00")
    return obj, alpha, beta


def test_eauction_view_results_ranking_order_and_savings(client_a, tenant_a):
    obj, alpha, beta = _closed_with_bids(tenant_a)
    r = client_a.get(reverse("procurement:eauc_results", args=[obj.pk]))
    assert r.status_code == 200
    ranked = r.context["ranked"]
    assert ranked[0]["supplier_id"] == alpha.pk and ranked[1]["supplier_id"] == beta.pk
    assert r.context["savings"] == Decimal("1500.00")
    assert r.context["total_bids"] == 3
    body = r.content.decode()
    assert "Saving vs opening ceiling" in body
    assert body.index(alpha.name) < body.index(beta.name)


def test_eauction_view_award_flow_leader_once_note_truncated(client_a, tenant_a):
    obj, alpha, beta = _closed_with_bids(tenant_a)
    url = reverse("procurement:eauc_award", args=[obj.pk])
    r = client_a.post(url, {"supplier": str(beta.pk), "award_note": "wrong horse"},
                      follow=True)
    obj.refresh_from_db()
    assert obj.status == "closed" and obj.awarded_supplier is None
    assert "Award refused" in " ".join(_flash(r))
    r = client_a.post(url, {"supplier": str(alpha.pk), "award_note": "x" * 600},
                      follow=True)
    obj.refresh_from_db()
    assert obj.status == "awarded"
    assert obj.awarded_supplier == alpha and obj.awarded_amount == Decimal("8500.00")
    assert len(obj.award_note) == 500
    assert "awarded to Alpha Bidding Ltd" in " ".join(_flash(r))
    assert AuditLog.objects.filter(action="award", object_id=obj.pk).exists()
    r = client_a.post(url, {"supplier": str(alpha.pk)}, follow=True)
    obj.refresh_from_db()
    assert obj.status == "awarded" and obj.awarded_supplier == alpha
    assert "Award refused" in " ".join(_flash(r))
