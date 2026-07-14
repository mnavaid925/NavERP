"""Accounting 2.12 Reporting & Compliance — ScheduledReports models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ============================================================= 2.12 Reporting & Compliance
class ScheduledReport(TenantOwned):
    """Configuration for an automated financial report (the delivery worker is deferred)."""

    REPORT_CHOICES = [
        ("balance_sheet", "Balance Sheet"),
        ("profit_and_loss", "Profit & Loss"),
        ("trial_balance", "Trial Balance"),
        ("ar_aging", "AR Aging"),
        ("ap_aging", "AP Aging"),
        ("budget_variance", "Budget Variance"),
    ]
    FREQUENCY_CHOICES = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"), ("quarterly", "Quarterly")]

    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=REPORT_CHOICES, default="balance_sheet")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="monthly")
    recipients = models.TextField(blank=True, help_text="Comma-separated email addresses")
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
