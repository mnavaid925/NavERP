"""Projects 7.13 Agile & Scrum Management — SprintImpediment views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.projects.forms.AgileScrumManagement.SprintImpediments import (
    SprintImpedimentForm,
)
from apps.projects.models.AgileScrumManagement.SprintImpediments import (
    SprintImpediment,
)
from apps.projects.models.AgileScrumManagement.Sprints import Sprint
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def imp_list(request):
    qs = (
        SprintImpediment.objects.filter(tenant=request.tenant)
        .select_related("sprint", "owner", "raised_by")
    )
    sprint_id = as_db_int(request.GET.get("sprint"))
    if sprint_id:
        qs = qs.filter(sprint_id=sprint_id)

    sprints = Sprint.objects.filter(tenant=request.tenant).order_by("-created_at")

    return crud_list(
        request,
        qs,
        "projects/agile/impediment/list.html",
        search_fields=["title", "description", "resolution_notes"],
        filters=[
            ("status", "status", False),
            ("severity", "severity", False),
        ],
        extra_context={
            "impediments": qs,
            "severity_choices": SprintImpediment.SEVERITY_CHOICES,
            "status_choices": SprintImpediment.STATUS_CHOICES,
            "sprints": sprints,
            "selected_sprint_id": sprint_id,
            "total_count": qs.count(),
        },
    )


@login_required
def imp_create(request):
    return crud_create(
        request,
        form_class=SprintImpedimentForm,
        template="projects/agile/impediment/form.html",
        success_url="projects:imp_list",
    )


@login_required
def imp_detail(request, pk):
    impediment = get_object_or_404(
        SprintImpediment.objects.select_related("sprint", "owner", "raised_by"),
        pk=pk,
        tenant=request.tenant,
    )

    return render(
        request,
        "projects/agile/impediment/detail.html",
        {
            "obj": impediment,
            "impediment": impediment,
        },
    )


@login_required
def imp_edit(request, pk):
    return crud_edit(
        request,
        model=SprintImpediment,
        pk=pk,
        form_class=SprintImpedimentForm,
        template="projects/agile/impediment/form.html",
        success_url="projects:imp_list",
    )


@login_required
@require_POST
def imp_delete(request, pk):
    return crud_delete(
        request,
        model=SprintImpediment,
        pk=pk,
        success_url="projects:imp_list",
    )


@login_required
@require_POST
def imp_resolve(request, pk):
    impediment = get_object_or_404(SprintImpediment, pk=pk, tenant=request.tenant)
    resolution_notes = request.POST.get("resolution_notes", "").strip()
    if resolution_notes:
        impediment.resolution_notes = resolution_notes

    impediment.status = "resolved"
    impediment.resolved_at = timezone.now()
    impediment.save(
        update_fields=["status", "resolved_at", "resolution_notes", "updated_at"]
    )
    write_audit_log(request.user, "resolve", impediment)
    messages.success(request, f"Impediment {impediment.number} resolved successfully.")
    return redirect("projects:imp_detail", pk=pk)
