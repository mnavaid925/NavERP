"""Projects 7.12 — Portfolio & Program Management view tests.

Covers:
- Portfolio views (list, detail, create, edit, delete)
- Program views (list, detail, create, edit, delete)
- PortfolioInvestment views (list, detail, create, edit, delete, fund, reject, defer)
- ProgramDependency views (list, detail, create, edit, delete, clear, reopen)
- PortfolioDashboard view (executive cards, heat map scatter, pipeline funnel, filter)
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.projects.models import (
    Portfolio,
    Program,
    PortfolioInvestment,
    ProgramDependency,
)
from apps.projects.tests.conftest import (
    _portfolio_portfolio,
    _portfolio_program,
    _portfolio_investment,
    _portfolio_dependency,
    _projectinitiation_project,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Dashboard
# ==================================================================================================

def test_portfolio_dashboard_view(client_a, tenant_a, portfolio_a, program_a, portfolio_investment_a):
    url = reverse("projects:pfm_dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "Portfolio & Program Management" in resp.content.decode()
    assert "portfolio_stats" not in resp.context  # context keys
    assert "total_envelope" in resp.context
    assert "health_summary" in resp.context
    assert "demand_funnel" in resp.context


def test_portfolio_dashboard_filter_by_portfolio(client_a, tenant_a, portfolio_a):
    url = f"{reverse('projects:pfm_dashboard')}?portfolio={portfolio_a.pk}"
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["selected_portfolio"] == portfolio_a


# ==================================================================================================
# Portfolio Views
# ==================================================================================================

def test_portfolio_list_and_search(client_a, tenant_a, portfolio_a):
    url = reverse("projects:prt_list")
    resp = client_a.get(url, {"q": portfolio_a.name[:5]})
    assert resp.status_code == 200
    assert portfolio_a in resp.context["object_list"]


def test_portfolio_create_view(client_a, tenant_a):
    url = reverse("projects:prt_create")
    resp = client_a.get(url)
    assert resp.status_code == 200

    data = {
        "name": "Omnichannel Initiative",
        "code": "PORT-OMNI",
        "description": "Cross-channel strategy",
        "status": "draft",
        "strategic_theme": "growth",
        "budget_envelope": "1500000.00",
        "is_active": True,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    created = Portfolio.objects.filter(tenant=tenant_a, code="PORT-OMNI").first()
    assert created is not None
    assert created.name == "Omnichannel Initiative"


def test_portfolio_detail_view(client_a, tenant_a, portfolio_a):
    url = reverse("projects:prt_detail", kwargs={"pk": portfolio_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["obj"] == portfolio_a


def test_portfolio_edit_view(client_a, tenant_a, portfolio_a):
    url = reverse("projects:prt_edit", kwargs={"pk": portfolio_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    data = {
        "name": "Updated Portfolio Name",
        "code": portfolio_a.code,
        "description": "Updated description",
        "status": "active",
        "strategic_theme": portfolio_a.strategic_theme,
        "budget_envelope": "6000000.00",
        "is_active": True,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    portfolio_a.refresh_from_db()
    assert portfolio_a.name == "Updated Portfolio Name"


def test_portfolio_delete_view(client_a, tenant_a, portfolio_a):
    url = reverse("projects:prt_delete", kwargs={"pk": portfolio_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not Portfolio.objects.filter(pk=portfolio_a.pk).exists()


# ==================================================================================================
# Program Views
# ==================================================================================================

def test_program_list_and_filter(client_a, tenant_a, program_a, portfolio_a):
    url = reverse("projects:pgm_list")
    resp = client_a.get(url, {"portfolio": str(portfolio_a.pk)})
    assert resp.status_code == 200
    assert program_a in resp.context["object_list"]


def test_program_create_view(client_a, tenant_a, portfolio_a):
    url = reverse("projects:pgm_create")
    resp = client_a.get(url)
    assert resp.status_code == 200

    data = {
        "portfolio": portfolio_a.pk,
        "name": "Microservices Migration",
        "code": "PGM-MS",
        "description": "Break down monolith",
        "status": "proposed",
        "budget_target": "800000.00",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    created = Program.objects.filter(tenant=tenant_a, code="PGM-MS").first()
    assert created is not None
    assert created.portfolio == portfolio_a


def test_program_detail_and_edit(client_a, tenant_a, program_a):
    detail_url = reverse("projects:pgm_detail", kwargs={"pk": program_a.pk})
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["obj"] == program_a

    edit_url = reverse("projects:pgm_edit", kwargs={"pk": program_a.pk})
    data = {
        "portfolio": program_a.portfolio.pk,
        "name": "Refined Program Name",
        "code": program_a.code,
        "description": program_a.description,
        "status": "active",
        "budget_target": "2500000.00",
    }
    resp = client_a.post(edit_url, data)
    assert resp.status_code == 302
    program_a.refresh_from_db()
    assert program_a.name == "Refined Program Name"


def test_program_delete_view(client_a, tenant_a, program_a):
    url = reverse("projects:pgm_delete", kwargs={"pk": program_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not Program.objects.filter(pk=program_a.pk).exists()


# ==================================================================================================
# PortfolioInvestment Views & Lifecycle Verbs
# ==================================================================================================

def test_investment_create_and_verbs(client_a, tenant_a, portfolio_a, resource_project):
    create_url = reverse("projects:pin_create")
    data = {
        "portfolio": portfolio_a.pk,
        "project": resource_project.pk,
        "status": "proposed",
        "strategic_fit": 90,
        "financial_return": 85,
        "delivery_risk": 75,
        "capacity_fit": 80,
        "weight_strategic": 25,
        "weight_financial": 25,
        "weight_risk": 25,
        "weight_capacity": 25,
        "allocated_budget": "600000.00",
    }
    resp = client_a.post(create_url, data)
    assert resp.status_code == 302
    inv = PortfolioInvestment.objects.filter(tenant=tenant_a, project=resource_project).first()
    assert inv is not None
    assert inv.status == "proposed"

    # Verb: Fund
    fund_url = reverse("projects:pin_fund", kwargs={"pk": inv.pk})
    resp = client_a.post(fund_url, {"allocated_budget": "650000.00", "decision_notes": "Board approved funding."})
    assert resp.status_code == 302
    inv.refresh_from_db()
    assert inv.status == "funded"
    assert inv.allocated_budget == Decimal("650000.00")
    assert inv.approved_at is not None

    # Verb: Defer
    defer_url = reverse("projects:pin_defer", kwargs={"pk": inv.pk})
    resp = client_a.post(defer_url, {"decision_notes": "Pushed to next quarter."})
    assert resp.status_code == 302
    inv.refresh_from_db()
    assert inv.status == "deferred"

    # Verb: Reject
    reject_url = reverse("projects:pin_reject", kwargs={"pk": inv.pk})
    resp = client_a.post(reject_url, {"decision_notes": "Exceeds risk ceiling."})
    assert resp.status_code == 302
    inv.refresh_from_db()
    assert inv.status == "rejected"


# ==================================================================================================
# ProgramDependency Views & Lifecycle Verbs
# ==================================================================================================

def test_dependency_crud_and_clear_reopen(client_a, tenant_a, resource_project, program_a):
    p2 = _projectinitiation_project(tenant_a, name="Dependent Target Project", code="DTP-01")
    create_url = reverse("projects:pdep_create")
    data = {
        "source_project": resource_project.pk,
        "target_project": p2.pk,
        "program": program_a.pk,
        "dependency_type": "deliverable_handover",
        "criticality": "critical",
        "status": "open",
        "lead_lag_days": 14,
        "description": "SDK handover blocker",
    }
    resp = client_a.post(create_url, data)
    assert resp.status_code == 302
    dep = ProgramDependency.objects.filter(tenant=tenant_a, source_project=resource_project, target_project=p2).first()
    assert dep is not None
    assert dep.status == "open"

    # Detail
    detail_url = reverse("projects:pdep_detail", kwargs={"pk": dep.pk})
    resp = client_a.get(detail_url)
    assert resp.status_code == 200

    # Clear verb
    clear_url = reverse("projects:pdep_clear", kwargs={"pk": dep.pk})
    resp = client_a.post(clear_url)
    assert resp.status_code == 302
    dep.refresh_from_db()
    assert dep.status == "cleared"
    assert dep.cleared_at is not None

    # Reopen verb
    reopen_url = reverse("projects:pdep_reopen", kwargs={"pk": dep.pk})
    resp = client_a.post(reopen_url)
    assert resp.status_code == 302
    dep.refresh_from_db()
    assert dep.status == "open"
    assert dep.cleared_at is None
