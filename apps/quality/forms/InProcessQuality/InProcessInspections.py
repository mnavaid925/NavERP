from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.InProcessQuality.InProcessInspections import InProcessInspection

User = get_user_model()


class InProcessInspectionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = InProcessInspection
        fields = [
            "title",
            "inspection_type",
            "stage_gate",
            "status",
            "disposition",
            "production_order_number",
            "work_order",
            "work_center_code",
            "work_center",
            "operation_step",
            "item_code",
            "item_name",
            "lot_number",
            "serial_number",
            "batch_quantity",
            "sample_size_inspected",
            "quantity_passed",
            "quantity_rejected",
            "quantity_reworked",
            "defect_category",
            "defect_description",
            "controlled_document",
            "work_instruction_step",
            "operator_sign_off",
            "operator",
            "inspector",
            "inspection_date",
            "non_conformance",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "inspection_type": forms.Select(attrs={"class": "form-select"}),
            "stage_gate": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Primary Machining, In-Line Assembly"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "disposition": forms.Select(attrs={"class": "form-select"}),
            "production_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "work_center_code": forms.TextInput(attrs={"class": "form-input"}),
            "work_center": forms.Select(attrs={"class": "form-select"}),
            "operation_step": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Op 020 - Turning"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_number": forms.TextInput(attrs={"class": "form-input"}),
            "batch_quantity": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "sample_size_inspected": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "quantity_passed": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "quantity_rejected": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "quantity_reworked": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "defect_category": forms.Select(attrs={"class": "form-select"}),
            "defect_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "controlled_document": forms.Select(attrs={"class": "form-select"}),
            "work_instruction_step": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Step 4.2 Torque Check"}),
            "operator_sign_off": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "operator": forms.Select(attrs={"class": "form-select"}),
            "inspector": forms.Select(attrs={"class": "form-select"}),
            "inspection_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "non_conformance": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            users = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "email")
            self.fields["operator"].queryset = users
            self.fields["inspector"].queryset = users

            try:
                ControlledDocument = apps.get_model("quality", "ControlledDocument")
                self.fields["controlled_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            except LookupError:
                pass

            try:
                NonConformanceReport = apps.get_model("quality", "NonConformanceReport")
                self.fields["non_conformance"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant).order_by("-created_at")
            except LookupError:
                pass

            try:
                WorkOrder = apps.get_model("scm", "WorkOrder")
                self.fields["work_order"].queryset = WorkOrder.objects.filter(tenant=self.tenant).order_by("-created_at")
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
            "operator", "inspector", "controlled_document",
            "non_conformance", "work_order", "work_center"
        ])

        batch_qty = cleaned_data.get("batch_quantity") or 0
        sample_qty = cleaned_data.get("sample_size_inspected") or 0
        qty_passed = cleaned_data.get("quantity_passed") or 0
        qty_rejected = cleaned_data.get("quantity_rejected") or 0
        qty_reworked = cleaned_data.get("quantity_reworked") or 0

        if sample_qty > batch_qty:
            self.add_error("sample_size_inspected", "Sample size cannot exceed total batch quantity.")

        if (qty_passed + qty_rejected + qty_reworked) > sample_qty:
            self.add_error(
                "quantity_passed",
                "Total passed, rejected, and reworked pieces cannot exceed inspected sample size."
            )

        disposition = cleaned_data.get("disposition")
        defect_desc = cleaned_data.get("defect_description")
        if (disposition in ("rework_required", "reject_scrap", "quarantine_hold") or qty_rejected > 0) and not defect_desc:
            self.add_error("defect_description", "Defect description is required when parts are rejected, reworked, or quarantined.")

        return cleaned_data
