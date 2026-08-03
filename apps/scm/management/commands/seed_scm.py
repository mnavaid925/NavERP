"""Seed Supply Chain Management (Module 4) demo data — sub-modules 4.1-4.9.

4.1 Procurement (below), 4.2 Supplier Relationship Management, 4.3 Inventory (the StockMove spine),
4.4 Warehouse Management, 4.5 Order Management, 4.6 Transportation, 4.7 Demand Planning, 4.8
Manufacturing and 4.9 Quality Management. The 4.3 pass must run before 4.4 and 4.5, and
that ordering is load-bearing rather than cosmetic: every putaway/pick/count row and every order
allocation references the items and locations 4.3 seeds.

Creates, per tenant, a walk down the whole procure-to-pay chain so every 4.1 page has something
real on it: an approved requisition (budget-checked), an RFQ sent to two suppliers with competing
quotes (one awarded), the purchase order that award produced, and a goods receipt three-way matched
against an ``accounting.Bill``.

Reuses the spine rather than inventing rows: suppliers are ``core.Party`` + ``PartyRole``, the
budget/GL accounts/currency/payment terms come from ``apps.accounting``, departments from
``core.OrgUnit``. Run after ``seed_core`` and ``seed_accounting``.

Idempotent: a tenant that already has a PurchaseRequisition is skipped, so a second run is a no-op
without ``--flush``.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Party, PartyRole, Tenant
from apps.accounting.models import Bill, BillLine, Budget, BudgetLine, Currency, GLAccount, PaymentTerm
from apps.scm.models import (
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    RFQ,
    RFQLine,
    RFQQuote,
    RFQQuoteLine,
    RFQVendor,
)

User = get_user_model()

SUPPLIERS = [
    ("Northwind Industrial Supply", "organization"),
    ("Cascade Components Ltd", "organization"),
]

# (description, sku, uom, qty, est_unit_price)
REQUISITION_LINES = [
    ("Laptop workstation, 16GB RAM", "WS-16", "each", Decimal("5"), Decimal("1250.00")),
    ("Docking station, USB-C", "DOCK-C", "each", Decimal("5"), Decimal("180.00")),
    ("27-inch monitor", "MON-27", "each", Decimal("10"), Decimal("310.00")),
]


class Command(BaseCommand):
    help = ("Seed SCM 4.1 procurement + 4.2 SRM + 4.3 inventory + 4.4 warehouse + 4.5 orders + "
            "4.6 transportation + 4.7 demand planning + 4.8 manufacturing + 4.9 quality + "
            "4.10 returns + 4.11 analytics + 4.12 contract & compliance + 4.13 asset management "
            "demo data — idempotent (skips a tenant that already has the rows each pass creates).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help="Delete this module's rows for every tenant before seeding (destructive).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run `seed_core` first."))
            return

        for tenant in tenants:
            if PurchaseRequisition.objects.filter(tenant=tenant).exists():
                self.stdout.write(
                    f"{tenant.name}: procurement data already exists — skipping. Use --flush to re-seed.")
            else:
                self._seed_tenant(tenant)
            # 4.2 SRM and 4.3 Inventory are guarded independently so they seed even when 4.1 exists.
            self._seed_srm_tenant(tenant)
            self._seed_inventory_tenant(tenant)
            # 4.4 runs LAST: putaway/picks/counts all reference the items and locations that
            # _seed_inventory_tenant creates, so this ordering is a real dependency, not cosmetic.
            self._seed_warehouse_tenant(tenant)
            # 4.5 also depends on 4.3's items/locations (it reserves against them), so it follows.
            self._seed_oms_tenant(tenant)
            # 4.6 TMS follows 4.5/4.1: shipments link the seeded sales/purchase orders, and the
            # inbound delivered shipment gives the carrier scorecard a real on-time signal.
            self._seed_tms_tenant(tenant)
            # 4.7 LAST: it back-dates demand history onto 4.5's sales orders, fits a forecast on
            # that derived history, and recalculates 4.3's reorder rules — so every one of those
            # must already exist.
            self._seed_demand_planning_tenant(tenant)
            # 4.8 LAST: it builds a BOM over 4.3's items and CONSUMES their on-hand stock through
            # the real posting path, so every one of those rows must already exist.
            self._seed_manufacturing_tenant(tenant)
            # 4.9 LAST: it inspects 4.1's goods receipts, 4.3's items/locations/lots, 4.6's
            # shipments and 4.8's work orders, and it scraps real lot-tracked stock through the
            # ledger — so every one of those must already exist.
            self._seed_quality_tenant(tenant)
            # 4.10 LAST OF ALL: it returns goods against 4.5's sales orders, grades them on a
            # bench location from 4.3, restocks one through the REAL posting path (the only 4.10
            # ledger write), drafts a credit note against 4.2's accounting spine and raises a
            # warranty claim on a 4.1 supplier — so every one of those must already exist.
            self._seed_returns_tenant(tenant)
            # 4.11 LAST OF ALL, and this one genuinely has to be: it MEASURES every sub-module
            # above. It reads the stock ledger, the purchase orders and receipts, the shipments and
            # freight invoices, the sales orders, the quality findings and the returns — so each of
            # those must already be seeded or the snapshots freeze a network that is still empty.
            # It writes nothing back: no StockMove, no JournalEntry, no change to any 4.1-4.10 row.
            self._seed_analytics_tenant(tenant)
            # 4.12 AFTER 4.11, and after everything it points at: it hangs standing obligations off
            # 4.2's SupplierContract, raises trade documents against 4.6's shipments and carriers,
            # and its carbon report is computed over 4.6's Load.distance_km x Shipment.weight_kg —
            # which 4.6 stored expressly for this. It also back-fills the two columns 4.12 added to
            # 4.2's contracts (`owner` and the `parent_contract` amendment link), so those contracts
            # have to exist first. Like 4.11 it writes no StockMove and no JournalEntry.
            self._seed_compliance_tenant(tenant)
            # 4.13 AFTER 4.12, and it is the one pass since 4.10 that WRITES to the stock ledger
            # again — so its dependencies are real, not decorative. Its assets sit at 4.3's locations
            # and its conveyor serves one of 4.8's work centres; it flips 4.3 items to spare parts and
            # hangs the machines' parts lists off them; and the completed PM job draws those parts out
            # of 4.3's storeroom through the REAL _post_stock_move path under the new `maintenance`
            # move type. Every one of those rows must already exist, and like 4.9-4.12 it posts no
            # JournalEntry — the only ledger effect in the whole sub-module is that one stock issue.
            self._seed_asset_tenant(tenant)

        self.stdout.write(self.style.SUCCESS(
            "SCM 4.1 procurement + 4.2 SRM + 4.3 inventory + 4.4 warehouse + 4.5 orders + "
            "4.6 transportation + 4.7 demand planning + 4.8 manufacturing + 4.9 quality + "
            "4.10 returns + 4.11 analytics + 4.12 contract & compliance + 4.13 asset management "
            "seed complete."))
        self.stdout.write("Log in as a tenant admin (e.g. admin_acme / password) to view procurement data.")
        self.stdout.write(self.style.WARNING(
            "Superuser 'admin' has no tenant — SCM pages show no data when logged in as admin."))

    def _seed_srm_tenant(self, tenant):
        """4.2 SRM demo rows for a tenant — a profile/scorecard/contract/catalog/risk per supplier.

        Idempotent via a per-tenant SupplierProfile guard. Reuses the 4.1 suppliers (matched by name)
        rather than inventing new Party rows, and derives the scorecard from real 4.1 signals so the
        demo shows the signal path working, not a hand-typed number.
        """
        from apps.scm.models import (
            SupplierProfile, SupplierScorecard, SupplierContract, SupplierCatalog,
            SupplierCatalogItem, SupplierRiskAssessment,
        )
        if SupplierProfile.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: SRM data already exists — skipping.")
            return

        today = timezone.localdate()
        admin = self._admin(tenant)
        currency = Currency.objects.filter(code="USD").first()
        terms = PaymentTerm.objects.filter(tenant=tenant).order_by("id").first()
        suppliers = [self._supplier(tenant, name, kind) for name, kind in SUPPLIERS]

        tiers = ["strategic", "preferred"]
        for i, supplier in enumerate(suppliers):
            # Onboarding profile — first supplier fully approved with due diligence done, second in review.
            approved = i == 0
            profile = SupplierProfile(
                tenant=tenant, party=supplier, tier=tiers[i % len(tiers)],
                onboarding_status="approved" if approved else "due_diligence",
                category="Industrial supplies", legal_name=f"{supplier.name} LLC",
                primary_contact_name="A. Buyer", primary_contact_email="sales@example.com",
                country="United States", year_established=2008 + i,
                dd_financials_verified=True, dd_compliance_verified=True,
                dd_insurance_verified=approved, dd_quality_cert_verified=approved,
                dd_references_checked=approved,
                notes="Seeded SRM profile.",
            )
            if approved:
                profile.approved_by = admin
                profile.approved_at = timezone.now()
                profile.decision_note = "Qualified after due diligence."
            profile.save()

            # Scorecard for the last 90 days — derived from real 4.1 receipts/quotes where they exist.
            sc = SupplierScorecard(
                tenant=tenant, party=supplier, period_start=today - datetime.timedelta(days=90),
                period_end=today, status="draft",
            )
            sc.save()
            sc.recompute_from_signals(save=True)
            sc.status = "published"
            sc.save(update_fields=["status", "updated_at"])

            # A contract, the first one expiring soon so the renewal-alert path is visible.
            end = today + datetime.timedelta(days=20 if i == 0 else 300)
            contract = SupplierContract(
                tenant=tenant, party=supplier, title=f"{supplier.name} master agreement",
                contract_type="master", status="active",
                start_date=today - datetime.timedelta(days=340), end_date=end,
                contract_value=Decimal("50000.00"), currency=currency, payment_terms=terms,
                auto_renew=(i == 0), renewal_notice_days=30,
                terms_summary="Net 30. Prices held 12 months. Delivery DDP.",
                notes="Seeded contract.",
            )
            contract.save()
            contract.refresh_status()

            # A price-list catalog with a couple of free-text items.
            catalog = SupplierCatalog(
                tenant=tenant, party=supplier, name=f"{supplier.name} 2026 price list",
                currency=currency, valid_from=today - datetime.timedelta(days=30),
                valid_until=today + datetime.timedelta(days=335), status="active",
            )
            catalog.save()
            for name, sku, price in [("Laptop workstation", "WS-16", "1250.00"),
                                     ("27-inch monitor", "MON-27", "310.00")]:
                SupplierCatalogItem.objects.create(
                    catalog=catalog, item_name=name, sku=sku, uom="each",
                    unit_price=Decimal(price), lead_time_days=7 + i, min_order_qty=Decimal("1"),
                )

            # A risk assessment — second supplier carries a higher compliance flag.
            risk = SupplierRiskAssessment(
                tenant=tenant, party=supplier, assessment_date=today, status="reviewed",
                financial_score=2, geopolitical_score=1 + i,
                compliance_score=2 if approved else 4, operational_score=2,
                mitigation_plan="Quarterly review; require updated insurance certificate.",
                next_review_date=today + datetime.timedelta(days=180), assessed_by=admin,
            )
            risk.recompute_risk_level(save=False)
            risk.save()

        self.stdout.write(
            f"{tenant.name}: seeded SRM for {len(suppliers)} suppliers "
            f"(profiles, scorecards, contracts, catalogs, risk assessments)."
        )

    def _seed_inventory_tenant(self, tenant):
        """4.3 Inventory demo: UOMs, categories, items, locations, opening-balance StockMoves, a
        completed transfer, a posted adjustment, and reorder rules (one deliberately low so the
        reorder-alert path shows). Idempotent via a per-tenant Item guard. Exercises the derived
        on-hand path — nothing stores a quantity."""
        from apps.scm.models import (
            Item, ItemCategory, UOM, Location, StockMove, StockTransfer, StockTransferLine,
            StockAdjustment, StockAdjustmentLine, ReorderRule,
        )
        from apps.scm.views._helpers import _post_transfer, _post_adjustment, _post_stock_move
        if Item.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: inventory data already exists — skipping.")
            return

        each, _ = UOM.objects.get_or_create(tenant=tenant, code="EA", defaults={"name": "Each", "factor": 1})
        box, _ = UOM.objects.get_or_create(tenant=tenant, code="BOX", defaults={"name": "Box of 12", "factor": 12})
        cat = ItemCategory.objects.create(tenant=tenant, name="IT Equipment")

        # Items with different costing methods so the valuation report shows each path.
        items = [
            Item.objects.create(tenant=tenant, sku="WS-16", name="Laptop workstation 16GB", category=cat,
                                uom=each, costing_method="weighted_avg", standard_cost=Decimal("1200")),
            Item.objects.create(tenant=tenant, sku="MON-27", name="27-inch monitor", category=cat,
                                uom=each, costing_method="fifo", standard_cost=Decimal("300")),
            Item.objects.create(tenant=tenant, sku="DOCK-C", name="USB-C docking station", category=cat,
                                uom=box, costing_method="weighted_avg", standard_cost=Decimal("150")),
        ]
        main = Location.objects.create(tenant=tenant, code="WH-MAIN", name="Main Warehouse",
                                       location_type="warehouse")
        store = Location.objects.create(tenant=tenant, code="WH-STORE", name="Retail Store",
                                        location_type="warehouse")

        # Opening balances as receipt StockMoves through the posting service (rolls average cost).
        opening = [
            (items[0], main, Decimal("20"), Decimal("1200")),
            (items[1], main, Decimal("40"), Decimal("290")),   # a first FIFO layer
            (items[1], main, Decimal("15"), Decimal("330")),   # a second, dearer FIFO layer
            (items[2], main, Decimal("8"), Decimal("150")),
        ]
        now = timezone.now()
        with transaction.atomic():
            # Through the posting service like every other movement — not hand-rolled — so the
            # weighted-average roll follows the same path the app uses at runtime.
            for i, (item, loc, qty, cost) in enumerate(opening):
                _post_stock_move(tenant, item=item, location=loc, quantity=qty, unit_cost=cost,
                                 move_type="receipt", reference="OPENING",
                                 moved_at=now - datetime.timedelta(days=30 - i))

        # A completed transfer of 5 monitors main -> store, posting the paired moves.
        transfer = StockTransfer.objects.create(
            tenant=tenant, from_location=main, to_location=store, status="draft",
            transfer_date=timezone.localdate(), notes="Store replenishment.")
        StockTransferLine.objects.create(transfer=transfer, item=items[1], quantity=Decimal("5"))
        with transaction.atomic():
            _post_transfer(transfer, self._admin(tenant))
            transfer.status = "completed"
            transfer.completed_at = timezone.now()
            transfer.save(update_fields=["status", "completed_at", "updated_at"])

        # A posted cycle-count adjustment: found 2 extra docks at main.
        adj = StockAdjustment.objects.create(
            tenant=tenant, location=main, reason="cycle_count", status="draft",
            adjustment_date=timezone.localdate(), notes="Cycle count: found 2 extra docks.")
        StockAdjustmentLine.objects.create(adjustment=adj, item=items[2], quantity_delta=Decimal("2"),
                                           unit_cost=Decimal("150"))
        with transaction.atomic():
            _post_adjustment(adj, self._admin(tenant))
            adj.status = "posted"
            adj.posted_at = timezone.now()
            adj.save(update_fields=["status", "posted_at", "updated_at"])

        # Reorder rules — the dock rule sits above current on-hand so a reorder alert fires.
        ReorderRule.objects.create(tenant=tenant, item=items[0], location=main,
                                   reorder_point=Decimal("5"), safety_stock=Decimal("3"),
                                   reorder_quantity=Decimal("10"))
        ReorderRule.objects.create(tenant=tenant, item=items[2], location=main,
                                   reorder_point=Decimal("15"), safety_stock=Decimal("5"),
                                   reorder_quantity=Decimal("24"))

        self.stdout.write(
            f"{tenant.name}: seeded inventory ({len(items)} items, 2 locations, opening stock, "
            f"{transfer.number} transfer, {adj.number} adjustment, 2 reorder rules)."
        )

    def _seed_warehouse_tenant(self, tenant):
        """4.4 WMS demo: a completed putaway, a picked+packed task, a cycle count that reconciles
        into a real StockAdjustment, and a truck at a dock. Idempotent via a PutawayTask guard.

        Runs AFTER _seed_inventory_tenant because every row here references its items/locations.
        Posts through the real service helpers so the seed exercises the same path the app uses.
        """
        from apps.scm.models import (
            CycleCountTask, CycleCountTaskLine, Item, Location, PickTask, PickTaskLine,
            PutawayTask, StockAdjustment, StockAdjustmentLine, YardVisit,
        )
        from apps.scm.views._helpers import _post_putaway, _post_pick, _post_adjustment
        if PutawayTask.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: warehouse data already exists — skipping.")
            return

        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
        if main is None:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no seeded locations — skipping warehouse seed."))
            return
        admin = self._admin(tenant)
        today = timezone.localdate()

        # A pickable bin under the main warehouse, so slotting attributes actually show up.
        bin_a, _ = Location.objects.get_or_create(
            tenant=tenant, code="WH-MAIN-A1",
            defaults={"name": "Aisle A Bin 1", "location_type": "bin", "parent": main,
                      "pick_sequence": 10, "abc_class": "a", "capacity": Decimal("500")})
        door, _ = Location.objects.get_or_create(
            tenant=tenant, code="DOCK-1",
            defaults={"name": "Dock Door 1", "location_type": "staging", "parent": main,
                      "is_pickable": False})

        mon = Item.objects.filter(tenant=tenant, sku="MON-27").first()
        dock_item = Item.objects.filter(tenant=tenant, sku="DOCK-C").first()
        if not (mon and dock_item):
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: seeded items missing — skipping warehouse seed."))
            return

        # --- a completed putaway: 5 monitors off the main floor into bin A1 ------------------
        put = PutawayTask(tenant=tenant, item=mon, from_location=main, to_location=bin_a,
                          quantity=Decimal("5"), strategy="directed", status="pending",
                          assigned_to=admin, notes="Seeded putaway.")
        put.save()
        with transaction.atomic():
            _post_putaway(put, admin)
            put.status = "completed"
            put.completed_at = timezone.now()
            put.save(update_fields=["status", "completed_at", "updated_at"])

        # --- a picked + packed wave pulling 2 back out of that bin ---------------------------
        pick = PickTask(tenant=tenant, strategy="wave", status="released", zone=main,
                        wave_ref="WAVE-001", assigned_to=admin, ship_to="Acme retail store",
                        notes="Seeded pick.")
        pick.save()
        PickTaskLine.objects.create(pick_task=pick, item=mon, from_location=bin_a,
                                    quantity_requested=Decimal("2"), quantity_picked=Decimal("2"))
        with transaction.atomic():
            _post_pick(pick, admin)
            pick.status = "picked"
            pick.picked_at = timezone.now()
            pick.save(update_fields=["status", "picked_at", "updated_at"])
        pick.package_count = 1
        pick.package_weight = Decimal("12.500")
        pick.status = "packed"
        pick.packed_at = timezone.now()
        pick.save(update_fields=["package_count", "package_weight", "status", "packed_at",
                                 "updated_at"])

        # --- a cycle count that finds one dock short, reconciled into a real adjustment ------
        count = CycleCountTask(tenant=tenant, location=main, scheduled_date=today,
                               count_method="full", status="scheduled", assigned_to=admin,
                               notes="Seeded cycle count.")
        count.save()
        expected = dock_item.on_hand(location=main)
        line = CycleCountTaskLine.objects.create(
            cycle_count=count, item=dock_item, expected_quantity=expected,
            counted_quantity=expected - Decimal("1"))
        count.status = "counted"
        count.started_at = timezone.now()
        count.counted_at = timezone.now()
        count.save(update_fields=["status", "started_at", "counted_at", "updated_at"])
        with transaction.atomic():
            adj = StockAdjustment.objects.create(
                tenant=tenant, location=main, reason="cycle_count", status="draft",
                adjustment_date=today, notes=f"Generated from cycle count {count.number}.")
            StockAdjustmentLine.objects.create(
                adjustment=adj, item=dock_item, quantity_delta=line.variance,
                unit_cost=dock_item.average_cost or Decimal("0"))
            _post_adjustment(adj, admin)
            adj.status = "posted"
            adj.posted_at = timezone.now()
            adj.save(update_fields=["status", "posted_at", "updated_at"])
            count.adjustment = adj
            count.status = "reconciled"
            count.reconciled_at = timezone.now()
            count.save(update_fields=["adjustment", "status", "reconciled_at", "updated_at"])

        # --- a truck currently at a dock door -------------------------------------------------
        yard = YardVisit(tenant=tenant, carrier_name="Northbound Haulage", vehicle_ref="TRK-4471",
                         trailer_ref="TRL-88", driver_name="J. Rivera", direction="inbound",
                         dock_door=door, status="arrived", scheduled_at=timezone.now(),
                         notes="Seeded yard visit.")
        yard.save()
        yard.arrived_at = timezone.now()
        yard.status = "at_dock"
        yard.docked_at = timezone.now()
        yard.save(update_fields=["arrived_at", "status", "docked_at", "updated_at"])

        self.stdout.write(
            f"{tenant.name}: seeded warehouse ({put.number} putaway, {pick.number} pick, "
            f"{count.number} count -> {adj.number}, {yard.number} yard visit).")

    def _seed_oms_tenant(self, tenant):
        """4.5 OMS demo: three orders sitting at three different lifecycle points, so the order
        list, the credit-hold queue and the backorder queue each have something real on them.

        Idempotent via a SalesOrder guard. Runs after _seed_inventory_tenant because every
        allocation reserves against a real item at a real location.

        Note the deliberate asymmetry with 4.4's seeder: that one posts through the real service
        helpers because posting IS the behaviour being demonstrated. Here the interesting behaviour
        is the DERIVED state (allocated vs backordered vs held), so the rows are built directly and
        then run through the same recompute_allocation_status() the views call — which is what
        actually decides each order's status.
        """
        from apps.scm.models import Item, Location, SalesOrder, SalesOrderLine, SalesOrderAllocation
        if SalesOrder.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: order data already exists — skipping.")
            return

        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
        if main is None:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no seeded locations — skipping order seed."))
            return
        ws16 = Item.objects.filter(tenant=tenant, sku="WS-16").first()
        mon27 = Item.objects.filter(tenant=tenant, sku="MON-27").first()
        if ws16 is None or mon27 is None:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no seeded items — skipping order seed."))
            return

        today = timezone.localdate()
        currency = Currency.objects.filter(code="USD").first()
        terms = PaymentTerm.objects.filter(tenant=tenant).order_by("id").first()
        # A healthy credit limit for the ordinary customer, and a deliberately tiny one for the
        # customer whose order must land in the hold queue.
        good = self._customer(tenant, "Fabrikam Retail Group", "organization",
                              credit_limit=Decimal("15000.00"))
        tight = self._customer(tenant, "Contoso Discount Stores", "organization",
                               credit_limit=Decimal("500.00"))

        def _order(customer, channel, note):
            order = SalesOrder(
                tenant=tenant, customer=customer, source_channel=channel, order_date=today,
                requested_date=today + datetime.timedelta(days=7),
                currency=currency, payment_terms=terms, notes=note,
            )
            order.save()
            return order

        # 1) Fully allocated — reserves less than the 4.3 opening balance, so it covers cleanly.
        on_hand_ws = ws16.on_hand(location=main)
        qty1 = min(Decimal("5"), on_hand_ws) if on_hand_ws > 0 else Decimal("5")
        o1 = _order(good, "web", "Seeded: fully allocated order.")
        l1 = SalesOrderLine.objects.create(
            sales_order=o1, item=ws16, quantity_ordered=qty1, unit_price=Decimal("1450.00"),
            tax_pct=Decimal("8.00"))
        o1.recalc_totals()
        o1.status = "submitted"
        o1.confirmation_sent_at = timezone.now()
        o1.save(update_fields=["status", "confirmation_sent_at", "updated_at"])
        if qty1 > 0:
            SalesOrderAllocation.objects.create(
                tenant=tenant, sales_order_line=l1, location=main, quantity=qty1,
                notes="Seeded reservation.")
        o1.recompute_allocation_status()

        # 2) Backordered — deliberately orders MORE than is on hand at this one location, and
        #    reserves only what is actually there, so quantity_backordered() is genuinely non-zero
        #    rather than a hand-set status. This is what makes the Backorder queue real.
        on_hand_mon = mon27.on_hand(location=main)
        covered = on_hand_mon if on_hand_mon > 0 else Decimal("0")
        ordered2 = covered + Decimal("15")
        o2 = _order(good, "marketplace", "Seeded: partially covered, remainder on backorder.")
        l2 = SalesOrderLine.objects.create(
            sales_order=o2, item=mon27, quantity_ordered=ordered2, unit_price=Decimal("349.00"),
            tax_pct=Decimal("8.00"))
        o2.recalc_totals()
        o2.status = "submitted"
        o2.confirmation_sent_at = timezone.now()
        o2.save(update_fields=["status", "confirmation_sent_at", "updated_at"])
        if covered > 0:
            SalesOrderAllocation.objects.create(
                tenant=tenant, sales_order_line=l2, location=main, quantity=covered,
                notes="Seeded partial reservation — the rest is backordered.")
        o2.recompute_allocation_status()

        # 3) On credit hold — the total is well over Contoso's 500 limit, and the flags are set by
        #    the SAME evaluation the submit view runs, not typed in, so the demo shows the real rule.
        from apps.scm.views.OrderManagement.SalesOrders import _evaluate_hold
        o3 = _order(tight, "phone", "Seeded: held for credit review.")
        SalesOrderLine.objects.create(
            sales_order=o3, item=ws16, quantity_ordered=Decimal("2"),
            unit_price=Decimal("1450.00"), tax_pct=Decimal("8.00"))
        o3.recalc_totals()
        credit_hold, fraud_flag, reason = _evaluate_hold(o3)
        o3.credit_hold, o3.fraud_flag, o3.hold_reason = credit_hold, fraud_flag, reason
        o3.status = "on_hold" if (credit_hold or fraud_flag) else "submitted"
        o3.save(update_fields=["credit_hold", "fraud_flag", "hold_reason", "status", "updated_at"])

        self.stdout.write(
            f"{tenant.name}: seeded orders {o1.number} [{o1.get_status_display()}], "
            f"{o2.number} [{o2.get_status_display()}], {o3.number} [{o3.get_status_display()}].")

    # ---------------------------------------------------------------- 4.7 Demand Planning
    #: Monthly demand shape for the seeded history — a real Q4-peaking curve, so the derived
    #: seasonality indices and the statistical fit both have something honest to find.
    SEASONAL_SHAPE = [Decimal(s) for s in
                      ("0.80", "0.80", "0.90", "0.90", "1.00", "1.00",
                       "1.00", "1.05", "1.10", "1.20", "1.40", "1.50")]

    def _seed_demand_history(self, tenant, item, customer, months, base_qty, unit_price):
        """Back-date ``months`` of closed sales orders so demand history actually EXISTS.

        4.7 derives every history series from ``SalesOrderLine`` — it stores none of its own — and
        4.5's seeder only creates today's orders. Without a back-dated trail the forecast, the
        seasonality derivation and the safety-stock calculator would all correctly compute zero, and
        every 4.7 page would demo nothing. These are ordinary closed orders, so they flush with the
        rest of 4.5's rows and no 4.7-only history table is introduced.
        """
        from apps.scm.models import SalesOrder, SalesOrderLine
        today = timezone.localdate()
        created = 0
        for offset in range(months, 0, -1):
            total = today.year * 12 + (today.month - 1) - offset
            year, month = divmod(total, 12)
            order_date = datetime.date(year, month + 1, 12)
            factor = self.SEASONAL_SHAPE[month]
            # A gentle year-on-year lift so the trend engines have a slope to find.
            growth = Decimal("1") + Decimal("0.10") * Decimal((months - offset) // 12)
            quantity = (base_qty * factor * growth).quantize(Decimal("1"))
            order = SalesOrder(tenant=tenant, customer=customer, source_channel="web",
                               order_date=order_date, notes="Seeded demand history.")
            order.save()
            SalesOrderLine.objects.create(sales_order=order, item=item,
                                          quantity_ordered=quantity, unit_price=unit_price)
            order.recalc_totals()
            order.status = "closed"
            order.save(update_fields=["status", "updated_at"])
            created += 1
        return created

    def _seed_demand_planning_tenant(self, tenant):
        """4.7 Demand Planning demo: back-dated demand history, a seasonal curve and a promotion, an
        approved forecast driven through the REAL generate/consensus code paths, three signals at
        three triage points, three consensus adjustments, and reorder rules switched onto a
        service-level safety-stock policy with a calculated-but-not-applied recommendation.

        Idempotent via a DemandForecast guard. Runs last: it needs 4.3's items/locations/reorder
        rules and 4.5's sales orders to exist first.

        Everything is produced through the same methods the views call — ``generate_periods()``,
        ``apply_to_forecast()``, ``recompute_consensus()``, ``detect_order_surge()``,
        ``calculate()`` — so the demo data is exactly what the app would have produced, not
        hand-set fields that happen to look plausible.
        """
        from apps.scm.models import (DemandForecast, DemandForecastPeriod, DemandSignal,
                                     ForecastAdjustment, Item, Location, ReorderRule,
                                     SeasonalityIndex, SeasonalityProfile, SupplierCatalogItem)
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        from apps.scm.models.DemandPlanning._history import demand_series_map
        if DemandForecast.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: demand planning data already exists — skipping.")
            return

        ws16 = Item.objects.filter(tenant=tenant, sku="WS-16").first()
        mon27 = Item.objects.filter(tenant=tenant, sku="MON-27").first()
        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
        if ws16 is None or mon27 is None or main is None:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no seeded items/locations — skipping demand planning seed."))
            return

        admin = self._admin(tenant)
        today = timezone.localdate()
        currency = Currency.objects.filter(code="USD").first()
        customer = self._customer(tenant, "Fabrikam Retail Group", "organization")
        history_months = 24
        orders = self._seed_demand_history(tenant, ws16, customer, history_months,
                                           Decimal("20"), Decimal("1450.00"))
        orders += self._seed_demand_history(tenant, mon27, customer, history_months,
                                            Decimal("35"), Decimal("349.00"))

        # 1) A recurring seasonal curve, derived from the history that now exists.
        seasonal = SeasonalityProfile(tenant=tenant, name="Workstation Q4 seasonality",
                                      profile_type="seasonal", bucket="month", scope="item",
                                      item=ws16, derived_from_years=2,
                                      notes="Derived from two years of closed sales orders.")
        seasonal.save()
        for index, factor in enumerate(self.SEASONAL_SHAPE, start=1):
            SeasonalityIndex.objects.create(
                profile=seasonal, period_number=index,
                period_label=datetime.date(2000, index, 1).strftime("%b"), index_factor=factor)

        # 2) A finite promotional window — the SAME table, a different profile_type. Exercises the
        #    other half of the Seasonality Analysis bullet without a second model.
        promo_start = datetime.date(today.year, 11, 1) if today.month <= 11 else \
            datetime.date(today.year + 1, 11, 1)
        SeasonalityProfile.objects.create(
            tenant=tenant, name="Black Friday monitor promotion", profile_type="promotion",
            bucket="month", scope="item", item=mon27,
            event_start=promo_start, event_end=promo_start + datetime.timedelta(days=29),
            uplift_pct=Decimal("25.00"), promotion_mechanic="price_discount",
            cannibalization_pct=Decimal("10.00"), cannibalized_category=ws16.category,
            notes="Seeded: 25% uplift inside the window, 10% taken from the sibling category.")

        # 3) The plan of record — generated through the real code path, then submitted and approved.
        #    The horizon deliberately OPENS THREE MONTHS AGO and runs six months, so the demo has
        #    elapsed periods (the accuracy panel and league table score against real actuals), the
        #    current month (the order-surge detector has a live period to compare against), and
        #    future periods (the signals and consensus adjustments have something to move).
        next_month = datetime.date(today.year + (today.month // 12), (today.month % 12) + 1, 1)
        horizon_start = self._add_months(datetime.date(today.year, today.month, 1), -3)
        forecast = DemandForecast(
            tenant=tenant, name="Workstation demand — rolling 6 months", item=ws16, location=main,
            demand_source="sales_orders", bucket="month", horizon_start=horizon_start,
            horizon_end=self._month_end(self._add_months(horizon_start, 5)),
            history_months=history_months,
            method="moving_average", method_parameter=Decimal("3"), seasonality_profile=seasonal,
            currency=currency, scenario="baseline",
            notes="Seeded: fitted on derived sales history, seasonalised by the Q4 curve.")
        forecast.save()
        forecast.generate_periods()
        periods = list(forecast.periods.all())
        for period in periods:
            period.unit_price = Decimal("1450.00")
        DemandForecastPeriod.objects.bulk_update(periods, ["unit_price"])
        forecast.status = "in_review"
        forecast.save(update_fields=["status", "updated_at"])
        forecast.status, forecast.approved_by, forecast.approved_at = "approved", admin, timezone.now()
        forecast.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

        # 4) A second forecast left in draft so the list shows two statuses and the action gating.
        draft = DemandForecast(
            tenant=tenant, name="Monitor demand — best fit trial", item=mon27,
            demand_source="sales_orders", bucket="month", horizon_start=next_month,
            horizon_end=self._month_end(self._add_months(next_month, 2)),
            history_months=history_months, method="best_fit", currency=currency,
            scenario="optimistic", notes="Seeded: left in draft — generate it to see best fit run.")
        draft.save()

        # 5) Signals at three triage points. The surge one is produced by the REAL detector reading
        #    live sales orders, which is what proves demand sensing works with zero integrations.
        detected = detect_order_surge(tenant)
        for signal in detected:
            signal.status, signal.reviewed_by, signal.reviewed_at = ("under_review", admin,
                                                                     timezone.now())
            signal.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
            signal.apply_to_forecast(forecast)
        DemandSignal.objects.create(
            tenant=tenant, signal_type="customer_forecast", source="customer",
            source_reference="Fabrikam CPFR week 12", item=ws16, location=main, customer=customer,
            observed_at=timezone.now(), effective_from=next_month,
            effective_to=self._month_end(next_month), horizon_days=30,
            signal_value=Decimal("26"), baseline_value=Decimal("20"), impact_direction="increase",
            impact_pct=Decimal("30.00"), impact_quantity=Decimal("6"), confidence="high",
            notes="Seeded: customer shared their own forecast for next month.")
        DemandSignal.objects.create(
            tenant=tenant, signal_type="weather", source="weather_service",
            source_reference="Regional cold snap advisory", category=ws16.category,
            observed_at=timezone.now(), horizon_days=21, signal_value=Decimal("0"),
            baseline_value=Decimal("0"), impact_direction="decrease", impact_pct=Decimal("8.00"),
            impact_quantity=Decimal("3"), confidence="low",
            notes="Seeded: sits in the triage queue as New.")

        # 6) Consensus adjustments — one accepted (so the roll-up is genuinely non-zero), one
        #    awaiting review, one rejected.
        # Aim the period-level adjustments at a FUTURE period — overriding a month that has already
        # elapsed would be nonsense on a demo screen (and would skew its accuracy score).
        first_period = (forecast.periods.filter(period_start=next_month).first()
                        or forecast.periods.order_by("-sequence").first())
        org_unit = self._org_unit(tenant)
        ForecastAdjustment.objects.create(
            tenant=tenant, forecast=forecast, period=first_period, contributor_function="sales",
            submitted_by=admin, org_unit=org_unit, adjustment_type="delta",
            proposed_quantity=Decimal("8"), reason_code="new_customer", confidence="high",
            status="accepted", reviewed_by=admin, reviewed_at=timezone.now(),
            review_note="Seeded: accepted — the pipeline supports it.",
            rationale="A new regional reseller signed this quarter and their first order lands in "
                      "the opening period.")
        ForecastAdjustment.objects.create(
            tenant=tenant, forecast=forecast, contributor_function="marketing",
            submitted_by=admin, org_unit=org_unit, adjustment_type="percent",
            adjustment_pct=Decimal("12.00"), reason_code="promotion", confidence="medium",
            rationale="Q4 campaign spend is up on last year; expecting a broad lift across the "
                      "horizon rather than one period.")
        ForecastAdjustment.objects.create(
            tenant=tenant, forecast=forecast, period=first_period, contributor_function="finance",
            submitted_by=admin, org_unit=org_unit, adjustment_type="absolute",
            proposed_quantity=Decimal("40"), reason_code="budget_target", confidence="low",
            status="rejected", reviewed_by=admin, reviewed_at=timezone.now(),
            review_note="Seeded: rejected — that is the budget target, not a demand signal.",
            rationale="Budget commits to 40 units in the opening period.")
        forecast.recompute_consensus()

        # 7) Switch the existing 4.3 rules onto a real safety-stock policy and CALCULATE — without
        #    applying, so the report has a genuine computed-vs-live variance and the Apply button
        #    has something to do. This is the whole compute-then-accept contract in the seed data.
        rules = list(ReorderRule.objects.filter(tenant=tenant)
                     .select_related("item").prefetch_related("seasonality_profile__indices"))
        ReorderRule.assign_abc_classes(tenant, rules)
        # Hoisted out of the loop — it does not depend on the rule — and the history comes from ONE
        # batched query, mirroring what safety_stock_recalculate does at runtime.
        catalog_lead = (SupplierCatalogItem.objects
                        .filter(catalog__tenant=tenant, lead_time_days__gt=0)
                        .values_list("lead_time_days", flat=True).first())
        calc_end = timezone.localdate()
        calc_start = calc_end - datetime.timedelta(days=30 * ReorderRule.CALC_HISTORY_MONTHS)
        series_map = demand_series_map(tenant, {rule.item_id for rule in rules},
                                       start=calc_start, end=calc_end, bucket="month")
        for rule in rules:
            rule.safety_stock_method = "service_level"
            rule.service_level_pct = Decimal("95.00")
            rule.lead_time_days = catalog_lead or 7
            rule.lead_time_variability_days = Decimal("2.00")
            rule.review_period_days = 7
            if rule.item_id == ws16.pk:
                rule.seasonality_profile = seasonal
                rule.demand_forecast = forecast
            rule.calculate(series=series_map.get(rule.item_id, []))
        ReorderRule.objects.bulk_update(rules, [
            "safety_stock_method", "service_level_pct", "lead_time_days",
            "lead_time_variability_days", "review_period_days", "seasonality_profile",
            "demand_forecast", "avg_daily_demand", "demand_std_dev", "abc_class", "xyz_class",
            "computed_safety_stock", "computed_reorder_point", "last_calculated_at"])

        self.stdout.write(
            f"{tenant.name}: seeded demand planning ({orders} back-dated history orders, "
            f"2 seasonality profiles, forecast {forecast.number} [approved] + {draft.number} "
            f"[draft], {len(detected) + 2} demand signals, 3 consensus adjustments, "
            f"{len(rules)} reorder rules calculated but NOT applied).")
        self.stdout.write(
            "  Demand history is DERIVED from those sales orders — 4.7 stores no history table.")

    @staticmethod
    def _add_months(value, months):
        total = value.year * 12 + (value.month - 1) + months
        year, month = divmod(total, 12)
        return datetime.date(year, month + 1, 1)

    @staticmethod
    def _month_end(value):
        following = Command._add_months(datetime.date(value.year, value.month, 1), 1)
        return following - datetime.timedelta(days=1)

    def _seed_tms_tenant(self, tenant):
        """4.6 TMS demo: two carriers (+ rate cards), a booked load with a two-stop route, an
        outbound in-transit shipment consolidated on the load, an inbound delivered shipment (which
        seeds the carrier's on-time scorecard), and a freight invoice sitting in the price-variance
        queue — so every 4.6 page has something real on it.

        Idempotent via a Carrier guard. Runs after _seed_oms_tenant / procurement so the shipments can
        link the seeded SalesOrder / PurchaseOrder. Carriers reuse the supplier-party spine helper —
        no duplicate company rows. Events go through the real ``apply_tracking_event`` projection and
        the invoice through the real ``run_audit``, so the derived state is genuine, not hand-set.
        """
        import datetime as _dt
        from apps.scm.models import (
            Carrier, CarrierRateCard, Load, LoadStop, Shipment, TrackingEvent,
            FreightInvoice, FreightInvoiceLine, PurchaseOrder, SalesOrder,
        )
        if Carrier.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: transportation data already exists — skipping.")
            return

        today = timezone.localdate()
        now = timezone.now()
        usd = Currency.objects.filter(code="USD").first()

        swift_party = self._supplier(tenant, "Swift Freightways", "organization")
        swift = Carrier.objects.create(
            tenant=tenant, party=swift_party, carrier_type="asset_based", primary_mode="truckload",
            service_level="standard", scac_code="SWFT", mc_number="MC-123456", dot_number="DOT-778899",
            primary_contact_name="Dispatch Desk", primary_contact_email="dispatch@swiftfreight.example",
            is_preferred=True, status="active",
            insurance_certificate_expiry=today + _dt.timedelta(days=180))
        CarrierRateCard.objects.create(
            carrier=swift, lane_name="Chicago → Dallas", origin_region="Chicago, IL",
            destination_region="Dallas, TX", mode="truckload", equipment_type="dry_van",
            rate_basis="flat", base_rate=Decimal("1850.00"), fuel_surcharge_pct=Decimal("12.00"),
            min_charge=Decimal("500.00"), transit_days=2, currency=usd,
            effective_from=today - _dt.timedelta(days=30), is_active=True)

        aero_party = self._supplier(tenant, "AeroParcel Express", "organization")
        aero = Carrier.objects.create(
            tenant=tenant, party=aero_party, carrier_type="courier", primary_mode="parcel",
            service_level="expedited", scac_code="AERO", status="active")
        CarrierRateCard.objects.create(
            carrier=aero, lane_name="National parcel", mode="parcel", equipment_type="parcel",
            rate_basis="per_kg", base_rate=Decimal("4.50"), fuel_surcharge_pct=Decimal("8.00"),
            min_charge=Decimal("15.00"), transit_days=1, currency=usd, is_active=True)

        load = Load.objects.create(
            tenant=tenant, carrier=swift, mode="truckload", equipment_type="dry_van",
            origin_text="Main DC, Chicago IL", destination_text="Fabrikam RDC, Dallas TX",
            planned_departure=now, planned_arrival=now + _dt.timedelta(days=2),
            distance_km=Decimal("1480.00"), estimated_fuel_cost=Decimal("620.00"),
            freight_cost_estimate=Decimal("2072.00"),
            equipment_capacity_weight_kg=Decimal("18000.00"),
            equipment_capacity_volume_cbm=Decimal("76.000"),
            driver_name="J. Delgado", vehicle_ref="TRK-4471")
        LoadStop.objects.create(load=load, sequence=1, stop_type="pickup",
                                address_text="Main DC, Chicago IL", planned_arrival=now, status="completed")
        LoadStop.objects.create(load=load, sequence=2, stop_type="delivery",
                                address_text="Fabrikam RDC, Dallas TX",
                                planned_arrival=now + _dt.timedelta(days=2), status="pending")
        load.status = "booked"
        load.save(update_fields=["status", "updated_at"])

        # Outbound shipment on the load — links a seeded sales order when one exists, in transit.
        so = SalesOrder.objects.filter(tenant=tenant).order_by("id").first()
        ship = Shipment.objects.create(
            tenant=tenant, direction="outbound", carrier=swift, load=load, sales_order=so,
            origin_text="Main DC, Chicago IL", destination_text="Fabrikam RDC, Dallas TX",
            mode="truckload", planned_pickup_date=today,
            planned_delivery_date=today + _dt.timedelta(days=2),
            weight_kg=Decimal("9200.00"), volume_cbm=Decimal("34.500"), package_count=48,
            carrier_tracking_number="SWFT-000123", freight_cost_estimate=Decimal("2072.00"))
        for etype, loc, when in [
            ("pickup", "Chicago, IL", now - _dt.timedelta(hours=6)),
            ("in_transit", "St. Louis, MO", now - _dt.timedelta(hours=1)),
        ]:
            ev = TrackingEvent.objects.create(shipment=ship, event_type=etype, event_at=when,
                                              location_text=loc, source="carrier_api")
            ship.apply_tracking_event(ev)

        # Inbound shipment delivered on time — gives the carrier scorecard a real signal.
        po = PurchaseOrder.objects.filter(tenant=tenant).order_by("id").first()
        inbound = Shipment.objects.create(
            tenant=tenant, direction="inbound", carrier=swift, purchase_order=po,
            origin_text="Northwind Warehouse", destination_text="Main DC, Chicago IL",
            mode="ltl", planned_pickup_date=today - _dt.timedelta(days=4),
            planned_delivery_date=today - _dt.timedelta(days=1),
            weight_kg=Decimal("3100.00"), volume_cbm=Decimal("12.000"), package_count=12,
            carrier_tracking_number="SWFT-000090")
        for etype, loc, when in [
            ("pickup", "Supplier Dock", now - _dt.timedelta(days=4)),
            ("delivered", "Main DC, Chicago IL", now - _dt.timedelta(days=1, hours=2)),
        ]:
            ev = TrackingEvent.objects.create(shipment=inbound, event_type=etype, event_at=when,
                                              location_text=loc, source="driver_app")
            inbound.apply_tracking_event(ev)
        swift.recompute_scorecard()

        # Freight invoice with a fuel + detention over-billing — lands in the price-variance queue.
        inv = FreightInvoice.objects.create(
            tenant=tenant, carrier=swift, load=load, shipment=ship,
            carrier_invoice_number="SWFT-INV-5567", invoice_date=today,
            due_date=today + _dt.timedelta(days=30), currency=usd, match_tolerance_pct=Decimal("2.00"))
        FreightInvoiceLine.objects.create(
            freight_invoice=inv, charge_type="linehaul", description="Chicago → Dallas linehaul",
            billed_amount=Decimal("1850.00"), contract_amount=Decimal("1850.00"))
        FreightInvoiceLine.objects.create(
            freight_invoice=inv, charge_type="fuel_surcharge", description="Fuel surcharge",
            billed_amount=Decimal("260.00"), contract_amount=Decimal("222.00"))
        FreightInvoiceLine.objects.create(
            freight_invoice=inv, charge_type="detention", description="Detention — 2 hrs",
            billed_amount=Decimal("90.00"), contract_amount=Decimal("0.00"))
        inv.run_audit()

        self.stdout.write(
            f"{tenant.name}: seeded carriers {swift.number}/{aero.number}, load {load.number}, "
            f"shipments {ship.number}/{inbound.number}, freight invoice {inv.number} "
            f"[{inv.get_match_status_display()}].")

    def _flush(self):
        # The AP bills this seeder created are reachable only through the receipts that link them,
        # so they must go FIRST — once the GRNs are gone there is no way to tell a seeded bill from
        # a real one, and every --flush cycle would strand another set of orphans in accounting.
        # Scoped to bills actually linked to a receipt, so a hand-entered bill is never touched.
        orphaned_bills = Bill.objects.filter(scm_goods_receipts__isnull=False).distinct()
        bill_count = orphaned_bills.count()
        orphaned_bills.delete()

        # 4.13 Asset Management FIRST (newest sub-module). The order inside it is forced by ONE
        # PROTECT edge: MaintenanceWorkOrder.asset is PROTECT onto Asset — a completed job is history
        # and must never be one click from deletion — so every job goes before the assets they were
        # raised against. MaintenancePlan.asset is CASCADE and MaintenanceWorkOrder.plan is SET_NULL,
        # so the plans could not block anything; they are named before the assets anyway so the
        # teardown reads top-down like every block below it. MeterReading CASCADEs from its asset and
        # the three child tables (parts, both task tables) CASCADE from their parents — deleting the
        # four parents clears all of them.
        #
        # AssetSparePart.item and MaintenanceWorkOrderPart.item are PROTECT onto 4.3's Item, which is
        # cleared at the BOTTOM of this method: both cascade away with the rows deleted here, so 4.3's
        # masters are already unblocked by the time they are reached.
        #
        # The `maintenance` StockMoves the issue-parts path posted carry no FK to 4.13 — only the MWO
        # number as free text — exactly like 4.8's consumption/production moves and 4.9's scrap
        # adjustment, so StockMove.objects.all().delete() further down would cover them. They are
        # named here regardless, and deliberately: the seeder's "post these parts exactly once" guard
        # keys on precisely this filter, so flush and guard describe the SAME set of rows rather than
        # one of them being an implicit consequence of a line 180 lines further down. Tenant-less like
        # every other delete in this method — --flush is workspace-wide by design.
        #
        # `Item.is_spare_part` is deliberately NOT unwound: it is a property of the item itself
        # ("this is a machine spare"), not of the asset register, and the whole Item table is deleted
        # at the bottom of this method anyway — a hand-written UPDATE first would only be a slower way
        # to reach the same empty table (the 4.12 SupplierContract.owner reasoning).
        from apps.scm.models import (Asset, MaintenancePlan, MaintenanceWorkOrder, MeterReading,
                                     StockMove as _StockMove)
        MeterReading.objects.all().delete()
        MaintenanceWorkOrder.objects.all().delete()   # parts + task snapshots cascade
        MaintenancePlan.objects.all().delete()        # plan tasks cascade
        Asset.objects.all().delete()                  # spare-part lists cascade
        _StockMove.objects.filter(move_type="maintenance").delete()

        # 4.12 Contract & Compliance NEXT. Exactly ONE edge inside it is
        # PROTECT and it decides the whole order: TradeDocument.license is PROTECT onto TradeLicense,
        # because the record of what actually moved under a licence IS that licence's audit trail and
        # its consumed balance, so losing it must never be one click away. That puts the licences
        # LAST of the four models — documents and their lines have to clear first or every --flush
        # raises ProtectedError. Everything else here either CASCADEs from its own parent (checks
        # from their requirement, lines from their document) or is SET_NULL (a requirement's
        # contract/license/document pointers, a document's shipment/carrier/order/party pointers), so
        # nothing else in 4.12 can block a deletion further down.
        #
        # The two COLUMNS 4.12 added to 4.2's SupplierContract are deliberately not unwound here:
        # `owner` is SET_NULL onto a user this seeder never created, `parent_contract` is SET_NULL
        # onto another contract, and the whole SupplierContract table is deleted in the 4.2 block
        # below anyway — a hand-written UPDATE first would only be a slower way to reach the same
        # empty table.
        from apps.scm.models import (ComplianceCheck, ComplianceRequirement,
                                     SustainabilityAssessment, TradeDocument, TradeDocumentLine,
                                     TradeLicense)
        ComplianceCheck.objects.all().delete()
        ComplianceRequirement.objects.all().delete()
        TradeDocumentLine.objects.all().delete()
        TradeDocument.objects.all().delete()
        TradeLicense.objects.all().delete()
        SustainabilityAssessment.objects.all().delete()

        # 4.11 Analytics NEXT. Unlike every block below it, NOTHING here is
        # PROTECT — KpiSnapshot.kpi_target is CASCADE and all six of SupplyChainAlert's subject FKs
        # plus KpiTarget's four scope FKs are SET_NULL — so these rows could not block any deletion
        # further down. They still go this early, because a snapshot or alert left pointing at a deleted
        # item reads as a measurement of something that no longer exists, and 4.11 is the one
        # sub-module whose whole value is that its numbers are traceable. Snapshots before targets
        # so the intent reads top-down even though the cascade would handle it.
        from apps.scm.models import KpiSnapshot, KpiTarget, SupplyChainAlert
        KpiSnapshot.objects.all().delete()
        SupplyChainAlert.objects.all().delete()
        KpiTarget.objects.all().delete()

        # 4.10 Returns next, and the ORDER inside it is forced by PROTECT:
        #
        #   WarrantyClaim.supplier/item are PROTECT onto core.Party and 4.3's Item, and
        #   WarrantyClaim.return_authorization is SET_NULL onto the RMA — so claims go before both
        #   the RMAs and the 4.3 masters at the bottom of this method. Costs cascade from the claim
        #   but are deleted explicitly so the intent reads top-down.
        #
        #   ReturnDisposition.location is PROTECT onto Location and ReturnLine.item/reason are
        #   PROTECT onto Item and ReturnReason — so dispositions go before lines, lines before
        #   reasons, and the whole tree before 4.3's masters.
        #
        #   ReturnAuthorization.customer is PROTECT onto core.Party, .policy is PROTECT onto
        #   ReturnPolicy and .currency is PROTECT onto accounting.Currency — so RMAs go before
        #   policies. Currency is a GLOBAL master this seeder never deletes, so nothing more is
        #   needed there.
        #
        # The draft CREDIT NOTES this seeder raised are reachable only through
        # ReturnAuthorization.credit_note (SET_NULL), so they must go BEFORE the RMAs or every
        # --flush cycle strands another set of orphans in Accounts Receivable — the same
        # orphan-avoidance the GRN and freight blocks do. Scoped to invoices actually linked to a
        # return, so a hand-entered credit note is never touched.
        #
        # The `receipt` StockMove a restock posted carries no FK to 4.10 — only the RMA number as
        # free text — so it is already covered by StockMove.objects.all().delete() further down.
        from apps.accounting.models import Invoice as _AccInvoice
        from apps.scm.models import (ReturnAuthorization, ReturnDisposition, ReturnLine,
                                     ReturnPolicy, ReturnReason, WarrantyClaim, WarrantyClaimCost)
        return_credit_notes = _AccInvoice.objects.filter(
            scm_return_authorizations__isnull=False).distinct()
        return_credit_count = return_credit_notes.count()
        return_credit_notes.delete()
        WarrantyClaimCost.objects.all().delete()
        WarrantyClaim.objects.all().delete()
        ReturnDisposition.objects.all().delete()
        ReturnLine.objects.all().delete()
        ReturnAuthorization.objects.all().delete()
        ReturnPolicy.objects.all().delete()
        ReturnReason.objects.all().delete()

        # 4.9 Quality NEXT. QualityInspection.item/lot_serial/location and
        # NonConformance.item/lot_serial/location are PROTECT against the 4.3 masters cleared at
        # the bottom of this method, so the whole 4.9 tree has to go before them. Within the tree:
        # CapaTask/InspectionResult cascade from their parents but are deleted explicitly so the
        # intent reads top-down, CapaAction before NonConformance and NonConformance before
        # QualityAudit/QualityInspection (those FKs are SET_NULL and would not block, but deleting
        # children first keeps the order meaningful), and the plans last because the inspections
        # and audits point at them. The `adjustment` StockMove the NCR scrap posted is already
        # covered by StockMove.objects.all().delete() further down — it carries no FK to 4.9, only
        # the NCR number as free text.
        from apps.scm.models import (CapaAction, CapaTask, InspectionCharacteristic,
                                     InspectionPlan, InspectionResult, NonConformance,
                                     QualityAudit, QualityInspection)
        CapaTask.objects.all().delete()
        CapaAction.objects.all().delete()
        NonConformance.objects.all().delete()
        InspectionResult.objects.all().delete()
        QualityInspection.objects.all().delete()
        QualityAudit.objects.all().delete()
        InspectionCharacteristic.objects.all().delete()
        InspectionPlan.objects.all().delete()

        # 4.8 Manufacturing next. BillOfMaterials.item, BOMLine.component and
        # WorkOrderComponent.item are all PROTECT against 4.3's items below, and WorkOrder.
        # work_center / ProductionTimeLog.work_center are PROTECT against WorkCenter — so the order
        # here is forced: logs and components (children) → orders → BOMs → centres. The WS-KIT item
        # this seeder created is removed with them; 4.3's own items are cleared further down.
        from apps.scm.models import (BillOfMaterials, BOMLine, ProductionTimeLog,
                                     WorkCenter, WorkOrder, WorkOrderComponent)
        ProductionTimeLog.objects.all().delete()
        WorkOrderComponent.objects.all().delete()
        WorkOrder.objects.all().delete()
        BOMLine.objects.all().delete()
        BillOfMaterials.objects.all().delete()
        WorkCenter.objects.all().delete()
        # WS-KIT is NOT deleted here: this seeder posts a `production` StockMove for it, and
        # StockMove.item is PROTECT — removing the item before the ledger below would raise
        # ProtectedError on every --flush that follows a 4.8 seed. Item.objects.all().delete()
        # further down clears it once the moves are gone.

        # 4.7 Demand Planning first (newest module). DemandForecast.item is PROTECT, so the whole
        # forecast tree has to clear before 4.3's items below; ForecastAdjustment.forecast and
        # DemandSignal.applied_to_forecast point AT the forecast, so they go first. ReorderRule's
        # 4.7 links are SET_NULL, so the existing rule teardown below needs no change.
        from apps.scm.models import (DemandForecast, DemandForecastPeriod, DemandSignal,
                                     ForecastAdjustment, SeasonalityProfile)
        ForecastAdjustment.objects.all().delete()
        DemandSignal.objects.all().delete()
        DemandForecastPeriod.objects.all().delete()
        DemandForecast.objects.all().delete()
        SeasonalityProfile.objects.all().delete()   # index rows cascade

        # 4.6 TMS next. FreightInvoice.carrier is PROTECT, so freight invoices must
        # clear before their carriers; children (lines/events/stops/rate-cards) cascade. Any draft AP
        # bill a freight hand-off created is reachable only through FreightInvoice.bill (SET_NULL), so
        # drop those bills first — the same orphan-avoidance the GRN block above does.
        from apps.scm.models import Carrier, FreightInvoice, Load, Shipment
        freight_bills = Bill.objects.filter(scm_freight_invoices__isnull=False).distinct()
        freight_bill_count = freight_bills.count()
        freight_bills.delete()
        FreightInvoice.objects.all().delete()   # lines cascade
        Shipment.objects.all().delete()         # tracking events cascade
        Load.objects.all().delete()             # stops cascade
        Carrier.objects.all().delete()          # rate cards cascade

        # Child rows cascade from their parents; delete parents newest-first down the chain so the
        # PROTECT on GoodsReceiptLine.po_line / GoodsReceiptNote.purchase_order never blocks.
        GoodsReceiptLine.objects.all().delete()
        GoodsReceiptNote.objects.all().delete()
        PurchaseOrderLine.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        RFQQuoteLine.objects.all().delete()
        RFQQuote.objects.all().delete()
        RFQVendor.objects.all().delete()
        RFQLine.objects.all().delete()
        RFQ.objects.all().delete()
        PurchaseRequisitionLine.objects.all().delete()
        PurchaseRequisition.objects.all().delete()

        # 4.2 SRM rows (children cascade from their parent; profiles/scorecards/etc. cascade from Party
        # for CASCADE FKs, but SupplierContract.party is PROTECT so delete the SRM tables directly).
        from apps.scm.models import (
            SupplierCatalog, SupplierContract, SupplierProfile, SupplierRiskAssessment,
            SupplierScorecard,
        )
        SupplierCatalog.objects.all().delete()   # items cascade
        SupplierContract.objects.all().delete()
        SupplierScorecard.objects.all().delete()
        SupplierRiskAssessment.objects.all().delete()
        SupplierProfile.objects.all().delete()

        # 4.3 Inventory — StockMove is PROTECT-referenced by item/location, so delete moves and the
        # domain docs (transfers/adjustments/reorder rules) before the masters they point at.
        from apps.scm.models import (
            Item, ItemCategory, UOM, Location, LotSerial, StockMove,
            StockTransfer, StockAdjustment, ReorderRule,
        )
        # 4.5 orders go before 4.4: SalesOrderLine PROTECTs Item and SalesOrderAllocation
        # PROTECTs Location, so the whole order tree has to clear before those masters do.
        from apps.scm.models import SalesOrder, SalesOrderAllocation, SalesOrderLine
        SalesOrderAllocation.objects.all().delete()
        SalesOrderLine.objects.all().delete()
        SalesOrder.objects.all().delete()

        # 4.4 warehouse docs next — their lines PROTECT the 4.3 items/locations below.
        from apps.scm.models import CycleCountTask, PickTask, PutawayTask, YardVisit
        CycleCountTask.objects.all().delete()     # lines cascade
        PickTask.objects.all().delete()           # lines cascade
        PutawayTask.objects.all().delete()
        YardVisit.objects.all().delete()

        StockMove.objects.all().delete()
        StockTransfer.objects.all().delete()      # lines cascade
        StockAdjustment.objects.all().delete()    # lines cascade
        ReorderRule.objects.all().delete()
        LotSerial.objects.all().delete()
        Item.objects.all().delete()
        Location.objects.all().delete()
        ItemCategory.objects.all().delete()
        UOM.objects.all().delete()
        self.stdout.write(self.style.WARNING(
            f"Flushed all SCM procurement + SRM + inventory + warehouse + order + transportation + "
            f"demand planning + manufacturing + quality + returns + analytics + compliance + asset "
            f"management rows (+{bill_count + freight_bill_count} linked accounting bill(s), "
            f"+{return_credit_count} linked credit note(s))."))

    def _seed_manufacturing_tenant(self, tenant):
        """4.8 Manufacturing demo: two work centres, a two-level BOM for an assembled bundle, and a
        work order driven through the REAL release → issue → report path so the ledger, the costs
        and the status all come out of the same code the views run.

        Idempotent via a BillOfMaterials guard. Runs last — it needs 4.3's items, locations and
        UOMs to exist, and it consumes their on-hand stock.
        """
        from apps.scm.models import (BillOfMaterials, BOMLine, Item, ItemCategory, Location,
                                     ProductionTimeLog, UOM, WorkCenter, WorkOrder)
        from apps.scm.views.Manufacturing.WorkOrders import _issue_components
        from apps.scm.views._helpers import _post_stock_move
        from apps.scm.models._base import ZERO, q4
        if BillOfMaterials.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: manufacturing data already exists — skipping.")
            return

        ws16 = Item.objects.filter(tenant=tenant, sku="WS-16").first()
        mon27 = Item.objects.filter(tenant=tenant, sku="MON-27").first()
        dock = Item.objects.filter(tenant=tenant, sku="DOCK-C").first()
        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
        if not all([ws16, mon27, dock, main]):
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no seeded items/locations — skipping manufacturing seed."))
            return

        each = UOM.objects.filter(tenant=tenant, code="EA").first()
        category = ItemCategory.objects.filter(tenant=tenant).first()
        admin = self._admin(tenant)

        assembly = WorkCenter.objects.create(
            tenant=tenant, code="WC-ASM", name="Bench Assembly", center_type="assembly",
            location=main, org_unit=self._org_unit(tenant), capacity_hours_per_day=Decimal("8"),
            efficiency_pct=Decimal("92"), setup_minutes=15,
            machine_cost_per_hour=Decimal("0"), labor_cost_per_hour=Decimal("38"))
        WorkCenter.objects.create(
            tenant=tenant, code="WC-QC", name="Inspection Bench", center_type="inspection",
            location=main, org_unit=self._org_unit(tenant), capacity_hours_per_day=Decimal("6"),
            efficiency_pct=Decimal("100"), machine_cost_per_hour=Decimal("0"),
            labor_cost_per_hour=Decimal("30"))

        # The produced good — a new finished item, so the BOM has a real output to receive into
        # stock rather than reusing a purchased one.
        bundle = Item.objects.create(
            tenant=tenant, sku="WS-KIT", name="Workstation bundle (laptop + monitor + dock)",
            category=category, uom=each, costing_method="weighted_avg",
            standard_cost=Decimal("1700"),
            description="Assembled from stocked components — see its bill of materials.")

        bom = BillOfMaterials.objects.create(
            tenant=tenant, item=bundle, name="Workstation bundle", version="1",
            bom_type="manufacture", output_quantity=Decimal("1"), uom=each, lead_time_days=2,
            default_work_center=assembly, status="active", is_default=True,
            effective_from=timezone.localdate() - datetime.timedelta(days=30),
            notes="Demo recipe — one laptop, one monitor and one dock per bundle.")
        BOMLine.objects.create(bom=bom, sequence=10, component=ws16, quantity_per=Decimal("1"),
                               uom=each, issue_method="manual")
        BOMLine.objects.create(bom=bom, sequence=20, component=mon27, quantity_per=Decimal("1"),
                               uom=each, scrap_pct=Decimal("2"), issue_method="manual")
        BOMLine.objects.create(bom=bom, sequence=30, component=dock, quantity_per=Decimal("1"),
                               uom=each, issue_method="backflush")

        order = WorkOrder.objects.create(
            tenant=tenant, item=bundle, uom=each, bom=bom, quantity_planned=Decimal("5"),
            order_policy="make_to_stock", work_center=assembly, priority="normal",
            planned_start=timezone.now() - datetime.timedelta(days=2),
            planned_end=timezone.now() + datetime.timedelta(days=1),
            due_date=timezone.localdate() + datetime.timedelta(days=5),
            component_location=main, output_location=main,
            notes="Demo run — released, part-issued and part-reported through the real actions.")
        order.explode_components()
        order.status = "released"
        order.released_by = admin
        order.save(update_fields=["status", "released_by", "updated_at"])

        # Drive the real posting path so the demo ledger is what the app would have written.
        components = [c for c in order.components.select_related("item", "lot_serial").all()
                      if c.issue_method == "manual"]
        _issue_components(order, components, {c.pk: c.quantity_outstanding for c in components},
                          admin)
        order.status = "in_progress"
        order.actual_start = timezone.now() - datetime.timedelta(days=1)
        order.save(update_fields=["status", "actual_start", "updated_at"])

        ProductionTimeLog.objects.create(
            tenant=tenant, work_order=order, work_center=assembly, operation="Assemble & cable",
            entry_type="setup", started_at=timezone.now() - datetime.timedelta(hours=9),
            ended_at=timezone.now() - datetime.timedelta(hours=8, minutes=45))
        ProductionTimeLog.objects.create(
            tenant=tenant, work_order=order, work_center=assembly, operation="Assemble & cable",
            entry_type="labor", started_at=timezone.now() - datetime.timedelta(hours=8, minutes=45),
            ended_at=timezone.now() - datetime.timedelta(hours=5), quantity_completed=Decimal("3"))
        ProductionTimeLog.objects.create(
            tenant=tenant, work_order=order, work_center=assembly, operation="Assemble & cable",
            entry_type="downtime", downtime_reason="material_shortage",
            started_at=timezone.now() - datetime.timedelta(hours=5),
            ended_at=timezone.now() - datetime.timedelta(hours=4, minutes=20),
            notes="Waiting on dock stock.")

        # Report 3 of 5 good — backflushing the DOCK-C line in proportion, exactly as
        # workorder_report_production does, so the demo run's ledger, its component issue state and
        # its absorbed unit cost are all what the app would have written rather than hand-set
        # fields that merely look plausible.
        good = Decimal("3")
        backflush = [c for c in order.components.select_related("item", "lot_serial").all()
                     if c.issue_method == "backflush"]
        planned = order.quantity_planned or Decimal("1")
        _issue_components(
            order, backflush,
            {c.pk: min(q4((c.quantity_required or ZERO) * good / planned), c.quantity_outstanding)
             for c in backflush},
            admin)
        unit_cost = order.computed_unit_cost(good)
        _post_stock_move(tenant, item=bundle, location=main, quantity=good,
                         move_type="production", unit_cost=unit_cost, reference=order.number,
                         reason=f"Produced by {order.number}")
        order.quantity_produced = good
        order.produced_unit_cost = unit_cost
        order.save(update_fields=["quantity_produced", "produced_unit_cost", "updated_at"])

        self.stdout.write(f"{tenant.name}: manufacturing — 2 work centres, BOM {bom.number}, "
                          f"work order {order.number} ({good} of 5 reported).")

    def _seed_quality_tenant(self, tenant):
        """4.9 Quality demo: three inspection plans, three inspections (one certified), three
        non-conformances (one posting a real scrap adjustment), two CAPAs and two audits.

        Idempotent via a QualityInspection guard. Runs LAST — it inspects 4.1's goods receipts,
        4.3's items/locations/lots, 4.6's shipments and 4.8's work orders, so every one of those
        must already exist.

        Everything goes through the SAME code the views run: ``generate_results()`` snapshots the
        characteristics, ``InspectionResult.save()`` derives each verdict from the snapshotted
        limits, ``evaluated_result`` decides pass/fail, ``coa_blockers()`` gates the certificate and
        ``next_number(..., field="coa_number")`` stamps it, and the scrap posts through
        ``_post_stock_move`` behind ``_insufficient_stock``. Nothing here hand-sets a field that
        merely looks plausible.
        """
        from apps.scm.models import (CapaAction, CapaTask, GoodsReceiptNote, InspectionPlan,
                                     InspectionCharacteristic, Item, Location, LotSerial,
                                     NonConformance, QualityAudit, QualityInspection, Shipment,
                                     UOM)
        from apps.scm.views._helpers import _insufficient_stock, _post_stock_move
        from apps.scm.models._base import ZERO, q2
        from apps.core.utils import next_number
        # Guarded on InspectionPlan, the FIRST thing this block writes — not on QualityInspection.
        # The plans are plain .create() calls against a unique ("tenant","code","version"), so a run
        # that aborted between them and the first inspection would leave a re-run to IntegrityError
        # on a guard that had not yet tripped.
        if InspectionPlan.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: quality data already exists — skipping.")
            return

        ws16 = Item.objects.filter(tenant=tenant, sku="WS-16").first()
        mon27 = Item.objects.filter(tenant=tenant, sku="MON-27").first()
        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
        grn = GoodsReceiptNote.objects.filter(tenant=tenant, status="received").order_by("id").first()
        shipment = (Shipment.objects.filter(tenant=tenant, direction="outbound")
                    .order_by("id").first())
        supplier = Party.objects.filter(tenant=tenant, name="Northwind Industrial Supply").first()
        inspector = self._employee(tenant, "Emma Williams")
        auditor = self._employee(tenant, "Olivia Martin")
        if any(x is None for x in (ws16, mon27, main, grn, shipment, supplier, inspector)):
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: missing items / location / received receipt / outbound shipment / "
                "supplier / employee party — skipping quality seed."))
            return

        today = timezone.localdate()
        each = UOM.objects.filter(tenant=tenant, code="EA").first()
        # A photometric unit for the CoA's luminance row — the certificate prints the unit next to
        # the limits, so a demo without one shows a bare number.
        cdm2, _ = UOM.objects.get_or_create(
            tenant=tenant, code="CDM2", defaults={"name": "Candela per m²", "factor": 1})

        # 4.3 seeds both items as tracking="none" because nothing needed batches yet. Quality does:
        # a certificate certifies a BATCH, quarantine is a lot status, and blocker rule 6 ("a
        # lot-tracked item needs a lot before it can be certified") is inert without this. One
        # field, on the two items 4.9 demonstrates.
        Item.objects.filter(pk__in=[ws16.pk, mon27.pk]).update(tracking="lot")
        ws16.tracking = mon27.tracking = "lot"
        ws16_lot, _ = LotSerial.objects.get_or_create(
            tenant=tenant, item=ws16, number="WS16-2409",
            defaults={"kind": "lot", "expiry_date": None, "status": "available"})
        mon_lot, _ = LotSerial.objects.get_or_create(
            tenant=tenant, item=mon27, number="MON27-2409",
            defaults={"kind": "lot", "expiry_date": None, "status": "available"})
        # Real lot-level stock so the scrap below has something to draw against — posted through
        # the same service every other movement in this seeder uses, so the weighted-average roll
        # follows the app's own path.
        with transaction.atomic():
            for item, lot, qty, cost in ((ws16, ws16_lot, Decimal("6"), Decimal("1200")),
                                         (mon27, mon_lot, Decimal("12"), Decimal("300"))):
                _post_stock_move(tenant, item=item, location=main, quantity=qty, unit_cost=cost,
                                 move_type="receipt", lot_serial=lot, reference="OPENING-QC",
                                 reason="Opening lot-tracked balance",
                                 moved_at=timezone.now() - datetime.timedelta(days=20))

        # ---------------------------------------------------------------- 1) the criteria masters
        iqc = InspectionPlan.objects.create(
            tenant=tenant, code="IQC-WS16", name="Incoming inspection — laptop workstation",
            plan_type="incoming_receipt", item=ws16, sampling_method="percentage",
            sample_percentage=Decimal("10"), frequency="every", version="1",
            effective_from=today - datetime.timedelta(days=60), is_active=True,
            notes="Sample 10% of every receipt; a wrong port count fails the whole lot.")
        InspectionCharacteristic.objects.create(
            plan=iqc, sequence=10, name="Port count", characteristic_type="measurement", uom=each,
            target_value=Decimal("16"), lower_limit=Decimal("16"), upper_limit=Decimal("16"),
            test_method="Visual count against the datasheet", is_critical=True, is_mandatory=True,
            include_on_coa=True)
        InspectionCharacteristic.objects.create(
            plan=iqc, sequence=20, name="Enclosure condition", characteristic_type="visual",
            expected_text="No dents or scratches", is_mandatory=True)
        InspectionCharacteristic.objects.create(
            plan=iqc, sequence=30, name="Firmware version recorded",
            characteristic_type="instruction", is_mandatory=False)

        oqc = InspectionPlan.objects.create(
            tenant=tenant, code="OQC-MON27", name="Outgoing inspection — 27-inch monitor",
            plan_type="outgoing_shipment", item=mon27, sampling_method="fixed_count",
            sample_size=5, frequency="every", version="1",
            effective_from=today - datetime.timedelta(days=60), is_active=True,
            notes="Two characteristics are certified — they print on the Certificate of Analysis.")
        InspectionCharacteristic.objects.create(
            plan=oqc, sequence=10, name="Luminance", characteristic_type="measurement", uom=cdm2,
            target_value=Decimal("300"), lower_limit=Decimal("280"), upper_limit=Decimal("320"),
            test_method="Photometer, centre of panel", is_critical=True, is_mandatory=True,
            include_on_coa=True)
        InspectionCharacteristic.objects.create(
            plan=oqc, sequence=20, name="Dead pixels", characteristic_type="measurement", uom=each,
            upper_limit=Decimal("0"), test_method="Full-screen colour sweep", is_mandatory=True,
            include_on_coa=True)
        InspectionCharacteristic.objects.create(
            plan=oqc, sequence=30, name="Packaging intact", characteristic_type="visual",
            expected_text="Sealed, undamaged carton", is_mandatory=True)
        InspectionCharacteristic.objects.create(
            plan=oqc, sequence=40, name="Serial label legible", characteristic_type="pass_fail",
            expected_text="Label scans first time", is_mandatory=True)

        checklist = InspectionPlan.objects.create(
            tenant=tenant, code="AUD-ISO9001", name="ISO 9001:2015 internal audit checklist",
            plan_type="audit_checklist", sampling_method="all_100", frequency="periodic",
            version="1", effective_from=today - datetime.timedelta(days=120), is_active=True,
            notes="Reused as the question set on an internal audit — the same table, no second "
                  "checklist model.")
        for index, question in enumerate([
            "Document control procedure is followed",
            "Training records are current for every operator",
            "Measuring equipment is within its calibration date",
            "Previous corrective actions were closed and verified",
            "The internal audit programme is on schedule",
        ], start=1):
            InspectionCharacteristic.objects.create(
                plan=checklist, sequence=index * 10, name=question,
                characteristic_type="pass_fail", expected_text="Conforms", is_mandatory=True)

        # ------------------------------------------------- 2) QC-00001 — incoming, passes cleanly
        qc1 = QualityInspection.objects.create(
            tenant=tenant, plan=iqc, inspection_type="incoming", goods_receipt=grn, item=ws16,
            lot_serial=ws16_lot, location=main, supplier=supplier,
            quantity_inspected=Decimal("5"), sample_size=Decimal("1"),
            quantity_accepted=Decimal("5"), quantity_rejected=ZERO, inspector=inspector,
            inspected_on=today - datetime.timedelta(days=10),
            notes="Routine incoming check against the receipt.")
        qc1.generate_results()
        qc1.status = "in_progress"
        qc1.save(update_fields=["status", "updated_at"])
        for row in qc1.results.all():
            if row.characteristic_type == "measurement":
                row.measured_value = Decimal("16")
            elif row.characteristic_type in ("pass_fail", "visual"):
                row.text_value = "As specified"
                row.result = "pass"
            row.save()   # save() is the single writer of `result` — see _evaluate
        qc1 = QualityInspection.objects.get(pk=qc1.pk)
        qc1.status = "passed" if qc1.evaluated_result == "pass" else "failed"
        qc1.usage_decision = "accept"
        qc1.save(update_fields=["status", "usage_decision", "updated_at"])

        # ------------------------------- 3) QC-00002 — the critical measurement fails, NCR follows
        qc2 = QualityInspection.objects.create(
            tenant=tenant, plan=iqc, inspection_type="incoming", goods_receipt=grn, item=ws16,
            lot_serial=ws16_lot, location=main, supplier=supplier,
            quantity_inspected=Decimal("4"), sample_size=Decimal("1"),
            quantity_accepted=Decimal("2"), quantity_rejected=Decimal("2"), inspector=inspector,
            inspected_on=today - datetime.timedelta(days=6),
            notes="Second receipt from the same supplier — port count short.")
        qc2.generate_results()
        qc2.status = "in_progress"
        qc2.save(update_fields=["status", "updated_at"])
        for row in qc2.results.all():
            if row.characteristic_type == "measurement":
                # 15 against a 16-16 band — out of spec, and the characteristic is CRITICAL, so
                # evaluated_result fails the lot however the rest read.
                row.measured_value = Decimal("15")
                row.notes = "Two ports missing on the sampled unit."
            elif row.characteristic_type in ("pass_fail", "visual"):
                row.text_value = "As specified"
                row.result = "pass"
            row.save()
        qc2 = QualityInspection.objects.get(pk=qc2.pk)
        qc2.status = "passed" if qc2.evaluated_result == "pass" else "failed"
        qc2.usage_decision = "reject"
        qc2.save(update_fields=["status", "usage_decision", "updated_at"])

        # The raise-NCR conversion, field for field as qualityinspection_raise_ncr builds it.
        ncr1 = NonConformance.objects.create(
            tenant=tenant, source="inspection", inspection=qc2, goods_receipt=grn, item=ws16,
            lot_serial=ws16_lot, location=main, supplier=supplier,
            quantity_affected=qc2.quantity_rejected, uom=ws16.uom,
            defect_category="functional",
            severity="critical" if qc2.has_critical_failure else "major",
            title=f"Failed inspection {qc2.number} — {ws16.sku}",
            description=(f"Raised from quality inspection {qc2.number}. Port count measured 15 "
                         "against a specification of 16."),
            detected_by=inspector, detected_on=qc2.inspected_on,
            containment_action="Affected units moved to the quality bench and the lot quarantined.",
            cost_of_quality=q2((qc2.quantity_rejected or ZERO) * (ws16.average_cost or ZERO)),
            owner=inspector, due_date=today + datetime.timedelta(days=7))
        qc2.action_taken = "ncr_raised"
        qc2.save(update_fields=["action_taken", "updated_at"])

        # Quarantine flips the LOT's status and posts NOTHING (ruling (b)) — then the scrap posts
        # ONE negative `adjustment` move carrying the NCR number (ruling (a)).
        with transaction.atomic():
            ws16_lot.status = "quarantine"
            ws16_lot.save(update_fields=["status", "updated_at"])
            ncr1.quarantine_applied = True
            scrap_qty = ncr1.quantity_affected
            ncr1.disposition = "scrap"
            ncr1.disposition_quantity = scrap_qty
            ncr1.disposition_by = inspector
            ncr1.disposition_on = timezone.now()
            ncr1.disposition_notes = "Material review board: units are unrepairable — write off."
            ncr1.status = "dispositioned"
            if ncr1.posts_stock and not _insufficient_stock(ws16, main, scrap_qty, ws16_lot):
                _post_stock_move(
                    tenant, item=ws16, location=main, quantity=-scrap_qty,
                    move_type="adjustment", unit_cost=ws16.average_cost or ZERO,
                    lot_serial=ws16_lot, reference=ncr1.number,
                    reason=f"NCR scrap — {ncr1.get_defect_category_display()}")
            ncr1.save()

        # --------------------- 4) NCR-00002 — dock rejection: dispositioned, but posts NOTHING
        ncr2 = NonConformance.objects.create(
            tenant=tenant, source="goods_receipt", goods_receipt=grn, item=mon27, supplier=supplier,
            location=None, quantity_affected=Decimal("1"), uom=mon27.uom,
            defect_category="packaging", severity="minor",
            title=f"Damaged carton refused at the dock — {grn.number}",
            description="One monitor carton crushed in transit; refused on arrival and never "
                        "booked into stock.",
            detected_by=inspector, detected_on=today - datetime.timedelta(days=8),
            containment_action="Refused at goods-in; the carrier signed the delivery note.",
            cost_of_quality=Decimal("0"), owner=inspector)
        ncr2.disposition = "return_to_vendor"
        ncr2.disposition_quantity = Decimal("1")
        ncr2.disposition_by = inspector
        ncr2.disposition_on = timezone.now()
        # posts_stock is False here BECAUSE source == "goods_receipt" — the rule is executable, not
        # a comment somebody has to remember. The return authorisation itself is 4.10's document.
        ncr2.disposition_notes = ("Returned to the supplier. Units rejected at the dock never "
                                  "entered stock, so this has no ledger effect.")
        ncr2.status = "dispositioned"
        ncr2.save()

        # ------------------------------------------------------------------------ 5) the audits
        audit1 = QualityAudit.objects.create(
            tenant=tenant, audit_type="internal", title="Annual internal quality-system audit",
            standard="ISO 9001:2015",
            scope="Goods-in inspection, calibration control and the corrective-action process.",
            auditee_org_unit=self._org_unit(tenant), checklist_plan=checklist,
            lead_auditor=auditor, planned_date=today - datetime.timedelta(days=7),
            risk_level="medium",
            conclusion="The system conforms overall. One minor finding on training records; the "
                       "calibration register is current.")
        audit1.actual_start = today - datetime.timedelta(days=7)
        audit1.actual_end = today - datetime.timedelta(days=6)
        audit1.status = "reported"
        audit1.save(update_fields=["actual_start", "actual_end", "status", "updated_at"])

        audit2 = QualityAudit.objects.create(
            tenant=tenant, audit_type="supplier",
            title=f"Supplier surveillance audit — {supplier.name}", standard="ISO 9001:2015",
            scope="Incoming quality performance and corrective-action responsiveness.",
            auditee_party=supplier, lead_auditor=auditor,
            planned_date=today + datetime.timedelta(days=21), risk_level="high",
            notes="Triggered by the port-count non-conformance.")

        # A finding IS a NonConformance(source="audit") — there is no second findings table, and
        # this is the only shape that creates one.
        ncr3 = NonConformance.objects.create(
            tenant=tenant, source="audit", audit=audit1, item=None, quantity_affected=ZERO,
            defect_category="documentation", severity="minor",
            title="Training records incomplete for two goods-in inspectors",
            description="Two of five goods-in inspectors have no recorded refresher training for "
                        "the current year.",
            detected_by=auditor, detected_on=audit1.actual_end, owner=inspector,
            due_date=today + datetime.timedelta(days=30),
            containment_action="Refresher session booked for both inspectors.")

        # ------------------------------------------------------------------------ 6) the CAPAs
        capa1 = CapaAction.objects.create(
            tenant=tenant, action_type="corrective", source="nonconformance", nonconformance=ncr1,
            item=ws16, supplier=supplier, title=ncr1.title, problem_statement=ncr1.description,
            containment_action=ncr1.containment_action, root_cause_method="five_why",
            root_cause="The supplier changed its board revision without notifying us, and our "
                       "incoming spec was never re-issued against the new part number.",
            action_plan="Re-issue the incoming specification against the new part number, add a "
                        "change-notification clause to the supply contract and re-train goods-in.",
            owner=inspector, priority="high", due_date=today + datetime.timedelta(days=14),
            effectiveness_due_date=today + datetime.timedelta(days=45))
        CapaTask.objects.create(capa=capa1, sequence=10,
                                description="Re-issue IQC-WS16 against the new part number",
                                owner=inspector, due_date=today + datetime.timedelta(days=5),
                                completed_on=today - datetime.timedelta(days=1), status="done")
        CapaTask.objects.create(capa=capa1, sequence=20,
                                description="Add a change-notification clause to the supply contract",
                                owner=auditor, due_date=today + datetime.timedelta(days=10),
                                status="open")
        CapaTask.objects.create(capa=capa1, sequence=30,
                                description="Re-train the goods-in team on the revised spec",
                                owner=inspector, due_date=today + datetime.timedelta(days=12),
                                status="open")
        capa1.status = "in_progress"
        capa1.save(update_fields=["status", "updated_at"])

        # The SCAR: a supplier-sourced preventive action, driven to the state capaaction_verify
        # actually accepts, so the verification button has a live target on first load.
        capa2 = CapaAction.objects.create(
            tenant=tenant, action_type="preventive", source="supplier", supplier=supplier,
            title=f"Supplier corrective-action request — {supplier.name}",
            problem_statement="Two quality escapes in one quarter from the same supplier.",
            root_cause_method="pareto",
            root_cause="Both escapes trace to unannounced component substitutions.",
            action_plan="Supplier to implement a change-control notification and a first-article "
                        "submission for every revision.",
            owner=auditor, priority="normal", due_date=today - datetime.timedelta(days=2),
            effectiveness_due_date=today + datetime.timedelta(days=30))
        CapaTask.objects.create(capa=capa2, sequence=10,
                                description="Supplier change-control procedure received and reviewed",
                                owner=auditor, due_date=today - datetime.timedelta(days=5),
                                completed_on=today - datetime.timedelta(days=4), status="done")
        capa2.status = "pending_verification"
        capa2.implemented_on = today - datetime.timedelta(days=3)
        capa2.save(update_fields=["status", "implemented_on", "updated_at"])

        # -------------------------- 7) QC-00003 — outgoing, passes, and IS certified (COA-00001)
        qc3 = QualityInspection.objects.create(
            tenant=tenant, plan=oqc, inspection_type="outgoing", shipment=shipment, item=mon27,
            lot_serial=mon_lot, location=main, quantity_inspected=Decimal("10"),
            sample_size=Decimal("5"), quantity_accepted=Decimal("10"), quantity_rejected=ZERO,
            inspector=inspector, inspected_on=today - datetime.timedelta(days=2),
            notes="Pre-shipment inspection — the batch this certificate covers.")
        qc3.generate_results()
        qc3.status = "in_progress"
        qc3.save(update_fields=["status", "updated_at"])
        measurements = {"Luminance": Decimal("302"), "Dead pixels": ZERO}
        for row in qc3.results.all():
            if row.characteristic_type == "measurement":
                row.measured_value = measurements.get(row.characteristic_name, ZERO)
            else:
                row.text_value = "As specified"
                row.result = "pass"
            row.save()
        qc3 = QualityInspection.objects.get(pk=qc3.pk)
        qc3.status = "passed" if qc3.evaluated_result == "pass" else "failed"
        qc3.usage_decision = "accept"
        qc3.save(update_fields=["status", "usage_decision", "updated_at"])

        # coa_blockers() is the gate the Issue action uses; asking it here means the seed can never
        # produce a certificate the app itself would have refused.
        customer = (shipment.sales_order.customer
                    if shipment.sales_order_id else None)
        blockers = qc3.coa_blockers()
        if blockers:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: {qc3.number} is not certifiable ({blockers[0]}) — no CoA issued."))
        else:
            qc3.coa_number = next_number(QualityInspection, tenant, "COA", field="coa_number")
            qc3.coa_issued_on = timezone.now()
            qc3.coa_issued_to = customer
            qc3.save(update_fields=["coa_number", "coa_issued_on", "coa_issued_to", "updated_at"])

        self.stdout.write(
            f"{tenant.name}: quality — 3 inspection plans, inspections {qc1.number}/{qc2.number}/"
            f"{qc3.number} (CoA {qc3.coa_number or 'not issued'}), NCRs {ncr1.number}/"
            f"{ncr2.number}/{ncr3.number} ({ncr1.number} scrapped {ncr1.disposition_quantity} "
            f"{ws16.sku} through an adjustment move), CAPAs {capa1.number}/{capa2.number}, "
            f"audits {audit1.number}/{audit2.number}.")

    def _seed_returns_tenant(self, tenant):
        """4.10 Returns demo: four reason codes, a default policy, three RMAs (one credit-only),
        a graded bench across three dispositions — one of which posts a REAL written-down restock
        through the ledger — a drafted credit note and a supplier warranty claim.

        Idempotent via a ``ReturnReason`` guard on the FIRST thing this block writes, NOT on the
        RMAs: the reasons are plain ``.create()`` calls against a unique ``("tenant", "code")``, so
        a run that aborted between them and the first RMA would leave a re-run to IntegrityError on
        a guard that had not yet tripped (the same correction 4.9's seeder already carries).

        Runs LAST — it returns goods against 4.5's sales orders onto 4.3's locations, restocks
        through 4.3's posting service, drafts against the accounting spine and claims against a
        4.1 supplier, so every one of those must already exist.

        Everything goes through the SAME code the views run: ``select_policy`` picks the governing
        policy, ``evaluate_return_eligibility`` produces the verdict that is frozen into
        ``policy_snapshot``, ``policy.restock_cost_for`` seeds each row's write-down, and the
        restock posts through ``_post_stock_move`` behind ``_insufficient_stock``. Nothing here
        hand-sets a field that merely looks plausible.
        """
        import json as _json

        from apps.scm.models import (Location, LotSerial, ReturnAuthorization, ReturnDisposition,
                                     ReturnLine, ReturnPolicy, ReturnReason, SalesOrder,
                                     SalesOrderLine, WarrantyClaim, WarrantyClaimCost,
                                     evaluate_return_eligibility, select_policy)
        from apps.scm.views._helpers import _post_stock_move
        from apps.scm.models._base import ZERO, q2, q4
        # Guarded on ReturnReason — the first row this block writes.
        if ReturnReason.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: returns data already exists — skipping.")
            return

        # ---- prerequisites: warn and RETURN rather than half-seed -------------------------------
        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
        order = (SalesOrder.objects.filter(tenant=tenant)
                 .exclude(status="cancelled").order_by("id").first())
        order_line = (SalesOrderLine.objects.filter(sales_order=order, item__isnull=False)
                      .select_related("item").order_by("id").first() if order else None)
        supplier = Party.objects.filter(tenant=tenant,
                                        name="Northwind Industrial Supply").first()
        clerk = self._employee(tenant, "Sophia Miller")
        if any(x is None for x in (main, order, order_line, supplier, clerk)):
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: missing location / sales order with a mapped item / supplier / "
                "employee party — skipping returns seed."))
            return

        today = timezone.localdate()
        item = order_line.item
        currency = Currency.objects.filter(code="USD").first()
        category = item.category

        # A dedicated returns bench, so the demo shows the bench being a DIFFERENT place from
        # sellable stock — which is the whole point of restock_location != location.
        bench, _ = Location.objects.get_or_create(
            tenant=tenant, code="WH-RETURNS",
            defaults={"name": "Returns bench", "location_type": "staging", "parent": main,
                      "is_active": True, "is_pickable": False})

        # 4.9 flips WS-16 and MON-27 to tracking="lot", and ReturnDisposition.clean() REQUIRES a
        # lot on a tracked item — returned serialised goods that land in the ledger with no lot are
        # untraceable and defeat the lot_history panel. So the returned units get their own batch
        # rather than being folded into 4.9's WS16-2409, which that seeder deliberately leaves
        # QUARANTINED: restocking into a quarantined lot would silently undo a quality decision.
        returned_lot = None
        if item.tracking != "none":
            returned_lot, _ = LotSerial.objects.get_or_create(
                tenant=tenant, item=item, number=f"{item.sku}-RET-01",
                defaults={"kind": "lot", "status": "available",
                          "notes": "Batch the seeded customer returns came back on."})

        # ---------------------------------------------------------------- 1) the reason master
        reasons = {}
        for code, name, fault, kwargs in [
            ("CHANGED-MIND", "Changed their mind", "customer",
             {"suggested_disposition": "restock", "allows_repair": False}),
            ("DAMAGED-TRANSIT", "Arrived damaged", "carrier",
             {"waives_return_fee": True, "suggested_disposition": "scrap",
              "requires_photo": False, "raises_nonconformance": True}),
            ("FAULTY", "Faulty on arrival", "supplier",
             {"waives_return_fee": True, "allows_repair": True,
              "suggested_disposition": "return_to_vendor", "raises_nonconformance": True,
              "follow_up_question": "What happens when you switch it on?"}),
            ("CONTAMINATED", "Contaminated / unsafe to resell", "unknown",
             {"waives_return_fee": True, "blocks_restock": True,
              "suggested_disposition": "scrap", "allows_exchange": False,
              "raises_nonconformance": True}),
        ]:
            reasons[code] = ReturnReason.objects.create(
                tenant=tenant, code=code, name=name, fault_party=fault,
                sort_order=10 * (len(reasons) + 1), **kwargs)

        # ---------------------------------------------------------------- 2) the policy
        policy = ReturnPolicy.objects.create(
            tenant=tenant, name="Standard 30-day returns", is_active=True, is_default=True,
            priority=10, item_category=category,
            window_basis="delivery", window_days=30, fallback_days=45,
            allow_refund=True, allow_store_credit=True, allow_exchange=True,
            allow_keep_item=False,
            refund_basis="full", restocking_fee_type="percent_of_value",
            restocking_fee_value=Decimal("10.00"), return_shipping_paid_by="by_fault",
            auto_approve=False,
            grade_a_cost_pct=Decimal("100"), grade_b_cost_pct=Decimal("75"),
            grade_c_cost_pct=Decimal("40"), grade_d_cost_pct=ZERO,
            warranty_window_days=365,
            return_to_address=("NavERP Returns\nUnit 4, Riverside Industrial Park\n"
                               "Manchester M17 1WA\nUnited Kingdom"),
            portal_instructions=("Pack the item in its original box, print the return slip and "
                                 "attach it to the outside of the parcel. Drop it at any carrier "
                                 "point within 14 days of your return being approved."))
        # select_policy is the app's own picker — asking it here means the seed can never produce a
        # return governed by a policy the app itself would not have chosen.
        assert select_policy(tenant, item) is not None

        # ------------------------------------- 3) RMA-00001 — the full journey, and the ONE post
        rma1 = ReturnAuthorization(
            tenant=tenant, customer=order.customer, sales_order=order, return_type="physical",
            source="portal", policy=policy, requested_on=today - datetime.timedelta(days=9),
            resolution="refund", refund_method="original_tender", return_method="mail_prepaid",
            return_tracking_number="RT-4410-88213", currency=currency,
            notes="Seeded: customer changed their mind on part of the order.")
        rma1.save()
        qty1 = min(Decimal("3"), order_line.quantity_ordered or Decimal("3"))
        line1 = ReturnLine.objects.create(
            return_authorization=rma1, sales_order_line=order_line, item=item,
            description=item.name, quantity_requested=qty1, quantity_approved=qty1,
            reason=reasons["CHANGED-MIND"], unit_price=order_line.unit_price or ZERO,
            tax_pct=order_line.tax_pct or ZERO,
            # What it COST us, never what they paid — restocking at unit_price would roll
            # Item.average_cost up toward the selling price.
            unit_cost=q4(item.average_cost or item.standard_cost or ZERO),
            line_fee=policy.fee_for(q2(qty1 * (order_line.unit_price or ZERO))),
            lot_serial=returned_lot,
            condition_reported="Unopened, original packaging.")

        # Approve through the SAME verdict the approve action freezes.
        verdict = evaluate_return_eligibility(
            order, item, reasons["CHANGED-MIND"], policy,
            as_of=rma1.requested_on,
            line_value=q2(qty1 * (order_line.unit_price or ZERO)))
        verdict["approved_resolution"] = "refund"
        # The seeded order carries no delivery stamp (it is a manual human action in 4.5), so the
        # verdict falls through to the ORDER-DATE fallback window — exactly the case the plan says
        # will be common, and the demo shows `basis_used` saying so on the detail page.
        verdict["window_overridden"] = bool(verdict["blockers"])
        verdict["approved_by_user"] = "seed_scm"
        verdict["approved_on"] = (today - datetime.timedelta(days=8)).isoformat()
        rma1.status = "received"
        rma1.approved_on = today - datetime.timedelta(days=8)
        rma1.approved_by = clerk
        rma1.policy_snapshot = _json.dumps(verdict)
        rma1.customer_shipped_on = today - datetime.timedelta(days=6)
        rma1.save(update_fields=["status", "approved_on", "approved_by", "policy_snapshot",
                                 "customer_shipped_on", "updated_at"])

        # Three units back as 2 restock + 1 scrap — the case that justifies the row grain at all.
        restock_qty = qty1 - Decimal("1") if qty1 > Decimal("1") else qty1
        scrap_qty = qty1 - restock_qty
        d_restock = ReturnDisposition.objects.create(
            tenant=tenant, return_line=line1, quantity=restock_qty,
            received_on=today - datetime.timedelta(days=3), received_by=clerk, location=bench,
            lot_serial=returned_lot,
            condition_grade="b", disposition="restock", restock_location=main,
            restock_unit_cost=policy.restock_cost_for("b", item.average_cost or ZERO),
            notes="Light shelf wear; goes back as B-grade at the written-down cost.")
        # THE ledger write — a POSITIVE `receipt` at the graded cost, carrying the RMA number.
        # Not `issue` (4.7's demand series negates issues and a positive one would deflate every
        # forecast) and not `transfer` (the FIFO/LIFO walk excludes transfers, so the write-down
        # would never become a cost layer).
        with transaction.atomic():
            move = _post_stock_move(
                tenant, item=item, location=main, quantity=restock_qty, move_type="receipt",
                unit_cost=q4(d_restock.restock_unit_cost), lot_serial=returned_lot,
                reference=rma1.number, reason="Return restock — grade B",
                moved_at=timezone.now() - datetime.timedelta(days=3))
            d_restock.stock_posted = True
            d_restock.stock_move = move
            d_restock.decided_on = today - datetime.timedelta(days=3)
            d_restock.decided_by = clerk
            d_restock.save(update_fields=["stock_posted", "stock_move", "decided_on", "decided_by",
                                          "updated_at"])
        d_scrap = None
        if scrap_qty > ZERO:
            # Scrapped STRAIGHT OFF THE BENCH, so it posts NOTHING: the unit never entered stock.
            # posts_stock is False here for exactly that reason — an executable rule, not a comment.
            d_scrap = ReturnDisposition.objects.create(
                tenant=tenant, return_line=line1, quantity=scrap_qty,
                received_on=today - datetime.timedelta(days=3), received_by=clerk,
                location=bench, lot_serial=returned_lot,
                condition_grade="d", disposition="scrap",
                restock_unit_cost=policy.restock_cost_for("d", item.average_cost or ZERO),
                decided_on=today - datetime.timedelta(days=3), decided_by=clerk,
                notes="Crushed corner; unsellable. Posted nothing — it never entered stock.")

        # -------------------------------------- 4) RMA-00002 — the credit-only trap, made visible
        # This one never gets a bench row, so every queue keyed on "received" would silently drop
        # it. It exists in the seed so the refund queue's credit_only branch has a live subject.
        rma2 = ReturnAuthorization(
            tenant=tenant, customer=order.customer, sales_order=order, return_type="credit_only",
            source="csr", policy=policy, requested_on=today - datetime.timedelta(days=4),
            resolution="refund", refund_method="original_tender", return_method="keep_item",
            currency=currency,
            notes="Seeded: cheap item, freight costs more than the unit — credit only, no goods "
                  "coming back.")
        rma2.save()
        ReturnLine.objects.create(
            return_authorization=rma2, sales_order_line=order_line, item=item,
            description=item.name, quantity_requested=Decimal("1"),
            quantity_approved=Decimal("1"), reason=reasons["DAMAGED-TRANSIT"],
            unit_price=order_line.unit_price or ZERO, tax_pct=order_line.tax_pct or ZERO,
            unit_cost=q4(item.average_cost or ZERO), line_fee=ZERO,
            lot_serial=returned_lot,
            condition_reported="Photographed on arrival, box crushed.")
        rma2.status = "settled"
        rma2.approved_on = today - datetime.timedelta(days=4)
        rma2.approved_by = clerk
        rma2.save(update_fields=["status", "approved_on", "approved_by", "updated_at"])

        # --------------------------------------- 5) the credit note — a DRAFT, and nothing more
        # Field for field as returnauthorization_draft_credit_note builds it, including the
        # tax_pct carry-across (without it every refund under-credits the customer by the VAT) and
        # the NEGATIVE fee line. SCM posts no JournalEntry (L29) and does not issue the note.
        from apps.accounting.models import Invoice, InvoiceLine
        subtotal, fee, tax, credit_total = rma1.settlement_figures
        credit_note = None
        if credit_total > ZERO and currency is not None:
            credit_note = Invoice(tenant=tenant, party=rma1.customer, kind="credit_note",
                                  status="draft", issue_date=today - datetime.timedelta(days=2),
                                  currency=currency,
                                  notes=f"Return {rma1.number} · order {order.number}")
            credit_note.save()
            for line in rma1.lines.select_related("item"):
                quantity = line.credit_quantity
                if quantity <= ZERO:
                    continue
                InvoiceLine.objects.create(
                    invoice=credit_note,
                    description=f"{line.item.sku} — {line.description} (return {rma1.number})",
                    quantity=quantity, unit_price=line.unit_price or ZERO,
                    tax_rate_pct=line.tax_pct or ZERO)
            if fee > ZERO:
                InvoiceLine.objects.create(
                    invoice=credit_note,
                    description=f"Restocking / handling fee — {rma1.number}",
                    quantity=Decimal("1"), unit_price=-fee, tax_rate_pct=ZERO)
            credit_note.recalc_totals()
            rma1.credit_note = credit_note
            rma1.refund_subtotal, rma1.fee_total = subtotal, fee
            rma1.tax_total, rma1.credit_total = tax, credit_total
            rma1.status = "settled"
            rma1.save(update_fields=["credit_note", "refund_subtotal", "fee_total", "tax_total",
                                     "credit_total", "status", "updated_at"])

        # -------------------------- 6) RMA-00003 — still on the bench, so the queue has a subject
        rma3 = ReturnAuthorization(
            tenant=tenant, customer=order.customer, sales_order=order, return_type="physical",
            source="phone", policy=policy, requested_on=today - datetime.timedelta(days=2),
            resolution="exchange", refund_method="none", return_method="drop_off",
            dropoff_location=main, currency=currency, advance_refund=True,
            advance_refund_deadline=today + datetime.timedelta(days=12),
            notes="Seeded: advance refund given, goods still awaiting disposition.")
        rma3.save()
        line3 = ReturnLine.objects.create(
            return_authorization=rma3, sales_order_line=order_line, item=item,
            description=item.name, quantity_requested=Decimal("1"),
            quantity_approved=Decimal("1"), reason=reasons["FAULTY"],
            unit_price=order_line.unit_price or ZERO, tax_pct=order_line.tax_pct or ZERO,
            unit_cost=q4(item.average_cost or ZERO), line_fee=ZERO,
            lot_serial=returned_lot,
            condition_reported="Will not power on.")
        rma3.status = "received"
        rma3.approved_on = today - datetime.timedelta(days=2)
        rma3.approved_by = clerk
        rma3.save(update_fields=["status", "approved_on", "approved_by", "updated_at"])
        d_pending = ReturnDisposition.objects.create(
            tenant=tenant, return_line=line3, quantity=Decimal("1"),
            received_on=today - datetime.timedelta(days=1), received_by=clerk, location=bench,
            lot_serial=returned_lot,
            condition_grade="c", disposition="received_pending",
            restock_unit_cost=policy.restock_cost_for("c", item.average_cost or ZERO),
            notes="On the bench awaiting a decision — deliberately off-ledger until dispositioned.")

        # --------------------------------------------------- 7) the supplier warranty claim
        # Drafts NOTHING in accounting: accounting.Bill has no `kind` field, so there is no
        # vendor-credit document to raise. The claim records the amounts and stops.
        claim = WarrantyClaim(
            tenant=tenant, supplier=supplier, item=item, quantity_claimed=Decimal("1"),
            lot_serial=returned_lot, return_authorization=rma3,
            # Back-dated deliberately rather than taken from the seeded order: 4.5 stamps every
            # demo order with TODAY's date, so reusing it would put the failure BEFORE the purchase
            # and make `is_in_warranty` render False on a unit that plainly is in warranty.
            purchase_date=today - datetime.timedelta(days=120),
            warranty_start=today - datetime.timedelta(days=120),
            warranty_end=today + datetime.timedelta(days=245),
            failure_date=today - datetime.timedelta(days=3),
            usage_context="Desk use, powered daily.", defect_classification="component",
            supplier_rma_number="NW-CLM-77120", submission_channel="email",
            response_due_on=today + datetime.timedelta(days=16),
            description=(f"Raised from return {rma3.number}. Unit will not power on; customer "
                         "reports no impact damage."),
            notes="Seeded warranty claim.")
        claim.save()
        for cost_type, description, quantity, unit_amount, approved in [
            ("part", "Replacement mainboard", Decimal("1"), Decimal("185.00"), Decimal("185.00")),
            ("labour", "Bench diagnosis and swap (1.5h)", Decimal("1.5"), Decimal("60.00"), ZERO),
            ("freight", "Return freight to supplier", Decimal("1"), Decimal("24.00"),
             Decimal("24.00")),
        ]:
            WarrantyClaimCost.objects.create(
                claim=claim, cost_type=cost_type, description=description, quantity=quantity,
                unit_amount=unit_amount, amount_approved=approved)
        # The realistic outcome: they accept the part and the freight and refuse the labour. A flat
        # claim_value column could not express that, which is why the child table exists.
        claim.status = "partially_approved"
        claim.submitted_on = today - datetime.timedelta(days=2)
        claim.responded_on = today - datetime.timedelta(days=1)
        claim.amount_approved = claim.cost_approved_total
        claim.supplier_response_notes = (
            f"[{today - datetime.timedelta(days=1):%Y-%m-%d} Partially approved] Part and freight "
            "accepted; labour is outside the terms of the supply agreement.")
        claim.save(update_fields=["status", "submitted_on", "responded_on", "amount_approved",
                                  "supplier_response_notes", "updated_at"])

        # ---------- 7) RMA-00004 — approved and awaiting the parcel, so the two token pages have a
        # subject. LABEL_STATUSES is ("approved","awaiting_receipt","partially_received"): without a
        # seeded RMA in one of them, `returnauthorization_label` — this sub-module's only print page
        # — 404s for every demo record, and the public status page never offers "I've shipped it".
        rma4 = ReturnAuthorization(
            tenant=tenant, customer=order.customer, sales_order=order, return_type="physical",
            source="portal", policy=policy, requested_on=today - datetime.timedelta(days=1),
            resolution="refund", refund_method="original_tender", return_method="mail_prepaid",
            currency=currency,
            notes="Seeded: approved and awaiting the parcel — the return slip prints for this one.")
        rma4.save()
        ReturnLine.objects.create(
            return_authorization=rma4, sales_order_line=order_line, item=item,
            description=item.name, quantity_requested=Decimal("1"),
            quantity_approved=Decimal("1"), reason=reasons["FAULTY"],
            unit_price=order_line.unit_price or ZERO, tax_pct=order_line.tax_pct or ZERO,
            unit_cost=q4(item.average_cost or ZERO), line_fee=ZERO,
            condition_reported="Screen flickers intermittently.")
        rma4.status = "awaiting_receipt"
        rma4.approved_on = today - datetime.timedelta(days=1)
        rma4.approved_by = clerk
        rma4.save(update_fields=["status", "approved_on", "approved_by", "updated_at"])

        self.stdout.write(
            f"{tenant.name}: returns — {len(reasons)} reason codes, policy '{policy.name}', "
            f"RMAs {rma1.number} (restocked {d_restock.quantity} {item.sku} at "
            f"{d_restock.restock_unit_cost} through a receipt move"
            + (f", scrapped {d_scrap.quantity} off-ledger" if d_scrap else "")
            + f"), {rma2.number} [credit-only], {rma3.number} "
            f"({d_pending.quantity} on the bench awaiting disposition), {rma4.number} "
            f"[awaiting receipt — its return slip prints], credit note "
            f"{credit_note.number if credit_note else 'not drafted'}, warranty claim "
            f"{claim.number} [{claim.get_status_display()}].")

    # ------------------------------------------------------------------ spine reuse helpers
    def _admin(self, tenant):
        return (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                or User.objects.filter(tenant=tenant).first())

    def _employee(self, tenant, name=None):
        """LOOK UP an employee Party — never create one.

        `seed_core` already creates four (Olivia Martin, Liam Johnson, Emma Williams, Sophia
        Miller), and 4.9 reuses `core.Party` + `PartyRole("employee")` for every inspector,
        auditor, owner and verifier rather than adding a person table (L29). Unlike `_supplier` /
        `_customer` this deliberately does NOT get-or-create: an inspector invented by a seeder
        would be a person nobody hired.
        """
        qs = Party.objects.filter(tenant=tenant, roles__role="employee").distinct()
        if name:
            match = qs.filter(name=name).first()
            if match is not None:
                return match
        return qs.order_by("id").first()

    def _supplier(self, tenant, name, kind):
        """Get-or-create a supplier Party by NAME (never duplicate the spine).

        Matched on name rather than "first party with this role" so the two demo suppliers stay
        distinct — an RFQ with one supplier quoting twice would defeat the comparison page.
        """
        party = Party.objects.filter(tenant=tenant, name=name).first()
        if party is None:
            party = Party.objects.create(tenant=tenant, kind=kind, name=name)
        PartyRole.objects.get_or_create(
            tenant=tenant, party=party, role="supplier",
            defaults={"status": "active", "start_date": timezone.localdate()},
        )
        return party

    def _customer(self, tenant, name, kind, credit_limit=None):
        """Get-or-create a customer Party (+ its accounting CustomerProfile) by NAME.

        Mirrors _supplier, with the `customer` role. Writing an accounting.CustomerProfile from
        here is consistent with this seeder already creating accounting Bill/Budget rows — and 4.5's
        credit hold has nothing to check against without one.
        """
        from apps.accounting.models import CustomerProfile
        party = Party.objects.filter(tenant=tenant, name=name).first()
        if party is None:
            party = Party.objects.create(tenant=tenant, kind=kind, name=name)
        PartyRole.objects.get_or_create(
            tenant=tenant, party=party, role="customer",
            defaults={"status": "active", "start_date": timezone.localdate()},
        )
        if credit_limit is not None:
            CustomerProfile.objects.get_or_create(
                tenant=tenant, party=party,
                defaults={"credit_limit": credit_limit},
            )
        return party

    def _org_unit(self, tenant):
        return (OrgUnit.objects.filter(tenant=tenant, kind="department").order_by("id").first()
                or OrgUnit.objects.filter(tenant=tenant).order_by("id").first())

    def _expense_account(self, tenant):
        """An expense GL account to charge — falls back to any account if the CoA looks different."""
        return (GLAccount.objects.filter(tenant=tenant, code__startswith="5").order_by("code").first()
                or GLAccount.objects.filter(tenant=tenant).order_by("code").first())

    # ------------------------------------------------------------------ the seed itself
    def _seed_tenant(self, tenant):
        today = timezone.localdate()
        admin = self._admin(tenant)
        currency = Currency.objects.filter(code="USD").first()
        terms = PaymentTerm.objects.filter(tenant=tenant).order_by("id").first()
        org_unit = self._org_unit(tenant)
        account = self._expense_account(tenant)
        budget = Budget.objects.filter(tenant=tenant).order_by("id").first()

        suppliers = [self._supplier(tenant, name, kind) for name, kind in SUPPLIERS]

        # Make the budget check on the requisition detail page meaningful: ensure the budget has a
        # line for the account we are charging. Without it budget_check() returns None and the card
        # would just say "no budget linked", which shows nothing off.
        if budget and account:
            BudgetLine.objects.get_or_create(
                tenant=tenant, budget=budget, gl_account=account, org_unit=None,
                defaults={"amount": Decimal("25000.00")},
            )

        # ---- 1. an approved requisition -------------------------------------------------
        req = PurchaseRequisition(
            tenant=tenant, title="Q3 workstation refresh", requester=admin, org_unit=org_unit,
            budget=budget, currency=currency, required_by=today + datetime.timedelta(days=30),
            status="approved", approved_by=admin, approved_at=timezone.now(),
            decision_note="Approved against the Q3 capex allowance.",
            justification="Replacing end-of-life laptops for the engineering team.",
        )
        req.save()
        for desc, sku, uom, qty, price in REQUISITION_LINES:
            PurchaseRequisitionLine.objects.create(
                requisition=req, item_description=desc, sku_hint=sku, uom_hint=uom,
                quantity=qty, estimated_unit_price=price, gl_account=account,
                needed_by=today + datetime.timedelta(days=30),
            )
        req.recalc_totals()

        # ---- 2. a draft requisition awaiting approval (so the queue is not empty) --------
        pending = PurchaseRequisition(
            tenant=tenant, title="Warehouse safety equipment", requester=admin, org_unit=org_unit,
            budget=budget, currency=currency, required_by=today + datetime.timedelta(days=14),
            status="pending_approval",
            justification="Annual replacement of high-vis gear and safety boots.",
        )
        pending.save()
        PurchaseRequisitionLine.objects.create(
            requisition=pending, item_description="High-visibility jacket", sku_hint="HV-J",
            uom_hint="each", quantity=Decimal("20"), estimated_unit_price=Decimal("34.50"),
            gl_account=account, needed_by=today + datetime.timedelta(days=14),
        )
        pending.recalc_totals()

        # ---- 3. an RFQ sent to both suppliers, with competing quotes --------------------
        rfq = RFQ(
            tenant=tenant, title="Workstation refresh sourcing", requisition=req, currency=currency,
            issue_date=today - datetime.timedelta(days=10),
            response_due=today - datetime.timedelta(days=3),
            status="sent",
            terms="Delivery DDP. Net 30. Prices held for 60 days.",
        )
        rfq.save()
        rfq_lines = [
            RFQLine.objects.create(
                rfq=rfq, item_description=desc, sku_hint=sku, uom_hint=uom, quantity=qty,
                specification="Business-grade, 3-year warranty.",
            )
            for desc, sku, uom, qty, _price in REQUISITION_LINES
        ]
        for supplier in suppliers:
            RFQVendor.objects.get_or_create(
                tenant=tenant, rfq=rfq, party=supplier,
                defaults={"invited_at": timezone.now(), "contact_note": "Sent to account manager."},
            )

        # Two quotes that genuinely differ per line, so the comparison page has a real winner per
        # row rather than one supplier being cheapest on everything.
        quote_prices = [
            # (supplier index, [unit prices per rfq line], lead_time_days)
            (0, [Decimal("1225.00"), Decimal("195.00"), Decimal("298.00")], 14),
            (1, [Decimal("1260.00"), Decimal("172.00"), Decimal("305.00")], 7),
        ]
        quotes = []
        for idx, prices, lead in quote_prices:
            quote = RFQQuote(
                tenant=tenant, rfq=rfq, party=suppliers[idx],
                vendor_reference=f"Q-{2026000 + idx}", received_date=today - datetime.timedelta(days=4),
                valid_until=today + datetime.timedelta(days=56), lead_time_days=lead,
                payment_terms=terms, status="received",
                notes="Includes on-site delivery.",
            )
            quote.save()
            for line, price in zip(rfq_lines, prices):
                RFQQuoteLine.objects.create(
                    quote=quote, rfq_line=line, quantity=line.quantity, unit_price=price,
                    lead_time_days=lead,
                )
            quote.recalc_totals()
            quotes.append(quote)

        # ---- 4. award the cheaper total -> the purchase order ---------------------------
        winner = min(quotes, key=lambda q: q.total)
        winner.status = "awarded"
        winner.save(update_fields=["status", "updated_at"])
        for other in quotes:
            if other.pk != winner.pk:
                other.status = "rejected"
                other.save(update_fields=["status", "updated_at"])
        rfq.status = "awarded"
        rfq.save(update_fields=["status", "updated_at"])
        req.status = "converted"
        req.save(update_fields=["status", "updated_at"])

        po = PurchaseOrder(
            tenant=tenant, vendor=winner.party, requisition=req, quote=winner, currency=currency,
            payment_terms=terms, order_date=today - datetime.timedelta(days=2),
            expected_date=today + datetime.timedelta(days=winner.lead_time_days or 14),
            ship_to=org_unit, status="sent",
            approved_by=admin, approved_at=timezone.now(),
            delivery_address="Receiving dock, gate 2.",
            notes=f"Created from {rfq.number} / quote {winner.number}.",
        )
        po.save()
        for quote_line in winner.lines.select_related("rfq_line"):
            PurchaseOrderLine.objects.create(
                purchase_order=po,
                item_description=quote_line.rfq_line.item_description,
                sku_hint=quote_line.rfq_line.sku_hint,
                uom_hint=quote_line.rfq_line.uom_hint,
                quantity=quote_line.quantity,
                unit_price=quote_line.unit_price,
                tax_rate_pct=Decimal("8.00"),
                gl_account=account,
            )
        po.recalc_totals()

        # ---- 5. a goods receipt, three-way matched against a real accounting Bill --------
        po_lines = list(po.lines.all())
        grn = GoodsReceiptNote(
            tenant=tenant, purchase_order=po, receipt_date=today, status="draft",
            delivery_note_ref="DN-88231", received_by=admin,
            notes="Two cartons; one monitor short-shipped.",
        )
        grn.save()
        for i, line in enumerate(po_lines):
            # Short-ship the last line so the match lands on a real variance rather than a
            # uniformly perfect receipt — the interesting demo state.
            received = line.quantity if i < len(po_lines) - 1 else line.quantity - Decimal("1")
            GoodsReceiptLine.objects.create(
                goods_receipt=grn, po_line=line, quantity_received=received,
                quantity_rejected=Decimal("0"),
            )

        bill = self._bill_for(tenant, po, grn, currency, terms, account, today)
        grn.bill = bill
        # Deliberately set directly rather than through _post_grn_receipt, and this is the ONE
        # receipt in the app that is 'received' without matching StockMoves. Two reasons, both
        # structural: this 4.1 pass runs BEFORE _seed_inventory_tenant, so neither an item master
        # nor a stock location exists yet to post against; and these PO lines are 4.1 free text
        # whose sku_hints name procurement demo goods, not 4.3 catalogue items, so the resolver
        # would match nothing even if it ran. The demo three-way match — the point of this row —
        # depends only on quantities and value, not on the ledger. Any receipt booked through the
        # UI does post stock (goodsreceipt_receive → _post_grn_receipt).
        grn.status = "received"
        grn.save(update_fields=["bill", "status", "updated_at"])
        grn.recompute_match()
        po.recompute_receipt_status()

        self.stdout.write(
            f"{tenant.name}: seeded {req.number}/{pending.number}, {rfq.number} "
            f"({len(quotes)} quotes, awarded {winner.number}), {po.number}, "
            f"{grn.number} [{grn.get_match_status_display()}]."
        )

    def _bill_for(self, tenant, po, grn, currency, terms, account, today):
        """The vendor's AP bill for what was actually received — the third leg of the match.

        Reuses ``accounting.Bill`` (Module 2 owns the AP ledger, per lesson L29); we deliberately do
        not invent a parallel "VendorInvoice" table here.
        """
        bill = Bill(
            tenant=tenant, party=po.vendor, payment_terms=terms, bill_date=today,
            due_date=today + datetime.timedelta(days=30), status="pending_approval",
            currency=currency, notes=f"Against {po.number} / {grn.number}.",
        )
        bill.save()
        for line in grn.lines.select_related("po_line"):
            BillLine.objects.create(
                bill=bill, description=line.po_line.item_description,
                quantity=line.quantity_received, unit_price=line.po_line.unit_price,
                tax_rate_pct=Decimal("8.00"), gl_account=account,
            )
        bill.recalc_totals()
        return bill

    # ------------------------------------------------------------------ 4.11 Supply Chain Analytics
    def _seed_analytics_tenant(self, tenant):
        """4.11 demo rows: a spread of KPI targets, then REAL snapshots and REAL alerts.

        Two rules shape this method.

        **It hand-writes no measurement.** The targets are human intent, so those are typed here.
        Every number under them is produced by calling the same ``analytics.capture_snapshots`` and
        ``analytics.detect_alerts`` the Capture and Detect buttons call. A seeder that invented
        plausible-looking values would demo a page nobody can reproduce by pressing the button on
        it — and would hide exactly the bugs a seeded workspace exists to surface.

        **It refuses rather than half-seeds.** 4.11 measures 4.1-4.10, so with no stock ledger and
        no purchase history there is nothing to measure: it says so and returns, instead of leaving
        a workspace full of targets that all read "no data".
        """
        from apps.scm import analytics
        from apps.scm.models import KpiTarget, PurchaseOrder, StockMove, SupplyChainAlert

        if KpiTarget.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: analytics data already exists — skipping.")
            return

        # ---- prerequisites: warn and RETURN rather than half-seed (the 4.10 posture) -------------
        if not StockMove.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no stock ledger — skipping 4.11 analytics (it measures 4.1-4.10)."))
            return
        if not PurchaseOrder.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no purchase history — skipping 4.11 analytics."))
            return

        admin_user = (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                      or User.objects.filter(tenant=tenant).first())

        # ---- 1. the targets — spread across all five bullets so every page has a banded tile -----
        # Each carries the parameter its own metric declares (dead stock needs a window, carrying
        # cost needs a rate, the spike band needs a deviation %), because KpiTarget.clean() rejects
        # a target missing the parameter its metric requires — these rows go through full_clean()
        # below precisely so the seed proves that validation rather than side-stepping it.
        specs = [
            # metric, name, direction, target, warning, critical, days, pct, alerting, severity, pinned
            ("inv_turnover", "Inventory turnover", "higher_is_better",
             Decimal("6.00"), Decimal("4.00"), Decimal("2.00"), None, None, True, "warning", True),
            ("inv_dead_stock_value", "Dead stock exposure", "lower_is_better",
             Decimal("2000.00"), Decimal("5000.00"), Decimal("10000.00"), 90, None,
             True, "warning", True),
            ("inv_carrying_cost", "Cost of holding stock", "lower_is_better",
             Decimal("1500.00"), Decimal("3000.00"), Decimal("6000.00"), None, Decimal("25.00"),
             False, "info", False),
            ("spend_off_contract_pct", "Off-contract spend", "lower_is_better",
             Decimal("10.00"), Decimal("25.00"), Decimal("40.00"), None, None,
             True, "critical", True),
            ("supplier_otd_pct", "Supplier on-time delivery", "higher_is_better",
             Decimal("95.00"), Decimal("90.00"), Decimal("80.00"), None, None,
             True, "warning", True),
            ("otd_pct", "Customer on-time delivery", "higher_is_better",
             Decimal("97.00"), Decimal("92.00"), Decimal("85.00"), None, None,
             True, "critical", True),
            ("freight_cost_per_unit", "Freight cost per unit", "lower_is_better",
             Decimal("2.50"), Decimal("4.00"), Decimal("6.00"), None, None, False, "info", False),
            ("gross_margin_pct", "Gross margin", "higher_is_better",
             Decimal("35.00"), Decimal("25.00"), Decimal("15.00"), None, None,
             True, "warning", True),
            ("supplier_disruption_score", "Supplier disruption risk", "lower_is_better",
             Decimal("25.00"), Decimal("50.00"), Decimal("70.00"), 60, None,
             True, "critical", True),
            ("demand_spike_count", "Demand spikes", "lower_is_better",
             Decimal("0"), Decimal("2"), Decimal("5"), None, Decimal("50.00"),
             True, "warning", False),
        ]
        created = []
        for order, spec in enumerate(specs, start=1):
            (metric, name, direction, target, warn, crit, days, pct,
             alerting, severity, pinned) = spec
            kpi = KpiTarget(
                tenant=tenant, metric=metric, name=name, scope="all",
                period_grain="month", date_range="last_90", direction=direction,
                target_value=target, warning_threshold=warn, critical_threshold=crit,
                parameter_days=days, parameter_pct=pct,
                is_alerting=alerting, severity=severity,
                # A floor of zero on the demo rows: the point of a seeded workspace is that the
                # queue is populated enough to look at. Tuning min_impact_value UP is the first
                # thing a real operator does, and the field is on the form for exactly that.
                min_impact_value=Decimal("0"),
                owner=admin_user, is_pinned=pinned, display_order=order, is_active=True,
            )
            kpi.full_clean(exclude=["number"])  # the seeded rows satisfy the REAL validation
            kpi.save()
            created.append(kpi)

        # ---- 2. the frozen history — through the REAL service, three periods back ----------------
        # Three months rather than one, so every trend line has something to draw and the "captured,
        # never re-derived" claim is visible rather than merely asserted. capture_snapshots is
        # idempotent on (tenant, target, period_start, dimension_key), so a second seeder run
        # updates these points instead of stacking duplicates.
        # period_windows(), not `today - timedelta(days=30 * n)`. Thirty-day steps are not month
        # arithmetic: from 31 July they land on 1 June / 1 July / 31 July — June and July, with the
        # third capture merely updating the second — and from 1 March they skip February entirely.
        # period_windows returns the real month buckets, which is also exactly what
        # capture_snapshots derives internally, so the seeded points line up with the trend the
        # pages draw.
        points = 0
        for _start, stop in analytics.period_windows("month", 3):
            captured = analytics.capture_snapshots(tenant, created, period_end=stop,
                                                   user=admin_user) or {}
            points += captured.get("created", 0) + captured.get("updated", 0)

        # ---- 3. the exception queue — also through the REAL detector -----------------------------
        summary = analytics.detect_alerts(tenant, user=admin_user) or {}

        # ---- 4. some human state, so the lifecycle is visible on a fresh seed --------------------
        # Without this every alert reads "open" and the acknowledge/assign/resolve UI has nothing to
        # show. Driven through the MODEL METHODS rather than by writing the columns, so a seeded row
        # is indistinguishable from one a person clicked through.
        open_alerts = list(SupplyChainAlert.objects.filter(tenant=tenant, status="open")
                           .order_by("-impact_value")[:3])
        if admin_user:
            if len(open_alerts) >= 1:
                open_alerts[0].acknowledge(admin_user)
            if len(open_alerts) >= 2:
                open_alerts[1].acknowledge(admin_user)
                open_alerts[1].assign(admin_user)
            if len(open_alerts) >= 3:
                open_alerts[2].resolve(admin_user,
                                       "Confirmed with the supplier; shipment re-booked.")

        # `points` is snapshots actually written, not loop turns — a counter that increments once
        # per iteration reports "3 periods" even when two collided or every target was skipped.
        # `below_impact`, not `skipped`: in detect_alerts, `skipped` counts targets whose metric
        # RAISED, and reporting those as "below the floor" hides a broken metric as a tuning choice.
        self.stdout.write(
            f"{tenant.name}: 4.11 analytics — {len(created)} KPI targets, {points} snapshots "
            f"captured, {summary.get('created', 0)} alerts raised, "
            f"{summary.get('updated', 0)} re-fired, "
            f"{summary.get('below_impact', 0)} below the impact floor, "
            f"{summary.get('skipped', 0)} metric errors.")

    # ------------------------------------------------------------ 4.12 Contract & Compliance Mgmt
    def _seed_compliance_tenant(self, tenant):
        """4.12 demo rows: the licence register, the paperwork issued under it, the standing-
        obligation register with its proof history, two ESG scorecards — plus the two columns 4.12
        added to 4.2's ``SupplierContract`` (a named ``owner``, and one real amendment hanging off
        the master agreement through ``parent_contract``).

        Idempotent via a ``ComplianceRequirement`` guard. Runs LAST: obligations point at 4.2's
        contracts, trade documents at 4.6's shipments and carriers, and the carbon report multiplies
        4.6's ``Load.distance_km`` by ``Shipment.weight_kg`` — so every one of those must already
        exist. It REFUSES rather than half-seeds when they do not (the 4.10/4.11 posture).

        **Nothing here hand-sets a workflow status.** ``TradeLicense.status`` and
        ``TradeDocument.status`` are ``editable=False``, so they are moved along exactly the path the
        verb routes take: draft -> applied -> active, and then ``refresh_status()`` lets the dates
        have the last word (which is why one of the two licences comes out amber rather than green);
        a document reaches ``issued`` only after ``can_charge()`` says yes, with ``recompute_usage()``
        re-deriving the balance afterwards rather than a ``+=``. A requirement's standing is moved
        only by ``record_check()``. So ``used_value``, ``used_quantity``, ``overall_score`` and
        ``rating`` on the seeded rows are what the app itself derived — a human can reproduce every
        one of them by pressing the button on the page, which is the whole point of a seeded
        workspace.

        Every row goes through ``full_clean()``, so the seed PROVES the scope / date-ladder /
        cross-tenant validation instead of side-stepping it (the 4.11 seeder posture). ``number`` is
        the one exclusion: ``TenantNumbered.save()`` mints it and it is blank until then.

        4.12 is read-only over 4.1-4.11 — no ``StockMove``, no ``JournalEntry`` (L29).
        """
        from django.db.models import Sum
        from apps.scm.models import (
            ComplianceCheck, ComplianceRequirement, Item, Location, Shipment, SupplierContract,
            SustainabilityAssessment, TradeDocument, TradeDocumentLine, TradeLicense,
        )
        from apps.scm.models._base import q2, q4

        if ComplianceRequirement.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: compliance data already exists — skipping.")
            return

        # ---- prerequisites: warn and RETURN rather than half-seed (the 4.10/4.11 posture) --------
        contract = (SupplierContract.objects.filter(tenant=tenant)
                    .select_related("party").order_by("id").first())
        shipment = (Shipment.objects.filter(tenant=tenant, direction="outbound")
                    .select_related("carrier", "load", "sales_order").order_by("id").first())
        if contract is None or shipment is None:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no 4.2 supplier contract or no 4.6 outbound shipment — skipping "
                "4.12 compliance (its obligations hang off contracts and its paperwork off "
                "shipments)."))
            return

        admin = self._admin(tenant)
        today = timezone.localdate()
        usd = Currency.objects.filter(code="USD").first()
        org_unit = self._org_unit(tenant)
        northwind = self._supplier(tenant, *SUPPLIERS[0])
        cascade = self._supplier(tenant, *SUPPLIERS[1])
        buyer = self._customer(tenant, "Fabrikam Retail Group", "organization")
        ws16 = Item.objects.filter(tenant=tenant, sku="WS-16").first()
        mon27 = Item.objects.filter(tenant=tenant, sku="MON-27").first()
        dock = Item.objects.filter(tenant=tenant, sku="DOCK-C").first()
        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()

        # ---- 1. the 4.2 additions: a named owner, and a real amendment hierarchy -----------------
        # `owner` is back-filled onto the contracts 4.2 already seeded — that is the column's whole
        # point (renewals and 4.12 obligations route to a named person, not to whoever last edited).
        # The amendment is a NEW row rather than a re-pointing of 4.2's second contract, because
        # those two are with DIFFERENT suppliers: making one the master of the other would render an
        # ancestry line on the detail page that is simply untrue. An amendment amends its own master
        # and is signed with the same party.
        owned = list(SupplierContract.objects.filter(tenant=tenant))
        if admin is not None and owned:
            for row in owned:
                row.owner = admin
            SupplierContract.objects.bulk_update(owned, ["owner"])

        amendment_title = f"{contract.title} — amendment 1 (2026 price schedule)"
        amendment = SupplierContract.objects.filter(tenant=tenant, title=amendment_title).first()
        if amendment is None:
            amendment = SupplierContract(
                tenant=tenant, party=contract.party, title=amendment_title,
                parent_contract=contract, owner=admin, contract_type="purchase", status="active",
                start_date=today - datetime.timedelta(days=30), end_date=contract.end_date,
                contract_value=Decimal("12000.00"), currency=usd,
                payment_terms=contract.payment_terms, auto_renew=False, renewal_notice_days=30,
                terms_summary="Amends the price schedule of the master agreement for calendar 2026. "
                              "All other terms unchanged.",
                notes="Seeded 4.12 amendment — it hangs off the master through parent_contract, so "
                      "the contract page has a real ancestry to walk.")
            amendment.full_clean(exclude=["number"])
            amendment.save()
            amendment.refresh_status()

        # ---- 2. two licences, driven through the REAL submit -> approve path ---------------------
        def _license(license_number, **fields):
            """Existence-checked on (tenant, license_number) — never a bare create on a unique_together."""
            existing = TradeLicense.objects.filter(
                tenant=tenant, license_number=license_number).first()
            if existing is not None:
                return existing
            obj = TradeLicense(tenant=tenant, license_number=license_number, **fields)
            obj.full_clean(exclude=["number"])
            obj.save()
            return obj

        def _grant(licence, issue_date):
            """``tradelicense_submit`` followed by ``tradelicense_approve``, in effect verbatim.

            ``status`` is ``editable=False``, so this is the only honest way to land a licence in
            force: lodge the application, record the grant with a real approver stamp, then let
            ``refresh_status()`` correct ``active`` to ``expiring`` / ``expired`` from the dates —
            exactly what the approve verb does, and why the permit below comes out amber.
            """
            licence.status = "applied"
            licence.save(update_fields=["status", "updated_at"])
            licence.status = "active"
            licence.issue_date = issue_date
            licence.approved_at = timezone.now()
            licence.approved_by = admin
            licence.save(update_fields=["status", "issue_date", "approved_at", "approved_by",
                                        "updated_at"])
            licence.refresh_status()

        export_lic = _license(
            "BIS-2026-114872",
            title="Export licence — workstation hardware, US to Canada",
            license_type="export_license",
            issuing_authority="US Bureau of Industry and Security (BIS)",
            issuing_country="United States", end_user_party=buyer,
            application_date=today - datetime.timedelta(days=120),
            expiry_date=today + datetime.timedelta(days=300), renewal_notice_days=60,
            authorized_value=Decimal("250000.00"), authorized_quantity=Decimal("500"),
            currency=usd,
            commodity_scope="Laptop workstations, 27-inch monitors and USB-C docking stations.",
            eccn_or_hs="EAR99 / HS 8471.30", destination_countries="Canada, Mexico",
            conditions="Annual end-use statement due to BIS. No re-export without prior written "
                       "approval.",
            notes="Seeded 4.12 licence — in force, capped in BOTH dimensions, and drawn down by a "
                  "genuinely issued document so its balance is reproducible.")
        _grant(export_lic, today - datetime.timedelta(days=110))

        permit_lic = _license(
            "CBP-IMP-2025-0043",
            title="Import permit — lithium cells packed with equipment",
            license_type="import_permit",
            issuing_authority="US Customs and Border Protection", issuing_country="United States",
            application_date=today - datetime.timedelta(days=400),
            expiry_date=today + datetime.timedelta(days=21), renewal_notice_days=60,
            authorized_quantity=Decimal("10000"), currency=usd,
            commodity_scope="Lithium-ion cells packed with equipment (UN3481).",
            eccn_or_hs="HS 8507.60", destination_countries="United States",
            conditions="Hazmat training records retained for two years and produced on request.",
            notes="Seeded 4.12 licence — deliberately inside its 60-day renewal window, so the "
                  "amber Expiring chip and the renewal queue are populated on first login.")
        # Issued 10 days after it was applied for and 21 days before it lapses — the ladder
        # clean() enforces (application <= issue <= expiry) holds on the seeded row too.
        _grant(permit_lic, today - datetime.timedelta(days=390))

        # ---- 3. the paperwork: one issued invoice that charges a licence, one draft declaration --
        invoice = TradeDocument(
            tenant=tenant, doc_type="commercial_invoice", direction="export",
            document_number="INV-EXP-4471", issue_date=today - datetime.timedelta(days=2),
            shipment=shipment, carrier=shipment.carrier, sales_order=shipment.sales_order,
            license=export_lic, consignee_party=buyer, country_of_origin="United States",
            country_of_destination="Canada", currency=usd,
            # Set to the sum of the two lines below so `declared_value_matches` reads green: a
            # divergence is a customs problem, and a demo should not open with a false one.
            declared_value=Decimal("12485.00"), freight_charges=Decimal("2072.00"),
            insurance_value=Decimal("13000.00"), incoterm="DAP",
            gross_weight_kg=Decimal("9200.00"), net_weight_kg=Decimal("8750.00"),
            package_count=48, vessel_or_flight="TRK-4471", port_of_loading="Chicago, IL",
            port_of_discharge="Dallas, TX", container_numbers="TRLU-8890321",
            filing_reference="AES ITN X20260214000871",
            notes="Seeded 4.12 commercial invoice — issued through can_charge(), so the licence "
                  "balance it consumed was derived rather than typed.")
        invoice.full_clean(exclude=["number"])
        invoice.save()
        # The snapshot block is typed here rather than copied off `item` in code, because that is
        # precisely what the model refuses to do for itself: a filed line records what was DECLARED,
        # and re-classifying an item next year must not rewrite a document already submitted.
        for item, description, hs, qty, unit in (
            (ws16, "Laptop workstation, 16GB RAM", "8471.30", Decimal("5"), Decimal("1450.00")),
            (mon27, "Monitor, 27-inch LCD", "8528.52", Decimal("15"), Decimal("349.00")),
        ):
            line = TradeDocumentLine(
                document=invoice, item=item, description=description, hs_code=hs,
                country_of_origin="United States", uom_text="each",
                uom=item.uom if item is not None else None, quantity=qty, unit_value=unit)
            line.full_clean()
            line.save()

        # The issue verb, in effect verbatim: the SAME two grains `_charge_figures()` sums (value off
        # the document, quantity off the lines — one aggregate each, because asking for both at once
        # fans the document row out per line), REFUSED rather than clamped if the headroom is short,
        # and the counters re-derived afterwards instead of incremented.
        charge_value = q2(invoice.declared_value)
        charge_qty = q4(invoice.lines.aggregate(total=Sum("quantity"))["total"])
        allowed, refusal = export_lic.can_charge(charge_value, charge_qty)
        if allowed:
            invoice.status = "issued"
            invoice.issued_at = timezone.now()
            invoice.issued_by = admin
            invoice.save(update_fields=["status", "issued_at", "issued_by", "updated_at"])
            export_lic.recompute_usage()
        else:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: {invoice.number} left in draft — {refusal}"))

        inbound = (Shipment.objects.filter(tenant=tenant, direction="inbound")
                   .select_related("carrier", "purchase_order").order_by("id").first())
        customs = TradeDocument(
            tenant=tenant, doc_type="customs_declaration", direction="import",
            document_number="ENT-2026-00918", issue_date=today,
            shipment=inbound, carrier=getattr(inbound, "carrier", None),
            purchase_order=getattr(inbound, "purchase_order", None), license=permit_lic,
            shipper_party=northwind, country_of_origin="China",
            country_of_destination="United States", currency=usd,
            declared_value=Decimal("3480.00"), incoterm="FOB",
            gross_weight_kg=Decimal("3100.00"), net_weight_kg=Decimal("2960.00"),
            package_count=12,
            notes="Seeded 4.12 import declaration — left in DRAFT on purpose. Only issued / "
                  "submitted / accepted documents are in CHARGING_STATUSES, so its permit still "
                  "reads unconsumed and the Issue button has something real to do.")
        customs.full_clean(exclude=["number"])
        customs.save()
        for item, description, hs, qty, unit in (
            (dock, "USB-C docking station", "8517.62", Decimal("8"), Decimal("150.00")),
            (mon27, "Monitor, 27-inch LCD", "8528.52", Decimal("8"), Decimal("285.00")),
        ):
            line = TradeDocumentLine(
                document=customs, item=item, description=description, hs_code=hs,
                country_of_origin="China", uom_text="each",
                uom=item.uom if item is not None else None, quantity=qty, unit_value=unit)
            line.full_clean()
            line.save()

        # ---- 4. the standing-obligation register ------------------------------------------------
        def _scoped(field, subject):
            """Scope kwargs for one typed pointer, degrading to workspace-wide when 4.3 left the
            subject absent. ``clean()`` rule (a) refuses a scope whose pointer is empty, so a
            missing item has to change the SCOPE — dropping the FK alone would not validate."""
            if subject is None:
                return {"scope": "tenant"}
            return {"scope": field, field: subject}

        def _requirement(**fields):
            obj = ComplianceRequirement(tenant=tenant, owner=admin, **fields)
            obj.full_clean(exclude=["number"])
            obj.save()
            return obj

        coi = _requirement(
            title="Certificate of insurance on file and current",
            description="The supplier's general liability and cargo cover must be evidenced "
                        "annually, naming us as additional insured.",
            source="contract", contract=contract, source_reference=f"{contract.number}, clause 11.2",
            framework="insurance_coi", obligation_category="insurance",
            jurisdiction="United States", frequency="annual",
            # The cycle the two checks below answer. record_check() advances from HERE rather than
            # from the day the proof happened, so a late proof does not drag the schedule with it.
            next_due_date=today - datetime.timedelta(days=40), notice_days=45,
            criticality="high", **_scoped("party", contract.party))

        hazmat = _requirement(
            title="Lithium-cell shipments classified and packed to UN3481",
            description="Every consignment containing cells must carry the correct UN number, "
                        "packing instruction and marks under DOT / IATA / IMDG.",
            source="regulation", source_reference="49 CFR 173.185; IATA DGR PI966",
            framework="hazmat_dot_iata_imdg", obligation_category="regulatory",
            jurisdiction="United States", frequency="quarterly",
            next_due_date=today - datetime.timedelta(days=12), notice_days=30,
            criticality="critical", **_scoped("item", ws16))
        # The clock, not a typed status: applicable -> overdue purely from the date, through the
        # same refresh_status() the list page rolls a whole page with.
        hazmat.refresh_status()

        proviso = _requirement(
            title="Hazmat training records retained under the import permit",
            description="A proviso of the import permit: training records for everyone handling "
                        "the cells are retained and produced to CBP on request.",
            source="license", license=permit_lic,
            source_reference=f"{permit_lic.license_number}, condition 4",
            framework="customs_export_control", obligation_category="regulatory",
            jurisdiction="United States", frequency="semi_annual",
            # Inside the 30-day notice window — this is what the amber "due soon" chip counts.
            next_due_date=today + datetime.timedelta(days=15), notice_days=30,
            criticality="high", scope="tenant")

        uflpa = _requirement(
            title="Forced-labour due diligence across the components supply chain",
            description="Customer terms require an annual UFLPA attestation covering the sub-tier "
                        "supply chain for this supplier's components.",
            source="customer_requirement", source_reference="Fabrikam MSA, schedule 4",
            framework="forced_labor_uflpa", obligation_category="regulatory",
            jurisdiction="United States", frequency="annual",
            next_due_date=today + datetime.timedelta(days=200), notice_days=60,
            criticality="critical", **_scoped("party", cascade))

        iso14001 = _requirement(
            title="ISO 14001 surveillance audit of the main warehouse",
            description="The certification body's surveillance visit for the environmental "
                        "management system covering this site.",
            source="certification", source_reference="ISO 14001:2015, cert. EMS-2024-8812",
            framework="iso_14001", jurisdiction="United States", frequency="biennial",
            next_due_date=today + datetime.timedelta(days=120), notice_days=60,
            criticality="medium", **_scoped("location", main))

        gdpr = _requirement(
            title="GDPR processor terms for EU shipment data",
            description="Whether the EU data-processing addendum binds this department.",
            source="internal_policy", source_reference="Data policy DP-07",
            framework="data_privacy_gdpr", obligation_category="data", jurisdiction="EU",
            frequency="one_time", notice_days=30, criticality="low", status="not_applicable",
            # A non-applicable row is KEPT for its reason: "we looked and it does not bind us" is
            # itself an auditable answer, and clean() refuses the assertion without one.
            not_applicable_reason="This department ships domestically only and holds no EU personal "
                                  "data; reviewed and closed out for the 2026 cycle.",
            **_scoped("org_unit", org_unit))
        requirements = [coi, hazmat, proviso, uflpa, iso14001, gdpr]

        # ---- 5. the proof history — every status below is WRITTEN BY record_check(), never typed -
        def _check(requirement, **fields):
            check = ComplianceCheck(requirement=requirement, performed_by=admin, **fields)
            check.full_clean()
            check.save()
            requirement.record_check(check)
            return check

        checks = [
            # A partial first (-> in_progress), then the pass that closes the SAME cycle
            # (-> compliant, stamps last_checked_on, advances next_due_date a year from the cycle
            # date). Two checks over one requirement is also what gives compliance_rate a value
            # other than a bare 0 or 100 to render.
            _check(coi, result="partial",
                   due_date=today - datetime.timedelta(days=40),
                   performed_on=today - datetime.timedelta(days=45),
                   finding="Cargo cover evidenced; the general liability certificate was still "
                           "with the broker.",
                   notes="Seeded: chased the missing certificate."),
            _check(coi, result="pass",
                   due_date=today - datetime.timedelta(days=40),
                   performed_on=today - datetime.timedelta(days=35),
                   finding="Both certificates received, in date, and naming us as additional "
                           "insured.",
                   notes="Seeded: the cycle closed."),
            # A fail flips its parent to non_compliant and deliberately leaves the due date alone —
            # the cycle was not satisfied, so it is still owed.
            _check(uflpa, result="fail",
                   due_date=today + datetime.timedelta(days=200),
                   performed_on=today - datetime.timedelta(days=6),
                   finding="Two sub-tier smelters could not be evidenced against the CMRT.",
                   corrective_reference="NCR-00002 / CAPA-00001",
                   notes="Seeded: escalated to 4.9 by reference — 4.12 does not refactor a shipped "
                         "sub-module for a convenience FK."),
        ]

        # ---- 6. two ESG scorecards — the medal is DERIVED by recompute_rating(), never set -------
        # (party, source, provider, status, four themes, carbon, six declaration flags, scopes 1/2/3,
        #  days ago, validity days, note)
        esg_specs = [
            (northwind, "third_party_rating", "EcoVadis", "validated",
             (72, 68, 75, 61), 58, (True, True, True, True, False, True),
             (Decimal("1240.500"), Decimal("3180.250"), Decimal("18640.000")), 60, 305,
             "Seeded: a full four-theme scorecard — the mean of 72/68/75/61 lands on gold."),
            (cascade, "self_assessment", "", "submitted",
             (41, 52, None, None), 33, (False, True, True, False, False, True),
             (Decimal("410.000"), Decimal("905.750"), None), 20, 345,
             "Seeded: a PARTIAL scorecard — two themes were never asked, so the mean is taken over "
             "the two that were. An unanswered theme is not a zero."),
        ]
        esg_rows = []
        for (party, source, provider, status, themes, carbon, flags, scopes, days_ago,
             valid_days, note) in esg_specs:
            esg = SustainabilityAssessment(
                tenant=tenant, party=party,
                assessment_date=today - datetime.timedelta(days=days_ago),
                valid_until=today + datetime.timedelta(days=valid_days),
                source=source, provider=provider, status=status,
                environment_score=themes[0], labor_human_rights_score=themes[1],
                ethics_score=themes[2], sustainable_procurement_score=themes[3],
                carbon_score=carbon,
                strengths="ISO 14001 certified sites; a published living-wage commitment.",
                improvement_areas="Publish a Scope 3 reduction target and extend the code of "
                                  "conduct to sub-tier suppliers.",
                conflict_minerals_declared=flags[0], reach_declared=flags[1],
                rohs_declared=flags[2], forced_labor_attested=flags[3],
                deforestation_declared=flags[4], code_of_conduct_signed=flags[5],
                scope1_tco2e=scopes[0], scope2_tco2e=scopes[1], scope3_tco2e=scopes[2],
                carbon_reporting_year=today.year - 1, assessed_by=admin, notes=note)
            esg.full_clean(exclude=["number"])
            # save() always calls recompute_rating() — the ONLY writer of overall_score / rating, on
            # every path including this one.
            esg.save()
            esg_rows.append(esg)

        utilization = export_lic.utilization_pct
        self.stdout.write(
            f"{tenant.name}: 4.12 compliance — licences {export_lic.number} "
            f"[{export_lic.get_status_display()}, {utilization if utilization is not None else '—'}% "
            f"of value used] / {permit_lic.number} [{permit_lic.get_status_display()}], documents "
            f"{invoice.number} [{invoice.get_status_display()}] / {customs.number} "
            f"[{customs.get_status_display()}], {len(requirements)} requirements "
            f"({len(checks)} checks recorded, {coi.number} now "
            f"{coi.get_status_display().lower()} at {coi.compliance_rate}%, {hazmat.number} "
            f"{hazmat.get_status_display().lower()}), {len(esg_rows)} ESG assessments "
            f"({', '.join(e.get_rating_display().lower() for e in esg_rows)}), contract owner set "
            f"on {len(owned)} 4.2 contract(s) + amendment {amendment.number}.")

    # --------------------------------------------------------------------- 4.13 Asset Management
    def _seed_asset_tenant(self, tenant):
        """4.13 demo rows: the asset register (with a real parent/child hierarchy), the machines'
        spare-parts lists, three maintenance plans on three DIFFERENT triggers, a rising meter
        history, and three jobs sitting at three different points of the lifecycle.

        Idempotent via an ``Asset`` guard. Runs LAST, and its dependencies are load-bearing rather
        than cosmetic: the assets sit at 4.3's locations, the conveyor serves one of 4.8's work
        centres, the parts lists point at 4.3 items this pass flips to ``is_spare_part``, and the
        completed PM job DRAWS those parts out of 4.3's storeroom. It REFUSES rather than half-seeds
        when 4.3 is absent (the 4.10/4.11/4.12 posture) — an asset register with no location and no
        parts to issue would demo three pages that all read "no data".

        **The one ledger write in the whole sub-module, and it goes through the real service.**
        ``_post_stock_move(..., move_type="maintenance")`` — the same call
        ``maintenanceworkorder_issue_parts`` makes, preceded by the same ``_insufficient_stock``
        check and the same ``_shared_items`` sharing, with ``unit_cost`` stamped from
        ``item.average_cost`` AT ISSUE TIME. So the seeded job's cost is what the app itself would
        have written and on-hand stays a pure aggregate of one append-only ledger. It posts **no
        ``JournalEntry``** — the standing 4.9-4.12 rule (L29).

        **Nothing here hand-sets a workflow status or a system stamp.** ``MaintenanceWorkOrder.status``
        is ``editable=False`` (L22), so the completed job is walked down the SAME ladder the verbs
        take — requested -> approved -> scheduled -> in_progress -> completed — with each verb's own
        stamps written at that step and the parts issued while the job is still open, exactly as
        ``ISSUABLE_STATUSES`` requires. The plan's schedule is rolled by
        :meth:`MaintenancePlan.advance` (once at generate, once at completion), never by date maths
        written here; ``downtime_minutes`` is derived by ``save()`` from the window; and
        ``AssetSparePart.quantity_per_service`` goes through the model's own ``q4``. Every row is
        checked with ``full_clean()``, so the seed PROVES the trigger contract, the plan/asset
        agreement and the cross-tenant guards instead of side-stepping them (the 4.11/4.12 posture).
        ``number`` is the one exclusion — ``TenantNumbered.save()`` mints it and it is blank until
        then.

        **Deliberately mixed demo state**, because a uniform register exercises nothing: one asset is
        down RIGHT NOW on an open breakdown (so ``is_down_now()`` is true and ``mttr_hours()`` hits
        its zero-denominator guard and answers ``None`` rather than a flattering 0 h); two of the four
        assets are linked to an ``accounting.FixedAsset`` and two are not, so the depreciation
        report's coverage figure is genuinely measured rather than faked; and the three plans come out
        scheduled / meter-overdue / condition-overdue so all three trigger arithmetics are visibly
        working on the first login.
        """
        from apps.accounting.models import FixedAsset
        from apps.scm.models import (Asset, AssetSparePart, Item, Location, MaintenancePlan,
                                     MaintenancePlanTask, MaintenanceWorkOrder,
                                     MaintenanceWorkOrderPart, MaintenanceWorkOrderTask,
                                     MeterReading, StockMove, WorkCenter)
        from apps.scm.models._base import ZERO, q4
        from apps.scm.views._helpers import (_insufficient_stock, _post_stock_move, _shared_items)

        if Asset.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: asset management data already exists — skipping.")
            return

        # ---- prerequisites: warn and RETURN rather than half-seed (the 4.10/4.11/4.12 posture) ---
        main = Location.objects.filter(tenant=tenant, code="WH-MAIN").first()
        dock = Item.objects.filter(tenant=tenant, sku="DOCK-C").first()
        mon27 = Item.objects.filter(tenant=tenant, sku="MON-27").first()
        if main is None or dock is None or mon27 is None:
            self.stdout.write(self.style.WARNING(
                f"{tenant.name}: no 4.3 items/locations — skipping 4.13 asset management (its assets "
                "sit at 4.3 locations and its jobs draw spare parts out of the 4.3 stock ledger)."))
            return

        now = timezone.now()
        today = timezone.localdate()
        admin = self._admin(tenant)
        org_unit = self._org_unit(tenant)
        custodian = self._employee(tenant, "Liam Johnson")
        technician = self._employee(tenant, "Emma Williams")
        reporter = self._employee(tenant, "Sophia Miller")
        northwind = self._supplier(tenant, *SUPPLIERS[0])
        cascade = self._supplier(tenant, *SUPPLIERS[1])
        # 4.8's assembly centre. None when manufacturing was skipped for this tenant — the link is
        # SET_NULL and the whole point of it is that it is optional, so a missing centre degrades the
        # conveyor to "not tied to production" rather than aborting the pass.
        assembly = WorkCenter.objects.filter(tenant=tenant, code="WC-ASM").first()

        def _at(day, hour, minute=0):
            """An aware datetime at a FIXED local time on ``day``.

            Deliberately not ``now - timedelta(days=n, hours=m)``: ``is_on_time`` compares the
            completion and the commitment by local DATE, so a seed run at 02:00 would push one of the
            two over a day boundary and the demo job would read late on some mornings and on time on
            others. Anchoring on the date makes it the same job whenever the seeder is run.
            """
            return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, minute)))

        # ---- 1. the register — existence-checked on (tenant, code), never a bare create ----------
        def _asset(code, **fields):
            existing = Asset.objects.filter(tenant=tenant, code=code).first()
            if existing is not None:
                return existing
            obj = Asset(tenant=tenant, code=code, **fields)
            obj.full_clean(exclude=["number"])
            obj.save()
            return obj

        # The two capitalised records 2.6 already seeded. Read, never created: 4.13 stores no
        # acquisition cost, no salvage value and no accumulated depreciation — the link exists so the
        # asset page can SHOW a book value the accounting row owns (the module docstring's rule), and
        # a second writer of one accumulated figure is exactly how two pages come to disagree.
        van = (FixedAsset.objects.filter(tenant=tenant, name="Delivery Van").first()
               or FixedAsset.objects.filter(tenant=tenant).order_by("id").first())
        racking = FixedAsset.objects.filter(tenant=tenant, name="Warehouse Racking").first()

        line = _asset(
            "LINE-01", name="Assembly Line 1", asset_type="machine", status="in_service",
            criticality="critical", category="Production lines",
            manufacturer="Vollmer Systemtechnik", model_number="VL-4400", serial_number="VS4400-11872",
            tag_code="QR-LINE-01",
            specifications="14 m modular line, 3-phase 400 V, rated 240 units/hour.",
            location=main, org_unit=org_unit, custodian=custodian, supplier=northwind,
            service_vendor=cascade,
            purchase_date=today - datetime.timedelta(days=930),
            commissioned_on=today - datetime.timedelta(days=900),
            # Deliberately lapsed, so the red Expired warranty chip is populated on first login — and
            # so is the case for reading it: this is the state in which somebody pays for a repair the
            # supplier used to owe them.
            warranty_expires_on=today - datetime.timedelta(days=60),
            purchase_cost=Decimal("185000.00"),
            notes="Seeded 4.13 parent asset — the child below hangs off it through `parent`, so the "
                  "hierarchy walk and the roll-ups have a real two-level tree to work on. "
                  "Deliberately NOT linked to a fixed asset: it is the coverage gap the depreciation "
                  "report is built to surface.")

        drive = _asset(
            "LINE-01-DRV", name="Line 1 drive motor & gearbox", asset_type="machine",
            status="in_service", criticality="high", category="Drives & motors",
            manufacturer="SEW-Eurodrive", model_number="K107-DRN132", serial_number="SEW-88-40219",
            tag_code="QR-LINE-01-DRV",
            specifications="7.5 kW geared motor, ratio 28.6:1, IP55.",
            parent=line, location=main, org_unit=org_unit, custodian=custodian, supplier=northwind,
            purchase_date=today - datetime.timedelta(days=930),
            commissioned_on=today - datetime.timedelta(days=900),
            purchase_cost=Decimal("12500.00"),
            notes="Seeded 4.13 CHILD component — a sub-assembly of LINE-01. No warranty date on "
                  "purpose: 'not recorded' is its own muted chip and must never read green.")

        forklift = _asset(
            "FL-002", name="Counterbalance forklift 2.5 t", asset_type="forklift",
            status="in_service", criticality="medium", category="Fork trucks",
            manufacturer="Toyota Material Handling", model_number="8FGCU25",
            serial_number="8FGCU25-31447", tag_code="QR-FL-002",
            specifications="2 500 kg at 500 mm load centre, LPG, triplex mast 4.7 m.",
            location=main, org_unit=org_unit, custodian=custodian, supplier=cascade,
            service_vendor=cascade,
            # The meter DEFINITION only — every number lives in MeterReading, append-only.
            meter_name="Running Hours", meter_unit="h",
            purchase_date=today - datetime.timedelta(days=520),
            commissioned_on=today - datetime.timedelta(days=500),
            # Inside the 60-day notice window, so the amber warranty chip is populated too.
            warranty_expires_on=today + datetime.timedelta(days=45),
            purchase_cost=Decimal("48000.00"), fixed_asset=van,
            notes="Seeded 4.13 asset — LINKED to a capitalised record, so the depreciation report has "
                  "a real book value to divide maintenance spend by. Its meter is the one the "
                  "meter-based plan schedules against.")

        conveyor = _asset(
            "CNV-03", name="Pick-line belt conveyor", asset_type="conveyor", status="in_service",
            criticality="high", category="Conveyors",
            manufacturer="Interroll", model_number="RM8730", serial_number="IR-8730-5521",
            tag_code="QR-CNV-03",
            specifications="18 m belt, 0.6 m wide, 0.55 kW drum motor, variable 0.2-0.8 m/s.",
            location=main, org_unit=org_unit, custodian=custodian, supplier=northwind,
            # THE SCM DIFFERENTIATOR: taking this machine down is a CAPACITY fact, so it points at
            # 4.8's work centre and a repair can explain a hole in the load board.
            work_center=assembly,
            meter_name="Bearing Temp", meter_unit="°C",
            purchase_date=today - datetime.timedelta(days=320),
            commissioned_on=today - datetime.timedelta(days=300),
            warranty_expires_on=today + datetime.timedelta(days=300),
            purchase_cost=Decimal("18000.00"), fixed_asset=racking,
            notes="Seeded 4.13 asset — tied to a 4.8 work centre AND to a capitalised record. It "
                  "carries the completed PM job, so it is the row whose repair-vs-replace ratio is a "
                  "real quotient rather than a zero.")
        assets = [line, drive, forklift, conveyor]

        # ---- 2. 4.3 items become spares — a GUARDED update that is a no-op on the second run -----
        # `.update()` on a filter that already excludes the flipped rows: the first run writes 2, the
        # second matches nothing and writes 0. A blanket `.update(is_spare_part=True)` would report
        # two flips forever and touch rows it did not change; `save()` per item would be two round
        # trips to say the same thing. There is deliberately no SparePart table — scm.Item already
        # owns UoM, costing, average cost, reorder point and a derived on-hand, and a parallel parts
        # master would fork every one of them (the model docstring's rule).
        spare_skus = ["DOCK-C", "MON-27"]
        flipped = Item.objects.filter(
            tenant=tenant, sku__in=spare_skus, is_spare_part=False).update(is_spare_part=True)

        # ---- 3. the machines' parts lists — the ASSOCIATION, nothing more ------------------------
        parts_specs = [
            (conveyor, dock, Decimal("2"), True,
             "Consumed at every service. Running out stops the job, so it is flagged critical."),
            (conveyor, mon27, Decimal("1"), False, "Replaced on condition, not every service."),
            (forklift, dock, Decimal("1"), False, "Carried as a shelf spare for the mast harness."),
            (drive, mon27, Decimal("1"), True, "Long-lead item — the line stops without it."),
        ]
        spare_rows = 0
        for asset, item, qty, critical, note in parts_specs:
            if AssetSparePart.objects.filter(asset=asset, item=item).exists():
                continue
            row = AssetSparePart(asset=asset, item=item, quantity_per_service=qty,
                                 is_critical=critical, notes=note)
            row.full_clean()
            row.save()
            spare_rows += 1

        # ---- 4. the meter history — a REAL rising trend, so the arithmetic has something to do ---
        # Six observations on the forklift's primary meter and two on the conveyor's. Both are what
        # the schedule below actually reads: the meter plan compares its target against the newest
        # forklift row, and the condition plan compares its threshold against the newest conveyor row.
        # A single reading would let both look configured while proving nothing.
        def _reading(asset, meter_name, unit, value, days_ago, **fields):
            read_at = _at(today - datetime.timedelta(days=days_ago), 9)
            existing = MeterReading.objects.filter(
                tenant=tenant, asset=asset, meter_name=meter_name, read_at=read_at).first()
            if existing is not None:
                return existing
            obj = MeterReading(tenant=tenant, asset=asset, meter_name=meter_name, unit=unit,
                               reading=value, read_at=read_at, recorded_by=technician, **fields)
            obj.full_clean()
            obj.save()
            return obj

        readings = []
        for days_ago, hours in ((150, "968.0"), (120, "1012.5"), (90, "1058.0"),
                                (60, "1104.5"), (30, "1161.0"), (3, "1218.5")):
            readings.append(_reading(forklift, "Running Hours", "h", Decimal(hours), days_ago,
                                     source="manual", notes="Seeded: read off the hour counter."))
        for days_ago, temp in ((14, "68.4"), (2, "77.2")):
            readings.append(_reading(conveyor, "Bearing Temp", "°C", Decimal(temp), days_ago,
                                     source="manual",
                                     notes="Seeded: drive-end bearing, infrared spot check."))

        # ---- 5. three plans on three DIFFERENT triggers ------------------------------------------
        def _plan(name, asset, tasks, **fields):
            """Existence-checked on (tenant, asset, name) — never a bare create on an auto-numbered
            row (the 4.12 `_license` pattern). The checklist is written only for a plan this run
            actually created, so a re-run cannot stack a second copy of the same steps."""
            existing = MaintenancePlan.objects.filter(
                tenant=tenant, asset=asset, name=name).first()
            if existing is not None:
                return existing
            obj = MaintenancePlan(tenant=tenant, asset=asset, name=name, **fields)
            obj.full_clean(exclude=["number"])
            obj.save()
            for sequence, description, expected, mandatory, safety in tasks:
                task = MaintenancePlanTask(
                    plan=obj, sequence=sequence, description=description,
                    expected_result=expected, is_mandatory=mandatory, is_safety_step=safety)
                task.full_clean()
                task.save()
            return obj

        calendar_plan = _plan(
            "Monthly conveyor inspection & belt lubrication", conveyor,
            [(10, "Isolate the drive and apply lock-out/tag-out",
              "Isolation proved dead; personal tag fitted", True, True),
             (20, "Inspect the belt for tears, tracking and edge wear",
              "No tears; tracking within 5 mm of centre", True, False),
             (30, "Grease the drive and idler bearings",
              "Two shots per nipple, no purge past the seal", True, False),
             (40, "Test the emergency pull-cord along both runs",
              "Belt stops within 1 s from every station", True, False),
             (50, "Record the bearing temperature after 10 minutes running",
              "Below 70 °C", False, False)],
            trigger_type="calendar", schedule_basis="floating", interval_days=30, lead_time_days=7,
            # The cycle the completed job below answers. It is rolled TWICE by advance() — once at
            # generate, once at completion — so what ends up on the row is the schedule the app
            # itself produced, not a date typed here.
            next_due_on=today - datetime.timedelta(days=5),
            priority="high", work_type="preventive", estimated_hours=Decimal("3.50"),
            assigned_to=technician, parts_location=main,
            instructions="The standing monthly service on the pick line. Runs during the Friday "
                         "shutdown window; the line must be isolated before any guard is opened.")

        meter_plan = _plan(
            "250-hour forklift service", forklift,
            [(10, "Park, lower the forks, isolate and apply lock-out/tag-out",
              "Key removed, tag fitted", True, True),
             (20, "Change the engine oil and filter", "5.5 L 15W-40; filter torqued to spec",
              True, False),
             (30, "Check hydraulic level, hoses and mast chains",
              "No weeping; chain stretch under 2%", True, False),
             (40, "Test the service and parking brakes", "Holds loaded on a 15% grade", True, False)],
            trigger_type="meter", schedule_basis="floating", meter_interval=Decimal("250"),
            lead_time_days=5,
            # 1 200 h against a newest reading of 1 218.5 h — meter_gap() is NEGATIVE, so due_status
            # answers `overdue` off the USAGE axis with no date involved at all. That is the half of
            # the trigger a boolean `is_meter_based` would have had, and the half a calendar-only
            # demo never exercises.
            next_due_reading=Decimal("1200"),
            priority="medium", work_type="preventive", estimated_hours=Decimal("3.00"),
            assigned_to=technician, parts_location=main,
            instructions="The 250-hour interval service. Due on RUNNING HOURS, not on the calendar — "
                         "a truck that sat idle for a month does not owe a service.")

        condition_plan = _plan(
            "Conveyor drive bearing temperature watch", conveyor,
            [(10, "Read the drive-end bearing temperature with the infrared gun",
              "Below 75 °C at steady state", True, False),
             (20, "If the reading is above threshold, check alignment and lubrication before "
                  "running on", "Cause identified and cleared, or the belt is stopped", True, False)],
            trigger_type="condition", condition_operator="gte",
            condition_threshold=Decimal("75"), lead_time_days=7,
            priority="high", work_type="predictive", estimated_hours=Decimal("1.00"),
            assigned_to=technician, parts_location=main,
            instructions="A condition trigger, not a schedule: the machine decides when this is due. "
                         "The newest seeded reading is 77.2 °C against a 75 °C threshold, so it "
                         "fires on first login and the trigger is visibly working rather than merely "
                         "configured.")
        plans = [calendar_plan, meter_plan, condition_plan]

        # ---- 6. the jobs -------------------------------------------------------------------------
        def _job(title, asset, tasks=(), **fields):
            """Existence-checked on (tenant, asset, title) — the auto-numbered rule again."""
            existing = MaintenanceWorkOrder.objects.filter(
                tenant=tenant, asset=asset, title=title).first()
            if existing is not None:
                return existing
            obj = MaintenanceWorkOrder(tenant=tenant, asset=asset, title=title, **fields)
            obj.full_clean(exclude=["number"])
            obj.save()
            # Plain COLUMN copies of the plan's checklist, with no FK back to it — the generate
            # action's rule: editing a plan next month must not rewrite what a finished job asked a
            # technician to check and sign.
            for task in tasks:
                snapshot = MaintenanceWorkOrderTask(
                    work_order=obj, sequence=task.sequence, description=task.description,
                    expected_result=task.expected_result, is_mandatory=task.is_mandatory,
                    is_safety_step=task.is_safety_step)
                snapshot.full_clean()
                snapshot.save()
            return obj

        def _walk(job, status, **stamps):
            """One verb's effect: write the stamps that verb owns, move ``status``, one round trip.

            ``status`` is ``editable=False`` and the verbs are its only writer (L22), so the seeded
            job is walked down the same ladder rather than being dropped straight into ``completed``
            with a set of stamps that never happened. ``save()`` folds ``downtime_minutes`` into
            ``update_fields`` itself, so the derived total always rides along with its inputs.
            """
            for field, value in stamps.items():
                setattr(job, field, value)
            job.status = status
            job.save(update_fields=["status", *stamps, "updated_at"])

        # --- 6a. the completed PM: generated from the calendar plan, worked, and costed -----------
        pm_day = today - datetime.timedelta(days=5)
        generated_on = today - datetime.timedelta(days=8)
        scheduled_start = _at(calendar_plan.next_due_on, 7)   # captured BEFORE advance() moves it
        pm_job = _job(
            "Monthly conveyor inspection & belt lubrication", conveyor,
            tasks=list(calendar_plan.tasks.all()),
            plan=calendar_plan, source="plan", work_type=calendar_plan.work_type,
            priority=calendar_plan.priority, assigned_to=calendar_plan.assigned_to,
            parts_location=calendar_plan.parts_location,
            reported_at=_at(generated_on, 9), scheduled_start=scheduled_start,
            labour_rate=Decimal("42.0000"),
            description="Generated from the monthly plan. Full inspection and lubrication of the "
                        "pick-line conveyor during the Friday shutdown window.")
        if pm_job.status == "requested":
            # The generate action rolls the schedule ONCE, from the day the job was raised, and
            # stamps last_generated_on. advance() returns the field names it wrote and saves nothing
            # by default, so its write is folded into this caller's own update_fields — its stated
            # contract, and one UPDATE instead of two.
            rolled = calendar_plan.advance(from_date=generated_on)
            calendar_plan.last_generated_on = generated_on
            calendar_plan.save(update_fields=list(dict.fromkeys(
                rolled + ["last_generated_on", "updated_at"])))

            _walk(pm_job, "approved")
            _walk(pm_job, "scheduled")
            _walk(pm_job, "in_progress",
                  started_at=_at(pm_day, 8), downtime_start=_at(pm_day, 8))

        # The part lines the job consumed. Added while the job is open, which is the only state the
        # issue verb accepts — a line planned onto a closed job could never be drawn.
        for item, qty in ((dock, Decimal("1")), (mon27, Decimal("2"))):
            if not pm_job.parts.filter(item=item).exists():
                part = MaintenanceWorkOrderPart(work_order=pm_job, item=item, quantity=qty)
                part.full_clean()
                part.save()

        # --- 6b. THE ONLY LEDGER WRITE IN 4.13 ----------------------------------------------------
        # Guarded on (move_type, reference) rather than on the seeder's outer Asset check, because
        # this is the one write here with an effect outside 4.13: a second post would draw the same
        # parts out of stock twice and silently understate on-hand for every page that reads the
        # ledger. The filter is exactly the one _flush() deletes on, so the guard and the teardown
        # describe the same set of rows.
        issued_lines, issued_value = 0, ZERO
        if StockMove.objects.filter(tenant=tenant, move_type="maintenance",
                                    reference=pm_job.number).exists():
            self.stdout.write(f"{tenant.name}: {pm_job.number} parts already issued — not "
                              f"re-posting the maintenance stock moves.")
        else:
            # `maintenanceworkorder_issue_parts`, in effect verbatim: _shared_items so two lines for
            # one part read ONE Item instance rather than each rolling its own stale average cost;
            # _insufficient_stock BEFORE every move so a line the storeroom cannot cover is named and
            # skipped rather than failing the whole issue; unit_cost stamped from average_cost AT
            # ISSUE TIME, because the job's cost has to be what the stock actually cost when drawn.
            lines = list(pm_job.parts.filter(is_issued=False).select_related("item", "lot_serial"))
            shared = _shared_items(lines)
            stamp = _at(pm_day, 8, 20)
            for part in lines:
                item = shared[part.item_id]
                shortfall = _insufficient_stock(item, pm_job.parts_location, part.quantity,
                                                part.lot_serial)
                if shortfall:
                    self.stdout.write(self.style.WARNING(
                        f"{tenant.name}: {pm_job.number} — not issued: {shortfall}"))
                    continue
                cost = item.average_cost or ZERO
                _post_stock_move(tenant, item=item, location=pm_job.parts_location,
                                 quantity=-part.quantity, move_type="maintenance", unit_cost=cost,
                                 lot_serial=part.lot_serial, reference=pm_job.number,
                                 reason="Maintenance issue", moved_at=stamp)
                part.unit_cost = q4(cost)
                part.is_issued = True
                part.issued_at = stamp
                # No `updated_at`: MaintenanceWorkOrderPart is a plain child and has no timestamps.
                part.save(update_fields=["unit_cost", "is_issued", "issued_at"])
                issued_value += part.line_cost
                issued_lines += 1

        # --- 6c. completion, and the second schedule roll -----------------------------------------
        if pm_job.status == "in_progress":
            _walk(pm_job, "completed",
                  completed_at=_at(pm_day, 11, 30), downtime_end=_at(pm_day, 10),
                  labour_hours=Decimal("3.50"), remedy_code="lubricate",
                  resolution_notes="Belt tracking corrected by 3 mm at the tail pulley, all four "
                                   "bearings greased, pull-cords proved. Bearing temperature 61 °C "
                                   "after 10 minutes — within tolerance.")
            for task, result in zip(pm_job.tasks.all(), (
                    "Isolated at the local isolator, tag fitted by E. Williams.",
                    "Minor edge fray at 11 m, within limits. Tracking 3 mm off centre, corrected.",
                    "All four bearings greased, no purge past the seals.",
                    "All six stations stopped the belt inside 1 s.",
                    "61 °C after 10 minutes.")):
                task.is_done = True
                task.actual_result = result
                task.completed_at = _at(pm_day, 11, 30)
                task.save(update_fields=["is_done", "actual_result", "completed_at"])

            # The complete verb's plan roll: stamp last_completed_on and advance ONE cycle from the
            # completion date. Exactly one cycle even when several were missed, so a plan that is
            # behind stays visibly behind instead of being silently caught up.
            rolled = calendar_plan.advance(from_date=pm_day)
            calendar_plan.last_completed_on = pm_day
            calendar_plan.save(update_fields=list(dict.fromkeys(
                ["last_completed_on", "updated_at"] + rolled)))

        # --- 6d. the OPEN breakdown: the line is down right now -----------------------------------
        # downtime_start set with downtime_end still NULL is the whole point: Asset.is_down_now()
        # answers from these rows rather than from a status column something has to remember to flip,
        # Asset.downtime_minutes() adds the still-running window that the stored total cannot see,
        # and mttr_hours() finds no FINISHED breakdown and answers None — the zero-denominator guard
        # doing its job, where a confident 0 h would read as instant repairs.
        breakdown = _job(
            "Line 1 stopped — heavy vibration from the drive end", line,
            source="request", work_type="breakdown", priority="urgent",
            reported_by=reporter, assigned_to=technician, parts_location=main,
            reported_at=now - datetime.timedelta(hours=9),
            downtime_start=now - datetime.timedelta(hours=9), is_unplanned_downtime=True,
            problem_code="vibration", cause_code="misalignment",
            labour_rate=Decimal("42.0000"),
            description="Night shift reported heavy vibration and a rising noise from the drive end "
                        "before the line tripped. Coupling alignment suspect; remedy not yet "
                        "determined.")
        if breakdown.status == "requested":
            _walk(breakdown, "approved")
            _walk(breakdown, "in_progress", started_at=now - datetime.timedelta(hours=6))
        # One PLANNED, deliberately UNISSUED line, so the Issue Parts button on the detail page has
        # something real to do and the planned-vs-issued split is visible: an unissued line carries
        # unit_cost 0 and contributes nothing to the job's cost, because the cost is stamped by the
        # issue, not by the intention.
        if not breakdown.parts.filter(item=dock).exists():
            part = MaintenanceWorkOrderPart(work_order=breakdown, item=dock, quantity=Decimal("1"))
            part.full_clean()
            part.save()

        # --- 6e. the intake: a request nobody has approved yet ------------------------------------
        # status stays at its default `requested`, which IS the maintenance request — see the model
        # docstring for why there is no second request table to convert from.
        request_job = _job(
            "Hydraulic weep at the mast cylinder", forklift,
            source="request", work_type="corrective", priority="medium",
            reported_by=reporter, parts_location=main,
            reported_at=now - datetime.timedelta(days=1, hours=2),
            description="Driver reports a slow weep at the lift cylinder gland and a puddle under "
                        "the mast after standing overnight. Truck still usable; raised for "
                        "assessment.")

        jobs = [pm_job, breakdown, request_job]
        self.stdout.write(
            f"{tenant.name}: 4.13 asset management — {len(assets)} assets "
            f"({line.code} > {drive.code} hierarchy, {conveyor.code} on "
            f"{assembly.code if assembly else 'no work centre'}, "
            f"{sum(1 for a in assets if a.fixed_asset_id)} of {len(assets)} linked to a fixed "
            f"asset), {flipped} item(s) flipped to spare parts, {spare_rows} parts-list row(s), "
            f"{len(plans)} plans ({calendar_plan.number} {calendar_plan.due_status_label.lower()} "
            f"next {calendar_plan.next_due_on}, {meter_plan.number} "
            f"{meter_plan.due_status_label.lower()} at {meter_plan.next_due_reading} h, "
            f"{condition_plan.number} {condition_plan.due_status_label.lower()}), "
            f"{len(readings)} meter readings, {len(jobs)} work orders "
            f"({pm_job.number} {pm_job.get_status_display().lower()} costing {pm_job.total_cost}, "
            f"{breakdown.number} {breakdown.get_status_display().lower()} and down now, "
            f"{request_job.number} {request_job.get_status_display().lower()}), "
            f"{issued_lines} part line(s) worth {issued_value} issued through the ledger.")
