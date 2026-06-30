"""Django admin registration for the HRM (Module 3) models."""
from django.contrib import admin

from .models import (
    AssetAllocation,
    AttendanceRecord,
    ClearanceItem,
    CostCenterProfile,
    DepartmentProfile,
    Designation,
    EmployeeDocument,
    EmployeeLifecycleEvent,
    EmployeeProfile,
    ExitInterview,
    FinalSettlement,
    JobDescriptionTemplate,
    JobGrade,
    JobRequisition,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
    OnboardingDocument,
    OnboardingProgram,
    OnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
    OrientationSession,
    PublicHoliday,
    RequisitionApproval,
    SeparationCase,
    Shift,
    ShiftAssignment,
)
from .models import (  # 3.6 Candidate Management
    CandidateCommunication,
    CandidateEmailTemplate,
    CandidateProfile,
    CandidateSkill,
    CandidateTag,
    JobApplication,
)
from .models import (  # 3.7 Interview Process
    FeedbackCriterion,
    Interview,
    InterviewFeedback,
    InterviewPanelist,
)


@admin.register(JobGrade)
class JobGradeAdmin(admin.ModelAdmin):
    list_display = ("name", "level_order", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("name", "description")
    ordering = ("level_order", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ("name", "job_grade", "grade", "department", "min_salary", "max_salary",
                    "budgeted_headcount", "is_active", "tenant")
    list_filter = ("is_active", "job_grade", "tenant")
    search_fields = ("name", "grade", "job_grade__name")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("job_grade", "department")


@admin.register(DepartmentProfile)
class DepartmentProfileAdmin(admin.ModelAdmin):
    list_display = ("org_unit", "code", "head", "cost_center", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("org_unit__name", "code")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("org_unit", "head", "cost_center")


@admin.register(CostCenterProfile)
class CostCenterProfileAdmin(admin.ModelAdmin):
    list_display = ("org_unit", "code", "owner", "budget_annual", "budget_year", "is_active", "tenant")
    list_filter = ("is_active", "budget_year", "tenant")
    search_fields = ("org_unit__name", "code")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("org_unit", "owner")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "employee_type", "designation", "gender", "created_at", "tenant")
    list_filter = ("employee_type", "tenant")
    search_fields = ("number", "party__name", "personal_email", "mobile")
    readonly_fields = ("number", "created_at", "updated_at")
    raw_id_fields = ("party", "employment", "designation")


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "document_type", "title", "verification_status",
                    "expires_on", "is_confidential", "created_at", "tenant")
    list_filter = ("document_type", "verification_status", "is_confidential", "tenant")
    search_fields = ("number", "title", "document_number", "employee__party__name")
    readonly_fields = ("number", "verification_status", "verified_by", "verified_at",
                       "created_at", "updated_at")
    raw_id_fields = ("employee", "verified_by")


@admin.register(EmployeeLifecycleEvent)
class EmployeeLifecycleEventAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "event_type", "effective_date", "to_designation",
                    "initiated_by", "created_at", "tenant")
    list_filter = ("event_type", "tenant")
    search_fields = ("number", "employee__party__name", "reason", "notes")
    readonly_fields = ("number", "initiated_by", "created_at", "updated_at")
    raw_id_fields = ("employee", "from_designation", "to_designation", "from_department",
                     "to_department", "from_manager", "to_manager", "initiated_by")


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_paid", "accrual_rule", "accrual_days", "encashable", "is_active", "tenant")
    list_filter = ("is_active", "is_paid", "accrual_rule", "tenant")
    search_fields = ("name", "code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(LeaveAllocation)
class LeaveAllocationAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "leave_type", "year", "allocated_days", "status", "tenant")
    list_filter = ("status", "year", "tenant")
    search_fields = ("number", "employee__party__name")
    readonly_fields = ("number", "created_at", "updated_at")
    raw_id_fields = ("employee", "leave_type")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "leave_type", "start_date", "end_date", "days", "status", "approver", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "employee__party__name", "reason")
    readonly_fields = ("number", "days", "approved_at", "created_at", "updated_at")
    raw_id_fields = ("employee", "leave_type", "approver")


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name", "is_optional", "tenant")
    list_filter = ("is_optional", "tenant")
    search_fields = ("name",)
    ordering = ("date",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("name", "start_time", "end_time", "grace_minutes", "is_default", "is_active", "tenant")
    list_filter = ("is_active", "is_default", "tenant")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "shift", "effective_from", "effective_to", "tenant")
    list_filter = ("tenant",)
    search_fields = ("employee__party__name", "shift__name")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("employee", "shift")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "date", "check_in", "check_out", "hours_worked", "status", "source", "tenant")
    list_filter = ("status", "source", "tenant")
    search_fields = ("number", "employee__party__name")
    readonly_fields = ("number", "hours_worked", "created_at", "updated_at")
    raw_id_fields = ("employee", "shift")


# ----------------------------------------------------------------- 3.3 Employee Onboarding
class OnboardingTemplateTaskInline(admin.TabularInline):
    model = OnboardingTemplateTask
    extra = 0
    raw_id_fields = ()


@admin.register(OnboardingTemplate)
class OnboardingTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "designation", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("number", "created_at", "updated_at")
    raw_id_fields = ("designation",)
    inlines = [OnboardingTemplateTaskInline]


@admin.register(OnboardingTemplateTask)
class OnboardingTemplateTaskAdmin(admin.ModelAdmin):
    list_display = ("template", "title", "task_category", "assignee_role", "phase", "due_offset_days", "is_mandatory", "tenant")
    list_filter = ("task_category", "assignee_role", "phase", "is_mandatory", "tenant")
    search_fields = ("title", "template__name")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("template",)


@admin.register(OnboardingProgram)
class OnboardingProgramAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "start_date", "status", "buddy", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "employee__party__name")
    readonly_fields = ("number", "completed_at", "created_at", "updated_at")
    raw_id_fields = ("employee", "template", "buddy")


@admin.register(OnboardingTask)
class OnboardingTaskAdmin(admin.ModelAdmin):
    list_display = ("program", "title", "task_category", "phase", "status", "assignee", "due_date", "tenant")
    list_filter = ("status", "phase", "task_category", "tenant")
    search_fields = ("title", "program__number")
    readonly_fields = ("completed_at", "completed_by", "created_at", "updated_at")
    raw_id_fields = ("program", "assignee")


@admin.register(OnboardingDocument)
class OnboardingDocumentAdmin(admin.ModelAdmin):
    list_display = ("program", "title", "document_type", "esign_required", "esign_status", "due_date", "tenant")
    list_filter = ("document_type", "esign_status", "esign_required", "tenant")
    search_fields = ("title", "program__number", "external_ref")
    readonly_fields = ("signed_at", "created_at", "updated_at")
    raw_id_fields = ("program",)


@admin.register(AssetAllocation)
class AssetAllocationAdmin(admin.ModelAdmin):
    list_display = ("number", "asset_name", "asset_category", "employee", "status", "issued_at", "tenant")
    list_filter = ("status", "asset_category", "tenant")
    search_fields = ("number", "asset_name", "serial_number", "asset_tag", "employee__party__name")
    readonly_fields = ("number", "returned_at", "created_at", "updated_at")
    raw_id_fields = ("program", "employee", "issued_by")


@admin.register(OrientationSession)
class OrientationSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "session_type", "employee", "scheduled_at", "attendance_status", "facilitator", "tenant")
    list_filter = ("session_type", "attendance_status", "tenant")
    search_fields = ("title", "location", "employee__party__name", "facilitator_name")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("program", "employee", "facilitator")


# ----------------------------------------------------------------- 3.4 Employee Offboarding
@admin.register(SeparationCase)
class SeparationCaseAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "separation_type", "status", "expected_last_working_day",
                    "actual_last_working_day", "tenant")
    list_filter = ("status", "separation_type", "tenant")
    search_fields = ("number", "employee__party__name")
    readonly_fields = ("number", "submitted_at", "expected_last_working_day", "approver",
                       "approved_at", "relieving_letter_generated_at", "relieving_letter_generated_by",
                       "experience_letter_generated_at", "experience_letter_generated_by",
                       "created_at", "updated_at")
    raw_id_fields = ("employee", "approver")


@admin.register(ExitInterview)
class ExitInterviewAdmin(admin.ModelAdmin):
    list_display = ("number", "case", "mode", "status", "scheduled_at", "interviewer", "tenant")
    list_filter = ("status", "mode", "tenant")
    search_fields = ("number", "case__number", "case__employee__party__name")
    readonly_fields = ("number", "status", "conducted_at", "created_at", "updated_at")
    raw_id_fields = ("case", "interviewer")


@admin.register(ClearanceItem)
class ClearanceItemAdmin(admin.ModelAdmin):
    list_display = ("case", "department", "description", "is_mandatory", "status", "cleared_at", "tenant")
    list_filter = ("status", "department", "is_mandatory", "tenant")
    search_fields = ("description", "case__number", "case__employee__party__name")
    readonly_fields = ("status", "cleared_by", "cleared_at", "created_at", "updated_at")
    raw_id_fields = ("case", "assigned_to", "cleared_by", "asset_allocation")


@admin.register(FinalSettlement)
class FinalSettlementAdmin(admin.ModelAdmin):
    list_display = ("number", "case", "status", "net_payable_display", "paid_at", "tenant")
    list_filter = ("status", "gl_posted", "tenant")
    search_fields = ("number", "case__number", "case__employee__party__name")
    readonly_fields = ("number", "status", "hr_approved_by", "hr_approved_at", "finance_approved_by",
                       "finance_approved_at", "paid_at", "gl_posted", "created_at", "updated_at")
    raw_id_fields = ("case", "hr_approved_by", "finance_approved_by")

    @admin.display(description="Net Payable")
    def net_payable_display(self, obj):
        return obj.net_payable


# ----------------------------------------------------------------- 3.5 Job Requisition
@admin.register(JobDescriptionTemplate)
class JobDescriptionTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "designation", "employment_type", "is_active", "created_at", "tenant")
    list_filter = ("is_active", "employment_type", "tenant")
    search_fields = ("number", "name", "designation__name")
    readonly_fields = ("number", "created_at", "updated_at")
    raw_id_fields = ("designation",)


class RequisitionApprovalInline(admin.TabularInline):
    model = RequisitionApproval
    extra = 0
    readonly_fields = ("status", "decided_at", "decided_by", "created_at", "updated_at")
    raw_id_fields = ("approver", "decided_by")


@admin.register(JobRequisition)
class JobRequisitionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "designation", "status", "priority", "hiring_manager",
                    "headcount", "created_at", "tenant")
    list_filter = ("status", "priority", "req_type", "employment_type", "tenant")
    search_fields = ("number", "title", "location", "designation__name")
    readonly_fields = ("number", "status", "submitted_at", "approved_at", "posted_at", "filled_at",
                       "created_at", "updated_at")
    raw_id_fields = ("designation", "job_grade", "template", "department", "cost_center",
                     "hiring_manager", "recruiter")
    inlines = [RequisitionApprovalInline]


@admin.register(RequisitionApproval)
class RequisitionApprovalAdmin(admin.ModelAdmin):
    list_display = ("requisition", "step_order", "approver", "approver_role", "status",
                    "decided_at", "decided_by", "tenant")
    list_filter = ("status", "approver_role", "tenant")
    search_fields = ("requisition__number", "approver__username")
    readonly_fields = ("status", "decided_at", "decided_by", "created_at", "updated_at")
    raw_id_fields = ("requisition", "approver", "decided_by")


# --------------------------------------------------------------------- 3.6 Candidate Management
class CandidateSkillInline(admin.TabularInline):
    model = CandidateSkill
    extra = 0
    raw_id_fields = ("candidate",)


@admin.register(CandidateTag)
class CandidateTagAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "tenant")
    list_filter = ("tenant",)
    search_fields = ("name", "description")


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "first_name", "last_name", "email", "status", "source",
                    "do_not_contact", "tenant", "created_at")
    list_filter = ("status", "source", "gender", "highest_qualification", "do_not_contact", "tenant")
    search_fields = ("number", "first_name", "last_name", "email")
    readonly_fields = ("number", "status", "gdpr_consent_date", "created_at", "updated_at")
    raw_id_fields = ("party", "sourced_by")
    filter_horizontal = ("tags",)
    inlines = [CandidateSkillInline]


@admin.register(CandidateSkill)
class CandidateSkillAdmin(admin.ModelAdmin):
    list_display = ("candidate", "skill_name", "proficiency", "source", "tenant")
    list_filter = ("source", "proficiency", "tenant")
    search_fields = ("skill_name", "candidate__first_name", "candidate__last_name")
    raw_id_fields = ("candidate",)


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("number", "candidate", "requisition", "stage", "source", "rating",
                    "applied_at", "tenant")
    list_filter = ("stage", "source", "tenant")
    search_fields = ("number", "candidate__first_name", "candidate__email", "requisition__title")
    readonly_fields = ("number", "stage", "stage_changed_at", "hired_on", "applied_at",
                       "created_at", "updated_at")
    raw_id_fields = ("candidate", "requisition", "referred_by")


@admin.register(CandidateEmailTemplate)
class CandidateEmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "template_type", "is_active", "is_auto_send", "tenant")
    list_filter = ("template_type", "is_active", "is_auto_send", "tenant")
    search_fields = ("number", "name", "subject")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(CandidateCommunication)
class CandidateCommunicationAdmin(admin.ModelAdmin):
    """Append-only log — visible in admin for support, but add/change are blocked."""

    list_display = ("number", "candidate", "channel", "subject", "delivery_status", "sent_by", "sent_at")
    list_filter = ("channel", "direction", "delivery_status", "tenant")
    search_fields = ("number", "subject", "candidate__first_name", "candidate__last_name")
    readonly_fields = ("number", "sent_at", "created_at", "updated_at")
    raw_id_fields = ("candidate", "application", "template", "sent_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# --------------------------------------------------------------------- 3.7 Interview Process
class InterviewPanelistInline(admin.TabularInline):
    model = InterviewPanelist
    extra = 0
    readonly_fields = ("notified_at", "created_at", "updated_at")
    raw_id_fields = ("interviewer",)


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "application", "round_number", "mode", "status",
                    "scheduled_at", "tenant")
    list_filter = ("status", "mode", "video_provider", "tenant")
    search_fields = ("number", "title", "application__number",
                     "application__candidate__first_name", "application__candidate__last_name")
    readonly_fields = ("number", "status", "scheduled_by", "reminder_sent_at",
                       "feedback_reminder_sent_at", "created_at", "updated_at")
    raw_id_fields = ("application", "scheduled_by")
    inlines = [InterviewPanelistInline]


@admin.register(InterviewPanelist)
class InterviewPanelistAdmin(admin.ModelAdmin):
    list_display = ("interview", "interviewer", "role", "rsvp_status", "notified_at", "tenant")
    list_filter = ("role", "rsvp_status", "tenant")
    search_fields = ("interview__number", "interviewer__username")
    readonly_fields = ("notified_at", "created_at", "updated_at")
    raw_id_fields = ("interview", "interviewer")


class FeedbackCriterionInline(admin.TabularInline):
    model = FeedbackCriterion
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(InterviewFeedback)
class InterviewFeedbackAdmin(admin.ModelAdmin):
    list_display = ("number", "interview", "overall_recommendation", "is_submitted",
                    "submitted_by", "submitted_at", "tenant")
    list_filter = ("overall_recommendation", "is_submitted", "tenant")
    search_fields = ("number", "summary", "interview__number")
    readonly_fields = ("number", "submitted_by", "submitted_at", "created_at", "updated_at")
    raw_id_fields = ("interview", "panelist", "submitted_by")
    inlines = [FeedbackCriterionInline]


@admin.register(FeedbackCriterion)
class FeedbackCriterionAdmin(admin.ModelAdmin):
    list_display = ("feedback", "criterion_name", "rating", "tenant")
    list_filter = ("rating", "tenant")
    search_fields = ("criterion_name", "feedback__number")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("feedback",)
