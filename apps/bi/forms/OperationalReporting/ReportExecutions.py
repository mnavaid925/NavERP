from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportExecutions import ReportExecution
from apps.core.forms import TenantModelForm


class ReportExecutionRunForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReportExecution
        fields = [
            "report",
            "execution_mode",
            "output_format",
        ]
        widgets = {
            "report": forms.Select(attrs={"class": "form-select"}),
            "execution_mode": forms.Select(attrs={"class": "form-select"}),
            "output_format": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["report"].queryset = ReportDefinition.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["report"])
        return cleaned_data
