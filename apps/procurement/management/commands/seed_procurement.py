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
    ApprovalDelegation,
    ApprovalRoutingRule,
    BidScore,
    EaucBid,
    EaucInvite,
    Eauction,
    EscalationPolicy,
    EventCriterion,
    ProcurementAlert,
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
from apps.scm.models import PurchaseRequisition, SupplierProfile

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
            "6.5 sourcing events) — idempotent (skips a tenant that already has rows for each "
            "block).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help=("Delete ALL procurement workflow rows for ALL tenants before seeding "
                  "(alerts, approval-engine tables, templates, amendments, vendor-management "
                  "registers, sourcing events) - not just seeder-created ones."))

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
            VendorPortalAccess.objects.all().delete()
            VendorSuspension.objects.all().delete()
            VendorInvoiceSubmission.objects.all().delete()
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
                closes_at=NOW + timedelta(hours=2),
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

        today = timezone.localdate()
        made = 0
        with transaction.atomic():
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
                signer_name=(admin_user.get_full_name() or admin_user.username),
                signer_email=admin_user.email or "admin@example.com", order=1)
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
