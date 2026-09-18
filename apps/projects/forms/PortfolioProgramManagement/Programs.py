"""Projects 7.12 Portfolio & Program Management — ProgramForm.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.PortfolioProgramManagement.Programs import Program


class ProgramForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Program
        fields = [
            "portfolio",
            "name",
            "code",
            "description",
            "manager",
            "status",
            "target_start_date",
            "target_end_date",
            "objectives",
            "budget_target",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["portfolio"].queryset = Portfolio.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            User = get_user_model()
            self.fields["manager"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["portfolio"])
        start = cleaned.get("target_start_date")
        end = cleaned.get("target_end_date")
        if start and end and start > end:
            self.add_error("target_end_date", "Target end date must be on or after start date.")
        return cleaned
