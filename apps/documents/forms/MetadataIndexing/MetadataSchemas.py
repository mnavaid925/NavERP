import json
from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import OrgUnit
from apps.documents.models import DocumentFolder, MetadataSchema


class MetadataSchemaForm(forms.ModelForm):
    class Meta:
        model = MetadataSchema
        fields = [
            "name",
            "code",
            "description",
            "target_type",
            "department",
            "target_folder",
            "fields_definition_json",
            "inheritance_mode",
            "is_required",
            "allow_custom_fields",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Standard NDA Metadata"}),
            "code": forms.TextInput(attrs={"class": "form-input uppercase", "placeholder": "e.g. NDA_SCHEMA"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "target_type": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "target_folder": forms.Select(attrs={"class": "form-select"}),
            "fields_definition_json": forms.Textarea(attrs={
                "class": "form-textarea font-mono text-sm",
                "rows": 6,
                "placeholder": '[{"key": "effective_date", "label": "Effective Date", "data_type": "date", "required": true}]',
            }),
            "inheritance_mode": forms.Select(attrs={"class": "form-select"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "allow_custom_fields": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["target_folder"].queryset = DocumentFolder.objects.filter(tenant=self.tenant)
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["target_folder"].queryset = DocumentFolder.objects.none()

        self.fields["department"].empty_label = "— Global / All Departments —"
        self.fields["target_folder"].empty_label = "— Global / Root Level —"

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        if not code:
            raise ValidationError("Schema code is required.")
        qs = MetadataSchema.objects.filter(code=code)
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"A metadata schema with code '{code}' already exists for this tenant.")
        return code

    def clean_fields_definition_json(self):
        raw = self.cleaned_data.get("fields_definition_json", "").strip()
        if not raw:
            return "[]"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON format: {exc}")
        if not isinstance(parsed, list):
            raise ValidationError("Fields definition must be a JSON array of field objects.")
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise ValidationError(f"Field at index {idx} must be a dictionary object.")
            if "key" not in item or not str(item["key"]).strip():
                raise ValidationError(f"Field at index {idx} must specify a non-empty 'key'.")
            if "label" not in item:
                item["label"] = str(item["key"]).replace("_", " ").title()
            if "data_type" not in item:
                item["data_type"] = "text"
        return json.dumps(parsed, indent=2)

    def clean(self):
        cleaned_data = super().clean()
        dept = cleaned_data.get("department")
        if dept and self.tenant and dept.tenant != self.tenant:
            raise ValidationError("Selected department does not belong to your organization.")
        folder = cleaned_data.get("target_folder")
        if folder and self.tenant and folder.tenant != self.tenant:
            raise ValidationError("Selected folder does not belong to your organization.")
        return cleaned_data
