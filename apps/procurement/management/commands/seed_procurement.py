"""Seed Procurement Management (Module 6) demo data — 6.1 portal baseline + 6.2 Requisition
Management.

6.1 creates, per tenant, the Task & Alert Center baseline: a handful of alerts across every kind,
severity and lifecycle state, assigned to the workspace's members. The overview's other widgets
are COMPUTED over data that already exists (``scm.PurchaseRequisition`` / ``scm.PurchaseOrder``
per L36, ``core.AuditLog`` for the feed), so this command deliberately creates no requisitions —
run ``seed_scm`` first if you want the approval/spend widgets populated.

6.2 adds the management layer around those same spine requisitions: recurring-order TEMPLATES
(with lines) ready to apply, and — when ``seed_scm`` has left at least one pending/approved
requisition to work with — one PENDING AMENDMENT so the decision queue is not empty. Both blocks
reuse existing rows rather than inventing parallel ones.

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

from apps.core.models import OrgUnit, Tenant
from apps.core.utils import write_audit_log
from apps.procurement.models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    EscalationPolicy,
    ProcurementAlert,
    RequisitionAmendment,
    RequisitionAmendmentLine,
    RequisitionApproval,
    RequisitionTemplate,
    RequisitionTemplateLine,
)
from apps.scm.models import PurchaseRequisition

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
            "templates and a pending amendment) — idempotent (skips a tenant that already has "
            "rows for each block).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true",
            help=("Delete ALL procurement workflow rows for ALL tenants before seeding "
                  "(alerts, approval-engine tables, templates, amendments) - not just "
                  "seeder-created ones."))

    def handle(self, *args, **options):
        global NOW
        NOW = timezone.now()
        if options["flush"]:
            deleted = ProcurementAlert.objects.all().count()
            # Children first: signatures reference their DOA grant (SET_NULL, but cleanest
            # in order), grants/rules/policy are standalone config.
            RequisitionApproval.objects.all().delete()
            ApprovalDelegation.objects.all().delete()
            ApprovalRoutingRule.objects.all().delete()
            EscalationPolicy.objects.all().delete()
            ProcurementAlert.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Flushed {deleted} procurement alerts."))

        for tenant in Tenant.objects.order_by("name"):
            self._seed_alerts(tenant)
            self._seed_templates(tenant)
            self._seed_amendment(tenant)
            self._seed_approval_engine(tenant)

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
