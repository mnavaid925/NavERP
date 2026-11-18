from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.InProcessQuality.ProcessParameterLogs import ProcessParameterLog

User = get_user_model()


class ProcessParameterLogForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProcessParameterLog
        fields = [
            "parameter_name",
            "parameter_category",
            "unit_of_measure",
            "work_center_code",
            "work_center",
            "production_order_number",
            "work_order",
            "operation_step",
            "item_code",
            "lot_number",
            "target_nominal_value",
            "lower_spec_limit",
            "upper_spec_limit",
            "lower_control_limit",
            "upper_control_limit",
            "recorded_value",
            "recorded_at",
            "excursion_status",
            "logged_by",
            "containment_action",
            "containment_notes",
            "non_conformance",
            "process_deviation",
        ]
        widgets = {
            "parameter_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Solder Reflow Peak Temp"}),
            "parameter_category": forms.Select(attrs={"class": "form-select"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. °C, bar, RPM, mm, V"}),
            "work_center_code": forms.TextInput(attrs={"class": "form-input"}),
            "work_center": forms.Select(attrs={"class": "form-select"}),
            "production_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "operation_step": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Op 040 SMT Reflow"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "target_nominal_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "lower_spec_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "upper_spec_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "lower_control_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "upper_control_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "recorded_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "recorded_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "excursion_status": forms.Select(attrs={"class": "form-select"}),
            "logged_by": forms.Select(attrs={"class": "form-select"}),
            "containment_action": forms.Select(attrs={"class": "form-select"}),
            "containment_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "non_conformance": forms.Select(attrs={"class": "form-select"}),
            "process_deviation": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["logged_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "email")

            try:
                NonConformanceReport = apps.get_model("quality", "NonConformanceReport")
                self.fields["non_conformance"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                ProcessDeviation = apps.get_model("quality", "ProcessDeviation")
                self.fields["process_deviation"].queryset = ProcessDeviation.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                WorkOrder = apps.get_model("scm", "WorkOrder")
                self.fields["work_order"].queryset = WorkOrder.objects.filter(tenant=self.tenant).select_related("item").order_by("-created_at")
            except LookupError:
                pass

            try:
                WorkCenter = apps.get_model("scm", "WorkCenter")
                self.fields["work_center"].queryset = WorkCenter.objects.filter(tenant=self.tenant).order_by("code")
            except LookupError:
                pass

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "logged_by", "non_conformance", "process_deviation", "work_order", "work_center"
        ])

        target = cleaned_data.get("target_nominal_value")
        lsl = cleaned_data.get("lower_spec_limit")
        usl = cleaned_data.get("upper_spec_limit")
        lcl = cleaned_data.get("lower_control_limit")
        ucl = cleaned_data.get("upper_control_limit")
        recorded = cleaned_data.get("recorded_value")

        if lsl is not None and usl is not None and lsl > usl:
            self.add_error("upper_spec_limit", "Upper specification limit (USL) cannot be less than lower limit (LSL).")

        if lcl is not None and ucl is not None and lcl > ucl:
            self.add_error("upper_control_limit", "Upper control limit (UCL) cannot be less than lower control limit (LCL).")

        # Auto-detect excursion state if limits exist
        if recorded is not None and lsl is not None and usl is not None:
            if recorded < lsl or recorded > usl:
                cleaned_data["excursion_status"] = "out_of_spec"
            elif lcl is not None and ucl is not None and (recorded < lcl or recorded > ucl):
                if cleaned_data.get("excursion_status") != "out_of_spec":
                    cleaned_data["excursion_status"] = "out_of_control"

        excursion = cleaned_data.get("excursion_status")
        containment = cleaned_data.get("containment_action")

        if excursion == "out_of_spec" and containment == "none":
            self.add_error(
                "containment_action",
                "Immediate containment action is mandatory when a parameter excursion is Out-of-Spec."
            )

        return cleaned_data
