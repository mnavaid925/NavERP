"""Projects 7.12 Portfolio & Program Management — PortfolioInvestmentForm.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign
from apps.projects.models.PortfolioProgramManagement.PortfolioInvestments import (
    PortfolioInvestment,
)
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.PortfolioProgramManagement.Programs import Program
from apps.projects.models.ProjectInitiation.Projects import Project


class PortfolioInvestmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PortfolioInvestment
        fields = [
            "portfolio",
            "project",
            "program",
            "status",
            "allocated_budget",
            "strategic_fit",
            "financial_return",
            "delivery_risk",
            "capacity_fit",
            "weight_strategic",
            "weight_financial",
            "weight_risk",
            "weight_capacity",
            "decision_notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["portfolio"].queryset = Portfolio.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["project"].queryset = Project.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["program"].queryset = Program.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["portfolio", "project", "program"])
        portfolio = cleaned.get("portfolio")
        program = cleaned.get("program")
        if portfolio and program and program.portfolio_id != portfolio.id:
            self.add_error("program", "Selected program does not belong to the selected portfolio.")
        return cleaned


class InvestmentDecisionForm(forms.Form):
    allocated_budget = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input"}),
    )
    decision_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        required=False,
    )
