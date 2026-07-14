"""Accounting 2.2 General Ledger — FiscalPeriods models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class FiscalPeriod(TenantOwned):
    """An accounting period. Posting is blocked once it is anything other than ``open``."""

    PERIOD_TYPE_CHOICES = [("month", "Month"), ("quarter", "Quarter"), ("year", "Year")]
    STATUS_CHOICES = [("open", "Open"), ("closed", "Closed"), ("locked", "Locked")]

    name = models.CharField(max_length=60)
    period_type = models.CharField(max_length=10, choices=PERIOD_TYPE_CHOICES, default="month")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="accounting_periods_closed", editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["tenant", "status"], name="acc_period_tenant_status_idx")]

    @property
    def is_open(self):
        return self.status == "open"

    def __str__(self):
        return self.name
