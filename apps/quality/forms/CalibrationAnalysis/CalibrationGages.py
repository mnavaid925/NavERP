from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.scm.models.AssetManagement.Assets import Asset
from apps.scm.models.Manufacturing.WorkCenters import WorkCenter

User = get_user_model()


class CalibrationGageForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CalibrationGage
        exclude = ("tenant", "number", "last_calibration_result", "created_at", "updated_at")
        widgets = {
            "gage_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. GAG-0042"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 0-150mm Digital Caliper"}),
            "gage_type": forms.Select(attrs={"class": "form-select"}),
            "criticality": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "manufacturer": forms.TextInput(attrs={"class": "form-input"}),
            "model_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_number": forms.TextInput(attrs={"class": "form-input"}),
            "measurement_range": forms.TextInput(attrs={"class": "form-input", "placeholder": "0 to 150 mm"}),
            "resolution": forms.TextInput(attrs={"class": "form-input", "placeholder": "0.01 mm"}),
            "accuracy_spec": forms.TextInput(attrs={"class": "form-input", "placeholder": "+/- 0.02 mm"}),
            "max_permissible_error": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "engineering_unit": forms.TextInput(attrs={"class": "form-input", "placeholder": "mm"}),
            "is_reference_standard": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "nist_traceability_number": forms.TextInput(attrs={"class": "form-input"}),
            "reference_standard_parent": forms.Select(attrs={"class": "form-select"}),
            "asset_link": forms.Select(attrs={"class": "form-select"}),
            "work_center": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "custodian": forms.Select(attrs={"class": "form-select"}),
            "storage_location": forms.TextInput(attrs={"class": "form-input"}),
            "calibration_interval_days": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "last_calibration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_calibration_due": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "sop_document": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            parent_qs = CalibrationGage.objects.filter(
                tenant=self.tenant, is_reference_standard=True
            )
            if self.instance and self.instance.pk:
                parent_qs = parent_qs.exclude(pk=self.instance.pk)
            self.fields["reference_standard_parent"].queryset = parent_qs
            self.fields["asset_link"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["work_center"].queryset = WorkCenter.objects.filter(tenant=self.tenant)
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["custodian"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["sop_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self, cleaned,
            ["reference_standard_parent", "asset_link", "work_center", "department", "custodian", "sop_document"]
        )
        parent = cleaned.get("reference_standard_parent")
        if self.instance and self.instance.pk and parent and parent.pk == self.instance.pk:
            self.add_error("reference_standard_parent", "A gage cannot be its own reference standard parent.")
        interval = cleaned.get("calibration_interval_days")
        if interval is not None and interval <= 0:
            self.add_error("calibration_interval_days", "Interval must be greater than zero.")
        return cleaned
