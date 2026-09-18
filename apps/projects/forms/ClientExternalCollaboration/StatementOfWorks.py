"""Projects 7.14 Client & External Collaboration — StatementOfWork forms.
"""
from apps.accounting.models import Currency
from apps.core.models.Party import Party
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.ClientExternalCollaboration.StatementOfWorks import (
    SOWAmendment,
    StatementOfWork,
)
from apps.projects.models.ProjectInitiation.Projects import Project


class StatementOfWorkForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = StatementOfWork
        fields = [
            "project",
            "client",
            "title",
            "sow_code",
            "billing_type",
            "contract_value",
            "currency",
            "start_date",
            "end_date",
            "status",
            "scope_summary",
            "terms_and_conditions",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["client"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            # currency is global (accounting.Currency has no tenant FK, L29)
            self.fields["currency"].queryset = Currency.objects.all().order_by("code")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "client"])
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "SOW end date must be on or after start date.")
        return cleaned


class SOWAmendmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SOWAmendment
        fields = [
            "sow",
            "amendment_number",
            "title",
            "effective_date",
            "value_change",
            "revised_scope",
            "justification",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["sow"].queryset = StatementOfWork.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["sow"])
        return cleaned
