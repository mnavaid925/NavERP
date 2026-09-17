"""Projects 7.12 Portfolio & Program Management — PortfolioInvestment views.
"""
from apps.projects.forms.PortfolioProgramManagement.PortfolioInvestments import (
    InvestmentDecisionForm,
    PortfolioInvestmentForm,
)
from apps.projects.models.PortfolioProgramManagement.PortfolioInvestments import (
    PortfolioInvestment,
)
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.PortfolioProgramManagement.Programs import Program
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def pin_list(request):
    qs = (
        PortfolioInvestment.objects.filter(tenant=request.tenant)
        .select_related("portfolio", "project", "program")
    )
    return crud_list(
        request,
        qs,
        "projects/portfolio/investment/list.html",
        search_fields=["number", "project__name", "project__code", "portfolio__name"],
        filters=[
            ("status", "status", False),
            ("portfolio", "portfolio_id", True),
            ("program", "program_id", True),
        ],
        extra_context={
            "status_choices": PortfolioInvestment.STATUS_CHOICES,
            "portfolios": Portfolio.objects.filter(tenant=request.tenant).order_by("name"),
            "programs": Program.objects.filter(tenant=request.tenant).order_by("name"),
            "total_count": qs.count(),
        },
    )


@login_required
def pin_create(request):
    initial = {}
    portfolio_id = request.GET.get("portfolio")
    program_id = request.GET.get("program")
    if portfolio_id:
        initial["portfolio"] = portfolio_id
    if program_id:
        initial["program"] = program_id

    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = PortfolioInvestmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Investment {obj.number} created.")
            return redirect("projects:pin_list")
    else:
        form = PortfolioInvestmentForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "projects/portfolio/investment/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def pin_detail(request, pk):
    obj = get_object_or_404(
        PortfolioInvestment.objects.select_related(
            "portfolio", "project", "program", "approved_by"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    decision_form = InvestmentDecisionForm(
        initial={
            "allocated_budget": obj.allocated_budget,
            "decision_notes": obj.decision_notes,
        }
    )
    return render(
        request,
        "projects/portfolio/investment/detail.html",
        {
            "obj": obj,
            "investment": obj,
            "decision_form": decision_form,
        },
    )


@login_required
def pin_edit(request, pk):
    return crud_edit(
        request,
        model=PortfolioInvestment,
        pk=pk,
        form_class=PortfolioInvestmentForm,
        template="projects/portfolio/investment/form.html",
        success_url="projects:pin_list",
    )


@login_required
@require_POST
def pin_delete(request, pk):
    return crud_delete(
        request,
        model=PortfolioInvestment,
        pk=pk,
        success_url="projects:pin_list",
    )


@login_required
@require_POST
def pin_fund(request, pk):
    obj = get_object_or_404(PortfolioInvestment, pk=pk, tenant=request.tenant)
    form = InvestmentDecisionForm(request.POST)
    if form.is_valid():
        allocated = form.cleaned_data.get("allocated_budget")
        notes = form.cleaned_data.get("decision_notes")
        if allocated is not None:
            obj.allocated_budget = allocated
        if notes:
            obj.decision_notes = notes
    obj.status = "funded"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save()
    write_audit_log(request.user, obj, "fund")
    messages.success(request, f"Investment {obj.number} approved and funded.")
    return redirect("projects:pin_detail", pk=obj.pk)


@login_required
@require_POST
def pin_reject(request, pk):
    obj = get_object_or_404(PortfolioInvestment, pk=pk, tenant=request.tenant)
    form = InvestmentDecisionForm(request.POST)
    if form.is_valid() and form.cleaned_data.get("decision_notes"):
        obj.decision_notes = form.cleaned_data.get("decision_notes")
    obj.status = "rejected"
    obj.save()
    write_audit_log(request.user, obj, "reject")
    messages.warning(request, f"Investment {obj.number} rejected.")
    return redirect("projects:pin_detail", pk=obj.pk)


@login_required
@require_POST
def pin_defer(request, pk):
    obj = get_object_or_404(PortfolioInvestment, pk=pk, tenant=request.tenant)
    form = InvestmentDecisionForm(request.POST)
    if form.is_valid() and form.cleaned_data.get("decision_notes"):
        obj.decision_notes = form.cleaned_data.get("decision_notes")
    obj.status = "deferred"
    obj.save()
    write_audit_log(request.user, obj, "defer")
    messages.info(request, f"Investment {obj.number} deferred.")
    return redirect("projects:pin_detail", pk=obj.pk)
