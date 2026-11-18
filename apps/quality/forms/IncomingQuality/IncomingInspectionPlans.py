import json

from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit, Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.IncomingQuality.IncomingInspectionPlans import (
    IncomingInspectionPlan,
)


class IncomingInspectionPlanForm(TenantUniqueMixin, TenantModelForm):
    characteristics_json = forms.CharField(
        required=False,
        label="Characteristics Matrix (JSON)",
        help_text="Define CTQ specs as JSON list: [{'name': 'Diameter', 'type': 'variable', 'lsl': 9.8, 'usl': 10.2, 'unit': 'mm'}]",
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-sm", "rows": 4}),
    )

    class Meta:
        model = IncomingInspectionPlan
        fields = [
            "title",
            "item_code",
            "item_name",
            "revision",
            "supplier",
            "sampling_standard",
            "inspection_level",
            "inspection_severity",
            "inspection_frequency",
            "skip_lot_interval",
            "aql_critical",
            "aql_major",
            "aql_minor",
            "requires_coa",
            "requires_coc",
            "status",
            "sop_document",
            "assigned_team",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Precision CNC Machined Shaft IQC"}),
            "item_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PRT-10024"}),
            "item_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Drive Shaft 25mm"}),
            "revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. B"}),
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "sampling_standard": forms.Select(attrs={"class": "form-select"}),
            "inspection_level": forms.Select(attrs={"class": "form-select"}),
            "inspection_severity": forms.Select(attrs={"class": "form-select"}),
            "inspection_frequency": forms.Select(attrs={"class": "form-select"}),
            "skip_lot_interval": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "aql_critical": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "aql_major": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "aql_minor": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "requires_coa": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_coc": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "sop_document": forms.Select(attrs={"class": "form-select"}),
            "assigned_team": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["supplier"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role__in=("supplier", "vendor"),
            ).only("id", "name").order_by("name").distinct()
            self.fields["sop_document"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant,
            ).order_by("number")
            self.fields["assigned_team"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant,
            ).order_by("name")

        if self.instance and self.instance.pk and self.instance.characteristics_matrix:
            self.fields["characteristics_json"].initial = json.dumps(
                self.instance.characteristics_matrix, indent=2
            )

    def clean_characteristics_json(self):
        raw = self.cleaned_data.get("characteristics_json", "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("Characteristics must be a JSON array of characteristic objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["supplier", "sop_document", "assigned_team"])

        aql_crit = cleaned.get("aql_critical")
        aql_maj = cleaned.get("aql_major")
        aql_min = cleaned.get("aql_minor")

        if aql_crit is not None and aql_crit < 0:
            self.add_error("aql_critical", "Critical AQL cannot be negative.")
        if aql_maj is not None and aql_maj < 0:
            self.add_error("aql_major", "Major AQL cannot be negative.")
        if aql_min is not None and aql_min < 0:
            self.add_error("aql_minor", "Minor AQL cannot be negative.")

        if aql_crit is not None and aql_maj is not None and aql_crit > aql_maj:
            self.add_error("aql_critical", "Critical AQL must not exceed Major AQL.")
        if aql_maj is not None and aql_min is not None and aql_maj > aql_min:
            self.add_error("aql_major", "Major AQL must not exceed Minor AQL.")

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "characteristics_json" in self.cleaned_data:
            instance.characteristics_matrix = self.cleaned_data["characteristics_json"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance
