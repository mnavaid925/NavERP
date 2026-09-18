"""Projects 7.12 — Portfolio & Program Management model tests.

Covers the four 7.12 entities:
- Portfolio [PRT-] (multi-project container, strategic themes, budget envelope)
- Program [PGM-] (sub-portfolio program, target dates, budget targets)
- PortfolioInvestment [PIN-] (4-criteria scoring, OKR alignment, investment governance)
- ProgramDependency [PDEP-] (cross-project dependency, lead/lag, lifecycle)

Naming: every test ``test_portfolio_*``, every helper ``_portfolio_*``.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.projects.models import (
    Portfolio,
    Program,
    PortfolioInvestment,
    ProgramDependency,
    ZERO,
    q2,
)
from apps.projects.tests.conftest import (
    _portfolio_portfolio,
    _portfolio_program,
    _portfolio_investment,
    _portfolio_dependency,
    _projectinitiation_project,
)

pytestmark = pytest.mark.django_db

_NUMBERED_MODELS = [
    (Portfolio, "PRT"),
    (Program, "PGM"),
    (PortfolioInvestment, "PIN"),
    (ProgramDependency, "PDEP"),
]


# ==================================================================================================
# Numbering & Tenant Isolation
# ==================================================================================================

@pytest.mark.parametrize("model,prefix", _NUMBERED_MODELS)
def test_portfolio_number_prefix_is_pinned(model, prefix):
    assert model.NUMBER_PREFIX == prefix


def test_portfolio_numbers_are_per_tenant_not_global(tenant_a, tenant_b):
    p_a = _portfolio_portfolio(tenant_a, name="Portfolio Alpha")
    p_b = _portfolio_portfolio(tenant_b, name="Portfolio Alpha")
    assert p_a.number == p_b.number
    assert p_a.tenant != p_b.tenant


def test_portfolio_number_mints_sequentially(tenant_a):
    p1 = _portfolio_portfolio(tenant_a, name="P1")
    p2 = _portfolio_portfolio(tenant_a, name="P2")
    assert int(p2.number.split("-")[1]) == int(p1.number.split("-")[1]) + 1


# ==================================================================================================
# Portfolio Model Tests
# ==================================================================================================

def test_portfolio_properties_and_str(tenant_a):
    prt = _portfolio_portfolio(tenant_a, name="Innovation Portfolio", budget_envelope=Decimal("1000000.00"))
    assert str(prt) == f"{prt.number} — Innovation Portfolio"
    assert prt.total_programs == 0
    assert prt.total_investments == 0
    assert prt.allocated_budget == ZERO
    assert prt.budget_variance == Decimal("1000000.00")


# ==================================================================================================
# Program Model Tests
# ==================================================================================================

def test_program_properties_and_str(tenant_a, portfolio_a):
    pgm = _portfolio_program(tenant_a, portfolio_a, name="Data Platform Initiative")
    assert str(pgm) == f"{pgm.number} — Data Platform Initiative"
    assert pgm.total_projects == 0
    assert pgm.allocated_budget == ZERO


def test_program_name_unique_per_portfolio_and_tenant(tenant_a, portfolio_a):
    _portfolio_program(tenant_a, portfolio_a, name="Duplicate Program")
    with pytest.raises((IntegrityError, ValidationError)):
        with transaction.atomic():
            _portfolio_program(tenant_a, portfolio_a, name="Duplicate Program")


# ==================================================================================================
# PortfolioInvestment Model Tests
# ==================================================================================================

def test_portfolio_investment_weighted_score(tenant_a, portfolio_a, resource_project):
    inv = _portfolio_investment(
        tenant_a,
        portfolio_a,
        resource_project,
        strategic_fit=100,
        financial_return=80,
        delivery_risk=60,
        capacity_fit=40,
        weight_strategic=25,
        weight_financial=25,
        weight_risk=25,
        weight_capacity=25,
    )
    # (100*25 + 80*25 + 60*25 + 40*25) / 100 = 70.0
    assert inv.weighted_score == Decimal("70.0")


def test_portfolio_investment_clean_rejects_cross_tenant_project(tenant_a, tenant_b, portfolio_a, resource_project_b):
    inv = PortfolioInvestment(
        tenant=tenant_a,
        portfolio=portfolio_a,
        project=resource_project_b,
    )
    with pytest.raises(ValidationError, match="different workspace"):
        inv.clean()


def test_portfolio_investment_clean_rejects_mismatched_program(tenant_a, portfolio_a, resource_project):
    p2 = _portfolio_portfolio(tenant_a, name="Second Portfolio")
    pgm_other = _portfolio_program(tenant_a, p2, name="Other Program")
    inv = PortfolioInvestment(
        tenant=tenant_a,
        portfolio=portfolio_a,
        project=resource_project,
        program=pgm_other,
    )
    with pytest.raises(ValidationError, match="does not belong to the selected portfolio"):
        inv.clean()


def test_portfolio_investment_unique_per_portfolio_project(tenant_a, portfolio_a, resource_project):
    _portfolio_investment(tenant_a, portfolio_a, resource_project)
    with pytest.raises((IntegrityError, ValidationError)):
        with transaction.atomic():
            _portfolio_investment(tenant_a, portfolio_a, resource_project)


# ==================================================================================================
# ProgramDependency Model Tests
# ==================================================================================================

def test_program_dependency_clean_rejects_self_dependency(tenant_a, resource_project):
    dep = ProgramDependency(
        tenant=tenant_a,
        source_project=resource_project,
        target_project=resource_project,
    )
    with pytest.raises(ValidationError, match="cannot have a dependency on itself"):
        dep.clean()


def test_program_dependency_clean_rejects_cross_tenant_projects(tenant_a, tenant_b, resource_project, resource_project_b):
    dep = ProgramDependency(
        tenant=tenant_a,
        source_project=resource_project,
        target_project=resource_project_b,
    )
    with pytest.raises(ValidationError, match="different workspace"):
        dep.clean()


def test_program_dependency_str_and_lifecycle(tenant_a, resource_project):
    p2 = _projectinitiation_project(tenant_a, name="Target Project", code="TGT-01")
    dep = _portfolio_dependency(tenant_a, resource_project, p2)
    assert f"{resource_project.name} → {p2.name}" in str(dep)
