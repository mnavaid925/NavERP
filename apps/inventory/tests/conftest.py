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


# ---- 5.10 Returns Management (RMA) -----------------------------------------------------------

@pytest.fixture
def customer_party_a(db, tenant_a):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Customer Corp", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="customer")
    return party


@pytest.fixture
def customer_party_b(db, tenant_b):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Customer LLC", kind="organization")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="customer")
    return party


@pytest.fixture
def rma_a(db, tenant_a, customer_party_a):
    from apps.scm.models import ReturnAuthorization
    return ReturnAuthorization.objects.create(
        tenant=tenant_a, customer=customer_party_a, return_type="physical", status="received"
    )


@pytest.fixture
def rma_b(db, tenant_b, customer_party_b):
    from apps.scm.models import ReturnAuthorization
    return ReturnAuthorization.objects.create(
        tenant=tenant_b, customer=customer_party_b, return_type="physical", status="received"
    )


@pytest.fixture
def rma_line_a(db, tenant_a, rma_a, item_a):
    from apps.scm.models import ReturnLine
    return ReturnLine.objects.create(
        tenant=tenant_a, return_authorization=rma_a, item=item_a, quantity_authorized=Decimal("2.0000"),
        quantity_received=Decimal("2.0000"), unit_price=Decimal("12.00"), unit_cost=Decimal("8.00")
    )


@pytest.fixture
def rma_line_b(db, tenant_b, rma_b, item_b):
    from apps.scm.models import ReturnLine
    return ReturnLine.objects.create(
        tenant=tenant_b, return_authorization=rma_b, item=item_b, quantity_authorized=Decimal("1.0000"),
        quantity_received=Decimal("1.0000"), unit_price=Decimal("9.00"), unit_cost=Decimal("5.00")
    )


@pytest.fixture
def disposition_rule_a(db, tenant_a, item_a, location_a):
    from apps.inventory.models import DispositionRoutingRule
    return DispositionRoutingRule.objects.create(
        tenant=tenant_a, name="Acme Grade A Restock", item=item_a, condition_grade="a",
        suggested_disposition="restock", destination_location=location_a, priority=10, is_active=True
    )


@pytest.fixture
def disposition_rule_b(db, tenant_b, item_b, location_b):
    from apps.inventory.models import DispositionRoutingRule
    return DispositionRoutingRule.objects.create(
        tenant=tenant_b, name="Globex Grade A Restock", item=item_b, condition_grade="a",
        suggested_disposition="restock", destination_location=location_b, priority=10, is_active=True
    )


@pytest.fixture
def inspection_a(db, tenant_a, rma_a, rma_line_a, item_a):
    from apps.inventory.models import ReturnInspection
    return ReturnInspection.objects.create(
        tenant=tenant_a, return_authorization=rma_a, return_line=rma_line_a, item=item_a,
        quantity=Decimal("2.0000"), packaging_condition="intact", completeness="complete",
        functional_status="pass", cosmetic_condition="new", condition_grade="a",
        is_restock_eligible=True, status="passed"
    )


@pytest.fixture
def inspection_b(db, tenant_b, rma_b, rma_line_b, item_b):
    from apps.inventory.models import ReturnInspection
    return ReturnInspection.objects.create(
        tenant=tenant_b, return_authorization=rma_b, return_line=rma_line_b, item=item_b,
        quantity=Decimal("1.0000"), packaging_condition="opened", completeness="complete",
        functional_status="pass", cosmetic_condition="minor_wear", condition_grade="b",
        is_restock_eligible=True, status="passed"
    )


# ---- 5.9 Order Management & Fulfillment (Waves) --------------------------------------------------
#
# FROZEN CONTRACT — every 5.9 test writer MUST use exactly these names and nothing else:
#
#   Model     : FulfillmentWave [WAV-] (TenantNumbered) — status planned/released/closed/
#               cancelled (default "planned", editable=False). Lifecycle moves ONLY through
#               the verbs release(user) [planned->released, refuses zero-member waves],
#               close(user) [released->closed] and cancel(user) [planned|released->
#               cancelled]; all three are tenant-admin-only at the VIEW layer
#               (@tenant_admin_required, @require_POST). Header fields: description /
#               location (FK scm.Location, related_name="inventory_waves") / carrier
#               (FK scm.Carrier) / ship_method (economy|standard|expedited) /
#               planned_ship_date / cutoff_at / priority / criteria_text / notes;
#               released_at + closed_at are system-set by the verbs.
#               FULFILLED_STATUSES = ("partially_fulfilled", "fulfilled", "invoiced",
#               "closed") — frozen from scm.SalesOrder.STATUS_CHOICES; "cancelled" is
#               deliberately NOT progress. orders_fulfilled_count reads members through it.
#               Pick linkage is a TEXT CONVENTION: scm.PickTask.wave_ref == wave.number
#               (case-sensitive), PICK_DONE_STATUSES = ("picked", "packed");
#               pick_progress_pct answers None (never a flattering 0%) when no picks match;
#               linked_picks() -> newest-first queryset over the matched tasks.
#   Child     : FulfillmentWaveOrder — tenant / wave (related_name="orders") /
#               sales_order (PROTECT, related_name="inventory_wave_orders") / added_by /
#               created_at; unique_together ("wave", "sales_order"). Membership LOCKS once
#               the wave leaves "planned" (model clean() raises on "__all__" — non-form
#               writers included). The FORM rejects a duplicate member with an "__all__"
#               error ("That sales order is already in this wave.") because validate_unique
#               skips constraints whose fields are not on the form ("wave" never is).
#   Urls      : inventory:wave_list         /inventory/waves/
#               inventory:wave_create      /inventory/waves/add/
#               inventory:wave_detail      /inventory/waves/<pk>/
#               inventory:wave_edit        /inventory/waves/<pk>/edit/
#               inventory:wave_delete      /inventory/waves/<pk>/delete/    (POST)
#               inventory:wave_release     /inventory/waves/<pk>/release/   (POST)
#               inventory:wave_close       /inventory/waves/<pk>/close/     (POST)
#               inventory:wave_cancel      /inventory/waves/<pk>/cancel/    (POST)
#               inventory:waveorder_add    /inventory/waves/<pk>/orders/add/  (POST)
#               inventory:waveorder_remove /inventory/waves/<pk>/orders/remove/<member pk>/ (POST)
#               inventory:wave_board       /inventory/waves-board/
#   Context   : wave_list   -> object_list (waves annotated member_count; each row also
#                              carries a precomputed .pick_pct) + page_obj + q +
#                              status_choices + status + is_admin.
#               wave_detail -> obj + members + linked_picks + add_form (None unless admin
#                              AND wave still planned) + is_admin + pick_pct.
#               wave_board  -> object_list = row DICTS {wave, members, fulfilled,
#                              pick_pct} + page_obj + stats{open_waves, released_today,
#                              unassigned_orders} + status_choices + status + locations +
#                              location + q + is_admin.
#
# Fixtures below give every lane an owned PLANNED wave with a member, a REAL-released wave
# (release() actually ran, so released_at is stamped), open sales orders to wave, and a
# foreign-workspace mirror.


def _fulfillment_carrier(tenant, name):
    """A minimal ACTIVE scm.Carrier on a get_or_create'd vendor-role core.Party (4.6 shape:
    a carrier is a TMS profile on a Party, never a standalone company row)."""
    from apps.core.models import Party, PartyRole
    from apps.scm.models import Carrier
    party, _created = Party.objects.get_or_create(
        tenant=tenant, name=name, defaults={"kind": "organization"})
    PartyRole.objects.get_or_create(tenant=tenant, party=party, role="vendor")
    carrier, _created = Carrier.objects.get_or_create(tenant=tenant, party=party)
    return carrier


def _fulfillment_sales_order(customer, item):
    """An OPEN (submitted) scm.SalesOrder with one line; totals derived via recalc_totals()."""
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(
        tenant=customer.tenant, customer=customer, status="submitted",
        source_channel="manual", order_date=datetime.date(2026, 8, 21))
    SalesOrderLine.objects.create(
        sales_order=order, item=item, quantity_ordered=Decimal("4"),
        unit_price=Decimal("15.00"))
    order.recalc_totals()
    return order


@pytest.fixture
def fulfillment_loc_wave_a(db, tenant_a):
    """The warehouse wave_a ships from (get_or_create-safe by the spine's (tenant, code))."""
    return _receiving_location(tenant_a, "FWH-A", location_type="warehouse")


@pytest.fixture
def fulfillment_loc_wave_b(db, tenant_b):
    """Globex's warehouse — foreign-workspace mirror of FWH-A."""
    return _receiving_location(tenant_b, "FWH-B", location_type="warehouse")


@pytest.fixture
def fulfillment_carrier_a(db, tenant_a):
    """Minimal active truckload carrier, tenant_a."""
    return _fulfillment_carrier(tenant_a, "Acme Wave Freight")


@pytest.fixture
def fulfillment_carrier_b(db, tenant_b):
    """Minimal active truckload carrier, tenant_b — the cross-tenant rejection target."""
    return _fulfillment_carrier(tenant_b, "Globex Wave Freight")


@pytest.fixture
def fulfillment_so_open_a(db, tenant_a, customer_party_a, item_a):
    """First open (submitted) sales order — waveable stock for the planned wave."""
    return _fulfillment_sales_order(customer_party_a, item_a)


@pytest.fixture
def fulfillment_so_second_a(db, tenant_a, customer_party_a, item_a):
    """Second open sales order — the released wave's member."""
    return _fulfillment_sales_order(customer_party_a, item_a)


@pytest.fixture
def fulfillment_wave_planned_a(db, tenant_a, fulfillment_loc_wave_a, fulfillment_carrier_a):
    """A still-PLANNED Acme wave — membership open, verbs pending, description set."""
    from apps.inventory.models import FulfillmentWave
    return FulfillmentWave.objects.create(
        tenant=tenant_a, description="August backlog wave",
        location=fulfillment_loc_wave_a, carrier=fulfillment_carrier_a,
        ship_method="standard", priority=50,
        criteria_text="All submitted Midwest orders under 20 kg")


@pytest.fixture
def fulfillment_member_a(db, tenant_a, admin_user, fulfillment_wave_planned_a,
                         fulfillment_so_open_a):
    """so_open travelling in the planned wave — the detail page's owned membership row."""
    from apps.inventory.models import FulfillmentWaveOrder
    return FulfillmentWaveOrder.objects.create(
        tenant=tenant_a, wave=fulfillment_wave_planned_a,
        sales_order=fulfillment_so_open_a, added_by=admin_user)


@pytest.fixture
def fulfillment_wave_released_a(db, tenant_a, admin_user, fulfillment_loc_wave_a,
                                fulfillment_carrier_a, fulfillment_so_second_a):
    """A REALLY released wave — release() itself ran (refuses empty waves, hence the
    member), so released_at is stamped and today's board stat counts it."""
    from apps.inventory.models import FulfillmentWave, FulfillmentWaveOrder
    wave = FulfillmentWave.objects.create(
        tenant=tenant_a, description="Friday parcel sweep",
        location=fulfillment_loc_wave_a, carrier=fulfillment_carrier_a,
        ship_method="expedited", priority=100)
    FulfillmentWaveOrder.objects.create(
        tenant=tenant_a, wave=wave, sales_order=fulfillment_so_second_a, added_by=admin_user)
    return wave.release(admin_user)


@pytest.fixture
def fulfillment_foreign_wave_b(db, tenant_b, fulfillment_loc_wave_b, fulfillment_carrier_b):
    """Globex's own planned wave — the foreign-workspace control for IDOR/guard lanes."""
    from apps.inventory.models import FulfillmentWave
    return FulfillmentWave.objects.create(
        tenant=tenant_b, description="Globex outbound batch",
        location=fulfillment_loc_wave_b, carrier=fulfillment_carrier_b,
        ship_method="standard")

