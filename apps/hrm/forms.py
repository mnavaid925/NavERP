"""HRM forms — one ``TenantModelForm`` per model. The shared base
(``apps.core.forms.TenantModelForm``) auto-scopes every FK dropdown to the active tenant and
applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``, and
system-computed fields (``days``, ``hours_worked``, ``approved_at``, ``confirmed_on``,
``rejected_reason``/``cancelled_reason`` — set by the workflow actions in the view).
"""
import os
import re

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit, Party

# Photo upload safety: rasterizable-image allowlist + size cap (mirrors core DocumentForm).
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB

# Onboarding document upload safety: contracts/forms/scans allowlist + cap (mirrors clean_photo).
ALLOWED_ONBOARDING_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
MAX_ONBOARDING_DOC_BYTES = 10 * 1024 * 1024  # 10 MB

# Resume / cover-letter upload safety (3.6): documents only (no images) + 10 MB cap.
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB

# 3.8 offer/background-check/pre-boarding upload safety: signed offers + vendor reports are
# documents only; pre-boarding docs also allow ID-proof photos. 10 MB cap (mirrors onboarding docs).
ALLOWED_OFFER_DOC_EXTENSIONS = {".pdf", ".doc", ".docx"}
ALLOWED_PREBOARDING_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
MAX_OFFER_DOC_BYTES = 10 * 1024 * 1024  # 10 MB

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
from .models import (  # noqa: E402  — 3.6 Candidate Management
    CANDIDATE_SOURCE_CHOICES,
    CandidateEmailTemplate,
    CandidateProfile,
    CandidateSkill,
    CandidateTag,
    JobApplication,
)
from .models import (  # noqa: E402  — 3.7 Interview Process
    FeedbackCriterion,
    Interview,
    InterviewFeedback,
    InterviewPanelist,
)
from .models import (  # noqa: E402  — 3.8 Offer Management
    BackgroundVerification,
    Offer,
    OfferApproval,
    OfferLetterTemplate,
    PreboardingItem,
)
from .models import (  # noqa: E402  — 3.13 Salary Structure
    EmployeeSalaryStructure,
    PayComponent,
    SalaryStructureLine,
    SalaryStructureTemplate,
)
from .models import (  # noqa: E402  — 3.14 Payroll Processing
    Payslip,
    PayrollCycle,
)
from .models import (  # noqa: E402  — 3.15 Statutory Compliance
    EmployeeStatutoryIdentifier,
    StatutoryConfig,
    StatutoryReturn,
    StatutoryStateRule,
)
from .models import (  # noqa: E402  — 3.16 Tax & Investment
    InvestmentDeclaration,
    InvestmentDeclarationLine,
    InvestmentProof,
    TaxComputation,
    TaxRegimeConfig,
    TaxSlabBand,
)
from .models import (  # noqa: E402  — 3.17 Payout & Reports
    BankReconciliation,
    PayoutBatch,
)
from .models import (  # noqa: E402  — 3.18 Goal Setting
    GoalCheckIn,
    GoalPeriod,
    KeyResult,
    Objective,
)


# ----------------------------------------------------------------------- 3.2 Organizational Structure
class JobGradeForm(TenantModelForm):
    class Meta:
        model = JobGrade
        fields = ["name", "level_order", "description", "is_active"]


class DesignationForm(TenantModelForm):
    class Meta:
        model = Designation
        fields = ["name", "job_grade", "department", "min_salary", "mid_salary", "max_salary",
                  "grade", "budgeted_headcount", "is_active", "description", "requirements"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Offer only active grades for selection (base form already scopes to tenant).
        if self.tenant is not None:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("level_order", "name"))
            self.fields["department"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))


class DepartmentProfileForm(TenantModelForm):
    class Meta:
        model = DepartmentProfile
        fields = ["org_unit", "code", "description", "head", "cost_center", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            # Only department OrgUnits that don't already have a profile (plus this row's own).
            self.fields["org_unit"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="department")
                .filter(Q(department_profile__isnull=True) | Q(pk=self.instance.org_unit_id))
                .order_by("name"))
            self.fields["head"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))
            self.fields["cost_center"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="cost_center").order_by("name"))


class CostCenterProfileForm(TenantModelForm):
    class Meta:
        model = CostCenterProfile
        fields = ["org_unit", "code", "description", "owner", "budget_annual", "budget_year",
                  "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["org_unit"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="cost_center")
                .filter(Q(cost_center_profile__isnull=True) | Q(pk=self.instance.org_unit_id))
                .order_by("name"))
            self.fields["owner"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))


class EmployeeProfileForm(TenantModelForm):
    class Meta:
        model = EmployeeProfile
        fields = [
            "party", "employment", "designation", "employee_type", "gender", "date_of_birth",
            "blood_group", "marital_status", "nationality", "personal_email", "work_email", "mobile",
            "work_location", "notice_period_days", "father_name", "spouse_name",
            "national_id", "national_id_type", "passport_number", "passport_expiry",
            "current_address", "permanent_address", "bank_name", "bank_account", "bank_routing",
            "probation_end_date", "confirmed_on", "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation", "emergency_contact_2_name", "emergency_contact_2_phone",
            "emergency_contact_2_relation", "photo", "notes",
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


class EmployeeDocumentForm(TenantModelForm):
    # SECURITY: `verification_status`, `verified_by`, `verified_at` are excluded — set only by the
    # mark-verified / reject workflow actions (which stamp who/when + an audit row). Exposing them
    # would let any user self-verify a document via a crafted POST.
    class Meta:
        model = EmployeeDocument
        fields = ["employee", "document_type", "title", "document_number", "issuing_authority",
                  "issuing_country", "issued_on", "expires_on", "is_confidential", "file", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["employee"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))

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
            # WARNING: extension allowlist only — keep MEDIA_ROOT outside the web root and serve with
            # Content-Disposition: attachment + X-Content-Type-Options: nosniff (mirrors onboarding docs).
        return f


class EmployeeLifecycleEventForm(TenantModelForm):
    # SECURITY: `initiated_by` is excluded — stamped from request.user in the create view, never
    # settable via the form.
    class Meta:
        model = EmployeeLifecycleEvent
        fields = ["employee", "event_type", "effective_date", "reason",
                  "from_designation", "to_designation", "from_department", "to_department",
                  "from_location", "to_location", "from_job_title", "to_job_title",
                  "from_salary", "to_salary", "from_manager", "to_manager",
                  "from_employee_type", "to_employee_type", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            employees = (EmployeeProfile.objects.filter(tenant=self.tenant)
                         .select_related("party").order_by("party__name"))
            for fld in ("employee", "from_manager", "to_manager"):
                self.fields[fld].queryset = employees
            designations = (Designation.objects.filter(tenant=self.tenant, is_active=True)
                            .order_by("name"))
            for fld in ("from_designation", "to_designation"):
                self.fields[fld].queryset = designations
            departments = OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name")
            for fld in ("from_department", "to_department"):
                self.fields[fld].queryset = departments


class LeaveTypeForm(TenantModelForm):
    class Meta:
        model = LeaveType
        fields = ["name", "code", "is_paid", "accrual_rule", "accrual_days", "max_balance",
                  "max_carry_forward", "encashable", "is_active"]


class LeaveAllocationForm(TenantModelForm):
    class Meta:
        model = LeaveAllocation
        fields = ["employee", "leave_type", "year", "allocated_days", "note", "status"]

    def save(self, commit=True):
        obj = super().save(commit=False)
        # A manual edit to allocated_days resets the carry-forward baseline — otherwise the engine's
        # idempotency invariant (allocated = accrued/base + carried_forward) is left inconsistent and
        # the next carry-forward run would mis-account the hand-edited value.
        if "allocated_days" in self.changed_data:
            obj.carried_forward = 0
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class LeaveRequestForm(TenantModelForm):
    # SECURITY: `status` and `approver` are deliberately NOT form fields — a new request starts
    # as the model default "draft", and both are set only by the privileged workflow actions
    # (submit/approve/reject). Exposing them here would let any user self-approve via a crafted POST.
    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "reason"]


class LeaveEncashmentForm(TenantModelForm):
    # `amount` is derived (days × rate) and status/approver/approved_at/paid_on/payment_reference/
    # decision_note are workflow-set in the view — never on the form (no self-approve via crafted POST).
    class Meta:
        model = LeaveEncashment
        fields = ["employee", "leave_type", "year", "days", "rate_per_day"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only encashable leave types can be encashed — narrow the dropdown to match the model clean().
        if "leave_type" in self.fields:
            self.fields["leave_type"].queryset = self.fields["leave_type"].queryset.filter(encashable=True)


# ----------------------------------------------------------------------- 3.11 Time Tracking
class TimesheetForm(TenantModelForm):
    # status/approver/approved_at/decision_note/rejected_reason + derived total/billable hours are
    # workflow-set in the view, never on the form (no self-approve via crafted POST).
    class Meta:
        model = Timesheet
        fields = ["employee", "period_start", "period_end"]


class TimesheetEntryForm(TenantModelForm):
    # `timesheet` is set from the view/URL context (inline child on the timesheet hub), not the form.
    class Meta:
        model = TimesheetEntry
        fields = ["date", "project", "task_description", "hours", "is_billable", "billable_rate", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }


class OvertimeRequestForm(TenantModelForm):
    class Meta:
        model = OvertimeRequest
        fields = ["employee", "timesheet", "date", "hours_claimed", "multiplier", "payout_method", "reason"]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class PublicHolidayForm(TenantModelForm):
    class Meta:
        model = PublicHoliday
        fields = ["date", "name", "is_optional", "category"]


class HolidayPolicyForm(TenantModelForm):
    class Meta:
        model = HolidayPolicy
        fields = ["name", "location", "org_unit", "employee_type", "designation",
                  "is_default", "floating_holiday_quota", "holidays", "is_active", "description"]
        # `holidays` keeps the default SelectMultiple widget so TenantModelForm styles it as a
        # themed `.form-select` (CheckboxSelectMultiple has no matching theme class and renders
        # as an unstyled <ul>).
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A policy only governs OPTIONAL (floating) holidays — narrow its pool to those (the base
        # form already tenant-scopes every FK/M2M queryset).
        # Only the holidays M2M needs narrowing (to optional holidays) — the base TenantModelForm
        # already tenant-scopes the org_unit/designation FKs, and Designation.Meta already orders by name.
        if self.tenant is not None and "holidays" in self.fields:
            self.fields["holidays"].queryset = (
                PublicHoliday.objects.filter(tenant=self.tenant, is_optional=True).order_by("date"))


class FloatingHolidayElectionForm(TenantModelForm):
    # SECURITY: `status`, `approved_by`, `approved_at` are deliberately NOT form fields — a new
    # election starts "pending" and all three are set only by the privileged approve/reject workflow
    # actions (mirrors LeaveRequestForm). Exposing them would let a user self-approve via a crafted POST.
    class Meta:
        model = FloatingHolidayElection
        fields = ["employee", "holiday", "policy", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only optional (floating) holidays are electable; policy auto-resolves in the model's save()
        # if left blank, so it's optional on the form.
        if self.tenant is not None and "holiday" in self.fields:
            self.fields["holiday"].queryset = (
                PublicHoliday.objects.filter(tenant=self.tenant, is_optional=True).order_by("date"))
        if self.tenant is not None and "policy" in self.fields:
            self.fields["policy"].queryset = (
                HolidayPolicy.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
        if "policy" in self.fields:
            self.fields["policy"].required = False


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
        fields = ["employee", "date", "check_in", "check_out", "shift", "status", "source",
                  "latitude", "longitude", "geofence", "notes"]
        widgets = {
            "check_in": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "check_out": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
        }


class GeoFenceForm(TenantModelForm):
    class Meta:
        model = GeoFence
        fields = ["name", "address", "latitude", "longitude", "radius_m", "is_active"]
        widgets = {
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
        }


class AttendanceRegularizationForm(TenantModelForm):
    class Meta:
        model = AttendanceRegularization
        # status / approver / approved_at / decision_note are workflow-set in the view, not on the form.
        fields = ["employee", "attendance_record", "date", "reason_type",
                  "requested_check_in", "requested_check_out", "reason"]
        widgets = {
            "requested_check_in": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "requested_check_out": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "reason": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
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


# ----------------------------------------------------------------------- 3.4 Employee Offboarding
class SeparationCaseForm(TenantModelForm):
    # SECURITY: every lifecycle field is excluded — `status`, `submitted_at`, `approver`,
    # `approved_at`, `rejection_reason`/`withdrawal_reason`, both letter-generated stamps, and the
    # derived `expected_last_working_day` (computed in save()). They're advanced only by the audited
    # workflow actions; exposing them would let a crafted POST skip approval/clearance.
    class Meta:
        model = SeparationCase
        fields = ["employee", "separation_type", "exit_reason", "resignation_letter",
                  "notice_period_days", "notice_start_date", "actual_last_working_day",
                  "notice_buyout_type", "requires_kt", "notes"]

    def clean_resignation_letter(self):
        f = self.cleaned_data.get("resignation_letter")
        # Only validate a freshly-uploaded file (an existing FieldFile has no new size to re-check).
        if f and hasattr(f, "name") and hasattr(f, "size"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_ONBOARDING_DOC_EXTENSIONS:
                raise forms.ValidationError(
                    f"File type '{ext}' is not allowed. Use PDF, DOC, DOCX, JPG or PNG.")
            if f.size and f.size > MAX_ONBOARDING_DOC_BYTES:
                raise forms.ValidationError("File exceeds the 10 MB limit.")
            # WARNING: extension allowlist only — keep MEDIA_ROOT outside the web root and serve with
            # Content-Disposition: attachment + X-Content-Type-Options: nosniff (mirrors onboarding docs).
        return f


class ExitInterviewForm(TenantModelForm):
    # SECURITY: `status` and `conducted_at` are excluded — both are advanced only by the complete /
    # skip workflow actions (which stamp/audit). A crafted POST must not be able to mark an interview
    # "completed" without going through the action.
    class Meta:
        model = ExitInterview
        fields = ["case", "interviewer", "scheduled_at", "mode",
                  "rating_job_satisfaction", "rating_management", "rating_compensation",
                  "rating_work_environment", "rating_growth_opportunities",
                  "rating_work_life_balance", "rating_culture", "rating_overall",
                  "primary_reason", "would_recommend", "would_rejoin",
                  "what_went_well", "what_to_improve", "additional_comments"]

    def clean(self):
        cleaned = super().clean()
        case = cleaned.get("case")
        # One exit interview per case (form-level — a skipped/no-show one can be superseded by
        # deleting it first). The tenant lives on the form, so this guard belongs here, not on the model.
        if case and self.tenant is not None:
            dupes = ExitInterview.objects.filter(tenant=self.tenant, case=case)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error("case", "An exit interview already exists for this separation case.")
        return cleaned


class ClearanceItemForm(TenantModelForm):
    # SECURITY: `status`, `cleared_by`, `cleared_at` are excluded — set only by the mark-cleared /
    # mark-na / reject workflow actions (the mark-cleared action also returns the linked asset).
    class Meta:
        model = ClearanceItem
        fields = ["case", "department", "department_label", "description", "is_mandatory",
                  "assigned_to", "due_date", "asset_allocation", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only an issued asset can be the subject of a return-clearance line.
        if self.tenant is not None:
            self.fields["asset_allocation"].queryset = (
                AssetAllocation.objects.filter(tenant=self.tenant, status="issued")
                .select_related("employee__party").order_by("-issued_at"))


class FinalSettlementForm(TenantModelForm):
    # SECURITY: `status`, the HR/finance approval stamps, `paid_at`, and `gl_posted` are excluded —
    # advanced only by the compute / hr-approve / finance-approve / mark-paid actions. `net_payable`
    # is a derived property (no column). Earnings/deductions are editable so HR can adjust the
    # service-computed figures before approval.
    class Meta:
        model = FinalSettlement
        fields = ["case", "settlement_date",
                  "prorata_salary", "leave_encashment_days", "leave_encashment_amount",
                  "gratuity_eligible", "gratuity_amount", "bonus_amount",
                  "reimbursement_amount", "other_income",
                  "notice_recovery_amount", "loan_recovery", "asset_deduction",
                  "advance_recovery", "tax_deduction", "professional_tax", "other_deduction",
                  "notes"]

    def clean(self):
        cleaned = super().clean()
        case = cleaned.get("case")
        # One settlement per case (also DB-enforced via unique_together) — surface a friendly error
        # rather than an IntegrityError 500.
        if case and self.tenant is not None:
            dupes = FinalSettlement.objects.filter(tenant=self.tenant, case=case)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error("case", "A settlement already exists for this separation case.")
        return cleaned


# ----------------------------------------------------------------------- 3.5 Job Requisition
class JobDescriptionTemplateForm(TenantModelForm):
    class Meta:
        model = JobDescriptionTemplate
        fields = ["name", "designation", "employment_type", "jd_summary", "jd_responsibilities",
                  "jd_requirements", "jd_nice_to_have", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["designation"].queryset = (
                Designation.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))


class JobRequisitionForm(TenantModelForm):
    # SECURITY: the workflow-owned fields (`status`, `submitted_at`, `approved_at`, `posted_at`,
    # `filled_at`) and the auto `number` are excluded — advanced only by the audited POST actions.
    # Mirrors the SeparationCaseForm exclusion pattern (prevents status forging via a crafted POST).
    class Meta:
        model = JobRequisition
        fields = ["title", "designation", "job_grade", "template", "department", "cost_center",
                  "location", "headcount", "req_type", "employment_type", "reason_for_hire",
                  "is_replacement_for", "posting_type", "hiring_manager", "recruiter",
                  "target_start_date", "priority", "salary_min", "salary_max", "salary_currency",
                  "estimated_annual_cost", "hiring_cost_budget", "jd_summary", "jd_responsibilities",
                  "jd_requirements", "jd_nice_to_have", "notes"]
        widgets = {"target_start_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["designation"].queryset = (
                Designation.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("level_order", "name"))
            self.fields["template"].queryset = (
                JobDescriptionTemplate.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("name"))
            self.fields["department"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            self.fields["cost_center"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="cost_center").order_by("name"))
            employees = (EmployeeProfile.objects.filter(tenant=self.tenant)
                         .select_related("party").order_by("party__name"))
            self.fields["hiring_manager"].queryset = employees
            self.fields["recruiter"].queryset = employees

    def clean(self):
        cleaned = super().clean()
        salary_min = cleaned.get("salary_min")
        salary_max = cleaned.get("salary_max")
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            self.add_error("salary_max", "Salary minimum cannot exceed maximum.")
        headcount = cleaned.get("headcount")
        if headcount is not None and headcount < 1:
            self.add_error("headcount", "Headcount must be at least 1.")
        return cleaned


class RequisitionApprovalForm(TenantModelForm):
    # SECURITY: `status`, `decided_at`, `decided_by` are excluded — set only by the approve/reject/
    # return actions. `requisition` is set in the view (the step is added from the requisition hub).
    class Meta:
        model = RequisitionApproval
        fields = ["step_order", "approver", "approver_role", "comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Approvers are tenant users (an approval step authorizes a hire for this workspace).
        if self.tenant is not None:
            self.fields["approver"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True)
                .order_by("username"))
        else:
            self.fields["approver"].queryset = get_user_model().objects.none()


# ----------------------------------------------------------------------- 3.6 Candidate Management
class CandidateTagForm(TenantModelForm):
    class Meta:
        model = CandidateTag
        fields = ["name", "color", "description"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def clean_color(self):
        # Defense-in-depth: the value is interpolated into a CSS `style=` attribute on the badge, so a
        # non-hex value (e.g. "red;background:url(//evil)") would be CSS-injection. Enforce strict hex
        # here too, not only via the model validator.
        color = (self.cleaned_data.get("color") or "").strip()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise forms.ValidationError("Enter a valid hex color, e.g. #3B82F6.")
        return color


class CandidateProfileForm(TenantModelForm):
    # SECURITY: `party` is set in the view (a fresh person Party is minted per candidate); `status`,
    # `gdpr_consent_date` are workflow-owned; `tags` are managed via inline POST actions on the hub.
    class Meta:
        model = CandidateProfile
        fields = ["first_name", "last_name", "email", "phone", "linkedin_url", "current_job_title",
                  "current_employer", "city", "country", "years_of_experience", "highest_qualification",
                  "skill_set", "resume_file", "resume_text", "photo", "gender", "source",
                  "expected_salary", "notice_period_days", "sourced_by", "do_not_contact",
                  "gdpr_consent", "gdpr_consent_expires", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["sourced_by"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
        else:
            self.fields["sourced_by"].queryset = get_user_model().objects.none()

    def clean_email(self):
        # Enforce the (tenant, email) uniqueness as a friendly form error rather than a 500 on the
        # DB constraint (mirrors the duplicate-detection anchor in every ATS product).
        email = self.cleaned_data["email"]
        if self.tenant is not None:
            qs = CandidateProfile.objects.filter(tenant=self.tenant, email__iexact=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A candidate with this email already exists in this workspace.")
        return email

    def clean_resume_file(self):
        return _validate_resume(self.cleaned_data.get("resume_file"))

    def clean_photo(self):
        f = self.cleaned_data.get("photo")
        if f and hasattr(f, "name") and hasattr(f, "size"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_PHOTO_EXTENSIONS:
                raise forms.ValidationError(f"Photo type '{ext}' is not allowed. Use JPG, PNG, WebP or GIF.")
            if f.size and f.size > MAX_PHOTO_BYTES:
                raise forms.ValidationError("Photo exceeds the 5 MB limit.")
        return f


class CandidateSkillForm(TenantModelForm):
    # Inline-add on the candidate detail hub; `candidate` is set in the view.
    class Meta:
        model = CandidateSkill
        fields = ["skill_name", "proficiency", "source"]


class JobApplicationForm(TenantModelForm):
    # SECURITY: `stage`, `stage_changed_at`, `hired_on`, `rejection_reason`, `rejection_notes` are
    # workflow-owned (set only by the stage-move / reject actions). `screening_answers` is captured by
    # the public apply flow, not hand-edited here.
    class Meta:
        model = JobApplication
        fields = ["candidate", "requisition", "source", "referred_by", "cover_letter_text",
                  "cover_letter_file", "rating", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["candidate"].queryset = (
                CandidateProfile.objects.filter(tenant=self.tenant).order_by("-created_at"))
            # Explicit tenant scope (not just the TenantModelForm base) — a recruiter can only file an
            # application against a requisition in their own workspace.
            self.fields["requisition"].queryset = (
                JobRequisition.objects.filter(tenant=self.tenant).order_by("-created_at"))
            self.fields["referred_by"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))

    def clean_cover_letter_file(self):
        return _validate_resume(self.cleaned_data.get("cover_letter_file"))

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not (1 <= rating <= 5):
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating


class CandidateEmailTemplateForm(TenantModelForm):
    class Meta:
        model = CandidateEmailTemplate
        fields = ["name", "template_type", "subject", "body_html", "is_active", "is_auto_send"]


class PublicApplicationForm(forms.Form):
    """Unauthenticated career-portal application form (3.6) — a plain ``forms.Form`` (no tenant binding;
    the requisition's public_token already pins the tenant in the view). Resume is required."""

    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-input"}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-input"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-input"}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    linkedin_url = forms.URLField(required=False, widget=forms.URLInput(attrs={"class": "form-input"}))
    city = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    resume_file = forms.FileField(widget=forms.ClearableFileInput(attrs={"class": "form-input",
                                                                         "accept": ".pdf,.doc,.docx"}))
    cover_letter_text = forms.CharField(required=False, widget=forms.Textarea(
        attrs={"class": "form-textarea", "rows": 5}))
    source = forms.ChoiceField(choices=CANDIDATE_SOURCE_CHOICES, initial="careers_page",
                               widget=forms.Select(attrs={"class": "form-select"}))
    gdpr_consent = forms.BooleanField(required=True, widget=forms.CheckboxInput(attrs={"class": "form-check"}),
        label="I consent to the storage and processing of my personal data for recruitment purposes.")

    def clean_resume_file(self):
        return _validate_resume(self.cleaned_data.get("resume_file"))


def _validate_resume(f):
    """Shared resume/cover-letter upload guard — documents only (PDF/DOC/DOCX), 10 MB cap.
    Validates a freshly-uploaded file only (an existing FieldFile has no new size to re-check)."""
    return _validate_upload(f, allowed_ext=ALLOWED_RESUME_EXTENSIONS, max_bytes=MAX_RESUME_BYTES)


def _validate_upload(f, *, allowed_ext, max_bytes, label="File"):
    """Generic upload guard — extension allowlist + size cap. Validates a freshly-uploaded file only
    (an existing FieldFile has no new size to re-check)."""
    if f and hasattr(f, "name") and hasattr(f, "size"):
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in allowed_ext:
            raise forms.ValidationError(
                f"{label} type '{ext}' is not allowed. Use {', '.join(sorted(allowed_ext))}.")
        if f.size and f.size > max_bytes:
            raise forms.ValidationError(f"{label} exceeds the {max_bytes // (1024 * 1024)} MB limit.")
        # WARNING: extension allowlist only — keep MEDIA_ROOT outside the web root and serve uploads with
        # Content-Disposition: attachment + X-Content-Type-Options: nosniff (mirrors onboarding docs).
    return f


# ----------------------------------------------------------------------- 3.7 Interview Process
class InterviewForm(TenantModelForm):
    # SECURITY/workflow: `status` (state machine), `scheduled_by` (set to request.user in the view),
    # `reminder_sent_at`/`feedback_reminder_sent_at` (stamped by the send-reminder actions) are OUT of
    # the form. `scheduled_at` gets the round-tripping datetime-local widget from TenantModelForm.
    class Meta:
        model = Interview
        fields = ["application", "title", "round_number", "mode", "scheduled_at", "duration_minutes",
                  "location", "video_provider", "meeting_url", "interviewer_instructions", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            # select_related the dropdown's __str__ traversal (candidate + requisition) to avoid an
            # N+1 per option; the base already tenant-scopes the queryset.
            self.fields["application"].queryset = (
                JobApplication.objects.filter(tenant=self.tenant)
                .select_related("candidate", "requisition").order_by("-applied_at"))


class InterviewPanelistForm(TenantModelForm):
    # Inline-add on the interview detail hub; `interview` is set in the view. `rsvp_status`/`notified_at`
    # are workflow-owned (the rsvp action / send-invite stamp them).
    class Meta:
        model = InterviewPanelist
        fields = ["interviewer", "role", "briefing_notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["interviewer"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
        else:
            self.fields["interviewer"].queryset = get_user_model().objects.none()


class InterviewFeedbackForm(TenantModelForm):
    # `number` auto; `submitted_by`/`submitted_at` AND `is_submitted` are workflow-owned — submission is
    # the dedicated submit POST action only (a form checkbox would let a submitted card be un-submitted).
    class Meta:
        model = InterviewFeedback
        fields = ["interview", "panelist", "overall_recommendation", "summary"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["interview"].queryset = (
                Interview.objects.filter(tenant=self.tenant)
                .select_related("application__candidate").order_by("-scheduled_at"))
            # Scope the panelist picker to the chosen interview's panel: on edit the interview is fixed;
            # on create it comes from ?interview= (initial) or the bound POST (data). When it can't be
            # resolved (or is junk), fall back to the full tenant list — clean() (below) still rejects a
            # cross-interview pick server-side, and the isdigit guard stops a hand-edited ?interview=abc
            # from raising ValueError while building the queryset.
            interview_id = None
            if self.instance and self.instance.pk and self.instance.interview_id:
                interview_id = self.instance.interview_id
            else:
                raw = (self.initial or {}).get("interview") or (self.data or {}).get("interview")
                if raw and str(raw).isdigit():
                    interview_id = int(raw)
            if interview_id:
                panel_qs = InterviewPanelist.objects.filter(interview_id=interview_id, tenant=self.tenant)
            else:
                panel_qs = InterviewPanelist.objects.filter(tenant=self.tenant)
            self.fields["panelist"].queryset = (
                panel_qs.select_related("interviewer", "interview").order_by("interview__pk", "role"))
        self.fields["panelist"].required = False

    def clean(self):
        cleaned = super().clean()
        interview = cleaned.get("interview")
        panelist = cleaned.get("panelist")
        if panelist and interview and panelist.interview_id != interview.id:
            self.add_error("panelist", "That panelist is not on the selected interview.")
        return cleaned


class FeedbackCriterionForm(TenantModelForm):
    # Inline-add on the feedback detail hub; `feedback` is set in the view.
    class Meta:
        model = FeedbackCriterion
        fields = ["criterion_name", "rating", "notes"]
        widgets = {"rating": forms.NumberInput(attrs={"min": 1, "max": 5})}

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not (1 <= rating <= 5):
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating


# ----------------------------------------------------------------------- 3.8 Offer Management
class OfferLetterTemplateForm(TenantModelForm):
    class Meta:
        model = OfferLetterTemplate
        fields = ["name", "is_active", "body_html"]


class OfferForm(TenantModelForm):
    # SECURITY/workflow: `status` (state machine), the workflow stamps (`extended_by`/`extended_at`/
    # `accepted_at`/`declined_at`/`rescinded_at`/`created_by`) and the auto `number` are excluded — set
    # only by the audited POST actions. `decline_reason`/`decline_notes`/`signature_status` stay on the
    # form as recruiter-editable annotations (mirrors JobApplication.rejection_* being form-editable).
    class Meta:
        model = Offer
        fields = ["application", "offer_letter_template", "base_salary", "currency", "bonus_amount",
                  "bonus_terms", "signing_bonus", "equity_terms", "relocation_assistance",
                  "benefits_summary", "start_date", "expires_on", "decline_reason", "decline_notes",
                  "signed_document", "signature_status", "notes"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}),
                   "expires_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional on the form so a blank submission defaults from the requisition's salary_currency in
        # the view; the model still carries "USD" as the ultimate fallback.
        self.fields["currency"].required = False
        if self.tenant is not None:
            # select_related the dropdown's __str__ traversal (candidate) to avoid an N+1 per option.
            self.fields["application"].queryset = (
                JobApplication.objects.filter(tenant=self.tenant)
                .select_related("candidate", "requisition").order_by("-applied_at"))
            self.fields["offer_letter_template"].queryset = (
                OfferLetterTemplate.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))

    def clean(self):
        cleaned = super().clean()
        for field in ("base_salary", "bonus_amount", "signing_bonus", "relocation_assistance"):
            value = cleaned.get(field)
            if value is not None and value < 0:
                self.add_error(field, "Amount cannot be negative.")
        return cleaned

    def clean_signed_document(self):
        return _validate_upload(self.cleaned_data.get("signed_document"),
                                allowed_ext=ALLOWED_OFFER_DOC_EXTENSIONS, max_bytes=MAX_OFFER_DOC_BYTES,
                                label="Signed document")


class OfferApprovalForm(TenantModelForm):
    # SECURITY: `status`, `decided_at`, `decided_by` are excluded — set only by the approve/reject
    # actions. `offer` is set in the view (the step is added from the offer hub). Mirrors
    # RequisitionApprovalForm exactly.
    class Meta:
        model = OfferApproval
        fields = ["step_order", "approver", "approver_role", "comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["approver"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
        else:
            self.fields["approver"].queryset = get_user_model().objects.none()


class BackgroundVerificationForm(TenantModelForm):
    # SECURITY/workflow: `status` (lifecycle), `result` (set only by the complete action — a form-editable
    # result would bypass the consent→initiate→complete gate), `initiated_at`/`completed_at`/`initiated_by`/
    # `consent_date` (workflow stamps) and the auto `number` are excluded. `offer` is set in the view (from
    # ?offer= or the FK dropdown on plain create).
    class Meta:
        model = BackgroundVerification
        fields = ["offer", "vendor", "check_type", "consent_given", "report_file", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["offer"].queryset = (
                Offer.objects.filter(tenant=self.tenant)
                .select_related("application__candidate").order_by("-created_at"))

    def clean_report_file(self):
        return _validate_upload(self.cleaned_data.get("report_file"),
                                allowed_ext=ALLOWED_OFFER_DOC_EXTENSIONS, max_bytes=MAX_OFFER_DOC_BYTES,
                                label="Report")


class PreboardingItemForm(TenantModelForm):
    # Inline-add on the offer detail hub; `offer` is set in the view. `status`/`submitted_at`/
    # `verified_by`/`verified_at`/`reminder_sent_at` are workflow-owned (the submit/verify/reject/
    # send-invite actions stamp them).
    class Meta:
        model = PreboardingItem
        fields = ["document_type", "is_required", "uploaded_file", "notes"]

    def clean_uploaded_file(self):
        return _validate_upload(self.cleaned_data.get("uploaded_file"),
                                allowed_ext=ALLOWED_PREBOARDING_DOC_EXTENSIONS, max_bytes=MAX_OFFER_DOC_BYTES,
                                label="Document")


# ----------------------------------------------------------------------- 3.13 Salary Structure
class PayComponentForm(TenantModelForm):
    class Meta:
        model = PayComponent
        fields = ["name", "code", "component_type", "variable_subtype", "calculation_type",
                  "default_amount", "default_percentage", "frequency", "is_taxable", "include_in_ctc",
                  "contribution_side", "annual_cap_amount", "requires_bill", "is_active",
                  "display_order", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class SalaryStructureTemplateForm(TenantModelForm):
    class Meta:
        model = SalaryStructureTemplate
        fields = ["name", "job_grade", "annual_ctc_amount", "currency", "is_active", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Offer only active grades (the base form already tenant-scopes the FK).
        if self.tenant is not None and "job_grade" in self.fields:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True).order_by("level_order", "name"))


class SalaryStructureLineForm(TenantModelForm):
    # `template` is set by the view from the URL, never a form field (no cross-template injection).
    class Meta:
        model = SalaryStructureLine
        fields = ["pay_component", "calculation_type", "amount", "percentage", "sequence"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "pay_component" in self.fields:
            self.fields["pay_component"].queryset = (
                PayComponent.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("display_order", "name"))
        # Blank calc-type defers to the component's own calculation_type.
        if "calculation_type" in self.fields:
            self.fields["calculation_type"].required = False

    def clean(self):
        cleaned = super().clean()
        # `template` is excluded from the form (set by the view), so Django's
        # (tenant, template, pay_component) unique_together check is skipped by validate_unique. Do the
        # duplicate check here — otherwise a repeated component surfaces as a raw IntegrityError 500 on
        # save instead of a friendly field error. The view presets instance.template before validation.
        pc = cleaned.get("pay_component")
        if self.instance.template_id and pc is not None and self.tenant is not None:
            dupes = (SalaryStructureLine.objects
                     .filter(tenant=self.tenant, template_id=self.instance.template_id, pay_component=pc)
                     .exclude(pk=self.instance.pk))
            if dupes.exists():
                raise forms.ValidationError(
                    {"pay_component": "This component is already in this salary structure."})
        return cleaned


class EmployeeSalaryStructureForm(TenantModelForm):
    class Meta:
        model = EmployeeSalaryStructure
        fields = ["employee", "template", "annual_ctc_amount", "effective_from", "effective_to",
                  "status", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # employee is tenant-scoped + name-ordered by the base form / EmployeeProfile.Meta.
        if self.tenant is not None and "template" in self.fields:
            self.fields["template"].queryset = (
                SalaryStructureTemplate.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))


# ----------------------------------------------------------------------- 3.14 Payroll Processing
class PayrollCycleForm(TenantModelForm):
    # status / submitted_by / approved_by / accounting_payroll_run are workflow-owned (set by the
    # generate/submit/approve/reject/lock actions), never form fields.
    class Meta:
        model = PayrollCycle
        fields = ["period_start", "period_end", "pay_date", "cycle_type", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class PayslipForm(TenantModelForm):
    # Only the manual inputs — gross/deductions/net/lop_amount are derived by recompute() (called by the
    # view after save); on_hold/hold_reason go through the dedicated hold/release actions.
    class Meta:
        model = Payslip
        fields = ["days_worked", "lop_days", "arrears_amount", "bonus_amount"]


# ----------------------------------------------------------------------- 3.15 Statutory Compliance
class StatutoryConfigForm(TenantModelForm):
    # tenant is set via StatutoryConfig.for_tenant() (one row per tenant) — never a form field.
    class Meta:
        model = StatutoryConfig
        fields = ["pf_establishment_code", "pf_wage_ceiling", "pf_employee_rate", "pf_employer_rate",
                  "esi_employer_code", "esi_wage_ceiling", "esi_employee_rate", "esi_employer_rate",
                  "pt_default_state", "tan_number", "tds_circle_address", "pan_of_deductor",
                  "is_lwf_applicable"]
        widgets = {
            "tds_circle_address": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }


class StatutoryStateRuleForm(TenantModelForm):
    # PT-only and LWF-only fields are all shown; model.clean() enforces which are required by scheme.
    class Meta:
        model = StatutoryStateRule
        fields = ["state", "scheme", "income_from", "income_to", "pt_monthly_amount",
                  "pt_deduction_month", "lwf_employee_contribution", "lwf_employer_contribution",
                  "lwf_periodicity", "lwf_due_month_1", "lwf_due_month_2", "registration_number",
                  "is_active", "effective_from"]

    def clean(self):
        # The model.clean() "one active LWF rule per (tenant, state)" guard can't fire on CREATE via
        # crud_create — tenant is assigned only AFTER form.is_valid(), so self.tenant_id is None at
        # model-validation time. Enforce that one case here (the form DOES have self.tenant), guarding
        # only the create path (instance.pk is None) so an edit doesn't double-report — model.clean()
        # already covers edit, where the instance carries a real tenant. Mirrors StatutoryReturnForm.clean().
        cleaned = super().clean()
        if self.instance.pk is None and self.tenant is not None:
            if cleaned.get("scheme") == "lwf" and cleaned.get("is_active") and cleaned.get("state"):
                if StatutoryStateRule.objects.filter(
                        tenant=self.tenant, state=cleaned["state"], scheme="lwf", is_active=True).exists():
                    raise forms.ValidationError(
                        "An active LWF rule already exists for this state — deactivate it first.")
        return cleaned


class EmployeeStatutoryIdentifierForm(TenantModelForm):
    class Meta:
        model = EmployeeStatutoryIdentifier
        fields = ["employee", "uan_number", "pf_number", "esi_number", "pt_state",
                  "is_pf_applicable", "is_esi_applicable"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "employee" in self.fields:
            qs = EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
            # On create (no instance pk) narrow to employees without an identifier row so the
            # OneToOne can't collide; on edit keep the current employee selectable.
            if self.instance.pk is None:
                qs = qs.exclude(statutory_identifiers__isnull=False)
            self.fields["employee"].queryset = qs.order_by("party__name")


class StatutoryReturnForm(TenantModelForm):
    # number + all derived totals + the filing/payment workflow fields are set by the model /
    # generate / mark_* actions — this form only carries the return's metadata.
    class Meta:
        model = StatutoryReturn
        fields = ["scheme", "period_type", "period_start", "period_end", "cycle", "employee",
                  "due_date", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "cycle" in self.fields:
                self.fields["cycle"].queryset = (
                    PayrollCycle.objects.filter(tenant=self.tenant).order_by("-pay_date"))
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))

    def clean(self):
        # One return per (tenant, scheme, period_start, employee). Enforced here at the FORM level
        # (not model.clean) because tenant is excluded from the form and only set in the view AFTER
        # validation — so a model.clean() guard couldn't see it on create; self.tenant always can.
        # This closes the org-level (employee=None) duplicate hole that unique_together leaves open,
        # since MariaDB treats NULL as distinct in a unique index (mirrors the StatutoryStateRule LWF
        # NULL-uniqueness concern).
        cleaned = super().clean()
        scheme = cleaned.get("scheme")
        period_start = cleaned.get("period_start")
        employee = cleaned.get("employee")
        if self.tenant is not None and scheme and period_start:
            dupe = StatutoryReturn.objects.filter(
                tenant=self.tenant, scheme=scheme, period_start=period_start, employee=employee)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                raise forms.ValidationError(
                    "A statutory return for this scheme, period start and employee already exists.")
        return cleaned


# ----------------------------------------------------------------------- 3.16 Tax & Investment
class TaxRegimeConfigForm(TenantModelForm):
    class Meta:
        model = TaxRegimeConfig
        fields = ["financial_year", "regime", "standard_deduction", "cess_rate",
                  "rebate_income_threshold", "rebate_max_tax", "is_default_regime", "tax_law_reference"]


class TaxSlabBandForm(TenantModelForm):
    # config is set from the parent config in the inline-management view, never a free-choice dropdown.
    class Meta:
        model = TaxSlabBand
        fields = ["income_from", "income_to", "rate_percent", "sequence"]


class InvestmentDeclarationForm(TenantModelForm):
    # number / status / submitted_at are workflow-owned (submit/lock actions), never form fields.
    class Meta:
        model = InvestmentDeclaration
        fields = ["employee", "financial_year", "regime_elected", "declaration_window_open",
                  "declaration_window_close", "proof_window_open", "proof_window_close",
                  "previous_employer_income", "previous_employer_tds", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "employee" in self.fields:
            self.fields["employee"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))


class InvestmentDeclarationLineForm(TenantModelForm):
    # declaration is set from the parent in the inline view; verified_amount is proof-derived.
    class Meta:
        model = InvestmentDeclarationLine
        fields = ["section_code", "declared_amount", "monthly_rent_amount", "is_metro_city",
                  "landlord_pan", "lender_name", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }


class InvestmentProofForm(TenantModelForm):
    # verification_status / verified_by / verified_at / rejection_reason are workflow-owned — set only
    # by the verify/reject/on_hold POST actions, never on this upload form.
    class Meta:
        model = InvestmentProof
        fields = ["file", "title", "amount", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def clean_file(self):
        # Reuse the shared extension+size guard (docs/images, 10 MB), mirroring EmployeeDocumentForm.
        return _validate_upload(self.cleaned_data.get("file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Proof")


class TaxComputationForm(TenantModelForm):
    # number + all derived (tax_payable/tax_paid_ytd/monthly_tds_amount) + statutory_return/computed_at
    # are set by recompute()/link_form16(), never form-typed.
    class Meta:
        model = TaxComputation
        fields = ["employee", "declaration", "computation_type", "manual_override_amount",
                  "override_reason", "remaining_pay_periods", "notes"]
        widgets = {
            "override_reason": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "declaration" in self.fields:
                self.fields["declaration"].queryset = (
                    InvestmentDeclaration.objects.filter(tenant=self.tenant)
                    .select_related("employee__party").order_by("-financial_year"))

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get("employee")
        declaration = cleaned.get("declaration")
        if employee and declaration:
            # The employee must own the chosen declaration (the engine mixes self.employee for TDS/salary
            # with self.declaration for the deduction lines — a mismatch would compute the wrong person).
            if declaration.employee_id != employee.pk:
                raise forms.ValidationError("The selected employee must match the declaration's employee.")
            # Denormalize financial_year FROM the declaration (the field is excluded from the form) — a
            # blank FY would silently compute zero tax (no matching TaxRegimeConfig).
            self.instance.financial_year = declaration.financial_year
            # One computation per (tenant, employee, FY) — enforced here since the excluded tenant/FY
            # fields keep ModelForm.validate_unique() from catching it (else it would 500 at the DB).
            if self.tenant is not None:
                dup = TaxComputation.objects.filter(
                    tenant=self.tenant, employee=employee, financial_year=declaration.financial_year)
                if self.instance.pk:
                    dup = dup.exclude(pk=self.instance.pk)
                if dup.exists():
                    raise forms.ValidationError(
                        "A tax computation for this employee and financial year already exists.")
        return cleaned


# ----------------------------------------------------------------------- 3.17 Payout & Reports
class PayoutBatchForm(TenantModelForm):
    # number + all workflow/derived fields (status/generated_*/approved_*/disbursed_at) are set by the
    # generate/approve/disburse actions, never form-typed.
    class Meta:
        model = PayoutBatch
        fields = ["cycle", "bank_file_format", "source_bank_name", "source_account_last4", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "cycle" in self.fields:
            # Only LOCKED cycles can be paid out — a draft/pending/approved cycle must never appear; on
            # create, also drop cycles that already have a batch (one batch per cycle).
            qs = PayrollCycle.objects.filter(tenant=self.tenant, status="locked")
            if self.instance.pk is None:
                qs = qs.exclude(payout_batches__isnull=False)
            self.fields["cycle"].queryset = qs.order_by("-pay_date")

    def clean(self):
        # Enforce the (tenant, cycle) uniqueness at the FORM level — ModelForm.validate_unique() can't
        # (tenant is excluded + only set post-validation in crud_create), so a duplicate would otherwise
        # 500 at the DB. self.tenant is available here. Mirrors FinalSettlementForm.clean().
        cleaned = super().clean()
        cycle = cleaned.get("cycle")
        if cycle and self.tenant is not None:
            dup = PayoutBatch.objects.filter(tenant=self.tenant, cycle=cycle)
            if self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise forms.ValidationError("A payout batch already exists for this payroll cycle.")
        return cleaned


class BankReconciliationForm(TenantModelForm):
    # number + matched/unmatched aggregates + reconciled_by/at are set by recompute()/the reconcile action.
    class Meta:
        model = BankReconciliation
        fields = ["batch", "statement_date", "statement_reference", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "batch" in self.fields:
            self.fields["batch"].queryset = (
                PayoutBatch.objects.filter(tenant=self.tenant).select_related("cycle").order_by("-created_at"))


# ------------------------------------------------------------------------- 3.18 Goal Setting
class GoalPeriodForm(TenantModelForm):
    # GoalPeriod has no in-module FKs; the tenant= kwarg is kept for signature consistency.
    # `status` is workflow-owned (create starts "draft"; only the @tenant_admin_required
    # activate/close actions change it) — NOT a directly-editable field, else a regular user
    # could POST status=active/closed and bypass the admin gate.
    class Meta:
        model = GoalPeriod
        fields = ["name", "period_type", "start_date", "end_date", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class ObjectiveForm(TenantModelForm):
    # number is auto-assigned; progress_pct/health_status are derived, never form-typed.
    class Meta:
        model = Objective
        fields = ["title", "description", "owner", "goal_period", "parent_objective", "department",
                  "scope", "target_type", "weight", "status", "start_date", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "goal_period" in self.fields:
                self.fields["goal_period"].queryset = (
                    GoalPeriod.objects.filter(tenant=self.tenant).order_by("-start_date"))
            if "department" in self.fields:
                self.fields["department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "parent_objective" in self.fields:
                # Exclude self so an objective can't be picked as its own parent (model clean() also guards).
                qs = Objective.objects.filter(tenant=self.tenant).select_related("goal_period").order_by("title")
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                self.fields["parent_objective"].queryset = qs


class KeyResultForm(TenantModelForm):
    # objective is set from the URL in the nested create view; progress/health are derived.
    class Meta:
        model = KeyResult
        fields = ["title", "metric_type", "start_value", "target_value", "current_value",
                  "is_milestone_event", "unit", "weight", "status"]


class GoalCheckInForm(TenantModelForm):
    # key_result + created_by are set from the URL/request in the view; number is auto-assigned.
    class Meta:
        model = GoalCheckIn
        fields = ["checkin_date", "value_at_checkin", "confidence", "is_milestone_event", "comment"]
        widgets = {
            "checkin_date": forms.DateInput(attrs={"type": "date"}),
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }
