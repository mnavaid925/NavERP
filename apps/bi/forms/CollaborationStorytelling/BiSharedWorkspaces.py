import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspace
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit

User = get_user_model()


class BiSharedWorkspaceForm(TenantUniqueMixin, TenantModelForm):
    members_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        label="Members & Role Overrides (JSON)",
        help_text='Optional JSON array of member roles, e.g. [{"username": "analyst1", "role": "contributor"}]',
    )

    class Meta:
        model = BiSharedWorkspace
        fields = [
            "name",
            "slug",
            "description",
            "department",
            "owner",
            "default_access_level",
            "status",
            "is_public",
            "is_favorite",
            "color",
            "icon",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "default_access_level": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_favorite": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "color": forms.TextInput(attrs={"type": "color", "class": "form-input h-10 w-20 p-1"}),
            "icon": forms.TextInput(attrs={"class": "form-input", "placeholder": "folder"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["owner"].queryset = User.objects.none()
        if self.instance and self.instance.pk:
            if self.instance.members_json:
                self.fields["members_raw"].initial = json.dumps(self.instance.members_json, indent=2)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["department", "owner"])
        return cleaned

    def clean_members_raw(self):
        raw = self.cleaned_data.get("members_raw", "").strip()
        if not raw:
            return []
        try:
            val = json.loads(raw)
            if not isinstance(val, list):
                raise ValidationError("Must be a JSON array of member objects.")
            return val
        except (json.JSONDecodeError, ValueError) as err:
            raise ValidationError(f"Invalid JSON format: {err}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "members_raw" in self.cleaned_data:
            instance.members_json = self.cleaned_data["members_raw"]
        if commit:
            instance.save()
        return instance
