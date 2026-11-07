from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.ConversationalBi.BiConversationSessions import BiConversationSession
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class BiConversationSessionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiConversationSession
        fields = [
            "title",
            "session_status",
            "is_pinned",
            "primary_semantic_model",
            "primary_dashboard",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Q4 Executive Revenue & Profitability Q&A",
                }
            ),
            "session_status": forms.Select(attrs={"class": "form-select"}),
            "is_pinned": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "primary_semantic_model": forms.Select(attrs={"class": "form-select"}),
            "primary_dashboard": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["primary_semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["primary_dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant)
        self.fields["primary_semantic_model"].required = False
        self.fields["primary_dashboard"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["primary_semantic_model", "primary_dashboard"],
        )
        return cleaned_data
