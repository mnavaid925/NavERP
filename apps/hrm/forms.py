"""HRM forms — one ``TenantModelForm`` per model. The shared base
(``apps.core.forms.TenantModelForm``) auto-scopes every FK dropdown to the active tenant and
applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``, and
system-computed fields (``days``, ``hours_worked``, ``approved_at``, ``confirmed_on``,
``rejected_reason``/``cancelled_reason`` — set by the workflow actions in the view).
"""
from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import Party

from .models import (
    AttendanceRecord,
    Designation,
    EmployeeProfile,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
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
