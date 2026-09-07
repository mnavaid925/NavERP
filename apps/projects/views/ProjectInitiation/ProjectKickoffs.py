"""Projects 7.1 — ProjectKickoff views: the launch ceremony.

Four verbs, all POST-only. Two of them advance the PROJECT's status as a side effect
(``mark-held`` ⇒ project `kickoff`, ``complete`` ⇒ project `active`), which is the point of the
ceremony: a project is not "active" because someone typed it, it becomes active because the
kickoff that started it was held and closed out.

``complete`` therefore refuses a kickoff that was never ``held`` AND a project whose charter is
not ``approved``: without both gates a member could go create-project → create-kickoff → Complete
and land an `active` project on a draft charter, routing around the ``@tenant_admin_required`` on
``prj_approve_charter``.

``baseline`` stamps an acknowledgement only — the baseline RECORD (the frozen schedule) is 7.2's.
"""
from django.contrib.contenttypes.models import ContentType

from apps.projects.forms import ProjectKickoffForm
from apps.projects.models import Project, ProjectKickoff
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, redirect, render


def _projects(tenant):
    if tenant is None:
        return Project.objects.none()
    return Project.objects.filter(tenant=tenant).order_by("name")


def _activities(project):
    """The project's `core.Activity` rows — the kickoff meeting plus the onboarding items.

    Read-only here; capturing individual items is 7.9's. Rendered on the kickoff detail page so
    the ceremony and its follow-up checklist are on one screen.
    """
    from apps.core.models import Activity
    if project is None:
        return Activity.objects.none()
    return (Activity.objects
            .filter(tenant=project.tenant_id,
                    content_type=ContentType.objects.get_for_model(Project),
                    object_id=project.pk)
            .select_related("owner", "party")
            .order_by("status", "-due_at"))


@login_required
def pko_list(request):
    qs = (ProjectKickoff.objects.filter(tenant=request.tenant)
          .select_related("project"))
    return crud_list(
        request, qs, "projects/initiation/projectkickoff/list.html",
        search_fields=["number", "location_or_link", "agenda"],
        filters=[("project", "project_id", True),
                 ("status", "status", False),
                 ("agenda_template", "agenda_template", False)],
        extra_context={
            "projects": _projects(request.tenant),
            "status_choices": ProjectKickoff.STATUS_CHOICES,
            "agenda_template_choices": ProjectKickoff.AGENDA_TEMPLATE_CHOICES,
        },
    )


@login_required
def pko_create(request):
    # FIRST LINE, not inside `if form.is_valid()`: a tenant-less user (User.tenant is SET_NULL,
    # so any member of a deleted tenant, not just the superuser) must never reach the form. GET
    # skips the POST branch entirely, and TenantModelForm only scopes its FK dropdowns when
    # tenant is not None — so the un-hoisted guard rendered every workspace's parties, org units,
    # documents and user emails. Same shape as apps/core/crud.py's crud_create.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectKickoffForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Kickoff {obj.number} planned.")
            return redirect("projects:pko_detail", pk=obj.pk)
    else:
        form = ProjectKickoffForm(tenant=request.tenant,
                                  initial={"project": request.GET.get("project", "")})
    return render(request, "projects/initiation/projectkickoff/form.html",
                  {"form": form, "is_edit": False})


@login_required
def pko_detail(request, pk):
    obj = get_object_or_404(
        ProjectKickoff.objects.select_related("project", "baseline_acknowledged_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/initiation/projectkickoff/detail.html", {
        "obj": obj,
        "attending": obj.project.stakeholders.filter(attending_kickoff=True).select_related(
            "party", "user"),
        "activities": _activities(obj.project),
    })


@login_required
def pko_edit(request, pk):
    return crud_edit(
        request, model=ProjectKickoff, pk=pk, form_class=ProjectKickoffForm,
        template="projects/initiation/projectkickoff/form.html",
        success_url="projects:pko_list",
    )


@login_required
@require_POST
def pko_delete(request, pk):
    return crud_delete(request, model=ProjectKickoff, pk=pk, success_url="projects:pko_list")


# -- ceremony verbs ------------------------------------------------------------------------------

@login_required
@require_POST
def pko_schedule(request, pk):
    obj = get_object_or_404(ProjectKickoff, pk=pk, tenant=request.tenant)
    if obj.status != "planned":
        messages.info(request, "That kickoff is already scheduled or past that point.")
        return redirect("projects:pko_detail", pk=obj.pk)
    if not obj.meeting_date:
        messages.error(request, "Set a meeting date before scheduling the kickoff.")
        return redirect("projects:pko_detail", pk=obj.pk)
    obj.status = "scheduled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "schedule",
                    changes={"verb": "schedule", "from": "planned", "to": obj.status})
    messages.success(request, "Kickoff scheduled.")
    return redirect("projects:pko_detail", pk=obj.pk)


@login_required
@require_POST
def pko_mark_held(request, pk):
    obj = get_object_or_404(ProjectKickoff, pk=pk, tenant=request.tenant)
    if obj.status in ("held", "completed"):
        messages.info(request, "That kickoff has already been held.")
        return redirect("projects:pko_detail", pk=obj.pk)
    # `planned` is NOT an allowed source: it would skip pko_schedule and, with it, the
    # "set a meeting date before scheduling" requirement — a ceremony marked held with
    # meeting_date NULL, which also advances the PROJECT to `kickoff`.
    if obj.status != "scheduled":
        messages.error(request, "Schedule the kickoff before marking it held.")
        return redirect("projects:pko_detail", pk=obj.pk)
    obj.status = "held"
    obj.save(update_fields=["status", "updated_at"])
    project = obj.project
    if project.status in ("draft", "chartered"):
        project.status = "kickoff"
        project.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "held",
                    changes={"verb": "mark_held", "from": "scheduled", "to": obj.status})
    messages.success(request, "Kickoff marked as held.")
    return redirect("projects:pko_detail", pk=obj.pk)


@login_required
@require_POST
def pko_complete(request, pk):
    obj = get_object_or_404(ProjectKickoff, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.info(request, "That kickoff is already completed.")
        return redirect("projects:pko_detail", pk=obj.pk)
    if obj.status != "held":
        messages.error(request, "Hold the kickoff before completing it.")
        return redirect("projects:pko_detail", pk=obj.pk)
    project = obj.project
    if project.charter_status != "approved":
        messages.error(
            request,
            "Approve the charter before completing the kickoff — a project must not go live on "
            "an unapproved charter.")
        return redirect("projects:pko_detail", pk=obj.pk)
    obj.status = "completed"
    obj.completed_at = timezone.now()
    obj.save(update_fields=["status", "completed_at", "updated_at"])
    if project.status in ("draft", "chartered", "kickoff"):
        project.status = "active"
        project.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "complete",
                    changes={"verb": "complete", "from": "held", "to": obj.status})
    messages.success(request, f"Kickoff completed — “{project.name}” is now active.")
    return redirect("projects:pko_detail", pk=obj.pk)


@login_required
@require_POST
def pko_mark_baseline_set(request, pk):
    """Attest that the baseline was acknowledged at the ceremony.

    Re-stamping is refused: the acknowledgement is evidence of who accepted the baseline and
    when, so a second click must not overwrite the first.
    """
    obj = get_object_or_404(ProjectKickoff, pk=pk, tenant=request.tenant)
    if obj.baseline_acknowledged_at:
        messages.info(request, "The baseline was already acknowledged for this kickoff.")
        return redirect("projects:pko_detail", pk=obj.pk)
    # `scheduled` is refused too, or the guard contradicts its own message: a merely scheduled
    # ceremony has not happened yet, and this stamps who accepted the baseline AT it.
    if obj.status in ("planned", "scheduled"):
        messages.error(request, "Hold the kickoff before acknowledging the baseline.")
        return redirect("projects:pko_detail", pk=obj.pk)
    obj.baseline_acknowledged_at = timezone.now()
    obj.baseline_acknowledged_by = request.user
    obj.save(update_fields=["baseline_acknowledged_at", "baseline_acknowledged_by", "updated_at"])
    write_audit_log(request.user, obj, "baseline",
                    changes={"verb": "mark_baseline_set", "from": "", "to": "acknowledged"})
    messages.success(request, "Baseline acknowledged.")
    return redirect("projects:pko_detail", pk=obj.pk)
