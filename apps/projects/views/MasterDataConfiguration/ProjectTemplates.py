"""Projects 7.19 — ProjectTemplate views [PTM-]."""
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q

from apps.projects.forms.MasterDataConfiguration.ProjectTemplates import (
    ProjectTemplateForm,
    ProjectTemplateInstantiateForm,
)
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import ProjectTemplate
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ProjectPlanningScheduling.ProjectMilestones import ProjectMilestone
from apps.projects.models.ProjectPlanningScheduling.ProjectTasks import ProjectTask
from apps.projects.views._common import *


@login_required
def ptm_list(request):
    """List project templates with search, filters, pagination and stats."""
    qs = ProjectTemplate.objects.filter(tenant=request.tenant).select_related("created_by")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q))

    methodology = request.GET.get("methodology", "").strip()
    if methodology:
        qs = qs.filter(methodology=methodology)

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    complexity = request.GET.get("complexity", "").strip()
    if complexity:
        qs = qs.filter(complexity=complexity)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        qs = qs.filter(is_active=False)

    stats = ProjectTemplate.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        waterfall=Count("id", filter=Q(methodology="waterfall")),
        agile=Count("id", filter=Q(methodology="agile")),
        hybrid=Count("id", filter=Q(methodology="hybrid")),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/masterdataconfiguration/template/list.html",
        {
            "templates": page_obj.object_list,
            "page_obj": page_obj,
            "methodology_choices": ProjectTemplate.METHODOLOGY_CHOICES,
            "category_choices": ProjectTemplate.CATEGORY_CHOICES,
            "complexity_choices": ProjectTemplate.COMPLEXITY_CHOICES,
            "q": q,
            "methodology": methodology,
            "category": category,
            "complexity": complexity,
            "is_active": is_active,
            "stats": stats,
        },
    )


@login_required
def ptm_detail(request, pk):
    """Detail view for a project template showing WBS structure and roles."""
    template = get_object_or_404(
        ProjectTemplate.objects.select_related("created_by"),
        pk=pk,
        tenant=request.tenant,
    )

    wbs_phases = template.wbs_structure or []
    tasks_count = 0
    milestones_count = 0
    if isinstance(wbs_phases, list):
        for phase in wbs_phases:
            if isinstance(phase, dict):
                for t in phase.get("tasks", []):
                    if t.get("is_milestone"):
                        milestones_count += 1
                    else:
                        tasks_count += 1

    return render(
        request,
        "projects/masterdataconfiguration/template/detail.html",
        {
            "template": template,
            "wbs_phases": wbs_phases,
            "tasks_count": tasks_count,
            "milestones_count": milestones_count,
        },
    )


@login_required
def ptm_create(request):
    """Create a new project template."""
    if request.method == "POST":
        form = ProjectTemplateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            template = form.save(commit=False)
            template.tenant = request.tenant
            template.created_by = request.user
            template.save()
            write_audit_log(
                user=request.user,
                obj=template,
                action="create",
                changes={"name": template.name, "methodology": template.methodology},
                tenant=request.tenant,
            )
            messages.success(request, f"Project template '{template.name}' created successfully.")
            return redirect("projects:ptm_detail", pk=template.pk)
    else:
        form = ProjectTemplateForm(tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/template/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def ptm_edit(request, pk):
    """Edit an existing project template."""
    template = get_object_or_404(ProjectTemplate, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectTemplateForm(request.POST, instance=template, tenant=request.tenant)
        if form.is_valid():
            template = form.save()
            write_audit_log(
                user=request.user,
                obj=template,
                action="update",
                changes={"name": template.name, "methodology": template.methodology},
                tenant=request.tenant,
            )
            messages.success(request, f"Project template '{template.name}' updated successfully.")
            return redirect("projects:ptm_detail", pk=template.pk)
    else:
        form = ProjectTemplateForm(instance=template, tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/template/form.html",
        {
            "form": form,
            "template": template,
            "is_edit": True,
        },
    )


@login_required
@require_POST
@tenant_admin_required
def ptm_delete(request, pk):
    """Delete a project template."""
    template = get_object_or_404(ProjectTemplate, pk=pk, tenant=request.tenant)
    name = template.name
    write_audit_log(
        user=request.user,
        obj=template,
        action="delete",
        changes={"name": name},
        tenant=request.tenant,
    )
    template.delete()
    messages.success(request, f"Project template '{name}' deleted successfully.")
    return redirect("projects:ptm_list")


@login_required
def ptm_instantiate(request, pk):
    """Create a live Project instantiated from this template's blueprint and WBS."""
    template = get_object_or_404(ProjectTemplate, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectTemplateInstantiateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                # Create the live project
                project = Project(
                    tenant=request.tenant,
                    name=form.cleaned_data["project_name"],
                    code=form.cleaned_data["project_code"],
                    methodology=template.methodology,
                    start_date=form.cleaned_data["start_date"],
                    target_end_date=form.cleaned_data.get("target_end_date"),
                    client=form.cleaned_data.get("client"),
                    project_manager=form.cleaned_data.get("project_manager"),
                    description=f"Instantiated from template: {template.name}\n\n{template.description}",
                    status="draft",
                )
                project.save()

                # Clone WBS phases/tasks if requested
                if form.cleaned_data.get("clone_wbs_tasks") and template.wbs_structure:
                    order_seq = 1
                    for phase in template.wbs_structure:
                        if not isinstance(phase, dict):
                            continue
                        phase_name = phase.get("phase", "General")
                        for t_data in phase.get("tasks", []):
                            if not isinstance(t_data, dict):
                                continue
                            t_name = t_data.get("name", "Task")
                            is_ms = t_data.get("is_milestone", False)
                            duration = t_data.get("duration_days", 1)

                            if is_ms:
                                ProjectMilestone.objects.create(
                                    tenant=request.tenant,
                                    project=project,
                                    name=f"[{phase_name}] {t_name}",
                                    target_date=project.start_date,
                                    status="planned",
                                )
                            else:
                                ProjectTask.objects.create(
                                    tenant=request.tenant,
                                    project=project,
                                    name=f"[{phase_name}] {t_name}",
                                    estimated_days=duration,
                                    wbs_code=f"1.{order_seq}",
                                    order=order_seq,
                                    status="planned",
                                )
                                order_seq += 1

                write_audit_log(
                    user=request.user,
                    obj=project,
                    action="create",
                    changes={"instantiated_from_template": template.pk},
                    tenant=request.tenant,
                )

            messages.success(request, f"Project '{project.name}' successfully chartered from template '{template.name}'.")
            return redirect("projects:prj_detail", pk=project.pk)
    else:
        initial_data = {
            "project_name": f"{template.name} - Project",
            "project_code": f"{template.code or 'PRJ'}-01",
            "start_date": timezone.now().date(),
        }
        form = ProjectTemplateInstantiateForm(initial=initial_data, tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/template/instantiate.html",
        {
            "form": form,
            "template": template,
        },
    )
