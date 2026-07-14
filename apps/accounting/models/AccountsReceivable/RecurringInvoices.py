"""Accounting 2.4 Accounts Receivable — RecurringInvoices models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class RecurringInvoice(TenantNumbered):
    """A recurring-billing schedule [RINV-] that generates draft Invoices on a cadence (2.4).

    Each run creates a one-line ``Invoice`` for ``party`` of ``amount`` and advances
    ``next_run_date``. The generation itself (Invoice + line + status/date math) lives in the view
    inside ``transaction.atomic()`` — the model just owns the schedule and the date arithmetic."""

    NUMBER_PREFIX = "RINV"

    CADENCE_CHOICES = [
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annually", "Annually"),
    ]
    STATUS_CHOICES = [("active", "Active"), ("paused", "Paused"), ("ended", "Ended")]

    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="recurring_invoices")
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="recurring_invoices")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="recurring_invoices")
    cadence = models.CharField(max_length=10, choices=CADENCE_CHOICES, default="monthly")
    start_date = models.DateField()
    next_run_date = models.DateField(null=True, blank=True,
                                     help_text="Defaults to the start date; advances after each generated invoice.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    last_generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    occurrences_generated = models.PositiveIntegerField(default=0, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_rinv_tenant_status_idx")]

    def save(self, *args, **kwargs):
        # Default next_run_date to start_date on INSERT only — never on update, or clearing the
        # field while editing would silently rewind a schedule already mid-run (review F2).
        if self._state.adding and not self.next_run_date:
            self.next_run_date = self.start_date
        super().save(*args, **kwargs)

    def run_date_for(self, n):
        """Anchored date of the ``n``-th occurrence (0-indexed). Always re-derived from
        ``start_date`` so a month-end schedule keeps its day-of-month instead of drifting earlier
        after passing through a short month (review F3)."""
        if self.cadence == "weekly":
            return self.start_date + timedelta(days=7 * n)
        if self.cadence == "monthly":
            return add_months(self.start_date, n)
        if self.cadence == "quarterly":
            return add_months(self.start_date, 3 * n)
        return add_months(self.start_date, 12 * n)  # annually

    def advance(self):
        """Point ``next_run_date`` at the next un-generated occurrence (anchored to start_date).
        Call AFTER incrementing ``occurrences_generated``."""
        self.next_run_date = self.run_date_for(self.occurrences_generated)

    def is_due(self, on=None):
        from django.utils import timezone
        today = on or timezone.localdate()
        return self.status == "active" and self.next_run_date is not None and self.next_run_date <= today

    def __str__(self):
        return f"{self.number} · {self.description}"
