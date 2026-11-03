from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.MultiStore.DeploymentPipelines import DeploymentPipeline
from apps.ecommerce.models.MultiStore.PlatformEnvironments import PlatformEnvironment


class DeploymentPipelineForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DeploymentPipeline
        exclude = ["tenant", "number", "created_at", "updated_at", "promoted_by", "promoted_at"]
        widgets = {
            "environment": forms.Select(attrs={"class": "form-select"}),
            "release_version": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. v2.4.0 or release-2026.11"}),
            "git_branch": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. main or release/v2.4"}),
            "git_commit_sha": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "40-character commit SHA"}),
            "deployment_strategy": forms.Select(attrs={"class": "form-select"}),
            "target_slot": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "preview_endpoint_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://preview-v240.shop.acme.com"}),
            "traffic_percentage": forms.NumberInput(attrs={"class": "form-input", "placeholder": "0", "min": "0", "max": "100"}),
            "migration_executed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "build_duration_seconds": forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. 180"}),
            "deployment_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Release changelog, bug fixes, smoke test notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self, "tenant", None) or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["environment"].queryset = PlatformEnvironment.objects.filter(tenant=tenant)

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk:
            status = cleaned_data.get("status")
            traffic_percentage = cleaned_data.get("traffic_percentage") or 0
            if status == "promoted_active":
                self.add_error(
                    "status",
                    "Cannot set 'Promoted / Active Live' status directly on creation. Use the promotion workflow.",
                )
            if traffic_percentage > 0:
                self.add_error(
                    "traffic_percentage",
                    "New deployments cannot be assigned live traffic on creation (must be 0%).",
                )
        return cleaned_data
