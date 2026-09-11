"""Django admin for the projects app.

Every changelist declares ``list_select_related`` for the FK columns it renders: without it a
100-row page is 100 extra queries per FK column (2-3N here). Cold path, but free.
"""
from django.contrib import admin

from .models import (
    BudgetRevision,
    CostControlAccount,
    IssueEscalation,
    Project,
    ProjectBudgetLine,
    ProjectExpense,
    ProjectIssue,
    ProjectKickoff,
    ProjectMilestone,
    ProjectRequest,
    ProjectRisk,
    ProjectStakeholder,
    ProjectTask,
    Requirement,
    ResourceAllocation,
    ResourceProfile,
    ResourceTimeEntry,
    RiskResponseAction,
    ScheduleBaseline,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
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


@admin.register(ResourceProfile)
class ResourceProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "resource_type", "default_role", "org_unit",
                    "weekly_capacity_hours", "status", "tenant")
    list_filter = ("resource_type", "status")
    # employee__party/party join for the name rendering; org_unit for the team column.
    list_select_related = ("tenant", "org_unit", "employee__party", "party")
    search_fields = ("number", "skill_summary")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ResourceAllocation)
class ResourceAllocationAdmin(admin.ModelAdmin):
    list_display = ("number", "role_name", "project", "resource", "allocation_unit",
                    "start_date", "end_date", "booking_status", "tenant")
    list_filter = ("booking_status", "allocation_unit")
    list_select_related = ("tenant", "project", "project_request", "resource")
    search_fields = ("number", "role_name", "skill_requirements")
    # booking_status and substitute_of are verb-driven — only the audited POST-only verbs move
    # them, so an admin-form edit cannot bypass the state machine.
    readonly_fields = ("booking_status", "substitute_of", "requested_by",
                       "created_at", "updated_at")


@admin.register(ResourceTimeEntry)
class ResourceTimeEntryAdmin(admin.ModelAdmin):
    list_display = ("number", "resource", "project", "entry_date", "hours", "status", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "resource", "project", "approved_by")
    search_fields = ("number", "task_description")
    # status and the approval stamps are verb-driven — the verbs write them exactly once and
    # nothing else may move them.
    readonly_fields = ("status", "submitted_at", "approved_at", "approved_by", "decision_note",
                       "created_at", "updated_at")


# --- 7.4 Cost & Budget Management -------------------------------------------------------------

@admin.register(BudgetRevision)
class BudgetRevisionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "revision_no", "status", "requested_at",
                    "decided_at", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "project")
    search_fields = ("number", "title", "reason")
    # status, decision_notes and every stamp are verb-driven (submit/approve/reject/activate) —
    # an admin-form edit would mint evidence-less governance state (the 7.2 ResourceTimeEntry
    # readonly decision_note precedent).
    readonly_fields = ("status", "decision_notes", "created_at", "updated_at", "created_by",
                       "requested_at", "decided_by", "decided_at", "activated_at")


@admin.register(CostControlAccount)
class CostControlAccountAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "project", "wbs_node", "status",
                    "percent_complete", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "project", "wbs_node")
    search_fields = ("number", "name", "code", "note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectBudgetLine)
class ProjectBudgetLineAdmin(admin.ModelAdmin):
    list_display = ("number", "budget_revision", "project", "category", "control_account",
                    "amount", "tenant")
    list_filter = ("category",)
    # wbs_node is deliberately NOT joined (the contract's pinned tuple includes it): it renders
    # in no changelist column, so the join would be dead weight — as-built wins.
    list_select_related = ("tenant", "budget_revision", "project", "control_account")
    search_fields = ("number", "note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectExpense)
class ProjectExpenseAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "control_account", "entry_type", "source_kind",
                    "source_number", "amount", "entry_date", "status", "tenant")
    list_filter = ("entry_type", "status")
    list_select_related = ("tenant", "project", "control_account")
    search_fields = ("number", "description", "source_number")
    # status is verb-driven (post/void) — the verbs write it exactly once; created_by is the
    # authorship stamp.
    readonly_fields = ("status", "created_by", "created_at", "updated_at")


@admin.register(ProjectRisk)
class ProjectRiskAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "category", "risk_type", "probability",
                    "impact", "status", "owner", "tenant")
    list_filter = ("status", "category", "risk_type")
    # Only the FKs a changelist column (or __str__) renders are joined — the same rule
    # ProjectBudgetLineAdmin documents: wbs_node / identified_by / contingency_account render
    # in no column, so their joins would be dead weight.
    list_select_related = ("tenant", "project", "owner")
    search_fields = ("number", "title", "description", "cause", "effect")
    # status is verb-driven (realize/close/reopen) and closed_at is stamped by the close verb —
    # neither is an editable field.
    readonly_fields = ("status", "closed_at", "created_by", "created_at", "updated_at")


@admin.register(RiskResponseAction)
class RiskResponseActionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "risk", "strategy", "owner", "due_date", "cost", "status",
                    "tenant")
    list_filter = ("status", "strategy")
    list_select_related = ("tenant", "risk", "owner")
    search_fields = ("number", "title", "description", "trigger")
    readonly_fields = ("status", "completed_at", "created_by", "created_at", "updated_at")


@admin.register(ProjectIssue)
class ProjectIssueAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "severity", "status", "owner",
                    "escalation_level", "escalated_to", "tenant")
    list_filter = ("status", "severity", "issue_type")
    # Same rule: wbs_node / risk / raised_by / resolved_by render in no changelist column.
    list_select_related = ("tenant", "project", "owner", "escalated_to")
    search_fields = ("number", "title", "description")
    # status, the escalation state and the resolution evidence are all verb-written — the log
    # keeps its stamps.
    readonly_fields = ("status", "escalation_level", "escalated_to", "escalated_at", "root_cause",
                       "resolution_note", "resolved_by", "resolved_at", "created_by", "created_at",
                       "updated_at")


@admin.register(IssueEscalation)
class IssueEscalationAdmin(admin.ModelAdmin):
    list_display = ("number", "issue", "level", "target_role", "target_user", "escalated_at",
                    "tenant")
    list_filter = ("level",)
    # Same rule: escalated_by renders in no changelist column (issue is walked by __str__).
    list_select_related = ("tenant", "issue", "target_user")
    search_fields = ("number", "target_role", "reason", "outcome")
    readonly_fields = ("escalated_at", "created_by", "created_at", "updated_at")


# --- 7.7 Scope & Requirements Management ------------------------------------------------------

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "requirement_type", "priority", "status",
                    "wbs_node", "owner", "tenant")
    list_filter = ("status", "requirement_type", "priority", "elicitation_method")
    list_select_related = ("tenant", "project", "parent", "wbs_node", "source_party", "owner",
                           "requested_by", "approved_by", "verified_by")
    search_fields = ("number", "title", "description", "acceptance_criteria")
    # status is verb-driven (submit/approve/reject/implement/verify) and every stamp is written by
    # the verb that owns the transition — an admin-form edit would mint evidence-less approvals.
    readonly_fields = ("status", "rejection_reason", "approved_by", "approved_at", "verified_by",
                       "verified_at", "verification_note", "created_by", "created_at",
                       "updated_at")


@admin.register(ScopeItem)
class ScopeItemAdmin(admin.ModelAdmin):
    list_display = ("number", "statement", "project", "item_type", "impact_area", "status",
                    "owner", "review_date", "tenant")
    list_filter = ("item_type", "status", "impact_area")
    list_select_related = ("tenant", "project", "requirement", "owner")
    search_fields = ("number", "statement", "description", "outcome")
    readonly_fields = ("status", "outcome", "closed_at", "created_by", "created_at", "updated_at")


@admin.register(ScopeChangeRequest)
class ScopeChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "source", "priority", "cost_impact",
                    "schedule_impact_days", "quality_impact", "status", "decided_by", "tenant")
    list_filter = ("status", "priority", "source", "quality_impact")
    list_select_related = ("tenant", "project", "requirement", "risk", "requested_by", "decided_by")
    search_fields = ("number", "title", "description", "justification")
    # status and the whole decision trail are verb-driven (submit/review/approve/reject/implement) —
    # the board's decision is evidence, so an admin-form edit must not be able to forge it.
    readonly_fields = ("status", "decision_note", "decided_by", "decided_at", "implemented_at",
                       "created_by", "created_at", "updated_at")


@admin.register(ScopeVerification)
class ScopeVerificationAdmin(admin.ModelAdmin):
    list_display = ("number", "deliverable", "project", "method", "result", "acceptance_status",
                    "inspected_by", "inspection_date", "tenant")
    list_filter = ("acceptance_status", "result", "method")
    list_select_related = ("tenant", "project", "wbs_node", "requirement", "inspected_by",
                           "accepted_by")
    search_fields = ("number", "deliverable", "findings", "decision_note")
    readonly_fields = ("acceptance_status", "decision_note", "accepted_by", "accepted_at",
                       "created_by", "created_at", "updated_at")
