"""Inventory 5.20 Units of Measure — security tests (tenancy, privilege, auth)."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.inventory.models import UomConversion
from apps.scm.models import UOM

pytestmark = pytest.mark.django_db


def _uom(tenant, code, factor="1"):
    uom, _ = UOM.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": code, "factor": Decimal(factor)})
    return uom


@pytest.fixture
def rule_a(db, tenant_a):
    case, _ = UOM.objects.get_or_create(
        tenant=tenant_a, code="CASE", defaults={"name": "Case", "factor": Decimal("12")})
    ea, _ = UOM.objects.get_or_create(
        tenant=tenant_a, code="EA", defaults={"name": "Each", "factor": Decimal("1")})
    return UomConversion.objects.create(
        tenant=tenant_a, from_uom=case, to_uom=ea, factor=Decimal("12"))


@pytest.fixture
def rule_b(db, tenant_b):
    case, _ = UOM.objects.get_or_create(
        tenant=tenant_b, code="CASE", defaults={"name": "Case", "factor": Decimal("12")})
    ea, _ = UOM.objects.get_or_create(
        tenant=tenant_b, code="EA", defaults={"name": "Each", "factor": Decimal("1")})
    return UomConversion.objects.create(
        tenant=tenant_b, from_uom=case, to_uom=ea, factor=Decimal("10"))


def test_cross_tenant_routes_404(client_a, rule_b):
    assert client_a.get(reverse("inventory:uomconversion_detail",
                                args=[rule_b.pk])).status_code == 404
    assert client_a.get(reverse("inventory:uomconversion_edit",
                                args=[rule_b.pk])).status_code == 404
    assert client_a.post(reverse("inventory:uomconversion_delete",
                                 args=[rule_b.pk])).status_code == 404


def test_member_reads_but_cannot_write(member_client, rule_a, tenant_a):
    from apps.scm.models import UOM as _U
    assert member_client.get(reverse("inventory:uomconversion_list")).status_code == 200
    assert member_client.get(reverse("inventory:uomconversion_detail",
                                     args=[rule_a.pk])).status_code == 200
    assert member_client.get(reverse("inventory:uom_calculator")).status_code == 200

    case = _U.objects.filter(tenant=tenant_a, code="CASE").first()
    ea = _U.objects.filter(tenant=tenant_a, code="EA").first()
    payload = {"from_uom": case.pk, "to_uom": ea.pk, "factor": "6", "notes": ""}
    assert member_client.post(reverse("inventory:uomconversion_create"),
                              payload).status_code in (302, 403)
    assert member_client.post(reverse("inventory:uomconversion_edit",
                                      args=[rule_a.pk]),
                              payload).status_code in (302, 403)
    assert member_client.post(reverse("inventory:uomconversion_delete",
                                      args=[rule_a.pk])).status_code in (302, 403)
    # Whatever the redirect behaviour, nothing may have been written.
    assert UomConversion.objects.filter(tenant=tenant_a, factor=Decimal("6")).count() == 0


def test_login_required_everywhere(client, db):
    assert client.get(reverse("inventory:uomconversion_list")).status_code in (302, 403)
    assert client.get(reverse("inventory:uom_calculator")).status_code in (302, 403)
    assert client.get(reverse("inventory:uomconversion_create")).status_code in (302, 403)


def test_calculator_never_leaks_foreign_rows(client_a, client_b, rule_a, rule_b):
    body_a = client_a.get(reverse("inventory:uom_calculator")).content.decode()
    # The foreign rule's distinctive factor must not surface anywhere on our page.
    assert ">10<" not in body_a
