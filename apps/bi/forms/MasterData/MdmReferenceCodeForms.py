import json
from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.MasterData.MdmReferenceCodes import MdmReferenceCode
from apps.core.forms import TenantModelForm


class MdmReferenceCodeForm(TenantUniqueMixin, TenantModelForm):
    attributes_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea font-mono text-xs",
                "rows": 3,
                "placeholder": '{"iso_numeric": "840", "alpha_2": "US", "dial_code": "+1"}',
            }
        ),
        required=False,
        label="Supplementary Attributes (JSON format)",
    )

    class Meta:
        model = MdmReferenceCode
        fields = [
            "code_set",
            "canonical_code",
            "canonical_name",
            "source_system",
            "source_code",
            "category",
            "status",
            "superseded_by",
            "effective_from",
            "effective_to",
            "description",
            "is_active",
        ]
        widgets = {
            "code_set": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. country_codes"}),
            "canonical_code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. USA"}),
            "canonical_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. United States of America"}),
            "source_system": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. legacy_crm (optional)"}),
            "source_code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. US (optional)"}),
            "category": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. North America (optional)"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "superseded_by": forms.Select(attrs={"class": "form-select"}),
            "effective_from": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_to": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Standard notes and mapping semantics"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.attributes_json:
                self.fields["attributes_text"].initial = json.dumps(
                    self.instance.attributes_json, indent=2
                )
        if self.tenant is not None:
            superseded_qs = MdmReferenceCode.objects.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                superseded_qs = superseded_qs.exclude(pk=self.instance.pk)
            self.fields["superseded_by"].queryset = (
                superseded_qs.only("id", "code_set", "canonical_code", "canonical_name", "source_system", "source_code")
                .order_by("code_set", "canonical_code")
            )

    def clean_attributes_text(self):
        data = self.cleaned_data.get("attributes_text", "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Attributes must be a valid JSON dictionary.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["superseded_by"])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.attributes_json = self.cleaned_data.get("attributes_text", {})
        if commit:
            instance.save()
        return instance
