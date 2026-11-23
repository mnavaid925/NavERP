import json
import re

from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin
from apps.documents.models.SecurityAccessControl.DlpPolicies import DlpPolicy


class DlpPolicyForm(TenantUniqueMixin, TenantModelForm):
    keywords_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 2,
            "placeholder": "Comma-separated keywords, e.g. Confidential, Secret, Acquisition, Financial Forecast",
        }),
        help_text="Enter sensitive keywords separated by commas.",
    )

    class Meta:
        model = DlpPolicy
        fields = [
            "name",
            "slug",
            "description",
            "rule_type",
            "built_in_pattern",
            "custom_regex",
            "match_threshold",
            "action",
            "severity",
            "notify_security_officer",
            "notification_email",
            "apply_to_all_types",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PCI Credit Card Exfiltration Guard"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "Auto-generated if blank"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Policy justification and regulatory mandate"}),
            "rule_type": forms.Select(attrs={"class": "form-select", "id": "id_rule_type"}),
            "built_in_pattern": forms.Select(attrs={"class": "form-select", "id": "id_built_in_pattern"}),
            "custom_regex": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": r"\b[A-Z]{3}-\d{6}\b"}),
            "match_threshold": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "action": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "notify_security_officer": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notification_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "security-officer@company.com"}),
            "apply_to_all_types": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["description"].required = False
        self.fields["custom_regex"].required = False
        self.fields["notification_email"].required = False

        if self.instance and self.instance.pk and self.instance.sensitive_keywords:
            self.fields["keywords_raw"].initial = ", ".join(self.instance.sensitive_keywords)

    def clean_custom_regex(self):
        val = self.cleaned_data.get("custom_regex")
        if val and val.strip():
            try:
                re.compile(val)
            except re.error as e:
                raise ValidationError(f"Invalid Python regular expression: {e}")
        return val

    def clean(self):
        cleaned_data = super().clean()
        rule_type = cleaned_data.get("rule_type")
        built_in = cleaned_data.get("built_in_pattern")
        regex = cleaned_data.get("custom_regex")
        keywords_str = cleaned_data.get("keywords_raw", "")

        if rule_type == "built_in_pattern" and (not built_in or built_in == "none"):
            self.add_error("built_in_pattern", "Please select a built-in pattern type.")
        elif rule_type == "custom_regex" and not regex:
            self.add_error("custom_regex", "Regular expression pattern is required for custom regex rules.")
        elif rule_type == "sensitive_keywords" and not keywords_str.strip():
            self.add_error("keywords_raw", "Please provide at least one sensitive keyword.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        keywords_str = self.cleaned_data.get("keywords_raw", "")
        if keywords_str:
            instance.sensitive_keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
        else:
            instance.sensitive_keywords = []

        if commit:
            instance.save()
        return instance
