"""Inventory 5.20 Units of Measure — model tests for UomConversion + engine."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    MAX_PATH_DEPTH,
    UomConversion,
    convert_quantity,
    find_conversion_path,
)
from apps.scm.models import UOM

pytestmark = pytest.mark.django_db


def _uom(tenant, code, factor="1", name=None):
    uom, _ = UOM.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name or code, "factor": Decimal(factor)})
    return uom


@pytest.fixture
def ea_a(db, tenant_a):
    return _uom(tenant_a, "EA")


@pytest.fixture
def case_a(db, tenant_a):
    return _uom(tenant_a, "CASE", "12")


@pytest.fixture
def plt_a(db, tenant_a):
    return _uom(tenant_a, "PLT", "480")


def test_str_and_is_default(tenant_a, case_a, ea_a):
    rule = UomConversion.objects.create(
        tenant=tenant_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("12"))
    assert rule.is_default
    assert "CASE" in str(rule) and "EA" in str(rule) and "12" in str(rule)


def test_reverse_factor_lossy_but_guarded(tenant_a, case_a, ea_a):
    rule = UomConversion.objects.create(
        tenant=tenant_a, from_uom=ea_a, to_uom=case_a, factor=Decimal("3"))
    assert rule.reverse_factor == Decimal("0.3333")
    assert rule.convert(Decimal("10")) == Decimal("30.0000")


def test_resolve_item_rule_beats_default(tenant_a, item_a, item_b, case_a, ea_a):
    default = UomConversion.objects.create(
        tenant=tenant_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("12"))
    pinned = UomConversion.objects.create(
        tenant=tenant_a, item=item_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("24"))
    # Another SKU's private rule never answers this item's question.
    UomConversion.objects.create(
        tenant=tenant_a, item=item_b, from_uom=case_a, to_uom=ea_a, factor=Decimal("99"))
    # .first() returns fresh instances — compare identities by pk.
    assert UomConversion.resolve(tenant_a, None, case_a, ea_a).pk == default.pk
    assert UomConversion.resolve(tenant_a, item_a, case_a, ea_a).pk == pinned.pk
    # Inactive rules never fire.
    pinned.is_active = False
    pinned.save(update_fields=["is_active"])
    assert UomConversion.resolve(tenant_a, item_a, case_a, ea_a).pk == default.pk
    # Unknown pair -> None, never a guess.
    other = _uom(tenant_a, "BOX")
    assert UomConversion.resolve(tenant_a, item_a, case_a, other) is None


def test_find_path_identity_chain_unreachable(tenant_a, case_a, ea_a, plt_a):
    case_to_each = UomConversion.objects.create(
        tenant=tenant_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("12"))
    pallet_to_case = UomConversion.objects.create(
        tenant=tenant_a, from_uom=plt_a, to_uom=case_a, factor=Decimal("40"))
    assert find_conversion_path(tenant_a, None, ea_a, ea_a) == []
    path = find_conversion_path(tenant_a, None, plt_a, ea_a)
    assert path == [pallet_to_case, case_to_each]
    # Reverse direction has no rules: honestly unreachable.
    assert find_conversion_path(tenant_a, None, ea_a, plt_a) is None
    res, path2 = convert_quantity(tenant_a, None, Decimal("2"), plt_a, ea_a)
    assert res == Decimal("960.0000") and len(path2) == 2


def test_path_depth_cap(tenant_a):
    uoms = [_uom(tenant_a, f"U{i}") for i in range(MAX_PATH_DEPTH + 3)]
    for src, dst in zip(uoms, uoms[1:]):
        UomConversion.objects.create(
            tenant=tenant_a, from_uom=src, to_uom=dst, factor=Decimal("2"))
    # MAX hops reachable...
    within = find_conversion_path(tenant_a, None, uoms[0], uoms[MAX_PATH_DEPTH])
    assert within is not None and len(within) <= MAX_PATH_DEPTH
    # ...one hop beyond the cap is refused, never guessed.
    assert find_conversion_path(tenant_a, None, uoms[0], uoms[MAX_PATH_DEPTH + 1]) is None


def test_engine_tenant_isolated(tenant_a, tenant_b, case_a, ea_a):
    from apps.scm.models import Item
    foreign_item = Item.objects.create(tenant=tenant_b, sku="F-1", name="Foreign")
    UomConversion.objects.create(
        tenant=tenant_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("12"))
    assert find_conversion_path(tenant_b, foreign_item, case_a, ea_a) is None
    assert convert_quantity(tenant_b, foreign_item, 1, case_a, ea_a) == (None, None)


def test_clean_refuses_same_unit(tenant_a, case_a, ea_a):
    rule = UomConversion(tenant=tenant_a, from_uom=case_a, to_uom=case_a, factor=1)
    with pytest.raises(ValidationError) as exc:
        rule.full_clean()
    assert "to_uom" in exc.value.message_dict


def test_clean_refuses_foreign_fk(tenant_a, tenant_b):
    foreign = _uom(tenant_b, "EA")
    local_case = _uom(tenant_a, "CASE")
    rule = UomConversion(
        tenant=tenant_a, from_uom=local_case, to_uom=foreign, factor=1)
    with pytest.raises(ValidationError) as exc:
        rule.full_clean()
    assert "to_uom" in exc.value.message_dict


def test_duplicate_probe_covers_null_item_gap(tenant_a, case_a, ea_a):
    """MariaDB/SQLite null-coalescing unique cannot see two item=NULL rows — clean() must."""
    UomConversion.objects.create(
        tenant=tenant_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("12"))
    twin = UomConversion(tenant=tenant_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("13"))
    with pytest.raises(ValidationError):
        twin.full_clean()
    # A different pair is fine, and editing the original excludes itself.
    other_pair = UomConversion(tenant=tenant_a, from_uom=ea_a, to_uom=case_a, factor=1)
    other_pair.full_clean()


def test_item_pinned_duplicates_are_rejected_too(tenant_a, item_a, case_a, ea_a):
    UomConversion.objects.create(
        tenant=tenant_a, item=item_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("24"))
    twin = UomConversion(
        tenant=tenant_a, item=item_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("48"))
    with pytest.raises(ValidationError):
        twin.full_clean()
