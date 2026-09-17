"""Projects 7.12 Portfolio & Program Management — PortfolioDashboard view.

Realizes NavERP 7.12 bullet 1 Portfolio Dashboard & Heat Maps,
bullet 4 Capacity & Pipeline Planning, and bullet 5 Portfolio Reporting & Governance.
"""
from django.db.models import Count, Q, Sum

from apps.core.crud import as_db_int
from apps.projects.models._base import ZERO, q2
from apps.projects.models.PortfolioProgramManagement.PortfolioInvestments import (
    PortfolioInvestment,
)
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.PortfolioProgramManagement.ProgramDependencies import (
    ProgramDependency,
)
from apps.projects.models.PortfolioProgramManagement.Programs import Program
from apps.projects.models.ProjectInitiation.ProjectRequests import ProjectRequest
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def pfm_dashboard(request):
    tenant = request.tenant
    portfolios = Portfolio.objects.filter(tenant=tenant).order_by("name")
    selected_portfolio_id = as_db_int(request.GET.get("portfolio"))

    portfolios_qs = Portfolio.objects.filter(tenant=tenant)
    programs_qs = Program.objects.filter(tenant=tenant)
    investments_qs = PortfolioInvestment.objects.filter(tenant=tenant).select_related(
        "project", "portfolio", "program"
    )
    dependencies_qs = ProgramDependency.objects.filter(tenant=tenant).select_related(
        "source_project", "target_project", "program"
    )
    requests_qs = ProjectRequest.objects.filter(tenant=tenant)

    selected_portfolio = None
    if selected_portfolio_id:
        selected_portfolio = portfolios.filter(pk=selected_portfolio_id).first()
        if selected_portfolio:
            programs_qs = programs_qs.filter(portfolio=selected_portfolio)
            investments_qs = investments_qs.filter(portfolio=selected_portfolio)
            dependencies_qs = dependencies_qs.filter(
                Q(program__portfolio=selected_portfolio)
                | Q(source_project__portfolio_investments__portfolio=selected_portfolio)
                | Q(target_project__portfolio_investments__portfolio=selected_portfolio)
            ).distinct()

    # Financial envelopes
    total_envelope = (
        portfolios_qs.aggregate(s=Sum("budget_envelope"))["s"] or ZERO
        if not selected_portfolio
        else selected_portfolio.budget_envelope
    )
    total_allocated = (
        investments_qs.filter(status="funded").aggregate(s=Sum("allocated_budget"))["s"]
        or ZERO
    )
    total_variance = q2(total_envelope - total_allocated)

    # Health summary derived from member projects
    project_status_counts = investments_qs.values("project__status").annotate(
        count=Count("id")
    )
    health_summary = {
        "active": 0,
        "completed": 0,
        "on_hold": 0,
        "draft": 0,
        "other": 0,
    }
    for row in project_status_counts:
        st = row["project__status"]
        c = row["count"]
        if st in health_summary:
            health_summary[st] += c
        else:
            health_summary["other"] += c

    # Demand funnel over 7.1 ProjectRequests
    funnel_counts = requests_qs.values("status").annotate(count=Count("id"))
    demand_funnel = {row["status"]: row["count"] for row in funnel_counts}

    # Quadrant data
    quadrant_items = []
    for inv in investments_qs[:40]:
        quadrant_items.append(
            {
                "name": inv.project.name,
                "number": inv.number,
                "x": inv.strategic_fit,
                "y": inv.financial_return,
                "risk": inv.delivery_risk,
                "score": float(inv.weighted_score),
                "status": inv.status,
                "budget": float(inv.allocated_budget),
                "pk": inv.pk,
            }
        )

    # Prioritized investments sorted by weighted score
    all_invs = list(investments_qs)
    sorted_investments = sorted(
        all_invs, key=lambda i: i.weighted_score, reverse=True
    )[:15]

    # Theme distribution
    theme_distribution = portfolios_qs.values("strategic_theme").annotate(
        count=Count("id"),
        total_budget=Sum("budget_envelope"),
    )

    ctx = {
        "portfolios": portfolios,
        "selected_portfolio": selected_portfolio,
        "total_envelope": total_envelope,
        "total_allocated": total_allocated,
        "total_variance": total_variance,
        "total_programs": programs_qs.count(),
        "total_investments": investments_qs.count(),
        "funded_investments": investments_qs.filter(status="funded").count(),
        "open_dependencies": dependencies_qs.filter(status="open").count(),
        "health_summary": health_summary,
        "demand_funnel": demand_funnel,
        "quadrant_items": quadrant_items,
        "sorted_investments": sorted_investments,
        "theme_distribution": theme_distribution,
        "recent_dependencies": dependencies_qs[:10],
    }
    return render(request, "projects/portfolio/dashboard.html", ctx)
