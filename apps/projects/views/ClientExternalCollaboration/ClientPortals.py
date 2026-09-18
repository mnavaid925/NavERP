"""Projects 7.14 Client & External Collaboration — ClientPortalAccess views.
"""
from django.shortcuts import get_object_or_404, render

from apps.core.crud import as_db_int, crud_create, crud_delete, crud_edit, crud_list
from apps.projects.forms.ClientExternalCollaboration.ClientPortals import ClientPortalAccessForm
from apps.projects.models.ClientExternalCollaboration.ClientPortals import ClientPortalAccess
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import login_required


@login_required
def cpa_list(request):
    qs = (
        ClientPortalAccess.objects.filter(tenant=request.tenant)
        .select_related("project", "client_contact", "portal_user")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/clientcollaboration/clientportal/list.html",
        search_fields=["number", "client_contact__name", "project__name", "notes"],
        filters=[
            ("is_active", "is_active", False),
        ],
        extra_context={
            "access_list": qs,
            "projects": projects,
            "project_filter": project_id,
            "status_filter": request.GET.get("is_active", ""),
            "total_count": qs.count(),
        },
    )


@login_required
def cpa_create(request):
    return crud_create(
        request,
        form_class=ClientPortalAccessForm,
        template="projects/clientcollaboration/clientportal/form.html",
        success_url="projects:cpa_list",
        extra_context={"is_edit": False},
    )


@login_required
def cpa_detail(request, pk):
    access = get_object_or_404(
        ClientPortalAccess.objects.select_related("project", "client_contact", "portal_user"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/clientcollaboration/clientportal/detail.html",
        {
            "obj": access,
            "access": access,
        },
    )


@login_required
def cpa_edit(request, pk):
    access = get_object_or_404(
        ClientPortalAccess,
        pk=pk,
        tenant=request.tenant,
    )
    return crud_edit(
        request,
        model=ClientPortalAccess,
        pk=pk,
        form_class=ClientPortalAccessForm,
        template="projects/clientcollaboration/clientportal/form.html",
        success_url="projects:cpa_list",
        extra_context={"is_edit": True, "obj": access, "access": access},
    )


@login_required
def cpa_delete(request, pk):
    return crud_delete(
        request,
        model=ClientPortalAccess,
        pk=pk,
        success_url="projects:cpa_list",
    )
