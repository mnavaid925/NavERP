"""Django admin for the projects app.

Every changelist declares ``list_select_related`` for the FK columns it renders: without it a
100-row page is 100 extra queries per FK column (2-3N here). Cold path, but free.
"""
from django.contrib import admin

from .models import (
    BudgetRevision,
    Channel,
    ChannelMessage,
    ClientApprovalRequest,
    ClientPortalAccess,
    CostControlAccount,
    DeliverableInspection,
    DocumentShare,
    DocumentTemplate,
    IssueEscalation,
    KnowledgeEntry,
    Meeting,
    MeetingActionItem,
    MeetingAgendaItem,
    OvertimeRule,
    Portfolio,
    PortfolioInvestment,
    Program,
    ProgramDependency,
    Project,
    ProjectBudgetLine,
    ProjectClientInvoice,
    ProjectDocument,
    ProjectDocumentRevision,
    ProjectEpic,
    ProjectFolder,
    ProjectExpense,
    ProjectIssue,
    ProjectKickoff,
    ProjectMilestone,
    ProjectNotification,
    ProjectOvertimeRecord,
    ProjectRelease,
    ProjectRequest,
    ProjectRisk,
    ProjectStakeholder,
    ProjectTask,
    QualityDefect,
    QualityPlan,
    QualityReview,
    Requirement,
    ResourceAllocation,
    ResourceProfile,
    ResourceTimeEntry,
    RiskResponseAction,
    ScheduleBaseline,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
    SOWAmendment,
    Sprint,
    SprintImpediment,
    SprintRetrospective,
    StatementOfWork,
    TaskBlock,
    TaskChecklistItem,
    TaskDependency,
    TimeActivityCode,
    VendorHandoff,
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


# --- 7.6 Quality Management -------------------------------------------------------------------

@admin.register(QualityPlan)
class QualityPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "wbs_node", "verification_method",
                    "standard_reference", "status", "owner", "approved_by", "tenant")
    list_filter = ("status", "verification_method")
    # Only the FKs a changelist column (or __str__) renders are joined — the same rule
    # ProjectBudgetLineAdmin documents: source_risk renders in no column, so its join would be
    # dead weight.
    list_select_related = ("tenant", "project", "wbs_node", "owner", "approved_by")
    search_fields = ("number", "title", "description", "acceptance_criteria",
                     "standard_reference")
    # status is verb-driven (approve/supersede) and the approval stamps are written by the verb
    # that owns the transition — an admin-form edit must not be able to forge a sign-off.
    readonly_fields = ("status", "approved_by", "approved_at", "created_by", "created_at",
                       "updated_at")


@admin.register(QualityReview)
class QualityReviewAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "review_type", "reviewer", "review_date",
                    "status", "improvement_status", "improvement_owner", "tenant")
    list_filter = ("status", "review_type", "improvement_status")
    # Only the FKs a changelist column (or __str__) renders are joined — wbs_node/quality_plan
    # render in no column, so their joins would be dead weight.
    list_select_related = ("tenant", "project", "reviewer", "improvement_owner")
    search_fields = ("number", "title", "scope", "findings", "improvement_action")
    # status is verb-driven (report/close) and closed_at is stamped by the close verb.
    readonly_fields = ("status", "closed_at", "created_by", "created_at", "updated_at")


@admin.register(DeliverableInspection)
class DeliverableInspectionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "wbs_node", "inspection_type", "result",
                    "usage_decision", "status", "inspector", "tenant")
    list_filter = ("status", "inspection_type", "result", "usage_decision")
    # Only the FKs a changelist column (or __str__) renders are joined — quality_plan, milestone
    # and the acceptor stamps render in no column, so their joins would be dead weight.
    list_select_related = ("tenant", "project", "wbs_node", "inspector")
    search_fields = ("number", "title", "description", "findings")
    # The usage decision, the acceptor stamps and the status are all verb-written (record /
    # accept / reject) — the acceptance evidence keeps its stamps.
    readonly_fields = ("result", "usage_decision", "accepted_by", "accepted_by_party",
                       "accepted_at", "status", "created_by", "created_at", "updated_at")


@admin.register(QualityDefect)
class QualityDefectAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "wbs_node", "defect_category", "severity",
                    "disposition", "status", "owner", "tenant")
    list_filter = ("status", "severity", "defect_category", "disposition")
    # Only the FKs a changelist column (or __str__) renders are joined — quality_plan, inspection
    # and the resolver stamp render in no column, so their joins would be dead weight.
    list_select_related = ("tenant", "project", "wbs_node", "owner")
    search_fields = ("number", "title", "description", "root_cause", "resolution_note")
    # status is verb-driven (resolve/close), the bridge is verb-written (raise_issue) and the
    # resolution evidence is stamped by the resolve verb.
    readonly_fields = ("project_issue", "root_cause", "resolution_note", "resolved_by",
                       "resolved_at", "status", "created_by", "created_at", "updated_at")


# --- 7.7 Scope & Requirements Management ------------------------------------------------------

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "requirement_type", "priority", "status",
                    "wbs_node", "owner", "tenant")
    list_filter = ("status", "requirement_type", "priority", "elicitation_method")
    list_select_related = ("tenant", "project", "wbs_node", "source_party", "owner",
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


# --- 7.8 Task & Work Management ---------------------------------------------------------------

@admin.register(TaskChecklistItem)
class TaskChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("number", "label", "task", "sequence", "is_done", "done_by", "done_at",
                    "tenant")
    list_filter = ("is_done",)
    list_select_related = ("tenant", "task", "done_by", "created_by")
    search_fields = ("number", "label")
    # is_done and the tick stamps are written by the tcl_check toggle — an admin-form edit would
    # mint a tick with no one behind it.
    readonly_fields = ("is_done", "done_by", "done_at", "created_by", "created_at", "updated_at")


@admin.register(TaskBlock)
class TaskBlockAdmin(admin.ModelAdmin):
    list_display = ("number", "task", "reason", "is_active", "blocked_by", "blocked_at",
                    "unblocked_by", "unblocked_at", "tenant")
    list_filter = ("blocked_at", "unblocked_at")
    list_select_related = ("tenant", "task", "blocked_by", "unblocked_by", "created_by")
    search_fields = ("number", "reason", "unblock_criteria", "resolution_note")
    # The whole lifecycle is verb-written: tsk_block mints the row with its stamps, tsk_unblock
    # closes it exactly once — the frozen evidence must not be editable from an admin form. The
    # `task` FK is in there too: repointing a block to another task would rewrite the evidence
    # trail with no audit entry (review M4).
    readonly_fields = ("task", "reason", "unblock_criteria", "blocked_by", "blocked_at",
                       "unblocked_by", "unblocked_at", "resolution_note", "created_by",
                       "created_at", "updated_at")

    # A block row is MINTED by tsk_block and CLOSED by tsk_unblock — an admin add would create
    # an evidence row with no verb behind it, and a delete would destroy the trail (review M4).
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(boolean=True, ordering="unblocked_at", description="Active")
    def is_active(self, obj):
        """The derived open/closed state as a boolean column — without this the list rendered
        the raw Python ``True``/``False`` (review M3). Ordered by ``unblocked_at`` so the
        boolean sort is the same ordering as the underlying column."""
        return obj.is_active


# --- 7.9 Collaboration & Communication ---------------------------------------------------------


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "kind", "is_archived", "tenant")
    list_filter = ("kind", "is_archived")
    list_select_related = ("tenant", "project", "created_by")
    search_fields = ("number", "name", "topic")
    # The archive state and its stamps are written by the chn_archive toggle — an admin-form edit
    # would mint an archive with no one behind it.
    readonly_fields = ("is_archived", "archived_by", "archived_at", "created_by", "created_at",
                       "updated_at")


@admin.register(ChannelMessage)
class ChannelMessageAdmin(admin.ModelAdmin):
    list_display = ("number", "channel", "parent", "created_by", "created_at", "tenant")
    list_filter = ("created_at",)
    list_select_related = ("tenant", "channel", "channel__project", "parent", "created_by")
    search_fields = ("number", "body")
    filter_horizontal = ("mentions",)
    # The edit stamps are written by msg_edit alone.
    readonly_fields = ("edited_by", "edited_at", "created_by", "created_at", "updated_at")


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "project", "access_level", "shared_with", "is_active",
                    "claimed_by", "tenant")
    list_filter = ("access_level", "is_active")
    list_select_related = ("tenant", "project", "channel", "document", "shared_with", "claimed_by")
    search_fields = ("number", "note", "document__name")
    # Both the revoke state and the edit claim are verb-written (dsh_revoke / dsh_claim /
    # dsh_release) — an admin edit could revoke a share without the claim release that must
    # accompany it.
    readonly_fields = ("is_active", "revoked_by", "revoked_at", "claimed_by", "claimed_at",
                       "created_by", "created_at", "updated_at")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "kind", "status", "scheduled_start",
                    "recurrence", "tenant")
    list_filter = ("kind", "status", "mode", "recurrence")
    list_select_related = ("tenant", "project", "created_by")
    search_fields = ("number", "title", "location")
    # The status machine (start/complete/cancel), the minutes capture and both actual-time stamps
    # are verb-written. An admin edit that moved the status would leave the actual stamps lying.
    readonly_fields = ("status", "minutes", "minutes_by", "minutes_at", "actual_start",
                       "actual_end", "created_by", "created_at", "updated_at")


@admin.register(MeetingAgendaItem)
class MeetingAgendaItemAdmin(admin.ModelAdmin):
    list_display = ("number", "meeting", "title", "sequence", "is_covered", "presenter", "tenant")
    list_filter = ("is_covered",)
    list_select_related = ("tenant", "meeting", "meeting__project", "presenter")
    search_fields = ("number", "title")
    # The covered tick and its stamps belong to the agi_cover toggle.
    readonly_fields = ("is_covered", "covered_by", "covered_at", "created_by", "created_at",
                       "updated_at")


@admin.register(MeetingActionItem)
class MeetingActionItemAdmin(admin.ModelAdmin):
    list_display = ("number", "meeting", "assignee", "due_date", "is_done", "task", "tenant")
    list_filter = ("is_done", "due_date")
    list_select_related = ("tenant", "meeting", "meeting__project", "assignee", "task")
    search_fields = ("number", "description")
    # The done state and its stamps belong to the mai_toggle verb.
    readonly_fields = ("is_done", "done_by", "done_at", "created_by", "created_at", "updated_at")


@admin.register(ProjectNotification)
class ProjectNotificationAdmin(admin.ModelAdmin):
    list_display = ("number", "kind", "title", "recipient", "project", "is_read", "created_at",
                    "tenant")
    list_filter = ("kind", "is_read")
    list_select_related = ("tenant", "project", "recipient", "channel", "triggered_by")
    search_fields = ("number", "title", "body")
    readonly_fields = ("is_read", "read_at", "created_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        """A notification is minted by a TRIGGER (msg_create/msg_edit, the seeder, later 7.17's
        rule engine) — an admin add would put a delivery row in someone's inbox with no event
        behind it, which is a lie the inbox cannot distinguish from a real one. Same ruling as
        7.8's TaskBlockAdmin; unlike a block, a notification IS deletable (an inbox must clear)."""
        return False


@admin.register(ProjectFolder)
class ProjectFolderAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "parent", "sequence", "is_archived",
                    "created_at", "tenant")
    list_filter = ("is_archived", "project")
    list_select_related = ("tenant", "project", "parent")
    search_fields = ("number", "name", "description")
    # The archive state and both stamps are written by the pfd_archive toggle — an admin-form edit
    # would mint an archive with no one behind it (the ChannelAdmin precedent, same file).
    readonly_fields = ("is_archived", "archived_by", "archived_at", "created_by", "created_at",
                       "updated_at")


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "folder", "document_type", "status",
                    "current_revision_no", "is_checked_out", "is_legal_hold", "is_archived",
                    "created_at", "tenant")
    list_filter = ("document_type", "status", "classification", "is_archived", "is_legal_hold")
    list_select_related = ("tenant", "project", "folder", "owner")
    search_fields = ("number", "title", "tags", "extracted_text")
    # The pointer, the search copy, the lock, the hold AND the archive are all VERB-WRITTEN state:
    # an admin edit would forge the one thing the register exists to attest (who checked what out,
    # and when). `is_archived`/`archived_by`/`archived_at` belong to pdm_archive alone — leaving
    # them writable let an admin archive a HELD record by typing, which the model's clean() refuses.
    readonly_fields = ("current_revision_no", "extracted_text", "is_checked_out", "checked_out_by",
                       "checked_out_at", "is_legal_hold", "hold_reason", "held_by", "held_at",
                       "is_archived", "archived_by", "archived_at", "pre_archive_status",
                       "created_by", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        """Refuse to delete a row under legal hold.

        The admin delete path never runs `clean()`, so the model's hold rule is not consulted there:
        without this, a superuser could destroy a held record that every in-app verb refuses.
        """
        if obj is not None and obj.is_legal_hold:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ProjectDocumentRevision)
class ProjectDocumentRevisionAdmin(admin.ModelAdmin):
    # Read-only by construction (structural immutability): no add, no change, no delete - the row is
    # created by the upload verb and stamped by the approve verb, and admin is not a second upload
    # path. `has_delete_permission` matters as much as the other two: an approved revision is the
    # EVIDENCE this module exists to keep, and the admin delete path runs no `full_clean()` and
    # writes no AuditLog row (the TaskBlockAdmin precedent, same file).
    list_display = ("document", "revision_no", "is_approved", "checksum", "uploaded_by",
                    "created_at", "tenant")
    list_filter = ("is_approved",)
    list_select_related = ("tenant", "document", "approved_by", "uploaded_by")
    search_fields = ("document__number", "document__title", "change_note", "checksum")
    readonly_fields = ("document", "revision_no", "file", "checksum", "change_note",
                       "is_approved", "approved_by", "approved_at", "extracted_text",
                       "extraction_note", "uploaded_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "category", "document_type", "version", "is_active",
                    "review_on", "created_at", "tenant")
    list_filter = ("category", "is_active")
    list_select_related = ("tenant", "owner")
    search_fields = ("number", "name", "description", "version")
    readonly_fields = ("created_by", "created_at", "updated_at")


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "kind", "status", "source_project", "usage_count",
                    "is_featured", "review_on", "created_at", "tenant")
    list_filter = ("kind", "status", "is_featured")
    list_select_related = ("tenant", "source_project", "document", "owner")
    search_fields = ("number", "title", "summary", "body", "tags")
    # usage_count is a CLICK COUNTER written by kne_use with an atomic F()+1 - an admin edit would
    # reset somebody's count by saving a stale copy of the row.
    readonly_fields = ("usage_count", "created_by", "created_at", "updated_at")


# --- 7.11 Time & Attendance Tracking ------------------------------------------------------------
@admin.register(TimeActivityCode)
class TimeActivityCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_billable_default", "is_active", "tenant")
    list_filter = ("category", "is_billable_default", "is_active")
    search_fields = ("code", "name", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(OvertimeRule)
class OvertimeRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "standard_daily_hours", "standard_weekly_hours",
                    "daily_overtime_multiplier", "is_active", "tenant")
    list_filter = ("is_active",)
    list_select_related = ("tenant", "project")
    search_fields = ("number", "name", "notes")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(ProjectOvertimeRecord)
class ProjectOvertimeRecordAdmin(admin.ModelAdmin):
    list_display = ("number", "resource", "project", "date", "overtime_hours", "overtime_type",
                    "status", "is_billable", "tenant")
    list_filter = ("status", "overtime_type", "is_billable")
    list_select_related = ("tenant", "resource", "project", "project_task", "approved_by")
    search_fields = ("number", "notes", "decision_note")
    readonly_fields = ("number", "status", "submitted_at", "approved_by", "approved_at",
                       "created_at", "updated_at")


# --- 7.12 Portfolio & Program Management --------------------------------------------------------
@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "status", "strategic_theme", "budget_envelope", "owner", "tenant")
    list_filter = ("status", "strategic_theme", "is_active")
    list_select_related = ("tenant", "owner", "currency")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "portfolio", "status", "manager", "budget_target", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "portfolio", "manager")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(PortfolioInvestment)
class PortfolioInvestmentAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "portfolio", "program", "status", "allocated_budget", "approved_by", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "project", "portfolio", "program", "approved_by")
    search_fields = ("number", "project__name", "decision_notes")
    readonly_fields = ("number", "approved_by", "approved_at", "created_at", "updated_at")


@admin.register(ProgramDependency)
class ProgramDependencyAdmin(admin.ModelAdmin):
    list_display = ("number", "source_project", "target_project", "program", "dependency_type", "criticality", "status", "tenant")
    list_filter = ("dependency_type", "criticality", "status")
    list_select_related = ("tenant", "source_project", "target_project", "program", "owner")
    search_fields = ("number", "source_project__name", "target_project__name", "description")
    readonly_fields = ("number", "cleared_at", "created_at", "updated_at")


# --- 7.13 Agile & Scrum Management --------------------------------------------------------------
@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "status", "start_date", "end_date", "committed_points", "scrum_master", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "project", "scrum_master")
    search_fields = ("number", "name", "goal", "standup_notes")
    readonly_fields = ("number", "started_at", "completed_at", "created_at", "updated_at")


@admin.register(ProjectEpic)
class ProjectEpicAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "project", "status", "owner", "target_start", "target_end", "color_code", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "project", "owner")
    search_fields = ("number", "name", "summary")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(ProjectRelease)
class ProjectReleaseAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "version_tag", "project", "status", "release_date", "released_by", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "project", "released_by")
    search_fields = ("number", "name", "version_tag", "release_notes")
    readonly_fields = ("number", "released_at", "released_by", "created_at", "updated_at")


@admin.register(SprintImpediment)
class SprintImpedimentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "sprint", "severity", "status", "owner", "raised_by", "tenant")
    list_filter = ("severity", "status")
    list_select_related = ("tenant", "sprint", "owner", "raised_by")
    search_fields = ("number", "title", "description", "resolution_notes")
    readonly_fields = ("number", "resolved_at", "created_at", "updated_at")


@admin.register(SprintRetrospective)
class SprintRetrospectiveAdmin(admin.ModelAdmin):
    list_display = ("number", "sprint", "status", "conducted_date", "conducted_by", "sentiment_score", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "sprint", "conducted_by")
    search_fields = ("number", "what_went_well", "what_needs_improvement", "action_items")
    readonly_fields = ("number", "closed_at", "created_at", "updated_at")


# --- 7.14 Client & External Collaboration -------------------------------------------------------
@admin.register(ClientPortalAccess)
class ClientPortalAccessAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "client_contact", "portal_user", "access_level", "is_active", "tenant")
    list_filter = ("access_level", "is_active")
    list_select_related = ("tenant", "project", "client_contact", "portal_user")
    search_fields = ("number", "client_contact__name", "project__name", "notes")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(ClientApprovalRequest)
class ClientApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "deliverable_name", "status", "due_date", "signed_by_name", "signed_at", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "project", "assigned_contact", "document", "milestone")
    search_fields = ("number", "deliverable_name", "review_notes", "client_feedback", "signed_by_name")
    readonly_fields = ("number", "signed_at", "created_at", "updated_at")


@admin.register(StatementOfWork)
class StatementOfWorkAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "sow_code", "project", "client", "billing_type", "contract_value", "currency", "status", "tenant")
    list_filter = ("billing_type", "status")
    list_select_related = ("tenant", "project", "client", "currency")
    search_fields = ("number", "title", "sow_code", "scope_summary")
    readonly_fields = ("number", "activated_at", "activated_by", "created_at", "updated_at")


@admin.register(SOWAmendment)
class SOWAmendmentAdmin(admin.ModelAdmin):
    list_display = ("number", "sow", "amendment_number", "title", "effective_date", "value_change", "status", "tenant")
    list_filter = ("status",)
    list_select_related = ("tenant", "sow", "approved_by")
    search_fields = ("number", "title", "revised_scope", "justification")
    readonly_fields = ("number", "approved_at", "approved_by", "created_at", "updated_at")


@admin.register(VendorHandoff)
class VendorHandoffAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "vendor", "title", "handoff_date", "target_completion_date", "status", "scorecard_rating", "tenant")
    list_filter = ("status", "scorecard_rating")
    list_select_related = ("tenant", "project", "vendor", "task")
    search_fields = ("number", "title", "deliverables_description", "performance_notes")
    readonly_fields = ("number", "accepted_at", "accepted_by", "created_at", "updated_at")


@admin.register(ProjectClientInvoice)
class ProjectClientInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "sow", "billing_type", "billing_date", "due_date", "amount", "tax_amount", "status", "accounting_invoice", "tenant")
    list_filter = ("billing_type", "status")
    list_select_related = ("tenant", "project", "sow", "milestone", "currency", "accounting_invoice")
    search_fields = ("number", "notes")
    readonly_fields = ("number", "invoiced_at", "created_at", "updated_at")




