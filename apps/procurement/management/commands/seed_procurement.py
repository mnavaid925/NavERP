"""Seed Procurement Management (Module 6) demo data — 6.1 portal baseline + 6.2 Requisition
Management + 6.3 Approval Workflow Engine + 6.4 Vendor Management + 6.5 Sourcing & Tendering +
6.6 RFx Management.

6.1 creates, per tenant, the Task & Alert Center baseline: a handful of alerts across every kind,
severity and lifecycle state, assigned to the workspace's members. The overview's other widgets
are COMPUTED over data that already exists (``scm.PurchaseRequisition`` / ``scm.PurchaseOrder``
per L36, ``core.AuditLog`` for the feed), so this command deliberately creates no requisitions —
run ``seed_scm`` first if you want the approval/spend widgets populated.

6.2 adds the management layer around those same spine requisitions: recurring-order TEMPLATES
(with lines) ready to apply, and — when ``seed_scm`` has left at least one pending/approved
requisition to work with — one PENDING AMENDMENT so the decision queue is not empty. Both blocks
reuse existing rows rather than inventing parallel ones.

6.3 seeds the governance layer: routing rules (catch-all + two more-specific), the escalation
policy singleton, a leave-cover DOA grant and one real tier-1 signature on an existing pending
requisition when its resolved chain has 2+ tiers.

6.5 seeds sourcing events over those same approved suppliers: one AWARDED tender whose matrix,
bids and scores were driven through the real model path (open→close→award, submit/disqualify),
one OPEN RFP taking bids, and one CANCELLED RFQ — so every status badge and the analytics page
have honest rows to show.

6.4 adds vendor-management rows over scm 4.2's approved suppliers: portal access bindings,
a suspension register covering every lifecycle state, and supplier-filed invoice submissions.
Like every block here it REUSES existing parties/orders rather than inventing parallel masters.

6.6 seeds RFx Management: a Template-Library RFI blueprint plus an issued RFP carrying two
supplier responses (one fully scored, one partial) so the comparison matrix, the scoring
leaderboard and the evaluation states are populated on a fresh workspace.

6.7 seeds E-Auction Management: one AWARDED auction with a complete five-bid history and one
LIVE auction whose bids already consumed one anti-snipe extension (its close is pushed out by
``extension_seconds`` to match ``extensions_used``), so the floor, console, rules and results
pages all have honest rows on a fresh workspace.

6.9 seeds Catalog Management: an approved+preferred internal catalog line carrying two active
volume tiers, a supplier product pending approval, a blocked line, two punch-out endpoint
configurations (cXML + manual-link fallback) and one validated upload batch with rejected rows
in its error log - the governed buy-side layer over seed_scm's item master.

Each seeded alert also writes one ``core.AuditLog`` row (user=None → rendered as "System"), which
gives the Recent Activity Feed an honest baseline instead of an empty page on a fresh workspace.

Idempotent: each entity block is guarded by its own per-tenant existence check, so a second run
is a no-op without ``--flush``.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Party, PartyRole, Tenant
from apps.core.utils import write_audit_log
from apps.procurement.models import (
    AdvancedShipmentNotice,
    AsnLine,
    Backorder,
    DeliverySchedule,
    ApprovalDelegation,
    ApprovalRoutingRule,
    BidScore,
    CatalogItem,
    CatalogPriceTier,
    CatalogUploadBatch,
    EaucBid,
    EaucInvite,
    Eauction,
    EscalationPolicy,
    EventCriterion,
    ProcurementAlert,
    PunchOutEndpoint,
    PurchaseOrderChange,
    PurchaseOrderChangeLine,
    ReceiptDiscrepancy,
    ReceiptTolerancePolicy,
    ReturnToVendor,
    ReturnToVendorLine,
    SupplierInvoice,
    SupplierInvoiceLine,
    InvoiceMatchVariance,
    InvoiceDispute,
    MaverickSpendFinding,
    SpendClassificationRule,
    SpendReport,
    SpendReportSnapshot,
    BudgetMapping,
    CostForecast,
    compute_forecast_amounts,
    generate_po_from_requisition,
    RequisitionAmendment,
    RequisitionAmendmentLine,
    RequisitionApproval,
    RequisitionTemplate,
    RequisitionTemplateLine,
    RfxAnswer,
    RfxEvent,
    RfxQuestion,
    RfxResponse,
    SourcingBid,
    SourcingEvent,
    ContractAmendment,
    ContractClause,
    ContractClauseLink,
    ContractMilestone,
    ContractSigner,
    VendorInvoiceSubmission,
    VendorPortalAccess,
    VendorSuspension,
)
from apps.accounting.models import Budget, Currency, GLAccount, PaymentTerm, Project, TaxCode
from apps.scm.models import Item, PurchaseRequisition, SupplierProfile, UOM

User = get_user_model()

NOW = None  # resolved in handle() so repeated runs inside the same second stay consistent


def _alert_rows(now):
    """The demo alert set — (days_offset, kind, severity, title, message, link)."""
    return [
        (-1, "deadline", "critical", "Printer paper reorder window closes",
         "The monthly office-supplies requisition must be submitted before the supplier's "
         "cut-off or delivery slips a full cycle.", "/procurement/quick-requisition/"),
        (0, "approval", "warning", "Requisition awaiting your approval",
         "A requisition has been sitting in pending approval for two days.",
         "/scm/requisitions/"),
        (2, "delivery", "info", "Delivery update expected",
         "Vendor promised a dispatch confirmation by Wednesday; chase if it does not land.",
         ""),
        (3, "task", "warning", "Quarterly stationery stocktake",
         "Count consumables against last quarter's GRNs before raising next quarter's request.",
         ""),
        (5, "deadline", "info", "Contract renewal decision due next week",
         "Decide whether to renew, renegotiate or retender before the notice period expires.",
         ""),
        (-3, "approval", "critical", "Escalated: approval idle beyond SLA",
         "This approval breached its response SLA and was escalated to the team lead.",
         "/scm/requisitions/"),
    ]


class Command(BaseCommand):
    help = ("Seed Procurement demo data (6.1 Task & Alert Center baseline + 6.2 requisition "
            "templates and a pending amendment + 6.3 approval engine + 6.4 vendor registers + "
            "6.5 sourcing events + 6.6 RFx events + 6.7 e-auctions) — idempotent (skips a "
            "tenant that already has rows for each block).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help=("Delete ALL procurement workflow rows for ALL tenants before seeding "
                  "(alerts, approval-engine tables, templates, amendments, vendor-management "
                  "registers, sourcing events, RFx events, e-auctions) - not just "
                  "seeder-created ones."))

    def handle(self, *args, **options):
        global NOW
        NOW = timezone.now()
        if options["flush"]:
            deleted = ProcurementAlert.objects.all().count()
            # Children first: signatures reference their DOA grant (SET_NULL, but cleanest
            # in order), grants/rules/policy are standalone config. Vendor-management
            # registers are standalone rows (submissions point at POs SET_NULL) so order
            # barely matters — delete them children-last anyway.
            RequisitionApproval.objects.all().delete()
            ApprovalDelegation.objects.all().delete()
            ApprovalRoutingRule.objects.all().delete()
            EscalationPolicy.objects.all().delete()
            ProcurementAlert.objects.all().delete()
            RfxResponse.objects.all().delete()
            RfxEvent.objects.all().delete()
            # 6.5 sourcing rows: scores/criteria are event children and vanish with them.
            BidScore.objects.all().delete()
            EventCriterion.objects.all().delete()
            SourcingBid.objects.all().delete()
            SourcingEvent.objects.all().delete()
            # 6.7 e-auction rows: bids and invites are auction children (cascade) but are
            # deleted explicitly children-first so the register clears in one pass.
            EaucBid.objects.all().delete()
            EaucInvite.objects.all().delete()
            Eauction.objects.all().delete()
            VendorPortalAccess.objects.all().delete()
            VendorSuspension.objects.all().delete()
            VendorInvoiceSubmission.objects.all().delete()
            # 6.9 catalog rows: tiers are item children (cascade) but go first so the
            # register clears in one pass; endpoints/batches are standalone config.
            CatalogPriceTier.objects.all().delete()
            CatalogItem.objects.all().delete()
            CatalogUploadBatch.objects.all().delete()
            PunchOutEndpoint.objects.all().delete()
            # 6.10 change orders: lines are change children (cascade) but go first so the
            # register clears in one pass.
            PurchaseOrderChangeLine.objects.all().delete()
            PurchaseOrderChange.objects.all().delete()
            # 6.11 fulfillment rows: backorders point at schedules/ASNs (SET_NULL) so they
            # go first, then the ladder, then the ASN lines and their notices.
            Backorder.objects.all().delete()
            DeliverySchedule.objects.all().delete()
            AsnLine.objects.all().delete()
            AdvancedShipmentNotice.objects.all().delete()
            # 6.12 receipt rows: a discrepancy may point at an RTV (SET_NULL) and an RTV may
            # point back at the discrepancy that raised it, so the claims go first, then the
            # return lines (cascade children, deleted explicitly so the register clears in one
            # pass), then the returns themselves. Tolerance policies are standalone config.
            ReceiptDiscrepancy.objects.all().delete()
            ReturnToVendorLine.objects.all().delete()
            ReturnToVendor.objects.all().delete()
            ReceiptTolerancePolicy.objects.all().delete()
            # 6.13 invoice rows: a variance may point at the dispute that was raised from it
            # (SET_NULL), so disputes go first, then the variances, then the lines (cascade
            # children, deleted explicitly so the register clears in one pass), then the headers.
            # Without these four the 6.13 block's "already present, skipping" guard survives a
            # --flush and the demo invoices can never be regenerated.
            InvoiceDispute.objects.all().delete()
            InvoiceMatchVariance.objects.all().delete()
            SupplierInvoiceLine.objects.all().delete()
            SupplierInvoice.objects.all().delete()
            # 6.14 analytics rows: snapshots are report children (cascade) but go first so the
            # register clears in one pass; findings PROTECT their vendor but nothing points at a
            # finding, and a rule PROTECTs its category — neither is pointed at from anywhere, so
            # they are standalone deletes. Nothing here is a document: every row is either a
            # saved question, a frozen answer, or a detector's observation.
            SpendReportSnapshot.objects.all().delete()
            SpendReport.objects.all().delete()
            MaverickSpendFinding.objects.all().delete()
            SpendClassificationRule.objects.all().delete()
            # 6.15 budget & cost rows: a forecast points at its budget SET_NULL so order is not
            # load-bearing, but children-first keeps the flush reading top-down like every block
            # above. Without these two the 6.15 block's exists() guard survives a --flush.
            CostForecast.objects.all().delete()
            BudgetMapping.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Flushed {deleted} procurement alerts."))

        for tenant in Tenant.objects.order_by("name"):
            self._seed_alerts(tenant)
            self._seed_templates(tenant)
            self._seed_amendment(tenant)
            self._seed_approval_engine(tenant)
            self._seed_sourcing(tenant)
            self._seed_vendor_management(tenant)
            self._seed_rfx(tenant)
            self._seed_eauction(tenant)
            self._seed_contracts(tenant)
            self._seed_catalog(tenant)
            self._seed_po_management(tenant)
            self._seed_order_fulfillment(tenant)
            self._seed_goods_receipt(tenant)
            self._seed_invoice_vouchers(tenant)
            # 6.14 runs LAST on purpose: its detectors read the invoices, orders, contracts and
            # catalogue rows every block above has just created. Run earlier it would scan an
            # empty workspace and honestly report nothing.
            self._seed_spend_analytics(tenant)
            # 6.15 runs AFTER 6.14 for the same reason one level down: its frozen forecasts are
            # computed through compute_forecast_amounts over the open purchase orders and the
            # recognised invoices the blocks above just created, so the stored amounts are real
            # figures rather than zeros.
            self._seed_budget_cost(tenant)

    # -- entity blocks -------------------------------------------------------------------------

    def _seed_alerts(self, tenant):
        if ProcurementAlert.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: alerts already present, skipping.")
            return
        members = list(User.objects.filter(tenant=tenant, is_active=True)
                       .order_by("id")[:3])
        created = 0
        for index, (offset_days, kind, severity, title, message, link) in enumerate(_alert_rows(NOW)):
            status = "open"
            acknowledged_at = None
            resolved_at = None
            resolution_note = ""
            assignee = members[index % len(members)] if members else None
            # Walk two of the six rows through the lifecycle so every badge colour exists.
            if index == 1:
                status, acknowledged_at = "acknowledged", NOW - timedelta(hours=4)
            elif index == 5:
                status = "resolved"
                acknowledged_at = NOW - timedelta(days=2)
                resolved_at = NOW - timedelta(days=1)
                resolution_note = "Approved after the requester supplied the missing quote."
            alert = ProcurementAlert.objects.create(
                tenant=tenant,
                kind=kind, severity=severity, status=status,
                title=title, message=message, link_url=link,
                due_at=NOW + timedelta(days=offset_days),
                assigned_to=assignee,
                acknowledged_at=acknowledged_at,
                resolved_at=resolved_at,
                resolution_note=resolution_note,
                raised_at=NOW - timedelta(days=max(0, 3 - index)),
            )
            # The feed reads core.AuditLog; seed its baseline so the widget is not empty.
            write_audit_log(None, alert, "create")
            created += 1
        self.stdout.write(self.style.SUCCESS(f"  {tenant.name}: {created} procurement alerts."))

    # -- 6.2 Requisition Management ------------------------------------------------------------

    #: (name, description, lead_days, justification, lines=[(desc, sku, uom, qty, price)])
    _TEMPLATE_ROWS = [
        ("Monthly office supplies", "Standing monthly order for printer paper, pens and "
         "consumables. Apply in the first week of each month.", 10,
         "Recurring office consumables — budgeted under facilities overhead.",
         [("A4 printer paper (boxes of 5 reams)", "OF-PAP-A4", "box", "4", "22.50"),
          ("Ballpoint pens blue", "OF-PEN-BLU", "box", "2", "6.80"),
          ("Sticky notes assorted", "OF-NTS-AST", "pack", "3", "4.20")]),
        ("Lab consumables restock", "Quarterly laboratory consumables top-up: gloves, pipette "
         "tips, cleaning solvent.", 21,
         "Lab operations cannot run below safety stock on consumables.",
         [("Nitrile gloves medium", "LB-GLV-M", "box", "10", "8.40"),
          ("Pipette tips 1000uL", "LB-TIP-1K", "rack", "6", "31.00"),
          ("Isopropyl alcohol 5L", "LB-SOL-IPA5", "bottle", "4", "18.75")]),
        ("Annual software licences", "Renewal batch for the design team's seats — apply at least "
         "30 days before licence expiry.", 45,
         "Licences lapse without renewal; late reactivation carries a surcharge.",
         [("CAD seat subscription", "SW-CAD-SEAT", "seat", "3", "420.00"),
          ("Version control add-on", "SW-VCS-ADD", "seat", "3", "60.00")]),
    ]

    def _seed_templates(self, tenant):
        if RequisitionTemplate.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: requisition templates already present, skipping.")
            return
        from decimal import Decimal

        from django.db import transaction

        org_unit = tenant.org_units.first() if hasattr(tenant, "org_units") else None
        created = 0
        # One transaction per template: a mid-line crash must not leave a lineless template that
        # the per-tenant existence guard would then preserve forever.
        with transaction.atomic():
            for name, description, lead_days, justification, line_rows in self._TEMPLATE_ROWS:
                template = RequisitionTemplate.objects.create(
                    tenant=tenant,
                    name=name,
                    description=description,
                    default_lead_days=lead_days,
                    justification=justification,
                    org_unit=org_unit,
                    created_by=None,
                )
                for desc, sku, uom, qty, price in line_rows:
                    RequisitionTemplateLine.objects.create(
                        template=template,
                        item_description=desc,
                        sku_hint=sku,
                        uom_hint=uom,
                        quantity=Decimal(qty),
                        estimated_unit_price=Decimal(price),
                    )
                # The feed reads core.AuditLog; seed its baseline so templates are not invisible
                # there until first UI edit (same contract as _seed_alerts).
                write_audit_log(None, template, "create")
                created += 1
        self.stdout.write(self.style.SUCCESS(f"  {tenant.name}: {created} requisition templates."))

    def _seed_amendment(self, tenant):
        if RequisitionAmendment.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: requisition amendments already present, skipping.")
            return
        # Amend an EXISTING spine requisition rather than inventing one — seed_scm owns the PRs.
        target = (PurchaseRequisition.objects
                  .filter(tenant=tenant,
                          status__in=RequisitionAmendment.AMENDABLE_STATUSES)
                  .order_by("-created_at", "-id")
                  .first())
        if target is None:
            self.stdout.write(f"  {tenant.name}: no pending/approved requisition to amend, "
                              f"skipping (run seed_scm first).")
            return
        amendment = RequisitionAmendment.objects.create(
            tenant=tenant,
            requisition=target,
            amendment_type="amend",
            status="pending",
            reason="Vendor moved the price; quantities need a small bump and the date slips a "
                   "week to match their next dispatch.",
            new_required_by=(target.required_by or NOW.date()) + timedelta(days=7),
        )
        first_line = target.lines.order_by("id").first()
        if first_line is not None:
            RequisitionAmendmentLine.objects.create(
                amendment=amendment,
                target_line=first_line,
                action="update",
                quantity=first_line.quantity + 2,
            )
        write_audit_log(None, amendment, "create", {"requisition": target.number})
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: pending amendment {amendment.number} on {target.number}."))

    def _seed_approval_engine(self, tenant):
        """6.3 Approval Workflow Engine � routing rules, DOA grant, policy, one live chain.

        Two routing rules (a department-scoped executive band and a commodity rule)
        over a single-tier catch-all, the tenant's escalation policy singleton, a
        leave-cover delegation, and ONE real tier-1 signature recorded through the
        model path on an existing pending requisition so the queue shows mid-chain
        progress. Guarded per tenant on the rules block; the policy is get_or_create.
        """
        if ApprovalRoutingRule.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: approval engine rows already present, skipping.")
            return
        admin = (User.objects.filter(tenant=tenant, is_tenant_admin=True, is_active=True)
                 .order_by("id").first())
        delegate = (User.objects.filter(tenant=tenant, is_active=True)
                    .exclude(pk=getattr(admin, "pk", None)).order_by("id").first())

        # -- policy singleton -------------------------------------------------------------------
        policy = EscalationPolicy.for_tenant(tenant)
        if admin is not None and not policy.escalate_to_id:
            policy.escalate_to = admin
            policy.save(update_fields=["escalate_to", "updated_at"])

        # -- routing rules: catch-all band + two more-specific tiers -----------------------------
        today = timezone.localdate()
        ApprovalRoutingRule.objects.create(
            tenant=tenant, org_unit=None, commodity="",
            min_total=None, max_total=Decimal("10000"),
            required_tiers=1, notes="Catch-all: routine spend needs one signature.")
        dept = OrgUnit.objects.filter(tenant=tenant).order_by("id").first()
        if dept is not None:
            ApprovalRoutingRule.objects.create(
                tenant=tenant, org_unit=dept, commodity="",
                min_total=Decimal("10000"), max_total=None,
                required_tiers=2, escalation_hours=24,
                notes=f"Executive band for {dept.name}: big spend, two signatures, fast escalation.")
        ApprovalRoutingRule.objects.create(
            tenant=tenant, org_unit=None, commodity="safety",
            min_total=None, max_total=None,
            required_tiers=2,
            notes="Safety-related lines always double-sign regardless of amount.")

        # -- one DOA grant (leave cover) ----------------------------------------------------------
        if admin is not None and delegate is not None:
            ApprovalDelegation.objects.create(
                tenant=tenant, delegator=admin, delegate=delegate,
                valid_from=today, valid_until=today + timedelta(days=30),
                reason="Annual leave cover")

        # -- one REAL tier-1 signature on an existing pending requisition -------------------------
        # Honesty rules of record: approver=None (a fabricated action is never
        # attributed to a real admin), and only when the resolved chain has 2+
        # tiers — signing a single-tier chain would show a "complete" ledger over
        # a still-pending spine and corrupt the next human decision's tier math.
        pending = PurchaseRequisition.objects.filter(
            tenant=tenant, status="pending_approval").order_by("created_at").first()
        signed = None
        if pending is not None:
            from apps.procurement.models import resolve_routing
            rules = list(ApprovalRoutingRule.objects.filter(tenant=tenant, is_active=True))
            rule, _reason = resolve_routing(pending, rules=rules)
            tier_count = rule.required_tiers if rule is not None else 1
            if tier_count >= 2:
                with transaction.atomic():
                    locked = type(pending).objects.select_for_update().get(pk=pending.pk)
                    signed = RequisitionApproval.record(
                        tenant, locked, tier=1, tier_count=tier_count,
                        decision="approved", approver=None,
                        comment="Seeded first signature (System) — chain left open on purpose.")
                    write_audit_log(None, locked, "tier_approve",
                                    {"tier": f"1/{tier_count}", "seeded": True})
        made_rules = ApprovalRoutingRule.objects.filter(tenant=tenant).count()
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: approval engine ready "
            f"({made_rules} routing rules, policy {policy.idle_hours}h, "
            f"{'DOA grant' if admin is not None and delegate is not None else 'no DOA pair'}, "
            f"{f'chain {signed.number} at tier 1/{signed.tier_count}' if signed else 'no multi-tier pending requisition to sign'})."))

    # -- 6.5 Sourcing & Tendering -----------------------------------------------------------------

    def _seed_sourcing(self, tenant):
        """6.5 Sourcing & Tendering — one awarded tender (scored matrix), one open RFP with
        bids arriving, one cancelled RFQ. Suppliers come from scm 4.2's APPROVED parties
        (L36: never a parallel vendor master); with none seeded the block reports and skips.
        Guarded per tenant on the event block like every other section here.
        """
        if SourcingEvent.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: sourcing events already present, skipping.")
            return
        suppliers = [sp.party for sp in SupplierProfile.objects
                     .filter(tenant=tenant, onboarding_status="approved")
                     .select_related("party").order_by("id")]
        if not suppliers:
            self.stdout.write(f"  {tenant.name}: no approved suppliers (run seed_scm first), "
                              f"skipping sourcing.")
            return

        def _supplier(index):
            return suppliers[index % len(suppliers)]

        created = 0
        # -- event A: awarded tender, full evaluation trail --------------------------------------
        # Lifecycle honesty (CONV-I3): the event walks open→close→award() and each bid walks
        # draft→submit()/decide() through the model path with System attribution, so the
        # activity feed shows the same verbs a human run would have produced.
        with transaction.atomic():
            awarded_event = SourcingEvent.objects.create(
                tenant=tenant,
                title="Annual packaging materials supply",
                description="Two-year frame agreement for corrugated boxes, stretch wrap and "
                            "tape across the distribution centre.",
                event_type="tender", status="draft",
                currency=None, budget_estimate=Decimal("48000.00"),
                rules="Bids are evaluated on total cost (40%), delivery reliability (30%) and "
                      "quality certifications (30%). Non-compliant bids are excluded.",
                created_by=None,
            )
            write_audit_log(None, awarded_event, "create")
            awarded_event.status = "open"
            awarded_event.opened_at = NOW - timedelta(days=30)
            awarded_event.save(update_fields=["status", "opened_at", "updated_at"])
            write_audit_log(None, awarded_event, "open")

            cost = EventCriterion.objects.create(event=awarded_event, name="Total cost",
                                                 weight_pct=Decimal("40"), max_score=10)
            delivery = EventCriterion.objects.create(event=awarded_event, name="Delivery reliability",
                                                     weight_pct=Decimal("30"), max_score=10)
            quality = EventCriterion.objects.create(event=awarded_event, name="Quality & certifications",
                                                    weight_pct=Decimal("30"), max_score=10)
            bid_rows = [
                (_supplier(0), "9450.00", 12, True,
                 {"cost": Decimal("8.5"), "delivery": Decimal("9"), "quality": Decimal("9")}),
                (_supplier(1), "10200.00", 18, True,
                 {"cost": Decimal("7"), "delivery": Decimal("7.5"), "quality": Decimal("8")}),
                (_supplier(2) if len(suppliers) > 2 else _supplier(1), "8900.00", 25, False,
                 {}),
            ]
            bids = []
            for index, (party, price, lead_days, compliant, scores) in enumerate(bid_rows):
                bid = SourcingBid.objects.create(
                    tenant=tenant, event=awarded_event, supplier=party,
                    status="draft", total_price=Decimal(price),
                    lead_time_days=lead_days, is_compliant=compliant,
                    compliance_note="" if compliant else "Food-safety certificate expired.",
                    summary="Frame-agreement pricing attached; see reference for validity.",
                    contact_ref=f"bids@supplier{index + 1}.example",
                    submitted_at=NOW - timedelta(days=27 - index),
                )
                bid.submit(None)  # System-submitted demo row (CODE-M11: through the model path)
                write_audit_log(None, bid, "submit", {"event": awarded_event.number})
                for criterion, raw in (
                        (cost, scores.get("cost")),
                        (delivery, scores.get("delivery")),
                        (quality, scores.get("quality"))):
                    if raw is not None:
                        BidScore.objects.create(bid=bid, criterion=criterion, score=raw)
                        write_audit_log(None, bid, "score", {"criterion": criterion.name})
                if not compliant:
                    bid.decision_note = "Food-safety certificate expired."
                    bid.status = "disqualified"
                    bid.save(update_fields=["status", "decision_note", "updated_at"])
                    write_audit_log(None, bid, "disqualify", {"event": awarded_event.number})
                bids.append(bid)

            awarded_event.status = "closed"
            awarded_event.closed_at = NOW - timedelta(days=16)
            awarded_event.save(update_fields=["status", "closed_at", "updated_at"])
            write_audit_log(None, awarded_event, "close")

            winner = min((b for b in bids if b.is_compliant), key=lambda b: b.pk)
            awarded_event.award(winner, at=NOW - timedelta(days=14))
            write_audit_log(None, awarded_event, "award", {"bid": str(winner)})
        created += 1

        # -- event B: open RFP taking bids ---------------------------------------------------------
        with transaction.atomic():
            open_event = SourcingEvent.objects.create(
                tenant=tenant,
                title="Fleet telematics platform RFP",
                description="GPS tracking and driver-behaviour analytics for the delivery fleet.",
                event_type="rfp", status="draft",
                budget_estimate=Decimal("15000.00"),
                rules="Submit a whole-package price including hardware, install and two years "
                      "of service.",
                created_by=None,
            )
            write_audit_log(None, open_event, "create")
            open_event.status = "open"
            open_event.opened_at = NOW - timedelta(days=3)
            open_event.save(update_fields=["status", "opened_at", "updated_at"])
            write_audit_log(None, open_event, "open")
            criteria = [
                EventCriterion.objects.create(event=open_event, name=name, weight_pct=weight,
                                              max_score=10)
                for name, weight in (("Package price", Decimal("50")),
                                     ("Coverage & support", Decimal("30")),
                                     ("Implementation effort", Decimal("20")))
            ]
            submitted = SourcingBid.objects.create(
                tenant=tenant, event=open_event, supplier=_supplier(1),
                status="draft", total_price=Decimal("14200.00"), lead_time_days=21,
                summary="Includes on-site installation for all 24 vehicles.",
                contact_ref="telematics@vendor.example",
            )
            submitted.submit(None)  # System-submitted demo row (CODE-M11)
            write_audit_log(None, submitted, "submit", {"event": open_event.number})
            SourcingBid.objects.create(
                tenant=tenant, event=open_event, supplier=_supplier(0),
                status="draft", total_price=Decimal("13900.00"),
                summary="Draft — awaiting the service-level appendix before submitting.",
            )
        created += 1

        # -- event C: cancelled RFQ ------------------------------------------------------------------
        with transaction.atomic():  # CONV-I4: same atomic wrap as its siblings
            cancelled = SourcingEvent.objects.create(
                tenant=tenant,
                title="Office refurbishment RFQ (cancelled)",
                description="Partitioning and cabling for the second floor — pulled when the "
                            "lease decision changed.",
                event_type="rfq", status="cancelled",
                opens_at=NOW - timedelta(days=45), closes_at=NOW - timedelta(days=38),
                opened_at=NOW - timedelta(days=45),
            )
            write_audit_log(None, cancelled, "create")
            write_audit_log(None, cancelled, "cancel")  # CONV-I3: the trail shows the verb
        created += 1
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {created} sourcing events ready "
            f"(1 awarded w/ scored matrix, 1 open RFP, 1 cancelled)."))

    # -- 6.4 Vendor Management -------------------------------------------------------------------

    def _seed_vendor_management(self, tenant):
        """6.4 Vendor Management — portal access, suspension register, invoice submissions.

        Everything hangs off scm 4.2's APPROVED suppliers (L36: never a parallel vendor
        master); with none seeded the block reports and skips. Lifecycle coverage: one
        active access row (plus one unlinked spare), suspensions in requested/active/
        lifted states, and invoice submissions in submitted/accepted states — the accepted
        one linked to a real PO for that supplier when seed_scm left any.
        """
        suppliers = list(SupplierProfile.objects
                         .filter(tenant=tenant, onboarding_status="approved")
                         .select_related("party").order_by("id"))
        if not suppliers:
            self.stdout.write(f"  {tenant.name}: no approved suppliers (run seed_scm first), "
                              f"skipping vendor management.")
            return

        admin = (User.objects.filter(tenant=tenant, is_tenant_admin=True, is_active=True)
                 .order_by("id").first())

        # -- portal access bindings ---------------------------------------------------------------
        if not VendorPortalAccess.objects.filter(tenant=tenant).exists():
            VendorPortalAccess.objects.create(
                tenant=tenant, supplier=suppliers[0].party, invited_by=admin,
                note="Demo binding — assign a portal user to walk the gated pages.")
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: vendor portal access for {suppliers[0].party.name}."))

        # -- suspension register --------------------------------------------------------------------
        if not VendorSuspension.objects.filter(tenant=tenant).exists():
            VendorSuspension.objects.create(
                tenant=tenant, supplier=suppliers[0].party,
                kind="suspension", reason_category="delivery",
                reason="Two consecutive orders arrived outside the agreed window; suspend "
                       "while the delivery process is re-agreed.",
                status="requested", starts_on=NOW.date())
            blocked = suppliers[1] if len(suppliers) > 1 else suppliers[0]
            VendorSuspension.objects.create(
                tenant=tenant, supplier=blocked.party,
                kind="blacklist", reason_category="compliance",
                reason="Compliance certificates lapsed and were not renewed after two "
                       "chases — blocked from new POs.",
                status="active", starts_on=NOW.date() - timedelta(days=10),
                decided_at=NOW - timedelta(days=9),
                decision_note="Seeded in force (System) — lift it to demo unblocking.")
            VendorSuspension.objects.create(
                tenant=tenant, supplier=suppliers[0].party,
                kind="suspension", reason_category="quality",
                reason="Batch rejected at GRN inspection; suspended pending corrective action.",
                status="lifted", starts_on=NOW.date() - timedelta(days=60),
                ends_on=NOW.date() - timedelta(days=30),
                decided_at=NOW - timedelta(days=58),
                decision_note="In force until the CAPA closed.",
                lifted_at=NOW - timedelta(days=30),
                lift_note="CAPA verified effective; supply resumed.")
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: suspension register ready "
                f"(1 requested / 1 active / 1 lifted)."))

        # -- invoice submissions ----------------------------------------------------------------------
        if not VendorInvoiceSubmission.objects.filter(tenant=tenant).exists():
            from apps.scm.models import PurchaseOrder
            po = PurchaseOrder.objects.filter(
                tenant=tenant, vendor=suppliers[0].party).order_by("-order_date", "-id").first()
            VendorInvoiceSubmission.objects.create(
                tenant=tenant, supplier=suppliers[0].party, purchase_order=po,
                invoice_ref="INV-2026-0041", invoice_date=(NOW - timedelta(days=3)).date(),
                amount=Decimal("1840.00"),
                note="Paper goods as delivered against the standing order.",
                status="accepted", reviewed_at=NOW - timedelta(days=2),
                review_note="Matched to the GRN on review — accepted for keying into "
                            "Accounts Payable by the team.")
            VendorInvoiceSubmission.objects.create(
                tenant=tenant, supplier=suppliers[1].party if len(suppliers) > 1 else suppliers[0].party,
                invoice_ref="INV-77312", invoice_date=NOW.date(),
                amount=Decimal("412.50"),
                note="Monthly consumables top-up.",
                status="submitted")
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: invoice submission register ready (1 accepted / 1 submitted)."))

    # -- 6.6 RFx Management ---------------------------------------------------------------------

    #: (section, prompt, answer_type, options, weight, scored)
    _RFI_TEMPLATE_QUESTIONS = [
        ("Company profile", "How many years has your company operated in this market?",
         "number", "", "1.00", True),
        ("Company profile", "List the certifications relevant to this category.",
         "longtext", "", "2.00", True),
        ("Capability", "Describe your production capacity per month.",
         "longtext", "", "2.00", True),
        ("Capability", "Do you offer nationwide delivery?",
         "choice", "Yes\nNo\nPartial", "1.00", True),
        ("Compliance", "Confirm you accept our standard payment terms.",
         "choice", "Yes\nNo", "0", False),
    ]

    def _seed_rfx(self, tenant):
        """6.6 RFx Management - one Template-Library RFI blueprint plus a live issued RFP with
        two supplier responses (one fully scored, one partial) so the comparison matrix, the
        scoring leaderboard and the evaluation states are populated on a fresh workspace.
        Suppliers reuse seed_scm's core.Party rows by name (get-or-create, never duplicate).
        Guarded per tenant like every other block."""
        if RfxEvent.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: RFx events already present, skipping.")
            return

        def _supplier(name):
            party = Party.objects.filter(tenant=tenant, name=name).first()
            if party is None:
                party = Party.objects.create(tenant=tenant, kind="organization", name=name)
            PartyRole.objects.get_or_create(
                tenant=tenant, party=party, role="supplier",
                defaults={"status": "active", "start_date": timezone.localdate()})
            return party

        made = 0
        with transaction.atomic():
            library = RfxEvent.objects.create(
                tenant=tenant, is_template=True, rfx_type="rfi",
                title="Standard supplier capability RFI",
                description="Baseline questionnaire for qualifying a new supplier: company "
                            "profile, capability and compliance basics.",
            )
            for i, row in enumerate(self._RFI_TEMPLATE_QUESTIONS):
                section, prompt, qtype, options, weight, scored = row
                RfxQuestion.objects.create(
                    event=library, section=section, prompt=prompt, answer_type=qtype,
                    options=options, weight=Decimal(weight), is_scored=scored, order=i + 1)
            write_audit_log(None, library, "create")
            made += 1

            requisition = (PurchaseRequisition.objects.filter(tenant=tenant)
                           .order_by("-created_at").first())
            rfp = RfxEvent.objects.create(
                tenant=tenant, rfx_type="rfp",
                title="Managed print services RFP",
                description="Proposal request covering devices, service levels and "
                            "consumables pricing for a three-year term.",
                requisition=requisition, status="issued",
                issued_at=NOW - timedelta(days=2),
                response_due=NOW + timedelta(days=5))
            for i, (section, prompt, qtype, options, weight, scored) in enumerate([
                ("Technical", "Describe your managed-print platform and reporting.",
                 "longtext", "", "2.00", True),
                ("Commercial", "State your cost-per-page for mono and colour.",
                 "number", "", "3.00", True),
                ("Service", "What is your guaranteed on-site response time?",
                 "choice", "4 hours\nNext business day\n2 business days", "1.00", True),
            ]):
                RfxQuestion.objects.create(
                    event=rfp, section=section, prompt=prompt, answer_type=qtype,
                    options=options, weight=Decimal(weight), is_scored=scored, order=i + 1)
            write_audit_log(None, rfp, "create")
            write_audit_log(None, rfp, "issue")
            made += 1

            questions = list(rfp.questions.order_by("order"))
            plans = [
                ("Northwind Industrial Supply",
                 ["8", "7", "7"],
                 "Strong platform proposal; pricing mid-field.",
                 "under_review"),
                ("Cascade Components Ltd",
                 ["6", None, "5"],
                 "Competitive service terms; commercial answer outstanding.",
                 "submitted"),
            ]
            for name, scores, note, status in plans:
                response = RfxResponse.objects.create(
                    tenant=tenant, event=rfp, supplier=_supplier(name), notes=note)
                for question, score in zip(questions, scores):
                    RfxAnswer.objects.create(
                        response=response, question=question,
                        answer_text="Detailed in the attached proposal." if score else "",
                        score=Decimal(score) if score else None)
                if not response.submit():
                    raise RuntimeError(f"seed: could not submit seeded response {response.pk}")
                if status == "under_review" and not response.transition("under_review"):
                    raise RuntimeError(f"seed: could not advance seeded response {response.pk}")
                write_audit_log(None, response, "create")
                made += 1
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: RFx ready ({made} events/responses)."))

    # -- 6.7 E-Auction Management ----------------------------------------------------------------

    def _eauc_supplier(self, tenant, name):
        """Same get-or-create-by-name contract as _seed_rfx's helper — one supplier identity
        per name per tenant, never a duplicate Party."""
        party = Party.objects.filter(tenant=tenant, name=name).first()
        if party is None:
            party = Party.objects.create(tenant=tenant, kind="organization", name=name)
        PartyRole.objects.get_or_create(
            tenant=tenant, party=party, role="supplier",
            defaults={"status": "active", "start_date": timezone.localdate()})
        return party

    def _seed_eauction(self, tenant):
        """6.7 E-Auction Management - one AWARDED auction with a complete bid history (so the
        results page shows real savings and an award decision) and one LIVE auction (window
        open right now) whose bids already triggered the anti-snipe extension once. Suppliers
        reuse seed_scm's core.Party rows; guarded per tenant like every other block."""
        if Eauction.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: e-auctions already present, skipping.")
            return
        northwind = self._eauc_supplier(tenant, "Northwind Industrial Supply")
        cascade = self._eauc_supplier(tenant, "Cascade Components Ltd")
        requisition = (PurchaseRequisition.objects.filter(tenant=tenant)
                       .order_by("-created_at").first())
        made = 0

        # -- finished + awarded: full history for the results page --------------------------------
        with transaction.atomic():
            done = Eauction.objects.create(
                tenant=tenant,
                title="Annual packaging consumables reverse auction",
                description="Twelve-month supply of corrugated packaging; awarded to the "
                            "lowest compliant bidder at close.",
                currency=requisition.currency if requisition else None,
                requisition=requisition,
                start_price=Decimal("48000.00"), reserve_price=Decimal("39000.00"),
                min_decrement=Decimal("500.00"),
                opens_at=NOW - timedelta(days=2), closes_at=NOW - timedelta(hours=1),
                status="closed",
            )
            for invitee in (northwind, cascade):
                EaucInvite.objects.create(tenant=tenant, auction=done, supplier=invitee,
                                          contact_note="Seeded invite.")
            ladder = [
                (northwind, "46800.00", 26), (cascade, "45500.00", 21),
                (northwind, "44750.00", 15), (cascade, "43900.00", 8),
                (northwind, "43000.00", 3),
            ]
            # Backfill straight through save(): the write-time rules check the CURRENT
            # window, which has already closed for this finished auction - the seeded
            # ladder complies with every pace rule anyway.
            for supplier, amount, minutes_ago in ladder:
                bid = EaucBid(tenant=tenant, auction=done, supplier=supplier,
                              amount=Decimal(amount),
                              placed_at=NOW - timedelta(minutes=minutes_ago))
                bid.save()
                write_audit_log(None, bid, "create")
            if not done.award(northwind, note="Lowest compliant bidder at close."):
                raise RuntimeError(f"seed: could not award seeded auction {done.pk}")
            write_audit_log(None, done, "create")
            write_audit_log(None, done, "award")
            made += 1

        # -- live now: window open, extension already fired once -----------------------------------
        with transaction.atomic():
            live = Eauction.objects.create(
                tenant=tenant,
                title="IT peripherals spot-buy reverse auction",
                description="Spot buy closing this afternoon — anti-snipe rules active.",
                start_price=Decimal("12500.00"),
                min_decrement=Decimal("250.00"),
                extension_trigger_seconds=90, extension_seconds=120, max_extensions=3,
                extensions_used=1,
                opens_at=NOW - timedelta(hours=1),
                # The one consumed extension pushed the close out by extension_seconds —
                # presetting extensions_used without moving closes_at would contradict it.
                closes_at=NOW + timedelta(hours=2) + timedelta(seconds=120),
                status="scheduled",
            )
            for invitee in (northwind, cascade):
                EaucInvite.objects.create(tenant=tenant, auction=live, supplier=invitee)
            live_bids = [
                (cascade, "11900.00", 42), (northwind, "11400.00", 18),
                (cascade, "10900.00", 2),
            ]
            for supplier, amount, minutes_ago in live_bids:
                bid = EaucBid(tenant=tenant, auction=live, supplier=supplier,
                              amount=Decimal(amount),
                              placed_at=NOW - timedelta(minutes=minutes_ago))
                bid.save()
                write_audit_log(None, bid, "create")
            write_audit_log(None, live, "create")
            write_audit_log(None, live, "publish")
            made += 1
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: e-auctions ready ({made} auctions: 1 awarded w/ history, "
            f"1 live)."))

    # -- 6.8 Contract Management ------------------------------------------------------------------

    def _contract_supplier(self, tenant, name):
        """Same get-or-create-by-name contract as the 6.5/6.7 helpers — one supplier
        identity per name per tenant, never a duplicate Party."""
        party = Party.objects.filter(tenant=tenant, name=name).first()
        if party is None:
            party = Party.objects.create(tenant=tenant, kind="organization", name=name)
        PartyRole.objects.get_or_create(
            tenant=tenant, party=party, role="supplier",
            defaults={"status": "active", "start_date": timezone.localdate()})
        return party

    def _seed_contracts(self, tenant):
        """6.8 Contract Management - the clause library (5 pre-approved clauses), one
        AUTHORED agreement on scm 4.2's SupplierContract spine with clause links,
        signature slots (1 supplier + 1 internal, unsigned so the sign page has a live
        token), milestones across every kind/state, and one PENDING amendment so the
        decision queue is not empty. Reuses spine parties; guarded per tenant."""
        from apps.scm.models import SupplierContract

        if ContractClause.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: contracts already present, skipping.")
            return
        admin_user = User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
        member = User.objects.filter(tenant=tenant, is_tenant_admin=False).first()
        supplier = self._contract_supplier(tenant, "Northwind Industrial Supply")
        # User rows are optional in bare tenants — never assume an admin exists when
        # stamping the internal signer.
        internal_name = ((admin_user.get_full_name() or admin_user.username)
                         if admin_user else "Tenant Admin")
        internal_email = (admin_user.email or "admin@example.com"
                          if admin_user else "admin@example.com")

        today = timezone.localdate()
        made = 0
        with transaction.atomic():
            # The clause library is part of this sub-module's seeded state, so it is
            # created INSIDE the atomic block: a partial failure must roll back
            # together with the agreement, or the exists() guard above would see the
            # half-built clauses on the next run and silently skip the tenant forever.
            clauses = {}
            for title, category, body in [
                ("Governing law & venue", "legal",
                 "This Agreement is governed by the laws agreed in writing by the Parties; "
                 "the courts of that jurisdiction have exclusive venue."),
                ("Payment terms — net 30", "payment",
                 "Invoices are payable within thirty (30) days of a valid invoice. Late "
                 "payments accrue interest at 1% per month."),
                ("Delivery & acceptance", "delivery",
                 "Goods must conform to the purchase order. Buyer has five (5) business "
                 "days to inspect; acceptance waives non-conformity discoverable then."),
                ("Confidentiality", "confidentiality",
                 "Each Party protects the other's confidential information with at least "
                 "the care it applies to its own, for three (3) years after disclosure."),
                ("Termination for convenience", "termination",
                 "Either Party may terminate on sixty (60) days' written notice; Buyer pays "
                 "for conforming goods delivered before the effective date."),
            ]:
                clauses[title] = ContractClause.objects.create(
                    tenant=tenant, title=title, category=category, body=body,
                    version="v1.0", is_pre_approved=True)
                write_audit_log(None, clauses[title], "create")

            contract = SupplierContract.objects.create(
                tenant=tenant,
                party=supplier,
                title="Annual facilities & consumables master agreement",
                contract_type="master",
                status="active",
                start_date=today - timedelta(days=330),
                end_date=today + timedelta(days=20),
                contract_value=Decimal("96000.00"),
                auto_renew=True,
                renewal_notice_days=30,
                owner=admin_user,
                terms_summary="Twelve-month master supply agreement with quarterly price review.",
            )
            for order, clause in enumerate(clauses.values(), start=1):
                ContractClauseLink.objects.create(
                    contract=contract, clause=clause, section_order=order)
            internal_signer = ContractSigner.objects.create(
                tenant=tenant, contract=contract, role="internal",
                signer_name=internal_name,
                signer_email=internal_email, order=1)
            supplier_signer = ContractSigner.objects.create(
                tenant=tenant, contract=contract, role="supplier",
                signer_party=supplier, signer_name="Dana Reyes",
                signer_email="dana.reyes@northwind.example.com", order=2)
            ContractMilestone.objects.create(
                tenant=tenant, contract=contract, kind="deliverable",
                title="Quarterly business review Q1", due_date=today + timedelta(days=12),
                notes="Scorecard + savings walkthrough.")
            ContractMilestone.objects.create(
                tenant=tenant, contract=contract, kind="payment",
                title="Milestone payment 2 of 4", due_date=today + timedelta(days=30),
                amount=Decimal("24000.00"))
            ContractMilestone.objects.create(
                tenant=tenant, contract=contract, kind="penalty",
                title="Late-delivery credit (March)", due_date=today - timedelta(days=6),
                amount=Decimal("750.00"), status="completed",
                completed_at=NOW, completed_by=admin_user,
                notes="Credited on the March invoice.")
            amendment = ContractAmendment.objects.create(
                tenant=tenant, contract=contract,
                reason="Supplier requested an earlier renewal notice window to plan stock.",
                proposed_notice_days=45,
                proposed_summary="Renewal notice window moves 30 → 45 days; no other terms move.",
                requested_by=member or admin_user)
            write_audit_log(None, contract, "create")
            write_audit_log(None, amendment, "create")
            made += 1
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: contracts ready ({made} agreement: clause library x{len(clauses)}, "
            f"2 signature slots, 3 milestones, 1 pending amendment)."))

    # -- 6.9 Catalog Management -------------------------------------------------------------------

    def _catalog_supplier(self, tenant, name):
        """Catalog block's own name for the shared get-or-create-by-name supplier helper —
        one supplier identity per name per tenant, never a duplicate Party."""
        return self._eauc_supplier(tenant, name)

    def _seed_catalog(self, tenant):
        """6.9 Catalog Management - the governed buy-side layer over seed_scm's item master and
        4.2 suppliers: one approved+preferred internal catalog line carrying two active volume
        tiers, a supplier product still pending approval, a blocked line, two punch-out endpoint
        configurations and one validated upload batch whose error log shows rejected rows.
        Reuses existing Item/UOM/Currency/Party rows; guarded per tenant like every block."""
        if CatalogItem.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: catalog items already present, skipping.")
            return
        item = Item.objects.filter(tenant=tenant).select_related("uom").first()
        currency = Currency.objects.order_by("id").first()
        if item is None:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no scm.Item rows (run seed_scm first) - catalog skipped."))
            return
        supplier = self._catalog_supplier(tenant, "Northwind Industrial Supply")
        # ONE lookup before the atomic block — the same user stamps every approval/submit;
        # no post-create UPDATE round-trips.
        approver = User.objects.filter(tenant=tenant).order_by("id").first()
        made = 0
        with transaction.atomic():
            approved = CatalogItem.objects.create(
                tenant=tenant, source_type="internal", item=item,
                uom=item.uom, currency=currency,
                name=f"{item.name} (preferred buy)", description="Internal stock item "
                "published to the buying catalog with contracted volume breaks.",
                base_price=item.standard_cost or Decimal("120.00"),
                status="approved", approved_by=approver, approved_at=NOW,
                is_preferred=True, category_text="Office supplies",
            )
            write_audit_log(None, approved, "create")
            for qty, price in ((Decimal("10"), Decimal("118.00")), (Decimal("50"), Decimal("112.50"))):
                tier = CatalogPriceTier.objects.create(
                    tenant=tenant, catalog_item=approved, min_quantity=qty,
                    unit_price=price, valid_from=timezone.localdate(), status="active",
                    approved_by=approver, approved_at=NOW)
                write_audit_log(None, tier, "create")
                made += 1
            pending = CatalogItem.objects.create(
                tenant=tenant, source_type="supplier_product", supplier=supplier,
                name="Industrial safety gloves (cut level D)",
                supplier_part_no="NW-GLOVE-D1", description="Nitrile-coated cut-resistant "
                "gloves, pack of 12.", base_price=Decimal("34.90"),
                status="pending_approval", submitted_by=approver, submitted_at=NOW,
                category_text="Safety",
            )
            write_audit_log(None, pending, "create")
            blocked = CatalogItem.objects.create(
                tenant=tenant, source_type="supplier_product",
                name="Generic toner cartridge 85A",
                supplier_part_no="GEN-TONER-85A",
                description="Off-brand cartridge; blocked after two quality returns.",
                base_price=Decimal("58.00"), status="blocked",
                rejection_reason="Blocked by purchasing after repeated defect reports.",
            )
            write_audit_log(None, blocked, "create")
            poe_amazon = PunchOutEndpoint.objects.create(
                tenant=tenant, party=supplier, name="Amazon Business (sandbox)",
                protocol="cxml", punchout_url="https://sandbox.amazon-business.example/cxml",
                username="naverp-procurement", shared_secret="demo-only-not-a-secret",
                notes="cXML punch-out configuration; live handshake deferred.")
            write_audit_log(None, poe_amazon, "create")
            poe_grainger = PunchOutEndpoint.objects.create(
                tenant=tenant, party=self._catalog_supplier(tenant, "Cascade Components Ltd"),
                name="Grainger public catalogue", protocol="manual_link",
                punchout_url="https://www.grainger.example/", enabled=False,
                notes="Manual link fallback while OCI credentials are pending.")
            write_audit_log(None, poe_grainger, "create")
            batch = CatalogUploadBatch.objects.create(
                tenant=tenant, party=supplier,
                original_filename="northwind-catalogue-2026-08.csv",
                notes="August price-file submission from Northwind.",
                rows_parsed=8, rows_accepted=6, rows_rejected=2,
                error_log="row 3: unit_price missing\nrow 7: unknown uom_code 'BOXES'",
                status="validated", validated_at=NOW,
                validated_by=approver)
            write_audit_log(None, batch, "create")
            made += 3
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: catalog ready ({made} items/tiers, 2 punch-out endpoints, "
            f"1 validated upload batch)."))

    # -- 6.10 Purchase Order Management ----------------------------------------------------------

    def _seed_po_management(self, tenant):
        """6.10 Purchase Order Management - one PENDING change order (amend) over a dispatched
        purchase order, one REJECTED cancellation for the decision trail, and one generated PO
        from an approved requisition. The generation runs through the REAL
        generate_po_from_requisition() service under a lock, exactly as the view does, so the
        seeded order has honest derived totals. Guarded per tenant like every other block."""
        if PurchaseOrderChange.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: PO change orders already present, skipping.")
            return
        from django.db import transaction

        from apps.scm.models import (  # local: spine touch, peer-app models
            PurchaseOrder as _PO,
            PurchaseOrderLine as _POLine,
            PurchaseRequisitionLine as _PRLine,
        )

        members = list(User.objects.filter(tenant=tenant, is_active=True).order_by("id"))
        filer = members[0] if members else None
        suppliers = list(Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
                         .distinct().order_by("id"))
        if not suppliers:
            suppliers = [Party.objects.filter(tenant=tenant).order_by("id").first()]
        supplier = suppliers[0]
        currency = Currency.objects.order_by("id").first()

        # A dispatched order to hang the change on — reuse a seeded one, else draft a small one.
        order = _PO.objects.filter(
            tenant=tenant, status__in=PurchaseOrderChange.CHANGEABLE_STATUSES).first()
        if order is None:
            order = _PO.objects.create(
                tenant=tenant, vendor=supplier, currency=currency,
                order_date=(NOW - timedelta(days=7)).date(),
                expected_date=(NOW + timedelta(days=14)).date(),
                status="sent",
                notes="Standing monthly stationery order.")
            for desc, sku, qty, price in (
                    ("A4 printer paper (boxes of 5 reams)", "OF-PAP-A4", "12", "22.50"),
                    ("Ballpoint pens blue", "OF-PEN-BLU", "6", "6.80")):
                _POLine.objects.create(
                    purchase_order=order, item_description=desc, sku_hint=sku,
                    quantity=Decimal(qty), unit_price=Decimal(price))
            order.recalc_totals()
        first_line = order.lines.order_by("id").first()

        pending = PurchaseOrderChange.objects.create(
            tenant=tenant, purchase_order=order, change_type="amend", status="pending",
            requested_by=filer, reason="Delivery window moved after the supplier's schedule "
            "call — asking to push the expected date and top up the paper quantity.",
            new_expected_date=(NOW + timedelta(days=21)).date())
        if first_line is not None:
            PurchaseOrderChangeLine.objects.create(
                change=pending, action="update", target_line=first_line,
                quantity=first_line.quantity + Decimal("4"))
        write_audit_log(None, pending, "create")

        rejected = PurchaseOrderChange.objects.create(
            tenant=tenant, purchase_order=order, change_type="cancel", status="rejected",
            requested_by=filer, reason="Tried to cancel when the reorder seemed delayed.",
            decided_by=filer, decided_at=NOW - timedelta(hours=20),
            decision_note="Not rejected as a request — the delay resolved; order proceeds.")
        write_audit_log(None, rejected, "create")

        # A generated PO from an approved requisition — reuse one, else seed a small approved PR.
        requisition = PurchaseRequisition.objects.filter(
            tenant=tenant, status="approved").order_by("created_at").first()
        if requisition is None:
            requisition = PurchaseRequisition.objects.create(
                tenant=tenant, title="Lab consumables restock", requester=filer,
                currency=currency, status="approved", approved_at=NOW,
                required_by=(NOW + timedelta(days=30)).date(),
                justification="Quarterly laboratory consumables top-up; approved offline.")
            for desc, sku, uom, qty, price in (
                    ("Nitrile gloves medium", "LB-GLV-M", "box", "10", "8.40"),
                    ("Pipette tips 1000uL", "LB-TIP-1K", "rack", "6", "31.00")):
                _PRLine.objects.create(
                    requisition=requisition, item_description=desc, sku_hint=sku,
                    uom_hint=uom, quantity=Decimal(qty), estimated_unit_price=Decimal(price),
                    needed_by=(NOW + timedelta(days=30)).date())
            requisition.recalc_totals()
        generated = None
        with transaction.atomic():
            locked = PurchaseRequisition.objects.select_for_update().get(pk=requisition.pk)
            if (locked.status == "approved"
                    and not locked.purchase_orders.exists()):
                generated = generate_po_from_requisition(locked, vendor=supplier)

        note = (f"  {tenant.name}: PO management ready "
                f"(1 pending amend + 1 rejected cancel over {order.number}")
        if generated is not None:
            note += f"; generated {generated.number} from {requisition.number}"
        note += ")."
        self.stdout.write(self.style.SUCCESS(note))

    def _seed_order_fulfillment(self, tenant):
        """6.11 Order Fulfillment & Tracking - one IN-FLIGHT advance shipping notice whose first
        line is deliberately short of the ordered quantity (so the discrepancy fold, the variance
        badges and the "record the shortfall" hand-off all have something real to show), one
        DELIVERED notice carrying a proof-of-delivery block for the arrivals board's Confirmed
        tab (the in-flight one is due TODAY so the arrivals board's DEFAULT tab has a row to
        confirm), a three-instalment delivery ladder over one order line, and two backorders - one
        rescheduled with its promise still ahead and one already past due, so the risk buckets
        are not all the same colour.

        Idempotent like every other block: guarded per tenant, and every numbered row is reached
        through get_or_create or an existence check keyed on a natural business key. A bare
        .create() on a TenantNumbered model would mint ASN-00003 on the second run.
        """
        if AdvancedShipmentNotice.objects.filter(tenant=tenant).exists():
            self.stdout.write(
                f"  {tenant.name}: advance shipping notices already present, skipping.")
            return

        from apps.scm.models import PurchaseOrder as _PO  # local: spine touch, peer-app model

        members = list(User.objects.filter(tenant=tenant, is_active=True).order_by("id"))
        filer = members[0] if members else None

        # Reuse a real receivable order rather than inventing one - the spine's seed_scm leaves
        # several behind. It has to be one that still has HEADROOM on a line: an order whose
        # lines are already fully received gives every AsnLine an outstanding_at_declare of 0,
        # so the deliberately short line below reads as OVER-shipped, shortfall stays 0, and the
        # whole ASN-shortfall -> backorder hand-off is unreachable from the demo data.
        order = next(
            (candidate
             for candidate in _PO.objects.filter(
                 tenant=tenant, status__in=_PO.RECEIVABLE_STATUSES).order_by("id")
             if any(line.outstanding_quantity() > 0 for line in candidate.lines.all())),
            None)
        if order is None:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no receivable purchase order with an outstanding line - "
                f"skipping order fulfillment."))
            return
        lines = list(order.lines.order_by("id"))
        if not lines:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: {order.number} has no lines - skipping order fulfillment."))
            return

        # Land on lines that still have a live balance; lines[0] stays the fallback so the block
        # degrades to its old shape rather than skipping if nothing is outstanding.
        first = next((line for line in lines if line.outstanding_quantity() > 0), lines[0])
        second = next((line for line in lines
                       if line is not first and line.outstanding_quantity() > 0), first)
        today = NOW.date()

        # Size the shortfall against what is still OUTSTANDING, not against the ordered quantity:
        # an ASN's variance is declared-vs-outstanding, so a line whose balance was already
        # received renders every declaration as an over-shipment.
        first_qty = first.outstanding_quantity() or Decimal("1")
        # Short-ship the first line by 4 where the outstanding balance allows it, else by half -
        # a seeded order from another module may carry a much smaller line.
        gap = Decimal("4") if first_qty > Decimal("4") else (first_qty / 2)
        gap = gap.quantize(Decimal("0.0001"))
        short_qty = (first_qty - gap).quantize(Decimal("0.0001"))

        # (a) The in-flight notice: submitted, on the road, one line short.
        asn = AdvancedShipmentNotice.objects.filter(
            tenant=tenant, supplier_reference="DN-88412").first()
        if asn is None:
            asn = AdvancedShipmentNotice.objects.create(
                tenant=tenant, purchase_order=order, supplier_reference="DN-88412",
                source="email", status="submitted", submitted_at=NOW - timedelta(days=2),
                ship_date=today - timedelta(days=2),
                # Due TODAY, not tomorrow: the arrivals board defaults to its "Due today" tab,
                # so a notice landing tomorrow left the flagship Delivery Confirmation page
                # showing an empty state (and its inline confirm form unrendered) on a freshly
                # seeded system.
                expected_delivery_date=today,
                carrier_name="Meridian Freight", tracking_number="MF7741903221",
                bill_of_lading_ref="BOL-2291-A", container_ref="MSKU7741903",
                freight_terms="prepaid", package_count=14, pallet_count=2,
                gross_weight_kg=Decimal("318.40"), volume_cbm=Decimal("1.860"),
                created_by=filer,
                notes="Supplier confirmed dispatch by email; first line short-shipped, "
                      "balance to follow on the next production run.")
            AsnLine.objects.create(
                asn=asn, po_line=first, quantity_shipped=short_qty,
                package_ref="PAL-01", lot_number="LOT-2291", country_of_origin="DE",
                notes=f"Short by {gap} - balance backordered.")
            if second is not first:
                AsnLine.objects.create(
                    asn=asn, po_line=second, quantity_shipped=second.quantity or Decimal("1"),
                    package_ref="PAL-02", country_of_origin="DE")
            write_audit_log(None, asn, "create")

        # (b) Last cycle's notice, taken all the way to delivered through the REAL verb so the
        # POD block is stamped exactly the way the confirm view stamps it.
        delivered = AdvancedShipmentNotice.objects.filter(
            tenant=tenant, supplier_reference="DN-88109").first()
        if delivered is None:
            delivered = AdvancedShipmentNotice.objects.create(
                tenant=tenant, purchase_order=order, supplier_reference="DN-88109",
                source="portal", status="in_transit", submitted_at=NOW - timedelta(days=9),
                ship_date=today - timedelta(days=9),
                expected_delivery_date=today - timedelta(days=4),
                carrier_name="Meridian Freight", tracking_number="MF7741881004",
                freight_terms="prepaid", package_count=6, pallet_count=1,
                gross_weight_kg=Decimal("96.20"), created_by=filer,
                notes="Previous cycle's consignment - arrived, checked and signed for.")
            AsnLine.objects.create(
                asn=delivered, po_line=first,
                quantity_shipped=(first_qty / 2).quantize(Decimal("0.0001")),
                package_ref="PAL-A", country_of_origin="DE")
            delivered.confirm_delivery(
                filer, delivered_at=NOW - timedelta(days=4), arrival_condition="good",
                pod_reference="POD-55120", received_signature_name="R. Whitfield")
            write_audit_log(None, delivered, "create")

        # (c) A three-instalment ladder over the first line. Keyed on (po_line, sequence) -
        # the unique_together - so a re-run finds the rows instead of over-committing the line.
        per = (first_qty / 3).quantize(Decimal("0.0001"))
        final = (first_qty - per * 2).quantize(Decimal("0.0001"))
        schedules = []
        for index in range(3):
            need_by = today + timedelta(days=7 * (index + 1))
            row, _created = DeliverySchedule.objects.get_or_create(
                tenant=tenant, po_line=first, sequence=index + 1,
                defaults={
                    "scheduled_quantity": final if index == 2 else per,
                    "need_by_date": need_by,
                    "promised_quantity": final if index == 2 else per,
                    "promised_date": need_by + timedelta(days=2 if index else 0),
                    "status": "confirmed" if index == 0 else "planned",
                    "ship_to": order.ship_to,
                    "delivery_mode": "standard",
                    "asn": delivered if index == 0 else None,
                    "change_reason": "Split into three instalments at order confirmation.",
                    "created_by": filer,
                })
            schedules.append(row)

        # (d) Two backorders with different risk shapes. Keyed on
        # (po_line, reason, quantity_backordered) - no number is guessed.
        backorder_specs = [
            dict(po_line=first, reason="out_of_stock", quantity=gap,
                 delivery_schedule=schedules[2] if len(schedules) > 2 else None, asn=asn,
                 reason_note="Mill stock ran out mid-pick; balance promised from the next run.",
                 original=today + timedelta(days=1), revised=today + timedelta(days=5),
                 status="rescheduled", count=1,
                 note="Balance of the short-shipped line on DN-88412."),
            dict(po_line=second, reason="production_delay",
                 quantity=(min(Decimal("2"), second.quantity or Decimal("1"))
                           ).quantize(Decimal("0.0001")),
                 delivery_schedule=None, asn=None,
                 reason_note="Supplier's line stopped for a tooling change.",
                 original=today - timedelta(days=8), revised=today - timedelta(days=2),
                 status="open", count=0,
                 note="Promise date already blown - chase the supplier."),
        ]
        made = 0
        for spec in backorder_specs:
            exists = Backorder.objects.filter(
                tenant=tenant, po_line=spec["po_line"], reason=spec["reason"],
                quantity_backordered=spec["quantity"]).first()
            if exists is not None:
                continue
            row = Backorder.objects.create(
                tenant=tenant, po_line=spec["po_line"],
                delivery_schedule=spec["delivery_schedule"], asn=spec["asn"],
                quantity_backordered=spec["quantity"], reason=spec["reason"],
                reason_note=spec["reason_note"], original_promise_date=spec["original"],
                revised_promise_date=spec["revised"], status=spec["status"],
                reschedule_count=spec["count"], created_by=filer, notes=spec["note"])
            write_audit_log(None, row, "create")
            made += 1

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: order fulfillment ready ({asn.number} in flight, "
            f"{delivered.number} delivered, {len(schedules)} instalments, "
            f"{made} backorders on {order.number})."))

    def _seed_goods_receipt(self, tenant):
        """6.12 Goods Receipt & Inspection - the advisory tolerance band, two receipt
        discrepancies (one still open, one taken all the way to resolved through the real verbs)
        and two returns to vendor (one authorized with lines, one still draft), all hung off a
        receipt seed_scm already booked.

        Nothing here posts stock and nothing posts to the ledger: ``_post_grn_receipt``
        (apps/scm/views/_helpers.py) already moved the ACCEPTED quantity, a quantity rejected at
        the dock never entered stock, and ``accounting.Bill`` has no vendor-credit kind yet - so
        an RTV's ``credit_note_ref`` is a reference, not a posting (L29/L36).

        Idempotent in three independent blocks rather than behind one big guard, so a workspace
        that had no goods receipt on the first run still gets its discrepancies on the next:
        policies go through get_or_create keyed on (tenant, name), and every numbered row is
        reached through an existence check on a natural business key. A bare .create() on a
        TenantNumbered model would mint RDS-00003 / RTV-00003 on the second run.
        """
        from apps.scm.models import GoodsReceiptNote as _GRN  # local: spine touch, peer-app model

        members = list(User.objects.filter(tenant=tenant, is_active=True).order_by("id"))
        filer = members[0] if members else None
        today = NOW.date()

        # (a) The advisory band. Two rules on purpose: a catch-all every line resolves to, and a
        # stricter vendor-pinned one carrying a lower ``priority``, so the resolver's
        # specificity-then-priority tie-break is visible on a fresh workspace.
        catch_all, _created = ReceiptTolerancePolicy.objects.get_or_create(
            tenant=tenant, name="Standard receiving tolerance",
            defaults={
                "over_receipt_pct": Decimal("5.00"),
                "under_receipt_pct": Decimal("10.00"),
                "early_receipt_days": 3,
                "late_receipt_days": 2,
                "action": "warn",
                "priority": 10,
                "notes": "Applies to every line no more specific rule covers.",
            })
        policies = [catch_all]

        receipt = (_GRN.objects.filter(tenant=tenant)
                   .select_related("purchase_order", "purchase_order__vendor")
                   .order_by("-id").first())
        if receipt is None:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no goods receipt on file - seeded the catch-all tolerance "
                f"only (run seed_scm for discrepancies and returns)."))
            return

        order = receipt.purchase_order
        vendor = order.vendor
        strict, _created = ReceiptTolerancePolicy.objects.get_or_create(
            tenant=tenant, name=f"{vendor.name} - tight band",
            defaults={
                "vendor": vendor,
                "over_receipt_pct": Decimal("2.00"),
                "under_receipt_pct": Decimal("5.00"),
                "over_receipt_qty": Decimal("5.0000"),
                "early_receipt_days": 1,
                "late_receipt_days": 1,
                "action": "block_flag",
                "priority": 5,
                "notes": ("Repeated short shipments - flag every exception for review. "
                          "block_flag FLAGS the line; it never blocks scm:goodsreceipt_receive."),
            })
        policies.append(strict)

        lines = list(receipt.lines.select_related("po_line").order_by("id"))
        first_line = lines[0] if lines else None

        # (b) Two claims against that receipt. Keyed on (tenant, goods_receipt, kind) so a re-run
        # finds them rather than minting a third number.
        discrepancy_specs = [
            dict(kind="damaged", severity="major", quantity=Decimal("3.0000"),
                 remedy="rtv", lot="LOT-2291",
                 description=("Three units arrived with crushed corners - the outer carton was "
                              "wet on the pallet base. Photographed on the dock before "
                              "unwrapping.")),
            dict(kind="short_shipment", severity="minor", quantity=Decimal("4.0000"),
                 remedy="replacement", lot="",
                 description=("Delivery note declared the full quantity but the pallet was four "
                              "short on the count. Supplier acknowledged by phone.")),
        ]
        made = []
        for spec in discrepancy_specs:
            existing = ReceiptDiscrepancy.objects.filter(
                tenant=tenant, goods_receipt=receipt, kind=spec["kind"]).first()
            if existing is not None:
                made.append(existing)
                continue
            row = ReceiptDiscrepancy.objects.create(
                tenant=tenant, goods_receipt=receipt, goods_receipt_line=first_line,
                kind=spec["kind"], severity=spec["severity"],
                quantity_affected=spec["quantity"], remedy=spec["remedy"],
                lot_number=spec["lot"], description=spec["description"], created_by=filer)
            write_audit_log(None, row, "create")
            made.append(row)

        # Drive the SECOND claim to resolved through the real verbs rather than writing the
        # status column: notify_vendor and resolve stamp the dates, the actor and the notes
        # together, which is exactly what the detail page's timeline reads back.
        if len(made) > 1 and made[1].status == "open":
            made[1].notify_vendor(filer, reference="CLM-40218",
                                  notified_on=today - timedelta(days=6))
            made[1].resolve(filer, "replacement",
                            "Supplier shipped the balance on the next consignment; count agreed.")

        # (c) Two returns. Keyed on (tenant, vendor, supplier_rma_number) - no number is guessed.
        rtv_specs = [
            dict(rma="RMA-77341", reason="damaged", remedy="credit", authorize=True,
                 note="Crushed units off the damaged-goods claim - collected by the supplier.",
                 source=made[0] if made else None),
            dict(rma="", reason="not_to_spec", remedy="replacement", authorize=False,
                 note="Finish does not match the approved sample - awaiting the buyer sign-off.",
                 source=None),
        ]
        returns = []
        for spec in rtv_specs:
            existing = ReturnToVendor.objects.filter(
                tenant=tenant, vendor=vendor, supplier_rma_number=spec["rma"]).first()
            if existing is not None:
                returns.append(existing)
                continue
            row = ReturnToVendor.objects.create(
                tenant=tenant, vendor=vendor, purchase_order=order, goods_receipt=receipt,
                discrepancy=spec["source"], reason=spec["reason"], remedy=spec["remedy"],
                supplier_rma_number=spec["rma"],
                expected_return_date=today + timedelta(days=10),
                created_by=filer, notes=spec["note"])
            for index, line in enumerate(lines[:2]):
                ReturnToVendorLine.objects.create(
                    return_to_vendor=row, goods_receipt_line=line, po_line=line.po_line,
                    quantity_returned=Decimal("2.0000") if index == 0 else Decimal("1.0000"),
                    lot_number="LOT-2291" if index == 0 else "",
                    condition_note=("Crushed on arrival" if spec["reason"] == "damaged"
                                    else "Finish off-sample"))
            if spec["authorize"]:
                row.authorize(filer)
            write_audit_log(None, row, "create")
            returns.append(row)

        # Point the damaged-goods claim at the return it produced, so the detail page's
        # escalation panel has a live link instead of an empty slot.
        if made and returns and made[0].return_to_vendor_id is None:
            made[0].return_to_vendor = returns[0]
            made[0].save(update_fields=["return_to_vendor", "updated_at"])

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: goods receipt & inspection ready ({len(policies)} tolerance "
            f"policies, {len(made)} discrepancies, {len(returns)} returns on "
            f"{receipt.number})."))

    # -- 6.13 Invoice & Voucher Management -----------------------------------------------------

    def _seed_invoice_vouchers(self, tenant):
        """6.13 Invoice & Voucher Management - the supplier invoice register with one row in every
        lifecycle status, the three-way match exceptions that hold some of them, and the dispute
        register worked through its own verbs.

        **Every date is derived from ``NOW``** (L16). The early-payment discount dashboard computes
        "days to discount" and "still capturable" against TODAY, so a hardcoded invoice date reads
        as zero opportunities the moment the demo ages - the offsets below are what keep the
        discount panel, the payment schedule buckets and the dispute aging honest on any run.

        **Status moves through the verbs, never by writing the column.** Two consequences shape
        the code: ``run_match()`` SETS status itself (blocked / pending_approval), so it is called
        only on the rows whose verdict the engine should own; and ``approve()`` is the one
        transition that posts a Bill + a JournalEntry, so it runs only where the workspace has a
        chart of accounts to post to (tenant "SMOKETEST Acme" has none - those rows stay at
        pending_approval rather than being faked into "approved").

        Idempotent in the file's own two-part idiom: the block is guarded per tenant, and each
        numbered row is additionally keyed on ``(vendor, invoice_number_norm)`` - the natural
        business key - because ``number`` (SIV-/DSP-) is regenerated every run and a get_or_create
        on it would mint SIV-00016 on the second pass.
        """
        from apps.scm.models import GoodsReceiptNote as _GRN, PurchaseOrder as _PO

        if SupplierInvoice.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: supplier invoices already present, skipping.")
            return

        members = list(User.objects.filter(tenant=tenant, is_active=True).order_by("id"))
        filer = members[0] if members else None
        assignee = members[1] if len(members) > 1 else filer
        today = NOW.date()

        currency = Currency.objects.order_by("id").first()
        # The discount term is "2/10 Net 30": discount_days=10, discount_pct=2. Net 30 has no
        # window at all, which is just as important a row - it is what an invoice with nothing to
        # capture looks like.
        discount_term = (PaymentTerm.objects.filter(tenant=tenant, discount_days__gt=0)
                         .order_by("id").first())
        net_term = (PaymentTerm.objects.filter(tenant=tenant, discount_days=0)
                    .order_by("id").first() or discount_term)
        if discount_term is None:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no payment terms on file (run seed_accounting first) - "
                f"skipping invoice & voucher management."))
            return

        # Reuse real orders rather than inventing one: the vendor is taken FROM them, because
        # SupplierInvoice.clean() refuses an invoice whose order belongs to a different party.
        #
        # The vendor with the MOST ordered lines wins, and every invoice below draws its own line:
        # run_match() checks over-invoicing CUMULATIVELY per ordered line, so a register all
        # hanging off one line would breach that check on the second row and every later verdict
        # would read "over-invoiced" regardless of what was actually wrong.
        orders = list(_PO.objects.filter(tenant=tenant).exclude(vendor=None)
                      .prefetch_related("lines").order_by("id"))
        if not orders:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no purchase order with a vendor - skipping invoice & voucher "
                f"management."))
            return
        by_vendor = {}
        for candidate in orders:
            by_vendor.setdefault(candidate.vendor_id, []).append(candidate)
        # Prefer a vendor who has actually been RECEIPTED against: the quantity basis - invoice
        # versus what arrived - is the point of three-way matching, and a vendor with no goods
        # receipt behind it can only ever be matched two-way.
        received_orders = set(_GRN.objects.filter(tenant=tenant).exclude(purchase_order=None)
                              .values_list("purchase_order_id", flat=True))
        with_receipts = [key for key, rows in by_vendor.items()
                         if any(p.pk in received_orders for p in rows)]
        vendor_id = max(with_receipts or by_vendor,
                        key=lambda key: sum(p.lines.count() for p in by_vendor[key]))
        orders = by_vendor[vendor_id]
        order = orders[0]
        vendor = order.vendor
        pool = [line for candidate in orders for line in candidate.lines.order_by("id")]
        if not pool:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: {order.number} has no lines - skipping invoice & voucher "
                f"management."))
            return
        # pool[0] is RESERVED for the price-breach invoice: nothing else may invoice against it,
        # so its cumulative position stays inside the order and the price check is the one that
        # speaks. Everything else cycles round-robin over the remainder.
        price_line, shared_lines = pool[0], pool[1:] or pool
        # A GRN is only usable if it belongs to the same vendor (same clean() rule), and only
        # then does run_match() take the QUANTITY basis rather than the amount one.
        grn = next((row for row in _GRN.objects.filter(tenant=tenant)
                    .select_related("purchase_order").order_by("id")
                    if row.purchase_order_id in {p.pk for p in orders}), None)
        grn_line = grn.lines.order_by("id").first() if grn is not None else None

        # approve() writes a Bill and a balanced JournalEntry, and raises when either leg's
        # account cannot be resolved - so find out once, up front, rather than per row.
        expense_gl = (GLAccount.objects.filter(
            tenant=tenant, is_active=True,
            code__in=("5000", "5100", "5200", "6000", "6100")).first()
            or GLAccount.objects.filter(tenant=tenant, is_active=True, account_type="expense")
            .order_by("code").first())
        ap_gl = (GLAccount.objects.filter(
            tenant=tenant, is_active=True, code__in=("2000", "2010", "2100")).first()
            or GLAccount.objects.filter(tenant=tenant, is_active=True, account_type="liability")
            .order_by("code").first())
        postable = expense_gl is not None and ap_gl is not None
        tax_code = TaxCode.objects.filter(tenant=tenant, is_active=True).order_by("id").first()

        # (a) The register. One row per lifecycle status, plus the shapes the research plan calls
        # out: a credit memo, a debit memo, PO-less service invoices, one PDF text-layer capture
        # with a confidence score, and a duplicate pair.
        #
        # Quantities are NOT written into the spec - they are DERIVED from the ordered line, for a
        # reason that matters: ``run_match()`` checks over-invoicing CUMULATIVELY, so several
        # invoices sharing one ordered line at full quantity would breach it and mask every other
        # check with an over-invoice block. Taking a quarter of the ordered quantity keeps the
        # cumulative position inside the order and lets the intended variance surface instead.
        #
        # ``price_mult`` / ``qty_mult`` are the deliberate breaches; everything else is at 1.
        specs = [
            dict(key="draft", invoice_type="standard", days=1, discount=True, po=True, grn=False,
                 number="INV-41021", lines=[("Corrugated cartons 400x300x200", "20")]),
            dict(key="parked", invoice_type="standard", days=4, discount=True, po=True, grn=False,
                 number="INV-41022", lines=[("Stretch wrap 500mm clear", "20")]),
            dict(key="captured_pdf", invoice_type="standard", days=8, discount=True, po=True,
                 grn=True, number="INV-41023", lines=[("Corrugated cartons 400x300x200", "20")],
                 source="pdf_text_layer", confidence=Decimal("86.50")),
            dict(key="credit_memo", invoice_type="credit_memo", days=6, discount=False, po=True,
                 grn=False, number="CN-90041",
                 # NEGATIVE quantity - a credit memo's lines must not carry positive value.
                 lines=[("Credit: cartons returned crushed", "20", "negative")]),
            dict(key="debit_memo", invoice_type="debit_memo", days=7, discount=False, po=True,
                 grn=False, number="DM-90042",
                 lines=[("Recharge: pallet hire surcharge", "20")]),
            dict(key="service_1", invoice_type="service", days=3, discount=False, po=False,
                 grn=False, number="SVC-70031",
                 lines=[("Monthly forklift service call", "20", "fixed", "320.00")], gl=True),
            dict(key="service_2", invoice_type="service", days=5, discount=False, po=False,
                 grn=False, number="SVC-70032",
                 lines=[("Ad-hoc dock repair - callout", "0", "fixed", "485.00")], gl=True),
            # No GRN and no receipt line, so the match runs on the AMOUNT basis: the quantity
            # ladder is skipped entirely and the price check is the one that speaks. 30% over the
            # ordered price is far outside the 2% band.
            dict(key="blocked", invoice_type="standard", days=10, discount=False, po=True,
                 grn=False, number="INV-41024",
                 lines=[("Corrugated cartons 400x300x200", "20", "po", "1.30")]),
            # Two lines against the SAME receipt: the first is matched to what arrived, the second
            # has no receipt line at all and is 2% over the ordered quantity. The 2% is deliberate
            # - it is INSIDE the no-receipt band, so the quantity claim is recorded as a warning
            # and the check falls through to the cumulative one, which then blocks on
            # over-invoicing. One line, two different exception types, which is what an AP clerk
            # actually sees. Either way it is the open variance the dispute points at.
            dict(key="disputed", invoice_type="standard", days=12, discount=False, po=True,
                 grn=True, number="INV-41025",
                 lines=[("Corrugated cartons 400x300x200", "20"),
                        ("Stretch wrap 500mm clear", "20", "ordered", None, "1.02")]),
            dict(key="dup_original", invoice_type="standard", days=16, discount=False, po=True,
                 grn=False, number="INV-41026", lines=[("Corrugated cartons 400x300x200", "20")]),
            # Same supplier number, spaced differently - normalises to the SAME key, which is
            # exactly the collision duplicate detection exists to catch.
            dict(key="dup_suspect", invoice_type="standard", days=16, discount=False, po=True,
                 grn=False, number="INV 41026",
                 lines=[("Corrugated cartons 400x300x200", "20")]),
            dict(key="approved", invoice_type="standard", days=25, discount=True, po=True,
                 grn=False, number="INV-41027",
                 lines=[("Corrugated cartons 400x300x200", "20")]),
            dict(key="scheduled", invoice_type="standard", days=22, discount=False, po=True,
                 grn=False, number="INV-41028", lines=[("Stretch wrap 500mm clear", "20")]),
            dict(key="paid", invoice_type="standard", days=45, discount=False, po=True, grn=False,
                 number="INV-41029", lines=[("Corrugated cartons 400x300x200", "20")]),
            dict(key="void", invoice_type="standard", days=9, discount=False, po=True, grn=False,
                 number="INV-41030", lines=[("Stretch wrap 500mm clear", "20")]),
            dict(key="reversed", invoice_type="standard", days=50, discount=False, po=True,
                 grn=False, number="INV-41031",
                 lines=[("Corrugated cartons 400x300x200", "20")]),
        ]

        invoices = {}
        shared_index = 0

        def _alloc_line(reserved=None):
            """Hand out the next ordered line, round-robin, so no two invoices share one
            unless the workspace has fewer lines than the demo has rows."""
            nonlocal shared_index
            if reserved is not None:
                return reserved
            line = shared_lines[shared_index % len(shared_lines)]
            shared_index += 1
            return line

        for spec in specs:
            # Keyed on the supplier's number AS TYPED, not on invoice_number_norm: the duplicate
            # pair above is two different strings that normalise to the same key, and keying on
            # the norm would collapse them into one row and leave nothing to detect.
            existing = SupplierInvoice.objects.filter(
                tenant=tenant, vendor=vendor, invoice_number=spec["number"]).first()
            if existing is not None:
                invoices[spec["key"]] = existing
                continue
            # Allocate the ordered lines FIRST, because the header's own purchase_order has to be
            # the order those lines belong to - an invoice pointing at one order while billing
            # another's line is not a document anybody could reconcile.
            reserved = price_line if spec["key"] == "blocked" else None
            planned = []
            for line_spec in spec["lines"]:
                description, tax = line_spec[0], Decimal(line_spec[1])
                mode = line_spec[2] if len(line_spec) > 2 else "po"
                price_override = line_spec[3] if len(line_spec) > 3 else None
                qty_mult = Decimal(line_spec[4]) if len(line_spec) > 4 else Decimal("1")
                # The price-breach invoice owns its ordered line outright (see price_line above).
                line = _alloc_line(reserved)
                reserved = None
                # A receipted line has to point at the ordered line the RECEIPT was booked
                # against, or the "invoiced versus received" comparison compares two different
                # things and the quantity variance means nothing.
                if spec["grn"] and grn_line is not None and grn_line.po_line_id:
                    line = grn_line.po_line
                if mode == "fixed":
                    quantity, price = Decimal("1"), Decimal(price_override)
                else:
                    ordered = line.quantity or Decimal("1")
                    quantity = ordered if mode == "ordered" else max(
                        Decimal("1"), (ordered / 4).quantize(Decimal("0.0001")))
                    if mode == "negative":
                        quantity = -quantity
                    quantity = (quantity * qty_mult).quantize(Decimal("0.0001"))
                    price = line.unit_price or Decimal("0")
                    if price_override is not None:
                        price = (price * Decimal(price_override)).quantize(Decimal("0.01"))
                planned.append((line, description, quantity, price, tax))
            # The header's order is the order its FIRST line belongs to.
            invoice_order = (planned[0][0].purchase_order if (spec["po"] and planned)
                             else None)
            invoice = SupplierInvoice.objects.create(
                tenant=tenant, vendor=vendor,
                purchase_order=invoice_order,
                goods_receipt=grn if spec["grn"] else None,
                payment_term=discount_term if spec["discount"] else net_term,
                currency=currency, tax_code=tax_code,
                invoice_type=spec["invoice_type"],
                invoice_number=spec["number"],
                invoice_date=today - timedelta(days=spec["days"]),
                posting_date=today - timedelta(days=max(0, spec["days"] - 1)),
                source=spec.get("source", "manual"),
                extraction_confidence=spec.get("confidence"),
                notes=spec.get("notes", ""),
            )
            for index, (line, description, quantity, price, tax) in enumerate(planned):
                # sku_hint / uom_hint are MIRRORED from the ordered line: scm.PurchaseOrderLine
                # carries them as plain text (it has no item/uom FK), and the supplier's own
                # wording is what an AP clerk matches against the paper.
                SupplierInvoiceLine.objects.create(
                    invoice=invoice,
                    po_line=line if spec["po"] else None,
                    # Only the FIRST line of a receipted invoice is tied to a receipt line - the
                    # disputed invoice's second line is the one with nothing booked against it.
                    receipt_line=grn_line if (spec["grn"] and index == 0) else None,
                    gl_account=expense_gl if spec.get("gl") else None,
                    tax_code=tax_code,
                    description=description,
                    sku_hint=line.sku_hint if spec["po"] else "",
                    uom_hint=line.uom_hint if spec["po"] else "",
                    quantity=quantity, unit_price=price, tax_rate_pct=tax)
            invoice.recalc_totals()
            write_audit_log(None, invoice, "create")
            invoices[spec["key"]] = invoice

        # (b) The duplicate pair is a SUSPICION, never an auto-rejection: the link preserves the
        # evidence and leaves the decision to a person.
        suspect, original = invoices.get("dup_suspect"), invoices.get("dup_original")
        if suspect is not None and original is not None and suspect.duplicate_of_id is None:
            suspect.duplicate_of = original
            suspect.save(update_fields=["duplicate_of", "updated_at"])

        # (c) Three-way matching. run_match() OWNS the verdict - it deletes the previous run's
        # rows and writes status itself - so it is called only on the rows whose fate the engine
        # should decide: the price-breach block, the disputed invoice, and the duplicate, whose
        # suspicion is what holds it.
        for key in ("blocked", "disputed", "dup_suspect"):
            invoice = invoices.get(key)
            if invoice is not None and not invoice.is_locked:
                invoice.run_match(filer)

        # The engine never emits these two on a well-formed invoice, and both are real states an
        # AP clerk sees: a service line with no order behind it, and a claim for goods that were
        # never receipted. Recorded on rows that are never re-matched, so they survive.
        unmatched = invoices.get("service_2")
        if unmatched is not None and not unmatched.variances.exists():
            InvoiceMatchVariance.record(
                invoice=unmatched, variance_type="missing_po", basis="header",
                expected=Decimal("0.0000"), actual=unmatched.subtotal, outcome_override="block",
                message="Service invoice - no purchase order to match against.")
            InvoiceMatchVariance.record(
                invoice=unmatched, variance_type="missing_receipt", basis="header",
                expected=unmatched.subtotal, actual=Decimal("0.0000"), outcome_override="block",
                message="No goods receipt has been posted for this claim.")
        parked = invoices.get("parked")
        if parked is not None and not parked.variances.exists():
            InvoiceMatchVariance.record(
                invoice=parked, variance_type="fx_rate", basis="header",
                expected=parked.subtotal,
                actual=(parked.subtotal * Decimal("1.0185")).quantize(Decimal("0.0001")),
                pct_upper=SupplierInvoice.FX_TOL_PCT, pct_lower=SupplierInvoice.FX_TOL_PCT,
                message="Billed in the supplier's currency at a rate 1.85% off the order rate.")

        # (d) The lifecycle. Every step is a verb, each of which re-checks its own guard and
        # returns False rather than raising when the move is not open.
        def _walk(key, *verbs):
            invoice = invoices.get(key)
            if invoice is None:
                return
            for verb in verbs:
                invoice.refresh_from_db()
                if not verb(invoice):
                    break

        # park() only runs from draft - it is a SET-ASIDE, not a step past capture.
        _walk("parked", lambda i: i.park())

        # raise_dispute() needs at least one OPEN variance to point at - a dispute with nothing
        # behind it cannot be answered - so the block is forced first if the engine matched clean.
        def _dispute(invoice):
            if invoice.status != "blocked":
                invoice.block("Held pending a price check against the frame agreement.")
            return invoice.raise_dispute()

        _walk("disputed", _dispute)

        # The two PO-less service invoices and the credit/debit memos are captured but never
        # matched: a service invoice has no order to match, and a memo settles a claim rather
        # than being three-way matched.
        for key in ("credit_memo", "debit_memo", "service_1", "service_2", "dup_original"):
            _walk(key, lambda i: i.capture())
        # The PDF capture is the one sitting in the approval queue: it is complete, it matched
        # clean, and it still has a discount window running - the row the dashboard is for.
        _walk("captured_pdf", lambda i: i.capture(), lambda i: i.submit_for_approval())
        _walk("void", lambda i: i.capture(),
              lambda i: i.void(filer, "Superseded by a re-issued invoice from the supplier."))

        # approve() is the ONE transition that touches the ledger. Without a chart of accounts it
        # raises, so those rows stay at pending_approval - a workspace that cannot post cannot
        # honestly show an approved invoice.
        _walk("approved", lambda i: i.capture(), lambda i: i.submit_for_approval(),
              lambda i: i.approve(filer) if postable else False)
        _walk("scheduled", lambda i: i.capture(), lambda i: i.submit_for_approval(),
              lambda i: i.approve(filer) if postable else False, lambda i: i.schedule())
        _walk("paid", lambda i: i.capture(), lambda i: i.submit_for_approval(),
              lambda i: i.approve(filer) if postable else False, lambda i: i.schedule(),
              lambda i: i.mark_paid())
        _walk("reversed", lambda i: i.capture(), lambda i: i.submit_for_approval(),
              lambda i: i.approve(filer) if postable else False,
              lambda i: i.reverse(filer) if postable else False)

        # (e) The dispute register. Six claims across the workflow, two of them already past their
        # SLA so the aging board has something late on it.
        #
        # due_date is armed once on create (today + SLA_DAYS), so the late ones are given their
        # date explicitly - that is the only way a demo can show a breach, and it is what the
        # is_overdue property reads.
        def _dispute_row(key, invoice_key, reason, amount, description, due_in, *verbs):
            invoice = invoices.get(invoice_key)
            if invoice is None:
                return None
            # Idempotency is keyed on the BUSINESS key, not on a hand-written number. A
            # "DSP-DEMO-x" string sorts above DSP-0..., so next_number() fell into its int()
            # ValueError fallback and issued count()+1 for every user-created dispute - a number
            # that collides the moment one is deleted. TenantNumbered.save() mints DSP-00001...
            existing = InvoiceDispute.objects.filter(tenant=tenant, invoice=invoice,
                                                     reason_code=reason).first()
            if existing is not None:
                return existing
            row = InvoiceDispute.objects.create(
                tenant=tenant, invoice=invoice, reason_code=reason,
                disputed_amount=Decimal(amount), description=description,
                assigned_to=assignee, raised_by=filer,
                due_date=today + timedelta(days=due_in),
                supplier_contact="accounts@supplier.example")
            write_audit_log(None, row, "create")
            for verb in verbs:
                if not verb(row):
                    break
            return row

        aged_price = _dispute_row(
            "PRICE", "disputed", "price", "86.00",
            "Invoiced at 24.05 a roll against a frame price of 21.90. The supplier points at a "
            "resin surcharge we never accepted in writing; we are holding the difference until "
            "somebody produces the amendment.", -4)
        aged_goods = _dispute_row(
            "GOODS", "blocked", "goods_not_received", "312.00",
            "Two pallets of cartons are on the invoice but never appeared on the dock. The "
            "delivery note is signed for one pallet only and the CCTV does not show a second.",
            -2)
        _dispute_row(
            "DUP", "dup_suspect", "duplicate", "172.80",
            "Same supplier number as an invoice already on the register, spaced differently. "
            "Either the supplier re-sent it or we keyed the same document twice.", 3,
            lambda row: row.await_supplier(filer))
        aged_freight = _dispute_row(
            "FREIGHT", "service_2", "freight", "48.00",
            "Carriage charge that was never on the order and nobody approved. Supplier says it "
            "was a weekend callout; the rate card says callouts are included.", 6,
            lambda row: row.escalate(filer))
        _dispute_row(
            "CREDIT", "credit_memo", "credit_not_processed", "34.56",
            "The credit for the crushed cartons was raised six weeks ago and has never appeared "
            "on a statement. Chasing their accounts team.", 8,
            lambda row: row.await_internal(filer))
        settled = _dispute_row(
            "TAX", "dup_original", "tax", "28.80",
            "VAT charged at the standard rate on a line the supplier has since confirmed is "
            "zero-rated. They agreed to re-issue.", 1,
            lambda row: row.resolve(filer, "reinvoice",
                                   "Supplier re-issued the invoice at the correct tax rate."),
            lambda row: row.close(filer))

        # Link the settled claim to the credit memo that answered it, so the detail page's
        # settlement panel has a live link rather than an empty slot.
        if settled is not None and settled.credit_memo_invoice_id is None:
            memo = invoices.get("credit_memo")
            if memo is not None and memo.invoice_type == "credit_memo":
                settled.link_credit_memo(memo)

        # raised_at is auto_now_add, so the age bands are spread with a queryset update rather
        # than by back-dating on create - without this every open dispute lands in the 0-7 bucket
        # and the aging board has only two populated rows.
        for row, days in ((aged_price, 19), (aged_goods, 33), (aged_freight, 9)):
            if row is not None:
                InvoiceDispute.objects.filter(pk=row.pk).update(
                    raised_at=NOW - timedelta(days=days))

        variance_count = InvoiceMatchVariance.objects.filter(tenant=tenant).count()
        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: invoice & voucher management ready "
            f"({len(invoices)} invoices, {variance_count} match variances, "
            f"{InvoiceDispute.objects.filter(tenant=tenant).count()} disputes"
            f"{'' if postable else ' — no chart of accounts, so no invoice was posted'})."))

    #: Invoice numbers of the 6.14 recognised-spend baseline. The prefix is what makes the block
    #: idempotent and what tells a reader which sub-module put the row there.
    SPEND_BASELINE_PREFIX = "SPD-"

    def _seed_spend_baseline(self, tenant, categories, members):
        """Nine small recognised invoices so the 6.14 cube has a real shape. Idempotent.

        See the call site in ``_seed_spend_analytics`` for WHY these exist and why 6.13's own
        invoices are not promoted instead. Returns the number of invoices newly created.
        """
        filer = members[0] if members else None
        today = NOW.date()

        supplier_ids = list(PartyRole.objects.filter(tenant=tenant, role="supplier")
                            .values_list("party_id", flat=True))
        suppliers = list(Party.objects.filter(tenant=tenant, pk__in=supplier_ids)
                         .order_by("name")[:5])
        if not suppliers:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no supplier parties - skipping the 6.14 spend baseline."))
            return 0

        # Items carry the category the cube's passthrough leg reads (``item.category``); the rest
        # of the spend is left for the classification RULES to claim, which is what gives the
        # workbench and the coverage KPI something to actually do.
        items = list(Item.objects.filter(tenant=tenant, category__in=categories)
                     .select_related("category").order_by("id")[:6])

        currency = Currency.objects.order_by("id").first()
        tax_code = TaxCode.objects.filter(tenant=tenant, is_active=True).order_by("id").first()
        term = PaymentTerm.objects.filter(tenant=tenant, is_active=True).order_by("id").first()
        expense_gl = (GLAccount.objects.filter(
            tenant=tenant, is_active=True,
            code__in=("5000", "5100", "5200", "6000", "6100")).first()
            or GLAccount.objects.filter(tenant=tenant, is_active=True, account_type="expense")
            .order_by("code").first())
        ap_gl = (GLAccount.objects.filter(
            tenant=tenant, is_active=True, code__in=("2000", "2010", "2100")).first()
            or GLAccount.objects.filter(tenant=tenant, is_active=True, account_type="liability")
            .order_by("code").first())
        postable = expense_gl is not None and ap_gl is not None

        # (days_ago, supplier index, terminal status, [(description, qty, unit price)]).
        # Days are offsets from NOW (L16) so the window follows the demo rather than aging out of
        # it, and the amounts are deliberately small and varied: a Pareto needs a long tail, an
        # HHI below 10000 needs more than one supplier, and the A/B/C bands need a spread.
        specs = [
            (4, 0, "paid", [("Laptop dock - bulk order", "6", "148.00"),
                            ("USB-C cables", "24", "11.50")]),
            (9, 1, "paid", [("Cold-chain packaging", "40", "18.75"),
                            ("Dry ice pellets", "12", "42.00"),
                            ("Thermal liners", "18", "9.90")]),
            (16, 2, "scheduled", [("Site cleaning - monthly", "1", "860.00"),
                                  ("Consumables", "6", "37.50")]),
            (23, 0, "approved", [("Workstation monitors", "4", "215.00"),
                                 ("Monitor arms", "4", "64.00")]),
            (31, 3, "paid", [("Courier - regional", "1", "412.60"),
                             ("Fuel surcharge", "1", "38.40")]),
            (44, 1, "scheduled", [("Cold-chain packaging", "26", "18.75"),
                                  ("Temperature loggers", "8", "56.00")]),
            (57, 4, "paid", [("Office stationery", "30", "6.25"),
                             ("Printer toner", "6", "78.00")]),
            (69, 2, "approved", [("Facilities repair - HVAC", "1", "1240.00")]),
            (82, 3, "paid", [("Freight - inbound consolidation", "1", "705.20"),
                             ("Pallet handling", "14", "12.00")]),
        ]

        created = 0
        for index, (days, supplier_index, terminal, line_specs) in enumerate(specs, start=1):
            vendor = suppliers[supplier_index % len(suppliers)]
            number = f"{self.SPEND_BASELINE_PREFIX}{index:02d}"
            if SupplierInvoice.objects.filter(
                    tenant=tenant, vendor=vendor, invoice_number=number).exists():
                continue
            invoice_date = today - timedelta(days=days)
            invoice = SupplierInvoice.objects.create(
                tenant=tenant, vendor=vendor,
                payment_term=term, currency=currency, tax_code=tax_code,
                invoice_type="service",
                invoice_number=number,
                invoice_date=invoice_date,
                posting_date=invoice_date,
                source="manual",
                notes="Spend-analytics baseline: recognised spend so the 6.14 cube, Pareto and "
                      "KPI strip have a real population to describe.",
            )
            for line_index, (description, quantity, price) in enumerate(line_specs):
                item = items[(index + line_index) % len(items)] if items else None
                SupplierInvoiceLine.objects.create(
                    invoice=invoice,
                    item=item,
                    gl_account=expense_gl,
                    tax_code=tax_code,
                    description=description,
                    sku_hint=item.sku if item is not None else "",
                    quantity=Decimal(quantity), unit_price=Decimal(price))
            invoice.recalc_totals()
            write_audit_log(None, invoice, "create")

            # The lifecycle, through the verbs. approve() is the one that touches the ledger.
            invoice.capture()
            invoice.submit_for_approval()
            if postable and invoice.approve(filer):
                if terminal in ("scheduled", "paid"):
                    invoice.schedule()
                if terminal == "paid":
                    invoice.mark_paid()
            created += 1

        unposted = ("" if postable else
                    " - no chart of accounts, so they stopped at pending approval and are NOT "
                    "recognised spend")
        if created:
            self.stdout.write(
                f"  {tenant.name}: {created} baseline spend invoices across "
                f"{len(suppliers)} supplier(s){unposted}.")
        else:
            self.stdout.write(f"  {tenant.name}: spend baseline invoices already present.")
        return created

    def _seed_spend_analytics(self, tenant):
        """6.14 Spend Analytics & Reporting - classification rules, maverick findings, reports.

        Three blocks, each with its own existence guard so a partially-seeded workspace can be
        completed rather than skipped whole:

        1. **Classification rules.** One per match type over the categories, suppliers, GL
           accounts and departments the earlier blocks already created - keyed on
           ``(tenant, name)``, so a second run updates nothing and mints nothing. One rule is
           deliberately INACTIVE: a register whose every row is green never shows what the
           inactive badge looks like, and the resolver has to be seen skipping a disabled rule.
        2. **Maverick findings.** NOT hand-written. ``MaverickSpendFinding.scan()`` is run over
           the real window, which is the same code path the scan button on the board uses - so
           the demo data is whatever the detectors actually see in this workspace, and it can
           never describe spend that is not there. The scan is idempotent by construction (every
           candidate carries a deterministic ``dedupe_key`` and is upserted on it), so a second
           run refreshes rather than duplicates. A few rows are then walked through the real
           disposition verbs so the board is not a wall of "open" - guarded on there being no
           disposed row yet, so a re-run never re-decides work somebody has since re-opened.
        3. **Saved reports.** Four questions across four measures and four dimension pairs, plus
           ONE snapshot minted through ``analytics.compute_report`` - the same function the
           detail page calls - so the frozen payload is a real answer rather than a fixture.

        Nothing in this block posts to ``accounting.*`` (L29): 6.14 is a read-only analytics pass
        over spend that already exists.
        """
        from apps.procurement import analytics
        from apps.scm.models import ItemCategory

        categories = list(ItemCategory.objects.filter(tenant=tenant, is_active=True)
                          .order_by("name")[:4])
        if not categories:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no item categories (run seed_scm first) - skipping spend "
                f"analytics & reporting."))
            return

        members = list(User.objects.filter(tenant=tenant, is_active=True).order_by("id"))
        owner = members[0] if members else None

        # -- 0. recognised spend for the analytics window ------------------------------------
        #
        # Every 6.14 page reads ONE population: invoice lines whose header sits in
        # RECOGNISED_INVOICE_STATUSES (approved / scheduled / paid) inside the window. 6.13's
        # register deliberately spreads its sixteen invoices across EVERY lifecycle status, so
        # only three of them are recognised - which renders a Pareto with a single bar, an HHI of
        # 10000 and an A-band of 100%, and computes every KPI tile off three lines. Promoting
        # 6.13's rows is not the fix: their statuses are the point of that block, and moving one
        # would desync the Bill / JournalEntry it posted. These nine small invoices are additional
        # spend instead, spread across up to five suppliers, the item categories this workspace
        # actually has, and the last ninety days.
        #
        # Built through 6.13's OWN verbs (capture -> submit_for_approval -> approve -> schedule ->
        # mark_paid), never by writing ``status``: approve() is what posts the Bill and the
        # balanced JournalEntry, and an "approved" invoice with no entry behind it is a state the
        # application itself can never produce. Where the workspace has no chart of accounts the
        # row stops at pending_approval, exactly as 6.13 leaves its own - a workspace that cannot
        # post cannot honestly show approved spend.
        #
        # Idempotent on (tenant, vendor, invoice_number), the same business key 6.13 uses, because
        # ``number`` (SIV-) is regenerated on every run and a get_or_create on it would mint a new
        # row every time.
        self._seed_spend_baseline(tenant, categories, members)

        # -- 1. classification rules ---------------------------------------------------------
        if SpendClassificationRule.objects.filter(tenant=tenant).exists():
            self.stdout.write(
                f"  {tenant.name}: spend classification rules already present, skipping.")
        else:
            supplier_ids = set(PartyRole.objects.filter(
                tenant=tenant, role="supplier").values_list("party_id", flat=True))
            vendor = (Party.objects.filter(tenant=tenant, pk__in=supplier_ids)
                      .order_by("name").first())
            gl_account = (GLAccount.objects.filter(tenant=tenant, is_active=True)
                          .order_by("code").first())
            org_unit = OrgUnit.objects.filter(tenant=tenant).order_by("name").first()

            # (name, match_type, subject kwargs, category index, priority, applies_to, active,
            #  notes)
            rows = [
                ("Keyword: freight and delivery", "keyword",
                 {"keyword": "freight"}, 0, 10, "both", True,
                 "Freight lines are coded by their own description, not by the supplier - the "
                 "same carrier also sells consumables."),
                ("Keyword: service and maintenance", "keyword",
                 {"keyword": "service"}, 1 % len(categories), 20, "invoiced", True,
                 "A service invoice carries no item, so a keyword on the description is the "
                 "only attribute a rule can read on it."),
            ]
            if vendor is not None:
                rows.append((f"Supplier: {vendor.name}"[:120], "vendor",
                             {"vendor": vendor}, 2 % len(categories), 30, "both", True,
                             "A supplier who only ever sells into one category - the cheapest "
                             "rule there is, and the first one a buyer writes."))
            if gl_account is not None:
                rows.append((f"GL {gl_account.code} to {categories[0].name}"[:120], "gl_account",
                             {"gl_account": gl_account}, 0, 40, "both", True,
                             "GL coding is already a taxonomy; where finance has coded the "
                             "line, the rule simply reads it."))
            if org_unit is not None:
                rows.append((f"Department: {org_unit.name}"[:120], "org_unit",
                             {"org_unit": org_unit}, 3 % len(categories), 50, "committed", True,
                             "A committed-basis rule: a purchase order has no item and no "
                             "invoice type, so the requesting department is what it can be "
                             "classified by."))
            rows.append(("Retired: legacy stationery mapping", "keyword",
                         {"keyword": "stationery"}, 1 % len(categories), 90, "both", False,
                         "Kept, not deleted: an inactive rule is skipped by the resolver but "
                         "stays visible to the buyer auditing why last quarter classified the "
                         "way it did."))

            created = 0
            for name, match_type, subject, cat_index, priority, applies_to, active, note in rows:
                _rule, was_created = SpendClassificationRule.objects.get_or_create(
                    tenant=tenant, name=name,
                    defaults={
                        "match_type": match_type,
                        "category": categories[cat_index % len(categories)],
                        "priority": priority,
                        "applies_to": applies_to,
                        "is_active": active,
                        "notes": note,
                        **subject,
                    },
                )
                created += int(was_created)
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: {created} spend classification rules."))

        # -- 2. maverick findings ------------------------------------------------------------
        # A full year back, so the trend has months in it and the aging on the board is real.
        # The window is [start, end) with end EXCLUSIVE, exactly as every 6.14 page computes it.
        _start, end = analytics.range_bounds("year")
        start = min(_start, NOW.date() - timedelta(days=365))
        counts = MaverickSpendFinding.scan(tenant, start, end, user=None)
        raised = sum(counts.values())
        total = MaverickSpendFinding.objects.filter(tenant=tenant).count()

        # Walk a few rows through the REAL verbs so the board shows every disposition. Guarded on
        # nothing being disposed yet: a re-run must never re-decide work a person has since
        # re-opened, and the scan itself already preserves any disposition it finds.
        if total and not MaverickSpendFinding.objects.filter(
                tenant=tenant).exclude(status="open").exists():
            open_rows = list(MaverickSpendFinding.objects.filter(tenant=tenant, status="open")
                             .order_by("-amount", "id")[:5])
            verbs = [
                ("acknowledge", ""),
                ("justify", "One-off emergency buy, signed off by the category lead at the "
                            "time."),
                ("remediate", "Supplier moved onto the framework agreement; repeat spend is now "
                              "on contract."),
                ("dismiss", "Intercompany recharge - not addressable spend, so this was never "
                            "off-contract."),
                ("acknowledge", ""),
            ]
            for row, (verb, note) in zip(open_rows, verbs):
                action = getattr(row, verb)
                if verb == "acknowledge":
                    action(owner)
                else:
                    action(owner, note)

        if total:
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: {total} maverick findings ({raised} newly raised this run)."))
        else:
            self.stdout.write(
                f"  {tenant.name}: the maverick detectors found nothing in this window - every "
                f"purchase here is on contract, on catalogue and against an order.")

        # -- 3. saved reports ----------------------------------------------------------------
        if SpendReport.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: spend reports already present, skipping.")
            return

        report_rows = [
            ("Top suppliers by net spend", "invoiced", "net_spend", "supplier", "none",
             "last_90", "bar", 20, True,
             "The first question anybody asks: where did the money go, and to whom."),
            ("Category spend by department", "invoiced", "net_spend", "category", "department",
             "year", "table", 15, False,
             "Two axes: the category league, cut inside each cost centre that paid for it. The "
             "(unassigned) bucket is spend with no purchase order behind it."),
            ("Committed spend by month", "committed", "net_spend", "month", "none",
             "year", "line", 24, False,
             "The committed basis: purchase orders that are a real commitment. A draft or a "
             "cancelled order is deliberately not spend."),
            ("Maverick share by supplier", "invoiced", "maverick_pct", "supplier", "none",
             "last_90", "bar", 10, False,
             "Which suppliers we buy from around the process. Pair it with the maverick board, "
             "which carries the finding behind every figure."),
        ]
        made = 0
        for (name, basis, measure, dim1, dim2, date_range, chart, top_n,
             favorite, description) in report_rows:
            _report, was_created = SpendReport.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={
                    "description": description,
                    "basis": basis,
                    "measure": measure,
                    "dimension_1": dim1,
                    "dimension_2": dim2,
                    "date_range": date_range,
                    "chart_type": chart,
                    "top_n": top_n,
                    "is_favorite": favorite,
                    "is_shared": True,
                    "owner": owner,
                },
            )
            made += int(was_created)

        # ONE snapshot, minted through the SAME function the detail page calls, so the frozen
        # payload is a real answer rather than a fixture somebody typed. Guarded on the report
        # having none, which is what keeps a second run from stacking snapshots.
        first = SpendReport.objects.filter(tenant=tenant).order_by("id").first()
        if first is not None and not first.snapshots.exists():
            result = analytics.compute_report(first) or {}
            rows = result.get("rows") or []
            SpendReportSnapshot.objects.create(
                tenant=tenant, report=first,
                title=f"{first.name} - {NOW:%Y-%m-%d %H:%M}"[:160],
                generated_by=owner,
                summary=result.get("summary") or [],
                data={key: result.get(key) for key in
                      ("columns", "rows", "chart_type", "chart_labels", "chart_data")},
                row_count=len(rows),
            )
            SpendReport.objects.filter(pk=first.pk).update(last_run_at=NOW)

        self.stdout.write(self.style.SUCCESS(
            f"  {tenant.name}: {made} saved spend reports + 1 snapshot."))

    def _seed_budget_cost(self, tenant):
        """6.15 Budget & Cost Management - budget mappings + two frozen cost forecasts.

        REUSES seeded accounting rows (the first Budget = the seeded "FY Operating Budget",
        the first department org unit, the first project, the first expense GL account) and
        never creates accounting or core rows itself. A workspace without a budget (the
        SMOKETEST tenant) is skipped with a warning - a mapping needs something to point at.

        Idempotent twice over: the mapping block is guarded on no mappings existing yet and
        each row is a get_or_create on ``(tenant, budget, org_unit, project)``; the forecast
        block is guarded on no forecasts existing yet. The forecasts are minted THROUGH
        ``compute_forecast_amounts`` - the same pure function the create view calls - so the
        stored amounts are whatever that computation actually sees in this workspace.
        """
        budget = Budget.objects.filter(tenant=tenant).order_by("id").first()
        if budget is None:
            self.stdout.write(self.style.WARNING(
                f"  {tenant.name}: no accounting budget (run seed_accounting first) - "
                f"skipping budget & cost management."))
            return

        members = list(User.objects.filter(tenant=tenant, is_active=True).order_by("id"))
        owner = members[0] if members else None
        today = timezone.localdate()

        # -- 1. mappings ------------------------------------------------------------------------
        if BudgetMapping.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: budget mappings already present, skipping.")
        else:
            gl_account = (GLAccount.objects.filter(tenant=tenant, account_type="expense",
                                                   is_active=True)
                          .order_by("code").first())
            # DEPARTMENTS are units with a parent: the company root is where the whole tree
            # hangs from, and mapping the root as a department would hide that distinction.
            departments = list(OrgUnit.objects.filter(tenant=tenant, parent__isnull=False)
                               .order_by("id")[:2])
            department = (departments[0] if departments else
                          OrgUnit.objects.filter(tenant=tenant).order_by("id").first())
            second_department = departments[1] if len(departments) > 1 else None
            project = Project.objects.filter(tenant=tenant).order_by("id").first()

            rows = [
                # (org_unit, project, priority, is_active, notes)
                (None, None, 100, True,
                 "Workspace default - governs every department and project no more specific "
                 "mapping covers."),
                (department, None, 50, True,
                 "Department mapping - more specific than the workspace default, so this "
                 "department's spend follows this budget first."),
            ]
            if second_department is not None:
                # Deliberately INACTIVE, on its OWN department (a get_or_create key is
                # (tenant, budget, org_unit, project), so it cannot share the active row's):
                # a register whose every row is green never shows what the inactive badge
                # looks like, and resolve() has to be seen skipping a disabled row.
                rows.append((second_department, None, 40, False,
                             "Kept inactive so the register shows both states - resolve() "
                             "skips this row and falls through to the workspace default."))
            if project is not None:
                rows.append((department, project, 25, True,
                             "Project mapping - the most specific tier, so spend on this "
                             "project follows this budget even inside its department."))

            made = 0
            for org_unit, proj, priority, is_active, notes in rows:
                _obj, was_created = BudgetMapping.objects.get_or_create(
                    tenant=tenant, budget=budget, org_unit=org_unit, project=proj,
                    defaults={
                        "default_gl_account": gl_account,
                        "priority": priority,
                        "is_active": is_active,
                        "notes": notes,
                    },
                )
                made += int(was_created)
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: {made} budget mapping(s) for {budget.number}."))

        # -- 2. frozen forecasts ------------------------------------------------------------------
        if CostForecast.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"  {tenant.name}: cost forecasts already present, skipping.")
        else:
            made = 0
            # One budget-scoped run-rate projection...
            amounts = compute_forecast_amounts(tenant, budget, "run_rate", 3, today)
            CostForecast.objects.create(
                tenant=tenant, budget=budget, created_by=owner,
                name=f"{budget.name} - 3 month run rate",
                method="run_rate", horizon_months=3, as_of=today,
                committed_amount=amounts["committed"],
                historical_amount=amounts["historical"],
                forecast_amount=amounts["forecast"],
                assumptions=("Scoped by this budget's GL accounts; recognised invoices over "
                             "the three months before the as-of date, carried forward. "
                             "Seeded demo row."),
            )
            made += 1
            # ...and one workspace-wide open-PO projection.
            amounts = compute_forecast_amounts(tenant, None, "open_pos", 3, today)
            CostForecast.objects.create(
                tenant=tenant, budget=None, created_by=owner,
                name="Whole workspace - open purchase orders",
                method="open_pos", horizon_months=3, as_of=today,
                committed_amount=amounts["committed"],
                historical_amount=amounts["historical"],
                forecast_amount=amounts["forecast"],
                assumptions=("Every open purchase order approved or later, whatever its "
                             "budget. Seeded demo row."),
            )
            made += 1
            self.stdout.write(self.style.SUCCESS(
                f"  {tenant.name}: {made} frozen cost forecast(s)."))
