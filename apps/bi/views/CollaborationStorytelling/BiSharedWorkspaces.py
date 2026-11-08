from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspaceForm
from apps.bi.models.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspace
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log


@login_required
def bi_shared_workspace_list(request):
    qs = bi_scope(BiSharedWorkspace.objects.all(), request).select_related("department", "owner", "created_by")

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        public=Count("id", filter=Q(is_public=True)),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    public_count = counts["public"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(slug__icontains=q)
            | Q(description__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    access_level = request.GET.get("access_level", "").strip()
    if access_level:
        qs = qs.filter(default_access_level=access_level)

    department_id = request.GET.get("department", "").strip()
    if department_id and department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "workspaces": page_obj,
        "bi_shared_workspaces": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "public_count": public_count,
        "status_choices": BiSharedWorkspace.STATUS_CHOICES,
        "access_level_choices": BiSharedWorkspace.ACCESS_LEVEL_CHOICES,
        "departments": departments,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bisharedworkspace/list.html",
        context,
    )


@login_required
def bi_shared_workspace_create(request):
    if request.method == "POST":
        form = BiSharedWorkspaceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                workspace = form.save(commit=False)
                workspace.tenant = request.tenant
                workspace.created_by = request.user
                workspace.save()
                write_audit_log(
                    request.user,
                    workspace,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(request, f"Workspace '{workspace.name}' created successfully.")
            return redirect("bi:bi_shared_workspace_detail", pk=workspace.pk)
    else:
        form = BiSharedWorkspaceForm(tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bisharedworkspace/form.html",
        {"form": form, "title": "New Shared Workspace", "is_edit": False},
    )


@login_required
def bi_shared_workspace_detail(request, pk):
    workspace = bi_object(
        request,
        BiSharedWorkspace,
        pk,
        select_related=("department", "owner", "created_by"),
    )

    stories = workspace.stories.all().select_related("author").order_by("-created_at")[:10]
    decision_logs = workspace.decision_logs.all().select_related("decision_maker").order_by("-decision_date")[:10]

    context = {
        "workspace": workspace,
        "bi_shared_workspace": workspace,
        "obj": workspace,
        "stories": stories,
        "decision_logs": decision_logs,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bisharedworkspace/detail.html",
        context,
    )


@login_required
def bi_shared_workspace_edit(request, pk):
    workspace = bi_object(request, BiSharedWorkspace, pk)

    if request.method == "POST":
        form = BiSharedWorkspaceForm(request.POST, instance=workspace, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                workspace = form.save()
                write_audit_log(
                    request.user,
                    workspace,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(request, f"Workspace '{workspace.name}' updated successfully.")
            return redirect("bi:bi_shared_workspace_detail", pk=workspace.pk)
    else:
        form = BiSharedWorkspaceForm(instance=workspace, tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bisharedworkspace/form.html",
        {
            "form": form,
            "title": f"Edit Workspace: {workspace.name}",
            "workspace": workspace,
            "bi_shared_workspace": workspace,
            "obj": workspace,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def bi_shared_workspace_delete(request, pk):
    workspace = bi_object(request, BiSharedWorkspace, pk)
    name = workspace.name
    with transaction.atomic():
        write_audit_log(
            request.user,
            workspace,
            "delete",
            tenant=request.tenant,
        )
        workspace.delete()
    messages.success(request, f"Workspace '{name}' deleted successfully.")
    return redirect("bi:bi_shared_workspace_list")
