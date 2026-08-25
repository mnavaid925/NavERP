"""Inventory 5.18 — security tests: tenant isolation, privilege gating, junk-param probes."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, GLAccount
from apps.inventory.models import GLPostRule, TaxRule
from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote, Item, Location, PurchaseOrder, \
    PurchaseOrderLine


@pytest.fixture
def sec_gl(db, tenant_a):
    return {
        "inventory": GLAccount.objects.create(tenant=tenant_a, code="1500", name="Inventory",
                                              account_type="asset"),
        "offset": GLAccount.objects.create(tenant=tenant_a, code="6000",
                                           name="Operating Expenses", account_type="expense"),
    }


def _make_taxrule(tenant, code):
    from apps.accounting.models import TaxCode
    return TaxRule.objects.create(tenant=tenant, name="Sec rule",
                                  tax_code=TaxCode.objects.create(
                                      tenant=tenant, name="T", rate_pct=1), priority=10)


@pytest.mark.django_db
def test_finint_cross_tenant_detail_is_404(client_b, tenant_b, tenant_a, db):
    rule = _make_taxrule(tenant_a, None)
    assert client_b.get(reverse("inventory:taxrule_detail", args=[rule.pk])).status_code == 404
    assert client_b.get(reverse("inventory:taxrule_edit", args=[rule.pk])).status_code == 404


@pytest.mark.django_db
def test_finint_member_cannot_write_rules(member_client, tenant_a, sec_gl, db):
    response = member_client.post(reverse("inventory:taxrule_create"), {"name": "x"})
    assert response.status_code == 403
    response = member_client.post(reverse("inventory:glpostrule_create"), {"name": "x"})
    assert response.status_code == 403


@pytest.mark.django_db
def test_finint_member_cannot_run_syncs_or_posting(client_a, member_client, tenant_a,
                                                   admin_user, db):
    item = Item.objects.create(tenant=tenant_a, sku="SEC-1", name="S")
    loc = Location.objects.create(tenant=tenant_a, code="SEC-BIN", name="B",
                                  location_type="bin")
    po = PurchaseOrder(tenant=tenant_a, vendor=_vendor_party(tenant_a),
                       order_date=timezone.localdate(), status="approved")
    po.save()
    PurchaseOrderLine.objects.create(purchase_order=po, sku_hint=item.sku,
                                     quantity=Decimal("1"), unit_price=Decimal("1"))
    grn = GoodsReceiptNote(tenant=tenant_a, purchase_order=po, location=loc,
                           receipt_date=timezone.localdate(), status="draft")
    grn.save()
    GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=po.lines.get(),
                                    quantity_received=Decimal("1"))

    for url in (reverse("inventory:ap_sync_run", args=[grn.pk]),
                reverse("inventory:je_post_cogs")):
        response = member_client.post(url)
        assert response.status_code == 403, url


@pytest.mark.django_db
def test_finint_anonymous_is_redirected_to_login(db):
    from django.test import Client
    c = Client()
    for url in ("inventory:ap_sync", "inventory:ar_sync", "inventory:je_automation",
                "inventory:taxrule_list"):
        response = c.get(reverse(url))
        assert response.status_code == 302, url


@pytest.mark.django_db
def test_finint_junk_get_params_do_not_500(client_a, db):
    probes = (
        "/inventory/finance/ap-sync/?vendor=abc",
        "/inventory/finance/ap-sync/?vendor=\u00b2",
        "/inventory/finance/ap-sync/?vendor=999999999999999999999999&q=%C3%A9",
        "/inventory/tax-rules/?active=yes&q=<script>",
        "/inventory/gl-post-rules/?page=notanumber",
    )
    for url in probes:
        response = client_a.get(url)
        assert response.status_code in (200, 302), url


@pytest.mark.django_db
def test_finint_glpostrule_delete_is_admin_only_and_posts_nothing(client_a, member_client,
                                                                  tenant_a, sec_gl, db):
    rule = GLPostRule.objects.create(
        tenant=tenant_a, event_type="adjustment", name="Del probe",
        inventory_account=sec_gl["inventory"], offset_account=sec_gl["offset"])
    assert member_client.post(
        reverse("inventory:glpostrule_delete", args=[rule.pk])).status_code == 403
    assert client_a.post(
        reverse("inventory:glpostrule_delete", args=[rule.pk])).status_code == 302
    assert not GLPostRule.objects.filter(pk=rule.pk).exists()


def _vendor_party(tenant):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, kind="organization", name="Sec Vendor")
    PartyRole.objects.create(tenant=tenant, party=party, role="vendor", status="active",
                             start_date=timezone.localdate())
    return party
