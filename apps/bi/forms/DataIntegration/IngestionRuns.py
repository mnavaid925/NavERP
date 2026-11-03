from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.bi.models.DataIntegration.IngestionRuns import IngestionRun


class IngestionRunForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = IngestionRun
        fields = [
            "pipeline",
            "trigger_type",
            "status",
            "error_message",
            "log_summary",
        ]
        widgets = {
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "trigger_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "error_message": forms.TextInput(attrs={"class": "form-input", "placeholder": "Error or diagnostic flag"}),
            "log_summary": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4, "placeholder": "Diagnostic execution logs..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["pipeline"].queryset = IngestionPipeline.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["pipeline"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.tenant and not instance.tenant_id:
            instance.tenant = self.tenant
        if commit:
            instance.save()
            self.save_m2m()
        return instance
