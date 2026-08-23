"""Inventory 5.4 — model invariants for PutawayRule + the directed-putaway resolver.

The sub-module is ONE configuration table and ONE pure function, so this suite pins both
halves: the rule's per-field cross-tenant clean() and its legal-overlap Meta, and every
honesty property of :func:`resolve_putaway_suggestion` — frozen tier order (item >
category > catch-all > consolidation > condition > walk-order), the shared disqualifier
bar (inactive / full / foreign-owned / staging-itself), reason strings that cite codes
only, refusals that start "No Suggestion Found" rather than guessing, and the batch-kwargs
preload path answering exactly what the bare self-loading call answers.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import PutawayRule, resolve_putaway_suggestion
from apps.inventory.models.ReceivingPutaway.PutawayRules import (
    TIER_ANY,
    TIER_CATEGORY,
    TIER_ITEM,
)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _receiving_location(tenant, code, *, parent=None, location_type="bin", capacity=None,
                        pick_sequence=None, is_active=True, is_pickable=True,
                        storage_condition="", owner_client=None):
    """A stock location on the SCM spine; defaults describe an ordinary open bin."""
    from apps.scm.models import Location
    return Location.objects.create(
        tenant=tenant, code=code, name=f"Area {code}", location_type=location_type,
        parent=parent, capacity=capacity, pick_sequence=pick_sequence,
        is_active=is_active, is_pickable=is_pickable,
        storage_condition=storage_condition, owner_client=owner_client)


def _receiving_item(tenant, sku, *, category=None, storage_condition="", owner_client=None):
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant, sku=sku, name=f"Item {sku}", standard_cost=Decimal("1.00"),
        category=category, storage_condition=storage_condition, owner_client=owner_client)


def _receiving_category(tenant, name):
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant, name=name)


def _receiving_move(tenant, item, location, quantity):
    """One inbound ledger row — the ONLY way on-hand exists (append-only StockMove)."""
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, quantity=Decimal(quantity),
        move_type="receipt", unit_cost=Decimal("1.00"), moved_at=timezone.now())


def _receiving_task(tenant, item, from_location, to_location, quantity="1"):
    """An OPEN scm.PutawayTask built straight through the ORM."""
    from apps.scm.models import PutawayTask
    return PutawayTask.objects.create(
        tenant=tenant, item=item, from_location=from_location,
        to_location=to_location, quantity=Decimal(quantity), status="pending")


def _receiving_client(tenant, code):
    """A 3PL client: identity Party + the LogisticsClient commercial row."""
    from apps.core.models import Party
    from apps.scm.models import LogisticsClient
    party = Party.objects.create(tenant=tenant, name=f"Client {code}", kind="organization")
    return LogisticsClient.objects.create(tenant=tenant, party=party, code=code)


def _receiving_view(result):
    """Normalise a resolver answer into pk/reason pairs so equality asserts read cleanly."""
    suggestion, reason, candidates = result
    return (suggestion.pk if suggestion is not None else None, reason,
            [(loc.pk, why) for loc, why in candidates])


def _receiving_locs(candidates):
    return [loc for loc, _why in candidates]


# ------------------------------------------------------------------ model basics


class TestReceivingPutawayRuleModel:
    def test_receiving_str_item_scope_uses_sku(self, receiving_rule_a):
        assert str(receiving_rule_a) == "CAT-1 → RA-01"

    def test_receiving_str_category_scope_uses_category_name(self, tenant_a, receiving_loc_bin_a):
        cat = _receiving_category(tenant_a, "Electronics")
        rule = PutawayRule.objects.create(
            tenant=tenant_a, category=cat, destination=receiving_loc_bin_a)
        assert str(rule) == "Electronics → RA-01"

    def test_receiving_str_catchall_scope_and_unsaved_placeholder(self, tenant_a, receiving_loc_bin_a):
        catchall = PutawayRule(tenant=tenant_a, destination=receiving_loc_bin_a)
        assert str(catchall) == "Any item → RA-01"
        # An unsaved row with no destination yet must not blow up either.
        assert str(PutawayRule(tenant=tenant_a)) == "Any item → ?"

    def test_receiving_ordering_is_priority_then_id(self, tenant_a, item_a, receiving_loc_bin_a):
        first = PutawayRule.objects.create(
            tenant=tenant_a, item=item_a, destination=receiving_loc_bin_a, priority=50)
        low = PutawayRule.objects.create(
            tenant=tenant_a, item=item_a, destination=receiving_loc_bin_a, priority=5)
        second = PutawayRule.objects.create(
            tenant=tenant_a, item=item_a, destination=receiving_loc_bin_a, priority=50)
        assert list(PutawayRule.objects.all()) == [low, first, second]  # priority ASC, id tiebreak

    def test_receiving_meta_index_tier_consts_and_no_unique_together(self):
        indexes = {idx.name: idx.fields for idx in PutawayRule._meta.indexes}
        assert indexes.get("inv_pwr_tnt_active_idx") == ["tenant", "is_active"]
        assert (TIER_ITEM, TIER_CATEGORY, TIER_ANY) == (3, 2, 1)
        assert TIER_ITEM > TIER_CATEGORY > TIER_ANY
        # Overlapping rules are the DESIGN — no unique_together may exist.
        assert not PutawayRule._meta.unique_together

    def test_receiving_overlapping_rules_coexist_same_scope_different_priority(
            self, tenant_a, receiving_rule_catchall_a, receiving_loc_dock_a, receiving_loc_bin_a):
        PutawayRule.objects.create(  # same catch-all scope as the fixture, sharper priority
            tenant=tenant_a, destination=receiving_loc_bin_a, priority=1)
        assert PutawayRule.objects.filter(tenant=tenant_a).count() == 2


# ------------------------------------------------------------------ clean()


class TestReceivingPutawayRuleClean:
    def test_receiving_clean_rejects_cross_tenant_fields_keyed_on_field(
            self, tenant_a, tenant_b, item_b, receiving_loc_bin_a,
            receiving_loc_dock_b, receiving_loc_bin_b):
        category_b = _receiving_category(tenant_b, "Globex Cat")
        cases = {
            "item": PutawayRule(tenant=tenant_a, item=item_b, destination=receiving_loc_bin_a),
            "category": PutawayRule(tenant=tenant_a, category=category_b,
                                    destination=receiving_loc_bin_a),
            "source_location": PutawayRule(tenant=tenant_a,
                                           source_location=receiving_loc_dock_b,
                                           destination=receiving_loc_bin_a),
            "destination": PutawayRule(tenant=tenant_a, destination=receiving_loc_bin_b),
        }
        for field, instance in cases.items():
            with pytest.raises(ValidationError) as err:
                instance.full_clean()
            assert field in err.value.message_dict, f"error not keyed on {field}"

    def test_receiving_clean_same_source_destination_is_nonfield_error(
            self, tenant_a, receiving_loc_bin_a):
        rule = PutawayRule(tenant=tenant_a, source_location=receiving_loc_bin_a,
                           destination=receiving_loc_bin_a)
        with pytest.raises(ValidationError) as err:
            rule.full_clean()
        assert "__all__" in err.value.message_dict
        assert "different" in " ".join(err.value.messages).lower()

    def test_receiving_clean_unset_destination_raises_validation_error_not_related_does_not_exist(
            self, tenant_a):
        """C1 regression: a crafted/incomplete POST leaves destination unassigned; full_clean()
        must surface a FIELD error, never let RelatedObjectDoesNotExist escape as a 500."""
        with pytest.raises(ValidationError) as err:
            PutawayRule(tenant=tenant_a).full_clean()
        assert "destination" in err.value.message_dict


# ------------------------------------------------------------------ resolver tier order


class TestReceivingResolverTiers:
    def test_receiving_rule_hit_reason_cites_arrival_point(
            self, receiving_task_a, receiving_loc_bin_a, receiving_rule_a):
        suggestion, reason, candidates = resolve_putaway_suggestion(receiving_task_a)
        assert suggestion.pk == receiving_loc_bin_a.pk
        assert reason == "Rule: CAT-1 arriving RDOCK-A → RA-01"
        assert candidates[0][0].pk == suggestion.pk  # candidates[0] IS the suggestion

    def test_receiving_rule_reason_omits_arriving_without_source(
            self, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a):
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        PutawayRule.objects.create(tenant=tenant_a, destination=receiving_loc_bin_a)
        suggestion, reason, _candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == receiving_loc_bin_a.pk
        assert reason == f"Rule: Any item → {receiving_loc_bin_a.code}"
        assert "arriving" not in reason

    def test_receiving_item_tier_beats_priority_inverted_catchall(
            self, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a):
        hi_bin = _receiving_location(tenant_a, "RA-HI")
        lo_bin = _receiving_location(tenant_a, "RA-LO")
        PutawayRule.objects.create(tenant=tenant_a, item=item_a,
                                   destination=hi_bin, priority=999)
        PutawayRule.objects.create(tenant=tenant_a, destination=lo_bin, priority=1)
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, reason, candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == hi_bin.pk  # tier 3 wins despite the worst priority
        assert reason.startswith("Rule: CAT-1")
        assert [_loc.pk for _loc, _ in candidates[:2]] == [hi_bin.pk, lo_bin.pk]

    def test_receiving_category_tier_fires_when_no_item_rule(
            self, tenant_a, receiving_loc_dock_a, receiving_loc_bin_a):
        cat = _receiving_category(tenant_a, "Electronics")
        item = _receiving_item(tenant_a, "ELEC-9", category=cat)
        PutawayRule.objects.create(tenant=tenant_a, category=cat,
                                   destination=receiving_loc_bin_a)
        task = _receiving_task(tenant_a, item, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, reason, _candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == receiving_loc_bin_a.pk
        assert reason == f"Rule: {cat.name} → {receiving_loc_bin_a.code}"

    def test_receiving_dual_pinned_rule_does_not_fall_through_to_category_leg(
            self, tenant_a, receiving_loc_warehouse_a, receiving_loc_dock_a):
        # Seq 5 beats the conftest bin_a fixture (RA-01, seq 10) in walk-order ties.
        other_bin = _receiving_location(tenant_a, "RA-OT", parent=receiving_loc_warehouse_a,
                                        pick_sequence=5)
        dual_bin = _receiving_location(tenant_a, "RA-DU", parent=receiving_loc_warehouse_a,
                                       pick_sequence=30)
        cat = _receiving_category(tenant_a, "Electronics")
        pinned = _receiving_item(tenant_a, "DUAL-1", category=cat)
        sibling = _receiving_item(tenant_a, "DUAL-2", category=cat)  # same category, NOT pinned
        PutawayRule.objects.create(tenant=tenant_a, item=pinned, category=cat,
                                   destination=dual_bin, priority=1)
        task = _receiving_task(tenant_a, sibling, receiving_loc_dock_a, other_bin)
        suggestion, reason, candidates = resolve_putaway_suggestion(task)
        # The dual-pinned rule matches NEITHER leg for the sibling item…
        assert all(not why.startswith("Rule:") for _loc, why in candidates)
        assert dual_bin.pk in [loc.pk for loc in _receiving_locs(candidates)]
        # …so the answer degrades to the walk-order fallback, skipping the dual bin's slot.
        assert suggestion.pk == other_bin.pk
        assert reason == "First pickable bin by walk order"


# ------------------------------------------------------------------ disqualifiers


class TestReceivingDisqualifiers:
    def test_receiving_inactive_destination_walked_past_to_next_rule(
            self, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_warehouse_a,
            receiving_loc_bin_a):
        dead_bin = _receiving_location(tenant_a, "RA-DEAD", parent=receiving_loc_warehouse_a,
                                       is_active=False)
        PutawayRule.objects.create(tenant=tenant_a, item=item_a, source_location=receiving_loc_dock_a,
                                   destination=dead_bin, priority=10)
        PutawayRule.objects.create(tenant=tenant_a, item=item_a,
                                   destination=receiving_loc_bin_a, priority=900)
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, _reason, candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == receiving_loc_bin_a.pk
        assert dead_bin.pk not in [loc.pk for loc in _receiving_locs(candidates)]

    def test_receiving_full_declared_capacity_refused_blank_capacity_never_full(
            self, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_warehouse_a,
            receiving_loc_bin_a):
        full_bin = _receiving_location(tenant_a, "RA-FULL", parent=receiving_loc_warehouse_a,
                                       capacity=Decimal("100"))
        huge_bin = _receiving_location(tenant_a, "RA-HUGE", parent=receiving_loc_warehouse_a)
        _receiving_move(tenant_a, item_a, full_bin, "100")       # exactly AT declared capacity
        _receiving_move(tenant_a, item_a, huge_bin, "1000000")   # blank capacity = unlimited
        PutawayRule.objects.create(tenant=tenant_a, item=item_a, destination=full_bin, priority=10)
        PutawayRule.objects.create(tenant=tenant_a, destination=huge_bin, priority=500)
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, _reason, candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == huge_bin.pk
        assert full_bin.pk not in [loc.pk for loc in _receiving_locs(candidates)]

    def test_receiving_owner_client_conflict_refused_blank_shared_and_matching_accepted(
            self, tenant_a, receiving_loc_warehouse_a, receiving_loc_dock_a, receiving_loc_bin_a):
        # Seqs 5/6 put both ahead of the conftest bin_a fixture (RA-01, seq 10), so this
        # test's ownership verdict is decided between reserved and shared — not by RA-01.
        client_x = _receiving_client(tenant_a, "CX")
        reserved = _receiving_location(tenant_a, "RA-CX", parent=receiving_loc_warehouse_a,
                                       pick_sequence=5, owner_client=client_x)
        shared = _receiving_location(tenant_a, "RA-SH", parent=receiving_loc_warehouse_a,
                                     pick_sequence=6)
        plain_item = _receiving_item(tenant_a, "OWN-N")           # blank owner = house goods
        owned_item = _receiving_item(tenant_a, "OWN-X", owner_client=client_x)
        # Client X's dedicated bin refuses another owner's goods (walk order would pick it first)…
        plain_task = _receiving_task(tenant_a, plain_item, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, _reason, candidates = resolve_putaway_suggestion(plain_task)
        assert suggestion.pk == shared.pk
        assert reserved.pk not in [loc.pk for loc in _receiving_locs(candidates)]
        # …but takes its own owner's arrival, ahead of the lower-walked shared bin.
        owned_task = _receiving_task(tenant_a, owned_item, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, _reason, _candidates = resolve_putaway_suggestion(owned_task)
        assert suggestion.pk == reserved.pk

    def test_receiving_candidate_equals_from_location_excluded(
            self, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a):
        PutawayRule.objects.create(tenant=tenant_a, item=item_a,
                                   destination=receiving_loc_dock_a, priority=10)
        PutawayRule.objects.create(tenant=tenant_a, destination=receiving_loc_bin_a, priority=100)
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, reason, candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == receiving_loc_bin_a.pk  # the dock itself is never suggested
        assert receiving_loc_dock_a.pk not in [loc.pk for loc in _receiving_locs(candidates)]
        assert reason == f"Rule: Any item → {receiving_loc_bin_a.code}"

    def test_receiving_dedupe_across_tiers_keeps_first_best_reason(
            self, receiving_task_a, receiving_loc_bin_a, receiving_rule_a):
        _receiving_move(receiving_task_a.tenant, receiving_task_a.item,
                        receiving_loc_bin_a, "60")  # also qualifies via consolidation tier
        _suggestion, reason, candidates = resolve_putaway_suggestion(receiving_task_a)
        hits = [(loc.pk, why) for loc, why in candidates if loc.pk == receiving_loc_bin_a.pk]
        assert len(hits) == 1  # one candidate per bin, ever
        assert hits[0] == (receiving_loc_bin_a.pk, "Rule: CAT-1 arriving RDOCK-A → RA-01")
        assert candidates[0][1].startswith("Rule:")  # the EARLIER tier's reason survives


# ------------------------------------------------------------------ fallback tiers


class TestReceivingFallbackTiers:
    def test_receiving_consolidation_tier_already_holds_sku(
            self, tenant_a, item_a, receiving_loc_warehouse_a, receiving_loc_dock_a,
            receiving_loc_bin_a):
        hold_bin = _receiving_location(tenant_a, "RA-HOLD", parent=receiving_loc_warehouse_a,
                                       pick_sequence=5)
        _receiving_move(tenant_a, item_a, hold_bin, "5")
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, reason, _candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == hold_bin.pk  # no rules exist — consolidation speaks first
        assert reason == f"Already holds {item_a.sku}"

    def test_receiving_condition_match_reason_nearest_node_wins(
            self, tenant_a, item_a, receiving_loc_warehouse_a, receiving_loc_dock_a,
            receiving_loc_bin_a):
        zone = _receiving_location(tenant_a, "RZONE-C", parent=receiving_loc_warehouse_a,
                                   location_type="zone", storage_condition="chilled")
        own_bin = _receiving_location(tenant_a, "RA-COLD", parent=receiving_loc_warehouse_a,
                                      pick_sequence=10, storage_condition="chilled")
        inherited_bin = _receiving_location(tenant_a, "RA-INH", parent=zone, pick_sequence=20)
        chilled = _receiving_item(tenant_a, "CHIL-1", storage_condition="chilled")
        task = _receiving_task(tenant_a, chilled, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, _reason, candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == own_bin.pk
        assert candidates[0] == (own_bin, "Condition 'chilled' matched at RA-COLD")
        assert candidates[1] == (inherited_bin, "Condition 'chilled' matched at RZONE-C")

    def test_receiving_walk_order_fallback_under_receipts_warehouse(
            self, tenant_a, item_a, receiving_loc_warehouse_a, receiving_loc_dock_a,
            receiving_loc_bin_a):
        # The conftest bin_a fixture would otherwise join the fallback stream behind this
        # pair; take it offline so the workspace holds EXACTLY the bins asserted below.
        receiving_loc_bin_a.is_active = False
        receiving_loc_bin_a.save()
        unpickable = _receiving_location(tenant_a, "RA-NP", parent=receiving_loc_warehouse_a,
                                         pick_sequence=4, is_pickable=False)
        # Seqs 5/6 keep this pair ahead of the conftest bin_a fixture (RA-01, seq 10) so the
        # walk-order assertion lists exactly these two candidates.
        first = _receiving_location(tenant_a, "RA-B1", parent=receiving_loc_warehouse_a,
                                    pick_sequence=5)
        second = _receiving_location(tenant_a, "RA-B2", parent=receiving_loc_warehouse_a,
                                     pick_sequence=6)
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, reason, candidates = resolve_putaway_suggestion(task)
        assert suggestion.pk == first.pk
        assert reason == "First pickable bin by walk order"
        assert [loc.pk for loc in _receiving_locs(candidates)] == [first.pk, second.pk]
        assert unpickable.pk not in [loc.pk for loc in _receiving_locs(candidates)]

    def test_receiving_total_refusal_starts_no_suggestion_found(
            self, tenant_a, item_a, receiving_loc_warehouse_a, receiving_loc_dock_a,
            receiving_loc_bin_a):
        # The conftest bin_a fixture would otherwise be an eligible fallback bin; take the
        # whole workspace offline so the ONLY bin left is the inactive one below.
        receiving_loc_bin_a.is_active = False
        receiving_loc_bin_a.save()
        _receiving_location(tenant_a, "RA-OFF", parent=receiving_loc_warehouse_a,
                            is_active=False)  # the only other bin, and it cannot take stock
        task = _receiving_task(tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a)
        suggestion, reason, candidates = resolve_putaway_suggestion(task)
        assert suggestion is None
        assert candidates == []
        assert reason.startswith("No Suggestion Found")


# ------------------------------------------------------------------ determinism + kwargs parity


class TestReceivingDeterminismAndPreload:
    def test_receiving_preloaded_kwargs_match_bare_call_and_repeat_calls_equal(
            self, tenant_a, item_a, receiving_rule_a, receiving_rule_catchall_a,
            receiving_task_a, receiving_loc_warehouse_a, receiving_loc_bin_a):
        from apps.scm.models import Location, StockMove
        extra_bin = _receiving_location(tenant_a, "RA-XTRA", parent=receiving_loc_warehouse_a)
        _receiving_move(tenant_a, item_a, receiving_loc_bin_a, "60")  # dedupes with the rule hit
        _receiving_move(tenant_a, item_a, extra_bin, "40")            # a live consolidation rival

        bare_once = _receiving_view(resolve_putaway_suggestion(receiving_task_a))
        bare_twice = _receiving_view(resolve_putaway_suggestion(receiving_task_a))
        assert bare_once == bare_twice  # determinism: identical data, identical answer

        # Batch kwargs are keyword-only by contract.
        with pytest.raises(TypeError):
            resolve_putaway_suggestion(receiving_task_a, [])

        rules = list(PutawayRule.objects.filter(tenant=tenant_a, is_active=True))
        by_pk = {loc.pk: loc for loc in Location.objects.filter(tenant=tenant_a)}
        held = dict(
            StockMove.objects.filter(tenant=tenant_a, item_id=item_a.pk)
            .values_list("location").annotate(qty=Sum("quantity")).values_list("location", "qty"))
        preloaded = _receiving_view(resolve_putaway_suggestion(
            receiving_task_a, rules=rules, by_pk=by_pk, on_hand={item_a.pk: held}))
        assert preloaded == bare_once  # I2 regression: preload answers EXACTLY what bare loads
