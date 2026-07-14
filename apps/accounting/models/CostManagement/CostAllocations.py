"""Accounting 2.7 Inventory & Cost Management — CostAllocations models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ====================================================== 2.7 Inventory & Cost Management
class CostAllocation(TenantNumbered):
    """Distributes a cost from a source GL account to a target account/cost-centre — posts
    Dr target / Cr source. (The accounting slice of inventory/cost management; the Item master
    arrives with Inventory, Module 5.)"""

    NUMBER_PREFIX = "CALLOC"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    description = models.CharField(max_length=255)
    allocation_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    source_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="cost_alloc_source")
    target_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="cost_alloc_target")
    target_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="cost_allocations")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="cost_allocations", editable=False)

    class Meta:
        ordering = ["-allocation_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_calloc_tenant_status_idx")]

    @property
    def is_locked(self):
        return self.status == "posted"

    def __str__(self):
        return self.number
