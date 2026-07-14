"""Accounting 2.6 Fixed Assets — AssetDisposals models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class AssetDisposal(TenantNumbered):
    """Retirement/sale of a FixedAsset — posts a balanced JE that removes cost + accumulated
    depreciation, records proceeds, and books the gain or loss."""

    NUMBER_PREFIX = "DISP"
    STATUS_CHOICES = [("draft", "Draft"), ("posted", "Posted")]

    asset = models.ForeignKey("accounting.FixedAsset", on_delete=models.PROTECT, related_name="disposals")
    disposal_date = models.DateField()
    proceeds = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="asset_disposals", editable=False)
    gain_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-disposal_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_disp_tenant_status_idx")]

    @property
    def is_locked(self):
        return self.status == "posted"

    def computed_gain_loss(self):
        """Proceeds minus net book value at disposal (positive = gain, negative = loss)."""
        return (self.proceeds or ZERO) - self.asset.book_value()

    def __str__(self):
        return f"{self.number} · {self.asset_id and self.asset.name}"
