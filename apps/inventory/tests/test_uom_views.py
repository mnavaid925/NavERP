"""Inventory 5.20 Units of Measure — view tests (CRUD + calculator branches)."""
from decimal import Decimal

import pytest
from django.urls import reverse

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
def plt_a(db, tenant_a):
    return _uom(tenant_a, "PLT", "480")


@pytest.fixture
def default_rule(db, tenant_a, case_a, ea_a):
    return UomConversion.objects.create(
        tenant=tenant_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("12"),
        notes="every case is twelve")


def test_list_renders_with_seeded_rule(client_a, default_rule):
    body = client_a.get(reverse("inventory:uomconversion_list")).content.decode()
    assert "CASE" in body and "EA" in body and "{#" not in body


def test_list_scope_and_active_lenses(client_a, tenant_a, case_a, ea_a, default_rule):
    list_url = reverse("inventory:uomconversion_list")
    assert client_a.get(list_url + "?scope=default").status_code == 200
    assert client_a.get(list_url + "?scope=item").status_code == 200
    assert client_a.get(list_url + "?scope=bogus").status_code == 200  # falls back to all
    assert client_a.get(list_url + "?active=True").status_code == 200
    assert client_a.get(list_url + "?item=99999999").status_code == 200  # empty, not crash


def test_list_search_hits_notes(client_a, default_rule):
    body = client_a.get(
        reverse("inventory:uomconversion_list") + "?q=twelve").content.decode()
    assert "CASE" in body


def test_detail_shows_ladder_and_fires_verdict(client_a, tenant_a, item_a,
                                                case_a, ea_a, default_rule):
    body = client_a.get(
        reverse("inventory:uomconversion_detail", args=[default_rule.pk])).content.decode()
    assert "Ladder" in body and "Fires today?" in body and "Yes" in body
    # An inactive rule that lost its pair shows the honest "No".
    pinned = UomConversion.objects.create(
        tenant=tenant_a, item=item_a, from_uom=case_a, to_uom=ea_a,
        factor=Decimal("24"), is_active=False)
    body = client_a.get(
        reverse("inventory:uomconversion_detail", args=[pinned.pk])).content.decode()
    assert "No" in body


def test_create_edit_delete_roundtrip(client_a, tenant_a, case_a, ea_a, default_rule):
    r = client_a.post(reverse("inventory:uomconversion_create"),
                      {"from_uom": case_a.pk, "to_uom": ea_a.pk, "factor": "6",
                       "is_active": "on", "notes": "half dozen"})
    assert r.status_code == 302
    assert UomConversion.objects.filter(tenant=tenant_a, factor=Decimal("6")).exists()

    r = client_a.post(reverse("inventory:uomconversion_edit", args=[default_rule.pk]),
                      {"from_uom": case_a.pk, "to_uom": ea_a.pk, "factor": "13",
                       "is_active": "on", "notes": ""})
    assert r.status_code == 302
    default_rule.refresh_from_db()
    assert default_rule.factor == Decimal("13")

    r = client_a.post(reverse("inventory:uomconversion_delete", args=[default_rule.pk]))
    assert r.status_code == 302
    assert not UomConversion.objects.filter(pk=default_rule.pk).exists()


def test_delete_get_is_method_not_allowed(client_a, default_rule):
    assert client_a.get(
        reverse("inventory:uomconversion_delete",
                args=[default_rule.pk])).status_code in (403, 405)


def test_calculator_direct_chain_override_identity(client_a, tenant_a, item_a,
                                                    case_a, ea_a, plt_a, default_rule):
    url = reverse("inventory:uom_calculator")
    r = client_a.get(f"{url}?qty=5&from={case_a.pk}&to={ea_a.pk}")
    body = r.content.decode()
    assert "60" in body and "Route taken" in body

    # Chained through the CASE hop.
    UomConversion.objects.create(
        tenant=tenant_a, from_uom=plt_a, to_uom=case_a, factor=Decimal("40"))
    body = client_a.get(f"{url}?qty=2&from={plt_a.pk}&to={ea_a.pk}").content.decode()
    assert "960" in body

    # Item-pinned rule outranks the default only when the item is named.
    UomConversion.objects.create(
        tenant=tenant_a, item=item_a, from_uom=case_a, to_uom=ea_a, factor=Decimal("24"))
    body = client_a.get(
        f"{url}?qty=1&from={case_a.pk}&to={ea_a.pk}&item={item_a.pk}").content.decode()
    assert ">24<" in body
    body = client_a.get(f"{url}?qty=1&from={case_a.pk}&to={ea_a.pk}").content.decode()
    assert '>12<' in body

    # Identity renders its own branch.
    body = client_a.get(f"{url}?qty=7&from={ea_a.pk}&to={ea_a.pk}").content.decode()
    assert "Identity" in body


def test_calculator_honest_refusals(client_a, tenant_a, case_a, ea_a, plt_a):
    url = reverse("inventory:uom_calculator")
    body = client_a.get(url).content.decode()  # bare page renders
    assert "Convert" in body
    body = client_a.get(f"{url}?qty=1&from={ea_a.pk}&to={plt_a.pk}").content.decode()
    assert "No conversion path" in body
    body = client_a.get(f"{url}?qty=abc&from={ea_a.pk}&to={case_a.pk}").content.decode()
    assert "not a quantity" in body
    body = client_a.get(f"{url}?qty=Infinity&from={ea_a.pk}&to={case_a.pk}").content.decode()
    assert "finite number" in body
    body = client_a.get(f"{url}?qty=NaN&from={ea_a.pk}&to={case_a.pk}").content.decode()
    assert "finite number" in body
    body = client_a.get(f"{url}?qty=1e999&from={case_a.pk}&to={ea_a.pk}").content.decode()
    assert "too large" in body
    body = client_a.get(f"{url}?to={ea_a.pk}").content.decode()
    assert "Pick both units" in body
