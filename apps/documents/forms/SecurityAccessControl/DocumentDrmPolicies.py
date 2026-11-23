from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicy
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document


class DocumentDrmPolicyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentDrmPolicy
        fields = [
            "name",
            "slug",
            "description",
            "classification",
            "document_type",
            "target_document",
            "target_folder",
            "allow_download",
            "allow_print",
            "allow_copy_paste",
            "screen_shield_enabled",
            "secure_viewer_required",
            "require_watermark",
            "max_offline_hours",
            "expiry_days",
            "ip_allowlist",
            "geo_fencing_countries",
            "encryption_standard",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Restricted Board Papers DRM"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "Auto-generated if blank"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Policy scope and compliance justification"}),
            "classification": forms.Select(attrs={"class": "form-select"}),
            "document_type": forms.TextInput(attrs={"class": "form-input", "placeholder": "'all' or specific type like 'contract'"}),
            "target_document": forms.Select(attrs={"class": "form-select"}),
            "target_folder": forms.Select(attrs={"class": "form-select"}),
            "allow_download": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "allow_print": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "allow_copy_paste": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "screen_shield_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "secure_viewer_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "require_watermark": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "max_offline_hours": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "expiry_days": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "ip_allowlist": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2, "placeholder": "192.168.1.0/24, 10.0.0.1"}),
            "geo_fencing_countries": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US, CA, GB"}),
            "encryption_standard": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["target_folder"].queryset = DocumentFolder.objects.filter(tenant=self.tenant).order_by("name")

        self.fields["slug"].required = False
        self.fields["description"].required = False
        self.fields["target_document"].required = False
        self.fields["target_folder"].required = False
        self.fields["ip_allowlist"].required = False
        self.fields["geo_fencing_countries"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["target_document", "target_folder"])
        return cleaned_data
