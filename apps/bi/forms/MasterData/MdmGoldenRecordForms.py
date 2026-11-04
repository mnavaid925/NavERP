from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.MasterData.MdmGoldenRecords import MdmGoldenRecord
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.core.forms import TenantModelForm
from apps.core.models import Party, PartyRole
from apps.scm.models.InventoryManagement.Items import Item
from apps.scm.models.AssetManagement.Assets import Asset


class MdmGoldenRecordForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MdmGoldenRecord
        fields = [
            "name",
            "code",
            "domain",
            "status",
            "trust_tier",
            "confidence_score",
            "tax_id",
            "primary_email",
            "primary_phone",
            "primary_address",
            "party",
            "party_role",
            "item",
            "asset",
            "warehouse_table",
            "assigned_steward",
            "stewardship_notes",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Global Industries Inc."}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. acme_global_corp"}),
            "domain": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "trust_tier": forms.Select(attrs={"class": "form-select"}),
            "confidence_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "100.00"}),
            "tax_id": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. US-123456789"}),
            "primary_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "contact@acme.example.com"}),
            "primary_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "+1-555-0199"}),
            "primary_address": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "100 Innovation Way, Suite 400"}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "party_role": forms.Select(attrs={"class": "form-select"}),
            "item": forms.Select(attrs={"class": "form-select"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "assigned_steward": forms.Select(attrs={"class": "form-select"}),
            "stewardship_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Steward audit notes and resolution history"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "status" in self.fields:
            self.fields["status"].choices = [c for c in MdmGoldenRecord.STATUS_CHOICES if c[0] != "merged"]
        if self.tenant is not None:
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["party_role"].queryset = PartyRole.objects.filter(tenant=self.tenant).order_by("role")
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant).order_by("name")
            
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk and self.instance.assigned_steward_id:
                steward_filter |= Q(pk=self.instance.assigned_steward_id)
            self.fields["assigned_steward"].queryset = user_qs.filter(steward_filter).order_by("first_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["party", "party_role", "item", "asset", "warehouse_table", "assigned_steward"],
        )
        return cleaned


class MdmGoldenRecordMergeForm(forms.Form):
    secondary_record = forms.ModelChoiceField(
        queryset=MdmGoldenRecord.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Record to Absorb & Merge",
        help_text="Select the duplicate golden record that will be marked merged and absorbed into this master record.",
    )
    stewardship_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reason for merge and survivorship decisions"}),
        required=False,
    )

    def __init__(self, tenant, primary_record, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["secondary_record"].queryset = (
            MdmGoldenRecord.objects.filter(tenant=tenant, domain=primary_record.domain)
            .exclude(pk=primary_record.pk)
            .exclude(status="merged")
            .order_by("name")
        )
