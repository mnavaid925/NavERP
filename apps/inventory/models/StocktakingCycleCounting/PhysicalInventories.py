"""Inventory 5.11 Stocktaking & Cycle Counting — PhysicalInventory.

**Full Physical Inventory** bullet: "Freezing inventory to conduct a complete warehouse
count." SCM 4.4 counts SECTIONS on demand; nothing owns the warehouse-wide EVENT — the
decision to freeze a building, spawn a count sheet for every bin under it, and hold the
freeze until every sheet reconciles. This is that event, and like every stock claim in
this codebase it posts NOTHING itself (L37): the freeze is an operational marker, the
counting stays ``scm.CycleCountTask`` work, and any correction still lands as the
spine's own reconciliation adjustment. The event's only job is orchestration and an
honest coverage figure derived from its spawned sheets.

Lifecycle (verb-driven, status editable=False)::

    draft ──start()──▶ counting(frozen) ──reconcile()──▶ reconciled(unfrozen)
       │                    │
       └────cancel()────────┴──▶ cancelled(unfrozen)

``reconcile()`` refuses while any spawned sheet is still open, so a freeze can never be
quietly dropped with bins uncounted. Every verb re-reads its row FOR UPDATE inside the
atomic block, mirroring the reservation lifecycle.
"""
import datetime

from django.conf import settings
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.inventory.models._base import *  # noqa: F401,F403


class PhysicalInventory(TenantNumbered):
    """A warehouse-wide count freeze [PHY-] orchestrating spine CycleCountTasks."""

    NUMBER_PREFIX = "PHY"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("counting", "Counting"),
        ("reconciled", "Reconciled"),
        ("cancelled", "Cancelled"),
    ]
    #: Statuses start() accepts; reconcile()/cancel() guard their own sources below.
    EDITABLE_STATUSES = ("draft",)

    STATUS_CSS = {
        "draft": "badge-muted",
        "counting": "badge-amber",
        "reconciled": "badge-green",
        "cancelled": "badge-slate",
    }

    warehouse = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="physical_inventories",
        help_text="The warehouse being frozen for a full count")
    scheduled_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft",
                              editable=False)
    # The freeze marker: advisory to operations (nothing auto-blocks a move), but the
    # board surfaces it and reconcile() refuses to close while sheets remain open.
    is_frozen = models.BooleanField(default=False, editable=False)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_physical_inventories")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_phy_tnt_status_idx"),
            # The default ordering is -scheduled_date: without this every paginated
            # list render filesorts the tenant's rows.
            models.Index(fields=["tenant", "-scheduled_date"],
                         name="inv_phy_tnt_sched_idx"),
        ]

    # -- provenance -----------------------------------------------------------------------------

    def task_marker(self):
        """The CycleCountTask.notes stamp linking spawned sheets back to this event.

        One canonical builder — every writer and every string-matching consumer goes
        through this, so the stamp can't drift. The ``#pk`` component is what makes a
        re-issued number safe: after a flush re-seed PHY numbering restarts while sheets
        minted by the previous row generation may still live in SCM, and a number-only
        stamp would let the new event adopt (and report) those stale sheets.
        """
        return f"Physical inventory {self.number} #{self.pk}"

    def spawned_tasks(self):
        from apps.scm.models import CycleCountTask

        # notes is an unindexed TextField on the spine, so a bare left-anchored
        # prefix match full-scans the tenant's sheets on every detail render / verb.
        # start() mints every sheet with scheduled_date == the day it ran — recorded
        # as started_at — so bounding the scan to that day (±1 for a midnight
        # crossing) lets the spine's own indexed (tenant, scheduled_date) pair narrow
        # the candidate rows first. Draft events (started_at None) own no sheets yet,
        # so they stay unbounded without harm. No scm schema change needed.
        qs = CycleCountTask.objects.filter(
            tenant_id=self.tenant_id,
            notes__startswith=self.task_marker())
        if self.started_at:
            day = timezone.localdate(self.started_at)
            qs = qs.filter(scheduled_date__gte=day - datetime.timedelta(days=1),
                           scheduled_date__lte=day + datetime.timedelta(days=1))
        return qs

    @property
    def coverage(self):
        """(reconciled, total) over the spawned sheets — None when none were spawned."""
        total = self.spawned_tasks().count()
        if not total:
            return None
        done = self.spawned_tasks().filter(status="reconciled").count()
        return done, total

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    # -- actions ----------------------------------------------------------------------------------

    def _locked(self):
        return type(self).objects.select_for_update().get(pk=self.pk)

    def _bin_locations(self):
        """Every bin/zone under the frozen warehouse — one sheet each."""
        from apps.scm.models import Location

        return list(Location.objects.filter(
            tenant_id=self.tenant_id,
            location_type__in=("bin", "zone"),
            parent__isnull=False).exclude(pk=self.warehouse_id)
            .filter(Q(parent=self.warehouse_id) |
                    Q(parent__parent=self.warehouse_id) |
                    Q(parent__parent__parent=self.warehouse_id))
            .order_by("code"))

    def start(self, user):
        """Freeze the warehouse and spawn one full-count sheet per bin/zone."""
        from apps.scm.models import CycleCountTask

        with transaction.atomic():
            obj = self._locked()
            if obj.status != "draft":
                raise ValidationError(
                    f"{obj.number} is {obj.get_status_display().lower()} and cannot be started.")
            today = timezone.localdate()
            marker = obj.task_marker()
            covered = set(obj.spawned_tasks()
                          .values_list("location_id", flat=True))
            pending = [loc for loc in obj._bin_locations() if loc.pk not in covered]
            # One numbered INSERT beats one-per-bin: a per-sheet create() runs
            # next_number's max+1 SELECT inside this lock-holding transaction —
            # thousands of serialized round trips on a wall-to-wall count. Read the
            # tenant's highest CC number ONCE, pre-assign locally, insert all sheets
            # in a single statement (same left-anchored max probe next_number uses).
            last = (CycleCountTask.objects
                    .filter(tenant_id=obj.tenant_id, number__startswith="CC-")
                    .order_by("-number").first())
            seq = int(last.number.split("-")[-1]) + 1 if last else 1
            CycleCountTask.objects.bulk_create([
                CycleCountTask(
                    tenant_id=obj.tenant_id, location=loc,
                    number=f"CC-{seq + offset:05d}", scheduled_date=today,
                    count_method="full", notes=marker)
                for offset, loc in enumerate(pending)])
            made = len(pending)
            obj.status = "counting"
            obj.is_frozen = True
            obj.started_at = timezone.now()
            obj.save(update_fields=["status", "is_frozen", "started_at", "updated_at"])
            write_audit_log(user, obj, "start", {"sheets_spawned": made})
        return obj

    def reconcile(self, user):
        """Close the event and lift the freeze — refused while sheets are still open."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status != "counting":
                raise ValidationError(
                    f"{obj.number} is {obj.get_status_display().lower()} — only a counting "
                    "event can be reconciled.")
            open_sheets = obj.spawned_tasks().exclude(status__in=("reconciled", "cancelled"))
            open_count = open_sheets.count()
            if open_count:
                sample = ", ".join(open_sheets.order_by("number")
                                   .values_list("number", flat=True)[:3])
                raise ValidationError(
                    f"{open_count} count sheet(s) still open ({sample}"
                    f"{'…' if open_count > 3 else ''}) — reconcile or cancel them in "
                    "SCM first; lifting the freeze now would hide uncounted bins.")
            obj.status = "reconciled"
            obj.is_frozen = False
            obj.closed_at = timezone.now()
            obj.save(update_fields=["status", "is_frozen", "closed_at", "updated_at"])
            write_audit_log(user, obj, "reconcile")
        return obj

    def cancel(self, user):
        with transaction.atomic():
            obj = self._locked()
            if obj.status not in ("draft", "counting"):
                raise ValidationError(
                    f"{obj.number} is already {obj.get_status_display().lower()}.")
            was_frozen = obj.is_frozen
            obj.status = "cancelled"
            obj.is_frozen = False
            obj.closed_at = timezone.now()
            obj.save(update_fields=["status", "is_frozen", "closed_at", "updated_at"])
            write_audit_log(user, obj, "cancel", {"lifted_freeze": was_frozen})
        return obj

    def clean(self):
        super().clean()
        if self.warehouse_id and self.warehouse.tenant_id != self.tenant_id:
            raise ValidationError({"warehouse": "That location belongs to another workspace."})

    def __str__(self):
        wh = self.warehouse.code if self.warehouse_id else "?"
        return f"{self.number or 'PHY'} · {wh}"
