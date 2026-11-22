from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.LimsManagement.LabSamples import LabSample

User = get_user_model()


class LabSampleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LabSample
        fields = [
            "sample_name",
            "sample_type",
            "status",
            "matrix_description",
            "source_batch_number",
            "item_code",
            "item_name",
            "sampling_point",
            "sampled_by",
            "sampled_at",
            "received_by",
            "current_custodian",
            "storage_location",
            "storage_condition",
            "quantity_collected",
            "unit_of_measure",
            "retest_date",
            "expiry_date",
            "barcode_identifier",
            "chain_of_custody_log",
            "work_order",
            "batch_record",
            "facility",
            "notes",
        ]
        widgets = {
            "sample_name": forms.TextInput(attrs={"class": "form-input"}),
            "sample_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "matrix_description": forms.TextInput(attrs={"class": "form-input"}),
            "source_batch_number": forms.TextInput(attrs={"class": "form-input"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "sampling_point": forms.TextInput(attrs={"class": "form-input"}),
            "sampled_by": forms.Select(attrs={"class": "form-select"}),
            "sampled_at": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "received_by": forms.Select(attrs={"class": "form-select"}),
            "current_custodian": forms.Select(attrs={"class": "form-select"}),
            "storage_location": forms.TextInput(attrs={"class": "form-input"}),
            "storage_condition": forms.Select(attrs={"class": "form-select"}),
            "quantity_collected": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input"}),
            "retest_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiry_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "barcode_identifier": forms.TextInput(attrs={"class": "form-input"}),
            "chain_of_custody_log": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "batch_record": forms.Select(attrs={"class": "form-select"}),
            "facility": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["sampled_by"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["received_by"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["current_custodian"].queryset = User.objects.filter(tenant=self.tenant)

            WorkOrder = apps.get_model("scm", "WorkOrder")
            self.fields["work_order"].queryset = WorkOrder.objects.filter(tenant=self.tenant)

            BatchRecord = apps.get_model("quality", "BatchRecord")
            self.fields["batch_record"].queryset = BatchRecord.objects.filter(tenant=self.tenant)

            OrgUnit = apps.get_model("core", "OrgUnit")
            self.fields["facility"].queryset = OrgUnit.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "sampled_by",
                "received_by",
                "current_custodian",
                "work_order",
                "batch_record",
                "facility",
            ],
        )
        return cleaned_data
