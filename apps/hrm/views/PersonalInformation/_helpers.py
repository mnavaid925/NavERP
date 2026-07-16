"""HRM 3.25 Personal Information — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeBankAccount,
    EmployeeInfoChangeRequest,
    EmployeeProfile,
    FamilyMember,
    _json_safe,
)
from apps.hrm.forms import (
    BankAccountChangeForm,
    FamilyMemberChangeForm,
    ProfileFieldChangeForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _changed


def _require_own_profile(request):
    """Resolve the requester's own EmployeeProfile, or return ``(None, redirect)`` for a user with no
    linked employee record (e.g. the superuser) — the ESS hub pages only make sense with a profile."""
    profile = _current_employee_profile(request)
    if profile is None:
        messages.error(request,
                        "Your account isn't linked to an employee record, so there's no personal info to show.")
        return None, redirect("hrm:hrm_overview")
    return profile, None


def _can_manage_own_child(request, obj):
    """A self-service row (emergency contact / bank account / family member / change request) is
    manageable by a tenant admin or by the employee who owns it (mirrors _can_edit_review's shape)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and obj.employee_id == profile.pk


def _ss_scope(request, qs):
    """Restrict a self-service queryset: an admin sees the whole tenant; a plain employee sees only
    their own rows; an employee-less user sees nothing."""
    if _is_admin(request.user):
        return qs
    profile = _current_employee_profile(request)
    if profile is None:
        return qs.none()
    return qs.filter(employee=profile)


def _ss_employees(request):
    """The tenant's employee dropdown for the admin filter/picker (party-joined, name-ordered)."""
    return (EmployeeProfile.objects.filter(tenant=request.tenant)
            .select_related("party").order_by("party__name"))


def _is_own_change_request(request, obj):
    """Maker-checker separation: the acting user is the MAKER (submitted it) or the SUBJECT (their own
    record), so they must NOT also be the CHECKER who approves/rejects it."""
    if obj.requested_by_id and obj.requested_by_id == request.user.id:
        return True
    profile = _current_employee_profile(request)
    return profile is not None and obj.employee_id == profile.pk


# ---------------------------------------------------------------- Shared self-service child CRUD
def _ss_child_create(request, form_class, template, list_url):
    """Create a self-service child row: a non-admin creates for THEMSELVES; an admin may target
    ``?employee=<id>`` (GET) or ``employee_pk`` (POST). Mirrors _employee_child_create."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    is_admin = _is_admin(request.user)
    own = _current_employee_profile(request)
    target = own
    if is_admin:
        emp_pk = (request.GET.get("employee", "") or request.POST.get("employee_pk", "")).strip()
        if emp_pk.isdigit():
            target = EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_pk)).first() or own
    if target is None:
        messages.error(request, "Select an employee to attach this record to.")
        return redirect(list_url)
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.employee = target
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect(list_url)
    else:
        form = form_class(tenant=request.tenant)
    return render(request, template, {
        "form": form, "is_edit": False, "is_admin": is_admin,
        "target_employee": target, "employees": _ss_employees(request) if is_admin else None,
    })


def _ss_child_edit(request, model, pk, form_class, template, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only edit your own records.")
        return redirect(detail_url, pk=obj.pk)
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            # changes=_changed(form) redacts account_number (etc.) per _SENSITIVE_AUDIT_FIELDS.
            write_audit_log(request.user, obj, "update", changes=_changed(form))
            messages.success(request, "Updated successfully.")
            return redirect(detail_url, pk=obj.pk)
    else:
        form = form_class(instance=obj, tenant=request.tenant)
    return render(request, template, {
        "form": form, "obj": obj, "is_edit": True, "is_admin": _is_admin(request.user),
        "target_employee": obj.employee, "employees": None,
    })


def _ss_child_detail(request, model, pk, template, select_related=()):
    qs = model.objects.filter(tenant=request.tenant)
    if select_related:
        qs = qs.select_related(*select_related)
    obj = get_object_or_404(qs, pk=pk)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This record belongs to another employee.")
    # `is_own` lets a detail template hide review actions on the viewer's OWN row (e.g. the 3.26
    # self-approval guard: an admin can't approve/reject their own request). Harmless extra context
    # for the 3.25 child templates, which don't reference it.
    profile = _current_employee_profile(request)
    is_own = profile is not None and obj.employee_id == profile.pk
    return render(request, template,
                  {"obj": obj, "is_admin": _is_admin(request.user), "is_own": is_own})


def _ss_child_delete(request, model, pk, list_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only delete your own records.")
        return redirect(list_url)
    if request.method == "POST":
        # A GenericForeignKey gives no referential integrity on the TARGET row's deletion, so a
        # pending change request pointing at this row would be left dangling (unapprovable). Auto-cancel
        # any such request so nothing is silently orphaned (a no-op for EmergencyContact — never a target).
        ct = ContentType.objects.get_for_model(model)
        cancelled = EmployeeInfoChangeRequest.objects.filter(
            tenant=obj.tenant, content_type=ct, object_id=obj.pk, status="pending"
        ).update(status="cancelled", decision_note="Auto-cancelled: the target record was deleted.")
        write_audit_log(request.user, obj, "delete")
        obj.delete()
        msg = "Deleted successfully."
        if cancelled:
            msg += f" {cancelled} pending change request(s) targeting it were cancelled."
        messages.success(request, msg)
    return redirect(list_url)


# ---------------------------------------------------------------- Change Requests (maker-checker)
_CHANGE_FORMS = {"profile_field": ProfileFieldChangeForm, "bank": BankAccountChangeForm,
                 "family": FamilyMemberChangeForm}


_BANK_CR_FIELDS = ["bank_name", "account_holder_name", "account_number", "routing_number",
                   "account_type", "split_percentage"]


_FAMILY_CR_FIELDS = ["name", "relationship", "date_of_birth", "gender", "occupation", "phone",
                     "is_dependent", "is_minor", "guardian_name", "guardian_relationship",
                     "is_nominee", "nominee_percentage"]


def _assemble_change_request(request, employee, req_type, form):
    """Build (unsaved) an EmployeeInfoChangeRequest from a validated sub-form: resolve
    content_type/object_id server-side (never trusting the client) and snapshot the old→new
    field_changes JSON."""
    cd = form.cleaned_data
    cr = EmployeeInfoChangeRequest(tenant=request.tenant, employee=employee, request_type=req_type,
                                   reason=cd.get("reason", ""), requested_by=request.user)
    if req_type == "profile_field":
        field = cd["field_name"]
        old = employee.party.name if field == "legal_name" else getattr(employee, field, None)
        cr.content_type = ContentType.objects.get_for_model(EmployeeProfile)
        cr.object_id = employee.pk
        cr.field_changes = {field: {"old": _json_safe(old), "new": _json_safe(cd["new_value"])}}
    else:
        existing = cd.get("existing_account") if req_type == "bank" else cd.get("existing_member")
        model = EmployeeBankAccount if req_type == "bank" else FamilyMember
        fields = _BANK_CR_FIELDS if req_type == "bank" else _FAMILY_CR_FIELDS
        cr.content_type = ContentType.objects.get_for_model(model)
        cr.object_id = existing.pk if existing else None
        cr.field_changes = {
            f: {"old": _json_safe(getattr(existing, f, None)) if existing else None,
                "new": _json_safe(cd.get(f))}
            for f in fields
        }
    return cr


# Change-request diff keys whose raw value must be masked when rendered (the field_changes JSON stores
# the plaintext account/routing number; every other surface uses masked_account_number()).
_SENSITIVE_DIFF_FIELDS = frozenset({"account_number", "routing_number"})


def _mask_diff_value(field, value):
    if value and field in _SENSITIVE_DIFF_FIELDS:
        return EmployeeBankAccount._mask_last4(value)
    return value


def _resolve_cr_employee(request, is_admin, own):
    """Resolve the subject employee for a change request: admins may target ?employee/employee_pk,
    everyone else is forced to themselves."""
    if is_admin:
        emp_pk = (request.GET.get("employee", "") or request.POST.get("employee_pk", "")).strip()
        if emp_pk.isdigit():
            return EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_pk)).first() or own
    return own
