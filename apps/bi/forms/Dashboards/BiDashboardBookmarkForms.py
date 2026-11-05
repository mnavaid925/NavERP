from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardBookmarks import BiDashboardBookmark
from apps.core.forms import TenantModelForm


class BiDashboardBookmarkForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiDashboardBookmark
        fields = [
            "dashboard",
            "name",
            "is_default",
            "is_shared",
            "description",
            "is_active",
        ]
        widgets = {
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Western Region High-Priority"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "What this bookmark view captures..."}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_shared": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant, is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["dashboard"])
        return cleaned_data
