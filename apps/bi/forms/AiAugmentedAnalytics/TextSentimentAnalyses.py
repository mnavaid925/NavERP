from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AiAugmentedAnalytics.TextSentimentAnalyses import TextSentimentAnalysis
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party


class TextSentimentAnalysisForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = TextSentimentAnalysis
        fields = [
            "source_type",
            "source_reference",
            "text_content",
            "language",
            "sentiment_category",
            "polarity_score",
            "subjectivity_score",
            "linked_party",
            "linked_org_unit",
        ]
        widgets = {
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "source_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TKT-00421, REV-9811"}),
            "text_content": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Enter unstructured text to analyze..."}),
            "language": forms.TextInput(attrs={"class": "form-input", "placeholder": "en"}),
            "sentiment_category": forms.Select(attrs={"class": "form-select"}),
            "polarity_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "-1", "max": "1"}),
            "subjectivity_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "1"}),
            "linked_party": forms.Select(attrs={"class": "form-select"}),
            "linked_org_unit": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["linked_party"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["linked_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
        self.fields["linked_party"].required = False
        self.fields["linked_org_unit"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["linked_party", "linked_org_unit"])
        return cleaned_data
