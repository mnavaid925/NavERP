"""HRM 3.3 Employee Onboarding — Assetallocation models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class AssetAllocation(TenantNumbered):
    """A physical asset issued to a new hire (3.3) — laptop, ID card, access card, etc.
    ``returned_at`` is system-set by the return action. ``program`` is nullable so assets can be
    issued/tracked outside a formal onboarding program (and reused for offboarding returns)."""

    NUMBER_PREFIX = "AST"

    ASSET_CATEGORY_CHOICES = [
        ("laptop", "Laptop"),
        ("desktop", "Desktop"),
        ("phone", "Phone"),
        ("id_card", "ID Card"),
        ("access_card", "Access Card"),
        ("uniform", "Uniform"),
        ("vehicle", "Vehicle"),
        ("sim", "SIM Card"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("issued", "Issued"),
        ("returned", "Returned"),
        ("lost", "Lost"),
        ("damaged", "Damaged"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="asset_allocations")
    asset_name = models.CharField(max_length=255)
    asset_category = models.CharField(max_length=30, choices=ASSET_CATEGORY_CHOICES, default="other")
    serial_number = models.CharField(max_length=100, blank=True)
    asset_tag = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_assets_issued")
    returned_at = models.DateTimeField(null=True, blank=True, editable=False)
    return_due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # Optional link to the 3.33 central Asset register. When set, saving this allocation syncs the
    # asset's status/current_holder (see _sync_linked_asset). Nullable — every pre-3.33 row leaves it
    # None and behaves exactly as before.
    asset = models.ForeignKey("hrm.Asset", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="allocations")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_ast_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ast_tenant_status_idx"),
            models.Index(fields=["tenant", "program"], name="hrm_ast_tenant_prog_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.asset_name} → {self.employee}" if self.number else self.asset_name

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.asset_id:
                self._sync_linked_asset()

    def _sync_linked_asset(self):
        """Mirror this allocation's status onto the linked Asset's status/current_holder — the SINGLE
        sync point for issue (assetallocation_issue), return (assetallocation_return,
        clearanceitem_mark_cleared), a lost/damaged correction, and the 3.33 asset_assign/asset_return
        actions (they all .save() the allocation, which triggers this transparently). No-op when
        asset_id is None (every pre-3.33 row)."""
        mapping = {"issued": ("assigned", self.employee_id), "returned": ("in_stock", None),
                   "damaged": ("in_repair", None), "lost": ("retired", None)}
        if self.status not in mapping:
            return
        new_status, new_holder_id = mapping[self.status]
        asset = self.asset
        if asset.status != new_status or asset.current_holder_id != new_holder_id:
            asset.status = new_status
            asset.current_holder_id = new_holder_id
            asset.save(update_fields=["status", "current_holder", "updated_at"])
