"""Projects 7.19 — ProjectTemplate views [PTM-]."""
from datetime import timedelta
from decimal import Decimal

from django.core.paginator import Paginator
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from apps.projects.forms.MasterDataConfiguration.ProjectTemplates import (
    ProjectTemplateForm,
    ProjectTemplateInstantiateForm,
)
from apps.core.models import LocaleProfile
from apps.core.models.Calendar import Holiday
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import (
    resolve_project_locale,
)
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import (
    ProjectTemplate,
    normalize_default_roles,
    normalize_wbs_structure,
    normalize_workflow_config,
)
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeamMember
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ProjectPlanningScheduling.ProjectMilestones import ProjectMilestone
from apps.projects.models.ProjectPlanningScheduling.ProjectTasks import ProjectTask
from apps.projects.models.ResourceManagement.ResourceAllocations import ResourceAllocation
from apps.projects.models.WorkflowAutomation.ApprovalGates import ProjectApprovalGate
from apps.projects.models.WorkflowAutomation.WorkflowRules import ProjectWorkflowRule
from apps.projects.views._common import *


class _InvalidTemplateDefinition(Exception):
    pass


class _EndDateBeforeWbs(Exception):
    pass


def _add_template_save_error(form, exc):
    errors = getattr(exc, "message_dict", None)
    if errors:
        for field, messages in errors.items():
            form.add_error(field if field in form.fields else None, messages)
    else:
        form.add_error(None, getattr(exc, "messages", [str(exc)]))


def _is_working_day(day, working_days, holidays):
    return day.isoweekday() in working_days and day not in holidays


def _next_working_day(day, working_days, holidays):
    candidate = day
    while not _is_working_day(candidate, working_days, holidays):
        candidate += timedelta(days=1)
    return candidate


def _add_working_days(start, duration, working_days, holidays):
    current = _next_working_day(start, working_days, holidays)
    for _ in range(duration - 1):
        current = _next_working_day(current + timedelta(days=1), working_days, holidays)
    return current


def _estimated_end_date(start_date, duration, locale):
    working_days = set(locale["working_days"])
    if not working_days:
        return start_date + timedelta(days=max(duration, 1) - 1)
    horizon = start_date + timedelta(days=max(duration, 1) * 7 + 14)
    holidays = set(
        Holiday.objects.filter(
            tenant=locale["tenant"],
            date__gte=start_date,
            date__lte=horizon,
        ).values_list("date", flat=True)
    ) if locale["override"] or locale["calendar"] else set()
    return _add_working_days(start_date, max(duration, 1), working_days, holidays)


def _validated_template_config(template):
    try:
        return (
            normalize_default_roles(template.default_roles or []),
            normalize_wbs_structure(template.wbs_structure or []),
            normalize_workflow_config(template.workflow_config or {}),
        )
    except ValidationError as exc:
        raise _InvalidTemplateDefinition("; ".join(exc.messages)) from exc


def _materialize_template_demand(template, project, end_date, user):
    for role in template.default_roles:
        ResourceAllocation.objects.create(
            tenant=project.tenant,
            project=project,
            role_name=role,
            allocation_unit="pct_capacity",
            pct_capacity=100,
            start_date=project.start_date,
            end_date=end_date,
            booking_status="requested",
            requested_by=user,
            notes=f"Template {template.number} recommended role: {role}",
        )


def _materialize_workflow_config(template, project, user):
    config = template.workflow_config or {}
    rules = []
    for rule_config in config.get("rules", []):
        rules.append(ProjectWorkflowRule.objects.create(
            tenant=project.tenant,
            project=project,
            name=rule_config["name"],
            description=(
                f"{rule_config['description']} (materialized from {template.number})"
            ).strip(),
            is_active=True,
            trigger_entity=rule_config["trigger_entity"],
            trigger_event=rule_config["trigger_event"],
            trigger_field=rule_config["trigger_field"],
            trigger_value=rule_config["trigger_value"],
            conditions=rule_config["conditions"],
            actions=rule_config["actions"],
            owner=user,
        ))
    if not config.get("approval_gates"):
        return
    milestones = list(
        ProjectMilestone.objects.filter(project=project).order_by("target_date", "id")
    )
    for gate_config in config["approval_gates"]:
        if gate_config["target_kind"] == "project":
            target = project
            target_model = "Project"
        else:
            target_index = gate_config["target_index"]
            if target_index > len(milestones):
                raise _InvalidTemplateDefinition(
                    f"Workflow approval gate '{gate_config['title']}' references "
                    f"milestone {target_index}, but the WBS has {len(milestones)}."
                )
            target = milestones[target_index - 1]
            target_model = "ProjectMilestone"
        approver = project.project_manager or user
        ProjectApprovalGate.objects.create(
            tenant=project.tenant,
            project=project,
            rule=rules[0] if rules else None,
            gate_type=gate_config["gate_type"],
            title=gate_config["title"],
            description=gate_config["description"],
            target_model=target_model,
            target_id=target.pk,
            target_label=str(target)[:255],
            requested_by=user,
            approver=approver,
            timeout_hours=gate_config["timeout_hours"],
            threshold_amount=gate_config["threshold_amount"],
            auto_approve_threshold=gate_config["auto_approve_threshold"],
            status="pending",
        )


def _bulk_numbers(model, tenant, prefix, count):
    from apps.core.models import Tenant

    Tenant.objects.select_for_update().get(pk=tenant.pk)
    last_number = model.objects.filter(
        tenant=tenant,
        number__startswith=f"{prefix}-",
    ).order_by("-number").values_list("number", flat=True).first()
    sequence = 1
    if last_number:
        try:
            sequence = int(str(last_number).split("-")[-1]) + 1
        except (TypeError, ValueError):
            sequence = 1
    return [f"{prefix}-{sequence + offset:05d}" for offset in range(count)]


def _instantiate_wbs(template, project, user, locale):
    working_days = set(locale["working_days"])
    daily_hours = locale["working_hours_per_day"]
    holidays = set()
    phases = template.wbs_structure or []
    if working_days and (locale["override"] or locale["calendar"]):
        schedule_days = sum(item["duration_days"] for phase in phases for item in phase["tasks"])
        horizon = project.start_date + timedelta(days=schedule_days * 7 + 14)
        holidays = set(
            Holiday.objects.filter(
                tenant=project.tenant,
                date__gte=project.start_date,
                date__lte=horizon,
            ).values_list("date", flat=True)
        )
    task_count = len(phases) + sum(
        not item["is_milestone"] for phase in phases for item in phase["tasks"]
    )
    milestone_count = sum(
        item["is_milestone"] for phase in phases for item in phase["tasks"]
    )
    task_numbers = iter(_bulk_numbers(ProjectTask, project.tenant, "TSK", task_count))
    milestone_numbers = iter(_bulk_numbers(ProjectMilestone, project.tenant, "MST", milestone_count))
    cursor = (
        _next_working_day(project.start_date, working_days, holidays)
        if working_days else project.start_date
    )
    sequence = 1
    generated_end = cursor
    phase_objects = []
    phase_records = []
    for phase in phases:
        phase_start = cursor
        phase_object = ProjectTask(
            number=next(task_numbers),
            tenant=project.tenant,
            project=project,
            node_type="deliverable",
            name=phase["phase"],
            description=phase["description"],
            owner=project.project_manager,
            status="planned",
            planned_start=phase_start,
            planned_end=phase_start,
            sequence=sequence,
            created_by=user,
        )
        sequence += 1
        phase_objects.append(phase_object)
        phase_records.append((phase, phase_object, phase_start))
    if phase_objects:
        ProjectTask.objects.bulk_create(phase_objects, batch_size=500)
        phase_ids = dict(
            ProjectTask.objects.filter(
                tenant=project.tenant,
                number__in=[obj.number for obj in phase_objects],
            ).values_list("number", "id")
        )
    else:
        phase_ids = {}
    child_tasks = []
    milestones = []
    for phase, phase_object, phase_start in phase_records:
        phase_object.pk = phase_ids[phase_object.number]
        phase_object.id = phase_object.pk
        phase_end = phase_start
        for item in phase["tasks"]:
            duration = item["duration_days"]
            item_end = (
                _add_working_days(cursor, duration, working_days, holidays)
                if working_days else cursor + timedelta(days=duration - 1)
            )
            phase_end = max(phase_end, item_end)
            generated_end = max(generated_end, item_end)
            if item["is_milestone"]:
                milestones.append(ProjectMilestone(
                    number=next(milestone_numbers),
                    tenant=project.tenant,
                    project=project,
                    anchor_task_id=phase_object.pk,
                    name=item["name"],
                    description=item["description"],
                    target_date=item_end,
                    is_phase_gate=item["is_phase_gate"],
                    status="planned",
                ))
            else:
                effort_hours = (
                    (Decimal(duration) * Decimal(daily_hours)).quantize(Decimal("0.01"))
                    if daily_hours is not None else None
                )
                child_tasks.append(ProjectTask(
                    number=next(task_numbers),
                    tenant=project.tenant,
                    project=project,
                    parent_id=phase_object.pk,
                    node_type="work_package",
                    name=item["name"],
                    description=item["description"],
                    owner=project.project_manager,
                    status="planned",
                    planned_start=cursor,
                    planned_end=item_end,
                    effort_hours=effort_hours,
                    estimation_method=item["estimation_method"],
                    confidence=item["confidence"],
                    sequence=sequence,
                    created_by=user,
                ))
                sequence += 1
            cursor = (
                _next_working_day(item_end + timedelta(days=1), working_days, holidays)
                if working_days else item_end + timedelta(days=1)
            )
        phase_object.planned_end = phase_end
        phase_object.updated_at = timezone.now()
    if child_tasks:
        ProjectTask.objects.bulk_create(child_tasks, batch_size=500)
    if milestones:
        ProjectMilestone.objects.bulk_create(milestones, batch_size=500)
    if phase_objects:
        ProjectTask.objects.bulk_update(phase_objects, ["planned_end", "updated_at"], batch_size=500)
    return generated_end



@login_required
def ptm_list(request):
    """List project templates with search, filters, pagination and stats."""
    qs = ProjectTemplate.objects.filter(tenant=request.tenant).select_related("created_by").defer(
        "description", "default_roles", "wbs_structure", "workflow_config"
    )

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
        is_active = "active"
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        is_active = "inactive"
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
            "has_filters": bool(q or methodology or category or complexity or is_active),
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

    workspace_locale = LocaleProfile.objects.filter(
        tenant=request.tenant
    ).select_related("base_currency").first()
    role_labels = dict(ProjectTeamMember.ROLE_CHOICES)
    role_details = [
        {"key": role, "label": role_labels.get(role, role)}
        for role in template.default_roles
    ]
    return render(
        request,
        "projects/masterdataconfiguration/template/detail.html",
        {
            "template": template,
            "wbs_phases": wbs_phases,
            "tasks_count": tasks_count,
            "milestones_count": milestones_count,
            "budget_currency": workspace_locale.base_currency if workspace_locale else None,
            "role_details": role_details,
        },
    )


@login_required
@tenant_admin_required
def ptm_create(request):
    """Create a new project template."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectTemplateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            try:
                template = form.save(commit=False)
                template.tenant = request.tenant
                template.created_by = request.user
                template.save()
            except ValidationError as exc:
                _add_template_save_error(form, exc)
            else:
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
@tenant_admin_required
def ptm_edit(request, pk):
    """Edit an existing project template."""
    template = get_object_or_404(ProjectTemplate, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectTemplateForm(request.POST, instance=template, tenant=request.tenant)
        if form.is_valid():
            try:
                template = form.save(commit=False)
                template.save()
            except ValidationError as exc:
                _add_template_save_error(form, exc)
            else:
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
    if not template.is_active:
        messages.error(request, "Inactive templates cannot be instantiated.")
        return redirect("projects:ptm_detail", pk=template.pk)

    if request.method == "POST":
        form = ProjectTemplateInstantiateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            try:
                _validated_template_config(template)
            except _InvalidTemplateDefinition as exc:
                form.add_error(None, str(exc))
            if not form.errors:
                try:
                    with transaction.atomic():
                        locked = ProjectTemplate.objects.select_for_update().get(
                            pk=template.pk,
                            tenant=request.tenant,
                        )
                        roles, wbs_structure, workflow_config = _validated_template_config(locked)
                        locked.default_roles = roles
                        locked.wbs_structure = wbs_structure
                        locked.workflow_config = workflow_config
                        start_date = form.cleaned_data["start_date"]
                        target_end_date = form.cleaned_data.get("target_end_date")
                        project = Project(
                            tenant=request.tenant,
                            name=form.cleaned_data["project_name"],
                            code=form.cleaned_data["project_code"],
                            methodology=locked.methodology,
                            start_date=start_date,
                            end_date=target_end_date,
                            client=form.cleaned_data.get("client"),
                            project_manager=form.cleaned_data.get("project_manager"),
                            description=(
                                f"Instantiated from template: {locked.name}\n\n"
                                f"{locked.description}"
                            ),
                            status="draft",
                            created_by=request.user,
                        )
                        project.save()
                        locale = resolve_project_locale(project)
                        if form.cleaned_data.get("clone_wbs_tasks") and locked.wbs_structure:
                            generated_end_date = _instantiate_wbs(
                                locked, project, request.user, locale
                            )
                            if target_end_date and target_end_date < generated_end_date:
                                raise _EndDateBeforeWbs(
                                    f"The generated WBS ends on {generated_end_date:%Y-%m-%d}; "
                                    "the target completion date must not precede it."
                                )
                            if target_end_date is None:
                                project.end_date = generated_end_date
                                project.save(update_fields=["end_date"])
                        elif target_end_date is None:
                            project.end_date = _estimated_end_date(
                                start_date,
                                max(locked.estimated_duration_days, 1),
                                locale,
                            )
                            project.save(update_fields=["end_date"])
                        _materialize_template_demand(
                            locked,
                            project,
                            project.end_date or project.start_date,
                            request.user,
                        )
                        _materialize_workflow_config(locked, project, request.user)
                        write_audit_log(
                            user=request.user,
                            obj=project,
                            action="instantiate",
                            changes={"instantiated_from_template": locked.pk},
                            tenant=request.tenant,
                        )
                except _InvalidTemplateDefinition as exc:
                    form.add_error(None, str(exc))
                except _EndDateBeforeWbs as exc:
                    form.add_error("target_end_date", str(exc))
                else:
                    messages.success(
                        request,
                        f"Draft project '{project.name}' created from template '{locked.name}'. "
                        "It still requires charter submission and approval.",
                    )
                    return redirect("projects:prj_detail", pk=project.pk)
    else:
        initial_data = {
            "project_name": f"{template.name} - Project",
            "project_code": f"{template.code or 'PRJ'}-01",
            "start_date": timezone.localdate(),
        }
        form = ProjectTemplateInstantiateForm(initial=initial_data, tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/template/instantiate.html",
        {
            "form": form,
            "template": template,
            "schedule_basis": (
                "Business days from the project override or core business calendar; "
                "calendar days when neither is configured."
            ),
            "effort_basis": (
                "Configured working hours per day; effort remains unset when no project "
                "override supplies hours."
            ),
        },
    )
