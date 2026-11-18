import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CapaManagement.CapaActions import CapaAction
from apps.quality.models.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLot,
)
from apps.quality.models.IncomingQuality.IncomingInspectionPlans import (
    IncomingInspectionPlan,
)
from apps.quality.models.NonConformance.NonConformanceReports import (
    NonConformanceReport,
)
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation
from apps.quality.models.NonConformance.QuarantineContainments import (
    QuarantineContainment,
)
from apps.quality.models.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveAction,
)
from apps.scm.models.ProcurementManagement.GoodsReceiptNotes import GoodsReceiptNote
from apps.scm.models.ProcurementManagement.PurchaseOrders import PurchaseOrder

User = get_user_model()


class IncomingInspectionLotForm(TenantUniqueMixin, TenantModelForm):
    measurements_json = forms.CharField(
        required=False,
        label="Inspection Measurements (JSON)",
        help_text="Recorded CTQ readings: [{'characteristic': 'Shaft OD', 'sample_no': 1, 'value': 25.02, 'is_pass': true}]",
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-sm", "rows": 4}),
    )

    class Meta:
        model = IncomingInspectionLot
        fields = [
            "inspection_plan",
            "item_code",
            "item_name",
            "supplier",
            "purchase_order",
            "goods_receipt_note",
            "lot_number",
            "heat_or_batch",
            "receipt_date",
            "inspection_date",
            "lot_quantity",
            "sample_size",
            "inspected_quantity",
            "accepted_quantity",
            "rejected_quantity",
            "quarantine_quantity",
            "critical_defects",
            "major_defects",
            "minor_defects",
            "stage",
            "usage_decision",
            "usage_decision_notes",
            "decided_by",
            "inspector",
            "linked_ncr",
            "linked_deviation",
            "linked_containment",
            "linked_scar",
            "notes",
        ]
        widgets = {
            "inspection_plan": forms.Select(attrs={"class": "form-select"}),
            "item_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PRT-10024"}),
            "item_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Drive Shaft 25mm"}),
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "purchase_order": forms.Select(attrs={"class": "form-select"}),
            "goods_receipt_note": forms.Select(attrs={"class": "form-select"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOT-2026-0881"}),
            "heat_or_batch": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. HEAT-9941"}),
            "receipt_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "inspection_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "lot_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.001", "min": "0"}),
            "sample_size": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "inspected_quantity": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "accepted_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.001", "min": "0"}),
            "rejected_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.001", "min": "0"}),
            "quarantine_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.001", "min": "0"}),
            "critical_defects": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "major_defects": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "minor_defects": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "stage": forms.Select(attrs={"class": "form-select"}),
            "usage_decision": forms.Select(attrs={"class": "form-select"}),
            "usage_decision_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "decided_by": forms.Select(attrs={"class": "form-select"}),
            "inspector": forms.Select(attrs={"class": "form-select"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
            "linked_deviation": forms.Select(attrs={"class": "form-select"}),
            "linked_containment": forms.Select(attrs={"class": "form-select"}),
            "linked_scar": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["inspection_plan"].queryset = IncomingInspectionPlan.objects.filter(
                tenant=self.tenant
            ).order_by("number")
            self.fields["supplier"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role__in=("supplier", "vendor"),
            ).order_by("name")
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["goods_receipt_note"].queryset = GoodsReceiptNote.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["decided_by"].queryset = User.objects.filter(is_active=True).order_by("username")
            self.fields["inspector"].queryset = User.objects.filter(is_active=True).order_by("username")
            self.fields["linked_ncr"].queryset = NonConformanceReport.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_deviation"].queryset = ProcessDeviation.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_containment"].queryset = QuarantineContainment.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_scar"].queryset = SupplierCorrectiveAction.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

        if self.instance and self.instance.pk and self.instance.measurements_data:
            self.fields["measurements_json"].initial = json.dumps(
                self.instance.measurements_data, indent=2
            )

    def clean_measurements_json(self):
        raw = self.cleaned_data.get("measurements_json", "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("Measurements must be a JSON array of reading objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "inspection_plan",
                "supplier",
                "purchase_order",
                "goods_receipt_note",
                "linked_ncr",
                "linked_deviation",
                "linked_containment",
                "linked_scar",
            ],
        )

        r_date = cleaned.get("receipt_date")
        i_date = cleaned.get("inspection_date")
        if r_date and i_date and r_date > i_date:
            self.add_error("inspection_date", "Inspection date cannot precede receipt date.")

        lot_qty = cleaned.get("lot_quantity")
        acc_qty = cleaned.get("accepted_quantity")
        rej_qty = cleaned.get("rejected_quantity")
        quar_qty = cleaned.get("quarantine_quantity")

        if lot_qty is not None and lot_qty < 0:
            self.add_error("lot_quantity", "Lot quantity cannot be negative.")
        if acc_qty is not None and acc_qty < 0:
            self.add_error("accepted_quantity", "Accepted quantity cannot be negative.")
        if rej_qty is not None and rej_qty < 0:
            self.add_error("rejected_quantity", "Rejected quantity cannot be negative.")
        if quar_qty is not None and quar_qty < 0:
            self.add_error("quarantine_quantity", "Quarantined quantity cannot be negative.")

        if lot_qty is not None and acc_qty is not None and rej_qty is not None and quar_qty is not None:
            if (acc_qty + rej_qty + quar_qty) > lot_qty:
                self.add_error(
                    "accepted_quantity",
                    "Sum of accepted, rejected, and quarantined quantities cannot exceed total lot quantity.",
                )

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "measurements_json" in self.cleaned_data:
            instance.measurements_data = self.cleaned_data["measurements_json"]
            instance.recalculate_spc()
        if commit:
            instance.save()
            self.save_m2m()
        return instance
