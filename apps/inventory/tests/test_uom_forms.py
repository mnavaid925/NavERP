"""Inventory 5.20 Units of Measure — form tests."""
from decimal import Decimal

import pytest

from apps.inventory.forms import UomConversionForm
from apps.inventory.models import UomConversion
from apps.scm.models import Item, UOM

pytestmark = pytest.mark.django_db


def _uom(tenant, code, factor="1"):
    uom, _ = UOM.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": code, "factor": Decimal(factor)})
    return uom


@pytest.fixture
def ea_a(db, tenant_a):
    return _uom(tenant_a, "EA")


@pytest.fixture
def case_a(db, tenant_a):
    return _uom(tenant_a, "CASE", "12")


@pytest.fixture
def ea_b(db, tenant_b):
    return _uom(tenant_b, "EA")


def _payload(case, each, **over):
    data = {"from_uom": case.pk, "to_uom": each.pk, "factor": "24",
            "is_active": "on", "notes": "double case"}
    data.update(over)
    return data


def test_valid_create_saves(tenant_a, case_a, ea_a):
    form = UomConversionForm(_payload(case_a, ea_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.pk is not None and obj.tenant_id == tenant_a.pk
    assert UomConversion.objects.filter(
        tenant=tenant_a, from_uom=case_a, to_uom=ea_a).exists()


def test_same_unit_refused_once(tenant_a, case_a):
    form = UomConversionForm(_payload(case_a, case_a), tenant=tenant_a)
    assert not form.is_valid()
    # The refusal lives ONLY in the model clean() — exactly one message on the field.
    errors = form.errors.get("to_uom", [])
    assert len([e for e in errors if "different units" in e]) == 1


def test_foreign_uom_rejected(tenant_a, tenant_b, case_a, ea_b):
    form = UomConversionForm(_payload(case_a, ea_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "another workspace" in str(form.errors)


def test_duplicate_pair_rejected_at_form(tenant_a, case_a, ea_a):
    item = Item.objects.create(tenant=tenant_a, sku="DUP-1", name="Dup")
    UomConversion.objects.create(
        tenant=tenant_a, item=item, from_uom=case_a, to_uom=ea_a, factor=Decimal("24"))
    form = UomConversionForm(
        {"item": item.pk, "from_uom": case_a.pk, "to_uom": ea_a.pk,
         "factor": "48", "notes": ""},
        tenant=tenant_a)
    assert not form.is_valid()
    assert any("already exists" in e for e in form.non_field_errors())


def test_blank_item_is_the_default_scope(tenant_a, case_a, ea_a):
    form = UomConversionForm(_payload(case_a, ea_a, item=""), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.item is None
