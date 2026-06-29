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
from .models import (  # noqa: E402  — 3.6 Candidate Management
    CANDIDATE_SOURCE_CHOICES,
    CandidateEmailTemplate,
    CandidateProfile,
    CandidateSkill,
    CandidateTag,
    JobApplication,
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
    if f and hasattr(f, "name") and hasattr(f, "size"):
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_RESUME_EXTENSIONS:
            raise forms.ValidationError(f"File type '{ext}' is not allowed. Use PDF, DOC or DOCX.")
        if f.size and f.size > MAX_RESUME_BYTES:
            raise forms.ValidationError("File exceeds the 10 MB limit.")
        # WARNING: extension allowlist only — keep MEDIA_ROOT outside the web root and serve uploads with
        # Content-Disposition: attachment + X-Content-Type-Options: nosniff (mirrors onboarding docs).
    return f
