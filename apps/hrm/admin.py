"""Django admin registration for the HRM (Module 3) models."""
from django.contrib import admin

from .models import (
    AssetAllocation,
    AttendanceRecord,
    ClearanceItem,
    CostCenterProfile,
    DepartmentProfile,
    Designation,
    EmployeeProfile,
    ExitInterview,
    FinalSettlement,
    JobGrade,
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
    SeparationCase,
    Shift,
    ShiftAssignment,
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
