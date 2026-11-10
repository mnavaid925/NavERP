from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetRequisition
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.models.AssetDisposal.AssetTradeIns import AssetTradeIn
from apps.core.models import Document, Party

User = get_user_model()


class AssetTradeInForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetTradeIn
        fields = [
            "disposal_request",
            "retired_fixed_asset",
            "vendor",
            "replacement_requisition",
            "replacement_fixed_asset",
            "agreement_document",
            "agreement_number",
            "agreement_date",
            "handover_due_date",
            "dealer_appraised_value",
            "trade_in_allowance",
            "over_allowance_amount",
            "replacement_asset_cost",
            "like_kind_exchange",
            "gain_loss_deferred",
            "notes",
        ]
        widgets = {
            "disposal_request": forms.Select(attrs={"class": "form-select"}),
            "retired_fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "vendor": forms.Select(attrs={"class": "form-select"}),
            "replacement_requisition": forms.Select(attrs={"class": "form-select"}),
            "replacement_fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "agreement_document": forms.Select(attrs={"class": "form-select"}),
            "agreement_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CAT-DEALER-TI-2026-09"}),
            "agreement_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "handover_due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "dealer_appraised_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "trade_in_allowance": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "over_allowance_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "replacement_asset_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "like_kind_exchange": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "gain_loss_deferred": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Exchange terms, warranty transfers, delivery offsets..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["disposal_request"].queryset = AssetDisposalRequest.objects.filter(tenant=self.tenant)
            fa_qs = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["retired_fixed_asset"].queryset = fa_qs
            self.fields["replacement_fixed_asset"].queryset = fa_qs
            self.fields["vendor"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["replacement_requisition"].queryset = AssetRequisition.objects.filter(tenant=self.tenant)
            self.fields["agreement_document"].queryset = Document.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "disposal_request",
                "retired_fixed_asset",
                "vendor",
                "replacement_requisition",
                "replacement_fixed_asset",
                "agreement_document",
            ],
        )
        return cleaned
