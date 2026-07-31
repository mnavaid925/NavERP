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
            "4.10 returns + 4.11 analytics demo data — idempotent (skips a tenant that already "
            "has the rows each pass creates).")

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

        self.stdout.write(self.style.SUCCESS(
            "SCM 4.1 procurement + 4.2 SRM + 4.3 inventory + 4.4 warehouse + 4.5 orders + "
            "4.6 transportation + 4.7 demand planning + 4.8 manufacturing + 4.9 quality + "
            "4.10 returns + 4.11 analytics seed complete."))
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

        # 4.11 Analytics FIRST (newest sub-module). Unlike every block below it, NOTHING here is
        # PROTECT — KpiSnapshot.kpi_target is CASCADE and all six of SupplyChainAlert's subject FKs
        # plus KpiTarget's four scope FKs are SET_NULL — so these rows could not block any deletion
        # further down. They still go first, because a snapshot or alert left pointing at a deleted
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
            f"demand planning + manufacturing + quality + returns rows "
            f"(+{bill_count + freight_bill_count} linked accounting bill(s), "
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
