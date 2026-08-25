"""Procurement 6.7 - E-Auction Management model tests.

Load-bearing contracts (post-fix state): the auction type is REVERSE-ONLY (no "forward"
choice until its engine exists), LIVE is derived (scheduled AND inside the window) rather
than stored, the anti-snipe extension has exactly one writer via extend_if_needed(), award()
is leader-only with a once-guard on awarded_supplier_id, and every ranking/pace rule is
computed from the append-only bid log — nothing scored, ranked or weighted is ever stored.
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import Party, PartyRole
from apps.procurement.models import EaucBid, EaucInvite, Eauction

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ local helpers

def _party(tenant, name):
    """A supplier party: core.Party + its PartyRole('supplier')."""
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="supplier")
    return party


def _auction(tenant, **overrides):
    """An Eauction with a sane FUTURE window by default (opens 5m ago, closes in 10m)."""
    now = timezone.now()
    fields = dict(
        tenant=tenant,
        title="Model-test e-auction",
        description="Reverse auction rules apply.",
        auction_type="reverse",
        start_price=Decimal("10000.00"),
        min_decrement=Decimal("100.00"),
        extension_trigger_seconds=60,
        extension_seconds=120,
        max_extensions=3,
        opens_at=now - timedelta(minutes=5),
        closes_at=now + timedelta(minutes=10),
        status="draft",
    )
    fields.update(overrides)
    return Eauction.objects.create(**fields)


def _invite(auction, party):
    return EaucInvite.objects.create(tenant=auction.tenant, auction=auction,
                                     supplier=party)


def _bid(auction, supplier, amount, **overrides):
    """Append-only log entry seeded directly (objects.create never runs full_clean)."""
    fields = dict(tenant=auction.tenant, auction=auction, supplier=supplier,
                  amount=Decimal(amount))
    fields.update(overrides)
    return EaucBid.objects.create(**fields)


# ------------------------------------------------------------------ numbering / uniqueness

def test_eauction_number_auto_prefix_per_tenant_and_unique_together(tenant_a, tenant_b):
    a1 = _auction(tenant_a)
    a2 = _auction(tenant_a)
    b1 = _auction(tenant_b)
    assert a1.number.startswith("EAUC-") and b1.number.startswith("EAUC-")
    assert a2.number != a1.number                      # sequence advances within the tenant
    assert Eauction.objects.filter(tenant=tenant_a, number=a1.number).count() == 1
    # unique_together ("tenant", "number"): a preset duplicate must be refused.
    with pytest.raises(Exception):
        _auction(tenant_a, number=a1.number)


def test_eaucbid_number_prefix_and_unique_together(tenant_a):
    auction = _auction(tenant_a)
    supplier = _party(tenant_a, "Bidder Numbering Co")
    invitee_bid = _bid(auction, supplier, "9000.00")
    assert invitee_bid.number.startswith("EBID-")
    with pytest.raises(Exception):
        _bid(auction, supplier, "8900.00", number=invitee_bid.number)


def test_eauction_reverse_only_type_choices():
    """Post-fix: no 'forward' choice until that engine exists; default stays reverse."""
    codes = [code for code, _label in Eauction.AUCTION_TYPES]
    assert codes == ["reverse"]
    assert "forward" not in codes
    assert Eauction._meta.get_field("auction_type").default == "reverse"


# ------------------------------------------------------------------ lifecycle guards

def test_eauction_publish_success_requires_invitee_and_future_close(tenant_a):
    # No invitees -> refused.
    lonely = _auction(tenant_a)
    assert lonely.publish() is False and lonely.status == "draft"
    # Invitee but already-stale window -> refused.
    stale = _auction(tenant_a, opens_at=timezone.now() - timedelta(hours=2),
                     closes_at=timezone.now() - timedelta(hours=1))
    _invite(stale, _party(tenant_a, "Stale Window Supplier"))
    assert stale.publish() is False and stale.status == "draft"
    # Invitee + future close -> scheduled.
    good = _auction(tenant_a)
    _invite(good, _party(tenant_a, "Ready Supplier"))
    assert good.publish() is True
    good.refresh_from_db()
    assert good.status == "scheduled"


def test_eauction_publish_refuses_non_draft(tenant_a):
    done = _auction(tenant_a, status="closed")
    _invite(done, _party(tenant_a, "Closed Auction Supplier"))
    assert done.publish() is False
    done.refresh_from_db()
    assert done.status == "closed"


def test_eauction_close_only_from_scheduled_incl_early_manual(tenant_a):
    draft = _auction(tenant_a)
    assert draft.close() is False and draft.status == "draft"      # not scheduled yet
    live = _auction(tenant_a, status="scheduled")
    assert live.close() is True                                    # manual EARLY close is legal
    live.refresh_from_db()
    assert live.status == "closed"
    assert live.close() is False                                   # closed is terminal for close()


def test_eauction_cancel_from_draft_and_scheduled_only(tenant_a):
    draft = _auction(tenant_a)
    assert draft.cancel() is True and draft.status == "cancelled"
    assert draft.cancel() is False                                 # cancelled is terminal
    scheduled = _auction(tenant_a, status="scheduled")
    assert scheduled.cancel() is True
    closed = _auction(tenant_a, status="closed")
    awarded = _auction(tenant_a, status="awarded")
    assert closed.cancel() is False and awarded.cancel() is False


# ------------------------------------------------------------------ accepts_bids window semantics

def test_eauction_accepts_bids_window_semantics(tenant_a):
    now = timezone.now()
    before = _auction(tenant_a, status="scheduled",
                      opens_at=now + timedelta(minutes=5),
                      closes_at=now + timedelta(minutes=30))
    assert before.accepts_bids is False                            # window not open yet
    inside = _auction(tenant_a, status="scheduled")                # default: inside window
    assert inside.accepts_bids is True
    after = _auction(tenant_a, status="scheduled",
                     opens_at=now - timedelta(minutes=30),
                     closes_at=now - timedelta(minutes=5))
    assert after.accepts_bids is False                             # window elapsed


def test_eauction_accepts_bids_wrong_status_false(tenant_a):
    """LIVE is derived: any non-scheduled status refuses bids even inside a live window."""
    auction = _auction(tenant_a)                                   # inside the window
    for wrong in ("draft", "closed", "awarded", "cancelled"):
        auction.status = wrong
        assert auction.accepts_bids is False, wrong
    auction.status = "scheduled"
    assert auction.accepts_bids is True


# ------------------------------------------------------------------ countdown / extension zone

def test_eauction_time_left_display_none_off_scheduled(tenant_a):
    draft = _auction(tenant_a, status="draft")                     # live window, wrong status
    closed = _auction(tenant_a, status="closed")
    assert draft.time_left_display is None
    assert closed.time_left_display is None
    assert draft.seconds_remaining is None and closed.seconds_remaining is None


def test_eauction_time_left_display_positive_and_negative_after_close(tenant_a):
    import re
    now = timezone.now()
    running = _auction(tenant_a, status="scheduled",
                       opens_at=now - timedelta(seconds=5),
                       closes_at=now + timedelta(seconds=65))
    assert re.fullmatch(r"1m \d{2}s", running.time_left_display)   # "4m 12s" shape
    elapsed = _auction(tenant_a, status="scheduled",
                       opens_at=now - timedelta(minutes=3),
                       closes_at=now - timedelta(seconds=95))
    display = elapsed.time_left_display
    assert display is not None and display.startswith("-")         # negative = window elapsed
    assert re.fullmatch(r"-1m \d{2}s", display)
    assert elapsed.in_extension_zone is False                      # negative remaining exits zone


def test_eauction_in_extension_zone_edges(tenant_a):
    now = timezone.now()
    inside = _auction(tenant_a, status="scheduled",
                      closes_at=now + timedelta(seconds=30))       # <= trigger (60s)
    outside = _auction(tenant_a, status="scheduled",
                       closes_at=now + timedelta(minutes=3))       # > trigger
    off_status = _auction(tenant_a, status="draft",
                          closes_at=now + timedelta(seconds=30))   # right zone, wrong status
    assert inside.in_extension_zone is True
    assert outside.in_extension_zone is False
    assert off_status.in_extension_zone is False                   # seconds_remaining None


# ------------------------------------------------------------------ extend_if_needed

def test_eauction_extend_pushes_close_and_counts(tenant_a):
    original = timezone.now() + timedelta(seconds=30)              # inside the 60s trigger zone
    auction = _auction(tenant_a, status="scheduled", closes_at=original,
                       extension_trigger_seconds=60, extension_seconds=120,
                       max_extensions=3)
    assert auction.extend_if_needed() == "extended"
    auction.refresh_from_db()
    assert auction.closes_at - original == timedelta(seconds=120)  # pushed by extension_seconds
    assert auction.extensions_used == 1


def test_eauction_extend_capped_at_max_extensions(tenant_a):
    auction = _auction(tenant_a, status="scheduled",
                       closes_at=timezone.now() + timedelta(seconds=20),
                       max_extensions=3)
    Eauction.objects.filter(pk=auction.pk).update(extensions_used=3)
    auction = Eauction.objects.get(pk=auction.pk)                  # reload the raw counter
    assert auction.extend_if_needed() == "capped"
    auction.refresh_from_db()
    assert auction.extensions_used == 3
    assert auction.status == "scheduled"


def test_eauction_extend_no_outside_zone(tenant_a):
    auction = _auction(tenant_a, status="scheduled",
                       closes_at=timezone.now() + timedelta(minutes=10))
    assert auction.extend_if_needed() == "no"
    auction.refresh_from_db()
    assert auction.extensions_used == 0


def test_eauction_extend_one_second_works(tenant_a):
    original = timezone.now() + timedelta(minutes=5)
    auction = _auction(tenant_a, status="scheduled", closes_at=original,
                       extension_trigger_seconds=600, extension_seconds=1)
    assert auction.extend_if_needed() == "extended"
    auction.refresh_from_db()
    assert auction.closes_at - original == timedelta(seconds=1)
    assert auction.extensions_used == 1


# ------------------------------------------------------------------ clean()

def test_eauction_clean_rejects_close_before_open(tenant_a):
    now = timezone.now()
    bad = _auction(tenant_a, opens_at=now, closes_at=now - timedelta(minutes=1))
    with pytest.raises(ValidationError) as excinfo:
        bad.full_clean()
    assert "closes_at" in excinfo.value.message_dict
    sane = _auction(tenant_a)
    sane.full_clean()                                              # valid window passes clean


# ------------------------------------------------------------------ award()

def test_eauction_award_stamps_leader_once(tenant_a):
    winner_party = _party(tenant_a, "Lowest Bid Works")
    rival = _party(tenant_a, "Higher Rival Co")
    auction = _auction(tenant_a, status="scheduled")
    _invite(auction, winner_party)
    _invite(auction, rival)
    _bid(auction, winner_party, "8500.00")
    _bid(auction, rival, "9100.00")
    assert auction.award(winner_party) is False                    # must close first
    auction.close()
    assert auction.best_bid().supplier_id == winner_party.pk
    assert auction.award(winner_party, note="Best landed offer") is True
    auction.refresh_from_db()
    assert auction.status == "awarded"
    assert auction.awarded_supplier_id == winner_party.pk
    assert auction.awarded_amount == Decimal("8500.00")
    assert auction.award_note == "Best landed offer"
    assert auction.awarded_at is not None
    # once-guard: second call is False even for the SAME supplier.
    assert auction.award(winner_party) is False
    fresh = Eauction.objects.get(pk=auction.pk)
    assert fresh.award(fresh.awarded_supplier) is False
    fresh.refresh_from_db()
    assert fresh.awarded_amount == Decimal("8500.00")              # decision never overwritten


def test_eauction_award_refuses_non_leader_and_wrong_status(tenant_a):
    leader = _party(tenant_a, "Current Leader Co")
    outsider = _party(tenant_a, "Not The Leader Co")
    auction = _auction(tenant_a, status="scheduled")
    _invite(auction, leader)
    _invite(auction, outsider)
    best = _bid(auction, leader, "8000.00")
    _bid(auction, outsider, "9500.00")
    auction.close()
    assert auction.award(outsider) is False                        # only the leader may win
    assert auction.refusal_leader.pk == best.pk                    # refusal explains itself
    auction.refresh_from_db()
    assert auction.status == "closed" and auction.awarded_supplier_id is None
    no_bids = _auction(tenant_a, status="closed")
    assert no_bids.award(leader) is False                          # nothing to award against
    no_bids.refresh_from_db()
    assert no_bids.status == "closed"


# ------------------------------------------------------------------ aggregates

def test_eauction_savings_vs_start_none_pre_bid(tenant_a):
    auction = _auction(tenant_a, status="scheduled")
    assert auction.savings_vs_start() is None                      # honest None pre-first-bid
    supplier = _party(tenant_a, "Savings Supplier")
    _invite(auction, supplier)
    _bid(auction, supplier, "8500.00")
    assert auction.savings_vs_start() == Decimal("1500.00")


def test_eauction_rankings_ordering_best_first_with_tiebreak(tenant_a):
    auction = _auction(tenant_a, status="scheduled")
    alpha = _party(tenant_a, "Alpha Co")
    beta = _party(tenant_a, "Beta Co")
    gamma = _party(tenant_a, "Gamma Co")
    delta = _party(tenant_a, "Delta Co")
    echo = _party(tenant_a, "Echo Co")
    base = timezone.make_aware(datetime(2026, 1, 10, 12, 0, 0))
    _bid(auction, delta, "7000.00", placed_at=base + timedelta(minutes=1))
    _bid(auction, echo, "7000.00", placed_at=base + timedelta(minutes=5))
    _bid(auction, alpha, "8000.00", placed_at=base + timedelta(minutes=2))
    _bid(auction, beta, "8700.00", placed_at=base + timedelta(minutes=3))
    _bid(auction, beta, "8500.00", placed_at=base + timedelta(minutes=4))
    _bid(auction, gamma, "9000.00", placed_at=base + timedelta(minutes=6))

    rows = auction.rankings()
    assert [r["supplier_name"] for r in rows] == \
        ["Delta Co", "Echo Co", "Alpha Co", "Beta Co", "Gamma Co"]
    by_name = {r["supplier_name"]: r for r in rows}
    assert by_name["Beta Co"]["best"] == Decimal("8500.00")        # per-supplier MIN amount
    assert by_name["Beta Co"]["count"] == 2
    assert by_name["Beta Co"]["last_at"] == base + timedelta(minutes=4)  # MAX placed_at
    assert by_name["Delta Co"]["best"] == by_name["Echo Co"]["best"]      # tie...
    assert rows[0]["supplier_id"] == delta.pk                              # ...earlier last_at wins
    # best_bid agrees with the head of the leaderboard.
    assert auction.best_bid().amount == Decimal("7000.00")


# ------------------------------------------------------------------ next_floor matrix

def test_eaucbid_next_floor_not_live_or_non_invitee_none(tenant_a):
    supplier = _party(tenant_a, "Floor Gate Supplier")
    draft = _auction(tenant_a, status="draft")                     # live window, draft status
    _invite(draft, supplier)
    assert EaucBid.next_floor(draft, supplier) is None             # not live -> None
    live = _auction(tenant_a, status="scheduled")
    stranger = _party(tenant_a, "Uninvited Stranger Co")
    assert EaucBid.next_floor(live, stranger) is None              # non-invitee -> None


def test_eaucbid_next_floor_first_bid_start_ceiling(tenant_a):
    supplier = _party(tenant_a, "First Bidder Co")
    auction = _auction(tenant_a, status="scheduled", start_price=Decimal("10000.00"))
    _invite(auction, supplier)
    assert EaucBid.next_floor(auction, supplier) == Decimal("10000.00")


def test_eaucbid_next_floor_rival_first_capped_below_best(tenant_a):
    leader = _party(tenant_a, "Standing Leader Co")
    rival = _party(tenant_a, "Rival Opener Co")
    auction = _auction(tenant_a, status="scheduled", start_price=Decimal("10000.00"))
    _invite(auction, leader)
    _invite(auction, rival)
    _bid(auction, leader, "9000.00")                               # global best exists
    # Rival's FIRST bid: start ceiling tightened to strictly beat the standing best.
    assert EaucBid.next_floor(auction, rival) == Decimal("8999.99")


def test_eaucbid_next_floor_own_pace_cap(tenant_a):
    supplier = _party(tenant_a, "Pace Setter Co")
    auction = _auction(tenant_a, status="scheduled", min_decrement=Decimal("100.00"))
    _invite(auction, supplier)
    _bid(auction, supplier, "9000.00")                             # they lead the field
    # Leading their own ladder: own_best - min_decrement, no field cap applies.
    assert EaucBid.next_floor(auction, supplier) == Decimal("8900.00")


def test_eaucbid_next_floor_rival_leads_min_of_pace_and_field(tenant_a):
    rival = _party(tenant_a, "Field Leader Co")
    chaser = _party(tenant_a, "Chaser Co")
    auction = _auction(tenant_a, status="scheduled", min_decrement=Decimal("100.00"),
                        start_price=Decimal("12000.00"))
    _invite(auction, rival)
    _invite(auction, chaser)
    _bid(auction, chaser, "9000.00")                               # chaser's own best
    _bid(auction, rival, "8500.00")                                # rival leads globally
    # pace cap = 9000-100 = 8900 ; field cap = 8500-0.01 = 8499.99 -> the tighter one.
    assert EaucBid.next_floor(auction, chaser) == Decimal("8499.99")


def test_eaucbid_next_floor_exhausted_ladder_returns_none(tenant_a):
    leader = _party(tenant_a, "Near Floor Leader Co")
    auction = _auction(tenant_a, status="scheduled", min_decrement=Decimal("100.00"))
    _invite(auction, leader)
    _bid(auction, leader, "0.50")                                  # own pace would go negative
    assert EaucBid.next_floor(auction, leader) is None             # floor <= 0 -> None
    zero_start = _auction(tenant_a, status="scheduled", start_price=Decimal("0.00"))
    opener = _party(tenant_a, "Zero Ceiling Opener Co")
    _invite(zero_start, opener)
    assert EaucBid.next_floor(zero_start, opener) is None          # first-bid ceiling <= 0 too


# ------------------------------------------------------------------ EaucBid.clean messages

def test_eaucbid_clean_messages_matrix(tenant_a):
    invited = _party(tenant_a, "Clean Matrix Invitee Co")
    stranger = _party(tenant_a, "Clean Matrix Stranger Co")
    draft = _auction(tenant_a, status="draft")
    _invite(draft, invited)

    def message_of(bid):
        with pytest.raises(ValidationError) as excinfo:
            bid.clean()
        return [str(m) for m in excinfo.value.messages]

    # Door 1: bidding simply not open (wrong status despite a live window).
    msgs = message_of(EaucBid(auction=draft, supplier=invited, amount=Decimal("9000.00")))
    assert any("Bidding is not open" in m for m in msgs)
    # Door 2: open but the supplier was never admitted.
    live = _auction(tenant_a, status="scheduled")
    msgs = message_of(EaucBid(auction=live, supplier=stranger, amount=Decimal("9000.00")))
    assert any("not admitted" in m for m in msgs)
    # Door 3: admitted but the amount does not clear the current floor.
    _invite(live, invited)
    _bid(live, invited, "9000.00")
    msgs = message_of(EaucBid(auction=live, supplier=invited, amount=Decimal("9999.00")))
    assert any("Bid too high" in m for m in msgs)
    # Door 4 (overloaded None): ladder exhausted below zero.
    exhausted = _auction(tenant_a, status="scheduled", min_decrement=Decimal("100.00"))
    _invite(exhausted, invited)
    _bid(exhausted, invited, "0.50")
    msgs = message_of(EaucBid(auction=exhausted, supplier=invited, amount=Decimal("0.01")))
    assert any("ladder is exhausted" in m for m in msgs)
    # A legal amount raises nothing at all.
    ok = EaucBid(auction=live, supplier=invited, amount=Decimal("8900.00"))
    ok.clean()                                                     # must not raise


# ------------------------------------------------------------------ nothing weighted is stored

def test_eauction_no_weighted_score_columns_stored():
    """Rankings/scores stay derived from the append-only log — no score-like columns drift."""
    banned = ("score", "rank", "weight", "weighted")
    for model in (Eauction, EaucBid):
        names = {f.name for f in model._meta.get_fields()}
        drifted = [n for n in names if any(b in n.lower() for b in banned)]
        assert drifted == [], f"{model.__name__} grew stored scoring columns: {drifted}"
