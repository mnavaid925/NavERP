"""Inventory 5.11 Stocktaking & Cycle Counting — CountProgram.

**Cycle Count Scheduling** bullet: "Automating daily/weekly counts of specific zones or
ABC-classified items." SCM 4.4 owns the count EXECUTION — ``scm.CycleCountTask`` snapshots
expected quantities server-side, hides them from the counter (blind), and reconciles into
exactly one ``scm.StockAdjustment`` (L36: never re-declare any of that). What the spine
lacks is the recurring CALENDAR that decides "the A-class bins in Zone A get counted
every Monday": this is it. A program is due on its cadence; the generate action mints the
spine task(s) for its scope and stamps provenance into ``notes`` ("Via count program
CTP-#####") so duplicates are detectable and history stays attributable.

Provenance by notes marker rather than an FK is deliberate: adding a column to the spine
for a scheduling nicety would couple 4.4's migrations to Module 5's cadence changes.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class CountProgram(TenantNumbered):
    """A recurring cycle-count schedule [CTP-] minting spine CycleCountTasks."""

    NUMBER_PREFIX = "CTP"

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]
    #: 0 = Monday … 6 = Sunday (Python's weekday()).
    WEEKDAY_CHOICES = [
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
        (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
    ]
    ABC_CHOICES = [
        ("", "Any class"),
        ("a", "A only"),
        ("b", "B only"),
        ("c", "C only"),
    ]

    name = models.CharField(max_length=64)
    # The section this program counts. Null = whole-warehouse scope (tasks then land on
    # the location itself; a zone/bin scope lands there directly).
    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, null=True, blank=True,
        related_name="count_programs",
        help_text="The zone/bin/warehouse section counted on this cadence")
    abc_class = models.CharField(max_length=1, choices=ABC_CHOICES, blank=True,
                                 help_text="Restrict to one ABC class, or any")
    frequency = models.CharField(max_length=8, choices=FREQUENCY_CHOICES, default="weekly")
    weekday = models.PositiveSmallIntegerField(null=True, blank=True, choices=WEEKDAY_CHOICES,
                                               help_text="Weekly: which day (0=Monday)")
    day_of_month = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Monthly: which day (1-28; months without it roll up to the 28th)")
    count_method = models.CharField(
        max_length=8, choices=[("zone", "Zone"), ("abc", "ABC Class"), ("full", "Full Count")],
        default="zone")
    is_active = models.BooleanField(default=True)
    last_run_date = models.DateField(null=True, blank=True, editable=False)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="inv_ctp_tnt_active_idx")]

    # -- cadence --------------------------------------------------------------------------------

    def is_due(self, today=None):
        """Whether this program should mint tasks on ``today`` given its last run."""
        from django.utils import timezone

        today = today or timezone.localdate()
        if not self.is_active:
            return False
        if self.last_run_date == today:
            return False
        if self.frequency == "daily":
            return True
        if self.frequency == "weekly":
            return self.weekday is not None and today.weekday() == self.weekday
        return self.day_of_month is not None and min(today.day, 28) == self.day_of_month

    def generate_tasks(self, user, today=None):
        """Mint today's spine CycleCountTask for the program's scope and stamp the run.

        One task per run (the scope lives on the task's location + method). Duplicate
        protection: the same (tenant, location, scheduled_date) open task with this
        program's marker is reused instead of minted twice. The whole run is one
        transaction with the program row re-read FOR UPDATE (mirroring
        ``PhysicalInventory._locked``), so two near-simultaneous Run POSTs serialise:
        the second sees the first's sheet through the prefix probe instead of minting
        its own.
        """
        from apps.core.utils import write_audit_log
        from apps.scm.models import CycleCountTask

        if self.location_id is None:
            raise ValidationError(
                "This program has no counting scope — set its location first.")
        today = today or timezone.localdate()

        with transaction.atomic():
            program = type(self).objects.select_for_update().get(pk=self.pk)
            marker = f"Via count program {program.number}"
            existing = (CycleCountTask.objects
                        .filter(tenant_id=program.tenant_id, location=program.location,
                                scheduled_date=today, notes__startswith=marker)
                        .exclude(status__in=("cancelled",)).first())
            if existing is not None:
                task = existing
                created = False
            else:
                task = CycleCountTask.objects.create(
                    tenant_id=program.tenant_id, location=program.location,
                    scheduled_date=today, count_method=program.count_method,
                    notes=f"{marker} · {program.name}")
                created = True
            program.last_run_date = today
            program.save(update_fields=["last_run_date", "updated_at"])
            write_audit_log(user, program, "run" if created else "rerun",
                            {"task": task.number})
        self.last_run_date = program.last_run_date  # keep the caller's instance honest
        return task, created

    @property
    def cadence_label(self):
        if self.frequency == "daily":
            return "Every day"
        if self.frequency == "weekly":
            label = dict(self.WEEKDAY_CHOICES).get(self.weekday, "?")
            return f"Every {label}"
        return f"On day {self.day_of_month} monthly"

    def clean(self):
        super().clean()
        if self.location_id and self.location.tenant_id != self.tenant_id:
            raise ValidationError({"location": "That location belongs to another workspace."})
        if self.frequency == "weekly" and self.weekday is None:
            raise ValidationError({"weekday": "Weekly programs need a day of week."})
        if self.frequency == "monthly" and self.day_of_month is None:
            raise ValidationError({"day_of_month": "Monthly programs need a day of month."})

    def __str__(self):
        return f"{self.number or 'CTP'} · {self.name}"
