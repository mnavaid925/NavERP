"""Seed Procurement Management (Module 6) demo data — 6.1 User Dashboard & Portal.

Creates, per tenant, the Task & Alert Center baseline: a handful of alerts across every kind,
severity and lifecycle state, assigned to the workspace's members. The overview's other widgets
are COMPUTED over data that already exists (``scm.PurchaseRequisition`` / ``scm.PurchaseOrder``
per L36, ``core.AuditLog`` for the feed), so this command deliberately creates no requisitions —
run ``seed_scm`` first if you want the approval/spend widgets populated.

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
from apps.procurement.models import ProcurementAlert

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
    help = ("Seed Procurement 6.1 User Dashboard & Portal demo data (Task & Alert Center "
            "baseline) — idempotent (skips a tenant that already has alerts).")

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
