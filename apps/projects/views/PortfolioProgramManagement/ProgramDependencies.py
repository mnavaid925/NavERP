"""Projects 7.12 Portfolio & Program Management — ProgramDependency views.
"""
from apps.projects.forms.PortfolioProgramManagement.ProgramDependencies import (
    ProgramDependencyForm,
)
from apps.projects.models.PortfolioProgramManagement.ProgramDependencies import (
    ProgramDependency,
)
from apps.projects.models.PortfolioProgramManagement.Programs import Program
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def pdep_list(request):
    qs = (
        ProgramDependency.objects.filter(tenant=request.tenant)
        .select_related("source_project", "target_project", "program", "owner")
    )
    return crud_list(
        request,
        qs,
        "projects/portfolio/dependency/list.html",
        search_fields=[
            "number",
            "source_project__name",
            "target_project__name",
            "description",
        ],
        filters=[
            ("status", "status", False),
            ("criticality", "criticality", False),
            ("dependency_type", "dependency_type", False),
            ("program", "program_id", True),
        ],
        extra_context={
            "status_choices": ProgramDependency.STATUS_CHOICES,
            "criticality_choices": ProgramDependency.CRITICALITY_CHOICES,
            "type_choices": ProgramDependency.DEPENDENCY_TYPE_CHOICES,
            "programs": Program.objects.filter(tenant=request.tenant).order_by("name"),
            "total_count": qs.count(),
        },
    )


@login_required
def pdep_create(request):
    initial = {}
    program_id = request.GET.get("program")
    if program_id:
        initial["program"] = program_id

    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = ProgramDependencyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Dependency {obj.number} created.")
            return redirect("projects:pdep_list")
    else:
        form = ProgramDependencyForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "projects/portfolio/dependency/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def pdep_detail(request, pk):
    return crud_detail(
        request,
        model=ProgramDependency,
        pk=pk,
        template="projects/portfolio/dependency/detail.html",
        select_related=("source_project", "target_project", "program", "owner"),
    )


@login_required
def pdep_edit(request, pk):
    return crud_edit(
        request,
        model=ProgramDependency,
        pk=pk,
        form_class=ProgramDependencyForm,
        template="projects/portfolio/dependency/form.html",
        success_url="projects:pdep_list",
    )


@login_required
@require_POST
def pdep_delete(request, pk):
    return crud_delete(
        request,
        model=ProgramDependency,
        pk=pk,
        success_url="projects:pdep_list",
    )


@login_required
@require_POST
def pdep_clear(request, pk):
    obj = get_object_or_404(ProgramDependency, pk=pk, tenant=request.tenant)
    obj.status = "cleared"
    obj.cleared_at = timezone.now()
    obj.save()
    write_audit_log(request.user, obj, "clear")
    messages.success(request, f"Dependency {obj.number} marked cleared.")
    return redirect("projects:pdep_detail", pk=obj.pk)


@login_required
@require_POST
def pdep_reopen(request, pk):
    obj = get_object_or_404(ProgramDependency, pk=pk, tenant=request.tenant)
    obj.status = "open"
    obj.cleared_at = None
    obj.save()
    write_audit_log(request.user, obj, "reopen")
    messages.info(request, f"Dependency {obj.number} reopened.")
    return redirect("projects:pdep_detail", pk=obj.pk)
