from django import forms

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.models.AssetLeaseRental.AssetLeaseSchedules import AssetLeaseSchedule


class AssetLeaseScheduleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetLeaseSchedule
        fields = [
            "lease_contract",
            "period_number",
            "due_date",
            "payment_amount",
            "beginning_liability",
            "interest_expense",
            "principal_reduction",
            "ending_liability",
            "rou_depreciation",
            "ending_rou_asset_value",
            "status",
            "payment_reference",
            "paid_date",
            "notes",
        ]
        widgets = {
            "lease_contract": forms.Select(attrs={"class": "form-select"}),
            "period_number": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "payment_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "beginning_liability": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "interest_expense": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "principal_reduction": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "ending_liability": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "rou_depreciation": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "ending_rou_asset_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "payment_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ACH-2026-99081"}),
            "paid_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Payment or accrual verification notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["lease_contract"].queryset = AssetLeaseContract.objects.filter(
                tenant=self.tenant
            ).order_by("-id")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["lease_contract"])

        contract = cleaned.get("lease_contract")
        period = cleaned.get("period_number")
        if contract and period is not None and self.tenant:
            qs = AssetLeaseSchedule.objects.filter(
                tenant=self.tenant,
                lease_contract=contract,
                period_number=period,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "period_number",
                    f"Period {period} already exists for contract {contract.number}."
                )

        return cleaned
