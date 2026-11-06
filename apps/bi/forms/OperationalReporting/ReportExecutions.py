from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportExecutions import ReportExecution
from apps.core.forms import TenantModelForm


class ReportExecutionRunForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReportExecution
        fields = [
            "execution_mode",
            "output_format",
        ]
        widgets = {
            "execution_mode": forms.Select(attrs={"class": "form-select"}),
            "output_format": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data
