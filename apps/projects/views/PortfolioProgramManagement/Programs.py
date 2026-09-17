"""Projects 7.12 Portfolio & Program Management — Program views.
"""
from apps.projects.forms.PortfolioProgramManagement.Programs import ProgramForm
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.PortfolioProgramManagement.Programs import Program
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def pgm_list(request):
    qs = (
        Program.objects.filter(tenant=request.tenant)
        .select_related("portfolio", "manager")
        .prefetch_related("investments")
    )
    return crud_list(
        request,
        qs,
        "projects/portfolio/program/list.html",
        search_fields=["name", "code", "description"],
        filters=[
            ("status", "status", False),
            ("portfolio", "portfolio_id", True),
        ],
        extra_context={
            "status_choices": Program.STATUS_CHOICES,
            "portfolios": Portfolio.objects.filter(tenant=request.tenant).order_by("name"),
            "total_count": qs.count(),
        },
    )


@login_required
def pgm_create(request):
    initial = {}
    portfolio_id = request.GET.get("portfolio")
    if portfolio_id:
        initial["portfolio"] = portfolio_id

    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = ProgramForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Program {obj.number} created.")
            return redirect("projects:pgm_list")
    else:
        form = ProgramForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "projects/portfolio/program/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def pgm_detail(request, pk):
    program = get_object_or_404(
        Program.objects.select_related("portfolio", "manager"),
        pk=pk,
        tenant=request.tenant,
    )
    investments = program.investments.select_related("project").all()
    dependencies = program.dependencies.select_related(
        "source_project", "target_project", "owner"
    ).all()
    return render(
        request,
        "projects/portfolio/program/detail.html",
        {
            "obj": program,
            "program": program,
            "investments": investments,
            "dependencies": dependencies,
            "allocated_total": program.allocated_budget,
        },
    )


@login_required
def pgm_edit(request, pk):
    return crud_edit(
        request,
        model=Program,
        pk=pk,
        form_class=ProgramForm,
        template="projects/portfolio/program/form.html",
        success_url="projects:pgm_list",
    )


@login_required
@require_POST
def pgm_delete(request, pk):
    return crud_delete(
        request,
        model=Program,
        pk=pk,
        success_url="projects:pgm_list",
    )
