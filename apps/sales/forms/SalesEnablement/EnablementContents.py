"""Sales 8.9 — `EnablementContentForm`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.core.models import Document
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import CompetitorProfile
from apps.sales.models.OpportunityPipeline.Pipelines import PipelineStage
from apps.sales.models.SalesEnablement.EnablementContents import EnablementContent


class EnablementContentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = EnablementContent
        fields = [
            "title",
            "description",
            "content_type",
            "document",
            "external_url",
            "competitor",
            "target_stage",
            "target_persona",
            "pipeline_stage",
            "author",
            "tags",
            "version",
            "is_client_facing",
            "is_active",
            "expires_on",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Competitor Battlecard: Acme vs Apex"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Key takeaways, positioning angle, or script snippet"}),
            "content_type": forms.Select(attrs={"class": "form-select"}),
            "document": forms.Select(attrs={"class": "form-select"}),
            "external_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://docs.google.com/presentation/d/..."}),
            "competitor": forms.Select(attrs={"class": "form-select"}),
            "target_stage": forms.Select(attrs={"class": "form-select"}),
            "target_persona": forms.Select(attrs={"class": "form-select"}),
            "pipeline_stage": forms.Select(attrs={"class": "form-select"}),
            "author": forms.Select(attrs={"class": "form-select"}),
            "tags": forms.TextInput(attrs={"class": "form-input", "placeholder": "saas, enterprise, security, meddpicc"}),
            "version": forms.TextInput(attrs={"class": "form-input", "placeholder": "1.0"}),
            "is_client_facing": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "expires_on": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant)
            self.fields["competitor"].queryset = CompetitorProfile.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["pipeline_stage"].queryset = PipelineStage.objects.filter(tenant=self.tenant)
            self.fields["author"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
        else:
            self.fields["document"].queryset = Document.objects.none()
            self.fields["competitor"].queryset = CompetitorProfile.objects.none()
            self.fields["pipeline_stage"].queryset = PipelineStage.objects.none()
            self.fields["author"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["document", "competitor", "pipeline_stage", "author"])
        return cleaned
