"""Accounting 2.11 Tax — TaxReturns models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class TaxReturn(TenantNumbered):
    """A tax filing for a period — tracks taxable amount, tax due, filing and payment status."""

    NUMBER_PREFIX = "TAXR"
    STATUS_CHOICES = [("draft", "Draft"), ("filed", "Filed"), ("paid", "Paid")]

    tax_code = models.ForeignKey("accounting.TaxCode", on_delete=models.PROTECT, related_name="returns")
    period_start = models.DateField()
    period_end = models.DateField()
    taxable_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_due = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="draft")
    filed_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_taxr_tenant_status_idx")]

    def __str__(self):
        return f"{self.number} · {self.tax_code_id and self.tax_code.name}"
