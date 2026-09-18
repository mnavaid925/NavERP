"""Projects 7.14 Client & External Collaboration — VendorHandoff views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.core.utils import write_audit_log
from apps.projects.forms.ClientExternalCollaboration.VendorHandoffs import VendorHandoffForm
from apps.projects.models.ClientExternalCollaboration.VendorHandoffs import VendorHandoff
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def vhd_list(request):
    qs = (
        VendorHandoff.objects.filter(tenant=request.tenant)
        .select_related("project", "vendor", "task", "accepted_by")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/clientcollaboration/vendorhandoff/list.html",
        search_fields=["number", "title", "vendor__name", "description", "performance_notes"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "handoff_list": qs,
            "projects": projects,
            "project_filter": project_id,
            "status_choices": VendorHandoff.STATUS_CHOICES,
            "status_filter": request.GET.get("status", ""),
            "total_count": qs.count(),
        },
    )


@login_required
def vhd_create(request):
    return crud_create(
        request,
        form_class=VendorHandoffForm,
        template="projects/clientcollaboration/vendorhandoff/form.html",
        success_url="projects:vhd_list",
        extra_context={"is_edit": False},
    )


@login_required
def vhd_detail(request, pk):
    handoff = get_object_or_404(
        VendorHandoff.objects.select_related("project", "vendor", "task", "accepted_by"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/clientcollaboration/vendorhandoff/detail.html",
        {
            "obj": handoff,
            "handoff": handoff,
        },
    )


@login_required
def vhd_edit(request, pk):
    handoff = get_object_or_404(
        VendorHandoff,
        pk=pk,
        tenant=request.tenant,
    )
    return crud_edit(
        request,
        model=VendorHandoff,
        pk=pk,
        form_class=VendorHandoffForm,
        template="projects/clientcollaboration/vendorhandoff/form.html",
        success_url="projects:vhd_list",
        extra_context={"is_edit": True, "obj": handoff, "handoff": handoff},
    )


@login_required
def vhd_delete(request, pk):
    return crud_delete(
        request,
        model=VendorHandoff,
        pk=pk,
        success_url="projects:vhd_list",
    )


@login_required
@require_POST
def vhd_accept(request, pk):
    handoff = get_object_or_404(
        VendorHandoff,
        pk=pk,
        tenant=request.tenant,
    )
    if handoff.status == "accepted":
        messages.warning(request, f"Vendor handoff {handoff.number} is already accepted.")
        return redirect("projects:vhd_detail", pk=pk)

    rating_raw = request.POST.get("scorecard_rating")
    if rating_raw and rating_raw.isdigit():
        val = int(rating_raw)
        if 1 <= val <= 5:
            handoff.scorecard_rating = val

    notes = request.POST.get("performance_notes", "").strip()
    if notes:
        handoff.performance_notes = notes

    handoff.status = "accepted"
    handoff.accepted_at = timezone.now()
    handoff.accepted_by = request.user
    handoff.save()

    write_audit_log(
        request.user,
        handoff,
        "approve",
        changes={"status": "accepted", "scorecard_rating": handoff.scorecard_rating},
    )
    messages.success(request, f"Vendor handoff {handoff.number} marked as accepted.")
    return redirect("projects:vhd_detail", pk=pk)


@login_required
@require_POST
def vhd_reject(request, pk):
    handoff = get_object_or_404(
        VendorHandoff,
        pk=pk,
        tenant=request.tenant,
    )
    if handoff.status == "rejected":
        messages.warning(request, f"Vendor handoff {handoff.number} is already rejected.")
        return redirect("projects:vhd_detail", pk=pk)

    notes = request.POST.get("deficiency_notes", "").strip()
    handoff.status = "rejected"
    handoff.deficiency_notes = notes
    handoff.save()

    write_audit_log(
        request.user,
        handoff,
        "reject",
        changes={"status": "rejected", "deficiency_notes": notes},
    )
    messages.success(request, f"Vendor handoff {handoff.number} rejected.")
    return redirect("projects:vhd_detail", pk=pk)
