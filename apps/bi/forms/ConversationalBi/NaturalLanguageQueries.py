from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.ConversationalBi.BiConversationSessions import BiConversationSession
from apps.bi.models.ConversationalBi.NaturalLanguageQueries import NaturalLanguageQuery
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class NaturalLanguageQueryForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = NaturalLanguageQuery
        fields = [
            "query_text",
            "input_modality",
            "intent_type",
            "semantic_model",
            "warehouse_table",
            "kpi_definition",
            "conversation_session",
            "chart_type",
            "user_rating",
            "user_feedback_notes",
        ]
        widgets = {
            "query_text": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Show quarterly revenue by region for FY2026",
                }
            ),
            "input_modality": forms.Select(attrs={"class": "form-select"}),
            "intent_type": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "kpi_definition": forms.Select(attrs={"class": "form-select"}),
            "conversation_session": forms.Select(attrs={"class": "form-select"}),
            "chart_type": forms.Select(attrs={"class": "form-select"}),
            "user_rating": forms.Select(attrs={"class": "form-select"}),
            "user_feedback_notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Notes or accuracy feedback...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
            self.fields["kpi_definition"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)
            self.fields["conversation_session"].queryset = BiConversationSession.objects.filter(tenant=self.tenant)
        self.fields["semantic_model"].required = False
        self.fields["warehouse_table"].required = False
        self.fields["kpi_definition"].required = False
        self.fields["conversation_session"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["semantic_model", "warehouse_table", "kpi_definition", "conversation_session"],
        )
        return cleaned_data
