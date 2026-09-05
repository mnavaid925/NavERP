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


# =================================================================================================
# 6.14 Spend Analytics & Reporting
# =================================================================================================
#
# Every fixture below is prefixed ``spend_`` so the four 6.14 test lanes never collide with the
# 6.1 / 6.4 / 6.9 / 6.11 / 6.12 records above (or with whatever 6.15 appends next).
#
# The shape the lanes can rely on, all dated off ``timezone.localdate()`` so they sit inside the
# default ``last_90`` window every 6.14 page uses (L16 - never ``date.today()``):
#
#   spend_vendor_a         core.Party "Meridian Office Supplies" + supplier PartyRole
#   spend_vendor_other_a   core.Party "Cobalt Facilities Group"  + supplier PartyRole
#   spend_vendor_b         tenant-B supplier - the crafted-FK / IDOR target
#   spend_category_a       scm.ItemCategory "Office Supplies"    (spend_item_a hangs off it)
#   spend_category_other_a scm.ItemCategory "Facilities"
#   spend_category_b       tenant-B category
#   spend_item_a           scm.Item "PPR-A4" in spend_category_a (the invoiced category passthrough)
#
#   spend_invoice_a        SupplierInvoice, status "approved", invoice_date = TODAY -> RECOGNISED
#     spend_invoice_line_a       qty 10 @ 25.00 -> line_total 250.00, sku "PPR-A4", gl_expense_a
#   spend_invoice_draft_a  SupplierInvoice, status "draft"      -> NOT recognised spend
#   spend_invoice_b / spend_invoice_line_b   tenant-B twin
#
#   spend_po_a             scm.PurchaseOrder, status "approved", order_date = TODAY -> COMMITTED
#     spend_po_line_a            qty 4 @ 60.00 -> line_total 240.00, sku "TNR-55"
#   spend_po_b / spend_po_line_b             tenant-B twin
#
#   spend_rule_vendor_a    priority 10, match_type "vendor"  -> spend_category_a
#   spend_rule_keyword_a   priority 50, match_type "keyword" ("toner") -> spend_category_other_a
#   spend_rule_inactive_a  is_active False, match_type "gl_account"
#   spend_rule_b           tenant-B rule - the IDOR target
#
#   spend_finding_open_a       "no_contract",          open,         on spend_invoice_a
#   spend_finding_ack_a        "po_less_invoice",      acknowledged, on spend_invoice_a
#   spend_finding_leakage_a    "price_above_contract", open, high, amount 250 / benchmark 200
#   spend_finding_dismissed_a  "off_catalog",          dismissed (terminal), on spend_po_a
#   spend_finding_b            tenant-B finding - the IDOR target
#
#   spend_report_a         shared, owner admin_user, measure net_spend / dimension_1 supplier
#   spend_report_private_a is_shared False, owner MEMBER_user -> a 404 for client_a everywhere
#   spend_report_b         tenant-B report - the IDOR target
#   spend_snapshot_a / spend_snapshot_b   frozen runs of the two reports above
#
#   spend_contract_a / spend_contract_b   scm.SupplierContract (finding FK + form dropdown)
#   spend_catalog_item_a                  approved + preferred CatalogItem (the alternatives panel)

def _spend_party(tenant, name, role="supplier"):
    """A counterparty WITH its PartyRole - every 6.14 supplier dropdown and filter narrows on
    ``roles__role__in=("supplier", "vendor")``, so a Party with no role is invisible to the forms
    and to every ``?vendor=`` widget."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


def _spend_invoice(tenant, vendor, **overrides):
    """A SupplierInvoice (6.13 owns the table). ``status="approved"`` is RECOGNISED spend -
    ``RECOGNISED_INVOICE_STATUSES`` is ("approved", "scheduled", "paid")."""
    from apps.procurement.models import SupplierInvoice
    fields = dict(tenant=tenant, vendor=vendor, invoice_number="SUP-4400",
                  invoice_date=timezone.localdate(), status="approved",
                  invoice_type="standard")
    fields.update(overrides)
    return SupplierInvoice.objects.create(**fields)


def _spend_invoice_line(invoice, **overrides):
    """One invoice line. ``line_total`` is DERIVED in save() (qty * unit_price) and the header's
    money follows it - never pass ``line_total``."""
    from apps.procurement.models import SupplierInvoiceLine
    fields = dict(invoice=invoice, description="A4 copy paper 80gsm", sku_hint="PPR-A4",
                  quantity=Decimal("10"), unit_price=Decimal("25.00"))
    fields.update(overrides)
    return SupplierInvoiceLine.objects.create(**fields)


def _spend_po(tenant, vendor, **overrides):
    """A committed-basis purchase order - ``SPEND_PO_STATUSES`` includes "approved"."""
    from apps.scm.models import PurchaseOrder
    fields = dict(tenant=tenant, vendor=vendor, status="approved",
                  order_date=timezone.localdate())
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _spend_po_line(po, **overrides):
    from apps.scm.models import PurchaseOrderLine
    fields = dict(purchase_order=po, item_description="Toner cartridge 55A",
                  sku_hint="TNR-55", uom_hint="EA",
                  quantity=Decimal("4"), unit_price=Decimal("60.00"))
    fields.update(overrides)
    return PurchaseOrderLine.objects.create(**fields)


def _spend_rule(tenant, category, **overrides):
    from apps.procurement.models import SpendClassificationRule
    fields = dict(tenant=tenant, name="Meridian -> Office Supplies", match_type="vendor",
                  category=category, priority=10, applies_to="both", is_active=True)
    fields.update(overrides)
    return SpendClassificationRule.objects.create(**fields)


def _spend_finding(tenant, vendor, **overrides):
    """A MaverickSpendFinding. ``dedupe_key`` and ``leakage_amount`` are DERIVED in save() -
    never pass either, and vary ``reason`` / the source pointer across fixtures because
    ``unique_together`` includes ``(tenant, dedupe_key)``."""
    from apps.procurement.models import MaverickSpendFinding
    fields = dict(tenant=tenant, vendor=vendor, reason="no_contract", severity="medium",
                  document_date=timezone.localdate(), amount=Decimal("250.00"),
                  detail="No active contract covered this purchase.")
    fields.update(overrides)
    return MaverickSpendFinding.objects.create(**fields)


def _spend_report(tenant, **overrides):
    from apps.procurement.models import SpendReport
    fields = dict(tenant=tenant, name="Top suppliers, last 90 days", basis="invoiced",
                  measure="net_spend", dimension_1="supplier", dimension_2="none",
                  date_range="last_90", chart_type="bar", top_n=20,
                  is_favorite=False, is_shared=True)
    fields.update(overrides)
    return SpendReport.objects.create(**fields)


def _spend_snapshot(tenant, report, **overrides):
    from apps.procurement.models import SpendReportSnapshot
    fields = dict(
        tenant=tenant, report=report, title="Top suppliers - frozen run",
        summary=[{"label": "Net spend", "value": "250.00"}],
        data={"columns": ["Supplier", "Net spend", "Share", "Lines"],
              "rows": [["Meridian Office Supplies", "250.00", "100.0%", "1"]],
              "chart_type": "bar",
              "chart_labels": ["Meridian Office Supplies"],
              "chart_data": [250.0]},
        row_count=1)
    fields.update(overrides)
    return SpendReportSnapshot.objects.create(**fields)


# -- masters -------------------------------------------------------------------------------------

@pytest.fixture
def spend_vendor_a(db, tenant_a):
    return _spend_party(tenant_a, "Meridian Office Supplies")


@pytest.fixture
def spend_vendor_other_a(db, tenant_a):
    """A SECOND tenant-A supplier - the "two suppliers, one category" Pareto/HHI case."""
    return _spend_party(tenant_a, "Cobalt Facilities Group")


@pytest.fixture
def spend_vendor_b(db, tenant_b):
    """Tenant B's supplier - the crafted-POST FK target."""
    return _spend_party(tenant_b, "Globex Spend Partners")


@pytest.fixture
def spend_category_a(db, tenant_a):
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant_a, name="Office Supplies")


@pytest.fixture
def spend_category_other_a(db, tenant_a):
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant_a, name="Facilities")


@pytest.fixture
def spend_category_b(db, tenant_b):
    """Tenant B's taxonomy row - the crafted-POST FK target on both forms."""
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant_b, name="Globex Consumables")


@pytest.fixture
def spend_uom_a(db, tenant_a):
    from apps.scm.models import UOM
    obj, _ = UOM.objects.get_or_create(tenant=tenant_a, code="EA",
                                       defaults={"name": "Each", "factor": Decimal("1")})
    return obj


@pytest.fixture
def spend_item_a(db, tenant_a, spend_category_a, spend_uom_a):
    """SKU ``PPR-A4`` in ``spend_category_a`` - the invoiced-basis ``item.category`` passthrough
    leg of the classification order (item category -> rules -> "(Unclassified)")."""
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_a, sku="PPR-A4", name="A4 copy paper 80gsm",
                               category=spend_category_a, uom=spend_uom_a, item_type="stock")


@pytest.fixture
def spend_contract_a(db, tenant_a, spend_vendor_a):
    from apps.scm.models import SupplierContract
    return SupplierContract.objects.create(
        tenant=tenant_a, party=spend_vendor_a, title="Meridian stationery framework",
        contract_type="framework", status="active",
        start_date=timezone.localdate() - datetime.timedelta(days=30),
        end_date=timezone.localdate() + datetime.timedelta(days=300))


@pytest.fixture
def spend_contract_b(db, tenant_b, spend_vendor_b):
    """Tenant B's contract - the crafted-POST FK target on the finding form."""
    from apps.scm.models import SupplierContract
    return SupplierContract.objects.create(
        tenant=tenant_b, party=spend_vendor_b, title="Globex-only agreement",
        contract_type="purchase", status="active")


@pytest.fixture
def spend_catalog_item_a(db, tenant_a, spend_item_a, spend_vendor_other_a, usd):
    """An approved + active + PREFERRED catalogue entry at a DIFFERENT supplier - exactly what
    ``maverickfinding_detail``'s ``alternatives`` panel looks for."""
    from apps.procurement.models import CatalogItem
    return CatalogItem.objects.create(
        tenant=tenant_a, source_type="internal", item=spend_item_a,
        supplier=spend_vendor_other_a, currency=usd, uom=spend_item_a.uom,
        name="A4 copy paper (preferred buy)", supplier_part_no="PPR-A4",
        base_price=Decimal("21.00"), status="approved", is_preferred=True, is_active=True)


# -- spend documents (6.13 invoices + the SCM 4.1 order spine) ------------------------------------

@pytest.fixture
def spend_invoice_a(db, tenant_a, spend_vendor_a, usd):
    """RECOGNISED tenant-A invoice dated TODAY - inside every default window."""
    return _spend_invoice(tenant_a, spend_vendor_a, currency=usd)


@pytest.fixture
def spend_invoice_line_a(db, spend_invoice_a, spend_item_a, gl_expense_a):
    """qty 10 @ 25.00 -> ``line_total`` 250.00, item in ``spend_category_a``."""
    return _spend_invoice_line(spend_invoice_a, item=spend_item_a, gl_account=gl_expense_a)


@pytest.fixture
def spend_invoice_draft_a(db, tenant_a, spend_vendor_a, usd):
    """A DRAFT invoice - deliberately NOT recognised spend, so no 6.14 page counts it."""
    return _spend_invoice(tenant_a, spend_vendor_a, currency=usd, status="draft",
                          invoice_number="SUP-4401")


@pytest.fixture
def spend_invoice_b(db, tenant_b, spend_vendor_b):
    """Tenant B's invoice - the IDOR / crafted-FK target."""
    return _spend_invoice(tenant_b, spend_vendor_b, invoice_number="GBX-9001")


@pytest.fixture
def spend_invoice_line_b(db, spend_invoice_b):
    return _spend_invoice_line(spend_invoice_b, description="Globex-only line",
                               sku_hint="GBX-1", quantity=Decimal("2"),
                               unit_price=Decimal("40.00"))


@pytest.fixture
def spend_po_a(db, tenant_a, spend_vendor_a, org_unit_a):
    """Committed-basis tenant-A order dated TODAY, ship_to ``org_unit_a`` (the department axis)."""
    return _spend_po(tenant_a, spend_vendor_a, ship_to=org_unit_a)


@pytest.fixture
def spend_po_line_a(db, spend_po_a, gl_expense_a):
    """qty 4 @ 60.00 -> ``line_total`` 240.00, sku "TNR-55" (matches ``spend_rule_keyword_a``)."""
    return _spend_po_line(spend_po_a, gl_account=gl_expense_a)


@pytest.fixture
def spend_po_b(db, tenant_b, spend_vendor_b):
    """Tenant B's order - the IDOR / crafted-FK target."""
    return _spend_po(tenant_b, spend_vendor_b)


@pytest.fixture
def spend_po_line_b(db, spend_po_b):
    return _spend_po_line(spend_po_b, item_description="Globex-only spindle", sku_hint="GBX-SPN")


# -- SpendClassificationRule ----------------------------------------------------------------------

@pytest.fixture
def spend_rule_vendor_a(db, tenant_a, spend_vendor_a, spend_category_a):
    """priority 10, ``match_type="vendor"`` -> every line bought from ``spend_vendor_a``."""
    return _spend_rule(tenant_a, spend_category_a, vendor=spend_vendor_a)


@pytest.fixture
def spend_rule_keyword_a(db, tenant_a, spend_category_other_a):
    """priority 50, ``match_type="keyword"`` on "toner" - matches ``spend_po_line_a``'s
    ``item_description`` on the committed basis."""
    return _spend_rule(tenant_a, spend_category_other_a, name="Toner -> Facilities",
                       match_type="keyword", keyword="toner", vendor=None, priority=50)


@pytest.fixture
def spend_rule_inactive_a(db, tenant_a, spend_category_a, gl_expense_a):
    """``is_active=False`` - ``line_filter()`` returns None for it on BOTH bases."""
    return _spend_rule(tenant_a, spend_category_a, name="Retired GL rule",
                       match_type="gl_account", gl_account=gl_expense_a, vendor=None,
                       priority=90, is_active=False)


@pytest.fixture
def spend_rule_b(db, tenant_b, spend_vendor_b, spend_category_b):
    """Tenant B's rule - the cross-tenant 404 target on detail / edit / delete / preview."""
    return _spend_rule(tenant_b, spend_category_b, name="Globex -> Consumables",
                       vendor=spend_vendor_b)


# -- MaverickSpendFinding -------------------------------------------------------------------------

@pytest.fixture
def spend_finding_open_a(db, tenant_a, spend_vendor_a, spend_invoice_a, spend_category_a,
                         org_unit_a):
    """status "open" - the only state ``acknowledge()``, ``maverickfinding_edit`` and
    ``maverickfinding_delete`` accept."""
    return _spend_finding(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a,
                          category=spend_category_a, org_unit=org_unit_a)


@pytest.fixture
def spend_finding_ack_a(db, tenant_a, spend_vendor_a, spend_invoice_a):
    """status "acknowledged" - still OPEN work, so the three terminal verbs still apply."""
    obj = _spend_finding(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a,
                         reason="po_less_invoice",
                         detail="Service invoice raised with no purchase order.")
    obj.acknowledge(None)
    obj.refresh_from_db()
    return obj


@pytest.fixture
def spend_finding_leakage_a(db, tenant_a, spend_vendor_a, spend_invoice_a, spend_invoice_line_a,
                            spend_contract_a, spend_catalog_item_a):
    """amount 250 / benchmark 200 -> ``leakage_amount`` 50.00 DERIVED in save(),
    ``variance_pct`` 25.00. High severity, still open."""
    return _spend_finding(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a,
                          invoice_line=spend_invoice_line_a, contract=spend_contract_a,
                          catalog_item=spend_catalog_item_a,
                          reason="price_above_contract", severity="high",
                          amount=Decimal("250.00"), benchmark_amount=Decimal("200.00"),
                          detail="Unit price 25.00 against a contracted 20.00.")


@pytest.fixture
def spend_finding_dismissed_a(db, tenant_a, spend_vendor_a, spend_po_a, admin_user):
    """TERMINAL - edit and delete are refused, every disposition verb returns False, and the
    maverick RATE excludes it from the numerator."""
    obj = _spend_finding(tenant_a, spend_vendor_a, purchase_order=spend_po_a,
                         reason="off_catalog", severity="low",
                         amount=Decimal("240.00"),
                         detail="Bought off catalogue.")
    obj.dismiss(admin_user, "Catalogue entry was added the same week.")
    obj.refresh_from_db()
    return obj


@pytest.fixture
def spend_finding_b(db, tenant_b, spend_vendor_b, spend_invoice_b):
    """Tenant B's finding - the cross-tenant 404 target on detail / edit / delete / disposition."""
    return _spend_finding(tenant_b, spend_vendor_b, supplier_invoice=spend_invoice_b,
                          detail="Globex-only finding.")


# -- SpendReport + SpendReportSnapshot ------------------------------------------------------------

@pytest.fixture
def spend_report_a(db, tenant_a, admin_user):
    """SHARED, owned by ``admin_user`` - number ``SPR-00001``."""
    return _spend_report(tenant_a, owner=admin_user)


@pytest.fixture
def spend_report_favorite_a(db, tenant_a, admin_user, spend_category_a):
    """Pinned + narrowed to one category, two axes - exercises the ``?is_favorite=True`` filter
    and the ``dimension_2`` branch of ``compute_report``."""
    return _spend_report(tenant_a, owner=admin_user, name="Category by month",
                         dimension_1="category", dimension_2="month", chart_type="line",
                         category=spend_category_a, is_favorite=True)


@pytest.fixture
def spend_report_private_a(db, tenant_a, member_user):
    """``is_shared=False`` and owned by the MEMBER - every fetch in the SpendReports module goes
    through ``visible_reports()``, so this is a 404 for ``client_a`` on list, detail, edit, delete,
    run, snapshot, favourite and export alike."""
    return _spend_report(tenant_a, owner=member_user, name="Draft private cut",
                         is_shared=False)


@pytest.fixture
def spend_report_b(db, tenant_b, admin_b):
    """Tenant B's report - the cross-tenant 404 target."""
    return _spend_report(tenant_b, owner=admin_b, name="Globex spend by supplier")


@pytest.fixture
def spend_snapshot_a(db, tenant_a, spend_report_a, admin_user):
    return _spend_snapshot(tenant_a, spend_report_a, generated_by=admin_user)


@pytest.fixture
def spend_snapshot_private_a(db, tenant_a, spend_report_private_a, member_user):
    """A frozen run inherits its parent's privacy - a 404 for ``client_a``."""
    return _spend_snapshot(tenant_a, spend_report_private_a, generated_by=member_user,
                           title="Private frozen run")


@pytest.fixture
def spend_snapshot_b(db, tenant_b, spend_report_b, admin_b):
    """Tenant B's frozen run - the cross-tenant 404 target."""
    return _spend_snapshot(tenant_b, spend_report_b, generated_by=admin_b,
                           title="Globex frozen run")


# =================================================================================================
# 6.13 Invoice & Voucher Management
# =================================================================================================
#
# Every fixture below is prefixed ``invoice_`` so the four 6.13 test lanes never collide with the
# 6.1 / 6.2 / 6.4 / 6.5 / 6.9 / 6.11 / 6.12 / 6.14 records above (or with whatever 6.15 appends
# next). Dates derive from ``timezone.localdate()`` / ``timezone.now()`` - never
# ``datetime.date.today()`` - so exact-date assertions stay stable after local midnight (L16).
#
# The shape the lanes can rely on:
#
#   invoice_vendor_a        core.Party "Northwind Paper Mills"  + supplier PartyRole
#   invoice_vendor_other_a  core.Party "Southgate Stationers"   + supplier PartyRole (mismatch target)
#   invoice_vendor_b        tenant-B supplier - the crafted-FK / IDOR target
#   invoice_term_a          PaymentTerm "2/10 Net 30"  days_due 30, discount_pct 2, discount_days 10
#   invoice_term_net30_a    PaymentTerm "Net 30"       days_due 30, NO discount window
#   invoice_term_b          tenant-B term - the crafted-FK target
#   invoice_taxcode_a / invoice_taxcode_b
#   invoice_gl_ap_a         GLAccount "2000" liability  (the AP control leg approve() resolves)
#   invoice_gl_tax_a        GLAccount "1400" liability  (the input-tax leg)
#   invoice_gl_discount_a   GLAccount "5900" income     (purchase discounts received)
#   invoice_chart_a         all four at once -> (expense, ap, tax, discount); without it approve()
#                           raises ValidationError and rolls back (the configuration-fault case)
#   (``gl_expense_a`` from the 6.1 block above is code "5000" expense - the expense leg.)
#   invoice_item_a          scm.Item "PPR-A4" / invoice_item_b (tenant-B, crafted-FK target)
#
#   invoice_po_a            scm.PurchaseOrder approved, order_date = TODAY, currency USD
#     invoice_po_line_a       qty 10 @ 25.00  sku "PPR-A4"
#     invoice_po_line2_a      qty  4 @ 60.00  sku "TNR-55"
#   invoice_po_other_a      tenant-A order placed with invoice_vendor_other_a (mismatch target)
#   invoice_grn_a           scm.GoodsReceiptNote on invoice_po_a, receipt_date = TODAY
#     invoice_grn_line_a      po_line_a, quantity_received 10   (the exact-match receipt)
#   invoice_grn_short_a     a SHORT receipt (1 of the 4 ordered on po_line2_a)
#   invoice_po_b / invoice_po_line_b / invoice_grn_b / invoice_grn_line_b   tenant-B twins
#
#   invoice_draft_a         SIV draft, PO + GRN + 2/10 Net 30, invoice_number "SUP-7001"
#     invoice_line_a          po_line_a + grn_line_a, qty 10 @ 25.00 -> total 250.00
#   invoice_captured_a      status "captured", PO-less service invoice, "SUP-7002"
#   invoice_blocked_a       status "blocked",  one 10 @ 30.00 line -> total 300.00, "SUP-7003"
#   invoice_pending_a       status "pending_approval", one 10 @ 25.00 line -> 250.00, "SUP-7004"
#   invoice_scheduled_a     status "scheduled", one 4 @ 60.00 line -> 240.00, due in 5 days
#   invoice_paid_a          status "paid" - TERMINAL / is_locked,    "SUP-7006"
#   invoice_credit_memo_a   invoice_type "credit_memo", one 1 x -50.00 line -> -50.00, "CM-7001"
#   invoice_duplicate_a     same vendor / same normalised number / same total as invoice_draft_a
#   invoice_b / invoice_line_b   tenant-B invoice + line - the IDOR / crafted-FK targets
#
#   invoice_variance_block_a    "price",    outcome "block", resolution "open"  (on invoice_blocked_a)
#   invoice_variance_warn_a     "tax",      outcome "warn",  resolution "open"  (header-level)
#   invoice_variance_accepted_a "quantity", outcome "block", resolution "accepted"
#   invoice_variance_b          tenant-B variance - the IDOR target
#
#   invoice_dispute_open_a       status "open",      reason "price",    on invoice_draft_a
#   invoice_dispute_escalated_a  status "escalated", reason "quantity", on invoice_blocked_a
#   invoice_dispute_resolved_a   status "resolved" via resolve(..., "short_pay") - NOT editable
#   invoice_dispute_overdue_a    status "open", due_date 5 days in the PAST -> "overdue" bucket
#   invoice_dispute_b            tenant-B dispute - the IDOR target

def _invoice_party(tenant, name, role="supplier"):
    """A counterparty WITH its PartyRole. 6.13's own dropdowns do NOT filter on the role (the
    vendor field is auto-scoped by ``TenantModelForm``), but the sibling sub-modules' widgets do,
    so every procurement fixture party carries one."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


def _invoice_term(tenant, **overrides):
    from apps.accounting.models import PaymentTerm
    fields = dict(tenant=tenant, name="2/10 Net 30", days_due=30,
                  discount_pct=Decimal("2.00"), discount_days=10, is_active=True)
    fields.update(overrides)
    return PaymentTerm.objects.create(**fields)


def _invoice_gl(tenant, code, name, account_type):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(tenant=tenant, code=code, name=name,
                                    account_type=account_type, is_active=True)


def _invoice_po(tenant, vendor, **overrides):
    """A receivable (approved) spine order - the document an invoice is matched against."""
    from apps.scm.models import PurchaseOrder
    fields = dict(tenant=tenant, vendor=vendor, status="approved",
                  order_date=timezone.localdate(), expected_date=timezone.localdate())
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _invoice_po_line(po, description="A4 copy paper 80gsm", qty="10", price="25.00", **overrides):
    from apps.scm.models import PurchaseOrderLine
    fields = dict(purchase_order=po, item_description=description,
                  quantity=Decimal(qty), unit_price=Decimal(price),
                  sku_hint="PPR-A4", uom_hint="EA")
    fields.update(overrides)
    return PurchaseOrderLine.objects.create(**fields)


def _invoice_grn(tenant, po, **overrides):
    from apps.scm.models import GoodsReceiptNote
    fields = dict(tenant=tenant, purchase_order=po, receipt_date=timezone.localdate(),
                  status="draft", delivery_note_ref="DN-7001")
    fields.update(overrides)
    return GoodsReceiptNote.objects.create(**fields)


def _invoice_grn_line(grn, po_line, received="10", **overrides):
    from apps.scm.models import GoodsReceiptLine
    fields = dict(goods_receipt=grn, po_line=po_line, quantity_received=Decimal(received))
    fields.update(overrides)
    return GoodsReceiptLine.objects.create(**fields)


def _invoice(tenant, vendor, **overrides):
    """One SupplierInvoice header [SIV-].

    ``number`` / ``invoice_number_norm`` / ``due_date`` / ``discount_date`` /
    ``discount_expiry_date`` and every money column are DERIVED - never pass one.
    """
    from apps.procurement.models import SupplierInvoice
    fields = dict(tenant=tenant, vendor=vendor, invoice_number="SUP-7000",
                  invoice_date=timezone.localdate(), invoice_type="standard",
                  status="draft", source="manual")
    fields.update(overrides)
    return SupplierInvoice.objects.create(**fields)


def _invoice_line(invoice, **overrides):
    """One SupplierInvoiceLine. ``line_total`` is DERIVED in save() (quantity x unit_price) and the
    header money follows it through ``recalc_totals()`` - never pass ``line_total`` or
    ``matched_qty``."""
    from apps.procurement.models import SupplierInvoiceLine
    fields = dict(invoice=invoice, description="A4 copy paper 80gsm", sku_hint="PPR-A4",
                  uom_hint="EA", quantity=Decimal("10"), unit_price=Decimal("25.00"))
    fields.update(overrides)
    return SupplierInvoiceLine.objects.create(**fields)


def _invoice_variance(invoice, **overrides):
    """One InvoiceMatchVariance. ``variance_abs`` / ``variance_pct`` are DERIVED in save() from
    ``expected_value`` / ``actual_value`` and ``detected_at`` is ``auto_now_add`` - never pass any
    of the three."""
    from apps.procurement.models import InvoiceMatchVariance
    fields = dict(tenant=invoice.tenant, invoice=invoice, variance_type="price", basis="po",
                  expected_value=Decimal("25.0000"), actual_value=Decimal("30.0000"),
                  tolerance_pct_applied=Decimal("2.0000"),
                  outcome="block", resolution="open",
                  message="Unit price differs from the purchase order.")
    fields.update(overrides)
    return InvoiceMatchVariance.objects.create(**fields)


def _invoice_dispute(tenant, invoice, **overrides):
    """One InvoiceDispute [DSP-]. ``supplier`` is denormalised from ``invoice.vendor`` in save(),
    ``status`` is ``editable=False`` and moves only through the verbs, and ``due_date`` defaults to
    ``localdate() + SLA_DAYS`` on create - so none of the three is ever a form field."""
    from apps.procurement.models import InvoiceDispute
    fields = dict(tenant=tenant, invoice=invoice, reason_code="price",
                  disputed_amount=Decimal("50.00"),
                  description="Unit price billed above the agreed contract rate.",
                  supplier_contact="ap@northwind.example")
    fields.update(overrides)
    return InvoiceDispute.objects.create(**fields)


# -- counterparties, terms, tax codes and the chart of accounts approve() resolves -----------------

@pytest.fixture
def invoice_vendor_a(db, tenant_a):
    return _invoice_party(tenant_a, "Northwind Paper Mills")


@pytest.fixture
def invoice_vendor_other_a(db, tenant_a):
    """A SECOND tenant-A supplier - the vendor-agreement mismatch target (an invoice FROM one
    supplier against another supplier's order must be refused even though both rows live here)."""
    return _invoice_party(tenant_a, "Southgate Stationers")


@pytest.fixture
def invoice_vendor_b(db, tenant_b):
    """Tenant B's supplier - the crafted-POST FK / IDOR target."""
    return _invoice_party(tenant_b, "Globex Print Supplies")


@pytest.fixture
def invoice_term_a(db, tenant_a):
    """2/10 Net 30 - 2% off if paid within 10 days, due in 30. Annualised 36.73%."""
    return _invoice_term(tenant_a)


@pytest.fixture
def invoice_term_net30_a(db, tenant_a):
    """Plain Net 30 - no discount window, so save() must CLEAR discount_date / expiry."""
    return _invoice_term(tenant_a, name="Net 30", discount_pct=Decimal("0.00"),
                         discount_days=0)


@pytest.fixture
def invoice_term_b(db, tenant_b):
    return _invoice_term(tenant_b, name="Globex Net 45", days_due=45)


@pytest.fixture
def invoice_taxcode_a(db, tenant_a):
    from apps.accounting.models import TaxCode
    return TaxCode.objects.create(tenant=tenant_a, name="Standard VAT", tax_type="vat",
                                  rate_pct=Decimal("20.000"), is_active=True)


@pytest.fixture
def invoice_taxcode_b(db, tenant_b):
    from apps.accounting.models import TaxCode
    return TaxCode.objects.create(tenant=tenant_b, name="Globex VAT", tax_type="vat",
                                  rate_pct=Decimal("10.000"), is_active=True)


@pytest.fixture
def invoice_gl_ap_a(db, tenant_a):
    """Code "2000", type liability - the AP control leg ``approve()`` looks for FIRST."""
    return _invoice_gl(tenant_a, "2000", "Accounts Payable Control", "liability")


@pytest.fixture
def invoice_gl_tax_a(db, tenant_a):
    """Code "1400", type liability - the input-tax leg, only resolved when tax_total != 0."""
    return _invoice_gl(tenant_a, "1400", "Input VAT Recoverable", "liability")


@pytest.fixture
def invoice_gl_discount_a(db, tenant_a):
    """Code "5900", type income - purchase discounts received (the gross-method discount leg)."""
    return _invoice_gl(tenant_a, "5900", "Purchase Discounts Received", "income")


@pytest.fixture
def invoice_chart_a(db, gl_expense_a, invoice_gl_ap_a, invoice_gl_tax_a, invoice_gl_discount_a):
    """The WHOLE chart ``approve()`` needs, as one fixture -> (expense, ap, tax, discount).

    Request this and ``SupplierInvoice.approve()`` posts; omit it and approve() raises
    ``ValidationError`` and rolls the whole posting back, which is the configuration-fault case.
    """
    return gl_expense_a, invoice_gl_ap_a, invoice_gl_tax_a, invoice_gl_discount_a


@pytest.fixture
def invoice_item_a(db, tenant_a):
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_a, sku="PPR-A4", name="A4 copy paper 80gsm",
                               item_type="stock")


@pytest.fixture
def invoice_item_b(db, tenant_b):
    """Tenant B's item - the crafted-POST FK target on the line form."""
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_b, sku="GBX-1", name="Globex spindle",
                               item_type="stock")


# -- the order / receipt spine an invoice is matched against ---------------------------------------

@pytest.fixture
def invoice_po_a(db, tenant_a, invoice_vendor_a, usd):
    """Approved tenant-A order dated TODAY with TWO lines (10 @ 25.00, 4 @ 60.00)."""
    po = _invoice_po(tenant_a, invoice_vendor_a, currency=usd)
    _invoice_po_line(po)
    _invoice_po_line(po, description="Toner cartridge 55A", qty="4", price="60.00",
                     sku_hint="TNR-55")
    po.recalc_totals()
    return po


@pytest.fixture
def invoice_po_line_a(invoice_po_a):
    """First line of ``invoice_po_a`` - quantity 10, unit_price 25.00, sku PPR-A4."""
    return invoice_po_a.lines.order_by("id").first()


@pytest.fixture
def invoice_po_line2_a(invoice_po_a):
    """Second line of ``invoice_po_a`` - quantity 4, unit_price 60.00, sku TNR-55."""
    return invoice_po_a.lines.order_by("id").last()


@pytest.fixture
def invoice_po_other_a(db, tenant_a, invoice_vendor_other_a):
    """A tenant-A order placed with the OTHER supplier - the vendor-agreement mismatch target."""
    po = _invoice_po(tenant_a, invoice_vendor_other_a)
    _invoice_po_line(po, description="Envelope C4 box", qty="5", price="12.00",
                     sku_hint="ENV-C4")
    po.recalc_totals()
    return po


@pytest.fixture
def invoice_po_b(db, tenant_b, invoice_vendor_b):
    """Tenant-B order with one line - the cross-tenant crafted-POST target."""
    po = _invoice_po(tenant_b, invoice_vendor_b)
    _invoice_po_line(po, description="Globex-only spindle", qty="6", price="80.00",
                     sku_hint="GBX-SPN")
    po.recalc_totals()
    return po


@pytest.fixture
def invoice_po_line_b(invoice_po_b):
    return invoice_po_b.lines.order_by("id").first()


@pytest.fixture
def invoice_grn_a(db, tenant_a, invoice_po_a):
    """Receipt dated TODAY against ``invoice_po_a`` - delivery note ``DN-7001``."""
    return _invoice_grn(tenant_a, invoice_po_a)


@pytest.fixture
def invoice_grn_line_a(db, invoice_grn_a, invoice_po_line_a):
    """EXACTLY 10 received against the 10-unit ordered line - the clean three-way-match receipt."""
    return _invoice_grn_line(invoice_grn_a, invoice_po_line_a, received="10")


@pytest.fixture
def invoice_grn_short_a(db, tenant_a, invoice_po_a, invoice_po_line2_a):
    """A SHORT receipt (1 of the 4 ordered) - the quantity-variance receipt."""
    grn = _invoice_grn(tenant_a, invoice_po_a, delivery_note_ref="DN-7002")
    _invoice_grn_line(grn, invoice_po_line2_a, received="1")
    return grn


@pytest.fixture
def invoice_grn_b(db, tenant_b, invoice_po_b):
    return _invoice_grn(tenant_b, invoice_po_b, delivery_note_ref="GBX-DN-9001")


@pytest.fixture
def invoice_grn_line_b(db, invoice_grn_b, invoice_po_line_b):
    return _invoice_grn_line(invoice_grn_b, invoice_po_line_b, received="6")


# -- supplier invoices, one per lifecycle state ----------------------------------------------------

@pytest.fixture
def invoice_draft_a(db, tenant_a, invoice_vendor_a, invoice_po_a, invoice_grn_a,
                    invoice_term_a, usd):
    """DRAFT, PO- and GRN-matched, on 2/10 Net 30 - editable, deletable, matchable, submittable."""
    return _invoice(tenant_a, invoice_vendor_a, invoice_number="SUP-7001",
                    purchase_order=invoice_po_a, goods_receipt=invoice_grn_a,
                    payment_term=invoice_term_a, currency=usd)


@pytest.fixture
def invoice_line_a(db, invoice_draft_a, invoice_po_line_a, invoice_grn_line_a):
    """10 @ 25.00 against the ordered AND received line -> header total 250.00, a clean match."""
    return _invoice_line(invoice_draft_a, po_line=invoice_po_line_a,
                         receipt_line=invoice_grn_line_a)


@pytest.fixture
def invoice_captured_a(db, tenant_a, invoice_vendor_a, usd):
    """CAPTURED and PO-less (a service invoice) - still editable, still submittable."""
    return _invoice(tenant_a, invoice_vendor_a, invoice_number="SUP-7002", status="captured",
                    invoice_type="service", currency=usd,
                    posting_date=timezone.localdate())


@pytest.fixture
def invoice_blocked_a(db, tenant_a, invoice_vendor_a, invoice_po_a, invoice_term_a, usd):
    """BLOCKED with one 10 @ 30.00 line -> total 300.00. Overridable by an admin, disputable once
    it carries an open variance, and NOT editable (``EDITABLE_STATUSES`` stops at ``captured``)."""
    invoice = _invoice(tenant_a, invoice_vendor_a, invoice_number="SUP-7003", status="blocked",
                       purchase_order=invoice_po_a, payment_term=invoice_term_a, currency=usd,
                       match_basis="amount")
    _invoice_line(invoice, quantity=Decimal("10"), unit_price=Decimal("30.00"))
    invoice.refresh_from_db()
    return invoice


@pytest.fixture
def invoice_pending_a(db, tenant_a, invoice_vendor_a, invoice_po_a, invoice_term_a, usd):
    """PENDING_APPROVAL with one 10 @ 25.00 line -> total 250.00. The only state ``approve()``
    accepts, and the fixture the ledger-posting tests start from."""
    invoice = _invoice(tenant_a, invoice_vendor_a, invoice_number="SUP-7004",
                       status="pending_approval", purchase_order=invoice_po_a,
                       payment_term=invoice_term_a, currency=usd, match_basis="amount",
                       match_status="matched")
    _invoice_line(invoice)
    invoice.refresh_from_db()
    return invoice


@pytest.fixture
def invoice_scheduled_a(db, tenant_a, invoice_vendor_a, invoice_term_a, usd):
    """SCHEDULED with one 4 @ 60.00 line -> total 240.00, due in 5 days (invoice_date is 25 days
    back on a Net 30 term). The Payment Schedule board's bucketed row, and the only state
    ``mark_paid()`` accepts."""
    invoice = _invoice(tenant_a, invoice_vendor_a, invoice_number="SUP-7005",
                       status="scheduled", payment_term=invoice_term_a, currency=usd,
                       invoice_date=timezone.localdate() - datetime.timedelta(days=25))
    _invoice_line(invoice, quantity=Decimal("4"), unit_price=Decimal("60.00"))
    invoice.refresh_from_db()
    return invoice


@pytest.fixture
def invoice_paid_a(db, tenant_a, invoice_vendor_a, usd):
    """PAID - TERMINAL, so ``is_locked`` is True: no edit, no match, no void, no new lines."""
    return _invoice(tenant_a, invoice_vendor_a, invoice_number="SUP-7006", status="paid",
                    currency=usd)


@pytest.fixture
def invoice_credit_memo_a(db, tenant_a, invoice_vendor_a, usd):
    """A CREDIT MEMO carrying one NEGATIVE line (1 x -50.00) -> total -50.00.

    ``run_match()`` early-returns on one of these without touching ``status``, and lane B refuses a
    positive line on it.
    """
    memo = _invoice(tenant_a, invoice_vendor_a, invoice_number="CM-7001",
                    invoice_type="credit_memo", status="captured", currency=usd)
    _invoice_line(memo, description="Credit for over-billed reams",
                  quantity=Decimal("1"), unit_price=Decimal("-50.00"))
    memo.refresh_from_db()
    return memo


@pytest.fixture
def invoice_duplicate_a(db, tenant_a, invoice_vendor_a, invoice_draft_a, invoice_line_a, usd):
    """Same VENDOR, same NORMALISED number ("sup 7001" -> "SUP7001") and the same 250.00 total,
    dated today - four scoring reasons, so ``duplicate_candidates()`` reports it."""
    twin = _invoice(tenant_a, invoice_vendor_a, invoice_number="sup 7001", currency=usd)
    _invoice_line(twin)
    twin.refresh_from_db()
    return twin


@pytest.fixture
def invoice_b(db, tenant_b, invoice_vendor_b, invoice_po_b, usd):
    """Tenant B's invoice - the cross-tenant 404 target on every pk-scoped 6.13 route."""
    return _invoice(tenant_b, invoice_vendor_b, invoice_number="GBX-9001",
                    purchase_order=invoice_po_b, currency=usd)


@pytest.fixture
def invoice_line_b(db, invoice_b, invoice_po_line_b):
    """Tenant B's line - the IDOR target on the line register and the crafted-FK target."""
    return _invoice_line(invoice_b, po_line=invoice_po_line_b,
                         description="Globex-only spindle", sku_hint="GBX-SPN",
                         quantity=Decimal("6"), unit_price=Decimal("80.00"))


# -- match variances (evidence: no create / edit / delete route exists) ----------------------------

@pytest.fixture
def invoice_variance_block_a(db, invoice_blocked_a):
    """A BLOCKING, still-OPEN price variance - what ``override()`` accepts and ``raise_dispute()``
    requires at least one of."""
    return _invoice_variance(invoice_blocked_a)


@pytest.fixture
def invoice_variance_warn_a(db, invoice_blocked_a):
    """A header-level tax WARNING (``invoice_line`` NULL) - never blocking (cap="warn")."""
    return _invoice_variance(invoice_blocked_a, variance_type="tax", basis="header",
                             expected_value=Decimal("50.0000"),
                             actual_value=Decimal("50.4000"),
                             tolerance_pct_applied=None,
                             tolerance_abs_applied=Decimal("1.0000"),
                             outcome="warn",
                             message="Tax differs from the line-derived tax amount.")


@pytest.fixture
def invoice_variance_accepted_a(db, invoice_blocked_a):
    """Already ACCEPTED - ``accept()`` must no-op on it and the route must refuse."""
    return _invoice_variance(invoice_blocked_a, variance_type="quantity", basis="receipt",
                             expected_value=Decimal("10.0000"),
                             actual_value=Decimal("12.0000"),
                             resolution="accepted",
                             message="Invoiced quantity differs from the quantity received.")


@pytest.fixture
def invoice_variance_b(db, invoice_b):
    """Tenant B's exception - the cross-tenant 404 target on detail and accept."""
    return _invoice_variance(invoice_b, message="Globex-only exception.")


# -- disputes --------------------------------------------------------------------------------------

@pytest.fixture
def invoice_dispute_open_a(db, tenant_a, admin_user, invoice_draft_a, invoice_line_a):
    """OPEN price dispute pinned to the invoice's own line - editable, resolvable, escalatable.
    ``due_date`` is stamped by save() at ``localdate() + SLA_DAYS`` (10)."""
    return _invoice_dispute(tenant_a, invoice_draft_a, invoice_line=invoice_line_a,
                            raised_by=admin_user, assigned_to=admin_user)


@pytest.fixture
def invoice_dispute_escalated_a(db, tenant_a, admin_user, invoice_blocked_a):
    """ESCALATED - still OPEN work, so await_supplier / await_internal / resolve all still apply."""
    obj = _invoice_dispute(tenant_a, invoice_blocked_a, reason_code="quantity",
                           disputed_amount=Decimal("75.00"),
                           description="Three reams short against the delivery note.",
                           raised_by=admin_user)
    obj.escalate(admin_user)
    obj.refresh_from_db()
    return obj


@pytest.fixture
def invoice_dispute_resolved_a(db, tenant_a, admin_user, invoice_captured_a):
    """RESOLVED via ``short_pay`` - no longer open, so edit is refused and every open-state verb
    no-ops; only ``close()`` still applies."""
    obj = _invoice_dispute(tenant_a, invoice_captured_a, reason_code="freight",
                           disputed_amount=Decimal("0.00"),
                           description="Unapproved delivery surcharge.",
                           raised_by=admin_user)
    obj.resolve(admin_user, "short_pay", "Paid net of the surcharge.")
    obj.refresh_from_db()
    return obj


@pytest.fixture
def invoice_dispute_overdue_a(db, tenant_a, admin_user, invoice_draft_a):
    """OPEN with a due date FIVE DAYS in the past -> ``is_overdue`` True and ``age_bucket``
    "overdue" (which outranks the day bands on the aging board)."""
    return _invoice_dispute(tenant_a, invoice_draft_a, reason_code="duplicate",
                            disputed_amount=Decimal("25.00"),
                            description="Second copy of an invoice already paid.",
                            raised_by=admin_user,
                            due_date=timezone.localdate() - datetime.timedelta(days=5))


@pytest.fixture
def invoice_dispute_b(db, tenant_b, admin_b, invoice_b):
    """Tenant B's dispute - the cross-tenant 404 target on detail / edit / delete / every verb."""
    return _invoice_dispute(tenant_b, invoice_b, description="Globex-only argument.",
                            raised_by=admin_b)


# =================================================================================================
# 6.19 Document & Knowledge Management
# =================================================================================================
#
# Every fixture and helper below is prefixed ``dk_`` / ``_dk_`` so the four 6.19 test lanes
# (test_dk_models / test_dk_forms / test_dk_views / test_dk_security) never collide with the
# 6.1 / 6.2 / 6.4 / 6.5 / 6.9 / 6.11 / 6.12 / 6.13 / 6.14 / 6.15 records above, or with whatever
# 6.16-6.18 append next (L47). Dates derive from ``timezone.localdate()`` / ``timezone.now()`` -
# never ``datetime.date.today()`` - so exact-date assertions stay stable after local midnight (L16).
#
# THREE THINGS TO KNOW BEFORE USING THESE:
#
# 1. ``Model.objects.create()`` does NOT call ``clean()``. Tags on ``dk_*`` documents and
#    resources are therefore pre-normalised (lower case, ", "-joined) - assert ``normalize_tags``
#    and ``clean()`` through the MODEL/FORM directly, never by reading a fixture back.
# 2. Anything that stores a FILE depends on ``dk_media_root``, which points ``settings.MEDIA_ROOT``
#    at pytest's per-test ``tmp_path``. Nothing is left under the real ``media/`` when the test DB
#    tears down. Request it (directly or transitively) before writing any file in a test.
# 3. ``_dk_revision`` runs the REAL ``extract_document_text`` over the stored ``.txt`` bytes, and
#    ``_dk_approve`` performs exactly the writes ``pdocrevision_approve`` performs (stamp, move the
#    pointer, copy the text up, draft -> active). The fixture chain state is the production state.
#
# The shape the lanes can rely on:
#
#   dk_media_root              settings.MEDIA_ROOT -> tmp_path/media (auto-cleaned)
#   dk_supplier_a / dk_supplier_b   core.Party + supplier PartyRole (the ?supplier= facet + IDOR)
#
#   dk_document_draft_a        draft / internal / ZERO revisions      -> delete IS allowed
#   dk_document_active_a       active / internal / supplier + owner   -> supersede/archive source
#   dk_document_superseded_a   superseded / internal
#   dk_document_archived_a     archived / internal   -> checkout + upload are REFUSED on it
#   dk_document_public_a       public      / no owner -> member_user CAN read
#   dk_document_confidential_a confidential / owner=admin_user  -> member_user CANNOT (I5)
#   dk_document_restricted_a   restricted   / owner=admin_user  -> member_user CANNOT (I5)
#   dk_document_confidential_member_a  confidential / owner=member_user -> member_user CAN (I5)
#   dk_document_expiring_a     expires_on = today + 7   (inside EXPIRY_WARN_DAYS)
#   dk_document_expired_a      expires_on = today - 3
#   dk_document_review_due_a   review_on  = today - 1
#   dk_document_over_retention_a  retention_until = today - 1
#   dk_document_locked_a       checked_out_by = member_user -> admin_user is refused / may force
#   dk_document_chain_a        active, pointer = 1, r1 APPROVED + r2 PENDING
#   dk_documents_page2_a       16 public active rows -> forces page 2 at per_page=15
#   dk_document_b              tenant B - the IDOR / crafted-FK target
#
#   dk_revision_approved_a     r1 of dk_document_chain_a (is_approved=True, is_current=True)
#   dk_revision_pending_a      r2 of dk_document_chain_a (pending -> approvable, deletable)
#   dk_revision_confidential_a r1 of dk_document_confidential_a, approved (classification via FK)
#   dk_revision_no_file_a      r1 of dk_document_superseded_a with file="" (download guard)
#   dk_revision_b              r1 of dk_document_b - the IDOR / download target
#
#   dk_policy_v1_archived_a    "Competitive Bidding Threshold" v1.0 ARCHIVED (published_at set)
#   dk_policy_published_a      same title v2.0 PUBLISHED, previous_version = v1.0, threshold set
#   dk_policy_draft_a          same title v3.0 DRAFT, previous_version = v2.0
#                              -> publishing it ARCHIVES dk_policy_published_a
#   dk_policy_review_due_a     "Supplier Code of Conduct" v1.0 published, next_review_on = today-1
#   dk_attestation_a           6.17 PolicyAttestation on dk_policy_published_a -> delete REFUSED
#   dk_policy_b                tenant B - the IDOR / crafted-FK target
#
#   dk_resource_featured_a     published + is_featured -> the "start here" shelf
#   dk_resource_published_a    published, not featured
#   dk_resource_draft_a        draft            -> publish verb target
#   dk_resource_archived_a     archived         -> "use" is REFUSED, publish is allowed
#   dk_resource_used_a         published, usage_count = 7 (the stats.used tile + increment)
#   dk_resource_review_due_a   published, review_on = today - 1 (is_review_due badge)
#   dk_resource_b              tenant B - the IDOR / crafted-FK target

#: Distinctive file/search text for the two documents a non-admin must not be able to reach.
#: A ``?q=`` for either phrase is the SEARCH-ORACLE probe: it must return 200 with zero rows for
#: ``member_client`` and the row for ``client_a``. Both are >= 4 characters, so they cross
#: ``FILE_TEXT_SEARCH_MIN_CHARS`` and really do sweep ``extracted_text``.
_DK_CONFIDENTIAL_TEXT = ("Settlement schedule: zephyrindemnity ceiling of 2,400,000 payable in "
                         "four instalments. Not for circulation.")
_DK_RESTRICTED_TEXT = ("Board minute: quillbaseline pricing floor agreed with the incumbent "
                       "supplier. Named readers only.")
#: The public counterpart - every member may match this one, which is what makes the pair a test
#: of the RULE rather than of an empty database.
_DK_PUBLIC_TEXT = "Standard warranty terms: harborcoverage runs for 24 months from delivery."


@pytest.fixture
def dk_media_root(settings, tmp_path):
    """Point MEDIA_ROOT at pytest's per-test tmp_path so no fixture leaves bytes behind.

    ``FileSystemStorage`` connects ``setting_changed`` in ``__init__`` and drops its cached
    ``base_location`` / ``location``, so overriding the setting really does move where a
    ``FileField`` writes. ``tmp_path`` is removed by pytest; the real ``media/`` is never touched.
    """
    root = tmp_path / "media"
    root.mkdir(parents=True, exist_ok=True)
    settings.MEDIA_ROOT = str(root)
    return str(root)


# -- helpers --------------------------------------------------------------------------------------

def _dk_party(tenant, name, role="supplier"):
    """A counterparty WITH its PartyRole - the document register's ?supplier= facet and the form's
    ``_supplier_parties`` dropdown both filter ``roles__role__in=("supplier", "vendor")``, so a
    bare Party would not appear in either."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


def _dk_document(tenant, **overrides):
    """One ProcurementDocument [PDOC-].

    ``number`` is allocated by ``TenantNumbered.save()`` and ``current_revision_no`` is moved only
    by the approve path - never pass either. ``tags`` here is stored VERBATIM (``objects.create``
    skips ``clean()``), so fixtures pass it already normalised.
    """
    from apps.procurement.models import ProcurementDocument
    fields = dict(tenant=tenant, title="Boiler maintenance warranty", doc_type="warranty",
                  description="Manufacturer cover for the plant-room boiler.",
                  tags="warranty, facilities", classification="internal", status="draft")
    fields.update(overrides)
    return ProcurementDocument.objects.create(**fields)


def _dk_documents(tenant, count, **overrides):
    """``count`` register rows, newest last - the page-2 / pagination filler."""
    return [_dk_document(tenant, title=f"Bulk register row {i:02d}", **overrides)
            for i in range(1, count + 1)]


def _dk_revision(document, *, body=b"", filename="revision.txt", change_note="",
                 uploaded_by=None, **overrides):
    """One ProcurementDocumentRevision, minted exactly the way ``pdocument_revision_upload`` does.

    ``revision_no`` comes from ``next_revision_no``; the checksum, size and original filename are
    measured from the payload BEFORE the save; the REAL ``extract_document_text`` then runs over
    the stored file and its ``(text, note)`` is stamped on the row. Pass ``body=None`` for the
    file-less row the download guard needs (``file=""``).
    """
    import hashlib

    from django.core.files.base import ContentFile

    from apps.procurement.models import ProcurementDocumentRevision
    from apps.procurement.models.DocumentKnowledgeManagement.Revisions import (
        EXTRACT_MAX_CHARS, extract_document_text, next_revision_no)

    payload = body if body is None or isinstance(body, bytes) else body.encode("utf-8")
    fields = dict(tenant=document.tenant, document=document,
                  revision_no=next_revision_no(document), change_note=change_note,
                  uploaded_by=uploaded_by)
    if payload is None:
        # The row can outlive its bytes: no file at all, which is the branch
        # ``pdocrevision_download`` answers with a message and a redirect rather than a 500.
        fields.update(file="", original_filename="", file_size=0, sha256="")
        fields.update(overrides)
        return ProcurementDocumentRevision.objects.create(**fields)

    fields.update(original_filename=filename, file_size=len(payload),
                  sha256=hashlib.sha256(payload).hexdigest())
    fields.update(overrides)
    revision = ProcurementDocumentRevision(**fields)
    revision.file.save(filename, ContentFile(payload), save=False)
    revision.save()

    text, note = extract_document_text(revision)
    revision.extracted_text = (text or "")[:EXTRACT_MAX_CHARS]
    revision.extraction_note = note
    revision.save(update_fields=["extracted_text", "extraction_note"])
    return revision


def _dk_approve(revision, user):
    """Approve a revision exactly as ``pdocrevision_approve`` does - the four writes, in order.

    Stamps the revision, moves the parent's pointer, copies the revision's text up into the
    parent's denormalised SEARCH COPY, and lifts a still-draft document to ``active``. The parent
    is refreshed in place so the caller's object is not stale.
    """
    from apps.procurement.models.DocumentKnowledgeManagement.Revisions import EXTRACT_MAX_CHARS

    revision.is_approved = True
    revision.approved_by = user
    revision.approved_at = timezone.now()
    revision.save(update_fields=["is_approved", "approved_by", "approved_at"])

    document = revision.document
    document.current_revision_no = revision.revision_no
    document.extracted_text = (revision.extracted_text or "")[:EXTRACT_MAX_CHARS]
    if document.status == "draft":
        document.status = "active"
    document.save(update_fields=["current_revision_no", "extracted_text", "status", "updated_at"])
    return revision


def _dk_policy(tenant, **overrides):
    """One ProcurementPolicy [PPOL-].

    ``number`` is allocated in ``save()`` and ``status`` / ``published_at`` are verb-driven - pass
    them here only to BUILD a state the verbs would have produced. The review column is
    ``next_review_on`` on this model (``review_on`` is the document's and the resource's).
    """
    from apps.procurement.models import ProcurementPolicy
    fields = dict(tenant=tenant, title="Competitive Bidding Threshold",
                  policy_type="competitive_bidding",
                  summary="Purchases above the threshold need three written quotes.",
                  body="Three written quotes are required for any purchase order above the "
                       "stated figure. The figure is a guideline; routing is decided by 6.3.",
                  version_number="1.0", status="draft")
    fields.update(overrides)
    return ProcurementPolicy.objects.create(**fields)


def _dk_resource(tenant, **overrides):
    """One KnowledgeResource [PKR-].

    ``usage_count`` / ``last_used_at`` belong to the "use this" verb - pass them only to build a
    state that verb would have produced. ``tags`` is stored verbatim (no ``clean()`` on create).
    """
    from apps.procurement.models import KnowledgeResource
    fields = dict(tenant=tenant, title="RFP template - professional services",
                  resource_type="rfp_template", category="professional_services",
                  audience="buyer", summary="Start here for a services RFP.",
                  body="Sections 1-9 with the evaluation grid already weighted.",
                  tags="rfp, services", status="draft")
    fields.update(overrides)
    return KnowledgeResource.objects.create(**fields)


# -- counterparties --------------------------------------------------------------------------------

@pytest.fixture
def dk_supplier_a(db, tenant_a):
    return _dk_party(tenant_a, "Ironclad Filing Systems")


@pytest.fixture
def dk_supplier_b(db, tenant_b):
    """Tenant B's supplier - the crafted-POST target for ``ProcurementDocumentForm.supplier``."""
    return _dk_party(tenant_b, "Globex Records Depot")


# -- documents: one per status, one per classification ---------------------------------------------

@pytest.fixture
def dk_document_draft_a(db, tenant_a, admin_user):
    """Draft, NO revisions and ``current_revision_no == 0`` - the one document
    ``pdocument_delete`` will actually delete."""
    return _dk_document(tenant_a, title="Draft specification - server rack",
                        doc_type="specification", tags="specification, it",
                        owner=admin_user, created_by=admin_user)


@pytest.fixture
def dk_document_active_a(db, tenant_a, admin_user, dk_supplier_a):
    """Active with a supplier and an owner - the supersede / archive source row."""
    return _dk_document(tenant_a, title="Grounds maintenance statement of work",
                        doc_type="sow", status="active", supplier=dk_supplier_a,
                        owner=admin_user, created_by=admin_user,
                        tags="sow, facilities",
                        effective_date=timezone.localdate() - datetime.timedelta(days=30),
                        review_on=timezone.localdate() + datetime.timedelta(days=180))


@pytest.fixture
def dk_document_superseded_a(db, tenant_a, admin_user):
    return _dk_document(tenant_a, title="Superseded insurance certificate",
                        doc_type="insurance", status="superseded", owner=admin_user,
                        created_by=admin_user, tags="insurance")


@pytest.fixture
def dk_document_archived_a(db, tenant_a, admin_user):
    """Archived - checkout and revision upload are both REFUSED against this one."""
    return _dk_document(tenant_a, title="Archived drawing pack", doc_type="drawing",
                        status="archived", owner=admin_user, created_by=admin_user,
                        tags="drawing")


@pytest.fixture
def dk_document_public_a(db, tenant_a):
    """Public, owned by nobody - visible to every member, and the control row that proves an
    empty confidential search is the RULE and not an empty database."""
    return _dk_document(tenant_a, title="Public warranty summary", doc_type="warranty",
                        classification="public", status="active", tags="warranty, public",
                        extracted_text=_DK_PUBLIC_TEXT)


@pytest.fixture
def dk_document_confidential_a(db, tenant_a, admin_user):
    """Confidential, owned and created by the ADMIN - ``member_user`` must not see it in the
    register, on the detail page, through ``?q=zephyrindemnity`` or through any verb (I5)."""
    return _dk_document(tenant_a, title="Settlement schedule - confidential",
                        doc_type="correspondence", classification="confidential",
                        status="active", owner=admin_user, created_by=admin_user,
                        tags="legal, confidential", extracted_text=_DK_CONFIDENTIAL_TEXT)


@pytest.fixture
def dk_document_restricted_a(db, tenant_a, admin_user):
    """Restricted, owned and created by the ADMIN - the tier above confidential, same rule (I5).
    ``?q=quillbaseline`` is its search-oracle probe."""
    return _dk_document(tenant_a, title="Board pricing minute - restricted",
                        doc_type="correspondence", classification="restricted",
                        status="active", owner=admin_user, created_by=admin_user,
                        tags="legal, restricted", extracted_text=_DK_RESTRICTED_TEXT)


@pytest.fixture
def dk_document_confidential_member_a(db, tenant_a, member_user):
    """Confidential but OWNED BY ``member_user`` - the positive half of ``readable_document_q``:
    the rule is owner/creator/administrator, not a blanket ban on the tier."""
    return _dk_document(tenant_a, title="Member-owned confidential note",
                        doc_type="correspondence", classification="confidential",
                        status="active", owner=member_user, tags="confidential")


@pytest.fixture
def dk_document_expiring_a(db, tenant_a, admin_user):
    """``expires_on`` seven days out - inside ``EXPIRY_WARN_DAYS`` (30), so ``is_expiring`` is
    True, ``?expiry=expiring`` matches it and the reminder scan raises "expires" for it."""
    return _dk_document(tenant_a, title="Expiring certificate of insurance",
                        doc_type="insurance", status="active", owner=admin_user,
                        created_by=admin_user,
                        expires_on=timezone.localdate() + datetime.timedelta(days=7))


@pytest.fixture
def dk_document_expired_a(db, tenant_a, admin_user):
    """``expires_on`` three days PAST - ``is_expired`` True, ``is_expiring`` False."""
    return _dk_document(tenant_a, title="Expired public liability cover",
                        doc_type="insurance", status="active", owner=admin_user,
                        created_by=admin_user,
                        expires_on=timezone.localdate() - datetime.timedelta(days=3))


@pytest.fixture
def dk_document_review_due_a(db, tenant_a, admin_user):
    """``review_on`` yesterday - ``is_review_due`` True and ``?expiry=review_due`` matches."""
    return _dk_document(tenant_a, title="Policy document overdue for review",
                        doc_type="policy", status="active", owner=admin_user,
                        created_by=admin_user,
                        review_on=timezone.localdate() - datetime.timedelta(days=1))


@pytest.fixture
def dk_document_over_retention_a(db, tenant_a, admin_user):
    """``retention_until`` yesterday - a FLAG only. Nothing in 6.19 deletes it."""
    return _dk_document(tenant_a, title="Past-retention correspondence",
                        doc_type="correspondence", status="active", owner=admin_user,
                        created_by=admin_user,
                        retention_until=timezone.localdate() - datetime.timedelta(days=1))


@pytest.fixture
def dk_document_locked_a(db, tenant_a, admin_user, member_user):
    """Checked out by ``member_user``: ``admin_user`` is refused an ordinary checkout, MAY force
    the release (tenant admin), and the upload page refuses them by naming the holder."""
    return _dk_document(tenant_a, title="Checked-out quote pack", doc_type="quote",
                        status="active", owner=admin_user, created_by=admin_user,
                        checked_out_by=member_user, checked_out_at=timezone.now())


@pytest.fixture
def dk_document_chain_a(db, tenant_a, admin_user, dk_media_root):
    """The two-revision document: r1 APPROVED (pointer = 1, status lifted to active) and r2
    PENDING. Both revisions carry a real ``.txt`` file whose text was really extracted."""
    document = _dk_document(tenant_a, title="Boiler maintenance contract", doc_type="sow",
                            owner=admin_user, created_by=admin_user, tags="sow, facilities")
    first = _dk_revision(document, filename="boiler-r1.txt", uploaded_by=admin_user,
                         change_note="First issue",
                         body=b"Boiler maintenance contract, first issue. Cover includes "
                              b"quarterly servicing and a soleplate inspection.")
    _dk_approve(first, admin_user)
    _dk_revision(document, filename="boiler-r2.txt", uploaded_by=admin_user,
                 change_note="Section 4 rewritten",
                 body=b"Boiler maintenance contract, second issue. Section 4 rewritten to add "
                      b"an out-of-hours callout window.")
    document.refresh_from_db()
    return document


@pytest.fixture
def dk_documents_page2_a(db, tenant_a):
    """16 rows - one more than ``crud_list``'s per_page of 15, so page 2 exists on its own."""
    return _dk_documents(tenant_a, 16, classification="public", status="active")


@pytest.fixture
def dk_document_b(db, tenant_b, admin_b):
    """Tenant B's document - the cross-tenant 404 target on detail / edit / delete / every verb,
    and the crafted-FK target for the policy and knowledge-resource ``document`` fields."""
    return _dk_document(tenant_b, title="Globex-only master agreement", doc_type="sow",
                        status="active", owner=admin_b, created_by=admin_b)


# -- revisions ------------------------------------------------------------------------------------

@pytest.fixture
def dk_revision_approved_a(dk_document_chain_a):
    """r1 - approved AND current (``is_current`` True). Delete refuses it on BOTH guards."""
    return dk_document_chain_a.revisions.get(revision_no=1)


@pytest.fixture
def dk_revision_pending_a(dk_document_chain_a):
    """r2 - pending, not current: the one revision approve accepts and delete removes."""
    return dk_document_chain_a.revisions.get(revision_no=2)


@pytest.fixture
def dk_revision_confidential_a(db, dk_document_confidential_a, admin_user, dk_media_root):
    """An approved revision of a CONFIDENTIAL document. ``member_client`` must 404 on its detail
    page, on its download and on the revision register row (the parent's classification governs
    the child through ``readable_document_q(user, "document__")``)."""
    revision = _dk_revision(dk_document_confidential_a, filename="settlement.txt",
                            uploaded_by=admin_user, change_note="Signed settlement",
                            body=_DK_CONFIDENTIAL_TEXT.encode("utf-8"))
    return _dk_approve(revision, admin_user)


@pytest.fixture
def dk_revision_no_file_a(db, dk_document_superseded_a, admin_user):
    """A revision row with NO stored bytes - ``pdocrevision_download`` answers with a message and
    a redirect to its detail page, never a 500."""
    return _dk_revision(dk_document_superseded_a, body=None, uploaded_by=admin_user,
                        change_note="Row kept, bytes never arrived")


@pytest.fixture
def dk_revision_b(db, dk_document_b, admin_b, dk_media_root):
    """Tenant B's approved revision - the cross-tenant 404 target on detail, download, approve
    and delete."""
    revision = _dk_revision(dk_document_b, filename="globex-r1.txt", uploaded_by=admin_b,
                            change_note="Globex first issue",
                            body=b"Globex master agreement, first issue.")
    return _dk_approve(revision, admin_b)


# -- policies -------------------------------------------------------------------------------------

@pytest.fixture
def dk_policy_v1_archived_a(db, tenant_a, admin_user):
    """v1.0, ARCHIVED and stamped ``published_at`` - it WAS in force once, which is why archiving
    never clears the stamp. Publishing it again is refused."""
    return _dk_policy(tenant_a, version_number="1.0", status="archived", owner=admin_user,
                      created_by=admin_user,
                      published_at=timezone.now() - datetime.timedelta(days=400),
                      effective_from=timezone.localdate() - datetime.timedelta(days=400))


@pytest.fixture
def dk_policy_published_a(db, tenant_a, admin_user, usd, org_unit_a, dk_policy_v1_archived_a,
                          dk_document_active_a):
    """v2.0, PUBLISHED, pointing back at the archived v1.0 - "a published policy with an archived
    predecessor". Carries the advisory threshold (25,000 USD per purchase order), an org-unit
    scope and the controlled PDF, so the register's four joins all have something to read."""
    return _dk_policy(tenant_a, version_number="2.0", status="published",
                      previous_version=dk_policy_v1_archived_a, owner=admin_user,
                      created_by=admin_user, applies_to=org_unit_a,
                      document=dk_document_active_a,
                      published_at=timezone.now() - datetime.timedelta(days=30),
                      effective_from=timezone.localdate() - datetime.timedelta(days=30),
                      next_review_on=timezone.localdate() + datetime.timedelta(days=180),
                      threshold_amount=Decimal("25000.00"),
                      threshold_basis="per_purchase_order", threshold_currency=usd,
                      requires_acknowledgment=True)


@pytest.fixture
def dk_policy_draft_a(db, tenant_a, admin_user, dk_policy_published_a):
    """v3.0, DRAFT, pointing at the PUBLISHED v2.0. Publishing this one must archive v2.0 - the
    predecessor-retirement regression - and write two audit rows."""
    return _dk_policy(tenant_a, version_number="3.0", status="draft",
                      previous_version=dk_policy_published_a, owner=admin_user,
                      created_by=admin_user,
                      effective_from=timezone.localdate() + datetime.timedelta(days=7))


@pytest.fixture
def dk_policy_review_due_a(db, tenant_a, admin_user):
    """``next_review_on`` yesterday - ``is_review_due`` True, counted by ``stats.review_due`` and
    matched by ``?review=due``. A different TITLE, so the (tenant, title, version) constraint
    stays clear of the v1/v2/v3 chain."""
    return _dk_policy(tenant_a, title="Supplier Code of Conduct",
                      policy_type="supplier_code_of_conduct", version_number="1.0",
                      status="published", owner=admin_user, created_by=admin_user,
                      published_at=timezone.now() - datetime.timedelta(days=365),
                      next_review_on=timezone.localdate() - datetime.timedelta(days=1))


@pytest.fixture
def dk_attestation_a(db, tenant_a, admin_user, dk_policy_published_a):
    """One 6.17 ``PolicyAttestation`` against the published policy. It CASCADEs, which is why
    ``ppolicy_delete`` refuses while any exists - the guard this fixture is here to prove."""
    from apps.procurement.models import PolicyAttestation
    return PolicyAttestation.objects.create(
        tenant=tenant_a, policy=dk_policy_published_a, user=admin_user,
        due_on=timezone.localdate() + datetime.timedelta(days=14))


@pytest.fixture
def dk_policy_b(db, tenant_b, admin_b):
    """Tenant B's policy - the cross-tenant 404 target on detail / edit / delete / publish /
    archive, and the crafted-POST target for ``previous_version``."""
    return _dk_policy(tenant_b, title="Globex Purchasing Rule", policy_type="purchasing_rule",
                      status="published", owner=admin_b, created_by=admin_b,
                      published_at=timezone.now())


# -- knowledge resources ---------------------------------------------------------------------------

@pytest.fixture
def dk_resource_featured_a(db, tenant_a, admin_user, dk_document_active_a):
    """Published AND featured - the only state that reaches the "start here" shelf."""
    return _dk_resource(tenant_a, title="RFP template - IT services", resource_type="rfp_template",
                        category="it_software", audience="buyer", status="published",
                        is_featured=True, owner=admin_user, created_by=admin_user,
                        document=dk_document_active_a, tags="rfp, it")


@pytest.fixture
def dk_resource_published_a(db, tenant_a, admin_user):
    """Published, NOT featured - the ``?featured=False`` half of the facet."""
    return _dk_resource(tenant_a, title="Sourcing checklist - facilities",
                        resource_type="checklist", category="facilities", audience="all",
                        status="published", owner=admin_user, created_by=admin_user,
                        tags="checklist, facilities")


@pytest.fixture
def dk_resource_draft_a(db, tenant_a, admin_user):
    """Draft - the publish verb's target."""
    return _dk_resource(tenant_a, title="Negotiation playbook - draft",
                        resource_type="negotiation_playbook", category="general",
                        audience="buyer", owner=admin_user, created_by=admin_user,
                        tags="playbook")


@pytest.fixture
def dk_resource_archived_a(db, tenant_a, admin_user):
    """Archived - the "use this" verb REFUSES it (and leaves the counter alone); publish is
    still allowed, because guidance comes back into circulation."""
    return _dk_resource(tenant_a, title="Retired evaluation scorecard",
                        resource_type="evaluation_scorecard", category="other",
                        audience="approver", status="archived", owner=admin_user,
                        created_by=admin_user, tags="scorecard")


@pytest.fixture
def dk_resource_used_a(db, tenant_a, admin_user):
    """Published with ``usage_count == 7`` - one press must make it exactly 8, and it is one of
    the rows behind ``stats.used`` (rows WITH a press, not the sum of presses)."""
    return _dk_resource(tenant_a, title="Freight negotiation playbook",
                        resource_type="negotiation_playbook", category="logistics",
                        audience="buyer", status="published", owner=admin_user,
                        created_by=admin_user, tags="playbook, logistics",
                        usage_count=7, last_used_at=timezone.now() - datetime.timedelta(days=2))


@pytest.fixture
def dk_resource_review_due_a(db, tenant_a, admin_user):
    """``review_on`` yesterday - ``is_review_due`` True. This register offers NO ``?review=``
    facet and no review stat tile; the badge is the whole surface."""
    return _dk_resource(tenant_a, title="How-to guide overdue for review", resource_type="guide",
                        category="general", audience="all", status="published",
                        owner=admin_user, created_by=admin_user,
                        review_on=timezone.localdate() - datetime.timedelta(days=1))


@pytest.fixture
def dk_resource_b(db, tenant_b, admin_b):
    """Tenant B's resource - the cross-tenant 404 target on detail / edit / delete / publish /
    archive / use."""
    return _dk_resource(tenant_b, title="Globex sourcing guide", resource_type="guide",
                        category="general", status="published", owner=admin_b,
                        created_by=admin_b)
