"""Sales 8.9 — `SalesPlaybookForm`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline
from apps.sales.models.SalesEnablement.SalesPlaybooks import SalesPlaybook


class SalesPlaybookForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SalesPlaybook
        fields = [
            "name",
            "summary",
            "motion_type",
            "pipeline",
            "status",
            "target_audience",
            "discovery_questions",
            "talk_tracks",
            "objection_scripts",
            "dos_and_donts",
            "exit_criteria",
            "owner",
            "version",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Enterprise Mid-Market Outbound Playbook"}),
            "summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Overview and primary goals of this motion"}),
            "motion_type": forms.Select(attrs={"class": "form-select"}),
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "target_audience": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. B2B SaaS companies with 200+ employees"}),
            "discovery_questions": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "1. What is your current tech stack?\n2. What is your primary pain point with existing vendor?"}),
            "talk_tracks": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Key value anchors, customer testimonials, and elevator pitch"}),
            "objection_scripts": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Common objections: 'Too expensive', 'No budget this quarter', 'Happy with incumbent'"}),
            "dos_and_donts": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "DO: Quantify business ROI. DON'T: Trash the competitor product."}),
            "exit_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Confirmed economic buyer sponsor and technical proof of concept"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "version": forms.TextInput(attrs={"class": "form-input", "placeholder": "1.0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["pipeline"].queryset = Pipeline.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
        else:
            self.fields["pipeline"].queryset = Pipeline.objects.none()
            self.fields["owner"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["pipeline", "owner"])
        return cleaned
