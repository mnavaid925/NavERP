"""HRM 3.4 Employee Offboarding — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    SeparationCase,
)


# ============================================================ 3.4 Employee Offboarding
def _offboarding_create(request, form_class, template, redirect_resolver):
    """Shared create for the offboarding models: tenant guard, ``?case=<pk>`` pre-fill (the child
    create pages are reached from the case hub), save + audit, then redirect via
    ``redirect_resolver(obj)`` → ``(view_name, pk)``. Mirrors ``apps.core.crud.crud_create`` but adds
    the initial-case pre-fill and a pk-aware redirect (crud_create can only redirect to a bare name).

    Contract: every caller MUST be ``@login_required`` (this helper writes an audit row with
    ``request.user`` and assumes an authenticated session)."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            view_name, pk = redirect_resolver(obj)
            return redirect(view_name, pk=pk)
    else:
        initial = {}
        case_pk = request.GET.get("case", "").strip()
        if case_pk.isdigit():
            initial["case"] = case_pk
        form = form_class(tenant=request.tenant, initial=initial or None)
    return render(request, template, {"form": form, "is_edit": False})


def _generate_letter(request, pk, *, kind, template):
    """Shared relieving/experience letter generator: gate on a cleared case, stamp the
    generated-at/by once, then render the print-ready letter (Content-Disposition: inline)."""
    obj = get_object_or_404(
        SeparationCase.objects.select_related(
            "employee__party", "employee__employment", "employee__employment__org_unit",
            "employee__designation"),
        pk=pk, tenant=request.tenant)
    if obj.status not in SeparationCase.LETTER_READY_STATUSES:
        messages.error(request, "Letters can only be generated once the case is cleared.")
        return redirect("hrm:separationcase_detail", pk=obj.pk)
    if kind == "relieving" and obj.relieving_letter_generated_at is None:
        obj.relieving_letter_generated_at = timezone.now()
        obj.relieving_letter_generated_by = request.user
        obj.save(update_fields=["relieving_letter_generated_at",
                                "relieving_letter_generated_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "generate_relieving_letter"})
    elif kind == "experience" and obj.experience_letter_generated_at is None:
        obj.experience_letter_generated_at = timezone.now()
        obj.experience_letter_generated_by = request.user
        obj.save(update_fields=["experience_letter_generated_at",
                                "experience_letter_generated_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "generate_experience_letter"})
    emp = obj.employee
    response = render(request, template, {
        "case": obj,
        "employee": emp,
        "employment": emp.employment if emp.employment_id else None,
        "tenant": request.tenant,
        "today": timezone.localdate(),
    })
    response["Content-Disposition"] = "inline"
    return response
