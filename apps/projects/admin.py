"""Django admin for the projects app."""
from django.contrib import admin

from .models import Project, ProjectKickoff, ProjectRequest, ProjectStakeholder


@admin.register(ProjectRequest)
class ProjectRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "request_type", "priority", "status", "decision", "tenant")
    list_filter = ("status", "request_type", "priority", "feasibility")
    search_fields = ("number", "title", "description")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "decided_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "methodology", "charter_status", "status", "tenant")
    list_filter = ("status", "charter_status", "methodology")
    search_fields = ("number", "name", "code")
    readonly_fields = ("created_at", "updated_at", "charter_approved_at")


@admin.register(ProjectStakeholder)
class ProjectStakeholderAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "party", "raci_role", "influence", "interest", "tenant")
    list_filter = ("raci_role", "stakeholder_type", "influence", "interest")
    search_fields = ("number", "raci_scope")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectKickoff)
class ProjectKickoffAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "meeting_date", "status", "tenant")
    list_filter = ("status", "agenda_template")
    search_fields = ("number", "agenda")
    readonly_fields = ("created_at", "updated_at", "completed_at", "baseline_acknowledged_at")
