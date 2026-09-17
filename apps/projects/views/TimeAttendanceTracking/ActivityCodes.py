"""Projects 7.11 — TimeActivityCode views (activity catalog and overhead categories)."""
from apps.projects.forms import TimeActivityCodeForm
from apps.projects.models import TimeActivityCode
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST)


@login_required
def tac_list(request):
    qs = TimeActivityCode.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "projects/timeattendance/activitycode/list.html",
        search_fields=["code", "name", "description"],
        filters=[("category", "category", False), ("is_active", "is_active", False)],
        extra_context={
            "category_choices": TimeActivityCode.CATEGORY_CHOICES,
        },
    )


@login_required
def tac_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = TimeActivityCodeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Activity code {obj.code} created.")
            return redirect("projects:tac_detail", pk=obj.pk)
    else:
        form = TimeActivityCodeForm(tenant=request.tenant)
    return render(request, "projects/timeattendance/activitycode/form.html", {"form": form, "is_edit": False})


@login_required
def tac_detail(request, pk):
    obj = get_object_or_404(TimeActivityCode, pk=pk, tenant=request.tenant)
    return render(request, "projects/timeattendance/activitycode/detail.html", {"obj": obj})


@login_required
def tac_edit(request, pk):
    return crud_edit(
        request, model=TimeActivityCode, pk=pk, form_class=TimeActivityCodeForm,
        template="projects/timeattendance/activitycode/form.html",
        success_url="projects:tac_list")


@login_required
@require_POST
def tac_delete(request, pk):
    return crud_delete(
        request, model=TimeActivityCode, pk=pk,
        success_url="projects:tac_list")
