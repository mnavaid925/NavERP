"""Projects 7.13 Agile & Scrum Management — SprintRetrospective views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.projects.forms.AgileScrumManagement.SprintRetrospectives import (
    SprintRetrospectiveForm,
)
from apps.projects.models.AgileScrumManagement.SprintRetrospectives import (
    SprintRetrospective,
)
from apps.projects.models.AgileScrumManagement.Sprints import Sprint
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def ret_list(request):
    qs = (
        SprintRetrospective.objects.filter(tenant=request.tenant)
        .select_related("sprint", "conducted_by", "sprint__project")
    )
    sprint_id = as_db_int(request.GET.get("sprint"))
    if sprint_id:
        qs = qs.filter(sprint_id=sprint_id)

    sprints = Sprint.objects.filter(tenant=request.tenant).order_by("-created_at")

    return crud_list(
        request,
        qs,
        "projects/agile/retro/list.html",
        search_fields=["what_went_well", "what_needs_improvement", "action_items"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "retrospectives": qs,
            "status_choices": SprintRetrospective.STATUS_CHOICES,
            "sprints": sprints,
            "selected_sprint_id": sprint_id,
            "total_count": qs.count(),
        },
    )


@login_required
def ret_create(request):
    return crud_create(
        request,
        form_class=SprintRetrospectiveForm,
        template="projects/agile/retro/form.html",
        success_url="projects:ret_list",
    )


@login_required
def ret_detail(request, pk):
    retrospective = get_object_or_404(
        SprintRetrospective.objects.select_related(
            "sprint", "conducted_by", "sprint__project"
        ),
        pk=pk,
        tenant=request.tenant,
    )

    return render(
        request,
        "projects/agile/retro/detail.html",
        {
            "obj": retrospective,
            "retrospective": retrospective,
        },
    )


@login_required
def ret_edit(request, pk):
    return crud_edit(
        request,
        model=SprintRetrospective,
        pk=pk,
        form_class=SprintRetrospectiveForm,
        template="projects/agile/retro/form.html",
        success_url="projects:ret_list",
    )


@login_required
@require_POST
def ret_delete(request, pk):
    return crud_delete(
        request,
        model=SprintRetrospective,
        pk=pk,
        success_url="projects:ret_list",
    )


@login_required
@require_POST
def ret_open(request, pk):
    retrospective = get_object_or_404(
        SprintRetrospective, pk=pk, tenant=request.tenant
    )
    retrospective.status = "open"
    retrospective.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, retrospective, "open")
    messages.success(
        request,
        f"Retrospective {retrospective.number} opened for team contributions.",
    )
    return redirect("projects:ret_detail", pk=pk)


@login_required
@require_POST
def ret_close(request, pk):
    retrospective = get_object_or_404(
        SprintRetrospective, pk=pk, tenant=request.tenant
    )
    retrospective.status = "closed"
    retrospective.closed_at = timezone.now()
    retrospective.save(update_fields=["status", "closed_at", "updated_at"])
    write_audit_log(request.user, retrospective, "close")
    messages.success(request, f"Retrospective {retrospective.number} closed.")
    return redirect("projects:ret_detail", pk=pk)
