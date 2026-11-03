import json
import re

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.EtlPipelineVersions import EtlPipelineVersion
from apps.core.models.Backup import EnvironmentInstance


class EtlPipelineVersionForm(TenantUniqueMixin, forms.ModelForm):
    dag_definition_raw = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4}),
        required=False,
        label="DAG Definition Snapshot (JSON)",
        help_text="Declarative JSON snapshot of pipeline configuration and transformation steps. If left empty, automatically snapshot from current pipeline steps.",
    )

    class Meta:
        model = EtlPipelineVersion
        fields = [
            "pipeline",
            "version_number",
            "environment",
            "environment_instance",
            "status",
            "changelog",
        ]
        widgets = {
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "version_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. v1.0.0"}),
            "environment": forms.Select(attrs={"class": "form-select"}),
            "environment_instance": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "changelog": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe transformation and schema modifications in this release"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["pipeline"].queryset = EtlPipeline.objects.filter(tenant=self.tenant).only("id", "name", "number")
            self.fields["environment_instance"].queryset = EnvironmentInstance.objects.filter(tenant=self.tenant)
        if self.instance and self.instance.pk and self.instance.dag_definition:
            self.fields["dag_definition_raw"].initial = json.dumps(self.instance.dag_definition, indent=2)

    def clean_version_number(self):
        v = self.cleaned_data.get("version_number", "").strip()
        if not re.match(r"^[a-zA-Z0-9_\.\-]+$", v):
            raise forms.ValidationError("Version number can only contain alphanumeric characters, underscores, dots, and hyphens.")
        return v

    def clean_dag_definition_raw(self):
        raw = self.cleaned_data.get("dag_definition_raw", "").strip()
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            if not isinstance(val, dict):
                raise forms.ValidationError("DAG definition must be a valid JSON object.")
            return val
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["pipeline", "environment_instance"])
        pipeline = cleaned.get("pipeline")
        version_number = cleaned.get("version_number")
        if pipeline and version_number and self.tenant:
            qs = EtlPipelineVersion.objects.filter(
                tenant=self.tenant,
                pipeline=pipeline,
                version_number=version_number,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("version_number", f"Version '{version_number}' already exists for this pipeline.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        dag_def = self.cleaned_data.get("dag_definition_raw")
        if dag_def:
            instance.dag_definition = dag_def
        elif instance.pipeline_id:
            # Re-snapshot from current pipeline steps whenever raw input is empty
            steps = instance.pipeline.steps.all().order_by("sequence")
            instance.dag_definition = {
                "pipeline_number": instance.pipeline.number,
                "pipeline_name": instance.pipeline.name,
                "target_table": instance.pipeline.target_table,
                "steps": [
                    {
                        "sequence": s.sequence,
                        "name": s.name,
                        "step_type": s.step_type,
                        "upstream_step_ids": s.upstream_step_ids,
                        "step_config": s.step_config,
                        "is_blocking": s.is_blocking,
                    }
                    for s in steps
                ],
            }
        if commit:
            instance.save()
        return instance
