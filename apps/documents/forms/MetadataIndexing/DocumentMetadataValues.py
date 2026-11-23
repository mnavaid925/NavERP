import json
from django import forms
from django.core.exceptions import ValidationError

from apps.documents.models import Document, DocumentMetadataValue, DocumentVersion, MetadataSchema


class DocumentMetadataValueForm(forms.ModelForm):
    class Meta:
        model = DocumentMetadataValue
        fields = [
            "document",
            "version",
            "schema",
            "field_name",
            "field_label",
            "data_type",
            "value_text",
            "value_number",
            "value_date",
            "value_boolean",
            "value_json",
            "source",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "schema": forms.Select(attrs={"class": "form-select"}),
            "field_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. counterparty_name"}),
            "field_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Counterparty Name"}),
            "data_type": forms.Select(attrs={"class": "form-select"}),
            "value_text": forms.TextInput(attrs={"class": "form-input", "placeholder": "String/text value..."}),
            "value_number": forms.NumberInput(attrs={"class": "form-input", "placeholder": "0.00"}),
            "value_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "value_boolean": forms.Select(attrs={"class": "form-select"}, choices=[(None, "— Not Set —"), (True, "Yes / True"), (False, "No / False")]),
            "value_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-sm", "rows": 3, "placeholder": '{"key": "value"}'}),
            "source": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant)
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant)
            self.fields["schema"].queryset = MetadataSchema.objects.filter(tenant=self.tenant)
        else:
            self.fields["document"].queryset = Document.objects.none()
            self.fields["version"].queryset = DocumentVersion.objects.none()
            self.fields["schema"].queryset = MetadataSchema.objects.none()

        self.fields["version"].empty_label = "— Global Document Level (All Versions) —"
        self.fields["schema"].empty_label = "— Ad-hoc / Standalone (No Schema) —"

    def clean_value_json(self):
        val = self.cleaned_data.get("value_json", "").strip()
        if val:
            try:
                json.loads(val)
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValidationError(f"Invalid JSON syntax: {exc}")
        return val

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get("data_type")
        val_json = cleaned_data.get("value_json", "").strip()
        if data_type == "json" and not val_json:
            self.add_error("value_json", "JSON payload is required when data type is 'json'.")
        doc = cleaned_data.get("document")
        if doc and self.tenant and doc.tenant != self.tenant:
            self.add_error("document", "Selected document does not belong to your organization.")
        ver = cleaned_data.get("version")
        if ver and doc and ver.document != doc:
            self.add_error("version", "Selected revision version does not belong to the selected document.")
        schema = cleaned_data.get("schema")
        if schema and self.tenant and schema.tenant != self.tenant:
            self.add_error("schema", "Selected metadata schema does not belong to your organization.")

        field_name = cleaned_data.get("field_name")
        tenant = self.tenant or (self.instance.tenant if self.instance and hasattr(self.instance, "tenant") else None)
        if doc and field_name and tenant:
            qs = DocumentMetadataValue.objects.filter(
                tenant=tenant,
                document=doc,
                version=ver,
                field_name=field_name,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                ver_str = f"revision '{ver}'" if ver else "document global level"
                self.add_error("field_name", f"Metadata field '{field_name}' already exists for {ver_str}.")

        return cleaned_data
