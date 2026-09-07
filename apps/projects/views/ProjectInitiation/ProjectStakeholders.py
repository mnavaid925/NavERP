"""Projects 7.1 — ProjectStakeholder views: the RACI register.

The list keeps the influence/interest POWER RANKING the grid exists to show, without
``Meta.ordering`` doing it: ``influence`` is a CharField, so ``"-influence"`` sorts alphabetically
(medium → low → high) — the exact inverse of what is wanted. The view annotates a numeric rank
and orders by that instead, which also leaves ``Meta.ordering`` deterministic for every other
consumer.
"""
from django.db.models import Case, IntegerField, Value, When

from apps.projects.forms import ProjectStakeholderForm
from apps.projects.models import ProjectStakeholder
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, redirect, render
from apps.projects.views._helpers import projects


@login_required
def pst_list(request):
    rank = Case(
        When(influence="high", then=Value(3)),
        When(influence="medium", then=Value(2)),
        default=Value(1),
        output_field=IntegerField(),
    )
    qs = (ProjectStakeholder.objects.filter(tenant=request.tenant)
          .select_related("project", "party", "user")
          .annotate(influence_rank=rank)
          .order_by("-influence_rank", "id"))
    return crud_list(
        request, qs, "projects/initiation/projectstakeholder/list.html",
        search_fields=["number", "raci_scope", "notes"],
        filters=[("project", "project_id", True),
                 ("stakeholder_type", "stakeholder_type", False),
                 ("raci_role", "raci_role", False),
                 ("influence", "influence", False),
                 ("interest", "interest", False)],
        extra_context={
            "projects": projects(request.tenant),
            "stakeholder_type_choices": ProjectStakeholder.STAKEHOLDER_TYPE_CHOICES,
            "raci_role_choices": ProjectStakeholder.RACI_ROLE_CHOICES,
            "influence_choices": ProjectStakeholder.INFLUENCE_CHOICES,
            "interest_choices": ProjectStakeholder.INTEREST_CHOICES,
        },
    )


@login_required
def pst_create(request):
    # FIRST LINE, not inside `if form.is_valid()`: a tenant-less user (User.tenant is SET_NULL,
    # so any member of a deleted tenant, not just the superuser) must never reach the form. GET
    # skips the POST branch entirely, and TenantModelForm only scopes its FK dropdowns when
    # tenant is not None — so the un-hoisted guard rendered every workspace's parties, org units,
    # documents and user emails. Same shape as apps/core/crud.py's crud_create.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectStakeholderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Stakeholder {obj.number} added.")
            return redirect("projects:pst_detail", pk=obj.pk)
    else:
        # ?project=<pk> pre-selects the project when the register is entered from a charter.
        form = ProjectStakeholderForm(tenant=request.tenant, initial={
            "project": request.GET.get("project", "")})
    return render(request, "projects/initiation/projectstakeholder/form.html",
                  {"form": form, "is_edit": False})


@login_required
def pst_detail(request, pk):
    obj = get_object_or_404(
        ProjectStakeholder.objects.select_related("project", "party", "user"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/initiation/projectstakeholder/detail.html", {"obj": obj})


@login_required
def pst_edit(request, pk):
    return crud_edit(
        request, model=ProjectStakeholder, pk=pk, form_class=ProjectStakeholderForm,
        template="projects/initiation/projectstakeholder/form.html",
        success_url="projects:pst_list",
    )


@login_required
@require_POST
def pst_delete(request, pk):
    return crud_delete(request, model=ProjectStakeholder, pk=pk,
                       success_url="projects:pst_list")
