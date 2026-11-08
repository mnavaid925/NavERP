from django import forms

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetProcurement.AssetCapitalizations import AssetCapitalization
from apps.assets.models.AssetProcurement.AssetTags import AssetTag
from apps.scm.models import Asset


class AssetTagForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetTag
        exclude = [
            "tenant",
            "number",
            "status",
            "created_at",
            "updated_at",
            "affixed_by",
            "affixed_at",
            "verified_by",
            "verified_at",
        ]
        widgets = {
            "tag_code": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "AST-QR-2026-0001 / RFID-HEX-001"}),
            "tag_format": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "capitalization": forms.Select(attrs={"class": "form-select"}),
            "physical_placement": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Upper-left bezel near motor switch"}),
            "scanner_device_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ZEBRA-TC52-DOCK-1"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["capitalization"].queryset = AssetCapitalization.objects.filter(tenant=self.tenant)

    def clean_tag_code(self):
        code = self.cleaned_data.get("tag_code", "").strip()
        if not code:
            raise forms.ValidationError("Tag code cannot be blank.")
        qs = AssetTag.objects.filter(tenant=self.tenant, tag_code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Tag code '{code}' is already assigned to another asset in this workspace.")
        return code

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                ["operational_asset", "capitalization"],
            )
        return cleaned_data
