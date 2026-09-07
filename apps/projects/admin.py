"""Django admin for the projects app.

Every changelist declares ``list_select_related`` for the FK columns it renders: without it a
100-row page is 100 extra queries per FK column (2-3N here). Cold path, but free.
"""
from django.contrib import admin

from .models import Project, ProjectKickoff, ProjectRequest, ProjectStakeholder


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
