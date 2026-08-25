"""Inventory 5.18 — view tests: page rendering + the sync verbs end-to-end."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Bill, FiscalPeriod, GLAccount, Invoice, TaxCode
from apps.inventory.models import GLPostRule, JournalSyncLog, TaxRule, post_cogs_batch
from apps.scm.models import (
    GoodsReceiptLine,
    GoodsReceiptNote,
    Item,
    Location,
    PurchaseOrder,
    PurchaseOrderLine,
    Shipment,
    StockAdjustment,
    StockAdjustmentLine,
    StockMove,
)


# ------------------------------------------------------------------------ local fixtures

@pytest.fixture
def finint_gl(db, tenant_a):
    return {
        "inventory": GLAccount.objects.create(tenant=tenant_a, code="1500",
                                              name="Inventory", account_type="asset"),
        "cogs": GLAccount.objects.create(tenant=tenant_a, code="5000",
                                         name="Cost of Goods Sold", account_type="expense"),
        "gain": GLAccount.objects.create(tenant=tenant_a, code="6100",
                                         name="Adjustments", account_type="expense"),
    }


@pytest.fixture
def finint_rules(db, tenant_a, finint_gl):
    adjustment = GLPostRule.objects.create(
        tenant=tenant_a, event_type="adjustment", name="Stock adjustments",
        inventory_account=finint_gl["inventory"], offset_account=finint_gl["gain"])
    cogs = GLPostRule.objects.create(
        tenant=tenant_a, event_type="cogs", name="COGS",
        inventory_account=finint_gl["inventory"], offset_account=finint_gl["cogs"])
    return {"adjustment": adjustment, "cogs": cogs}


@pytest.fixture
def open_period(db, tenant_a):
    today = timezone.localdate()
    return FiscalPeriod.objects.create(
        tenant=tenant_a, name=f"{today:%b %Y}", period_type="month",
        start_date=today.replace(day=1), end_date=today + datetime.timedelta(days=28),
        status="open")


@pytest.fixture
def tax_code(db, tenant_a):
    return TaxCode.objects.create(tenant=tenant_a, name="Sales Tax", rate_pct=Decimal("8.25"))


@pytest.fixture
def finint_taxrule(db, tenant_a, tax_code):
    return TaxRule.objects.create(tenant=tenant_a, name="Default sales tax",
                                  country="", tax_code=tax_code, priority=900)


@pytest.fixture
def po_with_receipt(db, tenant_a, admin_user):
    """An approved PO + a received GRN with no bill — the AP queue's row."""
    vendor = _vendor_party(tenant_a)
    item = Item.objects.create(tenant=tenant_a, sku="FIN-V", name="View Widget")
    warehouse = Location.objects.create(tenant=tenant_a, code="FIN-WH",
                                        name="Main", location_type="warehouse")
    po = PurchaseOrder(tenant=tenant_a, vendor=vendor, order_date=timezone.localdate(),
                       status="approved")
    po.save()
    PurchaseOrderLine.objects.create(purchase_order=po, item_description=item.name,
                                     sku_hint=item.sku, quantity=Decimal("5"),
                                     unit_price=Decimal("20"))
    po.recalc_totals()
    grn = GoodsReceiptNote(tenant=tenant_a, purchase_order=po,
                           receipt_date=timezone.localdate(), status="draft")
    grn.save()
    GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=po.lines.get(),
                                    quantity_received=Decimal("5"))
    from apps.scm.views._helpers import _post_grn_receipt
    _post_grn_receipt(grn, admin_user)
    grn.status = "received"
    grn.save(update_fields=["status", "updated_at"])
    return grn


def _vendor_party(tenant):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, kind="organization", name="Fin Vendor")
    PartyRole.objects.create(tenant=tenant, party=party, role="vendor", status="active",
                             start_date=timezone.localdate())
    return party


# ------------------------------------------------------------------------------- pages

@pytest.mark.django_db
def test_finint_pages_render_for_admin(client_a, db):
    for url in ("inventory:ap_sync", "inventory:ar_sync", "inventory:je_automation",
                "inventory:taxrule_list", "inventory:glpostrule_list"):
        response = client_a.get(reverse(url))
        assert response.status_code == 200, url


@pytest.mark.django_db
def test_finint_taxrule_crud_pages(client_a, tenant_a, finint_taxrule, tax_code, db):
    assert client_a.get(reverse("inventory:taxrule_detail", args=[finint_taxrule.pk])).status_code == 200
    assert client_a.get(reverse("inventory:taxrule_create")).status_code == 200
    assert client_a.get(reverse("inventory:taxrule_edit", args=[finint_taxrule.pk])).status_code == 200
    response = client_a.post(reverse("inventory:taxrule_create"), {
        "name": "Germany VAT", "country": "Germany", "tax_code": tax_code.pk,
        "priority": "50", "is_active": "on"})
    assert response.status_code == 302
    assert TaxRule.objects.filter(tenant=tenant_a, name="Germany VAT").exists()


# --------------------------------------------------------------------------- AP verb

@pytest.mark.django_db
def test_finint_ap_sync_run_drafts_linked_bill(client_a, tenant_a, admin_user,
                                               finint_taxrule, po_with_receipt):
    grn = po_with_receipt
    response = client_a.post(reverse("inventory:ap_sync_run", args=[grn.pk]), follow=True)
    assert response.status_code == 200
    grn.refresh_from_db()
    assert grn.bill_id is not None
    bill = Bill.objects.get(pk=grn.bill_id)
    assert bill.status == "draft" and bill.party_id == grn.purchase_order.vendor_id
    assert bill.lines.count() == 1
    line = bill.lines.first()
    assert line.quantity == Decimal("5") and line.unit_price == Decimal("20")
    assert line.tax_rate_pct == Decimal("8.25")  # resolved through the catch-all TaxRule
    assert grn.match_status == "matched"  # billed exactly what was received at PO prices

    # second run is refused politely (no second bill)
    bills_before = Bill.objects.filter(tenant=tenant_a).count()
    client_a.post(reverse("inventory:ap_sync_run", args=[grn.pk]))
    assert Bill.objects.filter(tenant=tenant_a).count() == bills_before


# --------------------------------------------------------------------------- AR verb

@pytest.mark.django_db
def test_finint_ar_sync_run_links_invoice(client_a, tenant_a, admin_user, finint_taxrule,
                                          finint_item_order_delivery):
    shipment = finint_item_order_delivery
    response = client_a.post(reverse("inventory:ar_sync_run", args=[shipment.pk]),
                             follow=True)
    assert response.status_code == 200
    shipment.sales_order.refresh_from_db()
    invoice = Invoice.objects.get(pk=shipment.sales_order.invoice_id)
    assert invoice.status == "draft"
    assert invoice.lines.count() == 1
    assert invoice.total > 0


# --------------------------------------------------------------------------- JE board

@pytest.mark.django_db
def test_finint_je_post_adjustment_creates_log(client_a, tenant_a, admin_user,
                                               finint_rules, open_period):
    item = Item.objects.create(tenant=tenant_a, sku="FIN-A2", name="Adj Widget")
    loc = Location.objects.create(tenant=tenant_a, code="FIN-B2", name="Bin",
                                  location_type="bin")
    adj = StockAdjustment.objects.create(
        tenant=tenant_a, location=loc, reason="cycle_count", status="posted",
        adjustment_date=timezone.localdate(), posted_at=timezone.now())
    StockAdjustmentLine.objects.create(adjustment=adj, item=item,
                                       quantity_delta=Decimal("1"), unit_cost=Decimal("42"))
    response = client_a.post(reverse("inventory:je_post_adjustment", args=[adj.pk]),
                             follow=True)
    assert response.status_code == 200
    assert JournalSyncLog.objects.filter(tenant=tenant_a, stock_adjustment=adj).exists()


@pytest.mark.django_db
def test_finint_je_post_cogs_window_and_overlap(client_a, tenant_a, admin_user,
                                                finint_rules, open_period):
    item = Item.objects.create(tenant=tenant_a, sku="FIN-C2", name="Cogs Widget")
    loc = Location.objects.create(tenant=tenant_a, code="FIN-B3", name="Bin",
                                  location_type="bin")
    StockMove.objects.create(tenant=tenant_a, item=item, location=loc, quantity=-Decimal("2"),
                             unit_cost=Decimal("6"), move_type="issue", moved_at=timezone.now())
    response = client_a.post(reverse("inventory:je_post_cogs"), {
        "date_from": str(timezone.localdate() - datetime.timedelta(days=7)),
        "date_to": str(timezone.localdate())}, follow=True)
    assert response.status_code == 200
    assert JournalSyncLog.objects.filter(tenant=tenant_a, source_kind="cogs_batch").count() == 1

    # overlap refused politely — no second batch
    response = client_a.post(reverse("inventory:je_post_cogs"), {
        "date_from": str(timezone.localdate() - datetime.timedelta(days=1)),
        "date_to": str(timezone.localdate())}, follow=True)
    assert JournalSyncLog.objects.filter(tenant=tenant_a, source_kind="cogs_batch").count() == 1


@pytest.fixture
def finint_item_order_delivery(db, tenant_a, admin_user):
    """A delivered outbound shipment on an uninvoiced order — the AR queue's row."""
    from apps.core.models import Party, PartyRole
    from apps.scm.models import SalesOrder, SalesOrderLine, TrackingEvent

    customer = Party.objects.create(tenant=tenant_a, kind="organization", name="Fin Buyer")
    PartyRole.objects.create(tenant=tenant_a, party=customer, role="customer",
                             status="active", start_date=timezone.localdate())
    so = SalesOrder(tenant=tenant_a, customer=customer, order_date=timezone.localdate())
    so.save()
    item = Item.objects.create(tenant=tenant_a, sku="FIN-SO1", name="Ship Widget")
    SalesOrderLine.objects.create(sales_order=so, item=item, quantity_ordered=Decimal("3"),
                                  unit_price=Decimal("15"))
    shipment = Shipment(tenant=tenant_a, direction="outbound", sales_order=so,
                        origin_text="A", destination_text="B", mode="truckload")
    shipment.save()
    ev = TrackingEvent(shipment=shipment, event_type="delivered", event_at=timezone.now(),
                       location_text="Dock", source="probe")
    ev.save()
    shipment.apply_tracking_event(ev)
    return shipment
