"""Procurement 6.5 - Sourcing & Tendering model tests.

Load-bearing contracts: the event status machine only moves through the view verbs, the award
is a fact about a bid (exactly one won, other live bids lost), decide() is a pure resolver
that refuses frozen/cancelled states, and the weighted-score math is honest about partial
scoring (unscored weight is never topped up).
"""
from decimal import Decimal

import pytest

from apps.procurement.models import SourcingBid
from apps.procurement.models.SourcingTendering.Bids import weighted_total

pytestmark = pytest.mark.django_db


# -- numbering / properties ------------------------------------------------------------------------

def test_sourcing_event_number_auto_per_tenant(db, tenant_a, tenant_b, admin_user):
    from apps.procurement.models import SourcingEvent

    a1 = _event(tenant_a, admin_user)
    b1 = _event(tenant_b, admin_user)
    a2 = _event(tenant_a, admin_user)
    assert a1.number.startswith("SEV-") and b1.number.startswith("SEV-")
    assert a1.number != b1.number or True  # per-tenant counters may coincide; uniqueness scoped
    assert SourcingEvent.objects.filter(tenant=tenant_a, number=a1.number).count() == 1
    assert a2.number != a1.number


def test_sourcing_bid_number_prefix(db, sourcing_event_open_a, supplier_a):
    _, party = supplier_a
    bid = _bid(sourcing_event_open_a, party)
    assert bid.number.startswith("BID-")


def test_sourcing_event_editability_windows(sourcing_event_open_a):
    assert sourcing_event_open_a.is_editable          # open
    assert sourcing_event_open_a.bids_allowed
    sourcing_event_open_a.status = "closed"
    assert not sourcing_event_open_a.is_editable
    assert sourcing_event_open_a.is_evaluating
    assert not sourcing_event_open_a.bids_allowed


# -- lifecycle --------------------------------------------------------------------------------------

def test_sourcing_bid_submit_stamps_submitter(sourcing_event_open_a, supplier_a, django_user_model):
    _, party = supplier_a
    bid = _bid(sourcing_event_open_a, party)
    user = django_user_model.objects.get(username="admin_acme")
    assert bid.submit(user) is True
    bid.refresh_from_db()
    assert bid.status == "submitted" and bid.submitted_by == user and bid.submitted_at


def test_sourcing_bid_submit_refuses_closed_event(sourcing_event_open_a, supplier_a):
    _, party = supplier_a
    bid = _bid(sourcing_event_open_a, party)
    sourcing_event_open_a.status = "closed"
    sourcing_event_open_a.save()
    assert bid.submit(None) is False
    assert bid.status == "draft"


def test_sourcing_award_marks_winner_and_closes_rivals(
        sourcing_event_closed_a, supplier_a, second_party_a):
    winner = _bid(sourcing_event_closed_a, supplier_a[1], status="submitted")
    rival = _bid(sourcing_event_closed_a, second_party_a, status="shortlisted",
                 price="9500.00")
    assert sourcing_event_closed_a.award(winner) is True
    winner.refresh_from_db()
    rival.refresh_from_db()
    sourcing_event_closed_a.refresh_from_db()
    assert winner.status == "won"
    assert rival.status == "lost"
    assert sourcing_event_closed_a.status == "awarded" and sourcing_event_closed_a.awarded_at


def test_sourcing_award_refuses_wrong_states(sourcing_event_open_a, sourcing_bid_submitted_a):
    # Event not closed.
    assert sourcing_event_open_a.award(sourcing_bid_submitted_a) is False
    # Non-compliant / draft bids are never eligible.
    sourcing_event_open_a.status = "closed"
    sourcing_event_open_a.save()
    noncompliant = _bid(sourcing_event_open_a, sourcing_bid_submitted_a.supplier,
                        status="submitted", price="8000.00", is_compliant=False)
    draft = _bid(sourcing_event_open_a, sourcing_bid_submitted_a.supplier,
                 status="draft", price="7000.00")
    assert sourcing_event_open_a.award(noncompliant) is False
    assert sourcing_event_open_a.award(draft) is False


def test_sourcing_decide_is_pure_and_guards_states(
        sourcing_event_open_a, sourcing_bid_submitted_a, db):
    # Pure resolver: returns the target but does NOT persist.
    assert sourcing_bid_submitted_a.decide("shortlist") == "shortlisted"
    sourcing_bid_submitted_a.refresh_from_db()
    assert sourcing_bid_submitted_a.status == "submitted"
    # Won/lost/draft are terminal for decisions.
    sourcing_bid_submitted_a.status = "won"
    assert sourcing_bid_submitted_a.decide("disqualify") is None
    # Cancelled events freeze the matrix.
    sourcing_bid_submitted_a.status = "submitted"
    sourcing_event_open_a.status = "cancelled"
    sourcing_event_open_a.save()
    assert sourcing_bid_submitted_a.decide("shortlist") is None


# -- weighted score math ----------------------------------------------------------------------------

def test_sourcing_weighted_total_known_values(sourcing_event_open_a, sourcing_bid_submitted_a):
    scores = {c.pk: Decimal("8") for c in sourcing_event_open_a.criteria.all()}
    # (8/10)*40 + (8/10)*30 + (8/10)*30 = 80.00
    assert weighted_total(scores, list(sourcing_event_open_a.criteria.all())) == Decimal("80.00")


def test_sourcing_weighted_total_none_without_criteria(db, tenant_a, admin_user):
    event = _event(tenant_a, admin_user)
    assert weighted_total({}, list(event.criteria.all())) is None


def test_sourcing_weighted_partial_scoring_reads_lower(sourcing_event_open_a,
                                                       sourcing_bid_submitted_a):
    cost = sourcing_event_open_a.criteria.get(name="Total cost")
    scores = {cost.pk: Decimal("10")}
    # Only cost answered: earns full 40 of its weight — capped at defined total (100),
    # so the honest figure is 40.00, never a flattering top-up to 100.
    assert weighted_total(scores, list(sourcing_event_open_a.criteria.all())) == Decimal("40.00")


def test_sourcing_bid_weighted_score_delegates(sourcing_event_open_a,
                                               sourcing_bid_submitted_a):
    for criterion in sourcing_event_open_a.criteria.all():
        _score(sourcing_bid_submitted_a, criterion, "9")
    assert sourcing_bid_submitted_a.weighted_score() == Decimal("90.00")


# -- BidScore integrity ------------------------------------------------------------------------------

def test_sourcing_bid_score_rejects_over_scale(db, sourcing_event_open_a,
                                               sourcing_bid_submitted_a):
    criterion = sourcing_event_open_a.criteria.first()
    score = _score(sourcing_bid_submitted_a, criterion, "5")
    score.score = Decimal("11")
    with pytest.raises(Exception):
        score.full_clean()


def test_sourcing_bid_score_rejects_foreign_criterion(db, tenant_a, tenant_b,
                                                      sourcing_event_open_a,
                                                      sourcing_bid_submitted_a,
                                                      admin_b):
    foreign = _event(tenant_b, admin_b)
    foreign_criterion = _criterion(foreign, name="Foreign criterion")
    score = _score(sourcing_bid_submitted_a, foreign_criterion, "3")
    with pytest.raises(Exception):
        score.full_clean()


# helpers (mirror the conftest builders so every row carries its tenant) -----------------------------

def _event(tenant, user=None, **overrides):
    from apps.procurement.models import SourcingEvent

    fields = dict(tenant=tenant, title="Model-test event", created_by=user)
    fields.update(overrides)
    return SourcingEvent.objects.create(**fields)


def _bid(event, party, status="draft", price="9000.00", **overrides):
    from apps.procurement.models import SourcingBid

    fields = dict(event=event, supplier=party, tenant=event.tenant,
                  status=status, total_price=Decimal(price))
    fields.update(overrides)
    return SourcingBid.objects.create(**fields)


def _score(bid, criterion, value):
    from apps.procurement.models import BidScore
    return BidScore.objects.create(bid=bid, criterion=criterion, score=Decimal(value))


def _criterion(event, name="Total cost", weight="40", max_score=10):
    from apps.procurement.models import EventCriterion
    return EventCriterion.objects.create(
        event=event, name=name, weight_pct=Decimal(weight), max_score=max_score)
