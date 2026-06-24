"""HRM forms — one ``TenantModelForm`` per model. The shared base
(``apps.core.forms.TenantModelForm``) auto-scopes every FK dropdown to the active tenant and
applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``, and
system-computed fields (``days``, ``hours_worked``, ``approved_at``, ``confirmed_on``,
``rejected_reason``/``cancelled_reason`` — set by the workflow actions in the view).
"""
import os

from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import Party

# Photo upload safety: rasterizable-image allowlist + size cap (mirrors core DocumentForm).
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB

# Onboarding document upload safety: contracts/forms/scans allowlist + cap (mirrors clean_photo).
ALLOWED_ONBOARDING_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
MAX_ONBOARDING_DOC_BYTES = 10 * 1024 * 1024  # 10 MB

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


class DesignationForm(TenantModelForm):
    class Meta:
        model = Designation
        fields = ["name", "grade", "department", "min_salary", "max_salary", "is_active"]


class EmployeeProfileForm(TenantModelForm):
    class Meta:
        model = EmployeeProfile
        fields = [
            "party", "employment", "designation", "employee_type", "gender", "date_of_birth",
            "blood_group", "nationality", "personal_email", "mobile", "bank_name",
            "bank_account", "bank_routing", "probation_end_date", "emergency_contact_name",
            "emergency_contact_phone", "emergency_contact_relation", "photo", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The employee identity is a *person* Party; never offer organizations here.
        if self.tenant is not None:
            self.fields["party"].queryset = Party.objects.filter(
                tenant=self.tenant, kind="person").order_by("name")

    def clean_photo(self):
        f = self.cleaned_data.get("photo")
        # Only validate a freshly-uploaded file (an existing FieldFile has no size to re-check).
        if f and hasattr(f, "name") and hasattr(f, "size"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_PHOTO_EXTENSIONS:
                raise forms.ValidationError(f"Photo type '{ext}' is not allowed. Use JPG, PNG, WebP or GIF.")
            if f.size and f.size > MAX_PHOTO_BYTES:
                raise forms.ValidationError("Photo exceeds the 5 MB limit.")
        return f


class LeaveTypeForm(TenantModelForm):
    class Meta:
        model = LeaveType
        fields = ["name", "code", "is_paid", "accrual_rule", "accrual_days", "max_balance",
                  "max_carry_forward", "encashable", "is_active"]


class LeaveAllocationForm(TenantModelForm):
    class Meta:
        model = LeaveAllocation
        fields = ["employee", "leave_type", "year", "allocated_days", "note", "status"]


class LeaveRequestForm(TenantModelForm):
    # SECURITY: `status` and `approver` are deliberately NOT form fields — a new request starts
    # as the model default "draft", and both are set only by the privileged workflow actions
    # (submit/approve/reject). Exposing them here would let any user self-approve via a crafted POST.
    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "reason"]


class PublicHolidayForm(TenantModelForm):
    class Meta:
        model = PublicHoliday
        fields = ["date", "name", "is_optional"]


class ShiftForm(TenantModelForm):
    class Meta:
        model = Shift
        fields = ["name", "start_time", "end_time", "grace_minutes", "is_default", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
        }


class ShiftAssignmentForm(TenantModelForm):
    class Meta:
        model = ShiftAssignment
        fields = ["employee", "shift", "effective_from", "effective_to"]


class AttendanceRecordForm(TenantModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ["employee", "date", "check_in", "check_out", "shift", "status", "source", "notes"]
        widgets = {
            "check_in": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "check_out": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
        }


# ----------------------------------------------------------------------- 3.3 Employee Onboarding
class OnboardingTemplateForm(TenantModelForm):
    class Meta:
        model = OnboardingTemplate
        fields = ["name", "description", "designation", "is_active"]


class OnboardingTemplateTaskForm(TenantModelForm):
    class Meta:
        model = OnboardingTemplateTask
        fields = ["template", "title", "description", "task_category", "assignee_role",
                  "due_offset_days", "phase", "order", "is_mandatory"]


class OnboardingProgramForm(TenantModelForm):
    # SECURITY: `status` and `completed_at` are NOT form fields — a program starts at the model
    # default "draft" and both are advanced only by the privileged workflow actions
    # (activate/complete/cancel). Exposing them would let a crafted POST skip the workflow.
    class Meta:
        model = OnboardingProgram
        fields = ["employee", "template", "start_date", "buddy", "welcome_message",
                  "welcome_video_url", "first_day_notes", "notes"]

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get("employee")
        buddy = cleaned.get("buddy")
        if employee and buddy and employee == buddy:
            self.add_error("buddy", "An employee cannot be their own onboarding buddy.")
        # One onboarding program per employee per tenant — the form holds the tenant (the view
        # sets it on the instance only after save, so this guard lives here, not on the model).
        if employee and self.tenant is not None:
            dupes = OnboardingProgram.objects.filter(tenant=self.tenant, employee=employee)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error("employee", "This employee already has an onboarding program.")
        return cleaned


class OnboardingTaskForm(TenantModelForm):
    # SECURITY: `status`, `completed_at`, `completed_by` are excluded — task status is advanced
    # only by the complete/reopen/skip workflow actions (which stamp who/when).
    class Meta:
        model = OnboardingTask
        fields = ["program", "title", "description", "task_category", "assignee_role", "assignee",
                  "due_date", "phase", "is_mandatory", "order", "notes"]


class OnboardingDocumentForm(TenantModelForm):
    # SECURITY: `esign_status` and `signed_at` are excluded — both are workflow-owned. The model's
    # save() derives the open esign_status from `esign_required` (not_required ↔ pending), and the
    # mark-signed action advances pending → signed (stamping signed_at + an audit row). Exposing
    # esign_status here would let any user self-sign a document via a crafted POST, with no audit.
    class Meta:
        model = OnboardingDocument
        fields = ["program", "document_type", "title", "description", "file", "esign_required",
                  "due_date", "external_ref"]

    def clean_file(self):
        f = self.cleaned_data.get("file")
        # Only validate a freshly-uploaded file (an existing FieldFile has no new size to re-check).
        if f and hasattr(f, "name") and hasattr(f, "size"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_ONBOARDING_DOC_EXTENSIONS:
                raise forms.ValidationError(
                    f"File type '{ext}' is not allowed. Use PDF, DOC, DOCX, JPG or PNG.")
            if f.size and f.size > MAX_ONBOARDING_DOC_BYTES:
                raise forms.ValidationError("File exceeds the 10 MB limit.")
            # WARNING: this is an extension allowlist only (mirrors core DocumentForm /
            # EmployeeProfileForm.clean_photo). A renamed file passes — keep MEDIA_ROOT outside the
            # web root (README) and serve uploads with Content-Disposition: attachment +
            # X-Content-Type-Options: nosniff. Add MIME sniffing (python-magic) when that dep lands.
        return f


class AssetAllocationForm(TenantModelForm):
    # `issued_at` / `issued_by` are stamped by the Issue action (and `returned_at` by Return) — kept
    # out of the form so they can't be hand-spoofed/back-dated. `status` stays editable so HR can
    # record lost/damaged; the Issue/Return actions own the issued↔returned transition + timestamps.
    class Meta:
        model = AssetAllocation
        fields = ["program", "employee", "asset_name", "asset_category", "serial_number",
                  "asset_tag", "status", "return_due_date", "notes"]


class OrientationSessionForm(TenantModelForm):
    # SECURITY: `attendance_status` is excluded — it's advanced only by the mark-attended /
    # mark-missed workflow actions (which write an audit row). A session is created "scheduled";
    # exposing the field would let attendance be set via a crafted POST with no audit trail.
    class Meta:
        model = OrientationSession
        fields = ["program", "employee", "title", "session_type", "facilitator", "facilitator_name",
                  "scheduled_at", "duration_minutes", "location", "meeting_url", "notes"]
