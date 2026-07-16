"""HRM 3.1 Employee Management — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


# ============================================================ 3.1 Employee Management (completion)
def _is_hr_admin(user):
    """A tenant admin (or superuser) may view confidential personnel documents."""
    return user.is_superuser or getattr(user, "is_tenant_admin", False)


def _employee_child_create(request, form_class, template, *, stamp_initiated_by=False):
    """Shared create for the employee child entities (documents / lifecycle events): tenant guard,
    ``?employee=<pk>`` pre-fill (these pages are reached from the employee detail hub), save + audit,
    then redirect back to the employee detail hub. Mirrors ``_offboarding_create``.

    Contract: every caller MUST be ``@login_required``."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    # Validate the ?employee= pk once so the template's Cancel link can't NoReverseMatch on
    # crafted input (e.g. ?employee=abc).
    emp_pk = request.GET.get("employee", "").strip()
    cancel_employee = emp_pk if emp_pk.isdigit() else None
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if stamp_initiated_by:
                obj.initiated_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("hrm:employee_detail", pk=obj.employee_id)
    else:
        form = form_class(tenant=request.tenant,
                          initial={"employee": emp_pk} if cancel_employee else None)
    return render(request, template, {"form": form, "is_edit": False,
                                      "cancel_employee": cancel_employee})
