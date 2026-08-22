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

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Tenant
from apps.core.utils import write_audit_log
from apps.procurement.models import (
    ProcurementAlert,
    RequisitionAmendment,
    RequisitionAmendmentLine,
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
            help=("Delete ALL procurement alert rows for ALL tenants before seeding — not just "
                  "seeder-created ones."))

    def handle(self, *args, **options):
        global NOW
        NOW = timezone.now()
        if options["flush"]:
            deleted = ProcurementAlert.objects.all().count()
            ProcurementAlert.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Flushed {deleted} procurement alerts."))

        for tenant in Tenant.objects.order_by("name"):
            self._seed_alerts(tenant)
            self._seed_templates(tenant)
            self._seed_amendment(tenant)

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

        org_unit = tenant.org_units.first() if hasattr(tenant, "org_units") else None
        created = 0
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
