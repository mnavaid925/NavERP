import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin
from apps.bi.models.IntegrationHub.BiExtensionPlugins import BiExtensionPlugin
from apps.core.forms import TenantModelForm


class BiExtensionPluginForm(TenantUniqueMixin, TenantModelForm):
    manifest_metadata_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '{\n  "entrypoint_js": "/static/bi/plugins/sankey.js",\n  "min_naverp_version": "1.0.0"\n}',
            }
        ),
        label="Manifest Metadata (JSON)",
        help_text="Plugin manifest specifications, entrypoint scripts, and capabilities",
    )

    config_schema_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '{\n  "type": "object",\n  "properties": {"theme": {"type": "string"}}\n}',
            }
        ),
        label="Configuration JSON Schema",
        help_text="JSON Schema definition for configurable plugin properties",
    )

    current_config_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '{\n  "theme": "dark",\n  "node_width": 20\n}',
            }
        ),
        label="Active Tenant Configuration (JSON)",
        help_text="Tenant-specific configuration values matching the schema",
    )

    permissions_required_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '[\n  "read_semantic_layer",\n  "render_canvas_ui"\n]',
            }
        ),
        label="Permissions Required (JSON Array)",
        help_text='JSON list of sandboxed permissions: ["read_semantic_layer", "render_canvas_ui"]',
    )

    class Meta:
        model = BiExtensionPlugin
        fields = [
            "name",
            "plugin_identifier",
            "version",
            "plugin_type",
            "category",
            "description",
            "author_name",
            "homepage_url",
            "repository_url",
            "license",
            "status",
            "is_verified",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. ECharts Sankey Diagram Pro"}
            ),
            "plugin_identifier": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "io.naverp.visuals.sankey-pro"}
            ),
            "version": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "1.0.0"}
            ),
            "plugin_type": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Overview of capabilities and features..."}
            ),
            "author_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. NavERP Community Extensions"}
            ),
            "homepage_url": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://..."}
            ),
            "repository_url": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://github.com/..."}
            ),
            "license": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "MIT"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.manifest_metadata:
                self.fields["manifest_metadata_raw"].initial = json.dumps(
                    self.instance.manifest_metadata, indent=2
                )
            if self.instance.config_schema:
                self.fields["config_schema_raw"].initial = json.dumps(
                    self.instance.config_schema, indent=2
                )
            if self.instance.current_config:
                self.fields["current_config_raw"].initial = json.dumps(
                    self.instance.current_config, indent=2
                )
            if self.instance.permissions_required:
                self.fields["permissions_required_raw"].initial = json.dumps(
                    self.instance.permissions_required, indent=2
                )

    def clean_manifest_metadata_raw(self):
        data = self.cleaned_data.get("manifest_metadata_raw", "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Manifest metadata must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON in manifest metadata: {err}")

    def clean_config_schema_raw(self):
        data = self.cleaned_data.get("config_schema_raw", "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Config schema must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON in config schema: {err}")

    def clean_current_config_raw(self):
        data = self.cleaned_data.get("current_config_raw", "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Current config must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON in current config: {err}")

    def clean_permissions_required_raw(self):
        data = self.cleaned_data.get("permissions_required_raw", "").strip()
        if not data:
            return []
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, list):
                raise ValidationError("Permissions must be a JSON array of strings.")
            return [str(p).strip() for p in parsed if p]
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON in permissions required: {err}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.manifest_metadata = self.cleaned_data.get("manifest_metadata_raw") or {}
        instance.config_schema = self.cleaned_data.get("config_schema_raw") or {}
        instance.current_config = self.cleaned_data.get("current_config_raw") or {}
        instance.permissions_required = self.cleaned_data.get("permissions_required_raw") or []
        if commit:
            instance.save()
        return instance
