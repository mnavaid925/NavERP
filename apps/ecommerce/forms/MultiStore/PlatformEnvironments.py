from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.MultiStore.PlatformEnvironments import PlatformEnvironment
from apps.ecommerce.models.MultiStore.StorefrontInstances import StorefrontInstance


class PlatformEnvironmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PlatformEnvironment
        exclude = ["tenant", "number", "created_at", "updated_at", "last_health_check_at"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US Production Primary Cluster"}),
            "env_type": forms.Select(attrs={"class": "form-select"}),
            "storefront": forms.Select(attrs={"class": "form-select"}),
            "cluster_region": forms.Select(attrs={"class": "form-select"}),
            "base_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://prod.apexoutdoor.com"}),
            "current_active_slot": forms.Select(attrs={"class": "form-select"}),
            "is_sandbox_locked": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "resource_tier": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Environment tier notes, cluster sizing, release notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self, "tenant", None) or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["storefront"].queryset = StorefrontInstance.objects.filter(tenant=tenant)
