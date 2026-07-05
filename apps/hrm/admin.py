"""Django admin registration for the HRM (Module 3) models."""
from django.contrib import admin

from .models import (
    AssetAllocation,
    AttendanceRecord,
    AttendanceRegularization,
    ClearanceItem,
    CostCenterProfile,
    DepartmentProfile,
    Designation,
    EmployeeDocument,
    EmployeeLifecycleEvent,
    EmployeeProfile,
    ExitInterview,
    FinalSettlement,
    FloatingHolidayElection,
    GeoFence,
    HolidayPolicy,
    JobDescriptionTemplate,
    JobGrade,
    JobRequisition,
    LeaveAllocation,
    LeaveEncashment,
    LeaveRequest,
    LeaveType,
    OnboardingDocument,
    OnboardingProgram,
    OnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
    OrientationSession,
    OvertimeRequest,
    PublicHoliday,
    RequisitionApproval,
    Timesheet,
    TimesheetEntry,
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
from .models import (  # 3.8 Offer Management
    BackgroundVerification,
    Offer,
    OfferApproval,
    OfferLetterTemplate,
    PreboardingItem,
)
from .models import (  # 3.13 Salary Structure
    EmployeeSalaryStructure,
    PayComponent,
    SalaryStructureLine,
    SalaryStructureTemplate,
)
from .models import (  # 3.14 Payroll Processing
    Payslip,
    PayslipLine,
    PayrollCycle,
)
from .models import (  # 3.15 Statutory Compliance
    EmployeeStatutoryIdentifier,
    StatutoryConfig,
    StatutoryReturn,
    StatutoryStateRule,
)
from .models import (  # 3.16 Tax & Investment
    InvestmentDeclaration,
    InvestmentDeclarationLine,
    InvestmentProof,
    TaxComputation,
    TaxRegimeConfig,
    TaxSlabBand,
)
from .models import (  # 3.17 Payout & Reports
    BankReconciliation,
    PayoutBatch,
    PayoutPayment,
    PayslipDistribution,
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


@admin.register(LeaveEncashment)
class LeaveEncashmentAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "leave_type", "year", "days", "rate_per_day", "amount", "status", "approver", "tenant")
    list_filter = ("status", "year", "tenant")
    search_fields = ("number", "employee__party__name", "payment_reference")
    readonly_fields = ("number", "amount", "approved_at", "created_at", "updated_at")
    raw_id_fields = ("employee", "leave_type", "approver")


class TimesheetEntryInline(admin.TabularInline):
    model = TimesheetEntry
    extra = 0
    raw_id_fields = ("project",)


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "period_start", "period_end", "total_hours", "billable_hours", "status", "approver", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "employee__party__name")
    readonly_fields = ("number", "total_hours", "billable_hours", "approved_at", "created_at", "updated_at")
    raw_id_fields = ("employee", "approver")
    inlines = [TimesheetEntryInline]

    def save_formset(self, request, form, formset, change):
        # The app's own views call refresh_totals() after every entry change; the admin inline must
        # too, or total_hours/billable_hours silently drift from the true sum of the entries.
        super().save_formset(request, form, formset, change)
        if formset.model is TimesheetEntry and form.instance.pk:
            form.instance.refresh_totals()


@admin.register(OvertimeRequest)
class OvertimeRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "date", "hours_claimed", "multiplier", "payout_method", "status", "approver", "tenant")
    list_filter = ("status", "payout_method", "tenant")
    search_fields = ("number", "employee__party__name", "reason")
    readonly_fields = ("number", "approved_at", "created_at", "updated_at")
    raw_id_fields = ("employee", "timesheet", "approver")


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name", "category", "is_optional", "tenant")
    list_filter = ("category", "is_optional", "tenant")
    search_fields = ("name",)
    ordering = ("date",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(HolidayPolicy)
class HolidayPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "location", "org_unit", "employee_type", "designation",
                    "is_default", "floating_holiday_quota", "is_active")
    list_filter = ("tenant", "is_default", "is_active", "employee_type")
    search_fields = ("name", "location")
    raw_id_fields = ("org_unit", "designation")
    filter_horizontal = ("holidays",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(FloatingHolidayElection)
class FloatingHolidayElectionAdmin(admin.ModelAdmin):
    list_display = ("employee", "holiday", "policy", "status", "requested_on", "approved_by", "tenant")
    list_filter = ("tenant", "status")
    search_fields = ("employee__party__name", "holiday__name")
    raw_id_fields = ("employee", "holiday", "policy", "approved_by")
    readonly_fields = ("approved_at", "created_at", "updated_at")


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
    raw_id_fields = ("employee", "shift", "geofence")


@admin.register(GeoFence)
class GeoFenceAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude", "radius_m", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("name", "address")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AttendanceRegularization)
class AttendanceRegularizationAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "date", "reason_type", "status", "approver", "tenant")
    list_filter = ("status", "reason_type", "tenant")
    search_fields = ("number", "employee__party__name", "reason")
    readonly_fields = ("number", "approved_at", "created_at", "updated_at")
    raw_id_fields = ("employee", "attendance_record", "approver")


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


# --------------------------------------------------------------------- 3.8 Offer Management
@admin.register(OfferLetterTemplate)
class OfferLetterTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("number", "created_at", "updated_at")


class OfferApprovalInline(admin.TabularInline):
    model = OfferApproval
    extra = 0
    readonly_fields = ("status", "decided_at", "decided_by", "created_at", "updated_at")
    raw_id_fields = ("approver", "decided_by")


class PreboardingItemInline(admin.TabularInline):
    model = PreboardingItem
    extra = 0
    readonly_fields = ("status", "submitted_at", "verified_by", "verified_at", "reminder_sent_at",
                       "created_at", "updated_at")
    raw_id_fields = ("verified_by",)


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("number", "application", "status", "base_salary", "currency", "start_date",
                    "expires_on", "signature_status", "tenant")
    list_filter = ("status", "signature_status", "currency", "tenant")
    search_fields = ("number", "application__number", "application__candidate__first_name",
                     "application__candidate__last_name")
    readonly_fields = ("number", "status", "extended_by", "extended_at", "accepted_at", "declined_at",
                       "rescinded_at", "created_by", "created_at", "updated_at")
    raw_id_fields = ("application", "offer_letter_template")
    inlines = [OfferApprovalInline, PreboardingItemInline]


@admin.register(OfferApproval)
class OfferApprovalAdmin(admin.ModelAdmin):
    list_display = ("offer", "step_order", "approver", "approver_role", "status",
                    "decided_at", "decided_by", "tenant")
    list_filter = ("status", "approver_role", "tenant")
    search_fields = ("offer__number", "approver__username")
    readonly_fields = ("status", "decided_at", "decided_by", "created_at", "updated_at")
    raw_id_fields = ("offer", "approver", "decided_by")


@admin.register(BackgroundVerification)
class BackgroundVerificationAdmin(admin.ModelAdmin):
    list_display = ("number", "offer", "vendor", "check_type", "status", "result",
                    "consent_given", "tenant")
    list_filter = ("status", "result", "check_type", "vendor", "tenant")
    search_fields = ("number", "offer__number", "offer__application__candidate__first_name",
                     "offer__application__candidate__last_name")
    readonly_fields = ("number", "status", "consent_date", "initiated_at", "completed_at",
                       "initiated_by", "created_at", "updated_at")
    raw_id_fields = ("offer", "initiated_by")


@admin.register(PreboardingItem)
class PreboardingItemAdmin(admin.ModelAdmin):
    list_display = ("offer", "document_type", "is_required", "status", "submitted_at",
                    "verified_by", "tenant")
    list_filter = ("status", "document_type", "is_required", "tenant")
    search_fields = ("offer__number", "offer__application__candidate__first_name",
                     "offer__application__candidate__last_name")
    readonly_fields = ("status", "submitted_at", "verified_by", "verified_at", "reminder_sent_at",
                       "created_at", "updated_at")
    raw_id_fields = ("offer", "verified_by")


# ----------------------------------------------------------------------- 3.13 Salary Structure
class SalaryStructureLineInline(admin.TabularInline):
    model = SalaryStructureLine
    extra = 0
    raw_id_fields = ("pay_component",)
    fields = ("pay_component", "calculation_type", "amount", "percentage", "sequence")


@admin.register(PayComponent)
class PayComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "component_type", "calculation_type", "frequency",
                    "is_taxable", "is_active", "tenant")
    list_filter = ("tenant", "component_type", "calculation_type", "frequency", "is_active", "contribution_side")
    search_fields = ("name", "code")
    ordering = ("display_order", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SalaryStructureTemplate)
class SalaryStructureTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "job_grade", "annual_ctc_amount", "currency", "is_active", "tenant")
    list_filter = ("tenant", "is_active", "job_grade")
    search_fields = ("number", "name")
    raw_id_fields = ("job_grade",)
    readonly_fields = ("number", "created_at", "updated_at")
    inlines = [SalaryStructureLineInline]


@admin.register(EmployeeSalaryStructure)
class EmployeeSalaryStructureAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "template", "annual_ctc_amount", "effective_from",
                    "effective_to", "status", "tenant")
    list_filter = ("tenant", "status")
    search_fields = ("number", "employee__party__name")
    raw_id_fields = ("employee", "template")
    readonly_fields = ("number", "created_at", "updated_at")


# ----------------------------------------------------------------------- 3.14 Payroll Processing
@admin.register(PayrollCycle)
class PayrollCycleAdmin(admin.ModelAdmin):
    list_display = ("number", "cycle_type", "period_start", "period_end", "pay_date", "status",
                    "accounting_payroll_run", "tenant")
    list_filter = ("tenant", "status", "cycle_type")
    search_fields = ("number",)
    raw_id_fields = ("submitted_by", "approved_by", "accounting_payroll_run")
    readonly_fields = ("number", "submitted_by", "submitted_at", "approved_by", "approved_at",
                       "accounting_payroll_run", "created_at", "updated_at")


class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0
    fields = ("component_name", "component_type", "contribution_side", "amount", "sequence")
    readonly_fields = fields


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "cycle", "gross_pay", "total_deductions", "net_pay",
                    "on_hold", "tenant")
    list_filter = ("tenant", "on_hold", "cycle__status")
    search_fields = ("number", "employee__party__name")
    raw_id_fields = ("cycle", "employee", "salary_structure")
    readonly_fields = ("number", "lop_amount", "gross_pay", "total_deductions", "net_pay",
                       "released_at", "created_at", "updated_at")
    inlines = [PayslipLineInline]


@admin.register(PayslipLine)
class PayslipLineAdmin(admin.ModelAdmin):
    list_display = ("payslip", "component_name", "component_type", "contribution_side", "amount", "tenant")
    list_filter = ("tenant", "component_type", "contribution_side")
    search_fields = ("component_name", "payslip__number")
    raw_id_fields = ("payslip",)


# ----------------------------------------------------------------- 3.15 Statutory Compliance
@admin.register(StatutoryConfig)
class StatutoryConfigAdmin(admin.ModelAdmin):
    list_display = ("tenant", "pf_establishment_code", "esi_employer_code", "tan_number",
                    "is_lwf_applicable")
    list_filter = ("is_lwf_applicable",)
    search_fields = ("tenant__name", "pf_establishment_code", "esi_employer_code", "tan_number")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StatutoryStateRule)
class StatutoryStateRuleAdmin(admin.ModelAdmin):
    list_display = ("state", "scheme", "income_from", "income_to", "pt_monthly_amount",
                    "lwf_periodicity", "is_active", "effective_from", "tenant")
    list_filter = ("tenant", "scheme", "state", "is_active")
    search_fields = ("state", "registration_number")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmployeeStatutoryIdentifier)
class EmployeeStatutoryIdentifierAdmin(admin.ModelAdmin):
    list_display = ("employee", "uan_number", "pf_number", "esi_number", "pt_state",
                    "is_pf_applicable", "is_esi_applicable", "tenant")
    list_filter = ("tenant", "is_pf_applicable", "is_esi_applicable", "pt_state")
    search_fields = ("employee__party__name", "uan_number", "pf_number", "esi_number")
    raw_id_fields = ("employee",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(StatutoryReturn)
class StatutoryReturnAdmin(admin.ModelAdmin):
    list_display = ("number", "scheme", "period_type", "period_start", "period_end", "status",
                    "employee_contribution_total", "employer_contribution_total", "due_date", "tenant")
    list_filter = ("tenant", "scheme", "status", "period_type")
    search_fields = ("number", "registration_number_used", "notes")
    raw_id_fields = ("cycle", "employee")
    readonly_fields = ("number", "employee_contribution_total", "employer_contribution_total",
                       "headcount", "filed_on", "paid_on", "registration_number_used",
                       "created_at", "updated_at")


# ----------------------------------------------------------------- 3.16 Tax & Investment
class TaxSlabBandInline(admin.TabularInline):
    model = TaxSlabBand
    extra = 1
    fields = ("income_from", "income_to", "rate_percent", "sequence")


@admin.register(TaxRegimeConfig)
class TaxRegimeConfigAdmin(admin.ModelAdmin):
    list_display = ("financial_year", "regime", "standard_deduction", "cess_rate",
                    "is_default_regime", "tenant")
    list_filter = ("tenant", "financial_year", "regime")
    search_fields = ("financial_year", "tax_law_reference")
    readonly_fields = ("created_at", "updated_at")
    inlines = [TaxSlabBandInline]


class InvestmentDeclarationLineInline(admin.TabularInline):
    model = InvestmentDeclarationLine
    extra = 0
    fields = ("section_code", "declared_amount", "verified_amount")
    readonly_fields = ("verified_amount",)


@admin.register(InvestmentDeclaration)
class InvestmentDeclarationAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "financial_year", "regime_elected", "status", "tenant")
    list_filter = ("tenant", "financial_year", "regime_elected", "status")
    search_fields = ("number", "employee__party__name")
    raw_id_fields = ("employee",)
    readonly_fields = ("number", "submitted_at", "created_at", "updated_at")
    inlines = [InvestmentDeclarationLineInline]


@admin.register(InvestmentProof)
class InvestmentProofAdmin(admin.ModelAdmin):
    list_display = ("declaration_line", "title", "amount", "verification_status", "verified_by",
                    "verified_at", "tenant")
    list_filter = ("tenant", "verification_status")
    search_fields = ("title",)
    raw_id_fields = ("declaration_line", "verified_by")
    readonly_fields = ("verification_status", "verified_by", "verified_at", "created_at", "updated_at")


@admin.register(TaxComputation)
class TaxComputationAdmin(admin.ModelAdmin):
    list_display = ("number", "employee", "financial_year", "computation_type", "tax_payable",
                    "tax_paid_ytd", "monthly_tds_amount", "tenant")
    list_filter = ("tenant", "financial_year", "computation_type")
    search_fields = ("number", "employee__party__name")
    raw_id_fields = ("employee", "declaration", "statutory_return")
    readonly_fields = ("number", "tax_payable", "tax_paid_ytd", "monthly_tds_amount",
                       "statutory_return", "computed_at", "created_at", "updated_at")


# ----------------------------------------------------------------- 3.17 Payout & Reports
class PayoutPaymentInline(admin.TabularInline):
    model = PayoutPayment
    extra = 0
    fields = ("employee", "net_amount", "payment_method", "status", "transaction_reference", "retry_of")
    readonly_fields = ("employee", "net_amount", "retry_of")
    raw_id_fields = ("payslip",)


@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display = ("number", "cycle", "status", "bank_file_format", "generated_at", "disbursed_at", "tenant")
    list_filter = ("tenant", "status", "bank_file_format")
    search_fields = ("number", "cycle__number")
    raw_id_fields = ("cycle", "generated_by", "approved_by")
    readonly_fields = ("number", "generated_by", "generated_at", "approved_by", "approved_at",
                       "disbursed_at", "created_at", "updated_at")
    inlines = [PayoutPaymentInline]


@admin.register(PayoutPayment)
class PayoutPaymentAdmin(admin.ModelAdmin):
    list_display = ("batch", "employee", "net_amount", "payment_method", "status",
                    "transaction_reference", "tenant")
    list_filter = ("tenant", "status", "payment_method")
    search_fields = ("employee__party__name", "transaction_reference", "batch__number")
    raw_id_fields = ("batch", "payslip", "employee", "retry_of")
    readonly_fields = ("net_amount", "bank_name_snapshot", "bank_account_last4_snapshot",
                       "bank_routing_snapshot", "initiated_at", "paid_on", "created_at", "updated_at")


@admin.register(PayslipDistribution)
class PayslipDistributionAdmin(admin.ModelAdmin):
    list_display = ("payslip", "delivery_channel", "status", "sent_at", "viewed_at", "downloaded_at", "tenant")
    list_filter = ("tenant", "status", "delivery_channel")
    search_fields = ("payslip__number", "payslip__employee__party__name")
    raw_id_fields = ("payslip", "sent_by")
    readonly_fields = ("sent_to_email", "sent_at", "viewed_at", "downloaded_at", "sent_by",
                       "created_at", "updated_at")


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = ("number", "batch", "statement_date", "status", "matched_count", "unmatched_count", "tenant")
    list_filter = ("tenant", "status")
    search_fields = ("number", "batch__number", "statement_reference")
    raw_id_fields = ("batch", "reconciled_by")
    readonly_fields = ("number", "matched_count", "matched_amount", "unmatched_count", "unmatched_amount",
                       "reconciled_by", "reconciled_at", "created_at", "updated_at")
