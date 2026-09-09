"""Django admin for the projects app.

Every changelist declares ``list_select_related`` for the FK columns it renders: without it a
100-row page is 100 extra queries per FK column (2-3N here). Cold path, but free.
"""
from django.contrib import admin

from .models import (
    Project,
    ProjectKickoff,
    ProjectMilestone,
    ProjectRequest,
    ProjectStakeholder,
    ProjectTask,
    ScheduleBaseline,
    TaskDependency,
)


@admin.register(ProjectRequest)
class ProjectRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "request_type", "priority", "status", "decision", "tenant")
    list_filter = ("status", "request_type", "priority", "feasibility")
    list_select_related = ("tenant",)
    search_fields = ("number", "title", "description")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "decided_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "methodology", "charter_status", "status", "tenant")
    list_filter = ("status", "charter_status", "methodology")
    list_select_related = ("tenant",)
    search_fields = ("number", "name", "code")
    readonly_fields = ("created_at", "updated_at", "charter_approved_at")


@admin.register(ProjectStakeholder)
class ProjectStakeholderAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "party", "raci_role", "influence", "interest", "tenant")
    list_filter = ("raci_role", "stakeholder_type", "influence", "interest")
    # `user` is joined too even though it is not in list_display: ProjectStakeholder.__str__
    # falls back to `self.user` when `party` is NULL, and the changelist calls str(obj) per row.
    # Measured: 14 -> 8 queries on the seeded changelist.
    list_select_related = ("tenant", "project", "party", "user")
    search_fields = ("number", "raci_scope")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectKickoff)
class ProjectKickoffAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "meeting_date", "status", "tenant")
    list_filter = ("status", "agenda_template")
    list_select_related = ("tenant", "project")
    search_fields = ("number", "agenda")
    readonly_fields = ("created_at", "updated_at", "completed_at", "baseline_acknowledged_at")


# --- 7.2 Project Planning & Scheduling --------------------------------------------------------

@admin.register(ProjectTask)
class ProjectTaskAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "node_type", "status", "owner", "tenant")
    list_filter = ("node_type", "status", "estimation_method", "confidence")
    list_select_related = ("tenant", "project", "owner")
    search_fields = ("number", "name", "description")
    readonly_fields = ("created_at", "updated_at", "created_by")


@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ("number", "predecessor", "successor", "link_type", "lag_days", "tenant")
    list_filter = ("link_type",)
    # Both endpoints are joined: __str__ renders them, and the changelist calls str(obj) per row.
    list_select_related = ("tenant", "predecessor", "successor")
    search_fields = ("number", "note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "is_phase_gate", "status", "target_date",
                    "actual_date", "tenant")
    list_filter = ("status", "is_phase_gate")
    list_select_related = ("tenant", "project", "anchor_task")
    search_fields = ("number", "name", "description")
    readonly_fields = ("created_at", "updated_at", "actual_date")


@admin.register(ScheduleBaseline)
class ScheduleBaselineAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "baseline_type", "is_active", "frozen_on",
                    "planned_finish", "task_count", "tenant")
    list_filter = ("baseline_type", "is_active")
    list_select_related = ("tenant", "project")
    search_fields = ("number", "name", "strategy_note", "note")
    # `baseline_type` and `is_active` are read-only like the snapshot columns: a row's type only
    # moves through the audited bsl_promote verb, and is_active through the atomic
    # deactivate-siblings activate/promote verbs — an admin-form edit would bypass both.
    readonly_fields = ("baseline_type", "is_active", "created_at", "updated_at", "frozen_on",
                       "planned_finish", "task_count", "total_effort_hours")
