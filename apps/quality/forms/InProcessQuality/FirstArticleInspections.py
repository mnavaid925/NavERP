from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.InProcessQuality.FirstArticleInspections import FirstArticleInspection

User = get_user_model()


class FirstArticleInspectionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FirstArticleInspection
        fields = [
            "title",
            "fai_type",
            "setup_reason",
            "status",
            "production_order_number",
            "work_order",
            "work_center_code",
            "work_center",
            "machine_tooling_id",
            "item_code",
            "item_name",
            "drawing_number",
            "drawing_revision",
            "first_piece_lot_number",
            "serial_number",
            "total_characteristics_inspected",
            "characteristics_conforming",
            "characteristics_out_of_spec",
            "max_deviation_found",
            "as9102_form1_complete",
            "as9102_form2_complete",
            "as9102_form3_complete",
            "gage_serial_numbers",
            "release_verdict",
            "conditional_release_notes",
            "non_conformance",
            "inspector",
            "approved_by",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "fai_type": forms.Select(attrs={"class": "form-select"}),
            "setup_reason": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "production_order_number": forms.TextInput(attrs={"class": "form-input"}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "work_center_code": forms.TextInput(attrs={"class": "form-input"}),
            "work_center": forms.Select(attrs={"class": "form-select"}),
            "machine_tooling_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CNC-04 Die-B2"}),
            "item_code": forms.TextInput(attrs={"class": "form-input"}),
            "item_name": forms.TextInput(attrs={"class": "form-input"}),
            "drawing_number": forms.TextInput(attrs={"class": "form-input"}),
            "drawing_revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Rev C"}),
            "first_piece_lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_number": forms.TextInput(attrs={"class": "form-input"}),
            "total_characteristics_inspected": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "characteristics_conforming": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "characteristics_out_of_spec": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "max_deviation_found": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. +0.003 mm on Bore Dia"}),
            "as9102_form1_complete": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "as9102_form2_complete": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "as9102_form3_complete": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "gage_serial_numbers": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CMM-01, Caliper-402, HeightGage-12"}),
            "release_verdict": forms.Select(attrs={"class": "form-select"}),
            "conditional_release_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "non_conformance": forms.Select(attrs={"class": "form-select"}),
            "inspector": forms.Select(attrs={"class": "form-select"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            users = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "email")
            self.fields["inspector"].queryset = users
            self.fields["approved_by"].queryset = users

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
            "inspector", "approved_by", "non_conformance", "work_order", "work_center"
        ])

        total_chars = cleaned_data.get("total_characteristics_inspected") or 0
        conforming_chars = cleaned_data.get("characteristics_conforming") or 0
        oos_chars = cleaned_data.get("characteristics_out_of_spec") or 0

        if (conforming_chars + oos_chars) > total_chars and total_chars > 0:
            self.add_error(
                "characteristics_conforming",
                "Total conforming plus out-of-spec characteristics cannot exceed total inspected characteristics."
            )

        status = cleaned_data.get("status")
        verdict = cleaned_data.get("release_verdict")

        if status == "approved_run_released" or verdict == "released":
            if oos_chars > 0:
                self.add_error("characteristics_out_of_spec", "Full production run release requires zero out-of-spec characteristics.")
            form1 = cleaned_data.get("as9102_form1_complete")
            form2 = cleaned_data.get("as9102_form2_complete")
            form3 = cleaned_data.get("as9102_form3_complete")
            if not (form1 and form2 and form3):
                self.add_error("release_verdict", "Full production release requires AS9102 Forms 1, 2, and 3 verification sign-offs.")

        if (status == "conditional_approval" or verdict == "conditional_pilot_release") and not cleaned_data.get("conditional_release_notes"):
            self.add_error("conditional_release_notes", "Conditional release notes and containment boundaries are mandatory for pilot releases.")

        return cleaned_data
