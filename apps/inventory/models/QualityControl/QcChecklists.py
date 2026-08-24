"""Inventory 5.15 Quality Control (QC) & Inspection — QcChecklist + QcChecklistItem.

**OWNERSHIP (L36/L29):** SCM 4.9 owns the quality-engineering layer — ``scm.InspectionPlan``
with its measurement characteristics, limits and CoA flags, and the ``scm.QualityInspection``
execution record judged against a snapshotted plan. What 5.15 adds is the WAREHOUSE-FLOOR
gate: "which checks must the dock operator tick before goods from this vendor / for this
product are accepted into stock?" — an operational checklist, not a metrology plan.

A checklist pins to a product (``item``) OR a vendor (``vendor`` party role) OR neither
(tenant-wide default), exactly the three scopes the bullet names. The checkpoints are child
rows edited inline on the checklist form (the 5.10 ``ReturnInspectionChecklistFormSet``
pattern): one object with a ``kind`` covers visual/functional/documentation/quantity
checkpoints and plain instructions, because splitting them would fork CRUD to express one
choice field's worth of difference (5.1 ProductFile ruling).

No stock effect anywhere: a checklist defines what must be checked, never what happened to
the goods — that is :class:`~apps.inventory.models.QualityControl.QuarantineOrder`'s job.
"""
from django.core.exceptions import ValidationError

from apps.inventory.models._base import *  # noqa: F401,F403


class QcChecklist(TenantOwned):
    """The mandatory pre-acceptance checks for one product, vendor or the whole workspace."""

    name = models.CharField(max_length=100, help_text="e.g. 'Electronics dock inspection', 'ACME incoming check'")
    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_qc_checklists",
        help_text="Pin to one product — blank for category-wide/vendor-wide/workspace-wide use")
    vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_qc_checklists",
        help_text="Pin to one supplier — receipts from them run this checklist")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="inv_qcc_tnt_act_idx"),
            models.Index(fields=["tenant", "item"], name="inv_qcc_tnt_item_idx"),
            models.Index(fields=["tenant", "vendor"], name="inv_qcc_tnt_vendor_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def applies_to(self):
        """Human scope line for lists and detail headers."""
        if self.item_id and self.vendor_id:
            return f"{self.item.sku} · from {self.vendor.name}"
        if self.item_id:
            return f"SKU {self.item.sku}"
        if self.vendor_id:
            return f"Vendor: {self.vendor.name}"
        return "Workspace-wide"

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})
        if self.vendor_id and getattr(self.vendor, "tenant_id", None) != tenant_id:
            raise ValidationError({"vendor": "That vendor belongs to another workspace."})


class QcChecklistItem(TenantOwned):
    """One checkpoint on a checklist — 'what the operator ticks', in execution order."""

    KIND_CHOICES = [
        ("visual", "Visual Check"),
        ("functional", "Functional Test"),
        ("documentation", "Documentation / Labels"),
        ("quantity", "Quantity Verification"),
        ("instruction", "Instruction (no verdict)"),
    ]

    checklist = models.ForeignKey(
        QcChecklist, on_delete=models.CASCADE, related_name="checklist_items")
    label = models.CharField(max_length=255, help_text="e.g. 'Carton seal intact', 'Power-on test'")
    kind = models.CharField(max_length=13, choices=KIND_CHOICES, default="visual")
    expected_result = models.CharField(
        max_length=120, blank=True,
        help_text="What 'pass' looks like, e.g. 'Seal unbroken' — informational")
    is_mandatory = models.BooleanField(
        default=True,
        help_text="A failed mandatory checkpoint blocks acceptance; advisory ones only warn")
    sequence = models.PositiveIntegerField(default=10, help_text="Execution order — lower runs first")

    class Meta:
        ordering = ["checklist_id", "sequence", "id"]
        indexes = [models.Index(fields=["tenant", "checklist"], name="inv_qci_tnt_chk_idx")]

    def __str__(self):
        return f"{self.checklist_id and self.checklist.name} · {self.label}"
