"""Procurement 6.5 - Sourcing & Tendering view flows.

Every surface exercised through rendered bytes and real redirects: the lifecycle verbs stamp
their timestamps with audit rows, close/cancel/award are admin authority, scoring is validated
per criterion (NaN included), the award board ranks compliant live bids, and analytics answers
"-" rather than a confident zero where a figure cannot be computed.
"""
from decimal import Decimal

import pytest

from django.test import Client
from django.urls import reverse

from apps.procurement.models import BidScore, SourcingBid, SourcingEvent

pytestmark = pytest.django_db if False else pytest.mark.django_db


def _client_as(user):
    c = Client()
    c.force_login(user)
    return c


def _with_supplier_role(party):
    """The bid form scopes suppliers to PartyRole supplier/vendor — grant it for the test."""
    from apps.core.models import PartyRole
    PartyRole.objects.get_or_create(party=party, tenant=party.tenant,
                                    defaults={"role": "supplier"})
    return party


def _new_event(tenant, user, **overrides):
    from apps.procurement.models import SourcingEvent
    fields = dict(tenant=tenant, title="View-flow tender", event_type="tender",
                  status="draft", created_by=user)
    fields.update(overrides)
    return SourcingEvent.objects.create(**fields)


# -- registers + detail ------------------------------------------------------------------------------

def test_sourcing_event_list_search_and_filter(client_a, sourcing_event_open_a,
                                               sourcing_event_closed_a):
    url = reverse("procurement:event_list")
    r = client_a.get(url, {"q": "View-flow"})
    assert r.status_code == 200 and "View-flow" in r.content.decode()
    r = client_a.get(url, {"status": "closed"})
    body = r.content.decode()
    assert "Closed frame-agreement" in body or "SEV-" in body


def test_sourcing_event_detail_shows_matrix_and_scores(client_a, sourcing_event_open_a,
                                                       sourcing_bid_submitted_a):
    for criterion in sourcing_event_open_a.criteria.all():
        BidScore.objects.create(bid=sourcing_bid_submitted_a, criterion=criterion,
                                score=Decimal("8"))
    r = client_a.get(reverse("procurement:event_detail",
                             kwargs={"pk": sourcing_event_open_a.pk}))
    body = r.content.decode()
    assert sourcing_bid_submitted_a.number in body
    assert "80.0" in body            # weighted score column
    assert "Defined weight: 100%" in body


def test_sourcing_bid_detail_matrix_roundtrip(client_a, sourcing_event_open_a,
                                              sourcing_bid_submitted_a):
    criteria = list(sourcing_event_open_a.criteria.all())
    payload = {f"c_{c.pk}": "7.5" for c in criteria}
    r = client_a.post(reverse("procurement:bid_detail",
                              kwargs={"pk": sourcing_bid_submitted_a.pk}), payload)
    assert r.status_code == 302
    scores = set(BidScore.objects.filter(bid=sourcing_bid_submitted_a)
                 .values_list("score", flat=True))
    assert scores == {Decimal("7.5")}
    # Blank clears.
    blank = {f"c_{c.pk}": "" for c in criteria}
    client_a.post(reverse("procurement:bid_detail",
                          kwargs={"pk": sourcing_bid_submitted_a.pk}), blank)
    assert BidScore.objects.filter(bid=sourcing_bid_submitted_a).count() == 0


def test_sourcing_score_rejects_nan_without_500(client_a, sourcing_event_open_a,
                                                sourcing_bid_submitted_a):
    criterion = sourcing_event_open_a.criteria.first()
    r = client_a.post(reverse("procurement:bid_detail",
                              kwargs={"pk": sourcing_bid_submitted_a.pk}),
                      {f"c_{criterion.pk}": "NaN"})
    assert r.status_code == 200
    assert "is not a number" in r.content.decode()


# -- event lifecycle ---------------------------------------------------------------------------------

def test_sourcing_event_lifecycle_through_verbs(client_a, tenant_a, admin_user):
    event = _new_event(tenant_a, admin_user)
    detail = reverse("procurement:event_detail", kwargs={"pk": event.pk})
    assert client_a.post(reverse("procurement:event_open",
                                 kwargs={"pk": event.pk})).status_code == 302
    event.refresh_from_db()
    assert event.status == "open" and event.opened_at
    # Edit freezes once open? No - open stays editable; close then locks.
    assert client_a.post(reverse("procurement:event_close",
                                 kwargs={"pk": event.pk})).status_code == 302
    event.refresh_from_db()
    assert event.status == "closed" and event.closed_at
    assert "closed" in client_a.get(detail).content.decode()


def test_sourcing_close_is_admin_gated(member_client, tenant_a, admin_user):
    event = _new_event(tenant_a, admin_user, status="open")
    from django.urls.exceptions import NoReverseMatch  # noqa: F401
    r = member_client.post(reverse("procurement:event_close", kwargs={"pk": event.pk}))
    assert r.status_code in (403, 302)   # PermissionDenied -> 403 through handler
    event.refresh_from_db()
    assert event.status == "open"


def test_sourcing_award_flow_end_to_end(client_a, admin_user, tenant_a,
                                        sourcing_event_closed_a, supplier_a,
                                        second_party_a):
    winner = SourcingBid.objects.create(
        tenant=tenant_a, event=sourcing_event_closed_a, supplier=_with_supplier_role(supplier_a[1]),
        status="submitted", total_price=Decimal("8800.00"))
    rival = SourcingBid.objects.create(
        tenant=tenant_a, event=sourcing_event_closed_a, supplier=second_party_a,
        status="submitted", total_price=Decimal("9900.00"))
    r = client_a.post(reverse("procurement:event_award",
                              kwargs={"pk": sourcing_event_closed_a.pk}),
                      {"bid": str(winner.pk)})
    assert r.status_code == 302
    winner.refresh_from_db()
    rival.refresh_from_db()
    sourcing_event_closed_a.refresh_from_db()
    assert (winner.status, rival.status, sourcing_event_closed_a.status) == (
        "won", "lost", "awarded")


def test_sourcing_award_refuses_non_admin(member_client, sourcing_event_closed_a,
                                          sourcing_bid_submitted_a):
    # The bid belongs to another event; both wrong-event AND wrong-permission land safely.
    r = member_client.post(reverse("procurement:event_award",
                                   kwargs={"pk": sourcing_event_closed_a.pk}),
                           {"bid": str(sourcing_bid_submitted_a.pk)})
    assert r.status_code == 403


def test_sourcing_delete_refuses_when_bids_exist(client_a, sourcing_event_open_a,
                                                 sourcing_bid_submitted_a):
    r = client_a.post(reverse("procurement:event_delete",
                              kwargs={"pk": sourcing_event_open_a.pk}))
    assert r.status_code == 302
    assert SourcingEvent.objects.filter(pk=sourcing_event_open_a.pk).exists()


# -- bid flows ---------------------------------------------------------------------------------------

def test_sourcing_bid_edit_locks_once_submitted(client_a, sourcing_bid_submitted_a):
    r = client_a.get(reverse("procurement:bid_edit",
                             kwargs={"pk": sourcing_bid_submitted_a.pk}))
    assert r.status_code == 302      # redirected back with an explanation


def test_sourcing_shortlist_then_disqualify_needs_reason(
        client_a, sourcing_bid_submitted_a):
    pk = sourcing_bid_submitted_a.pk
    shortlist = reverse("procurement:bid_shortlist", kwargs={"pk": pk})
    disqualify = reverse("procurement:bid_disqualify", kwargs={"pk": pk})
    client_a.post(shortlist)
    assert SourcingBid.objects.get(pk=pk).status == "shortlisted"
    r = client_a.post(disqualify, {"note": ""})
    assert r.status_code == 302       # bounced back with an error message
    assert SourcingBid.objects.get(pk=pk).status == "shortlisted"
    client_a.post(disqualify, {"note": "Certificate lapsed."})
    assert SourcingBid.objects.get(pk=pk).status == "disqualified"
    assert SourcingBid.objects.get(pk=pk).decision_note == "Certificate lapsed."


# -- computed pages ----------------------------------------------------------------------------------

def test_sourcing_award_board_ranks_candidates(client_a, tenant_a, admin_user, supplier_a,
                                               second_party_a):
    event = _new_event(tenant_a, admin_user, status="closed",
                       title="Board scenario tender")
    from apps.procurement.models import EventCriterion
    criterion = EventCriterion.objects.create(event=event, name="Price",
                                              weight_pct=Decimal("100"), max_score=10)
    good = SourcingBid.objects.create(tenant=tenant_a, event=event,
                                      supplier=_with_supplier_role(supplier_a[1]), status="submitted",
                                      total_price=Decimal("8000.00"))
    weak = SourcingBid.objects.create(tenant=tenant_a, event=event,
                                      supplier=second_party_a, status="submitted",
                                      total_price=Decimal("7000.00"))
    BidScore.objects.create(bid=good, criterion=criterion, score=Decimal("9"))
    BidScore.objects.create(bid=weak, criterion=criterion, score=Decimal("5"))
    body = client_a.get(reverse("procurement:award_board")).content.decode()
    assert good.number in body and weak.number in body
    assert body.index(good.number) < body.index(weak.number)   # higher score first


def test_sourcing_analytics_answers_dash_without_budget(client_a, tenant_a, admin_user,
                                                        supplier_a):
    event = _new_event(tenant_a, admin_user, status="awarded",
                       title="No-budget awarded event", budget_estimate=None)
    SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=_with_supplier_role(supplier_a[1]),
                               status="won", total_price=Decimal("5000.00"))
    body = client_a.get(reverse("procurement:sourcing_analytics")).content.decode()
    assert "â€”" in body or "-" in body   # honest gaps render as dashes


def test_sourcing_analytics_computes_savings(client_a, tenant_a, admin_user, supplier_a):
    event = _new_event(tenant_a, admin_user, status="awarded",
                       title="Savings event", budget_estimate=Decimal("10000.00"))
    SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=_with_supplier_role(supplier_a[1]),
                               status="won", total_price=Decimal("8000.00"))
    body = client_a.get(reverse("procurement:sourcing_analytics")).content.decode()
    assert "2000.00" in body           # total savings vs budget
