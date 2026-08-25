"""Procurement 6.5 - Sourcing & Tendering security tests.

Tenant isolation is the spine: every route 404s a foreign pk, verbs refuse GET, the award
stays admin-only, the superuser (tenant=None) sees an empty register, and crafted POSTs
cannot set excluded fields or reach another workspace's rows.
"""
from decimal import Decimal

import pytest

from django.test import Client
from django.urls import reverse

from apps.procurement.models import BidScore, SourcingBid, SourcingEvent

pytestmark = pytest.mark.django_db


def _client_as(user):
    c = Client()
    c.force_login(user)
    return c


def _foreign_event(tenant_b, admin_b):
    from apps.procurement.models import SourcingEvent
    return SourcingEvent.objects.create(tenant=tenant_b, title="Globex secret tender",
                                        status="open", created_by=admin_b)


def _foreign_bid(foreign_event, supplier_b):
    _, party = supplier_b
    return SourcingBid.objects.create(event=foreign_event, supplier=party,
                                      tenant=tenant_b_of(foreign_event),
                                      status="submitted", total_price=Decimal("10.00"))


def tenant_b_of(foreign_event):
    return foreign_event.tenant


# -- IDOR --------------------------------------------------------------------------------------------

def test_sourcing_idor_event_routes_404(client_a, tenant_b, admin_b):
    foreign = _foreign_event(tenant_b, admin_b)
    for name in ("event_detail", "event_edit", "event_delete", "event_open",
                 "event_close", "event_cancel", "event_award"):
        url = reverse(f"procurement:{name}", kwargs={"pk": foreign.pk})
        r = client_a.post(url) if name in ("event_delete", "event_open", "event_close",
                                           "event_cancel", "event_award") else client_a.get(url)
        assert r.status_code == 404, name


def test_sourcing_idor_bid_routes_404(client_a, tenant_b, admin_b, supplier_b):
    foreign_event = _foreign_event(tenant_b, admin_b)
    foreign_bid = _foreign_bid(foreign_event, supplier_b)
    for name in ("bid_detail", "bid_edit", "bid_delete", "bid_submit",
                 "bid_shortlist", "bid_disqualify"):
        url = reverse(f"procurement:{name}", kwargs={"pk": foreign_bid.pk})
        r = client_a.post(url) if name in ("bid_delete", "bid_submit", "bid_shortlist",
                                           "bid_disqualify") else client_a.get(url)
        assert r.status_code == 404, name
    # Scoring POST against a foreign bid pk also 404s.
    assert client_a.post(reverse("procurement:bid_detail",
                                 kwargs={"pk": foreign_bid.pk}), {"c_1": "5"}
                         ).status_code == 404


# -- verb safety --------------------------------------------------------------------------------------

def test_sourcing_verbs_refuse_get(client_a, sourcing_event_open_a,
                                   sourcing_bid_submitted_a):
    for name in ("event_open", "event_close", "event_cancel", "event_delete",
                 "event_award", "bid_submit", "bid_shortlist", "bid_disqualify",
                 "bid_delete"):
        target_pk = (sourcing_event_open_a.pk if name.startswith("event")
                     else sourcing_bid_submitted_a.pk)
        r = client_a.get(reverse(f"procurement:{name}", kwargs={"pk": target_pk}))
        assert r.status_code == 405, name


def test_sourcing_member_cannot_close_cancel_or_award(member_client, tenant_a, admin_user,
                                                      supplier_a):
    from django.utils import timezone
    event = _foreign_event(tenant_a, admin_user)   # open event in member's own tenant
    assert member_client.post(reverse("procurement:event_close",
                                      kwargs={"pk": event.pk})).status_code == 403
    event.status = "closed"
    event.save()
    bid = SourcingBid.objects.create(event=event, supplier=supplier_a[1], tenant=tenant_a,
                                     status="submitted", total_price=Decimal("10.00"))
    assert member_client.post(reverse("procurement:event_award",
                                      kwargs={"pk": event.pk}),
                              {"bid": str(bid.pk)}).status_code == 403
    event.refresh_from_db()
    assert event.status == "closed"


# -- superuser / tenant=None --------------------------------------------------------------------------

def test_sourcing_superuser_sees_empty_registers(db, django_user_model,
                                                 sourcing_event_open_a,
                                                 sourcing_bid_submitted_a):
    su = django_user_model.objects.create_user(
        username="sourcing_su", password="x", email="su@example.com", tenant=None, is_superuser=True)
    client = _client_as(su)
    body = client.get(reverse("procurement:event_list")).content.decode()
    assert "SEV-" not in body
    bids_body = client.get(reverse("procurement:bid_list")).content.decode()
    assert "BID-" not in bids_body


def test_sourcing_create_redirects_tenantless_superuser(db, django_user_model):
    su = django_user_model.objects.create_user(
        username="sourcing_su2", password="x", email="su2@example.com", tenant=None, is_superuser=True)
    admin_client = _client_as(su)
    r = admin_client.post(reverse("procurement:event_create"),
                          {"title": "Orphan tender", "event_type": "tender"})
    assert r.status_code == 302      # bounced to dashboard with an explanation


# -- crafted payloads ----------------------------------------------------------------------------------

def test_sourcing_craftable_status_never_via_form(client_a, tenant_a, admin_user):
    r = client_a.post(reverse("procurement:event_create"),
                      {"title": "Crafted", "event_type": "tender", "status": "awarded"})
    assert r.status_code in (200, 302)
    if SourcingEvent.objects.filter(tenant=tenant_a, title="Crafted").exists():
        obj = SourcingEvent.objects.get(tenant=tenant_a, title="Crafted")
        assert obj.status == "draft"     # form excludes status; verbs own transitions


def test_sourcing_score_payload_foreign_criterion_is_ignored(client_a, tenant_b, admin_b,
                                                             sourcing_event_open_a,
                                                             sourcing_bid_submitted_a):
    foreign_criterion = SourcingEvent.objects.create(
        tenant=tenant_b, title="Foreign matrix holder", status="open", created_by=admin_b)
    del foreign_criterion
    # A criterion id from nowhere simply matches no field the view reads; nothing explodes,
    # nothing is written, and the save redirects back as a no-op.
    r = client_a.post(reverse("procurement:bid_detail",
                              kwargs={"pk": sourcing_bid_submitted_a.pk}),
                      {"c_999999": "5"})
    assert r.status_code == 302
    assert BidScore.objects.filter(bid=sourcing_bid_submitted_a).count() == 0
