from django import forms
from django.apps import apps

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.TraceabilitySerialization.SerializedItems import SerializedItem


class SerializedItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SerializedItem
        fields = [
            "serial_number",
            "gtin_or_di",
            "item_code",
            "item_name",
            "lot_number",
            "batch_record",
            "device_identifier",
            "packaging_level",
            "parent_container",
            "sscc_code",
            "commissioning_status",
            "epcis_state",
            "verification_code",
            "is_cold_chain",
            "temperature_limit_min",
            "temperature_limit_max",
            "custodian",
            "location_unit",
            "shipment",
            "manufacturing_date",
            "expiration_date",
            "notes",
        ]
        widgets = {
            "serial_number": forms.TextInput(attrs={"class": "form-input"}),
            "gtin_or_di": forms.TextInput(attrs={"class": "form-input"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "batch_record": forms.Select(attrs={"class": "form-select"}),
            "device_identifier": forms.Select(attrs={"class": "form-select"}),
            "packaging_level": forms.Select(attrs={"class": "form-select"}),
            "parent_container": forms.Select(attrs={"class": "form-select"}),
            "sscc_code": forms.TextInput(attrs={"class": "form-input"}),
            "commissioning_status": forms.Select(attrs={"class": "form-select"}),
            "epcis_state": forms.Select(attrs={"class": "form-select"}),
            "verification_code": forms.TextInput(attrs={"class": "form-input"}),
            "is_cold_chain": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "temperature_limit_min": forms.NumberInput(attrs={"class": "form-input", "step": "0.1"}),
            "temperature_limit_max": forms.NumberInput(attrs={"class": "form-input", "step": "0.1"}),
            "custodian": forms.Select(attrs={"class": "form-select"}),
            "location_unit": forms.Select(attrs={"class": "form-select"}),
            "shipment": forms.Select(attrs={"class": "form-select"}),
            "manufacturing_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            BatchRecord = apps.get_model("quality", "BatchRecord")
            self.fields["batch_record"].queryset = BatchRecord.objects.filter(tenant=self.tenant)

            DeviceIdentifier = apps.get_model("quality", "DeviceIdentifier")
            self.fields["device_identifier"].queryset = DeviceIdentifier.objects.filter(tenant=self.tenant)

            parent_qs = SerializedItem.objects.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                parent_qs = parent_qs.exclude(pk=self.instance.pk)
            self.fields["parent_container"].queryset = parent_qs

            Party = apps.get_model("core", "Party")
            self.fields["custodian"].queryset = Party.objects.filter(tenant=self.tenant)

            OrgUnit = apps.get_model("core", "OrgUnit")
            self.fields["location_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)

            Shipment = apps.get_model("scm", "Shipment")
            self.fields["shipment"].queryset = Shipment.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "batch_record",
                "device_identifier",
                "parent_container",
                "custodian",
                "location_unit",
                "shipment",
            ],
        )
        return cleaned_data
