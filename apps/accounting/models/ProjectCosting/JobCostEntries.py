"""Accounting 2.9 Project/Job Costing — JobCostEntries models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class JobCostEntry(TenantNumbered):
    """A single cost or revenue posting against a Project — posts a balanced JE (cost: Dr expense /
    Cr cash; revenue: Dr cash / Cr income)."""

    NUMBER_PREFIX = "JCE"
    KIND_CHOICES = [("cost", "Cost"), ("revenue", "Revenue")]
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    project = models.ForeignKey("accounting.Project", on_delete=models.CASCADE, related_name="cost_entries")
    entry_date = models.DateField()
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, default="cost")
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="job_cost_entries")
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="job_cost_entries", editable=False)

    class Meta:
        ordering = ["-entry_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="acc_jce_tenant_status_idx"),
            models.Index(fields=["tenant", "project"], name="acc_jce_tenant_project_idx"),
        ]

    @property
    def is_locked(self):
        return self.status == "posted"

    def __str__(self):
        return f"{self.number} · {self.get_kind_display()} {self.amount}"
