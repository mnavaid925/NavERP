"""HRM 3.33 Asset Management — Assetmaintenance models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class AssetMaintenance(TenantNumbered):
    """A maintenance / service / AMC / warranty-claim record for an Asset (3.33) — ``ASSETMNT-#####``.
    One type-discriminated model covers the whole Maintenance bullet; service history is just
    ``asset.maintenance_records.all()``."""

    NUMBER_PREFIX = "ASSETMNT"

    TYPE_CHOICES = [
        ("preventive", "Preventive"), ("repair", "Repair"),
        ("amc", "AMC (Annual Maintenance Contract)"), ("warranty_claim", "Warranty Claim"),
        ("inspection", "Inspection"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"), ("in_progress", "In Progress"),
        ("completed", "Completed"), ("cancelled", "Cancelled"),
    ]

    asset = models.ForeignKey("hrm.Asset", on_delete=models.CASCADE, related_name="maintenance_records")
    maintenance_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="preventive")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="scheduled")
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    vendor = models.CharField(max_length=255, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # AMC / warranty-claim contract window (blank for preventive/repair/inspection).
    contract_start = models.DateField(null=True, blank=True)
    contract_end = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "asset"], name="hrm_astmnt_tnt_asset_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_astmnt_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.asset.name} ({self.get_maintenance_type_display()})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            self._sync_asset_status()

    def _sync_asset_status(self):
        """Keep the linked Asset's status in step with a REPAIR record — the single sync point so it
        fires on create, edit, AND the mark-complete action (not just the dedicated views). An active
        repair (scheduled/in_progress) takes an in-service asset out to 'in_repair'; a completed or
        cancelled repair returns an 'in_repair' asset to service (assigned if it still has a holder,
        else in_stock). Non-repair records never change Asset.status."""
        if self.maintenance_type != "repair":
            return
        asset = self.asset
        if self.status in ("scheduled", "in_progress") and asset.status in ("in_stock", "assigned"):
            asset.status = "in_repair"
            asset.save(update_fields=["status", "updated_at"])
        elif self.status in ("completed", "cancelled") and asset.status == "in_repair":
            asset.status = "assigned" if asset.current_holder_id else "in_stock"
            asset.save(update_fields=["status", "updated_at"])
