from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.EtlPipelines.EtlPipelineRuns import EtlPipelineRun
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.EtlPipelineVersions import EtlPipelineVersion


class EtlPipelineRunForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = EtlPipelineRun
        fields = [
            "pipeline",
            "version",
            "trigger_type",
            "is_backfill",
            "backfill_range_start",
            "backfill_range_end",
        ]
        widgets = {
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "trigger_type": forms.Select(attrs={"class": "form-select"}),
            "is_backfill": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "backfill_range_start": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "backfill_range_end": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["pipeline"].queryset = EtlPipeline.objects.filter(tenant=self.tenant)
            self.fields["version"].queryset = EtlPipelineVersion.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["pipeline", "version"])
        pipeline = cleaned.get("pipeline")
        version = cleaned.get("version")
        if pipeline and version and version.pipeline_id != pipeline.id:
            self.add_error("version", "Selected pipeline version does not belong to the selected pipeline.")
        return cleaned
