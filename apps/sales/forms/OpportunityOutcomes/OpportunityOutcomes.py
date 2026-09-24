from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import OpportunityCompetitor
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import WinLossReason
from apps.sales.models.OpportunityPipeline.Pipelines import PipelineStage


class WinLossReasonForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = WinLossReason
        fields = ["code", "name", "description", "sequence", "result", "category", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "sequence": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = tenant

    def clean_code(self):
        code = self.cleaned_data.get("code")
        return code.strip().lower() if isinstance(code, str) else code

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        if self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The win/loss reason must belong to this workspace.")
        return cleaned


class OpportunityTransitionForm(forms.Form):
    target_stage = forms.ModelChoiceField(queryset=PipelineStage.objects.none())
    reason = forms.ModelChoiceField(queryset=WinLossReason.objects.none(), required=False)
    competitor_link = forms.ModelChoiceField(queryset=OpportunityCompetitor.objects.none(), required=False)
    notes = forms.CharField(
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(
        self,
        *args,
        tenant=None,
        opportunity=None,
        placement=None,
        current_stage=None,
        allowed_target_stages=None,
        current_placement=None,
        allowed_stages=None,
        target_stages=None,
        **kwargs,
    ):
        self.tenant = tenant
        self.opportunity = opportunity
        self.placement = placement if placement is not None else current_placement
        self.current_stage = current_stage
        self.allowed_target_stages = (
            allowed_target_stages
            if allowed_target_stages is not None
            else allowed_stages if allowed_stages is not None else target_stages
        )
        super().__init__(*args, **kwargs)
        self._placement_valid = self._validate_context()
        target_queryset = self._target_queryset()
        self.fields["target_stage"].queryset = target_queryset
        self.fields["reason"].queryset = self._reason_queryset(self._target_hint(target_queryset))
        self.fields["competitor_link"].queryset = self._competitor_queryset()

    def _tenant_id(self):
        return getattr(self.tenant, "pk", self.tenant)

    def _validate_context(self):
        tenant_id = self._tenant_id()
        if tenant_id is None or self.opportunity is None or self.placement is None:
            return False
        if self.opportunity.tenant_id != tenant_id:
            return False
        if self.placement.tenant_id != tenant_id or self.placement.opportunity_id != self.opportunity.pk:
            return False
        if self.current_stage is None and self.placement.current_stage_id:
            try:
                self.current_stage = PipelineStage.objects.filter(
                    pk=self.placement.current_stage_id,
                    tenant_id=tenant_id,
                    pipeline_id=self.placement.pipeline_id,
                ).first()
            except (ObjectDoesNotExist, ValueError):
                self.current_stage = None
        if self.current_stage is None:
            return False
        if (
            self.current_stage.tenant_id != tenant_id
            or self.current_stage.pipeline_id != self.placement.pipeline_id
            or not self.current_stage.is_active
        ):
            return False
        return True

    def _target_queryset(self):
        if not self._placement_valid:
            return PipelineStage.objects.none()
        tenant_id = self._tenant_id()
        queryset = PipelineStage.objects.filter(
            tenant_id=tenant_id,
            pipeline_id=self.placement.pipeline_id,
            is_active=True,
        ).exclude(pk=self.current_stage.pk)
        if self.allowed_target_stages is not None:
            allowed_ids = [getattr(stage, "pk", stage) for stage in self.allowed_target_stages]
            queryset = queryset.filter(pk__in=[stage_id for stage_id in allowed_ids if stage_id])
        return queryset.order_by("sequence", "pk")

    def _target_hint(self, target_queryset):
        if not self.is_bound:
            return None
        target_id = self.data.get("target_stage")
        if not target_id:
            return None
        return target_queryset.filter(pk=target_id).first()

    def _reason_queryset(self, target):
        tenant_id = self._tenant_id()
        if tenant_id is None:
            return WinLossReason.objects.none()
        queryset = WinLossReason.objects.filter(tenant_id=tenant_id, is_active=True)
        if target is not None and target.stage_kind in {"won", "lost"}:
            queryset = queryset.filter(Q(result="both") | Q(result=target.stage_kind))
        return queryset.order_by("sequence", "name", "pk")

    def _competitor_queryset(self):
        tenant_id = self._tenant_id()
        if tenant_id is None or self.opportunity is None or self.opportunity.tenant_id != tenant_id:
            return OpportunityCompetitor.objects.none()
        return (
            OpportunityCompetitor.objects.filter(
                tenant_id=tenant_id,
                opportunity_id=self.opportunity.pk,
            )
            .select_related("competitor_profile__party")
            .order_by("competitor_profile__party__name", "relationship", "pk")
        )

    def clean(self):
        cleaned = super().clean()
        if not self._placement_valid:
            self.add_error(None, "Place this opportunity in a pipeline before transitioning it.")
            return cleaned
        target = cleaned.get("target_stage")
        if target is None:
            return cleaned
        if target.tenant_id != self._tenant_id() or target.pipeline_id != self.placement.pipeline_id:
            self.add_error("target_stage", "Choose an active stage from the current pipeline.")
            return cleaned
        if not target.is_active:
            self.add_error("target_stage", "Choose an active stage from the current pipeline.")
            return cleaned
        if target.stage_kind not in {"open", "won", "lost"}:
            self.add_error("target_stage", "Choose a valid pipeline stage.")
            return cleaned
        reason = cleaned.get("reason")
        competitor_link = cleaned.get("competitor_link")
        if target.stage_kind in {"won", "lost"}:
            if reason is None:
                self.add_error("reason", "A reason is required when closing an opportunity.")
            elif reason.tenant_id != self._tenant_id() or not reason.is_active:
                self.add_error("reason", "Choose an active reason from this workspace.")
            elif reason.result not in {"both", target.stage_kind}:
                self.add_error("reason", "Choose a reason compatible with the closing result.")
        else:
            if reason is not None:
                self.add_error("reason", "A reason is only valid when closing an opportunity.")
            if competitor_link is not None:
                self.add_error("competitor_link", "A competitor link is only valid on a lost closure.")
        if competitor_link is not None:
            if competitor_link.tenant_id != self._tenant_id() or competitor_link.opportunity_id != self.opportunity.pk:
                self.add_error("competitor_link", "Choose a competitor link from this opportunity.")
            elif competitor_link.relationship in {"lost_to", "beaten"} and target.stage_kind != "lost":
                self.add_error("competitor_link", "This competitor relationship requires a lost target.")
        return cleaned
