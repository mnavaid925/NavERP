"""Inventory 5.10 Returns Management — ReturnInspection and checklist forms."""
from django import forms
from django.forms import inlineformset_factory

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models import ReturnInspection, ReturnInspectionChecklist
from apps.scm.models import Item, LotSerial, ReturnAuthorization, ReturnDisposition, ReturnLine


class ReturnInspectionForm(TenantUniqueMixin, TenantModelForm):
    """Form for logging a warehouse physical return inspection [RMI-]."""

    class Meta:
        model = ReturnInspection
        fields = [
            "return_authorization",
            "return_line",
            "return_disposition",
            "item",
            "quantity",
            "lot_serial",
            "inspected_by",
            "inspected_at",
            "packaging_condition",
            "completeness",
            "functional_status",
            "cosmetic_condition",
            "condition_grade",
            "serial_verified",
            "is_restock_eligible",
            "suggested_restock_fee_pct",
            "findings",
            "status",
        ]
        widgets = {
            "inspected_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "findings": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["return_authorization"].queryset = (
                ReturnAuthorization.objects.filter(tenant=self.tenant)
                .select_related("customer")
                .order_by("-id")
            )
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["return_line"].queryset = (
                ReturnLine.objects.filter(return_authorization__tenant=self.tenant)
                .select_related("return_authorization", "item")
                .order_by("-id")
            )
            self.fields["return_disposition"].queryset = (
                ReturnDisposition.objects.filter(tenant=self.tenant)
                .select_related("return_line__return_authorization", "return_line__item")
                .order_by("-id")
            )
            self.fields["lot_serial"].queryset = (
                LotSerial.objects.filter(tenant=self.tenant).order_by("number")
            )

    def clean(self):
        cleaned = super().clean()
        # ``scm.ReturnLine`` is tenant-less on the spine — its queryset is already scoped via
        # ``return_authorization__tenant``, and the guard below rides the parent authorization.
        _reject_foreign(
            self,
            cleaned,
            [
                "return_authorization",
                "return_disposition",
                "item",
                "lot_serial",
                "inspected_by",
            ],
        )

        line = cleaned.get("return_line")
        if line is not None:
            line_rma_tenant = getattr(line.return_authorization, "tenant_id", None)
            if self.tenant is not None and line_rma_tenant != self.tenant.pk:
                self.add_error("return_line", "That record belongs to another workspace.")

        # Integrity checks: return_line must match return_authorization if both set
        rma = cleaned.get("return_authorization")
        item = cleaned.get("item")
        if rma and line and line.return_authorization_id != rma.id:
            self.add_error("return_line", "The selected return line does not belong to the selected RMA.")
        if line and item and line.item_id != item.id:
            self.add_error("item", "The selected item SKU does not match the item on the return line.")

        return cleaned


class ReturnInspectionChecklistForm(TenantUniqueMixin, TenantModelForm):
    """Form for an individual checkpoint on a return inspection."""

    class Meta:
        model = ReturnInspectionChecklist
        fields = ["checkpoint", "result", "notes"]
        widgets = {
            "checkpoint": forms.TextInput(attrs={"placeholder": "e.g. Power-on test, Accessories present"}),
            "notes": forms.TextInput(attrs={"placeholder": "Notes or defect details"}),
        }


ReturnInspectionChecklistFormSet = inlineformset_factory(
    ReturnInspection,
    ReturnInspectionChecklist,
    form=ReturnInspectionChecklistForm,
    extra=3,
    can_delete=True,
)
