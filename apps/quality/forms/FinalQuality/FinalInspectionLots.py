from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.FinalQuality.FinalInspectionLots import FinalInspectionLot

User = get_user_model()


class FinalInspectionLotForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FinalInspectionLot
        fields = [
            "title",
            "inspection_stage",
            "sampling_standard",
            "aql_critical",
            "aql_major",
            "aql_minor",
            "status",
            "usage_decision",
            "decision_rationale",
            "item_code",
            "item_name",
            "lot_number",
            "batch_number",
            "serial_number_range",
            "lot_quantity",
            "sample_size_inspected",
            "critical_defects_count",
            "major_defects_count",
            "minor_defects_count",
            "units_passed",
            "units_rejected",
            "visual_inspection_passed",
            "dimensional_inspection_passed",
            "functional_test_passed",
            "packaging_inspection_passed",
            "is_on_hold",
            "hold_reason",
            "customer",
            "sales_order_number",
            "sales_order",
            "work_order_number",
            "work_order",
            "inspection_plan",
            "non_conformance",
            "process_deviation",
            "inspector",
            "decision_by",
            "inspection_date",
            "decision_date",
            "inspection_notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "inspection_stage": forms.Select(attrs={"class": "form-select"}),
            "sampling_standard": forms.Select(attrs={"class": "form-select"}),
            "aql_critical": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "aql_major": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "aql_minor": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "usage_decision": forms.Select(attrs={"class": "form-select"}),
            "decision_rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "batch_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_number_range": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. SN-1000 through SN-1250"}),
            "lot_quantity": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "sample_size_inspected": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "critical_defects_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "major_defects_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "minor_defects_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "units_passed": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "units_rejected": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "visual_inspection_passed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "dimensional_inspection_passed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "functional_test_passed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "packaging_inspection_passed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_on_hold": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "hold_reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "sales_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "work_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "inspection_plan": forms.Select(attrs={"class": "form-select"}),
            "non_conformance": forms.Select(attrs={"class": "form-select"}),
            "process_deviation": forms.Select(attrs={"class": "form-select"}),
            "inspector": forms.Select(attrs={"class": "form-select"}),
            "decision_by": forms.Select(attrs={"class": "form-select"}),
            "inspection_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "decision_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "inspection_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            users = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "email")
            self.fields["inspector"].queryset = users
            self.fields["decision_by"].queryset = users

            try:
                Party = apps.get_model("core", "Party")
                self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            except LookupError:
                pass

            try:
                ControlledDocument = apps.get_model("quality", "ControlledDocument")
                self.fields["inspection_plan"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            except LookupError:
                pass

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
                SalesOrder = apps.get_model("scm", "SalesOrder")
                self.fields["sales_order"].queryset = SalesOrder.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                WorkOrder = apps.get_model("scm", "WorkOrder")
                self.fields["work_order"].queryset = WorkOrder.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, [
            "customer", "sales_order", "work_order", "inspection_plan",
            "non_conformance", "process_deviation", "inspector", "decision_by",
        ])

        lot_qty = cleaned_data.get("lot_quantity") or 0
        sample_qty = cleaned_data.get("sample_size_inspected") or 0
        units_passed = cleaned_data.get("units_passed") or 0
        units_rejected = cleaned_data.get("units_rejected") or 0

        if sample_qty > lot_qty:
            self.add_error("sample_size_inspected", "Sample size cannot exceed total lot quantity.")

        if (units_passed + units_rejected) > sample_qty:
            self.add_error("units_passed", "Total units passed and rejected cannot exceed sample size inspected.")

        is_on_hold = cleaned_data.get("is_on_hold")
        hold_reason = cleaned_data.get("hold_reason")
        if is_on_hold and not hold_reason:
            self.add_error("hold_reason", "A hold reason is required when a lot is placed on hold.")

        usage_decision = cleaned_data.get("usage_decision")
        decision_rationale = cleaned_data.get("decision_rationale")
        if usage_decision in ("quarantined_hold", "rejected_mrb", "accepted_with_concession") and not decision_rationale:
            self.add_error("decision_rationale", "Decision rationale is mandatory when accepting with concession, holding, or rejecting.")

        return cleaned_data
