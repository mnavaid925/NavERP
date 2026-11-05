from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit


class BiDashboardForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiDashboard
        fields = [
            "title",
            "slug",
            "category",
            "layout_type",
            "refresh_interval_seconds",
            "theme",
            "role_required",
            "org_unit",
            "is_published",
            "is_template",
            "is_default",
            "is_kiosk_enabled",
            "description",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Executive Performance Command Center"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. executive-performance"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "layout_type": forms.Select(attrs={"class": "form-select"}),
            "refresh_interval_seconds": forms.NumberInput(attrs={"class": "form-input", "placeholder": "0 (manual) or seconds: 30, 60, 300"}),
            "theme": forms.Select(attrs={"class": "form-select"}),
            "role_required": forms.TextInput(attrs={"class": "form-input", "placeholder": "all, executive, finance_manager"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "High-level overview and purpose of this dashboard..."}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_template": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_kiosk_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["org_unit"].empty_label = "— All Departments / Org Units —"

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["org_unit"])
        title = cleaned_data.get("title")
        slug = cleaned_data.get("slug")
        if not slug and title:
            cleaned_data["slug"] = slugify(title)[:100]
        return cleaned_data


class BiDashboardDuplicateForm(forms.Form):
    new_title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Executive Performance (Copy)"}),
    )
    new_slug = forms.SlugField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "Auto-generated if blank"}),
    )
    copy_widgets = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        help_text="Duplicate all widgets and layouts onto the new dashboard",
    )
    copy_filters = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        help_text="Duplicate global top filter bar controls",
    )

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get("new_title")
        slug = cleaned_data.get("new_slug")
        if not slug and title:
            cleaned_data["new_slug"] = slugify(title)[:100]
        return cleaned_data
