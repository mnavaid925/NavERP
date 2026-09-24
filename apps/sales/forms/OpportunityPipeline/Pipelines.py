from django import forms
from django.core.exceptions import ValidationError

from apps.crm.models import Opportunity
from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin
from apps.sales.models.OpportunityPipeline.Pipelines import (
    PIPELINE_CRITERION_CHOICES,
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
)


class PipelineForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Pipeline
        fields = ["name", "description", "is_default", "is_active"]


class PipelineStageForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PipelineStage
        fields = [
            "pipeline",
            "name",
            "code",
            "sequence",
            "stage_kind",
            "crm_stage_key",
            "probability",
            "forecast_category",
            "entry_guidance",
            "exit_guidance",
            "entry_criteria",
            "exit_criteria",
            "target_days",
            "is_active",
        ]
        widgets = {
            "entry_guidance": forms.Textarea(attrs={"rows": 3}),
            "exit_guidance": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, tenant=None, pipeline=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.pipeline = pipeline or self.instance.pipeline
        if tenant is None:
            self.fields["pipeline"].queryset = Pipeline.objects.none()
        else:
            self.fields["pipeline"].queryset = Pipeline.objects.filter(tenant=tenant).order_by("name")
        if pipeline is not None and not self.instance.pipeline_id:
            self.instance.pipeline = pipeline
        if self.instance.pipeline_id and not self.instance.tenant_id:
            self.instance.tenant = tenant
        criterion_labels = dict(PIPELINE_CRITERION_CHOICES)
        for field_name in ("entry_criteria", "exit_criteria"):
            current = getattr(self.instance, field_name, []) or []
            self.fields[field_name] = forms.MultipleChoiceField(
                choices=PIPELINE_CRITERION_CHOICES,
                required=False,
                widget=forms.CheckboxSelectMultiple(),
                initial=[item.get("key") for item in current if isinstance(item, dict)],
            )
        locked_fields = []
        if self.instance.pk:
            self.fields["pipeline"].disabled = True
            locked_fields.append("pipeline")
            if self.instance.current_placements.exists():
                locked_fields.extend(
                    ["stage_kind", "crm_stage_key", "probability", "forecast_category", "is_active"]
                )
                for field_name in locked_fields:
                    self.fields[field_name].disabled = True
        self.locked_fields = locked_fields
        self.criterion_labels = criterion_labels

    def clean(self):
        cleaned = super().clean()
        for field_name in self.locked_fields:
            if self.instance.pk and field_name in self.data:
                expected = getattr(self.instance, field_name)
                submitted = self.data.get(field_name)
                if isinstance(expected, bool):
                    submitted_value = forms.CheckboxInput().value_from_datadict(
                        self.data,
                        self.files,
                        field_name,
                    )
                    matches = bool(submitted_value) == expected
                else:
                    expected_value = expected.pk if hasattr(expected, "pk") else expected
                    matches = str(submitted) == str(expected_value)
                if not matches:
                    self.add_error(field_name, "This field cannot be changed for the current record.")
        for field_name in ("entry_criteria", "exit_criteria"):
            if field_name in cleaned:
                cleaned[field_name] = [
                    {"key": key, "label": self.criterion_labels[key]}
                    for key in cleaned[field_name]
                ]
        return cleaned


class PipelineStageOrderForm(forms.Form):
    ordered_stage_ids = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, tenant=None, pipeline=None, **kwargs):
        self.tenant = tenant
        self.pipeline = pipeline
        super().__init__(*args, **kwargs)
        if pipeline is not None:
            stage_ids = list(
                PipelineStage.objects.filter(tenant=tenant, pipeline=pipeline)
                .order_by("sequence", "pk")
                .values_list("pk", flat=True)
            )
            self.fields["ordered_stage_ids"].initial = ",".join(str(stage_id) for stage_id in stage_ids)

    def clean(self):
        cleaned = super().clean()
        raw_value = cleaned.get("ordered_stage_ids", "")
        tokens = [token for token in raw_value.replace(",", " ").split() if token]
        if not tokens or any(not token.isdigit() for token in tokens):
            raise ValidationError("Choose every pipeline stage exactly once.")
        stage_ids = [int(token) for token in tokens]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValidationError("Choose every pipeline stage exactly once.")
        if self.pipeline is None or self.tenant is None:
            raise ValidationError("Pipeline stages are unavailable for this workspace.")
        expected = set(
            PipelineStage.objects.filter(tenant=self.tenant, pipeline=self.pipeline).values_list(
                "pk", flat=True
            )
        )
        if set(stage_ids) != expected:
            raise ValidationError("Choose every pipeline stage exactly once.")
        cleaned["ordered_stage_ids"] = stage_ids
        return cleaned


class OpportunityPipelinePlacementForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OpportunityPipelinePlacement
        fields = ["opportunity", "pipeline", "current_stage", "probability_override"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["opportunity"].queryset = (
            Opportunity.objects.none()
            if tenant is None
            else Opportunity.objects.filter(tenant=tenant).order_by("number")
        )
        self.fields["pipeline"].queryset = (
            Pipeline.objects.none()
            if tenant is None
            else Pipeline.objects.filter(tenant=tenant, is_active=True).order_by("name")
        )
        pipeline_id = self.data.get("pipeline") if self.is_bound else self.instance.pipeline_id
        self.fields["current_stage"].queryset = (
            PipelineStage.objects.none()
            if tenant is None or not pipeline_id
            else PipelineStage.objects.filter(
                tenant=tenant,
                pipeline_id=pipeline_id,
                is_active=True,
            ).order_by("sequence", "pk")
        )
        if self.instance.pk:
            self.fields["opportunity"].disabled = True

    def clean(self):
        cleaned = super().clean()
        tenant_id = self.tenant.pk if self.tenant is not None else None
        opportunity = cleaned.get("opportunity")
        pipeline = cleaned.get("pipeline")
        stage = cleaned.get("current_stage")
        if opportunity is not None and opportunity.tenant_id != tenant_id:
            self.add_error("opportunity", "Choose an opportunity from this workspace.")
        if pipeline is not None and (pipeline.tenant_id != tenant_id or not pipeline.is_active):
            self.add_error("pipeline", "Choose an active pipeline from this workspace.")
        if stage is not None:
            if stage.tenant_id != tenant_id or not stage.is_active:
                self.add_error("current_stage", "Choose an active stage from this workspace.")
            if pipeline is not None and stage.pipeline_id != pipeline.pk:
                self.add_error("current_stage", "Choose a stage from the selected pipeline.")
        probability_override = cleaned.get("probability_override")
        if stage is not None and probability_override is not None:
            if stage.stage_kind == "won" and probability_override != 100:
                self.add_error("probability_override", "Won placements require 100%.")
            if stage.stage_kind == "lost" and probability_override != 0:
                self.add_error("probability_override", "Lost placements require 0%.")
        return cleaned
