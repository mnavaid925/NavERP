from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLot,
)
from apps.quality.models.IncomingQuality.QualityReturnAuthorizations import (
    QualityReturnAuthorization,
)
from apps.quality.models.NonConformance.NonConformanceReports import (
    NonConformanceReport,
)
from apps.quality.models.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveAction,
)

User = get_user_model()


class QualityReturnAuthorizationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = QualityReturnAuthorization
        fields = [
            "inspection_lot",
            "supplier",
            "vendor_rma_number",
            "return_reason",
            "disposition_type",
            "return_quantity",
            "unit_of_measure",
            "estimated_credit_value",
            "status",
            "carrier",
            "tracking_number",
            "bill_of_lading",
            "shipped_date",
            "vendor_receipt_date",
            "debit_memo_number",
            "settled_amount",
            "settlement_date",
            "assigned_coordinator",
            "linked_ncr",
            "linked_scar",
            "notes",
        ]
        widgets = {
            "inspection_lot": forms.Select(attrs={"class": "form-select"}),
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "vendor_rma_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. VRMA-2026-1188"}),
            "return_reason": forms.Select(attrs={"class": "form-select"}),
            "disposition_type": forms.Select(attrs={"class": "form-select"}),
            "return_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.001", "min": "0"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EA, KG"}),
            "estimated_credit_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "carrier": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FedEx Freight / DHL"}),
            "tracking_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 7849 2011 8841"}),
            "bill_of_lading": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. BOL-99410"}),
            "shipped_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "vendor_receipt_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "debit_memo_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. DM-2026-041"}),
            "settled_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "settlement_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "assigned_coordinator": forms.Select(attrs={"class": "form-select"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
            "linked_scar": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["inspection_lot"].queryset = IncomingInspectionLot.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["supplier"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role__in=("supplier", "vendor"),
            ).order_by("name")
            self.fields["assigned_coordinator"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("username")
            self.fields["linked_ncr"].queryset = NonConformanceReport.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_scar"].queryset = SupplierCorrectiveAction.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["inspection_lot", "supplier", "assigned_coordinator", "linked_ncr", "linked_scar"],
        )

        ret_qty = cleaned.get("return_quantity")
        if ret_qty is not None and ret_qty < 0:
            self.add_error("return_quantity", "Return quantity cannot be negative.")

        est_cred = cleaned.get("estimated_credit_value")
        if est_cred is not None and est_cred < 0:
            self.add_error("estimated_credit_value", "Estimated credit value cannot be negative.")

        settled = cleaned.get("settled_amount")
        if settled is not None and settled < 0:
            self.add_error("settled_amount", "Settled amount cannot be negative.")

        s_date = cleaned.get("shipped_date")
        vr_date = cleaned.get("vendor_receipt_date")
        if s_date and vr_date and s_date > vr_date:
            self.add_error("vendor_receipt_date", "Vendor receipt date cannot precede shipped date.")

        st_date = cleaned.get("settlement_date")
        if s_date and st_date and s_date > st_date:
            self.add_error("settlement_date", "Settlement date cannot precede shipped date.")

        return cleaned
