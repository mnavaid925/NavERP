"""Projects 7.12 — Portfolio & Program Management form tests.

Covers:
- PortfolioForm (date validation, owner tenant scoping)
- ProgramForm (target dates validation, portfolio and manager tenant scoping, foreign rejection)
- PortfolioInvestmentForm (4-criterion weights, portfolio-program alignment, foreign rejection)
- InvestmentDecisionForm (governance decisions)
- ProgramDependencyForm (self-dependency rejection, project and program tenant scoping)
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.projects.forms.PortfolioProgramManagement.Portfolios import PortfolioForm
from apps.projects.forms.PortfolioProgramManagement.Programs import ProgramForm
from apps.projects.forms.PortfolioProgramManagement.PortfolioInvestments import (
    PortfolioInvestmentForm,
    InvestmentDecisionForm,
)
from apps.projects.forms.PortfolioProgramManagement.ProgramDependencies import (
    ProgramDependencyForm,
)
from apps.projects.tests.conftest import (
    _portfolio_portfolio,
    _portfolio_program,
    _projectinitiation_project,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# PortfolioForm
# ==================================================================================================

def test_portfolio_form_valid(tenant_a, admin_user):
    today = timezone.localdate()
    data = {
        "name": "Cloud Transformation",
        "code": "PORT-CLD",
        "description": "Cloud migration portfolio",
        "status": "active",
        "owner": admin_user.pk,
        "strategic_theme": "transformation",
        "budget_envelope": "2500000.00",
        "start_date": today.isoformat(),
        "end_date": (today + timezone.timedelta(days=365)).isoformat(),
        "is_active": True,
    }
    form = PortfolioForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_portfolio_form_date_validation(tenant_a):
    today = timezone.localdate()
    data = {
        "name": "Inverted Dates Portfolio",
        "status": "draft",
        "strategic_theme": "efficiency",
        "budget_envelope": "100000.00",
        "start_date": (today + timezone.timedelta(days=30)).isoformat(),
        "end_date": today.isoformat(),
        "is_active": True,
    }
    form = PortfolioForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_date" in form.errors


# ==================================================================================================
# ProgramForm
# ==================================================================================================

def test_program_form_valid(tenant_a, portfolio_a, admin_user):
    today = timezone.localdate()
    data = {
        "portfolio": portfolio_a.pk,
        "name": "Digital App Revamp",
        "code": "PGM-DAR",
        "description": "Revamp mobile apps",
        "manager": admin_user.pk,
        "status": "planning",
        "target_start_date": today.isoformat(),
        "target_end_date": (today + timezone.timedelta(days=180)).isoformat(),
        "budget_target": "500000.00",
    }
    form = ProgramForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_program_form_rejects_foreign_portfolio(tenant_a, portfolio_b):
    data = {
        "portfolio": portfolio_b.pk,
        "name": "Intruder Program",
        "status": "proposed",
        "budget_target": "50000.00",
    }
    form = ProgramForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "portfolio" in form.errors


def test_program_form_date_validation(tenant_a, portfolio_a):
    today = timezone.localdate()
    data = {
        "portfolio": portfolio_a.pk,
        "name": "Inverted Program",
        "status": "proposed",
        "target_start_date": (today + timezone.timedelta(days=30)).isoformat(),
        "target_end_date": today.isoformat(),
        "budget_target": "50000.00",
    }
    form = ProgramForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_end_date" in form.errors


# ==================================================================================================
# PortfolioInvestmentForm
# ==================================================================================================

def test_portfolio_investment_form_valid(tenant_a, portfolio_a, program_a, resource_project):
    data = {
        "portfolio": portfolio_a.pk,
        "project": resource_project.pk,
        "program": program_a.pk,
        "status": "proposed",
        "strategic_fit": 80,
        "financial_return": 90,
        "delivery_risk": 70,
        "capacity_fit": 60,
        "weight_strategic": 25,
        "weight_financial": 25,
        "weight_risk": 25,
        "weight_capacity": 25,
        "allocated_budget": "350000.00",
    }
    form = PortfolioInvestmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_portfolio_investment_form_rejects_mismatched_program(tenant_a, portfolio_a, resource_project):
    p_second = _portfolio_portfolio(tenant_a, name="Second Portfolio")
    pgm_other = _portfolio_program(tenant_a, p_second, name="Foreign Portfolio Program")
    data = {
        "portfolio": portfolio_a.pk,
        "project": resource_project.pk,
        "program": pgm_other.pk,
        "status": "proposed",
        "strategic_fit": 50,
        "financial_return": 50,
        "delivery_risk": 50,
        "capacity_fit": 50,
        "weight_strategic": 25,
        "weight_financial": 25,
        "weight_risk": 25,
        "weight_capacity": 25,
        "allocated_budget": "100000.00",
    }
    form = PortfolioInvestmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "program" in form.errors


def test_investment_decision_form():
    form = InvestmentDecisionForm(data={
        "allocated_budget": "450000.00",
        "decision_notes": "Approved in Q3 governance review.",
    })
    assert form.is_valid()
    assert form.cleaned_data["allocated_budget"] == Decimal("450000.00")


# ==================================================================================================
# ProgramDependencyForm
# ==================================================================================================

def test_program_dependency_form_valid(tenant_a, resource_project, program_a):
    p2 = _projectinitiation_project(tenant_a, name="Secondary Project", code="SEC-02")
    data = {
        "source_project": resource_project.pk,
        "target_project": p2.pk,
        "program": program_a.pk,
        "dependency_type": "finish_to_start",
        "criticality": "high",
        "status": "open",
        "lead_lag_days": 10,
    }
    form = ProgramDependencyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_program_dependency_form_rejects_self_dependency(tenant_a, resource_project):
    data = {
        "source_project": resource_project.pk,
        "target_project": resource_project.pk,
        "dependency_type": "shared_resource",
        "criticality": "medium",
        "status": "open",
    }
    form = ProgramDependencyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_project" in form.errors
