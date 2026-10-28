"""Form for SalesCustomEntityDefinition model."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.sales.models.MasterDataConfiguration.SalesCustomEntityDefinitions import SalesCustomEntityDefinition


class SalesCustomEntityDefinitionForm(TenantModelForm):
    """Form to create and update custom sales entity and field definitions."""

    picklist_options_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea font-mono text-sm",
                "rows": 3,
                "placeholder": 'Enter one option per line, e.g.:\nTier 1 Enterprise\nMid-Market Growth\nSMB Fast Track',
            }
        ),
        label="Picklist Options",
        help_text="One option per line or JSON array for picklist field types.",
    )

    class Meta:
        model = SalesCustomEntityDefinition
        fields = [
            "name",
            "entity_code",
            "target_model",
            "field_type",
            "is_required",
            "formula_expression",
            "lookup_target_model",
            "validation_rule",
            "display_order",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Deal Margin Percentage"}),
            "entity_code": forms.TextInput(attrs={"class": "form-input font-mono lowercase", "placeholder": "e.g. deal_margin_pct_c"}),
            "target_model": forms.Select(attrs={"class": "form-select"}),
            "field_type": forms.Select(attrs={"class": "form-select"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "formula_expression": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. (amount - cost) / amount * 100"}),
            "lookup_target_model": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. core.Party or crm.Opportunity"}),
            "validation_rule": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. ^[A-Z0-9_-]{3,20}$"}),
            "display_order": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Documentation and calculation rationale..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.picklist_options:
            if isinstance(self.instance.picklist_options, list):
                self.fields["picklist_options_raw"].initial = "\n".join(str(opt) for opt in self.instance.picklist_options)

    def clean_picklist_options_raw(self):
        raw = self.cleaned_data.get("picklist_options_raw", "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def clean(self):
        cleaned_data = super().clean()
        options = cleaned_data.get("picklist_options_raw")
        if options is not None:
            self.instance.picklist_options = options
        return cleaned_data
