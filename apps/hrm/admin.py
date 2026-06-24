"""Django admin registration for the HRM (Module 3) models."""
from django.contrib import admin

from .models import (
    AssetAllocation,
    AttendanceRecord,
    Designation,
    EmployeeProfile,
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
    Shift,
    ShiftAssignment,
)


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ("name", "grade", "department", "min_salary", "max_salary", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("name", "grade")
    readonly_fields = ("created_at", "updated_at")


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
