"""Procurement app test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b, client_a,
client_b, member_user, member_client) and adds the 6.1 User Dashboard & Portal records:
ProcurementAlert rows across every lifecycle state plus the accounting masters the quick
requisition form scopes against.
"""
import datetime

import pytest

from django.utils import timezone


# ------------------------------------------------------------------ accounting masters
@pytest.fixture
def usd(db):
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(code="USD",
                                            defaults={"name": "US Dollar", "symbol": "$"})
    return obj


@pytest.fixture
def gl_expense_a(db, tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="5000", name="Office Supplies Expense",
        account_type="expense")


@pytest.fixture
def gl_expense_b(db, tenant_b):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_b, code="5000", name="Globex Expense", account_type="expense")


@pytest.fixture
def org_unit_a(db, tenant_a):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="Acme Facilities", kind="department")


@pytest.fixture
def org_unit_b(db, tenant_b):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_b, name="Globex Facilities", kind="department")


# ------------------------------------------------------------------ alerts
def _alert(tenant, **overrides):
    from apps.procurement.models import ProcurementAlert
    fields = dict(
        tenant=tenant,
        kind="deadline", severity="critical", status="open",
        title="Printer paper reorder window closes",
        message="Submit before the supplier cut-off.",
        link_url="/procurement/quick-requisition/",
        due_at=timezone.now() + datetime.timedelta(days=2),
    )
    fields.update(overrides)
    return ProcurementAlert.objects.create(**fields)


@pytest.fixture
def alert_open(db, tenant_a, admin_user):
    return _alert(tenant_a, assigned_to=admin_user)


@pytest.fixture
def alert_acknowledged(db, tenant_a, admin_user):
    return _alert(tenant_a, assigned_to=admin_user, status="acknowledged",
                  severity="warning", kind="approval",
                  acknowledged_at=timezone.now())


@pytest.fixture
def alert_resolved(db, tenant_a):
    return _alert(tenant_a, status="resolved", severity="info", kind="task",
                  title="Quarterly stocktake closed out",
                  resolved_at=timezone.now(), resolution_note="Approved after quote arrived.")


@pytest.fixture
def alert_unassigned(db, tenant_a):
    """No assignee AND no due date - the 'team inbox' row that must not crowd dated ones."""
    return _alert(tenant_a, severity="info", kind="delivery", due_at=None)


@pytest.fixture
def alert_overdue(db, tenant_a, admin_user):
    return _alert(tenant_a, assigned_to=admin_user,
                  due_at=timezone.now() - datetime.timedelta(days=1))


@pytest.fixture
def alert_b(db, tenant_b, admin_b):
    return _alert(tenant_b, assigned_to=admin_b, title="Globex only alert")


# ------------------------------------------------------------------ 6.2 Requisition Management
from decimal import Decimal  # noqa: E402


def _pr(tenant, requester, status="draft", title="Test requisition", **overrides):
    from apps.scm.models import PurchaseRequisition

    fields = dict(
        tenant=tenant, title=title, requester=requester,
        required_by=datetime.date.today() + datetime.timedelta(days=10),
        status=status,
        justification="Needed for the smoke-free quarter.",
    )
    fields.update(overrides)
    return PurchaseRequisition.objects.create(**fields)


def _pr_line(pr, description="A4 printer paper", qty="4", price="22.50", **overrides):
    from apps.scm.models import PurchaseRequisitionLine

    fields = dict(
        requisition=pr, item_description=description,
        quantity=Decimal(qty), estimated_unit_price=Decimal(price),
    )
    fields.update(overrides)
    return PurchaseRequisitionLine.objects.create(**fields)


@pytest.fixture
def requisition_approved_a(db, tenant_a, admin_user, gl_expense_a):
    """An APPROVED spine requisition (amendable) with two lines."""
    pr = _pr(tenant_a, admin_user, status="approved",
             title="Quarterly office supplies")
    pr.approved_by = admin_user
    pr.save()
    _pr_line(pr, "A4 printer paper", "4", "22.50")
    _pr_line(pr, "Ballpoint pens blue", "2", "6.80")
    pr.recalc_totals()
    return pr


@pytest.fixture
def requisition_pending_a(db, tenant_a, admin_user):
    """A PENDING-approval spine requisition (also amendable) with one line."""
    pr = _pr(tenant_a, admin_user, status="pending_approval",
             title="Lab consumables restock")
    _pr_line(pr, "Nitrile gloves medium", "10", "8.40")
    pr.recalc_totals()
    return pr


@pytest.fixture
def template_with_lines_a(db, tenant_a, org_unit_a, gl_expense_a, admin_user):
    from apps.procurement.models import RequisitionTemplate, RequisitionTemplateLine

    template = RequisitionTemplate.objects.create(
        tenant=tenant_a, name="Monthly office supplies",
        description="Standing monthly order.", org_unit=org_unit_a,
        default_lead_days=7, justification="Recurring consumables.",
        created_by=admin_user,
    )
    RequisitionTemplateLine.objects.create(
        template=template, item_description="A4 printer paper",
        quantity=Decimal("4"), estimated_unit_price=Decimal("22.50"),
        gl_account=gl_expense_a)
    RequisitionTemplateLine.objects.create(
        template=template, item_description="Sticky notes assorted",
        quantity=Decimal("3"), estimated_unit_price=Decimal("4.20"))
    return template


@pytest.fixture
def amendment_pending_a(db, tenant_a, admin_user, requisition_approved_a):
    from apps.procurement.models import RequisitionAmendment

    return RequisitionAmendment.objects.create(
        tenant=tenant_a,
        requisition=requisition_approved_a,
        amendment_type="amend", status="pending",
        requested_by=admin_user,
        reason="Vendor moved the dispatch date.",
        new_required_by=datetime.date.today() + datetime.timedelta(days=17),
    )

# ------------------------------------------------------------------ 6.4 Vendor Management
def _supplier_party(tenant, name):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


@pytest.fixture
def supplier_a(db, tenant_a):
    """An APPROVED scm.SupplierProfile + its core.Party for tenant A -> (profile, party)."""
    from apps.scm.models import SupplierProfile
    party = _supplier_party(tenant_a, "Northwind Industrial Supply")
    profile = SupplierProfile.objects.create(
        tenant=tenant_a, party=party, onboarding_status="approved", tier="strategic",
        category="Industrial supplies")
    return profile, party


@pytest.fixture
def supplier_b(db, tenant_b):
    from apps.scm.models import SupplierProfile
    party = _supplier_party(tenant_b, "Globex Parts Co")
    profile = SupplierProfile.objects.create(
        tenant=tenant_b, party=party, onboarding_status="approved", tier="preferred")
    return profile, party


@pytest.fixture
def po_a(db, tenant_a, supplier_a):
    """An approved PO issued to supplier A's party."""
    from apps.scm.models import PurchaseOrder
    _, party = supplier_a
    return PurchaseOrder.objects.create(tenant=tenant_a, vendor=party,
                                        status="approved", order_date=timezone.localdate())


@pytest.fixture
def vpa_a(db, tenant_a, admin_user, supplier_a):
    from apps.procurement.models import VendorPortalAccess
    profile, party = supplier_a
    return VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party, portal_user=admin_user, invited_by=admin_user)


@pytest.fixture
def vsu_requested_a(db, tenant_a, member_user, supplier_a):
    from apps.procurement.models import VendorSuspension
    _, party = supplier_a
    return VendorSuspension.objects.create(
        tenant=tenant_a, supplier=party, kind="suspension", reason_category="delivery",
        reason="Late deliveries twice running.", status="requested",
        requested_by=member_user)


@pytest.fixture
def vis_submitted_a(db, tenant_a, admin_user, supplier_a, po_a):
    from apps.procurement.models import VendorInvoiceSubmission
    _, party = supplier_a
    return VendorInvoiceSubmission.objects.create(
        tenant=tenant_a, supplier=party, purchase_order=po_a,
        invoice_ref="INV-9001", amount=__import__("decimal").Decimal("120.00"),
        status="submitted", submitted_by=admin_user)


# ------------------------------------------------------------------ 6.5 Sourcing & Tendering
def _event(tenant, user, status="open", title="Test sourcing event", **overrides):
    from apps.procurement.models import SourcingEvent

    fields = dict(
        tenant=tenant, title=title, event_type="tender", status=status,
        budget_estimate=Decimal("10000.00"),
        rules="Score on cost and delivery.",
        created_by=user,
    )
    fields.update(overrides)
    return SourcingEvent.objects.create(**fields)


def _criterion(event, name="Total cost", weight="40", max_score=10):
    from apps.procurement.models import EventCriterion
    return EventCriterion.objects.create(
        event=event, name=name, weight_pct=Decimal(weight), max_score=max_score)


def _bid(event, party, status="draft", price="9000.00", **overrides):
    from apps.procurement.models import SourcingBid

    fields = dict(
        tenant=event.tenant, event=event, supplier=party,
        status=status, total_price=Decimal(price), lead_time_days=12,
        summary="Whole-package proposal.", contact_ref="bids@example.com",
    )
    fields.update(overrides)
    bid = SourcingBid.objects.create(**fields)
    if overrides.get("submitted_at") is None and status in ("submitted", "shortlisted"):
        bid.submitted_at = timezone.now()
        bid.save(update_fields=["submitted_at", "updated_at"])
    return bid


def _score(bid, criterion, value):
    from apps.procurement.models import BidScore
    return BidScore.objects.create(bid=bid, criterion=criterion, score=Decimal(value))


@pytest.fixture
def sourcing_event_open_a(db, tenant_a, admin_user):
    """An OPEN event with a 40/30/30 matrix."""
    event = _event(tenant_a, admin_user)
    _criterion(event, "Total cost", "40")
    _criterion(event, "Delivery reliability", "30")
    _criterion(event, "Quality & certifications", "30")
    return event


@pytest.fixture
def sourcing_event_closed_a(db, tenant_a, admin_user):
    """A CLOSED event (evaluation window) with the same matrix shape."""
    event = _event(tenant_a, admin_user, status="closed",
                   title="Closed frame-agreement tender")
    _criterion(event, "Total cost", "50")
    _criterion(event, "Coverage & support", "50")
    return event


@pytest.fixture
def sourcing_bid_submitted_a(sourcing_event_open_a, supplier_a):
    _, party = supplier_a
    return _bid(sourcing_event_open_a, party, status="submitted")


@pytest.fixture
def second_party_a(db, tenant_a):
    """A second organization party in tenant A (a rival bidder)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, name="Apex Packaging Co",
                                kind="organization")


@pytest.fixture
def sourcing_bid_second_a(sourcing_event_open_a, second_party_a):
    """A shortlisted rival bid on the same open event."""
    return _bid(sourcing_event_open_a, second_party_a,
                status="shortlisted", price="9800.00")


# ------------------------------------------------------------------ 6.9 Catalog Management
@pytest.fixture
def uom_a(db, tenant_a):
    from apps.scm.models import UOM
    obj, _ = UOM.objects.get_or_create(tenant=tenant_a, code="EA",
                                       defaults={"name": "Each", "factor": Decimal("1")})
    return obj


@pytest.fixture
def item_a(db, tenant_a, uom_a):
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant_a, sku="A4-PAPER", name="A4 copy paper 80gsm",
        uom=uom_a, standard_cost=Decimal("4.20"))


def _catalog_item(tenant, **overrides):
    from apps.procurement.models import CatalogItem
    fields = dict(tenant=tenant, source_type="supplier_product",
                  name="Industrial safety gloves", supplier_part_no="NW-GLOVE-D1",
                  base_price=Decimal("34.90"), status="draft")
    fields.update(overrides)
    return CatalogItem.objects.create(**fields)


@pytest.fixture
def catalog_item_approved_a(db, tenant_a, item_a, usd):
    """An APPROVED internal catalog line for tenant A (purchasable)."""
    from django.utils import timezone as tz
    ci = _catalog_item(
        tenant_a, source_type="internal", item=item_a, currency=usd,
        uom=item_a.uom, name="A4 copy paper (preferred buy)", status="approved",
        is_preferred=True)
    ci.approved_at = tz.now()
    ci.save(update_fields=["approved_at"])
    return ci


@pytest.fixture
def catalog_item_pending_a(db, tenant_a):
    """A supplier product awaiting approval in tenant A."""
    return _catalog_item(tenant_a, status="pending_approval")


@pytest.fixture
def catalog_item_blocked_a(db, tenant_a):
    return _catalog_item(tenant_a, name="Generic toner cartridge",
                         status="blocked")


@pytest.fixture
def catalog_item_b(db, tenant_b):
    """Tenant B's own catalog row - the IDOR target."""
    return _catalog_item(tenant_b, name="Globex-only catalog line")


def _tier(catalog_item, **overrides):
    from apps.procurement.models import CatalogPriceTier
    fields = dict(tenant=catalog_item.tenant, catalog_item=catalog_item,
                  min_quantity=Decimal("10"), unit_price=Decimal("31.50"),
                  status="active")
    fields.update(overrides)
    return CatalogPriceTier.objects.create(**fields)


@pytest.fixture
def tier_active_a(db, catalog_item_approved_a):
    return _tier(catalog_item_approved_a)


@pytest.fixture
def punchout_endpoint_a(db, tenant_a, supplier_a):
    from apps.procurement.models import PunchOutEndpoint
    _, party = supplier_a
    return PunchOutEndpoint.objects.create(
        tenant=tenant_a, party=party, name="Amazon Business (sandbox)",
        protocol="cxml", punchout_url="https://sandbox.example/cxml")


@pytest.fixture
def upload_batch_received_a(db, tenant_a, supplier_a):
    from apps.procurement.models import CatalogUploadBatch
    _, party = supplier_a
    return CatalogUploadBatch.objects.create(
        tenant=tenant_a, party=party, original_filename="northwind.csv",
        status="received")


# ------------------------------------------------------------------ 6.11 Order Fulfillment & Tracking
# Every fixture below is prefixed ``fulfillment_`` so the four 6.11 test lanes can share them
# without shadowing any earlier sub-module's fixture. Dates derive from timezone.localdate()
# (never date.today()) so exact-date assertions stay stable after local midnight (L16).

def _fulfillment_party(tenant, name):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _fulfillment_po(tenant, vendor, **overrides):
    """A receivable (approved) spine purchase order - the document an ASN declares against."""
    from apps.scm.models import PurchaseOrder
    fields = dict(tenant=tenant, vendor=vendor, status="approved",
                  order_date=timezone.localdate())
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _fulfillment_po_line(po, description="Bearing housing 40mm", qty="10", price="25.00",
                         **overrides):
    from apps.scm.models import PurchaseOrderLine
    fields = dict(purchase_order=po, item_description=description,
                  quantity=Decimal(qty), unit_price=Decimal(price),
                  sku_hint="BRG-40", uom_hint="EA")
    fields.update(overrides)
    return PurchaseOrderLine.objects.create(**fields)


def _fulfillment_asn(tenant, po, **overrides):
    from apps.procurement.models import AdvancedShipmentNotice
    fields = dict(tenant=tenant, purchase_order=po, source="manual", status="draft",
                  supplier_reference="", carrier_name="Northwind Express",
                  tracking_number="TRK-1001",
                  ship_date=timezone.localdate() - datetime.timedelta(days=2),
                  expected_delivery_date=timezone.localdate() + datetime.timedelta(days=3),
                  package_count=4, pallet_count=1,
                  gross_weight_kg=Decimal("120.50"), volume_cbm=Decimal("1.250"))
    fields.update(overrides)
    return AdvancedShipmentNotice.objects.create(**fields)


def _fulfillment_schedule(tenant, po_line, **overrides):
    from apps.procurement.models import DeliverySchedule
    fields = dict(tenant=tenant, po_line=po_line, sequence=1,
                  scheduled_quantity=Decimal("4"),
                  need_by_date=timezone.localdate() + datetime.timedelta(days=7),
                  status="planned", delivery_mode="standard")
    fields.update(overrides)
    return DeliverySchedule.objects.create(**fields)


def _fulfillment_backorder(tenant, po_line, **overrides):
    from apps.procurement.models import Backorder
    fields = dict(tenant=tenant, po_line=po_line,
                  quantity_backordered=Decimal("3"), reason="out_of_stock",
                  status="open",
                  revised_promise_date=timezone.localdate() + datetime.timedelta(days=3))
    fields.update(overrides)
    return Backorder.objects.create(**fields)


# -- spine documents ------------------------------------------------------------------------

@pytest.fixture
def fulfillment_vendor_a(db, tenant_a):
    return _fulfillment_party(tenant_a, "Northwind Forge Ltd")


@pytest.fixture
def fulfillment_vendor_b(db, tenant_b):
    return _fulfillment_party(tenant_b, "Globex Freight Partners")


@pytest.fixture
def fulfillment_po_a(db, tenant_a, fulfillment_vendor_a):
    """Approved tenant-A PO with TWO lines (10 bearings, 4 belts); totals recalculated."""
    po = _fulfillment_po(tenant_a, fulfillment_vendor_a)
    _fulfillment_po_line(po)
    _fulfillment_po_line(po, description="Drive belt 1200mm", qty="4", price="60.00",
                         sku_hint="BLT-1200")
    po.recalc_totals()
    return po


@pytest.fixture
def fulfillment_po_line_a(fulfillment_po_a):
    """First line of ``fulfillment_po_a`` - quantity 10."""
    return fulfillment_po_a.lines.order_by("id").first()


@pytest.fixture
def fulfillment_po_line2_a(fulfillment_po_a):
    """Second line of ``fulfillment_po_a`` - quantity 4."""
    return fulfillment_po_a.lines.order_by("id").last()


@pytest.fixture
def fulfillment_po_b(db, tenant_b, fulfillment_vendor_b):
    """Tenant-B PO with one line - the cross-tenant target for crafted-POST tests."""
    po = _fulfillment_po(tenant_b, fulfillment_vendor_b)
    _fulfillment_po_line(po, description="Globex-only spindle", qty="6", price="80.00",
                         sku_hint="GBX-SPN")
    po.recalc_totals()
    return po


@pytest.fixture
def fulfillment_po_line_b(fulfillment_po_b):
    return fulfillment_po_b.lines.order_by("id").first()


@pytest.fixture
def fulfillment_carrier_a(db, tenant_a):
    from apps.scm.models import Carrier
    party = _fulfillment_party(tenant_a, "Acme Road Freight")
    return Carrier.objects.create(tenant=tenant_a, party=party, carrier_type="asset_based",
                                  primary_mode="truckload", status="active")


@pytest.fixture
def fulfillment_carrier_b(db, tenant_b):
    from apps.scm.models import Carrier
    party = _fulfillment_party(tenant_b, "Globex Haulage")
    return Carrier.objects.create(tenant=tenant_b, party=party, status="active")


@pytest.fixture
def fulfillment_shipment_inbound_a(db, tenant_a, fulfillment_po_a, fulfillment_carrier_a):
    """An INBOUND SCM 4.6 shipment carrying the live tracking projections an ASN reads."""
    from apps.scm.models import Shipment
    return Shipment.objects.create(
        tenant=tenant_a, direction="inbound", carrier=fulfillment_carrier_a,
        purchase_order=fulfillment_po_a, mode="truckload",
        current_status_text="In Transit", last_known_location="Rotterdam hub",
        eta=timezone.now() + datetime.timedelta(days=2))


@pytest.fixture
def fulfillment_shipment_outbound_a(db, tenant_a):
    """OUTBOUND - an ASN must refuse it (``AdvancedShipmentNotice.clean()``)."""
    from apps.scm.models import Shipment
    return Shipment.objects.create(tenant=tenant_a, direction="outbound")


@pytest.fixture
def fulfillment_shipment_inbound_b(db, tenant_b):
    from apps.scm.models import Shipment
    return Shipment.objects.create(tenant=tenant_b, direction="inbound")


# -- advance shipping notices ---------------------------------------------------------------

@pytest.fixture
def fulfillment_asn_draft_a(db, tenant_a, admin_user, fulfillment_po_a):
    return _fulfillment_asn(tenant_a, fulfillment_po_a, supplier_reference="NW-DN-1001",
                            created_by=admin_user)


@pytest.fixture
def fulfillment_asn_line_a(db, fulfillment_asn_draft_a, fulfillment_po_line_a):
    """Exactly-on-the-balance declaration (10 shipped against 10 outstanding)."""
    from apps.procurement.models import AsnLine
    return AsnLine.objects.create(asn=fulfillment_asn_draft_a, po_line=fulfillment_po_line_a,
                                  quantity_shipped=Decimal("10"), package_ref="PLT-1",
                                  lot_number="LOT-77", country_of_origin="DE")


@pytest.fixture
def fulfillment_asn_in_transit_a(db, tenant_a, admin_user, fulfillment_po_a):
    """In flight and due TOMORROW - the delivery-confirmation board's 'awaiting' row."""
    return _fulfillment_asn(
        tenant_a, fulfillment_po_a, status="in_transit", supplier_reference="NW-DN-2002",
        submitted_at=timezone.now(), created_by=admin_user,
        expected_delivery_date=timezone.localdate() + datetime.timedelta(days=1))


@pytest.fixture
def fulfillment_asn_late_a(db, tenant_a, admin_user, fulfillment_po_a):
    """In flight and THREE DAYS overdue - drives is_late / days_late / ?late=1 / the overdue tab."""
    return _fulfillment_asn(
        tenant_a, fulfillment_po_a, status="in_transit", supplier_reference="NW-DN-2003",
        submitted_at=timezone.now(), created_by=admin_user, tracking_number="TRK-2003",
        expected_delivery_date=timezone.localdate() - datetime.timedelta(days=3))


@pytest.fixture
def fulfillment_asn_delivered_a(db, tenant_a, admin_user, fulfillment_po_a):
    """Closed record with its proof-of-delivery block already stamped."""
    return _fulfillment_asn(
        tenant_a, fulfillment_po_a, status="delivered", supplier_reference="NW-DN-3004",
        submitted_at=timezone.now(), created_by=admin_user,
        expected_delivery_date=timezone.localdate() - datetime.timedelta(days=1),
        delivered_at=timezone.now(), arrival_condition="good", pod_reference="POD-3004",
        received_signature_name="R. Keeper", confirmed_by=admin_user)


@pytest.fixture
def fulfillment_asn_b(db, tenant_b, admin_b, fulfillment_po_b):
    """Tenant B's own ASN - the IDOR target for detail/edit/delete/verb probes."""
    return _fulfillment_asn(tenant_b, fulfillment_po_b, supplier_reference="GBX-DN-9001",
                            carrier_name="Globex Haulage", created_by=admin_b)


# -- split-delivery instalments -------------------------------------------------------------

@pytest.fixture
def fulfillment_schedule_a(db, tenant_a, admin_user, fulfillment_po_line_a):
    """Instalment 1 of 10 ordered - 4 units due in a week (the line stays under-covered)."""
    return _fulfillment_schedule(tenant_a, fulfillment_po_line_a, created_by=admin_user)


@pytest.fixture
def fulfillment_schedule_late_a(db, tenant_a, admin_user, fulfillment_po_line_a):
    """Instalment 2 - 3 units whose need-by date has already passed (is_late)."""
    return _fulfillment_schedule(
        tenant_a, fulfillment_po_line_a, sequence=2, scheduled_quantity=Decimal("3"),
        need_by_date=timezone.localdate() - datetime.timedelta(days=2),
        promised_date=timezone.localdate() + datetime.timedelta(days=4),
        delivery_mode="express", created_by=admin_user)


@pytest.fixture
def fulfillment_schedule_b(db, tenant_b, fulfillment_po_line_b):
    return _fulfillment_schedule(tenant_b, fulfillment_po_line_b,
                                 scheduled_quantity=Decimal("2"))


# -- backorders -----------------------------------------------------------------------------

@pytest.fixture
def fulfillment_backorder_open_a(db, tenant_a, admin_user, fulfillment_po_line_a):
    """Open, promised in three days -> risk bucket ``at_risk``."""
    return _fulfillment_backorder(tenant_a, fulfillment_po_line_a, created_by=admin_user)


@pytest.fixture
def fulfillment_backorder_past_due_a(db, tenant_a, admin_user, fulfillment_po_line2_a):
    """Open with a promise two days in the past -> risk bucket ``past_due``."""
    return _fulfillment_backorder(
        tenant_a, fulfillment_po_line2_a, quantity_backordered=Decimal("2"),
        reason="production_delay", created_by=admin_user,
        original_promise_date=timezone.localdate() - datetime.timedelta(days=9),
        revised_promise_date=timezone.localdate() - datetime.timedelta(days=2))


@pytest.fixture
def fulfillment_backorder_closed_a(db, tenant_a, admin_user, fulfillment_po_line_a):
    """Fulfilled - frozen: edit is refused and every verb no-ops."""
    return _fulfillment_backorder(
        tenant_a, fulfillment_po_line_a, quantity_backordered=Decimal("1"),
        status="fulfilled", closed_at=timezone.now(), closure_note="Arrived on the 14th.",
        created_by=admin_user)


@pytest.fixture
def fulfillment_backorder_b(db, tenant_b, fulfillment_po_line_b):
    """Tenant B's shortfall - the IDOR target."""
    return _fulfillment_backorder(tenant_b, fulfillment_po_line_b,
                                  quantity_backordered=Decimal("2"),
                                  reason="logistics")


# ------------------------------------------------------------------ 6.12 Goods Receipt & Inspection
# Every fixture below is prefixed ``receipt_`` so the four 6.12 test lanes can share them without
# shadowing any earlier sub-module's fixture. Dates derive from timezone.localdate() (never
# date.today()) so exact-date assertions stay stable after local midnight (L16).
#
# Shape of the tenant-A spine these build (all dates relative to ``timezone.localdate()``):
#
#   receipt_po_a            order_date = today, expected_date = today, status "approved"
#     line 1 (receipt_po_line_a)   qty 10  @ 25.00  sku "BRG-40"
#     line 2 (receipt_po_line2_a)  qty  4  @ 60.00  sku "BLT-1200"
#   receipt_grn_a           receipt_date = today,     DN "DN-5001", draft
#     receipt_grn_line_a          po_line 1, received 12, rejected 1  -> OVER  bucket
#     receipt_grn_line2_a         po_line 2, received  1              -> SHORT bucket
#   receipt_grn_early_a     receipt_date = today - 4, DN "DN-5002"    -> EARLY bucket
#   receipt_grn_late_a      receipt_date = today + 4, DN "DN-5003"    -> LATE  bucket
#   receipt_grn_cancelled_a receipt_date = today,     DN "DN-5004", status "cancelled"

def _receipt_party(tenant, name, role="supplier"):
    """A counterparty WITH its PartyRole - every 6.12 vendor dropdown narrows on
    ``roles__role__in=("supplier", "vendor")``, so a Party with no role is invisible to the forms
    and to every ``?vendor=`` filter widget."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


def _receipt_po(tenant, vendor, **overrides):
    """An approved spine purchase order - the document a receipt is booked against."""
    from apps.scm.models import PurchaseOrder
    fields = dict(tenant=tenant, vendor=vendor, status="approved",
                  order_date=timezone.localdate(), expected_date=timezone.localdate())
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _receipt_po_line(po, description="Bearing housing 40mm", qty="10", price="25.00",
                     **overrides):
    from apps.scm.models import PurchaseOrderLine
    fields = dict(purchase_order=po, item_description=description,
                  quantity=Decimal(qty), unit_price=Decimal(price),
                  sku_hint="BRG-40", uom_hint="EA")
    fields.update(overrides)
    return PurchaseOrderLine.objects.create(**fields)


def _receipt_grn(tenant, po, **overrides):
    from apps.scm.models import GoodsReceiptNote
    fields = dict(tenant=tenant, purchase_order=po, receipt_date=timezone.localdate(),
                  status="draft", delivery_note_ref="DN-5001")
    fields.update(overrides)
    return GoodsReceiptNote.objects.create(**fields)


def _receipt_grn_line(grn, po_line, received="0", **overrides):
    from apps.scm.models import GoodsReceiptLine
    fields = dict(goods_receipt=grn, po_line=po_line, quantity_received=Decimal(received))
    fields.update(overrides)
    return GoodsReceiptLine.objects.create(**fields)


def _receipt_policy(tenant, name="Workspace 5% band", **overrides):
    from apps.procurement.models import ReceiptTolerancePolicy
    fields = dict(tenant=tenant, name=name, over_receipt_pct=Decimal("5"),
                  under_receipt_pct=Decimal("10"), early_receipt_days=2, late_receipt_days=3,
                  action="warn", priority=10, is_active=True)
    fields.update(overrides)
    return ReceiptTolerancePolicy.objects.create(**fields)


def _receipt_discrepancy(tenant, grn, **overrides):
    from apps.procurement.models import ReceiptDiscrepancy
    fields = dict(tenant=tenant, goods_receipt=grn, kind="short_shipment", severity="major",
                  quantity_affected=Decimal("2"),
                  description="Three cartons short on the pallet.")
    fields.update(overrides)
    return ReceiptDiscrepancy.objects.create(**fields)


def _receipt_rtv(tenant, vendor, **overrides):
    from apps.procurement.models import ReturnToVendor
    fields = dict(tenant=tenant, vendor=vendor, reason="damaged", remedy="credit",
                  supplier_rma_number="RMA-77")
    fields.update(overrides)
    return ReturnToVendor.objects.create(**fields)


def _receipt_rtv_line(rtv, po_line=None, qty="3", **overrides):
    from apps.procurement.models import ReturnToVendorLine
    fields = dict(return_to_vendor=rtv, po_line=po_line, quantity_returned=Decimal(qty))
    fields.update(overrides)
    return ReturnToVendorLine.objects.create(**fields)


def _receipt_asn(tenant, po, **overrides):
    from apps.procurement.models import AdvancedShipmentNotice
    fields = dict(tenant=tenant, purchase_order=po, source="manual", status="in_transit",
                  supplier_reference="NW-DN-7001", carrier_name="Northwind Express",
                  tracking_number="TRK-7001",
                  ship_date=timezone.localdate() - datetime.timedelta(days=1),
                  expected_delivery_date=timezone.localdate())
    fields.update(overrides)
    return AdvancedShipmentNotice.objects.create(**fields)


# -- counterparties, item master and locations ------------------------------------------------

@pytest.fixture
def receipt_vendor_a(db, tenant_a):
    """Tenant A supplier, WITH the ``supplier`` PartyRole every 6.12 dropdown filters on."""
    return _receipt_party(tenant_a, "Northwind Forge Ltd")


@pytest.fixture
def receipt_vendor_b(db, tenant_b):
    return _receipt_party(tenant_b, "Globex Freight Partners")


@pytest.fixture
def receipt_vendor_other_a(db, tenant_a):
    """A SECOND tenant-A supplier - the counterparty-mismatch target (returning goods to a
    supplier other than the one the order was placed with must be refused even though both rows
    live in this workspace)."""
    return _receipt_party(tenant_a, "Southgate Bearings")


@pytest.fixture
def receipt_category_a(db, tenant_a):
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant_a, name="Bearings")


@pytest.fixture
def receipt_category_b(db, tenant_b):
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant_b, name="Globex Spares")


@pytest.fixture
def receipt_item_a(db, tenant_a, receipt_category_a):
    """SKU ``BRG-40`` - matches ``receipt_po_line_a.sku_hint``, so ``resolve_line_item`` finds it."""
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_a, sku="BRG-40", name="Bearing housing 40mm",
                               category=receipt_category_a, item_type="stock")


@pytest.fixture
def receipt_item_b(db, tenant_b, receipt_category_b):
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_b, sku="GBX-SPN", name="Globex spindle",
                               category=receipt_category_b, item_type="stock")


@pytest.fixture
def receipt_location_a(db, tenant_a):
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_a, code="DOCK-A", name="Receiving dock",
                                   location_type="staging", is_active=True)


@pytest.fixture
def receipt_location_b(db, tenant_b):
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_b, code="DOCK-B", name="Globex dock",
                                   location_type="staging", is_active=True)


# -- spine: purchase orders --------------------------------------------------------------------

@pytest.fixture
def receipt_po_a(db, tenant_a, receipt_vendor_a):
    """Approved tenant-A PO, ``expected_date`` = TODAY, with TWO lines (10 bearings, 4 belts)."""
    po = _receipt_po(tenant_a, receipt_vendor_a)
    _receipt_po_line(po)
    _receipt_po_line(po, description="Drive belt 1200mm", qty="4", price="60.00",
                     sku_hint="BLT-1200")
    po.recalc_totals()
    return po


@pytest.fixture
def receipt_po_line_a(receipt_po_a):
    """First line of ``receipt_po_a`` - quantity 10, sku BRG-40, unit price 25.00."""
    return receipt_po_a.lines.order_by("id").first()


@pytest.fixture
def receipt_po_line2_a(receipt_po_a):
    """Second line of ``receipt_po_a`` - quantity 4, sku BLT-1200, unit price 60.00."""
    return receipt_po_a.lines.order_by("id").last()


@pytest.fixture
def receipt_po_b(db, tenant_b, receipt_vendor_b):
    """Tenant-B PO with one line - the cross-tenant target for crafted-POST tests."""
    po = _receipt_po(tenant_b, receipt_vendor_b)
    _receipt_po_line(po, description="Globex-only spindle", qty="6", price="80.00",
                     sku_hint="GBX-SPN")
    po.recalc_totals()
    return po


@pytest.fixture
def receipt_po_line_b(receipt_po_b):
    return receipt_po_b.lines.order_by("id").first()


# -- spine: goods receipts ---------------------------------------------------------------------

@pytest.fixture
def receipt_grn_a(db, tenant_a, admin_user, receipt_po_a, receipt_location_a):
    """Draft receipt dated TODAY, delivery note ``DN-5001``, landed in the receiving dock."""
    return _receipt_grn(tenant_a, receipt_po_a, location=receipt_location_a,
                        received_by=admin_user, notes="Two pallets, one shrink-wrap torn.")


@pytest.fixture
def receipt_grn_line_a(db, receipt_grn_a, receipt_po_line_a):
    """12 accepted against 10 ordered (+1 rejected) - the OVER-receipt exception row."""
    return _receipt_grn_line(receipt_grn_a, receipt_po_line_a, received="12",
                             quantity_rejected=Decimal("1"),
                             rejection_reason="Crushed carton")


@pytest.fixture
def receipt_grn_line2_a(db, receipt_grn_a, receipt_po_line2_a):
    """1 accepted against 4 ordered - the SHORT-receipt exception row."""
    return _receipt_grn_line(receipt_grn_a, receipt_po_line2_a, received="1")


@pytest.fixture
def receipt_grn_early_a(db, tenant_a, receipt_po_a, receipt_po_line_a):
    """Receipt dated FOUR DAYS BEFORE the order's expected date - the EARLY bucket row."""
    grn = _receipt_grn(tenant_a, receipt_po_a, delivery_note_ref="DN-5002",
                       receipt_date=timezone.localdate() - datetime.timedelta(days=4))
    _receipt_grn_line(grn, receipt_po_line_a, received="0")
    return grn


@pytest.fixture
def receipt_grn_late_a(db, tenant_a, receipt_po_a, receipt_po_line2_a):
    """Receipt dated FOUR DAYS AFTER the order's expected date - the LATE bucket row."""
    grn = _receipt_grn(tenant_a, receipt_po_a, delivery_note_ref="DN-5003",
                       receipt_date=timezone.localdate() + datetime.timedelta(days=4))
    _receipt_grn_line(grn, receipt_po_line2_a, received="1")
    return grn


@pytest.fixture
def receipt_grn_cancelled_a(db, tenant_a, receipt_po_a, receipt_po_line_a):
    """A cancelled receipt - every 6.12 board and queryset must EXCLUDE it."""
    grn = _receipt_grn(tenant_a, receipt_po_a, delivery_note_ref="DN-5004", status="cancelled")
    _receipt_grn_line(grn, receipt_po_line_a, received="5")
    return grn


@pytest.fixture
def receipt_grn_b(db, tenant_b, receipt_po_b):
    """Tenant B's receipt - the IDOR / crafted-FK target."""
    return _receipt_grn(tenant_b, receipt_po_b, delivery_note_ref="GBX-DN-9001")


@pytest.fixture
def receipt_grn_line_b(db, receipt_grn_b, receipt_po_line_b):
    return _receipt_grn_line(receipt_grn_b, receipt_po_line_b, received="6")


# -- tolerance policies ------------------------------------------------------------------------

@pytest.fixture
def receipt_policy_catchall_a(db, tenant_a):
    """Catch-all: 5% over / 10% under / 2 days early / 3 days late, action ``warn``, priority 10."""
    return _receipt_policy(tenant_a)


@pytest.fixture
def receipt_policy_item_a(db, tenant_a, receipt_item_a):
    """Item-pinned (tier 3), priority 5 - beats the catch-all for SKU BRG-40, zero over-tolerance."""
    return _receipt_policy(tenant_a, name="BRG-40 strict", item=receipt_item_a,
                           over_receipt_pct=Decimal("0"), under_receipt_pct=None,
                           early_receipt_days=None, late_receipt_days=None,
                           action="block_flag", priority=5)


@pytest.fixture
def receipt_policy_category_a(db, tenant_a, receipt_category_a):
    """Category-pinned (tier 2), priority 7 - beats the catch-all, loses to the item rule."""
    return _receipt_policy(tenant_a, name="Bearings band", category=receipt_category_a,
                           over_receipt_pct=Decimal("15"), priority=7)


@pytest.fixture
def receipt_policy_vendor_a(db, tenant_a, receipt_vendor_a):
    """Vendor-pinned catch-all - same tier as ``receipt_policy_catchall_a``, but more specific."""
    return _receipt_policy(tenant_a, name="Northwind exception", vendor=receipt_vendor_a,
                           over_receipt_qty=Decimal("2"), priority=10)


@pytest.fixture
def receipt_policy_inactive_a(db, tenant_a):
    """Highest priority but INACTIVE - the resolver must never return it."""
    return _receipt_policy(tenant_a, name="Retired band", is_active=False, priority=1,
                           allow_unlimited_over_receipt=True)


@pytest.fixture
def receipt_policy_b(db, tenant_b):
    """Tenant B's rule - the IDOR target for detail / edit / delete."""
    return _receipt_policy(tenant_b, name="Globex band")


# -- discrepancies -----------------------------------------------------------------------------

@pytest.fixture
def receipt_discrepancy_open_a(db, tenant_a, admin_user, receipt_grn_a, receipt_grn_line2_a):
    """OPEN short-shipment finding pinned to the short receipt line."""
    return _receipt_discrepancy(tenant_a, receipt_grn_a,
                                goods_receipt_line=receipt_grn_line2_a,
                                created_by=admin_user)


@pytest.fixture
def receipt_discrepancy_header_a(db, tenant_a, receipt_grn_a):
    """HEADER-level finding (no receipt line) - the paperwork never arrived."""
    return _receipt_discrepancy(tenant_a, receipt_grn_a, kind="documentation",
                                severity="minor", quantity_affected=Decimal("0"),
                                description="No packing list with the delivery.")


@pytest.fixture
def receipt_discrepancy_notified_a(db, tenant_a, receipt_grn_a):
    """Already VENDOR_NOTIFIED - notify_vendor must no-op; resolve / cancel must still work."""
    obj = _receipt_discrepancy(tenant_a, receipt_grn_a, kind="damaged",
                               quantity_affected=Decimal("1"),
                               description="Two cartons crushed in transit.")
    obj.notify_vendor(None, reference="SUP-CASE-11",
                      notified_on=timezone.localdate() - datetime.timedelta(days=1))
    return obj


@pytest.fixture
def receipt_discrepancy_resolved_a(db, tenant_a, admin_user, receipt_grn_a):
    """RESOLVED and therefore FROZEN - edit is refused and every verb no-ops."""
    obj = _receipt_discrepancy(tenant_a, receipt_grn_a, kind="wrong_item",
                               quantity_affected=Decimal("3"),
                               description="Belts sent instead of bearings.")
    obj.resolve(admin_user, "credit", "Credit note agreed with the supplier.")
    return obj


@pytest.fixture
def receipt_discrepancy_b(db, tenant_b, receipt_grn_b):
    """Tenant B's finding - the IDOR / crafted-FK target."""
    return _receipt_discrepancy(tenant_b, receipt_grn_b, description="Globex-only finding.")


# -- returns to vendor -------------------------------------------------------------------------

@pytest.fixture
def receipt_rtv_draft_a(db, tenant_a, admin_user, receipt_vendor_a, receipt_po_a, receipt_grn_a):
    """DRAFT return - editable, deletable, authorizable, cancellable."""
    return _receipt_rtv(tenant_a, receipt_vendor_a, purchase_order=receipt_po_a,
                        goods_receipt=receipt_grn_a, created_by=admin_user,
                        notes="Two crushed cartons going back.")


@pytest.fixture
def receipt_rtv_line_a(db, receipt_rtv_draft_a, receipt_po_line_a):
    """One returned line priced through ``po_line.unit_price`` (3 x 25.00 = 75.00 expected)."""
    return _receipt_rtv_line(receipt_rtv_draft_a, po_line=receipt_po_line_a, qty="3")


@pytest.fixture
def receipt_rtv_authorized_a(db, tenant_a, admin_user, receipt_vendor_a):
    """AUTHORIZED - shippable and cancellable, no longer editable or deletable."""
    obj = _receipt_rtv(tenant_a, receipt_vendor_a, reason="defective", remedy="replacement",
                       supplier_rma_number="RMA-88", created_by=admin_user)
    obj.authorize(admin_user)
    return obj


@pytest.fixture
def receipt_rtv_shipped_a(db, tenant_a, admin_user, receipt_vendor_a):
    """SHIPPED - closable only; cancel must be refused (the goods have physically gone)."""
    obj = _receipt_rtv(tenant_a, receipt_vendor_a, reason="expired", remedy="credit",
                       supplier_rma_number="RMA-99", created_by=admin_user)
    obj.authorize(admin_user)
    obj.mark_shipped(admin_user, carrier_name="DHL", tracking_number="TRK-RTV-1",
                     shipped_on=timezone.localdate() - datetime.timedelta(days=1))
    return obj


@pytest.fixture
def receipt_rtv_b(db, tenant_b, admin_b, receipt_vendor_b):
    """Tenant B's return - the IDOR / crafted-FK target."""
    return _receipt_rtv(tenant_b, receipt_vendor_b, reason="wrong_item",
                        supplier_rma_number="GBX-RMA-1", created_by=admin_b)


# -- advance shipping notices (the receiving console's rows) -----------------------------------

@pytest.fixture
def receipt_asn_a(db, tenant_a, admin_user, receipt_po_a):
    """IN TRANSIT and due TODAY - the console's ``?arrival=today`` row. Not yet booked."""
    return _receipt_asn(tenant_a, receipt_po_a, submitted_at=timezone.now(),
                        created_by=admin_user)


@pytest.fixture
def receipt_asn_line_a(db, receipt_asn_a, receipt_po_line_a):
    """5 declared against the 10-unit line, carrying a lot number the mint verb can adopt."""
    from apps.procurement.models import AsnLine
    return AsnLine.objects.create(asn=receipt_asn_a, po_line=receipt_po_line_a,
                                  quantity_shipped=Decimal("5"), package_ref="PLT-1",
                                  sku_hint="BRG-40", lot_number="LOT-A1",
                                  country_of_origin="DE")


@pytest.fixture
def receipt_asn_no_reference_a(db, tenant_a, receipt_po_a, receipt_po_line2_a):
    """Declares NO supplier reference - the book verb must key on the ASN number instead.
    Expected two days ago, so it also fills the console's ``?arrival=overdue`` tab."""
    from apps.procurement.models import AsnLine
    asn = _receipt_asn(tenant_a, receipt_po_a, supplier_reference="",
                       tracking_number="TRK-7002",
                       expected_delivery_date=timezone.localdate() - datetime.timedelta(days=2))
    AsnLine.objects.create(asn=asn, po_line=receipt_po_line2_a,
                           quantity_shipped=Decimal("2"), sku_hint="BLT-1200")
    return asn


@pytest.fixture
def receipt_asn_draft_a(db, tenant_a, receipt_po_a):
    """DRAFT - outside ``CONSOLE_STATUSES``, so the console must neither list nor book it."""
    return _receipt_asn(tenant_a, receipt_po_a, status="draft",
                        supplier_reference="NW-DN-7003", tracking_number="TRK-7003")


@pytest.fixture
def receipt_asn_b(db, tenant_b, admin_b, receipt_po_b):
    """Tenant B's shipment - the IDOR target for the console's two POST verbs."""
    return _receipt_asn(tenant_b, receipt_po_b, supplier_reference="GBX-DN-9001",
                        carrier_name="Globex Haulage", created_by=admin_b)


# -- the registers a discrepancy POINTS at (and never re-declares, L36) ------------------------

@pytest.fixture
def receipt_nonconformance_a(db, tenant_a, receipt_grn_a, receipt_item_a):
    from apps.scm.models import NonConformance
    return NonConformance.objects.create(
        tenant=tenant_a, source="receiving", goods_receipt=receipt_grn_a, item=receipt_item_a,
        title="Bearing bore out of spec", description="Bore measured 0.4mm oversize.",
        detected_on=timezone.localdate())


@pytest.fixture
def receipt_nonconformance_b(db, tenant_b, receipt_item_b):
    """Tenant B's quality record - the crafted-FK target on the discrepancy form."""
    from apps.scm.models import NonConformance
    return NonConformance.objects.create(
        tenant=tenant_b, source="receiving", item=receipt_item_b,
        title="Globex-only finding", description="Not ours.",
        detected_on=timezone.localdate())


@pytest.fixture
def receipt_quarantine_a(db, tenant_a, receipt_item_a, receipt_location_a):
    from apps.inventory.models import QuarantineOrder
    return QuarantineOrder.objects.create(
        tenant=tenant_a, item=receipt_item_a, source_location=receipt_location_a,
        quarantine_location=receipt_location_a, quantity=Decimal("2"), reason="qc_hold")


@pytest.fixture
def receipt_quarantine_b(db, tenant_b, receipt_item_b, receipt_location_b):
    """Tenant B's hold - the crafted-FK target on the discrepancy form."""
    from apps.inventory.models import QuarantineOrder
    return QuarantineOrder.objects.create(
        tenant=tenant_b, item=receipt_item_b, source_location=receipt_location_b,
        quarantine_location=receipt_location_b, quantity=Decimal("1"), reason="qc_hold")
