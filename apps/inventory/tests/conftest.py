"""Inventory test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b, client_a,
client_b, member_user) and adds the 5.1 catalog layer around SCM 4.3's item spine:
``scm.Item`` masters (one per tenant), then one ``ItemAttribute`` / ``ItemPrice`` /
``ProductFile`` row per tenant so list/detail/IDOR tests have both an owned and a
foreign target.
"""
from decimal import Decimal

import datetime

import pytest
from django.utils import timezone


@pytest.fixture
def item_a(db, tenant_a):
    """A stock item master on the SCM spine, tenant_a, with a cost basis."""
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant_a, sku="CAT-1", name="Catalog Widget", standard_cost=Decimal("8.00"),
    )


@pytest.fixture
def item_b(db, tenant_b):
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant_b, sku="CAT-1", name="Globex Catalog Widget", standard_cost=Decimal("5.00"),
    )


@pytest.fixture
def attribute_a(db, tenant_a, item_a):
    from apps.inventory.models import ItemAttribute
    return ItemAttribute.objects.create(
        tenant=tenant_a, item=item_a, name="Color", value="Industrial Blue", sequence=10,
    )


@pytest.fixture
def attribute_b(db, tenant_b, item_b):
    from apps.inventory.models import ItemAttribute
    return ItemAttribute.objects.create(
        tenant=tenant_b, item=item_b, name="Color", value="Safety Yellow", sequence=10,
    )


@pytest.fixture
def price_a(db, tenant_a, item_a):
    """A retail price row for item_a — $12.00 against an $8.00 standard cost."""
    from apps.inventory.models import ItemPrice
    return ItemPrice.objects.create(
        tenant=tenant_a, item=item_a, price_type="retail", unit_price=Decimal("12.00"),
    )


@pytest.fixture
def price_b(db, tenant_b, item_b):
    from apps.inventory.models import ItemPrice
    return ItemPrice.objects.create(
        tenant=tenant_b, item=item_b, price_type="retail", unit_price=Decimal("9.00"),
    )


@pytest.fixture
def product_file_a(db, tenant_a, item_a):
    """A linked photo marked as item_a's cover."""
    from apps.inventory.models import ProductFile
    return ProductFile.objects.create(
        tenant=tenant_a, item=item_a, kind="photo", title="Widget photo",
        url="https://files.example.com/catalog/cat-1/photo.jpg", is_primary=True,
    )


@pytest.fixture
def product_file_b(db, tenant_b, item_b):
    from apps.inventory.models import ProductFile
    return ProductFile.objects.create(
        tenant=tenant_b, item=item_b, kind="manual", title="Globex manual",
        url="https://files.example.com/catalog/globex/manual.pdf",
    )


# ---- 5.2 Vendor / Supplier Management ---------------------------------------------------------

@pytest.fixture
def vendor_party_a(db, tenant_a):
    """A supplier-role core.Party on the spine, tenant_a."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Supplies Ltd", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="supplier")
    return party


@pytest.fixture
def vendor_party_b(db, tenant_b):
    """A vendor-role core.Party, tenant_b — the foreign target for IDOR/guard tests."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Vendors Inc", kind="organization")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="vendor")
    return party


@pytest.fixture
def communication_a(db, tenant_a, vendor_party_a):
    """An overdue follow-up call logged against vendor_party_a."""
    import datetime

    from apps.inventory.models import VendorCommunication
    return VendorCommunication.objects.create(
        tenant=tenant_a, party=vendor_party_a, channel="call", direction="outbound",
        subject="Quarterly capacity check",
        body="Asked for a revised lead-time commitment.",
        occurred_at=datetime.datetime(2026, 8, 10, 10, 0),
        follow_up_on=datetime.date(2026, 8, 15),  # past → overdue badge/chip
    )


@pytest.fixture
def communication_b(db, tenant_b, vendor_party_b):
    from apps.inventory.models import VendorCommunication
    return VendorCommunication.objects.create(
        tenant=tenant_b, party=vendor_party_b, channel="email", direction="inbound",
        subject="Revised price list",
        body="Their 3% increase lands in January.",
    )


# ---- 5.3 Purchase Order (PO) Management --------------------------------------------------------

@pytest.fixture
def location_a(db, tenant_a):
    """A stock location on the SCM spine, tenant_a."""
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_a, code="DOCK-1", name="Receiving dock")


@pytest.fixture
def approval_rule_std_a(db, tenant_a):
    """Standard band: 0-10,000 inclusive/exclusive, ONE tier."""
    from apps.inventory.models import PurchaseOrderApprovalRule
    return PurchaseOrderApprovalRule.objects.create(
        tenant=tenant_a, name="Standard purchases",
        min_amount=Decimal("0"), max_amount=Decimal("10000"), tier_count=1)


@pytest.fixture
def approval_rule_cap_a(db, tenant_a):
    """Capital band: 100,000+, THREE tiers — the multi-tier path."""
    from apps.inventory.models import PurchaseOrderApprovalRule
    return PurchaseOrderApprovalRule.objects.create(
        tenant=tenant_a, name="Capital purchases",
        min_amount=Decimal("100000"), max_amount=None, tier_count=3)


def _make_po(tenant, vendor, *, status, quantity, unit_price, notes=""):
    """A spine purchase order with one line; totals derived via recalc_totals()."""
    from apps.scm.models import PurchaseOrder, PurchaseOrderLine
    po = PurchaseOrder(
        tenant=tenant, vendor=vendor, order_date=datetime.date(2026, 8, 20),
        status=status, notes=notes)
    po.save()
    PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Probe rig", sku_hint="PRB-1",
        quantity=Decimal(quantity), unit_price=Decimal(unit_price))
    po.recalc_totals()
    if po.status != status:
        po.status = status
        po.save(update_fields=["status", "updated_at"])
    return po


@pytest.fixture
def po_pending_a(db, tenant_a, admin_user, vendor_party_a):
    """A pending_approval order worth 250,000 -> resolves to the 3-tier Capital rule."""
    return _make_po(tenant_a, vendor_party_a, status="pending_approval",
                    quantity="5", unit_price="50000.00")


@pytest.fixture
def po_sent_a(db, tenant_a, admin_user, vendor_party_a):
    """An already-sent small order (dispatchable, but no approved->sent flip left to do)."""
    return _make_po(tenant_a, vendor_party_a, status="sent",
                    quantity="2", unit_price="100.00")


@pytest.fixture
def tier_decision_a(db, tenant_a, admin_user, po_pending_a, approval_rule_cap_a):
    """Tier 1 of the big order already cleared by the admin."""
    import django.utils

    from apps.inventory.models import PurchaseOrderApproval
    return PurchaseOrderApproval.objects.create(
        tenant=tenant_a, purchase_order=po_pending_a, rule=approval_rule_cap_a,
        tier=1, decision="approved", decided_by=admin_user,
        decided_at=django.utils.timezone.now(), note="looks fine")


@pytest.fixture
def po_dispatch_a(db, tenant_a, po_sent_a):
    """One recorded email transmission of the sent order."""
    import django.utils

    from apps.inventory.models import PurchaseOrderDispatch
    return PurchaseOrderDispatch.objects.create(
        tenant=tenant_a, purchase_order=po_sent_a, channel="email",
        recipient="orders@acmesupplies.example.com", reference="MSG-PO-1",
        dispatched_at=django.utils.timezone.now())


@pytest.fixture
def reorder_below_a(db, tenant_a, item_a, location_a):
    """An active reorder rule whose point is far above on-hand -> always a suggestion."""
    from decimal import Decimal

    from apps.scm.models import ReorderRule
    return ReorderRule.objects.create(
        tenant=tenant_a, item=item_a, location=location_a,
        reorder_point=Decimal("999999"), safety_stock=Decimal("10"),
        reorder_quantity=Decimal("0"))


# ---- 5.4 Receiving & Putaway -------------------------------------------------------------------
#
# FROZEN CONTRACT — pinned by the solo contract step; every 5.4 test writer MUST use exactly
# these names and nothing else:
#
#   Model     : PutawayRule — fields item / category / source_location / destination /
#               priority / is_active / notes (destination required, rest nullable;
#               overlapping rules legal — no unique_together). Tier constants
#               TIER_ITEM=3 > TIER_CATEGORY=2 > TIER_ANY=1.
#   Resolver  : resolve_putaway_suggestion(task, *, rules=None, by_pk=None, on_hand=None)
#               -> (suggestion | None, reason, candidates); refusals start
#               "No Suggestion Found"; when non-empty candidates[0] IS the suggestion;
#               keyword-only optional batch kwargs (bare call = self-loading).
#   Form      : PutawayRuleForm.Meta.fields == ["item", "category", "source_location",
#               "destination", "priority", "is_active", "notes"] — exactly 7.
#   Urls      : inventory:putawayrule_list      /inventory/putaway-rules/
#               inventory:putawayrule_create   /inventory/putaway-rules/add/
#               inventory:putawayrule_detail   /inventory/putaway-rules/<pk>/
#               inventory:putawayrule_edit     /inventory/putaway-rules/<pk>/edit/
#               inventory:putawayrule_delete   /inventory/putaway-rules/<pk>/delete/
#               inventory:putaway_suggestions  /inventory/putaway-suggestions/
#   Context   : putaway_suggestions -> rows[{task, receipt, item, staging, candidates,
#               suggestion, suggestion_reason}], stats{open_tasks, covered_by_rule,
#               uncovered}, warehouses, q, warehouse, page_obj.
#               Rule CRUD via core.crud -> list: object_list + page_obj + q +
#               is_admin + is_active_choices + is_active; detail: obj + is_admin;
#               create/edit: form + is_edit (+ obj when editing).
#
# Fixtures below build ONE scm.Location tree per tenant (warehouse › dock › bin) so models,
# forms, views and security lanes all have an owned target and a foreign one.


def _receiving_location(tenant, code, **fields):
    """get_or_create-safe by the spine's (tenant, code) uniqueness."""
    from apps.scm.models import Location
    loc, _created = Location.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": f"Area {code}", **fields})
    return loc


@pytest.fixture
def receiving_loc_warehouse_a(db, tenant_a):
    """The Acme warehouse row the whole 5.4 tree hangs under."""
    return _receiving_location(tenant_a, "RWH-A", location_type="warehouse")


@pytest.fixture
def receiving_loc_dock_a(db, tenant_a, receiving_loc_warehouse_a):
    """A non-pickable staging dock inside the warehouse — where arrivals sit."""
    return _receiving_location(
        tenant_a, "RDOCK-A", location_type="staging",
        parent=receiving_loc_warehouse_a, is_pickable=False)


@pytest.fixture
def receiving_loc_bin_a(db, tenant_a, receiving_loc_warehouse_a):
    """A pickable storage bin (declared capacity, walk sequence 10) — the rule's target."""
    return _receiving_location(
        tenant_a, "RA-01", location_type="bin", parent=receiving_loc_warehouse_a,
        capacity=Decimal("1000.00"), pick_sequence=10)


@pytest.fixture
def receiving_rule_a(db, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a):
    """Item-scoped (tier-3) rule: item_a arriving RDOCK-A goes to RA-01."""
    from apps.inventory.models import PutawayRule
    return PutawayRule.objects.create(
        tenant=tenant_a, item=item_a, source_location=receiving_loc_dock_a,
        destination=receiving_loc_bin_a, priority=10,
        notes="MON-27-style pinned-item routing for the receiving lane")


@pytest.fixture
def receiving_rule_catchall_a(db, tenant_a, receiving_loc_bin_a):
    """Tier-1 catch-all (no item/category/source): everything may land in RA-01."""
    from apps.inventory.models import PutawayRule
    return PutawayRule.objects.create(
        tenant=tenant_a, destination=receiving_loc_bin_a, priority=100,
        notes="Fallback routing for unclassified arrivals")


@pytest.fixture
def receiving_task_a(db, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a):
    """An OPEN scm.PutawayTask awaiting direction: 12 units staged at the dock."""
    from apps.scm.models import PutawayTask
    return PutawayTask.objects.create(
        tenant=tenant_a, item=item_a, from_location=receiving_loc_dock_a,
        to_location=receiving_loc_bin_a, quantity=Decimal("12"), status="pending")


@pytest.fixture
def receiving_loc_warehouse_b(db, tenant_b):
    """Globex's warehouse row — the foreign-workspace mirror of the A tree."""
    return _receiving_location(tenant_b, "RWH-B", location_type="warehouse")


@pytest.fixture
def receiving_loc_dock_b(db, tenant_b, receiving_loc_warehouse_b):
    """Globex's staging dock (mirror of RDOCK-A)."""
    return _receiving_location(
        tenant_b, "RDOCK-B", location_type="staging",
        parent=receiving_loc_warehouse_b, is_pickable=False)


@pytest.fixture
def receiving_loc_bin_b(db, tenant_b, receiving_loc_warehouse_b):
    """Globex's storage bin — the foreign target for cross-tenant isolation tests."""
    return _receiving_location(
        tenant_b, "RB-01", location_type="bin", parent=receiving_loc_warehouse_b,
        capacity=Decimal("1000.00"), pick_sequence=10)


@pytest.fixture
def receiving_foreign_rule_b(db, tenant_b, item_b, receiving_loc_dock_b, receiving_loc_bin_b):
    """tenant_b's own mirror rule (item_b → RB-01): must never leak into acme pages."""
    from apps.inventory.models import PutawayRule
    return PutawayRule.objects.create(
        tenant=tenant_b, item=item_b, source_location=receiving_loc_dock_b,
        destination=receiving_loc_bin_b, priority=10,
        notes="Globex-side routing — foreign workspace control")


# ---- 5.8 Lot & Serial Number Tracking ----------------------------------------------------------
#
# FROZEN CONTRACT — every 5.8 test writer MUST use exactly these names and nothing else:
#
#   Model     : LotNumberRule — fields name / item (nullable = tenant default) / kind
#               ("lot"|"serial") / prefix / include_date / sequence_padding / is_active /
#               notes; unique_together (tenant, name). Classmethods:
#               resolve(tenant, item) -> active rule or None (item rule beats default);
#               generate(user, item, *, expiry_date=None, notes="") -> scm.LotSerial
#               (refuses None/untracked/foreign/mismatched-kind items via ValidationError;
#               mints status="expired" when expiry already past).
#   Model     : ShelfLifePolicy — OneToOne item (+ related shelf_life_policy); fields
#               shelf_life_days / min_remaining_days / warning_days / fefo_enforced /
#               notes; clean() refuses warning_days < min_remaining_days.
#   Classifier: classify_lot(lot, policy, today=None) -> (code, css, label) with codes
#               exactly none/expired/blocked/warning/ok and css badge-muted/red/red/
#               amber/green.
#   Urls      : inventory:lotrule_list            /inventory/lot-rules/
#               inventory:lotrule_create          /inventory/lot-rules/add/
#               inventory:lot_generate            /inventory/lot-generate/
#               inventory:lotrule_detail/edit/delete  /inventory/lot-rules/<pk>[…]
#               inventory:shelflifepolicy_list/create/detail/edit/delete
#                                                 /inventory/shelf-life-policies[/…]
#               inventory:fefo_board              /inventory/fefo-board/
#               inventory:traceability            /inventory/traceability/?lot=<pk>
#   Context   : fefo_board -> object_list rows{item, lot, on_hand, policy, flag, css,
#               label, remaining} + q/flag_choices/items/counts/today/page_obj.
#               traceability -> picker mode {obj:None, lots[{lot,on_hand}], q};
#               trace mode {obj, on_hand, inbound, outbound, parents, children,
#               policy, flag, css, label, today}.
#               Rule/policy CRUD via core.crud -> list: object_list/page_obj/q(+extras);
#               detail: obj (+sample/recent_lots | lot_rows).

def _lot_tracked_item(tenant, sku):
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant, sku=sku, name=f"Batched {sku}", standard_cost=Decimal("6.00"),
        tracking="lot")


def _post_move(tenant, item, location, lot=None, quantity="4", move_type="receipt",
               reference="", reason=""):
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, lot_serial=lot,
        quantity=Decimal(quantity), unit_cost=Decimal("1"),
        move_type=move_type, reference=reference, reason=reason,
        moved_at=timezone.now())


@pytest.fixture
def tracked_item_a(db, tenant_a):
    return _lot_tracked_item(tenant_a, "LOT-A")


@pytest.fixture
def tracked_item_b(db, tenant_b):
    return _lot_tracked_item(tenant_b, "LOT-B")


@pytest.fixture
def lot_rule_default_a(db, tenant_a):
    from apps.inventory.models import LotNumberRule
    return LotNumberRule.objects.create(
        tenant=tenant_a, name="Default batch numbering", item=None, kind="lot",
        prefix="LOT", include_date=True, sequence_padding=5)


@pytest.fixture
def lot_rule_item_a(db, tenant_a, tracked_item_a):
    from apps.inventory.models import LotNumberRule
    return LotNumberRule.objects.create(
        tenant=tenant_a, name="Pinned batches", item=tracked_item_a, kind="lot",
        prefix="PINA", include_date=False, sequence_padding=3)


@pytest.fixture
def lot_rule_default_b(db, tenant_b):
    from apps.inventory.models import LotNumberRule
    return LotNumberRule.objects.create(
        tenant=tenant_b, name="Globex default", item=None, kind="lot",
        prefix="GBATCH", include_date=True, sequence_padding=4)


@pytest.fixture
def shelf_policy_a(db, tenant_a, tracked_item_a):
    from apps.inventory.models import ShelfLifePolicy
    return ShelfLifePolicy.objects.create(
        tenant=tenant_a, item=tracked_item_a, shelf_life_days=180,
        min_remaining_days=14, warning_days=45)


@pytest.fixture
def shelf_policy_b(db, tenant_b, tracked_item_b):
    from apps.inventory.models import ShelfLifePolicy
    return ShelfLifePolicy.objects.create(
        tenant=tenant_b, item=tracked_item_b, min_remaining_days=7, warning_days=20)


@pytest.fixture
def stocked_lot_a(db, tenant_a, tracked_item_a, location_a):
    """A dated lot holding 10 units at DOCK-1 — the FEFO board's owned row."""
    from apps.scm.models import LotSerial
    import datetime
    from django.utils import timezone

    lot = LotSerial.objects.create(
        tenant=tenant_a, item=tracked_item_a, number="LOTA-0001",
        expiry_date=timezone.localdate() + datetime.timedelta(days=30))
    _post_move(tenant_a, tracked_item_a, location_a, lot=lot, quantity="10")
    return lot


@pytest.fixture
def stocked_lot_b(db, tenant_b, tracked_item_b, location_b):
    """Foreign-workspace mirror lot — must never surface on acme pages."""
    from apps.scm.models import Location, LotSerial
    import datetime
    from django.utils import timezone

    loc, _ = Location.objects.get_or_create(
        tenant=tenant_b, code="DOCK-1", defaults={"name": "Receiving dock"})
    lot = LotSerial.objects.create(
        tenant=tenant_b, item=tracked_item_b, number="LOTB-0001",
        expiry_date=timezone.localdate() + datetime.timedelta(days=300))
    _post_move(tenant_b, tracked_item_b, loc, lot=lot, quantity="5")
    return lot


@pytest.fixture
def location_b(db, tenant_b):
    from apps.scm.models import Location
    loc, _ = Location.objects.get_or_create(
        tenant=tenant_b, code="BDOCK", defaults={"name": "Globex dock"})
    return loc
