"""Projects 7.19 — ProjectTeam views [PTE-]."""
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.crud import as_db_int
from apps.core.models import OrgUnit
from apps.projects.forms.MasterDataConfiguration.ProjectTeams import (
    ProjectTeamForm,
    ProjectTeamMemberForm,
)
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam, ProjectTeamMember
from apps.projects.models.ResourceManagement.ResourceAllocations import ResourceAllocation
from apps.projects.models.ResourceManagement.ResourceProfiles import ResourceProfile
from apps.projects.views._common import *


@login_required
def pte_list(request):
    """List project teams with matrix structure filters, org unit filtering, and stats."""
    qs = ProjectTeam.objects.filter(tenant=request.tenant).select_related(
        "org_unit", "project", "team_lead"
    ).annotate(
        member_count_annotated=Coalesce(
            Subquery(
                ProjectTeamMember.objects.filter(
                    team_id=OuterRef("pk"),
                    tenant_id=OuterRef("tenant_id"),
                    left_date__isnull=True,
                )
                .values("team")
                .annotate(c=Count("id"))
                .values("c")[:1],
                output_field=IntegerField(),
            ),
            Value(0),
        )
    ).defer("description").order_by("-created_at", "-id")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(number__icontains=q) | Q(location__icontains=q))

    team_type = request.GET.get("team_type", "").strip()
    if team_type:
        qs = qs.filter(team_type=team_type)

    org_unit_id = request.GET.get("org_unit", "").strip()
    org_unit_pk = as_db_int(org_unit_id)
    if org_unit_pk is not None and org_unit_pk > 0:
        qs = qs.filter(org_unit_id=org_unit_pk)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        is_active = "active"
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        is_active = "inactive"
        qs = qs.filter(is_active=False)

    stats = ProjectTeam.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        dedicated=Count("id", filter=Q(team_type="dedicated")),
        matrix=Count("id", filter=Q(team_type="matrix")),
        cross_functional=Count("id", filter=Q(team_type="cross_functional")),
        agile_pod=Count("id", filter=Q(team_type="agile_pod")),
    )

    org_units = OrgUnit.objects.filter(tenant=request.tenant).only(
        "id", "name", "tenant_id"
    ).order_by("name")[:500]

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
            "has_filters": bool(q or team_type or org_unit_id or is_active),
        },
    )


def _team_detail_context(request, team, member_form=None):
    current = ProjectTeamMember.objects.filter(
        team=team,
        tenant=request.tenant,
        left_date__isnull=True,
    ).select_related("user")
    historical = ProjectTeamMember.objects.filter(
        team=team,
        tenant=request.tenant,
        left_date__isnull=False,
    ).select_related("user")
    total_allocation = current.aggregate(total=Sum("allocation_percentage"))["total"] or 0
    members_page = Paginator(current.order_by("-is_primary_contact", "user__username"), 25).get_page(
        request.GET.get("members_page")
    )
    history_page = Paginator(historical.order_by("-left_date", "-id"), 25).get_page(
        request.GET.get("history_page")
    )
    if member_form is None:
        member_form = ProjectTeamMemberForm(
            tenant=request.tenant,
            team=team,
            initial={"joined_date": timezone.localdate()},
        )
    return {
        "team": team,
        "members": members_page.object_list,
        "members_page": members_page,
        "historical_members": history_page.object_list,
        "history_page": history_page,
        "member_form": member_form,
        "total_allocation": total_allocation,
    }


@login_required
def pte_detail(request, pk):
    """View details of a project team and manage allocated members."""
    team = get_object_or_404(
        ProjectTeam.objects.select_related("org_unit", "project", "team_lead"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/masterdataconfiguration/team/detail.html",
        _team_detail_context(request, team),
    )


@login_required
@tenant_admin_required
def pte_create(request):
    """Create a new project team."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectTeamForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            team = form.save(commit=False)
            team.tenant = request.tenant
            with transaction.atomic():
                team.save()
                form.save_custom_values(team, updated_by=request.user)
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
@tenant_admin_required
def pte_edit(request, pk):
    """Edit an existing project team."""
    team = get_object_or_404(ProjectTeam, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectTeamForm(
            request.POST,
            instance=team,
            tenant=request.tenant,
            updated_by=request.user,
        )
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
        form = ProjectTeamForm(
            instance=team,
            tenant=request.tenant,
            updated_by=request.user,
        )

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
@tenant_admin_required
def pte_add_member(request, pk):
    """Add a member to a project team."""
    team = get_object_or_404(ProjectTeam, pk=pk, tenant=request.tenant)
    form = ProjectTeamMemberForm(request.POST, tenant=request.tenant, team=team)
    if form.is_valid():
        try:
            with transaction.atomic():
                member = form.save(commit=False)
                member.tenant = request.tenant
                member.team = team
                member.save()
                if team.project_id:
                    resource = None
                    if member.user.party_id:
                        resource = ResourceProfile.objects.filter(
                            tenant=request.tenant
                        ).filter(
                            Q(party_id=member.user.party_id)
                            | Q(employee__party_id=member.user.party_id)
                        ).first()
                    ResourceAllocation.objects.get_or_create(
                        tenant=request.tenant,
                        project=team.project,
                        role_name=member.get_role_display(),
                        notes=f"Project team membership {member.pk}",
                        defaults={
                            "resource": resource,
                            "allocation_unit": "pct_capacity",
                            "pct_capacity": member.allocation_percentage,
                            "start_date": member.joined_date or timezone.localdate(),
                            "booking_status": "requested",
                            "requested_by": request.user,
                        },
                    )
        except IntegrityError:
            form.add_error("user", "This user was added concurrently; refresh and try again.")
        else:
            write_audit_log(
                user=request.user,
                obj=team,
                action="update",
                changes={"added_member": member.user.username, "role": member.role},
                tenant=request.tenant,
            )
            messages.success(request, f"Added {member.user.username} to {team.name}.")
            return redirect("projects:pte_detail", pk=team.pk)
    return render(
        request,
        "projects/masterdataconfiguration/team/detail.html",
        _team_detail_context(request, team, member_form=form),
    )


@login_required
@require_POST
@tenant_admin_required
def pte_remove_member(request, team_pk, pk):
    """Record a member's departure without destroying team history."""
    team = get_object_or_404(ProjectTeam, pk=team_pk, tenant=request.tenant)
    member = get_object_or_404(ProjectTeamMember, pk=pk, team=team, tenant=request.tenant)
    if member.left_date is not None:
        messages.info(request, "This membership is already historical.")
        return redirect("projects:pte_detail", pk=team.pk)
    with transaction.atomic():
        locked = ProjectTeamMember.objects.select_for_update().get(pk=member.pk)
        if locked.left_date is None:
            locked.left_date = timezone.localdate()
            locked.save(update_fields=["left_date", "updated_at"])
            ResourceAllocation.objects.filter(
                tenant=request.tenant,
                project_id=team.project_id,
                notes=f"Project team membership {locked.pk}",
                booking_status__in=("requested", "soft"),
            ).update(booking_status="cancelled")
            write_audit_log(
                user=request.user,
                obj=team,
                action="update",
                changes={
                    "departed_member": locked.user.username,
                    "left_date": locked.left_date.isoformat(),
                },
                tenant=request.tenant,
            )
    messages.success(request, f"Recorded {member.user.username}'s departure from {team.name}.")
    return redirect("projects:pte_detail", pk=team.pk)
