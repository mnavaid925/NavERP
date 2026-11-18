import json

from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.IncomingQuality.CertificatesOfAnalysis import (
    CertificateOfAnalysis,
)
from apps.quality.models.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLot,
)
from apps.quality.models.IncomingQuality.IncomingInspectionPlans import (
    IncomingInspectionPlan,
)


class CertificateOfAnalysisForm(TenantUniqueMixin, TenantModelForm):
    parameters_json = forms.CharField(
        required=False,
        label="Analytical Parameters (JSON)",
        help_text="Define CoA parameters: [{'parameter': 'Assay Purity', 'method': 'HPLC', 'lsl': 98.0, 'usl': 102.0, 'actual_value': 99.4, 'unit': '%'}]",
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-sm", "rows": 4}),
    )

    class Meta:
        model = CertificateOfAnalysis
        fields = [
            "certificate_number",
            "supplier",
            "item_code",
            "item_name",
            "lot_number",
            "inspection_lot",
            "inspection_plan",
            "manufacturer_name",
            "date_of_manufacture",
            "expiry_or_retest_date",
            "lab_accreditation",
            "status",
            "supporting_document",
            "notes",
        ]
        widgets = {
            "certificate_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. COA-VND-2026-9921"}),
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "item_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PRT-10024"}),
            "item_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Drive Shaft 25mm"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOT-2026-0881"}),
            "inspection_lot": forms.Select(attrs={"class": "form-select"}),
            "inspection_plan": forms.Select(attrs={"class": "form-select"}),
            "manufacturer_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Precision Alloys GmbH"}),
            "date_of_manufacture": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiry_or_retest_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "lab_accreditation": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ISO/IEC 17025 Accredited Lab #441"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "supporting_document": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["supplier"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role__in=("supplier", "vendor"),
            ).order_by("name")
            self.fields["inspection_lot"].queryset = IncomingInspectionLot.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["inspection_plan"].queryset = IncomingInspectionPlan.objects.filter(
                tenant=self.tenant
            ).order_by("number")
            self.fields["supporting_document"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant
            ).order_by("number")

        if self.instance and self.instance.pk and self.instance.parameters_payload:
            self.fields["parameters_json"].initial = json.dumps(
                self.instance.parameters_payload, indent=2
            )

    def clean_parameters_json(self):
        raw = self.cleaned_data.get("parameters_json", "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("Parameters must be a JSON array of parameter dictionaries.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["supplier", "inspection_lot", "inspection_plan", "supporting_document"],
        )

        dom = cleaned.get("date_of_manufacture")
        exp = cleaned.get("expiry_or_retest_date")
        if dom and exp and dom > exp:
            self.add_error("expiry_or_retest_date", "Expiry or retest date cannot precede date of manufacture.")

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "parameters_json" in self.cleaned_data:
            instance.parameters_payload = self.cleaned_data["parameters_json"]
            instance.verify_specifications()
        if commit:
            instance.save()
            self.save_m2m()
        return instance
