"""HRM 3.12 Holiday Management — Publicholiday models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.12 Holiday Management — PublicHoliday + HolidayPolicy + FloatingHolidayElection
# ---------------------------------------------------------------------------
class PublicHoliday(TenantOwned):
    """Tenant-scoped holiday calendar (3.12 — "Holiday Calendar" bullet). Non-optional holidays
    are excluded from ``LeaveRequest.days``; optional (floating) holidays are not — an employee
    instead elects them via ``FloatingHolidayElection``. ``category`` classifies the entry
    (national / regional / company / observance) for filtering."""

    CATEGORY_CHOICES = [
        ("national", "National"),
        ("regional", "Regional"),
        ("company", "Company"),
        ("observance", "Observance"),
    ]

    date = models.DateField()
    name = models.CharField(max_length=255)
    is_optional = models.BooleanField(default=False)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="national")

    class Meta:
        ordering = ["date"]
        unique_together = ("tenant", "date", "name")
        indexes = [
            models.Index(fields=["tenant", "date"], name="hrm_holiday_tenant_date_idx"),
        ]

    def __str__(self):
        return f"{self.date} — {self.name}"
