"""Projects 7.12 Portfolio & Program Management — Portfolio views.
"""
from apps.projects.forms.PortfolioProgramManagement.Portfolios import PortfolioForm
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def prt_list(request):
    qs = (
        Portfolio.objects.filter(tenant=request.tenant)
        .select_related("owner", "currency")
        .prefetch_related("programs", "investments")
    )
    return crud_list(
        request,
        qs,
        "projects/portfolio/portfolio/list.html",
        search_fields=["name", "code", "description"],
        filters=[
            ("status", "status", False),
            ("strategic_theme", "strategic_theme", False),
        ],
        extra_context={
            "status_choices": Portfolio.STATUS_CHOICES,
            "theme_choices": Portfolio.STRATEGIC_THEME_CHOICES,
            "total_count": qs.count(),
        },
    )


@login_required
def prt_create(request):
    return crud_create(
        request,
        form_class=PortfolioForm,
        template="projects/portfolio/portfolio/form.html",
        success_url="projects:prt_list",
    )


@login_required
def prt_detail(request, pk):
    portfolio = get_object_or_404(
        Portfolio.objects.select_related("owner", "currency"),
        pk=pk,
        tenant=request.tenant,
    )
    programs = portfolio.programs.select_related("manager").all()
    investments = portfolio.investments.select_related("project", "program").all()
    return render(
        request,
        "projects/portfolio/portfolio/detail.html",
        {
            "obj": portfolio,
            "portfolio": portfolio,
            "programs": programs,
            "investments": investments,
            "allocated_total": portfolio.allocated_budget,
            "budget_variance": portfolio.budget_variance,
        },
    )


@login_required
def prt_edit(request, pk):
    return crud_edit(
        request,
        model=Portfolio,
        pk=pk,
        form_class=PortfolioForm,
        template="projects/portfolio/portfolio/form.html",
        success_url="projects:prt_list",
    )


@login_required
@require_POST
def prt_delete(request, pk):
    return crud_delete(
        request,
        model=Portfolio,
        pk=pk,
        success_url="projects:prt_list",
    )
