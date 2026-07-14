"""Accounting 2.10 Multi-Entity & Consolidation — IntercompanyTransactions models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ===================================================== 2.10 Multi-Entity & Consolidation
class IntercompanyTransaction(TenantNumbered):
    """A due-to/due-from movement between two ``OrgUnit`` entities — posts Dr due-from (lender) /
    Cr due-to (borrower). ``eliminated`` flags it for the consolidation report."""

    NUMBER_PREFIX = "ICT"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    description = models.CharField(max_length=255)
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    from_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.PROTECT, related_name="ic_transactions_from")
    to_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.PROTECT, related_name="ic_transactions_to")
    due_from_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="ic_due_from")
    due_to_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="ic_due_to")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    eliminated = models.BooleanField(default=False)
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="ic_transactions", editable=False)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="acc_ict_tenant_status_idx"),
            models.Index(fields=["tenant", "eliminated"], name="acc_ict_tenant_elim_idx"),
        ]

    @property
    def is_locked(self):
        return self.status == "posted"

    def __str__(self):
        return self.number
