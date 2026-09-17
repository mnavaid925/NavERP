"""Projects 7.12 Portfolio & Program Management — PortfolioForm.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio


class PortfolioForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Portfolio
        fields = [
            "name",
            "code",
            "description",
            "status",
            "owner",
            "strategic_theme",
            "budget_envelope",
            "currency",
            "start_date",
            "end_date",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            User = get_user_model()
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "End date must be on or after start date.")
        return cleaned
