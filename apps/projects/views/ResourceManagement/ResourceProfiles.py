"""Projects 7.3 — ResourceProfile views (the resource pool, bullet 1).

The register is a people list: every queryset joins what renders (the ``name`` property walks
``employee__party``; the Team column renders ``org_unit``). The skills/competency matrix is NOT
duplicated here — the detail page deep-links HRM 3.40's ``employeeskill_list`` lens, and the
pool's ``skill_summary`` is quick filter text only.
"""
from apps.projects.forms import ResourceProfileForm
from apps.projects.models import ResourceProfile
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST)
from apps.projects.views._helpers import org_units


@login_required
def rsp_list(request):
    qs = (ResourceProfile.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "party", "org_unit"))
    return crud_list(
        request, qs, "projects/resource/resourceprofile/list.html",
        search_fields=["employee__party__name", "party__name", "number", "default_role",
                       "skill_summary"],
        filters=[("resource_type", "resource_type", False),
                 ("status", "status", False),
                 ("org_unit", "org_unit_id", True)],
        extra_context={
            "resource_type_choices": ResourceProfile.RESOURCE_TYPE_CHOICES,
            "status_choices": ResourceProfile.STATUS_CHOICES,
            "org_units": org_units(request.tenant),
        },
    )


@login_required
def rsp_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ResourceProfileForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Resource {obj.number} created.")
            return redirect("projects:rsp_detail", pk=obj.pk)
    else:
        form = ResourceProfileForm(tenant=request.tenant)
    return render(request, "projects/resource/resourceprofile/form.html",
                  {"form": form, "is_edit": False})


@login_required
def rsp_detail(request, pk):
    obj = get_object_or_404(
        ResourceProfile.objects.select_related("employee__party", "party", "org_unit"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/resource/resourceprofile/detail.html", {"obj": obj})


@login_required
def rsp_edit(request, pk):
    return crud_edit(
        request, model=ResourceProfile, pk=pk, form_class=ResourceProfileForm,
        template="projects/resource/resourceprofile/form.html", success_url="projects:rsp_list")


@login_required
@require_POST
def rsp_delete(request, pk):
    return crud_delete(request, model=ResourceProfile, pk=pk,
                       success_url="projects:rsp_list")
