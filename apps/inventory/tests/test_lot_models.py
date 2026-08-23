"""Inventory 5.8 Lot & Serial Number Tracking — model invariants.

The sub-module's whole contract lives at the model boundary: ``LotNumberRule`` resolves
most-specific-wins and mints ``scm.LotSerial`` rows (the spine's own master) through a
collision-retried sequence, refusing untracked/foreign/mismatched items; an already
past-dated expiry mints straight to status "expired" so the master never contradicts
the board; ``ShelfLifePolicy`` keeps its amber window at or beyond its red gate; and
``classify_lot`` is the ONE shared verdict function the FEFO board and policy pages
both read.
"""
from decimal import Decimal

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.inventory.models import LotNumberRule, ShelfLifePolicy, classify_lot

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ LotNumberRule


def test_lot_rule_prefix_uppercased_on_save(tenant_a):
    rule = LotNumberRule.objects.create(
        tenant=tenant_a, name="Case", prefix=" lotx ", include_date=False,
        sequence_padding=3)
    assert rule.prefix == "LOTX"


def test_lot_rule_name_unique_per_tenant(tenant_a, lot_rule_default_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LotNumberRule.objects.create(
                tenant=tenant_a, name="Default batch numbering", prefix="DUP",
                include_date=False, sequence_padding=3)


def test_lot_rule_sample_number_shape(lot_rule_default_a, lot_rule_item_a):
    dated = lot_rule_default_a.sample_number()
    assert dated.startswith("LOT") and "-" in dated
    stem, seq = dated.rsplit("-", 1)
    assert len(stem) == 3 + 6 and len(seq) == 5          # YYMMDD + zero-padded
    plain = lot_rule_item_a.sample_number(seq=7)         # include_date=False
    assert plain == f"PINA-{7:03d}"


def test_lot_rule_resolve_most_specific_wins(
        tenant_a, tracked_item_a, tracked_item_b,
        lot_rule_default_a, lot_rule_item_a,
        tenant_b, lot_rule_default_b):
    assert LotNumberRule.resolve(tenant_a, tracked_item_a) == lot_rule_item_a
    assert LotNumberRule.resolve(tenant_a, _other_tracked(tenant_a)) == lot_rule_default_a
    # Each workspace resolves within its own rows only.
    assert LotNumberRule.resolve(tenant_b, tracked_item_b) == lot_rule_default_b
    assert LotNumberRule.resolve(tenant_b, None) == lot_rule_default_b


def test_lot_rule_resolve_skips_inactive(tenant_a, tracked_item_a,
                                         lot_rule_default_a, lot_rule_item_a):
    lot_rule_default_a.is_active = False
    lot_rule_default_a.save()
    lot_rule_item_a.is_active = False
    lot_rule_item_a.save()
    assert LotNumberRule.resolve(tenant_a, tracked_item_a) is None


def _other_tracked(tenant):
    from apps.scm.models import Item
    item, _ = Item.objects.get_or_create(
        tenant=tenant, sku="LOT-OTHER", tracking="lot",
        defaults={"name": "Other batched", "standard_cost": Decimal("1")})
    return item


def test_generate_mints_spine_lotserial_sequenced(
        tenant_a, admin_user, tracked_item_a, lot_rule_item_a):
    first = lot_rule_item_a.generate(admin_user, tracked_item_a)
    second = lot_rule_item_a.generate(admin_user, tracked_item_a)
    assert first.number == "PINA-001" and second.number == "PINA-002"
    assert first.kind == "lot" and first.status == "available"
    assert first.tenant_id == tenant_a.pk and first.item_id == tracked_item_a.pk


def test_generate_refuses_untracked_and_kind_mismatch(
        db, tenant_a, admin_user, item_a, lot_rule_default_a, tracked_item_a):
    from apps.scm.models import Item
    serial_item = Item.objects.create(
        tenant=tenant_a, sku="SER-A", name="Serialised", tracking="serial")
    with pytest.raises(ValidationError):
        lot_rule_default_a.generate(admin_user, item_a)          # tracking="none"
    with pytest.raises(ValidationError):
        lot_rule_default_a.generate(admin_user, serial_item)     # rule lots vs serial SKU


def test_generate_refuses_foreign_item(db, tenant_a, admin_user, tracked_item_b,
                                       lot_rule_default_a):
    with pytest.raises(ValidationError):
        lot_rule_default_a.generate(admin_user, tracked_item_b)


def test_generate_past_expiry_mints_expired_status(
        tenant_a, admin_user, tracked_item_a, lot_rule_item_a):
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    lot = lot_rule_item_a.generate(admin_user, tracked_item_a, expiry_date=yesterday)
    assert lot.expiry_date == yesterday and lot.status == "expired"


def test_generate_sequence_advances_past_hand_made_numbers(
        db, tenant_a, admin_user, tracked_item_a, lot_rule_item_a):
    from apps.scm.models import LotSerial
    LotSerial.objects.create(tenant=tenant_a, item=tracked_item_a, number="PINA-042")
    lot = lot_rule_item_a.generate(admin_user, tracked_item_a)
    assert lot.number == "PINA-043"


def test_generate_writes_audit_row(tenant_a, admin_user, tracked_item_a,
                                   lot_rule_item_a):
    from django.contrib.contenttypes.models import ContentType

    from apps.core.models import AuditLog
    from apps.scm.models import LotSerial

    lot = lot_rule_item_a.generate(admin_user, tracked_item_a)
    assert AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(LotSerial),
        object_id=lot.pk).exists()


# ------------------------------------------------------------------ ShelfLifePolicy


def test_shelf_policy_one_per_item(db, shelf_policy_a, tenant_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ShelfLifePolicy.objects.create(tenant=tenant_a, item=shelf_policy_a.item)


def test_shelf_policy_warning_must_reach_past_gate(shelf_policy_a):
    shelf_policy_a.warning_days = shelf_policy_a.min_remaining_days - 1
    with pytest.raises(ValidationError):
        shelf_policy_a.full_clean()


def test_shelf_policy_foreign_item_rejected_in_clean(db, tenant_a, tracked_item_b):
    policy = ShelfLifePolicy(tenant=tenant_a, item=tracked_item_b)
    with pytest.raises(ValidationError):
        policy.full_clean()


# ------------------------------------------------------------------ classify_lot


def _lot_with_expiry(item, days, tenant=None):
    """An UNSAVED spine lot row with a date relative to today (None = never expires)."""
    from apps.scm.models import LotSerial
    return LotSerial(
        tenant_id=item.tenant_id, item=item, kind="lot", number=f"CLS-{days}",
        expiry_date=(timezone.localdate() + datetime.timedelta(days=days))
        if days is not None else None)


@pytest.mark.parametrize("days,policy,expected", [
    (-5, True, "expired"),
    (10, True, "blocked"),      # inside min_remaining_days=14 gate
    (30, True, "warning"),      # inside warning_days=45, past the gate
    (90, True, "ok"),
    (-5, False, "expired"),     # no policy: only expired/not matters
    (400, False, "ok"),
])
def test_classify_lot_codes(tracked_item_a, shelf_policy_a, days, policy, expected):
    verdict = classify_lot(_lot_with_expiry(tracked_item_a, days),
                           shelf_policy_a if policy else None)
    assert verdict[0] == expected


def test_classify_lot_no_expiry_is_none_code(tracked_item_a, shelf_policy_a):
    assert classify_lot(_lot_with_expiry(tracked_item_a, None), shelf_policy_a)[0] == "none"
