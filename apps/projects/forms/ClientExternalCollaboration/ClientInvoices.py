"""Projects 7.14 Client & External Collaboration — ProjectClientInvoice forms.
"""
from apps.accounting.models import Currency
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.ClientExternalCollaboration.ClientInvoices import ProjectClientInvoice
from apps.projects.models.ClientExternalCollaboration.StatementOfWorks import StatementOfWork
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ProjectPlanningScheduling.ProjectMilestones import ProjectMilestone


class ProjectClientInvoiceForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectClientInvoice
        fields = [
            "project",
            "sow",
            "milestone",
            "billing_type",
            "billing_date",
            "due_date",
            "currency",
            "amount",
            "tax_amount",
            "status",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["sow"].queryset = StatementOfWork.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["milestone"].queryset = ProjectMilestone.objects.filter(
                tenant=self.tenant
            ).order_by("target_date")
            self.fields["currency"].queryset = Currency.objects.all().order_by("code")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "sow", "milestone"])
        bdate = cleaned.get("billing_date")
        ddate = cleaned.get("due_date")
        if bdate and ddate and bdate > ddate:
            self.add_error("due_date", "Due date must be on or after billing date.")
        return cleaned
