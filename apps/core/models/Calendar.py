"""core — 0.10 bullet 4: Business Calendar & Fiscal Periods.

The calendar and its holidays are new. **Fiscal periods are NOT** — `accounting.FiscalPeriod` (2.x)
already owns them, including the close controls, and re-declaring a period table here would split the
ledger's own calendar from the business one (L36). This sub-module owns the WORKING-DAY calendar and
POINTS at the accounting periods; the page links out rather than duplicating.
"""
from apps.core.models._base import *  # noqa: F401,F403


class BusinessCalendar(models.Model):
    """The workspace's working week, used by anything that counts days rather than dates."""

    #: ISO weekday numbers (1 = Monday … 7 = Sunday), as a JSON list. A list rather than seven
    #: booleans because a working week is a set, and `[1,2,3,4,5]` is readable in the DB.
    working_days = models.JSONField(default=list, blank=True)
    timezone_name = models.CharField(max_length=64, blank=True,
                                     help_text="IANA name, e.g. 'Europe/London'.")
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE,
                                  related_name="business_calendar", db_index=True)

    class Meta:
        ordering = ["tenant__name"]

    @property
    def working_day_count(self):
        return len(self.working_days or [])

    def is_working_day(self, day):
        """True when `day` (a date) falls on a configured working day AND is not a holiday."""
        if day.isoweekday() not in (self.working_days or []):
            return False
        return not self.tenant.holidays.filter(date=day).exists()

    def __str__(self):
        return f"Calendar · {self.tenant}"


class Holiday(models.Model):
    """A non-working day. `is_recurring` covers fixed-date holidays without a row per year."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="holidays", db_index=True)
    name = models.CharField(max_length=150)
    date = models.DateField()
    is_recurring = models.BooleanField(
        default=False, help_text="Repeats on the same month/day every year (e.g. New Year's Day).")
    region = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        unique_together = ("tenant", "date", "name")
        indexes = [models.Index(fields=["tenant", "date"], name="holiday_tenant_date_idx")]

    def __str__(self):
        return f"{self.date} · {self.name}"
