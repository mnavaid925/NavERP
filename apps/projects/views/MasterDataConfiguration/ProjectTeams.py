"""Projects 7.19 — ProjectTeam views [PTE-]."""
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum

from apps.core.models import OrgUnit
from apps.projects.forms.MasterDataConfiguration.ProjectTeams import (
    ProjectTeamForm,
    ProjectTeamMemberForm,
)
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam, ProjectTeamMember
from apps.projects.views._common import *


@login_required
def pte_list(request):
    """List project teams with matrix structure filters, org unit filtering, and stats."""
    qs = ProjectTeam.objects.filter(tenant=request.tenant).select_related(
        "org_unit", "project", "team_lead"
    ).annotate(member_count_annotated=Count("members"))

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(number__icontains=q) | Q(location__icontains=q))

    team_type = request.GET.get("team_type", "").strip()
    if team_type:
        qs = qs.filter(team_type=team_type)

    org_unit_id = request.GET.get("org_unit", "").strip()
    if org_unit_id and org_unit_id.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_id))

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        qs = qs.filter(is_active=False)

    stats = ProjectTeam.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        dedicated=Count("id", filter=Q(team_type="dedicated")),
        matrix=Count("id", filter=Q(team_type="matrix")),
        cross_functional=Count("id", filter=Q(team_type="cross_functional")),
        agile_pod=Count("id", filter=Q(team_type="agile_pod")),
    )

    org_units = OrgUnit.objects.filter(tenant=request.tenant, is_active=True).order_by("name")

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/masterdataconfiguration/team/list.html",
        {
            "teams": page_obj.object_list,
            "page_obj": page_obj,
            "team_type_choices": ProjectTeam.TEAM_TYPE_CHOICES,
            "org_units": org_units,
            "q": q,
            "team_type": team_type,
            "org_unit_id": org_unit_id,
            "is_active": is_active,
            "stats": stats,
        },
    )


@login_required
def pte_detail(request, pk):
    """View details of a project team and manage allocated members."""
    team = get_object_or_404(
        ProjectTeam.objects.select_related("org_unit", "project", "team_lead"),
        pk=pk,
        tenant=request.tenant,
    )
    members = ProjectTeamMember.objects.filter(
        team=team, tenant=request.tenant
    ).select_related("user")

    total_allocation = members.aggregate(total=Sum("allocation_percentage"))["total"] or 0
    member_form = ProjectTeamMemberForm(tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/team/detail.html",
        {
            "team": team,
            "members": members,
            "member_form": member_form,
            "total_allocation": total_allocation,
        },
    )


@login_required
def pte_create(request):
    """Create a new project team."""
    if request.method == "POST":
        form = ProjectTeamForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            team = form.save(commit=False)
            team.tenant = request.tenant
            team.save()
            write_audit_log(
                user=request.user,
                obj=team,
                action="create",
                changes={"name": team.name, "team_type": team.team_type},
                tenant=request.tenant,
            )
            messages.success(request, f"Project team '{team.name}' created successfully.")
            return redirect("projects:pte_detail", pk=team.pk)
    else:
        form = ProjectTeamForm(tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/team/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def pte_edit(request, pk):
    """Edit an existing project team."""
    team = get_object_or_404(ProjectTeam, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectTeamForm(request.POST, instance=team, tenant=request.tenant)
        if form.is_valid():
            team = form.save()
            write_audit_log(
                user=request.user,
                obj=team,
                action="update",
                changes={"name": team.name, "team_type": team.team_type},
                tenant=request.tenant,
            )
            messages.success(request, f"Project team '{team.name}' updated successfully.")
            return redirect("projects:pte_detail", pk=team.pk)
    else:
        form = ProjectTeamForm(instance=team, tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/team/form.html",
        {
            "form": form,
            "team": team,
            "is_edit": True,
        },
    )


@login_required
@require_POST
@tenant_admin_required
def pte_delete(request, pk):
    """Delete a project team."""
    team = get_object_or_404(ProjectTeam, pk=pk, tenant=request.tenant)
    name = team.name
    write_audit_log(
        user=request.user,
        obj=team,
        action="delete",
        changes={"name": name},
        tenant=request.tenant,
    )
    team.delete()
    messages.success(request, f"Project team '{name}' deleted successfully.")
    return redirect("projects:pte_list")


@login_required
@require_POST
def pte_add_member(request, pk):
    """Add a member to a project team."""
    team = get_object_or_404(ProjectTeam, pk=pk, tenant=request.tenant)
    form = ProjectTeamMemberForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        member = form.save(commit=False)
        member.tenant = request.tenant
        member.team = team
        member.save()
        write_audit_log(
            user=request.user,
            obj=team,
            action="update",
            changes={"added_member": member.user.username, "role": member.role},
            tenant=request.tenant,
        )
        messages.success(request, f"Added {member.user.username} to {team.name}.")
    else:
        for err in form.errors.values():
            messages.error(request, err.as_text())

    return redirect("projects:pte_detail", pk=team.pk)


@login_required
@require_POST
def pte_remove_member(request, team_pk, pk):
    """Remove a member from a project team."""
    team = get_object_or_404(ProjectTeam, pk=team_pk, tenant=request.tenant)
    member = get_object_or_404(ProjectTeamMember, pk=pk, team=team, tenant=request.tenant)
    username = member.user.username
    member.delete()
    write_audit_log(
        user=request.user,
        obj=team,
        action="update",
        changes={"removed_member": username},
        tenant=request.tenant,
    )
    messages.success(request, f"Removed {username} from {team.name}.")
    return redirect("projects:pte_detail", pk=team.pk)
