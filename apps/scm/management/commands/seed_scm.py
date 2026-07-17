"""Seed Supply Chain Management (Module 4) demo data — sub-module 4.1 Procurement Management.

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
    help = "Seed SCM 4.1 Procurement demo data — idempotent (skips a tenant that already has requisitions)."

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
            # 4.2 SRM is guarded independently so it seeds even when 4.1 data already exists.
            self._seed_srm_tenant(tenant)

        self.stdout.write(self.style.SUCCESS("SCM 4.1 procurement + 4.2 SRM seed complete."))
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

    def _flush(self):
        # The AP bills this seeder created are reachable only through the receipts that link them,
        # so they must go FIRST — once the GRNs are gone there is no way to tell a seeded bill from
        # a real one, and every --flush cycle would strand another set of orphans in accounting.
        # Scoped to bills actually linked to a receipt, so a hand-entered bill is never touched.
        orphaned_bills = Bill.objects.filter(scm_goods_receipts__isnull=False).distinct()
        bill_count = orphaned_bills.count()
        orphaned_bills.delete()

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
        self.stdout.write(self.style.WARNING(
            f"Flushed all SCM procurement + SRM rows (+{bill_count} linked accounting bill(s))."))

    # ------------------------------------------------------------------ spine reuse helpers
    def _admin(self, tenant):
        return (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                or User.objects.filter(tenant=tenant).first())

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
