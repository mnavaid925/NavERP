"""Inventory 5.7 Stock Movement & Transfers - model invariants.

``TransferRoute`` / ``TransferApprovalRule`` are policy catalogs over SCM 4.3's
``StockTransfer`` spine; ``TransferApproval`` is the append-only decision chain.
These tests exercise the rules as committed behaviour: most-specific-wins resolution,
half-open unit bands, the replay-after-rejection semantics, and every cross-tenant
guard on the models themselves.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    SCOPE_ALL,
    SCOPE_INTER,
    SCOPE_INTRA,
    TransferApproval,
    TransferApprovalRule,
    TransferRoute,
)
from apps.scm.models import Location, StockTransfer

pytestmark = pytest.mark.django_db


def make_location(tenant, code, parent=None):
    return Location.objects.create(tenant=tenant, code=code, name=code, parent=parent)


def make_transfer(tenant, source, destination):
    from django.utils import timezone

    return StockTransfer.objects.create(
        tenant=tenant, from_location=source, to_location=destination,
        transfer_date=timezone.now().date())


# ------------------------------------------------------------------ TransferRoute


class TestTransferRouteModel:
    def test_str_is_the_name(self, tenant_a):
        assert str(TransferRoute.objects.create(tenant=tenant_a, name="Direct Run")) == "Direct Run"

    def test_covers_matches_set_endpoints_exactly(self, tenant_a):
        a = make_location(tenant_a, "WH-A")
        b = make_location(tenant_a, "WH-B")
        route = TransferRoute.objects.create(
            tenant=tenant_a, name="Lane", origin_location=a, destination_location=b)
        assert route.covers(a.pk, b.pk)
        assert not route.covers(b.pk, a.pk)
        assert not route.covers(a.pk, make_location(tenant_a, "WH-C").pk)

    def test_open_ends_match_anything(self, tenant_a):
        a = make_location(tenant_a, "WH-A")
        b = make_location(tenant_a, "WH-B")
        route = TransferRoute.objects.create(tenant=tenant_a, name="Any")
        assert route.covers(a.pk, b.pk)
        pinned = TransferRoute.objects.create(
            tenant=tenant_a, name="From A", origin_location=a)
        assert pinned.covers(a.pk, b.pk)
        assert not pinned.covers(b.pk, a.pk)

    def test_covers_same_endpoint_pair(self, tenant_a):
        """A degenerate X→X leg: a lane refuses even when its own pinned endpoint is
        the one repeated; an all-open service route still covers it (clean() forbids
        only a route whose OWN endpoints coincide — a transfer never has from == to)."""
        a = make_location(tenant_a, "WH-A")
        b = make_location(tenant_a, "WH-B")
        lane = TransferRoute.objects.create(
            tenant=tenant_a, name="Lane", origin_location=a, destination_location=b)
        assert not lane.covers(a.pk, a.pk)
        assert not lane.covers(b.pk, b.pk)
        open_route = TransferRoute.objects.create(tenant=tenant_a, name="Any")
        assert open_route.covers(a.pk, a.pk)

    def test_clean_rejects_foreign_tenant_locations(self, tenant_b):
        from apps.core.models import Tenant
        other = Tenant.objects.create(name="Other", slug="other")
        loc = make_location(other, "FOREIGN")
        route = TransferRoute(tenant=tenant_b, name="Bad", origin_location=loc)
        with pytest.raises(ValidationError):
            route.clean()

    def test_clean_rejects_same_start_and_end(self, tenant_a):
        a = make_location(tenant_a, "WH-A")
        route = TransferRoute(tenant=tenant_a, name="Loop", origin_location=a,
                              destination_location=a)
        with pytest.raises(ValidationError) as exc:
            route.clean()
        assert "different locations" in str(exc.value)


# ------------------------------------------------------------------ TransferApprovalRule


class TestTransferApprovalRuleResolution:
    def test_none_when_nothing_matches(self, tenant_a):
        TransferApprovalRule.objects.create(
            tenant=tenant_a, name="Big only", min_units=100, tier_count=2)
        assert TransferApprovalRule.resolve(tenant_a, 10, SCOPE_INTER) is None

    def test_scope_specific_beats_all(self, tenant_a):
        TransferApprovalRule.objects.create(
            tenant=tenant_a, name="All moves", applies_to=SCOPE_ALL, min_units=0)
        specific = TransferApprovalRule.objects.create(
            tenant=tenant_a, name="Inter only", applies_to=SCOPE_INTER, min_units=0)
        resolved = TransferApprovalRule.resolve(tenant_a, 5, SCOPE_INTER)
        assert resolved == specific

    def test_narrowest_band_wins(self, tenant_a):
        wide = TransferApprovalRule.objects.create(
            tenant=tenant_a, name="0+", min_units=0)
        narrow = TransferApprovalRule.objects.create(
            tenant=tenant_a, name="50-100", min_units=50, max_units=100)
        assert TransferApprovalRule.resolve(tenant_a, 60, SCOPE_ALL) == narrow
        assert TransferApprovalRule.resolve(tenant_a, 200, SCOPE_ALL) == wide

    def test_equal_width_rules_break_ties_by_name_ordering(self, tenant_a):
        """Two EQUALLY-wide matching bands: min() keeps the first candidate, so the
        tie-break IS the model ordering (-min_units, name) — pin it as deterministic."""
        TransferApprovalRule.objects.create(
            tenant=tenant_a, name="Zebra band", min_units=0, max_units=100)
        alpha = TransferApprovalRule.objects.create(
            tenant=tenant_a, name="Alpha band", min_units=0, max_units=100)
        assert TransferApprovalRule.resolve(tenant_a, 60, SCOPE_ALL) == alpha

    def test_band_upper_bound_is_exclusive(self, tenant_a):
        rule = TransferApprovalRule.objects.create(
            tenant=tenant_a, name="Under 50", min_units=0, max_units=50)
        assert TransferApprovalRule.resolve(tenant_a, 49, SCOPE_ALL) == rule
        assert TransferApprovalRule.resolve(tenant_a, 50, SCOPE_ALL) is None

    def test_inactive_rules_never_match(self, tenant_a):
        TransferApprovalRule.objects.create(
            tenant=tenant_a, name="Sleeping", min_units=0, is_active=False)
        assert TransferApprovalRule.resolve(tenant_a, 1, SCOPE_ALL) is None

    def test_clean_rejects_inverted_band(self, tenant_a):
        rule = TransferApprovalRule(tenant=tenant_a, name="Inverted",
                                    min_units=50, max_units=10)
        with pytest.raises(ValidationError):
            rule.clean()


# ------------------------------------------------------------------ TransferApproval chain


@pytest.fixture
def chain_transfer(db, tenant_a):
    src = make_location(tenant_a, "SRC")
    dst = make_location(tenant_a, "DST")
    return make_transfer(tenant_a, src, dst)


class TestTransferApprovalChain:
    def test_number_prefix_and_str(self, tenant_a, chain_transfer):
        row = TransferApproval.objects.create(
            tenant=tenant_a, transfer=chain_transfer, tier=1, decision="approved")
        assert row.number.startswith("TA-")
        assert f"tier {row.tier}" in str(row)

    def test_rejection_resets_the_replay(self, tenant_a, chain_transfer):
        """History survives; progress honestly restarts after a rejection."""
        TransferApproval.objects.create(
            tenant=tenant_a, transfer=chain_transfer, tier=1, decision="approved")
        TransferApproval.objects.create(
            tenant=tenant_a, transfer=chain_transfer, tier=2, decision="rejected")
        decisions = list(TransferApproval.objects.filter(transfer=chain_transfer))
        assert TransferApproval.cleared_tier_count(decisions) == 0
        TransferApproval.objects.create(
            tenant=tenant_a, transfer=chain_transfer, tier=1, decision="approved")
        # Replay CHRONOLOGICALLY like every production caller does (_chain_map/_decide
        # order by decided_at, id) — the model's Meta.ordering is by tier, which would
        # interleave two resubmission runs and read the stale rejection last.
        decisions = list(TransferApproval.objects
                         .filter(transfer=chain_transfer)
                         .order_by("decided_at", "id"))
        assert TransferApproval.cleared_tier_count(decisions) == 1

    def test_plain_strings_replay_too(self):
        assert TransferApproval.cleared_tier_count(["approved", "approved"]) == 2
        assert TransferApproval.cleared_tier_count(["approved", "rejected", "approved"]) == 1
