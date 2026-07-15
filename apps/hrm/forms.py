"""HRM forms — one ``TenantModelForm`` per model. The shared base
(``apps.core.forms.TenantModelForm``) auto-scopes every FK dropdown to the active tenant and
applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``, and
system-computed fields (``days``, ``hours_worked``, ``approved_at``, ``confirmed_on``,
``rejected_reason``/``cancelled_reason`` — set by the workflow actions in the view).
"""
import os
import re
from decimal import Decimal

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

# 3.23 LMS SCORM package upload safety: a zipped package only + a 50 MB cap.
ALLOWED_SCORM_EXTENSIONS = {".zip"}
MAX_SCORM_BYTES = 50 * 1024 * 1024  # 50 MB

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
from .models import (  # noqa: E402  — 3.19 Performance Review
    PerformanceReview,
    ReviewCycle,
    ReviewRating,
    ReviewTemplate,
)
from .models import (  # noqa: E402  — 3.20 Continuous Feedback
    Feedback,
    KudosBadge,
    MeetingActionItem,
    OneOnOneMeeting,
)
from .models import (  # noqa: E402  — 3.21 Performance Improvement
    CoachingNote,
    PIPCheckIn,
    PerformanceImprovementPlan,
    WarningLetter,
)
from .models import (  # noqa: E402  — 3.22 Training Management
    TrainingCourse,
    TrainingSession,
)
from .models import (  # noqa: E402  — 3.23 Learning Management (LMS)
    LearningContentItem,
    LearningPath,
    LearningPathItem,
    LearningProgress,
)
from .models import (  # noqa: E402  — 3.24 Training Administration
    TrainingAttendance,
    TrainingCertificate,
    TrainingFeedback,
    TrainingNomination,
)
from .models import (  # noqa: E402  — 3.25 Personal Information (Self-Service)
    EmergencyContact,
    EmployeeBankAccount,
    EmployeeInfoChangeRequest,
    FamilyMember,
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
        return _validate_upload(self.cleaned_data.get("photo"),
                                allowed_ext=ALLOWED_PHOTO_EXTENSIONS, max_bytes=MAX_PHOTO_BYTES, label="Photo")


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
        return _validate_upload(self.cleaned_data.get("file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="File")


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
        # WARNING: extension allowlist only (a renamed file passes). Keep MEDIA_ROOT outside the web
        # root (README) and serve uploads with Content-Disposition: attachment +
        # X-Content-Type-Options: nosniff. Add MIME sniffing (python-magic) when that dep lands.
        return _validate_upload(self.cleaned_data.get("file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="File")


class AssetAllocationForm(TenantModelForm):
    # `issued_at` / `issued_by` are stamped by the Issue action (and `returned_at` by Return) — kept
    # out of the form so they can't be hand-spoofed/back-dated. `status` stays editable so HR can
    # record lost/damaged; the Issue/Return actions own the issued↔returned transition + timestamps.
    class Meta:
        model = AssetAllocation
        # `asset` (optional) links this issuance to a specific 3.33 register row — when set, saving
        # this form syncs Asset.status/current_holder via AssetAllocation._sync_linked_asset().
        fields = ["program", "employee", "asset", "asset_name", "asset_category", "serial_number",
                  "asset_tag", "status", "return_due_date", "notes"]

    def clean(self):
        cleaned = super().clean()
        asset, status = cleaned.get("asset"), cleaned.get("status")
        # Don't let an "issued" allocation link an asset that already has another active (issued)
        # allocation — that would double-issue one register asset (bypassing the asset_assign guard).
        if asset and status == "issued":
            clash = asset.allocations.filter(status="issued").exclude(pk=self.instance.pk).exists()
            if clash:
                self.add_error("asset", "This asset already has an active (issued) allocation. "
                                        "Return it before re-issuing.")
        return cleaned


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
        return _validate_upload(self.cleaned_data.get("resignation_letter"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="File")


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
        return _validate_upload(self.cleaned_data.get("photo"),
                                allowed_ext=ALLOWED_PHOTO_EXTENSIONS, max_bytes=MAX_PHOTO_BYTES, label="Photo")


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
    (an existing FieldFile has no new size to re-check). The extension is enforced whenever the upload
    exposes a name; the size cap applies only when a size attribute is present (some file-like wrappers
    omit it), so a name-only upload is still extension-checked rather than skipped."""
    if f and hasattr(f, "name"):
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in allowed_ext:
            raise forms.ValidationError(
                f"{label} type '{ext}' is not allowed. Use {', '.join(sorted(allowed_ext))}.")
        if hasattr(f, "size") and f.size and f.size > max_bytes:
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


# ------------------------------------------------------------------------- 3.19 Performance Review
class ReviewCycleForm(TenantModelForm):
    # `status` is workflow-owned (the phase machine — changed only via reviewcycle_advance_phase,
    # never a directly-editable field). This mirrors the 3.18 GoalPeriodForm fix: exposing status
    # on the form would let a non-admin POST a phase change and bypass the @tenant_admin_required gate.
    class Meta:
        model = ReviewCycle
        fields = ["name", "cycle_type", "self_review_start", "self_review_end",
                  "manager_review_start", "manager_review_end", "calibration_date",
                  "results_release_date", "goal_period", "description"]
        widgets = {
            "self_review_start": forms.DateInput(attrs={"type": "date"}),
            "self_review_end": forms.DateInput(attrs={"type": "date"}),
            "manager_review_start": forms.DateInput(attrs={"type": "date"}),
            "manager_review_end": forms.DateInput(attrs={"type": "date"}),
            "calibration_date": forms.DateInput(attrs={"type": "date"}),
            "results_release_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "goal_period" in self.fields:
            self.fields["goal_period"].queryset = (
                GoalPeriod.objects.filter(tenant=self.tenant).order_by("-start_date"))


class ReviewTemplateForm(TenantModelForm):
    class Meta:
        model = ReviewTemplate
        fields = ["name", "review_type", "rating_scale_max", "include_goals", "is_anonymous",
                  "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class PerformanceReviewForm(TenantModelForm):
    # number + all workflow/calibration fields (status/manager_rating/calibrated_rating/
    # potential_rating/calibration_notes/*_at/acknowledged_by) are set only by the dedicated
    # submit/share/acknowledge/calibrate actions — never on this create/edit form.
    class Meta:
        model = PerformanceReview
        fields = ["cycle", "template", "subject", "reviewer", "review_type",
                  "strengths", "improvements", "private_notes", "is_anonymous"]
        widgets = {
            "strengths": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "improvements": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "private_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "cycle" in self.fields:
                self.fields["cycle"].queryset = (
                    ReviewCycle.objects.filter(tenant=self.tenant).order_by("-self_review_start"))
            if "template" in self.fields:
                self.fields["template"].queryset = (
                    ReviewTemplate.objects.filter(tenant=self.tenant, is_active=True).order_by("review_type", "name"))
            if "subject" in self.fields:
                self.fields["subject"].queryset = emps
            if "reviewer" in self.fields:
                self.fields["reviewer"].queryset = emps


class CalibrationForm(TenantModelForm):
    # A narrow, privileged form — the ONLY write path to calibrated_rating (the general edit form
    # must never expose it). tenant= kwarg kept for signature consistency (no FK to scope).
    class Meta:
        model = PerformanceReview
        fields = ["calibrated_rating", "potential_rating", "calibration_notes"]
        widgets = {
            "calibration_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class ReviewRatingForm(TenantModelForm):
    # review is set from the URL in the nested create view; number is auto-assigned.
    class Meta:
        model = ReviewRating
        fields = ["criterion_label", "criterion_category", "rating_value", "weight", "comment"]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }


# ------------------------------------------------------------------------- 3.20 Continuous Feedback
class KudosBadgeForm(TenantModelForm):
    # Small catalog (like GoalPeriodForm) — no in-module FK to scope; tenant= kept for signature parity.
    class Meta:
        model = KudosBadge
        fields = ["name", "description", "icon", "color", "linked_value", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class FeedbackForm(TenantModelForm):
    # `giver` is resolved from request.user server-side (never form-typed, mirroring how
    # GoalCheckIn.created_by is set in the view). `status`/`number`/`acknowledged_at` are
    # workflow-owned (the create-as-request path + the feedback_acknowledge action set them) —
    # never on this form, same reasoning as PerformanceReviewForm's workflow fields. `requested_from`
    # is a system linkage set from the ?respond_to= URL param in feedback_create, not a manual field.
    # `is_anonymous` masks the giver on READ only (the FK is still stored).
    class Meta:
        model = Feedback
        fields = ["receiver", "feedback_type", "visibility", "message", "is_anonymous",
                  "badge", "related_objective", "related_review"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, viewer_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "receiver" in self.fields:
                self.fields["receiver"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "badge" in self.fields:
                self.fields["badge"].queryset = (
                    KudosBadge.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
            if "related_objective" in self.fields:
                # Objectives are company-open in NavERP (unlike reviews), so no visibility scoping.
                self.fields["related_objective"].queryset = (
                    Objective.objects.filter(tenant=self.tenant)
                    .select_related("goal_period").order_by("title"))
            if "related_review" in self.fields:
                # Confidentiality (3.19): only surface reviews the FEEDBACK GIVER may see (their own
                # subject/reviewer rows) — never the tenant-wide review roster (who-is-reviewed is
                # confidential). The giver is the edit instance's giver, or (on create) the
                # viewer_profile the view passes.
                giver = self.instance.giver if self.instance and self.instance.giver_id else viewer_profile
                rq = PerformanceReview.objects.filter(tenant=self.tenant).select_related("subject__party")
                rq = rq.filter(Q(subject=giver) | Q(reviewer=giver)) if giver is not None else rq.none()
                self.fields["related_review"].queryset = rq.order_by("-created_at")


class OneOnOneMeetingForm(TenantModelForm):
    # `status` is workflow-owned (changed only via the complete/cancel actions) — exposing it would
    # let a non-admin POST a phase change and bypass the gate (the GoalPeriodForm/ReviewCycleForm fix).
    # `number`/`completed_at` are auto/workflow. `manager_private_notes` STAYS on the form: the writer
    # (the manager) must be able to type it — only the READ side is confidential, gated in the detail view.
    class Meta:
        model = OneOnOneMeeting
        fields = ["manager", "employee", "scheduled_at", "agenda", "shared_notes",
                  "manager_private_notes", "related_objective"]
        widgets = {
            "agenda": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "shared_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "manager_private_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "manager" in self.fields:
                self.fields["manager"].queryset = emps
            if "employee" in self.fields:
                self.fields["employee"].queryset = emps
            if "related_objective" in self.fields:
                self.fields["related_objective"].queryset = (
                    Objective.objects.filter(tenant=self.tenant)
                    .select_related("goal_period").order_by("title"))


class MeetingActionItemForm(TenantModelForm):
    # `meeting` is set from the URL in the nested create view; `status` is toggled only by
    # meetingactionitem_toggle (off the form, like KeyResultForm/ReviewRatingForm workflow fields);
    # `number`/`completed_at` are auto/workflow.
    class Meta:
        model = MeetingActionItem
        fields = ["description", "owner", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "owner" in self.fields:
            # Scope the owner to the 1:1's two participants — an action item must NOT be assignable to
            # an outsider (who could then edit/toggle/delete it while being blocked from viewing the
            # meeting: an inconsistent trust boundary). `meeting` is on the instance (set from the URL
            # on create, or carried by the edited row).
            meeting = self.instance.meeting if self.instance and self.instance.meeting_id else None
            base = EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
            self.fields["owner"].queryset = (
                base.filter(pk__in=[meeting.manager_id, meeting.employee_id]) if meeting is not None else base
            ).order_by("party__name")


# ------------------------------------------------------------------------- 3.21 Performance Improvement
class PerformanceImprovementPlanForm(TenantModelForm):
    # status/outcome/outcome_*/extended_end_date/*_at/*_by are workflow-owned (set only by the
    # hr_approve/acknowledge/close/extend actions — never on this form, mirroring PerformanceReviewForm).
    class Meta:
        model = PerformanceImprovementPlan
        fields = ["subject", "manager", "triggering_review", "performance_issue", "expected_standards",
                  "improvement_goals", "support_provided", "measurement_criteria", "start_date", "end_date"]
        widgets = {
            "performance_issue": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "expected_standards": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "improvement_goals": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "support_provided": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "measurement_criteria": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, viewer_profile=None, viewer_is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "subject" in self.fields:
                self.fields["subject"].queryset = emps
            if "manager" in self.fields:
                self.fields["manager"].queryset = emps
            if "triggering_review" in self.fields:
                # Confidentiality (3.19): a non-admin sees only reviews they may see (their own subject/
                # reviewer rows), NOT the tenant-wide review roster; an admin (full visibility) sees all.
                # Viewer = the PIP's manager (edit) or the passed creator (create); keep the already-linked
                # review selectable on edit.
                rq = PerformanceReview.objects.filter(tenant=self.tenant).select_related("subject__party")
                if not viewer_is_admin:
                    viewer = self.instance.manager if (self.instance and self.instance.manager_id) else viewer_profile
                    rq = rq.filter(Q(subject=viewer) | Q(reviewer=viewer)) if viewer is not None else rq.none()
                    if self.instance and self.instance.triggering_review_id:
                        rq = (rq | PerformanceReview.objects.filter(pk=self.instance.triggering_review_id)).distinct()
                self.fields["triggering_review"].queryset = rq.order_by("-created_at")


class PIPCheckInForm(TenantModelForm):
    # `pip` is set from the URL in the nested create view; `number`/`completed_at` are auto/workflow.
    class Meta:
        model = PIPCheckIn
        fields = ["checkin_date", "progress_rating", "progress_notes"]
        widgets = {
            "checkin_date": forms.DateInput(attrs={"type": "date"}),
            "progress_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }


class WarningLetterForm(TenantModelForm):
    # status/acknowledged_* are workflow-owned (issue/acknowledge actions); employee_response is captured
    # only via the acknowledge action (WarningAcknowledgeForm), never on this edit form; number auto.
    class Meta:
        model = WarningLetter
        fields = ["issued_to", "issued_by", "level", "category", "incident_date", "description",
                  "policy_reference", "related_pip", "expiry_date"]
        widgets = {
            "incident_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, viewer_profile=None, viewer_is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "issued_to" in self.fields:
                self.fields["issued_to"].queryset = emps
            if "issued_by" in self.fields:
                self.fields["issued_by"].queryset = emps
            if "related_pip" in self.fields:
                # PIPs are confidential — a non-admin sees only PIPs they may see (their own subject/
                # manager rows), never the tenant PIP roster; an admin sees all. Viewer = the letter's
                # issuer (edit) or creator (create).
                rq = PerformanceImprovementPlan.objects.filter(tenant=self.tenant).select_related("subject__party")
                if not viewer_is_admin:
                    viewer = self.instance.issued_by if (self.instance and self.instance.issued_by_id) else viewer_profile
                    rq = rq.filter(Q(subject=viewer) | Q(manager=viewer)) if viewer is not None else rq.none()
                    if self.instance and self.instance.related_pip_id:
                        rq = (rq | PerformanceImprovementPlan.objects.filter(pk=self.instance.related_pip_id)).distinct()
                self.fields["related_pip"].queryset = rq.order_by("-start_date")


class CoachingNoteForm(TenantModelForm):
    # `coach` is resolved server-side from request.user (NEVER form-typed — the strictest-confidentiality
    # model; a user must not log a coaching note as someone else, like Feedback.giver); `number` auto.
    class Meta:
        model = CoachingNote
        fields = ["employee", "related_pip", "note_date", "category", "content"]
        widgets = {
            "note_date": forms.DateInput(attrs={"type": "date"}),
            "content": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
        }

    def __init__(self, *args, viewer_profile=None, viewer_is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "related_pip" in self.fields:
                # A non-admin sees only PIPs they may see (their own subject/manager rows); an admin sees all.
                rq = PerformanceImprovementPlan.objects.filter(tenant=self.tenant).select_related("subject__party")
                if not viewer_is_admin:
                    viewer = self.instance.coach if (self.instance and self.instance.coach_id) else viewer_profile
                    rq = rq.filter(Q(subject=viewer) | Q(manager=viewer)) if viewer is not None else rq.none()
                    if self.instance and self.instance.related_pip_id:
                        rq = (rq | PerformanceImprovementPlan.objects.filter(pk=self.instance.related_pip_id)).distinct()
                self.fields["related_pip"].queryset = rq.order_by("-start_date")


class PIPCloseForm(TenantModelForm):
    # The narrow close-with-outcome form (the ONLY write path to outcome/outcome_date/outcome_notes — the
    # general edit form never exposes them). The close VIEW sets status="closed" on the instance before
    # validation so the model's outcome-iff-closed clean() passes. tenant= kept for signature parity.
    class Meta:
        model = PerformanceImprovementPlan
        fields = ["outcome", "outcome_date", "outcome_notes"]
        widgets = {
            "outcome_date": forms.DateInput(attrs={"type": "date"}),
            "outcome_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def clean_outcome(self):
        outcome = self.cleaned_data.get("outcome")
        if not outcome:
            raise forms.ValidationError("Select an outcome to close the plan.")
        return outcome


class WarningAcknowledgeForm(TenantModelForm):
    # Captures the recipient's optional written response at acknowledgment time (the ONLY employee_response
    # write path). tenant= kept for signature parity.
    class Meta:
        model = WarningLetter
        fields = ["employee_response"]
        widgets = {
            "employee_response": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


# ----------------------------------------------------------------------- 3.22 Training Management
class TrainingCourseForm(TenantModelForm):
    # Excludes tenant + auto number. prerequisite_course is tenant-scoped (by TenantModelForm) and,
    # on edit, must not offer the course itself as its own prerequisite.
    class Meta:
        model = TrainingCourse
        fields = ["title", "description", "category", "delivery_mode", "provider_type", "duration_hours",
                  "is_certification", "certification_name", "certification_validity_months",
                  "prerequisite_course", "default_capacity", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "prerequisite_course" in self.fields and self.tenant is not None:
            qs = TrainingCourse.objects.filter(tenant=self.tenant).order_by("title")
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)   # a course can't be its own prerequisite
            self.fields["prerequisite_course"].queryset = qs


class TrainingSessionForm(TenantModelForm):
    # Excludes tenant + auto number. course/instructor_employee are auto tenant-scoped by the base;
    # external_vendor is re-scoped to vendor-role parties, and currency is set from the GLOBAL
    # accounting.Currency master (lazy import — accounting is a runtime, not module-load, dependency).
    class Meta:
        model = TrainingSession
        fields = ["course", "delivery_mode", "status", "start_datetime", "end_datetime", "timezone",
                  "capacity", "waitlist_enabled", "venue_name", "venue_address", "meeting_platform",
                  "meeting_link", "meeting_id", "instructor_employee", "external_instructor_name",
                  "external_vendor", "estimated_cost", "actual_cost", "currency", "invoice_reference", "notes"]
        widgets = {
            # start_datetime/end_datetime get their datetime-local widget + round-trip input_formats
            # from TenantModelForm.__init__ (L22) — no need to re-declare them here.
            "venue_address": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Give the (possibly unsaved) instance its tenant BEFORE validation so the model's clean()
        # double-booking overlap query is tenant-scoped even on create. crud_create only sets
        # obj.tenant AFTER form.is_valid(), so without this the create-path clean() would filter on
        # tenant_id=None and the overlap guard would silently never fire (edit already has it from DB).
        if self.tenant is not None and self.instance is not None:
            self.instance.tenant = self.tenant
        if self.tenant is not None:
            if "external_vendor" in self.fields:
                # The base only filters by tenant; scope to vendor-role parties (mirrors accounting).
                self.fields["external_vendor"].queryset = (
                    Party.objects.filter(tenant=self.tenant, roles__role="vendor").distinct().order_by("name"))
            if "currency" in self.fields:
                from apps.accounting.models import Currency   # lazy — keep accounting a runtime dep
                self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")


# ----------------------------------------------------------------------- 3.23 Learning Management (LMS)
class LearningContentItemForm(TenantModelForm):
    # `course` is set from the URL in the nested create view (mirrors PIPCheckInForm excluding `pip`).
    class Meta:
        model = LearningContentItem
        fields = ["title", "description", "content_type", "sequence", "is_required",
                  "estimated_duration_minutes", "video_url", "document_file", "scorm_package",
                  "external_url", "body_text", "pass_threshold_percent", "max_attempts", "time_limit_minutes"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "body_text": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
        }

    def clean_document_file(self):
        # WARNING: extension allowlist only — keep MEDIA_ROOT outside the web root and serve with
        # Content-Disposition: attachment + X-Content-Type-Options: nosniff in production (mirrors the
        # onboarding-doc upload forms; MEDIA hardening is a tracked README TODO). _validate_upload
        # enforces the extension on name alone, preserving this method's original name-only guard.
        return _validate_upload(self.cleaned_data.get("document_file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Document")

    def clean_scorm_package(self):
        # WARNING: stored as an opaque file only — never extracted this pass. A future SCORM-extraction
        # handler MUST guard against zip-slip / path traversal before writing extracted files to disk.
        # Also (as for every upload here) keep MEDIA_ROOT outside the web root + serve with
        # Content-Disposition: attachment + X-Content-Type-Options: nosniff in production.
        return _validate_upload(self.cleaned_data.get("scorm_package"),
                                allowed_ext=ALLOWED_SCORM_EXTENSIONS,
                                max_bytes=MAX_SCORM_BYTES, label="SCORM package")


class LearningPathForm(TenantModelForm):
    # target_designation/target_department are auto tenant-scoped by TenantModelForm; the model's
    # limit_choices_to={"kind": "department"} narrows the department dropdown to department OrgUnits.
    class Meta:
        model = LearningPath
        fields = ["title", "description", "target_designation", "target_department",
                  "is_mandatory", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }


class LearningPathItemForm(TenantModelForm):
    # `path` is set from the URL in the nested create view; scope `course` to the tenant's active courses.
    class Meta:
        model = LearningPathItem
        fields = ["course", "sequence", "is_mandatory"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "course" in self.fields and self.tenant is not None:
            self.fields["course"].queryset = (
                TrainingCourse.objects.filter(tenant=self.tenant, is_active=True).order_by("title"))

    def clean(self):
        # Enforce the ("tenant","path","course") uniqueness at the form level — like LearningProgressForm,
        # both `tenant` and `path` are excluded from the form, so Django's validate_unique() SKIPS the
        # unique_together and a re-added course would only surface as an IntegrityError 500. `path` is set
        # on the instance by the nested create view (or loaded on edit).
        cleaned = super().clean()
        course = cleaned.get("course")
        path_id = getattr(self.instance, "path_id", None)
        if self.tenant is not None and path_id and course:
            dupes = LearningPathItem.objects.filter(tenant=self.tenant, path_id=path_id, course=course)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError("This course is already in this path.")
        return cleaned


class LearningProgressForm(TenantModelForm):
    class Meta:
        model = LearningProgress
        fields = ["employee", "course", "learning_path", "status", "percent_complete",
                  "time_spent_minutes", "score", "passed", "attempt_count", "points_earned",
                  "started_at", "completed_at"]

    def clean(self):
        # Enforce the ("tenant","employee","course") uniqueness at the form level. Django's ModelForm
        # validate_unique() SKIPS any unique_together that involves an excluded field, and `tenant` is
        # not a form field — so the DB constraint would otherwise only surface as an IntegrityError 500
        # on the flat create path. Check it explicitly here instead.
        cleaned = super().clean()
        employee = cleaned.get("employee")
        course = cleaned.get("course")
        if self.tenant is not None and employee and course:
            dupes = LearningProgress.objects.filter(tenant=self.tenant, employee=employee, course=course)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError("This employee already has a progress record for this course.")
        return cleaned


# ----------------------------------------------------------------------- 3.24 Training Administration
class TrainingNominationForm(TenantModelForm):
    # status/approver/approved_at/rejected_reason/cancelled_reason are workflow-owned (set by the
    # approve/reject/waitlist/cancel/withdraw actions, never on this form); number auto.
    class Meta:
        model = TrainingNomination
        fields = ["session", "employee", "nominated_by", "nomination_type", "justification", "priority"]
        widgets = {"justification": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "session" in self.fields and self.tenant is not None:
            self.fields["session"].queryset = (
                TrainingSession.objects.filter(tenant=self.tenant)
                .exclude(status__in=("cancelled", "postponed")).order_by("-start_datetime"))

    def clean(self):
        # (tenant, session, employee) unique_together — tenant is form-excluded so validate_unique()
        # skips it; check explicitly (the 3.22/3.23 gotcha).
        cleaned = super().clean()
        session, employee = cleaned.get("session"), cleaned.get("employee")
        if self.tenant is not None and session and employee:
            dupes = TrainingNomination.objects.filter(tenant=self.tenant, session=session, employee=employee)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError({"employee": "This employee is already nominated for this session."})
        return cleaned


class TrainingAttendanceForm(TenantModelForm):
    class Meta:
        model = TrainingAttendance
        fields = ["session", "employee", "nomination", "attendance_status", "completion_status",
                  "check_in_at", "check_out_at", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "nomination" in self.fields and self.tenant is not None:
            self.fields["nomination"].queryset = (
                TrainingNomination.objects.filter(tenant=self.tenant, status__in=("approved", "waitlisted"))
                .select_related("employee__party", "session").order_by("-created_at"))

    def clean(self):
        # (tenant, session, employee) unique_together — same form-excluded-tenant gotcha.
        cleaned = super().clean()
        session, employee = cleaned.get("session"), cleaned.get("employee")
        if self.tenant is not None and session and employee:
            dupes = TrainingAttendance.objects.filter(tenant=self.tenant, session=session, employee=employee)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError({"employee": "This employee already has an attendance record for this session."})
        return cleaned


class TrainingFeedbackForm(TenantModelForm):
    # `attendance` is set from the URL in the nested create view (excluded here). ratings 1-5 via
    # model MinValue/MaxValue validators; the form clean() only carries the (tenant, attendance) guard.
    class Meta:
        model = TrainingFeedback
        fields = ["overall_rating", "content_rating", "trainer_rating", "would_recommend",
                  "comments", "is_anonymous"]
        widgets = {"comments": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"})}

    def clean(self):
        # (tenant, attendance) unique_together — BOTH fields form-excluded, so validate_unique() skips
        # it entirely; the nested create view sets self.instance.attendance before is_valid().
        cleaned = super().clean()
        attendance_id = getattr(self.instance, "attendance_id", None)
        if self.tenant is not None and attendance_id:
            dupes = TrainingFeedback.objects.filter(tenant=self.tenant, attendance_id=attendance_id)
            if self.instance and self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError("Feedback has already been submitted for this attendance record.")
        return cleaned


class TrainingCertificateForm(TenantModelForm):
    # number/verification_code/expires_on are auto (save()); status/revoked_reason are workflow-owned.
    class Meta:
        model = TrainingCertificate
        fields = ["employee", "course", "source_attendance", "source_progress", "title", "issued_on"]
        widgets = {"issued_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "course" in self.fields and self.tenant is not None:
            # Only certification-granting courses — but keep an already-linked course selectable on edit.
            qs = TrainingCourse.objects.filter(tenant=self.tenant).filter(
                Q(is_certification=True) | Q(pk=getattr(self.instance, "course_id", None)))
            self.fields["course"].queryset = qs.order_by("title")


# ======================================================= 3.25 Personal Information (Self-Service)
# The child-entity ModelForms all EXCLUDE ``employee`` — the view sets it from
# ``_current_employee_profile(request)`` (non-admin) or an ``?employee=<id>`` picker (admin),
# mirroring the ``_employee_child_create`` pattern. ``verification_status`` is excluded from the bank
# form (model ``editable=False`` — set only by the verify/reject actions).
class EmergencyContactForm(TenantModelForm):
    class Meta:
        model = EmergencyContact
        fields = ["name", "relationship", "phone", "alt_phone", "email", "address",
                  "is_primary", "priority_order", "notes"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2}),
                   "notes": forms.Textarea(attrs={"rows": 2})}


class EmployeeBankAccountForm(TenantModelForm):
    class Meta:
        model = EmployeeBankAccount
        fields = ["bank_name", "account_holder_name", "account_number", "routing_number",
                  "account_type", "is_salary_account", "split_percentage", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class FamilyMemberForm(TenantModelForm):
    class Meta:
        model = FamilyMember
        fields = ["name", "relationship", "date_of_birth", "gender", "occupation", "phone",
                  "is_dependent", "is_minor", "guardian_name", "guardian_relationship",
                  "is_nominee", "nominee_percentage", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class EmployeeProfileMyInfoForm(TenantModelForm):
    """The employee's OWN direct-edit form — the non-gated subset of ``EmployeeProfile`` only
    (address / personal email / mobile / photo). The sensitive fields (legal name / DOB / national
    ID / passport / bank) are NOT here — they change only via ``EmployeeInfoChangeRequest``."""

    class Meta:
        model = EmployeeProfile
        fields = ["current_address", "permanent_address", "personal_email", "mobile", "photo"]
        widgets = {"current_address": forms.Textarea(attrs={"rows": 2}),
                   "permanent_address": forms.Textarea(attrs={"rows": 2})}

    def clean_photo(self):
        return _validate_upload(self.cleaned_data.get("photo"),
                                allowed_ext=ALLOWED_PHOTO_EXTENSIONS, max_bytes=MAX_PHOTO_BYTES, label="Photo")


class _ThemedForm(forms.Form):
    """Plain ``forms.Form`` base that applies the theme widget classes (TenantModelForm does this for
    ModelForms; the change-request forms assemble ``field_changes`` JSON rather than saving a model,
    so they need the same styling loop)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-textarea")
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check")
            else:
                widget.attrs.setdefault("class", "form-input")


class ProfileFieldChangeForm(_ThemedForm):
    """Employee proposes a new value for ONE sensitive ``EmployeeProfile`` field (or legal name). One
    generic text input drives every sensitive field; ``clean()`` validates the value per the selected
    field (date fields must parse; text fields respect the model column's max_length) so a bad value
    is caught at submission, not later at approval time inside ``apply()``."""

    # Date fields must parse; text fields are length-capped to their EmployeeProfile column widths.
    _DATE_FIELDS = ("date_of_birth", "passport_expiry")
    _MAX_LENGTHS = {"legal_name": 255, "national_id": 100, "national_id_type": 50, "passport_number": 50}

    field_name = forms.ChoiceField(
        choices=[(f, f.replace("_", " ").title()) for f in EmployeeInfoChangeRequest.SENSITIVE_PROFILE_FIELDS])
    new_value = forms.CharField(max_length=255, label="New value",
                                help_text="For date fields (Date of Birth / Passport Expiry) use YYYY-MM-DD.")
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        from django.utils.dateparse import parse_date
        cleaned = super().clean()
        field, value = cleaned.get("field_name"), cleaned.get("new_value")
        if not field or value is None:
            return cleaned
        if field in self._DATE_FIELDS and parse_date(value) is None:
            self.add_error("new_value", "Enter a valid date in YYYY-MM-DD format.")
        max_len = self._MAX_LENGTHS.get(field)
        if max_len and len(value) > max_len:
            self.add_error("new_value", f"This value must be at most {max_len} characters.")
        return cleaned


class BankAccountChangeForm(_ThemedForm):
    """Employee proposes a new bank account, or an edit to one of their existing accounts."""

    existing_account = forms.ModelChoiceField(
        queryset=EmployeeBankAccount.objects.none(), required=False,
        empty_label="-- Propose a new account --",
        help_text="Leave blank to add a new account; pick one to edit it.")
    bank_name = forms.CharField(max_length=255)
    account_holder_name = forms.CharField(max_length=255)
    account_number = forms.CharField(max_length=64)
    routing_number = forms.CharField(max_length=20, required=False)
    account_type = forms.ChoiceField(choices=EmployeeBankAccount.ACCOUNT_TYPE_CHOICES)
    split_percentage = forms.DecimalField(max_digits=5, decimal_places=2, required=False,
                                          min_value=0, max_value=100)
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, employee=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee is not None:
            self.fields["existing_account"].queryset = EmployeeBankAccount.objects.filter(
                tenant=tenant, employee=employee).order_by("bank_name")


class FamilyMemberChangeForm(_ThemedForm):
    """Employee proposes a new family member, or an edit to one of their existing members."""

    existing_member = forms.ModelChoiceField(
        queryset=FamilyMember.objects.none(), required=False,
        empty_label="-- Propose a new family member --",
        help_text="Leave blank to add a new member; pick one to edit it.")
    name = forms.CharField(max_length=255)
    relationship = forms.ChoiceField(choices=FamilyMember.RELATIONSHIP_CHOICES)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    gender = forms.ChoiceField(required=False, choices=[("", "---------")] + list(EmployeeProfile.GENDER_CHOICES))
    occupation = forms.CharField(max_length=255, required=False)
    phone = forms.CharField(max_length=30, required=False)
    is_dependent = forms.BooleanField(required=False)
    is_minor = forms.BooleanField(required=False)
    guardian_name = forms.CharField(max_length=255, required=False)
    guardian_relationship = forms.CharField(max_length=100, required=False)
    is_nominee = forms.BooleanField(required=False)
    nominee_percentage = forms.DecimalField(max_digits=5, decimal_places=2, required=False,
                                            min_value=0, max_value=100)
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, employee=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee is not None:
            self.fields["existing_member"].queryset = FamilyMember.objects.filter(
                tenant=tenant, employee=employee).order_by("name")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_minor") and not cleaned.get("guardian_name"):
            self.add_error("guardian_name", "Guardian name is required for a minor family member.")
        return cleaned


# ======================================================= 3.26 Request Management (Self-Service)
from .models import (  # noqa: E402  — 3.26 Request Management (Self-Service)
    AssetRequest,
    DocumentRequest,
    IdCardRequest,
)


class DocumentRequestForm(TenantModelForm):
    """Employee's official-letter request. Workflow fields (status/approver/approved_at/
    decision_note/fulfilled_at/output_file) are set by the approve/fulfill actions, and `employee`
    is resolved server-side by _ss_child_create — none appear on the form."""

    class Meta:
        model = DocumentRequest
        fields = ["document_type", "purpose", "addressed_to", "copies", "delivery_method", "needed_by"]
        widgets = {"purpose": forms.Textarea(attrs={"rows": 3})}


class IdCardRequestForm(TenantModelForm):
    """Employee's ID-card request. `card_number`/`issued_at` are stamped by the issue action; the
    reviewer/status fields are workflow-owned — none appear on the form."""

    class Meta:
        model = IdCardRequest
        fields = ["request_type", "reason_type", "reason", "delivery_location"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}


class AssetRequestForm(TenantModelForm):
    """Employee's equipment request. The `allocation` link + reviewer/status fields are set by the
    approve/fulfill actions — none appear on the form."""

    class Meta:
        model = AssetRequest
        fields = ["asset_category", "asset_name", "justification", "priority", "needed_by"]
        widgets = {"justification": forms.Textarea(attrs={"rows": 3})}


class DocumentFulfillForm(_ThemedForm):
    """The optional signed-letter upload captured by the document_fulfill action (admin-only). Reuses
    the shared _validate_upload helper + the onboarding-doc allowlist/size cap — no new constants."""

    output_file = forms.FileField(
        required=False,
        help_text="Optional: attach the signed letter (PDF/DOC/DOCX/JPG/PNG, max 10 MB).")

    def clean_output_file(self):
        return _validate_upload(self.cleaned_data.get("output_file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Letter")


# ======================================================= 3.27 Communication Hub
from .models import (  # noqa: E402  — 3.27 Communication Hub
    Announcement,
    Suggestion,
    Survey,
)


class AnnouncementForm(TenantModelForm):
    """Admin-authored announcement. `status`/`published_at`/`author` are workflow-owned (set by the
    publish action + server-side on create) and excluded. The department/designation targets are
    tenant-scoped automatically by TenantModelForm; `clean()` mirrors the model's matching-target rule
    so a mismatch surfaces inline on the form, not only at full_clean()."""

    class Meta:
        model = Announcement
        fields = ["title", "body", "category", "audience_type",
                  "target_department", "target_designation", "is_pinned", "expires_at"]
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get("audience_type")
        if audience == "department" and not cleaned.get("target_department"):
            self.add_error("target_department", "Select the department this announcement targets.")
        if audience == "designation" and not cleaned.get("target_designation"):
            self.add_error("target_designation", "Select the designation this announcement targets.")
        return cleaned


class SurveyForm(TenantModelForm):
    """Admin-authored survey. `questions` is a JSON list validated by clean_questions (structure, not
    just 'valid JSON'). `status`/`author` are workflow-owned and excluded."""

    class Meta:
        model = Survey
        fields = ["title", "description", "questions", "is_anonymous", "opens_at", "closes_at"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "questions": forms.Textarea(attrs={"rows": 8, "class": "form-textarea",
                                               "placeholder": '[{"text": "How likely are you to recommend us?", "type": "rating"},\n {"text": "What should we improve?", "type": "text"},\n {"text": "Preferred work mode?", "type": "single_choice", "options": ["Remote", "Hybrid", "Onsite"]}]'}),
        }

    def clean_questions(self):
        questions = self.cleaned_data.get("questions")
        if not isinstance(questions, list) or not questions:
            raise forms.ValidationError("Add at least one question as a JSON list of objects.")
        valid_types = {"rating", "text", "single_choice"}
        for idx, item in enumerate(questions, start=1):
            if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                raise forms.ValidationError(f"Question {idx}: each entry needs a non-empty \"text\".")
            qtype = item.get("type")
            if qtype not in valid_types:
                raise forms.ValidationError(
                    f"Question {idx}: \"type\" must be one of rating, text, single_choice.")
            if qtype == "single_choice" and not (isinstance(item.get("options"), list) and item["options"]):
                raise forms.ValidationError(
                    f"Question {idx}: a single_choice question needs a non-empty \"options\" list.")
        return questions


class SuggestionForm(TenantModelForm):
    """Employee's suggestion. `employee` is resolved server-side by _ss_child_create; all workflow
    fields (status/approver/approved_at/decision_note/implementation_note/implemented_at) are excluded.
    Mirrors AssetRequestForm's shape."""

    class Meta:
        model = Suggestion
        fields = ["title", "body", "category", "is_anonymous"]
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}


def build_survey_response_form(questions):
    """Assemble a plain themed Form with one field per survey question (rating -> a 0-10 select,
    single_choice -> a select of the question's options, text -> an optional textarea). Used by
    views.survey_respond — NOT a ModelForm, because SurveyResponse.answers is a JSON map keyed by
    question index. Fields are named `q_<index>` so the view can rebuild the {index: answer} map."""
    fields = {}
    for i, q in enumerate(questions or []):
        label = str(q.get("text") or f"Question {i + 1}")
        qtype = q.get("type")
        if qtype == "rating":
            fields[f"q_{i}"] = forms.ChoiceField(label=label, choices=[(str(n), str(n)) for n in range(11)])
        elif qtype == "single_choice":
            fields[f"q_{i}"] = forms.ChoiceField(label=label, choices=[(o, o) for o in (q.get("options") or [])])
        else:  # text
            fields[f"q_{i}"] = forms.CharField(label=label, required=False,
                                               widget=forms.Textarea(attrs={"rows": 2}))
    return type("SurveyResponseForm", (_ThemedForm,), fields)


from .models import HRDashboard, HRDashboardWidget  # noqa: E402  — 3.32 Analytics Dashboard


class HRDashboardForm(TenantModelForm):
    """A saved HR analytics dashboard. ``is_shared`` (publish tenant-wide) and ``is_default``
    (the owner's landing dashboard) are only offered to tenant admins — for a regular user the
    fields are dropped so the model defaults stand (no privilege escalation via the form). ``owner``
    is never a form field: it is always set to the creating user in the view."""

    class Meta:
        model = HRDashboard
        fields = ["name", "description", "is_shared", "is_default", "layout"]

    def __init__(self, *args, can_share=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_share:
            self.fields.pop("is_shared", None)
            self.fields.pop("is_default", None)


class HRDashboardWidgetForm(TenantModelForm):
    """Widget tile editor. ``dashboard``/``tenant``/``position`` are set in the view. ``clean()``
    rejects a chart type the chosen metric can't render (e.g. a table metric drawn as a line)."""

    class Meta:
        model = HRDashboardWidget
        fields = ["title", "metric", "chart_type", "date_range", "size", "target_value"]

    def clean(self):
        from .analytics import WIDGET_METRICS, allowed_charts
        cleaned = super().clean()
        metric = cleaned.get("metric")
        chart_type = cleaned.get("chart_type")
        if metric and chart_type and metric in WIDGET_METRICS:
            ok = allowed_charts(metric)
            if chart_type not in ok:
                self.add_error("chart_type", "This metric supports: " + ", ".join(ok) + ".")
        return cleaned


from .models import Asset, AssetMaintenance  # noqa: E402  — 3.33 Asset Management


class AssetForm(TenantModelForm):
    """Central asset register. `current_holder` is excluded — it is system-managed by
    AssetAllocation._sync_linked_asset() via the assign/return actions, never hand-edited. `status`
    stays editable so HR can hand-correct it (an out-of-band edit here does NOT create an allocation)."""

    class Meta:
        model = Asset
        fields = ["asset_tag", "name", "category", "manufacturer", "model_number", "serial_number",
                  "status", "condition", "purchase_date", "purchase_cost", "currency", "warranty_expiry",
                  "location", "depreciation_method", "useful_life_months", "salvage_value", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        cost, salvage = cleaned.get("purchase_cost"), cleaned.get("salvage_value")
        if cost is not None and salvage is not None and salvage > cost:
            self.add_error("salvage_value", "Salvage value cannot exceed purchase cost.")
        method = cleaned.get("depreciation_method")
        if method and method != "none" and not cleaned.get("useful_life_months"):
            self.add_error("useful_life_months",
                           "Useful life (months) is required for this depreciation method.")
        # Don't let a hand-edit set the asset back to in_stock while an issued allocation is still
        # open (that would desync current_holder + allow a double-issue) — return it properly first.
        if self.instance.pk and cleaned.get("status") == "in_stock":
            if self.instance.allocations.filter(status="issued").exists():
                self.add_error("status", "Return the active allocation before setting this asset "
                                         "back to in-stock.")
        return cleaned


class AssetMaintenanceForm(TenantModelForm):
    class Meta:
        model = AssetMaintenance
        fields = ["asset", "maintenance_type", "status", "scheduled_date", "completed_date", "vendor",
                  "cost", "contract_start", "contract_end", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        sched, comp = cleaned.get("scheduled_date"), cleaned.get("completed_date")
        if sched and comp and comp < sched:
            self.add_error("completed_date", "Completed date cannot be before the scheduled date.")
        cs, ce = cleaned.get("contract_start"), cleaned.get("contract_end")
        if cs and ce and ce <= cs:
            self.add_error("contract_end", "Contract end date must be after the contract start date.")
        return cleaned


from .models import ExpenseCategory, ExpenseClaim, ExpenseClaimLine  # noqa: E402  — 3.34 Expense Management


class ExpenseCategoryForm(TenantModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "code", "description", "per_claim_limit", "monthly_limit",
                  "requires_receipt_above", "gl_account_hint", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        for f in ("per_claim_limit", "monthly_limit", "requires_receipt_above"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        return cleaned


class ExpenseClaimForm(TenantModelForm):
    # status / approvers / timestamps / payment are workflow-owned (set by the action views);
    # employee is resolved server-side by _ss_child_create/_ss_child_edit, not on the form.
    class Meta:
        model = ExpenseClaim
        fields = ["title", "purpose", "period_start", "period_end", "currency"]
        widgets = {"purpose": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Period end cannot be before period start.")
        return cleaned


class ExpenseClaimLineForm(TenantModelForm):
    # claim / tenant are set by the view; multipart for the receipt upload.
    class Meta:
        model = ExpenseClaimLine
        fields = ["category", "expense_date", "merchant", "description", "amount", "receipt"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def clean_receipt(self):
        return _validate_upload(self.cleaned_data.get("receipt"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Receipt")


from .models import TravelPolicy, TravelRequest, TravelBooking  # noqa: E402  — 3.35 Travel Management


class TravelPolicyForm(TenantModelForm):
    class Meta:
        model = TravelPolicy
        fields = ["name", "job_grade", "trip_type", "travel_class", "daily_allowance_limit",
                  "hotel_limit_per_night", "advance_percent_limit", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "job_grade" in self.fields:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True).order_by("level_order", "name"))

    def clean(self):
        cleaned = super().clean()
        for f in ("daily_allowance_limit", "hotel_limit_per_night"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        pct = cleaned.get("advance_percent_limit")
        if pct is not None and not (0 <= pct <= 100):
            self.add_error("advance_percent_limit", "Must be between 0 and 100.")
        return cleaned


class TravelRequestForm(TenantModelForm):
    # status/approver/approved_at/decision_note/advance_approved/advance_paid_at/advance_reference/
    # settlement_claim are workflow-set; employee is resolved server-side by _ss_child_create.
    class Meta:
        model = TravelRequest
        fields = ["title", "trip_type", "origin", "destination", "purpose", "start_date", "end_date",
                  "policy", "estimated_cost", "currency", "advance_requested"]
        widgets = {"purpose": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "policy" in self.fields:
            self.fields["policy"].queryset = (
                TravelPolicy.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
        if self.tenant is not None and "currency" in self.fields:
            from apps.accounting.models import Currency
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before start date.")
        cost = cleaned.get("estimated_cost")
        if cost is not None and cost < 0:
            self.add_error("estimated_cost", "Must be zero or greater.")
        advance = cleaned.get("advance_requested")
        if advance is not None:
            if advance < 0:
                self.add_error("advance_requested", "Must be zero or greater.")
            elif cost is not None and advance > cost:
                self.add_error("advance_requested", "Cannot request an advance larger than the estimated cost.")
        policy, trip_type = cleaned.get("policy"), cleaned.get("trip_type")
        if policy and trip_type and policy.trip_type != "both" and policy.trip_type != trip_type:
            self.add_error("policy", f"This policy applies to {policy.get_trip_type_display()} trips, "
                                     f"not this {dict(TravelRequest.TRIP_TYPE_CHOICES).get(trip_type, trip_type)} one.")
        return cleaned


class TravelBookingForm(TenantModelForm):
    # travel_request/tenant are set by the view; multipart for the document.
    class Meta:
        model = TravelBooking
        fields = ["booking_type", "vendor", "reference", "depart_date", "return_date", "travel_class",
                  "cost", "document", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        depart, ret = cleaned.get("depart_date"), cleaned.get("return_date")
        if depart and ret and ret < depart:
            self.add_error("return_date", "Return/check-out date cannot be before the depart/check-in date.")
        cost = cleaned.get("cost")
        if cost is not None and cost < 0:
            self.add_error("cost", "Must be zero or greater.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Booking Document")


from .models import (  # noqa: E402  — 3.36 Helpdesk
    HelpdeskCategory, HelpdeskSLAPolicy, HelpdeskTicket, KnowledgeArticle)

# The per-priority (response, resolution) hour-field pairs on HelpdeskSLAPolicy — used by the form's
# clean() so a resolution target can never be shorter than its own response target.
_SLA_HOUR_PAIRS = [
    ("urgent_response_hours", "urgent_resolution_hours", "Urgent"),
    ("high_response_hours", "high_resolution_hours", "High"),
    ("medium_response_hours", "medium_resolution_hours", "Medium"),
    ("low_response_hours", "low_resolution_hours", "Low"),
]


class HelpdeskSLAPolicyForm(TenantModelForm):
    class Meta:
        model = HelpdeskSLAPolicy
        fields = ["name", "description",
                  "urgent_response_hours", "urgent_resolution_hours",
                  "high_response_hours", "high_resolution_hours",
                  "medium_response_hours", "medium_resolution_hours",
                  "low_response_hours", "low_resolution_hours",
                  "is_active", "is_default"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        for resp_f, res_f, label in _SLA_HOUR_PAIRS:
            resp, res = cleaned.get(resp_f), cleaned.get(res_f)
            if resp is not None and resp < 1:
                self.add_error(resp_f, "Must be at least 1 hour.")
            if res is not None and res < 1:
                self.add_error(res_f, "Must be at least 1 hour.")
            if resp is not None and res is not None and res < resp:
                self.add_error(res_f, f"{label} resolution target cannot be shorter than its response target.")
        return cleaned


class HelpdeskCategoryForm(TenantModelForm):
    class Meta:
        model = HelpdeskCategory
        fields = ["name", "department", "description", "default_assignee", "default_sla_policy", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "default_sla_policy" in self.fields:
            self.fields["default_sla_policy"].queryset = (
                HelpdeskSLAPolicy.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))


class HelpdeskTicketForm(TenantModelForm):
    # status / assignee / sla_policy / all timestamps / CSAT are workflow-owned (set by the action
    # views); employee (the requester) is resolved server-side by _ss_child_create.
    class Meta:
        model = HelpdeskTicket
        fields = ["subject", "description", "category", "priority"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "category" in self.fields:
            self.fields["category"].queryset = (
                HelpdeskCategory.objects.filter(tenant=self.tenant, is_active=True).order_by("department", "name"))


class KnowledgeArticleForm(TenantModelForm):
    # owner / view_count / helpful_count / published_at are set by the view / actions.
    class Meta:
        model = KnowledgeArticle
        fields = ["title", "category", "summary", "body", "tags", "status"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 2}), "body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "category" in self.fields:
            self.fields["category"].queryset = (
                HelpdeskCategory.objects.filter(tenant=self.tenant).order_by("department", "name"))


from .models import (  # noqa: E402  — 3.37 Compensation & Benefits
    SalaryBenchmark, BenefitPlan, EmployeeBenefitEnrollment, EquityGrant)


def _scope_currency(form):
    """Scope a form's ``currency`` field to active currencies (the GLOBAL master isn't tenant-scoped, so
    TenantModelForm's auto-scoper skips it)."""
    if "currency" in form.fields:
        from apps.accounting.models import Currency
        form.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")


class SalaryBenchmarkForm(TenantModelForm):
    class Meta:
        model = SalaryBenchmark
        fields = ["job_grade", "designation", "source", "region", "currency",
                  "percentile_25", "percentile_50", "percentile_75", "percentile_90", "survey_date", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)
        if self.tenant is not None and "job_grade" in self.fields:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True).order_by("level_order", "name"))

    def clean(self):
        cleaned = super().clean()
        # Percentiles should be non-negative and non-decreasing (P25 <= P50 <= P75 <= P90) when present.
        seq = [("percentile_25", "P25"), ("percentile_50", "P50"),
               ("percentile_75", "P75"), ("percentile_90", "P90")]
        prev_field, prev_val = None, None
        for field, label in seq:
            v = cleaned.get(field)
            if v is not None and v < 0:
                self.add_error(field, "Must be zero or greater.")
            elif v is not None and prev_val is not None and v < prev_val:
                self.add_error(field, f"{label} cannot be less than the lower percentile.")
            if v is not None:
                prev_field, prev_val = field, v
        return cleaned


class BenefitPlanForm(TenantModelForm):
    class Meta:
        model = BenefitPlan
        fields = ["name", "plan_type", "provider", "is_flex_credit_eligible", "flex_credit_amount",
                  "employer_cost_monthly", "employee_cost_monthly", "currency", "coverage_tier_options",
                  "enrollment_window_start", "enrollment_window_end", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, name): Django's validate_unique skips it (tenant is excluded from the
        # form), so guard it here — otherwise a duplicate name 500s on save instead of a friendly error.
        name = cleaned.get("name")
        if name and self.tenant is not None:
            dupe = BenefitPlan.objects.filter(tenant=self.tenant, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "A benefit plan with this name already exists.")
        for f in ("flex_credit_amount", "employer_cost_monthly", "employee_cost_monthly"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        start, end = cleaned.get("enrollment_window_start"), cleaned.get("enrollment_window_end")
        if start and end and end < start:
            self.add_error("enrollment_window_end", "Window end cannot be before the start.")
        return cleaned


class EmployeeBenefitEnrollmentForm(TenantModelForm):
    # employee is resolved server-side by _ss_child_create; status/enrolled_at/decided_by are workflow-set.
    # employee_contribution/employer_contribution are DERIVED from the plan in the view — never user-editable
    # (employer_contribution is employer money; a self-service enrollee must not be able to set it).
    class Meta:
        model = EmployeeBenefitEnrollment
        fields = ["plan", "election_choice", "coverage_tier", "effective_from", "effective_to", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "plan" in self.fields:
            self.fields["plan"].queryset = (
                BenefitPlan.objects.filter(tenant=self.tenant, is_active=True).order_by("plan_type", "name"))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("effective_from"), cleaned.get("effective_to")
        if start and end and end < start:
            self.add_error("effective_to", "Effective-to cannot be before effective-from.")
        # unique_together(tenant, employee, plan, effective_from): the form excludes tenant/employee so
        # Django can't validate it. On EDIT (instance has employee) guard against colliding with another
        # enrollment (create is guarded by the view's IntegrityError catch, where employee isn't yet known).
        if self.instance.pk and self.instance.employee_id and self.tenant is not None:
            plan, eff = cleaned.get("plan"), cleaned.get("effective_from")
            if plan and eff:
                dupe = EmployeeBenefitEnrollment.objects.filter(
                    tenant=self.tenant, employee_id=self.instance.employee_id, plan=plan, effective_from=eff
                ).exclude(pk=self.instance.pk)
                if dupe.exists():
                    self.add_error("effective_from",
                                   "This employee already has an enrollment for this plan and effective date.")
        return cleaned


class EquityGrantForm(TenantModelForm):
    # Admin-issued to a chosen employee; exercised_shares/last_exercised_at set by the record-exercise action.
    class Meta:
        model = EquityGrant
        fields = ["employee", "grant_type", "grant_date", "shares_granted", "exercise_price",
                  "fair_market_value_at_grant", "currency", "vesting_start_date", "cliff_months",
                  "vesting_duration_months", "vesting_frequency", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)
        if self.tenant is not None and "employee" in self.fields:
            self.fields["employee"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        shares = cleaned.get("shares_granted")
        if shares is not None and shares <= 0:
            self.add_error("shares_granted", "Must be greater than zero.")
        # Can't shrink a grant below shares already exercised (would corrupt exercisable/unvested math).
        if self.instance.pk and shares is not None and shares < self.instance.exercised_shares:
            self.add_error("shares_granted",
                           f"Cannot be less than the {self.instance.exercised_shares} share(s) already exercised.")
        cliff, dur = cleaned.get("cliff_months"), cleaned.get("vesting_duration_months")
        if cliff is not None and dur is not None and cliff > dur:
            self.add_error("cliff_months", "The cliff cannot be longer than the total vesting duration.")
        for f in ("exercise_price", "fair_market_value_at_grant"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        return cleaned


from .models import (  # noqa: E402  — 3.38 Talent Management & Succession Planning
    TalentPool, TalentPoolMembership, SuccessionPlan, SuccessionCandidate)


class TalentPoolForm(TenantModelForm):
    class Meta:
        model = TalentPool
        fields = ["name", "pool_type", "description", "owner", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "owner" in self.fields:
            self.fields["owner"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, name) — Django skips validate_unique because tenant is form-excluded.
        name = cleaned.get("name")
        if name and self.tenant is not None:
            dupe = TalentPool.objects.filter(tenant=self.tenant, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "A talent pool with this name already exists.")
        return cleaned


class TalentPoolMembershipForm(TenantModelForm):
    class Meta:
        model = TalentPoolMembership
        fields = ["pool", "employee", "joined_on", "status", "review", "performance_rating",
                  "potential_rating", "flight_risk", "retention_action_plan", "notes"]
        widgets = {"retention_action_plan": forms.Textarea(attrs={"rows": 3}),
                   "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "pool" in self.fields:
                self.fields["pool"].queryset = (
                    TalentPool.objects.filter(tenant=self.tenant, is_active=True).order_by("pool_type", "name"))
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        for f in ("performance_rating", "potential_rating"):
            v = cleaned.get(f)
            if v is not None and not (Decimal("1") <= v <= Decimal("5")):
                self.add_error(f, "Must be between 1 and 5.")
        # unique_together(tenant, pool, employee) — guard it (tenant is form-excluded).
        pool, employee = cleaned.get("pool"), cleaned.get("employee")
        if pool and employee and self.tenant is not None:
            dupe = TalentPoolMembership.objects.filter(tenant=self.tenant, pool=pool, employee=employee)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("employee", "This employee is already a member of that talent pool.")
        return cleaned


class SuccessionPlanForm(TenantModelForm):
    class Meta:
        model = SuccessionPlan
        fields = ["critical_role", "department", "incumbent", "vacancy_risk", "status", "review_date", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "critical_role" in self.fields:
                self.fields["critical_role"].queryset = (
                    Designation.objects.filter(tenant=self.tenant).order_by("name"))
            if "incumbent" in self.fields:
                self.fields["incumbent"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))
            if "department" in self.fields:
                self.fields["department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))


class SuccessionCandidateForm(TenantModelForm):
    # plan is set by the view (inline child of a SuccessionPlan).
    class Meta:
        model = SuccessionCandidate
        fields = ["candidate", "readiness", "rank_order", "development_notes"]
        widgets = {"development_notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "candidate" in self.fields:
            self.fields["candidate"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        rank = cleaned.get("rank_order")
        if rank is not None and rank < 1:
            self.add_error("rank_order", "Rank must be 1 or greater.")
        # unique_together(tenant, plan, candidate): plan_id is set on the instance on BOTH add (the
        # view passes SuccessionCandidate(tenant=..., plan=plan)) and edit, so this guard covers both —
        # exclude(pk=self.instance.pk) is a no-op on add (pk is None -> excludes nothing).
        candidate = cleaned.get("candidate")
        if self.instance.plan_id and candidate and self.tenant is not None:
            dupe = SuccessionCandidate.objects.filter(
                tenant=self.tenant, plan_id=self.instance.plan_id, candidate=candidate
            ).exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("candidate", "This employee is already a successor on this plan.")
        return cleaned


from .models import (  # noqa: E402  — 3.39 Compliance & Legal
    ComplianceRegister, EmploymentContract, Grievance, HRPolicy, PolicyAcknowledgment)

# Compliance document uploads (contracts / policies / inspection reports): documents + scans, 10 MB cap.
ALLOWED_COMPLIANCE_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
MAX_COMPLIANCE_DOC_BYTES = 10 * 1024 * 1024


class EmploymentContractForm(TenantModelForm):
    class Meta:
        model = EmploymentContract
        fields = ["employee", "contract_type", "start_date", "end_date", "probation_end_date",
                  "notice_period_days", "designation", "salary_structure", "status", "renewed_from",
                  "document", "signed_on", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))
            if "designation" in self.fields:
                self.fields["designation"].queryset = (
                    Designation.objects.filter(tenant=self.tenant).order_by("name"))
            if "renewed_from" in self.fields:
                qs = EmploymentContract.objects.filter(tenant=self.tenant)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)  # a contract can't renew itself
                self.fields["renewed_from"].queryset = qs.order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        probation = cleaned.get("probation_end_date")
        if start and probation and probation < start:
            self.add_error("probation_end_date", "Probation end cannot be before the start date.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_COMPLIANCE_DOC_EXTENSIONS,
                                max_bytes=MAX_COMPLIANCE_DOC_BYTES, label="Contract Document")


class HRPolicyForm(TenantModelForm):
    # published_at is stamped by the publish action; acknowledgments are raised there too.
    class Meta:
        model = HRPolicy
        fields = ["title", "category", "version_number", "previous_version", "applicable_org_unit",
                  "summary", "body", "document", "status", "effective_from", "requires_acknowledgment"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 2}), "body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "status" in self.fields:
            # WARNING (review finding): "published" must NOT be settable from this form. Publishing
            # goes through hrpolicy_publish, which stamps published_at AND raises a pending
            # PolicyAcknowledgment for every targeted employee. Setting it here would skip both — and
            # then permanently lock the policy out of the real publish action, whose own guard refuses
            # to run on an already-published policy. So the form offers draft/archived only.
            allowed = [c for c in HRPolicy.STATUS_CHOICES if c[0] != "published"]
            if self.instance.pk and self.instance.status == "published":
                # An already-published policy keeps its value (an edit must not silently demote it to
                # draft) and may only move on to archived.
                allowed = [c for c in HRPolicy.STATUS_CHOICES if c[0] in ("published", "archived")]
            self.fields["status"].choices = allowed
        if self.tenant is not None:
            if "applicable_org_unit" in self.fields:
                self.fields["applicable_org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "previous_version" in self.fields:
                qs = HRPolicy.objects.filter(tenant=self.tenant)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)  # a policy can't supersede itself
                self.fields["previous_version"].queryset = qs.order_by("-created_at")

    def clean_status(self):
        """Defence in depth behind the narrowed choices above — a crafted POST must not be able to
        publish a policy (and thereby skip the acknowledgment rows)."""
        status = self.cleaned_data.get("status")
        already_published = bool(self.instance.pk and self.instance.status == "published")
        if status == "published" and not already_published:
            raise forms.ValidationError(
                "Publish a policy from its detail page — that is what raises the acknowledgment "
                "requests. It cannot be published from this form.")
        return status

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, title, version_number) — Django skips validate_unique because tenant is
        # form-excluded, so a duplicate would 500 on save instead of showing a field error.
        title, version = cleaned.get("title"), cleaned.get("version_number")
        if title and version and self.tenant is not None:
            dupe = HRPolicy.objects.filter(tenant=self.tenant, title=title, version_number=version)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("version_number", "This policy already has a version with that number.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_COMPLIANCE_DOC_EXTENSIONS,
                                max_bytes=MAX_COMPLIANCE_DOC_BYTES, label="Policy Document")


class GrievanceForm(TenantModelForm):
    # employee (complainant) is resolved server-side by the create view; status/investigator/resolution/
    # resolved_at are workflow-set by the admin actions.
    class Meta:
        model = Grievance
        fields = ["category", "severity", "subject", "description", "is_anonymous", "related_policy"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "related_policy" in self.fields:
            self.fields["related_policy"].queryset = (
                HRPolicy.objects.filter(tenant=self.tenant, status="published").order_by("title"))


class ComplianceRegisterForm(TenantModelForm):
    class Meta:
        model = ComplianceRegister
        fields = ["register_type", "title", "jurisdiction", "authority", "period_start", "period_end",
                  "due_date", "status", "filed_on", "inspector_name", "findings", "document", "notes"]
        widgets = {"findings": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Period end cannot be before the period start.")
        if cleaned.get("status") == "filed" and not cleaned.get("filed_on"):
            self.add_error("filed_on", "A filed record needs a filing date.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_COMPLIANCE_DOC_EXTENSIONS,
                                max_bytes=MAX_COMPLIANCE_DOC_BYTES, label="Compliance Document")


from .models import (  # noqa: E402  — 3.40 Workforce Planning
    EmployeeSkill, WorkforcePlan, WorkforcePlanLine, WorkforceScenario)


class WorkforcePlanForm(TenantModelForm):
    class Meta:
        model = WorkforcePlan
        fields = ["name", "org_unit", "plan_type", "period_start", "period_end",
                  "growth_assumption_percent", "owner", "currency", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)
        if self.tenant is not None:
            if "org_unit" in self.fields:
                self.fields["org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Period end cannot be before the period start.")
        # unique_together(tenant, name) — Django skips validate_unique (tenant is form-excluded).
        name = cleaned.get("name")
        if name and self.tenant is not None:
            dupe = WorkforcePlan.objects.filter(tenant=self.tenant, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "A workforce plan with this name already exists.")
        return cleaned


class WorkforcePlanLineForm(TenantModelForm):
    # plan is set by the view (inline child).
    class Meta:
        model = WorkforcePlanLine
        fields = ["org_unit", "designation", "current_headcount", "planned_headcount", "hiring_type",
                  "avg_annual_cost", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "org_unit" in self.fields:
                self.fields["org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "designation" in self.fields:
                self.fields["designation"].queryset = (
                    Designation.objects.filter(tenant=self.tenant).order_by("name"))

    def clean(self):
        cleaned = super().clean()
        cost = cleaned.get("avg_annual_cost")
        if cost is not None and cost < 0:
            self.add_error("avg_annual_cost", "Must be zero or greater.")
        return cleaned


class WorkforceScenarioForm(TenantModelForm):
    # `plan` is an editable dropdown. When created from a plan's "New Scenario" link the view seeds
    # initial={"plan": ...} from ?plan=<id>, but the user can always change it here.
    class Meta:
        model = WorkforceScenario
        fields = ["plan", "name", "scenario_type", "affected_org_unit", "description",
                  "headcount_delta", "cost_delta", "is_baseline", "is_selected", "status", "notes"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}),
                   "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "plan" in self.fields:
                self.fields["plan"].queryset = (
                    WorkforcePlan.objects.filter(tenant=self.tenant).order_by("-created_at"))
            if "affected_org_unit" in self.fields:
                self.fields["affected_org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, plan, name) — guarded here (tenant is form-excluded).
        plan, name = cleaned.get("plan"), cleaned.get("name")
        if plan and name and self.tenant is not None:
            dupe = WorkforceScenario.objects.filter(tenant=self.tenant, plan=plan, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "This plan already has a scenario with that name.")
        return cleaned


class EmployeeSkillForm(TenantModelForm):
    # employee is resolved server-side by the create view (own-vs-admin self-service).
    class Meta:
        model = EmployeeSkill
        fields = ["skill_name", "skill_category", "proficiency_level", "years_experience",
                  "is_certified", "certification_name", "last_assessed_date", "is_critical_skill", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, employee, skill_name). The form excludes `employee`, but the view seeds
        # the unsaved instance with it (on ADD and EDIT), so both paths can be guarded here.
        skill = cleaned.get("skill_name")
        if skill and self.instance.employee_id and self.tenant is not None:
            dupe = EmployeeSkill.objects.filter(
                tenant=self.tenant, employee_id=self.instance.employee_id, skill_name=skill)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("skill_name", "This skill is already on the employee's profile.")
        return cleaned


from .models import (  # noqa: E402  — 3.41 Employee Engagement & Wellbeing
    FlexibleWorkArrangement, SurveyActionPlan, WellbeingParticipation, WellbeingProgram)
from .models import Survey as _Survey  # noqa: E402


class SurveyActionPlanForm(TenantModelForm):
    # tenant/number/completed_at are set/managed server-side.
    class Meta:
        model = SurveyActionPlan
        fields = ["survey", "title", "focus_area", "owner", "department", "description",
                  "related_objective", "target_date", "status"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            # NOTE: survey is NOT filtered to status="closed" — an already-linked plan whose survey later
            # reopens must still render its selected option. The help_text conveys the intent instead.
            if "survey" in self.fields:
                self.fields["survey"].queryset = (
                    _Survey.objects.filter(tenant=self.tenant).order_by("-created_at"))
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))
            if "department" in self.fields:
                self.fields["department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "related_objective" in self.fields:
                self.fields["related_objective"].queryset = (
                    Objective.objects.filter(tenant=self.tenant).order_by("title"))


class WellbeingProgramForm(TenantModelForm):
    class Meta:
        model = WellbeingProgram
        fields = ["title", "description", "program_type", "owner", "target_department", "start_date",
                  "end_date", "points_value", "external_resource_url", "is_confidential", "status"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "program_type": "EAP / Counseling is always treated as confidential, regardless of the box below.",
            "is_confidential": "Hides the per-employee roster (aggregate stats only). Forced on for EAP.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
            if "target_department" in self.fields:
                self.fields["target_department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        return cleaned


class WellbeingParticipationForm(TenantModelForm):
    """RSVP / attendance / points row. ``can_admin`` drops the privileged fields for a plain employee
    (mirrors HRDashboardForm(can_share=...)): a non-admin may register or withdraw only, and never
    self-award points or self-mark attended/completed."""

    # tenant/program/employee are all view-resolved (the (tenant, program, employee) unique_together is
    # therefore guarded by an explicit query in the view, not here — Django can't validate_unique it).
    class Meta:
        model = WellbeingParticipation
        fields = ["status", "points_earned", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, can_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_admin:
            # A plain employee can only RSVP or withdraw — never self-mark attendance or award points.
            self.fields.pop("points_earned", None)
            self.fields["status"].choices = [("registered", "Registered"), ("withdrawn", "Withdrawn")]


class FlexibleWorkArrangementForm(TenantModelForm):
    # status/approver/approved_at/decision_note are workflow-set; employee is resolved by _ss_child_create.
    class Meta:
        model = FlexibleWorkArrangement
        fields = ["arrangement_type", "start_date", "end_date", "days_per_week_remote", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        atype = cleaned.get("arrangement_type")
        days = cleaned.get("days_per_week_remote")
        if atype in ("remote", "hybrid"):
            if days is None:
                self.add_error("days_per_week_remote", "Required for a remote or hybrid arrangement.")
            elif not (1 <= days <= 5):
                self.add_error("days_per_week_remote", "Enter a value between 1 and 5.")
        elif days is not None:
            self.add_error("days_per_week_remote",
                           "Only applies to a remote or hybrid arrangement — leave it blank.")
        return cleaned
