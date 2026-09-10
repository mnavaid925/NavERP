"""Projects 7.3 — ResourceAllocation views (bullets 2-4: leveling, team assembly, demand).

``booking_status`` moves ONLY through the five verbs — never a form. ``ral_assign`` and
``ral_substitute`` are staffing decisions, so they are tenant-admin gated like every 7.1/7.2
verb that moves governance state; commit/complete/cancel are member-level. Both staffing verbs
tenant-resolve the POSTed resource through ``as_db_int`` (L11) — a narrowed ``<select>`` is UX,
not an authorization boundary. Every refusal is a ``messages`` + redirect, never a 500 or a
silent no-op, and every verb writes an audited ``AuditLog`` row with a ≤10-char action.
"""
from django.db import transaction
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import ResourceAllocationForm
from apps.projects.models import ResourceAllocation, ResourceProfile
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST, timezone)
from apps.projects.views._helpers import project_requests, projects, resource_profiles


def _live_q(today):
    """The is_live predicate as a Q — soft/firm bookings whose window covers ``today``.

    Shared by the ``?is_live=`` register lens (True AND its negation for False) so the two
    lenses can never drift apart.
    """
    return (Q(booking_status__in=("soft", "firm")) & Q(start_date__lte=today)
            & (Q(end_date__isnull=True) | Q(end_date__gte=today)))


@login_required
def ral_list(request):
    qs = (ResourceAllocation.objects.filter(tenant=request.tenant)
          .select_related("project", "project_request", "project_task",
                          "resource__employee__party", "resource__party"))
    # Hand-parsed lenses BEFORE crud_list's filters/pagination — they have no single ORM lookup.
    placeholder = request.GET.get("placeholder", "")
    if placeholder == "True":
        qs = qs.filter(resource__isnull=True)
    elif placeholder == "False":
        qs = qs.filter(resource__isnull=False)
    is_live = request.GET.get("is_live", "")
    if is_live == "True":
        qs = qs.filter(_live_q(timezone.localdate()))
    elif is_live == "False":
        qs = qs.filter(~_live_q(timezone.localdate()))
    return crud_list(
        request, qs, "projects/resource/resourceallocation/list.html",
        search_fields=["role_name", "number", "skill_requirements", "project__name"],
        filters=[("project", "project_id", True),
                 ("project_request", "project_request_id", True),
                 ("resource", "resource_id", True),
                 ("booking_status", "booking_status", False)],
        extra_context={
            "booking_status_choices": ResourceAllocation.BOOKING_STATUS_CHOICES,
            "projects": projects(request.tenant),
            "project_requests": project_requests(request.tenant),
            "resources": resource_profiles(request.tenant),
        },
    )


@login_required
def ral_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ResourceAllocationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.requested_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Allocation {obj.number} created.")
            return redirect("projects:ral_detail", pk=obj.pk)
    else:
        form = ResourceAllocationForm(
            tenant=request.tenant,
            initial={"project": request.GET.get("project", ""),
                     "resource": request.GET.get("resource", "")})
    return render(request, "projects/resource/resourceallocation/form.html",
                  {"form": form, "is_edit": False})


@login_required
def ral_detail(request, pk):
    obj = get_object_or_404(
        ResourceAllocation.objects.select_related(
            "project", "project_request", "project_task", "resource", "substitute_of"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/resource/resourceallocation/detail.html", {
        "obj": obj,
        "resources": resource_profiles(request.tenant),
        "successor": obj.substituted_by.order_by("pk").first(),
    })


@login_required
def ral_edit(request, pk):
    return crud_edit(
        request, model=ResourceAllocation, pk=pk, form_class=ResourceAllocationForm,
        template="projects/resource/resourceallocation/form.html",
        success_url="projects:ral_list")


@login_required
@require_POST
def ral_delete(request, pk):
    return crud_delete(request, model=ResourceAllocation, pk=pk,
                       success_url="projects:ral_list")


@login_required
@tenant_admin_required
@require_POST
def ral_assign(request, pk):
    obj = get_object_or_404(ResourceAllocation, pk=pk, tenant=request.tenant)
    if obj.resource_id is not None:
        messages.error(request,
                       "That allocation already names a resource — use Substitute to replace it.")
        return redirect("projects:ral_detail", pk=obj.pk)
    if obj.booking_status not in ("requested", "soft"):
        messages.error(request,
                       f"A {obj.get_booking_status_display().lower()} allocation cannot be staffed.")
        return redirect("projects:ral_detail", pk=obj.pk)
    resource_pk = as_db_int(request.POST.get("resource"))
    resource = (ResourceProfile.objects.filter(tenant=request.tenant, pk=resource_pk).first()
                if resource_pk is not None else None)
    if resource is None:
        messages.error(request, "Choose a resource to assign.")
        return redirect("projects:ral_detail", pk=obj.pk)
    was = obj.booking_status
    obj.resource = resource
    if was == "requested":
        obj.booking_status = "soft"
    obj.save(update_fields=["resource", "booking_status", "updated_at"])
    write_audit_log(request.user, obj, "assign",
                    changes={"verb": "assign", "resource": resource.name, "was": was})
    messages.success(request, f"Assigned {resource.name} to allocation {obj.number}.")
    return redirect("projects:ral_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def ral_substitute(request, pk):
    obj = get_object_or_404(ResourceAllocation, pk=pk, tenant=request.tenant)
    if obj.resource_id is None:
        messages.error(request,
                       "That allocation is a placeholder — assign a resource to it instead.")
        return redirect("projects:ral_detail", pk=obj.pk)
    if obj.booking_status not in ("soft", "firm"):
        messages.error(
            request,
            f"Only a soft or firm booking can be substituted — this one is "
            f"{obj.get_booking_status_display().lower()}.")
        return redirect("projects:ral_detail", pk=obj.pk)
    resource_pk = as_db_int(request.POST.get("resource"))
    replacement = (ResourceProfile.objects.filter(tenant=request.tenant, pk=resource_pk).first()
                   if resource_pk is not None else None)
    if replacement is None:
        messages.error(request, "Choose the replacement resource.")
        return redirect("projects:ral_detail", pk=obj.pk)
    if replacement.pk == obj.resource_id:
        messages.info(request, "That is already the assigned resource.")
        return redirect("projects:ral_detail", pk=obj.pk)
    with transaction.atomic():
        original_status = obj.booking_status
        obj.booking_status = "released"
        obj.save(update_fields=["booking_status", "updated_at"])
        successor = ResourceAllocation(
            tenant=obj.tenant,
            project=obj.project, project_request=obj.project_request,
            project_task=obj.project_task,
            resource=replacement, role_name=obj.role_name,
            skill_requirements=obj.skill_requirements,
            allocation_unit=obj.allocation_unit, hours_per_week=obj.hours_per_week,
            pct_capacity=obj.pct_capacity, total_hours=obj.total_hours,
            start_date=obj.start_date, end_date=obj.end_date,
            booking_status=original_status, substitute_of=obj,
            requested_by=obj.requested_by, notes=obj.notes,
        )
        successor.save()
        write_audit_log(request.user, obj, "substitute", changes={
            "verb": "substitute", "released": obj.number,
            "successor": successor.number, "resource": replacement.name})
    messages.success(request,
                     f"Released {obj.number}; {replacement.name} booked on successor "
                     f"{successor.number}.")
    return redirect("projects:ral_detail", pk=successor.pk)


@login_required
@require_POST
def ral_commit(request, pk):
    obj = get_object_or_404(ResourceAllocation, pk=pk, tenant=request.tenant)
    if obj.booking_status not in ("requested", "soft"):
        messages.error(
            request,
            f"Only a requested or soft booking can be committed — this one is "
            f"{obj.get_booking_status_display().lower()}.")
        return redirect("projects:ral_detail", pk=obj.pk)
    if obj.booking_status == "soft" and obj.resource_id is None:
        # A firm placeholder appears in NEITHER capacity (resource_id__isnull=False) NOR
        # demand (requested/soft), and assign/substitute both refuse it — refusing the commit
        # keeps the hiring-trigger demand visible. requested → soft stays legal: that IS the
        # pipeline signal.
        messages.error(request, "Assign a resource before committing a placeholder to firm.")
        return redirect("projects:ral_detail", pk=obj.pk)
    was = obj.booking_status
    obj.booking_status = "soft" if was == "requested" else "firm"
    obj.save(update_fields=["booking_status", "updated_at"])
    write_audit_log(request.user, obj, "commit",
                    changes={"verb": "commit", "from": was, "to": obj.booking_status})
    if was == "requested":
        messages.success(request, f"Allocation {obj.number} soft-booked.")
    else:
        messages.success(request, f"Allocation {obj.number} committed.")
    return redirect("projects:ral_detail", pk=obj.pk)


@login_required
@require_POST
def ral_complete(request, pk):
    obj = get_object_or_404(ResourceAllocation, pk=pk, tenant=request.tenant)
    if obj.booking_status not in ("soft", "firm"):
        messages.error(
            request,
            f"Only a soft or firm booking can be completed — this one is "
            f"{obj.get_booking_status_display().lower()}.")
        return redirect("projects:ral_detail", pk=obj.pk)
    obj.booking_status = "completed"
    obj.save(update_fields=["booking_status", "updated_at"])
    write_audit_log(request.user, obj, "complete", changes={"verb": "complete"})
    messages.success(request, f"Allocation {obj.number} completed.")
    return redirect("projects:ral_detail", pk=obj.pk)


@login_required
@require_POST
def ral_cancel(request, pk):
    obj = get_object_or_404(ResourceAllocation, pk=pk, tenant=request.tenant)
    if obj.booking_status == "cancelled":
        messages.info(request, "That allocation is already cancelled.")
        return redirect("projects:ral_detail", pk=obj.pk)
    if obj.booking_status not in ("requested", "soft", "firm"):
        messages.error(request,
                       f"A {obj.get_booking_status_display().lower()} booking cannot be cancelled.")
        return redirect("projects:ral_detail", pk=obj.pk)
    obj.booking_status = "cancelled"
    obj.save(update_fields=["booking_status", "updated_at"])
    write_audit_log(request.user, obj, "cancel", changes={"verb": "cancel"})
    messages.success(request, f"Allocation {obj.number} cancelled.")
    return redirect("projects:ral_detail", pk=obj.pk)
