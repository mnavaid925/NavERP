from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy


class WatermarkPolicyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = WatermarkPolicy
        fields = [
            "name",
            "slug",
            "description",
            "classification",
            "document_type",
            "department",
            "apply_to_all",
            "watermark_text",
            "secondary_text",
            "position",
            "opacity_percent",
            "font_size",
            "font_color",
            "rotation_angle",
            "show_classification_banner",
            "banner_position",
            "enforce_on_view",
            "enforce_on_download",
            "enforce_on_print",
            "priority",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Confidential Documents Watermark"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "Auto-generated if blank"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Policy scope and legal basis"}),
            "classification": forms.Select(attrs={"class": "form-select"}),
            "document_type": forms.TextInput(attrs={"class": "form-input", "placeholder": "'all' or specific type like 'contract'"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "apply_to_all": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "watermark_text": forms.TextInput(attrs={"class": "form-input", "placeholder": "{{classification}} | {{user_name}} | {{timestamp}}"}),
            "secondary_text": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Unauthorized Copying Prohibited"}),
            "position": forms.Select(attrs={"class": "form-select"}),
            "opacity_percent": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 100}),
            "font_size": forms.NumberInput(attrs={"class": "form-input", "min": 10, "max": 120}),
            "font_color": forms.TextInput(attrs={"class": "form-input", "placeholder": "#94a3b8"}),
            "rotation_angle": forms.NumberInput(attrs={"class": "form-input"}),
            "show_classification_banner": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "banner_position": forms.Select(attrs={"class": "form-select"}),
            "enforce_on_view": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "enforce_on_download": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "enforce_on_print": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")

        self.fields["slug"].required = False
        self.fields["description"].required = False
        self.fields["department"].required = False
        self.fields["secondary_text"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["department"])

        opacity = cleaned_data.get("opacity_percent")
        if opacity is not None and (opacity < 1 or opacity > 100):
            self.add_error("opacity_percent", "Opacity must be between 1% and 100%.")

        return cleaned_data
