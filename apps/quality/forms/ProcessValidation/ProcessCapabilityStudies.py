from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.InProcessQuality.ProcessParameterLogs import ProcessParameterLog
from apps.quality.models.ProcessValidation.ProcessCapabilityStudies import ProcessCapabilityStudy
from apps.quality.models.ProcessValidation.ValidationProtocols import ValidationProtocol

User = get_user_model()


class ProcessCapabilityStudyForm(TenantModelForm):
    class Meta:
        model = ProcessCapabilityStudy
        fields = [
            "title",
            "parameter_name",
            "parameter_category",
            "unit_of_measure",
            "upper_spec_limit",
            "lower_spec_limit",
            "target_nominal",
            "subgroup_size",
            "number_of_subgroups",
            "total_samples",
            "mean_value",
            "within_subgroup_stdev",
            "overall_stdev",
            "is_normally_distributed",
            "status",
            "process_name",
            "equipment_tag",
            "item_code",
            "lot_number",
            "analysis_summary",
            "study_date",
            "validation_protocol",
            "investigator",
            "approved_by",
            "linked_parameter_log",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Tablet Press 02 Fill Weight Capability Study"}),
            "parameter_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Core Tablet Weight (mg)"}),
            "parameter_category": forms.Select(attrs={"class": "form-select"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. mg, mm, °C, bar"}),
            "upper_spec_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "lower_spec_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "target_nominal": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "subgroup_size": forms.NumberInput(attrs={"class": "form-input"}),
            "number_of_subgroups": forms.NumberInput(attrs={"class": "form-input"}),
            "total_samples": forms.NumberInput(attrs={"class": "form-input"}),
            "mean_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "within_subgroup_stdev": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "overall_stdev": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "is_normally_distributed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "process_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Rotary Tableting Stage"}),
            "equipment_tag": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PR-02"}),
            "item_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FG-TAB-500"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOT-2026-09A"}),
            "analysis_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Statistical observations, Cp/Cpk interpretation, and actions"}),
            "study_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "validation_protocol": forms.Select(attrs={"class": "form-select"}),
            "investigator": forms.Select(attrs={"class": "form-select"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "linked_parameter_log": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "username")
            self.fields["investigator"].queryset = user_qs
            self.fields["approved_by"].queryset = user_qs
            self.fields["validation_protocol"].queryset = ValidationProtocol.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["linked_parameter_log"].queryset = ProcessParameterLog.objects.filter(tenant=self.tenant).order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        usl = cleaned.get("upper_spec_limit")
        lsl = cleaned.get("lower_spec_limit")
        if usl is not None and lsl is not None and usl <= lsl:
            self.add_error("upper_spec_limit", "Upper Specification Limit must be strictly greater than Lower Specification Limit.")

        reject_foreign(
            self,
            cleaned,
            [
                "validation_protocol",
                "investigator",
                "approved_by",
                "linked_parameter_log",
            ],
        )
        return cleaned
