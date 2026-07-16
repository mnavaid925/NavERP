"""HRM 3.39 Compliance & Legal — Hrpolicy views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.ComplianceLegal._helpers import _annotate_policy_acks
from apps.hrm.models import (
    EmployeeProfile,
    HRPolicy,
    PolicyAcknowledgment,
)
from apps.hrm.forms import (
    HRPolicyForm,
)
from apps.hrm.views.ComplianceLegal._helpers import _annotate_policy_acks
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


@login_required
def hrpolicy_list(request):
    is_admin = _is_admin(request.user)
    # defer the long free-text columns — the list renders neither.
    qs = (HRPolicy.objects.filter(tenant=request.tenant).select_related("applicable_org_unit")
          .defer("body", "summary"))
    if not is_admin:
        qs = qs.filter(status="published")  # employees only ever see published policies
    # EXPLICIT order_by: annotate() adds a GROUP BY which drops Meta.ordering and would otherwise leave
    # the paginator unordered (rows duplicate/skip across pages).
    qs = _annotate_policy_acks(qs).order_by("-created_at")
    return crud_list(request, qs, "hrm/compliance/hrpolicy/list.html",
                     search_fields=["number", "title", "summary", "body"],
                     filters=[("status", "status", False), ("category", "category", False)],
                     extra_context={"is_admin": is_admin,
                                    "status_choices": HRPolicy.STATUS_CHOICES,
                                    "category_choices": HRPolicy.CATEGORY_CHOICES})


@tenant_admin_required
def hrpolicy_create(request):
    return crud_create(request, form_class=HRPolicyForm, template="hrm/compliance/hrpolicy/form.html",
                       success_url="hrm:hrpolicy_list")


@login_required
def hrpolicy_detail(request, pk):
    obj = get_object_or_404(
        _annotate_policy_acks(
            HRPolicy.objects.select_related("applicable_org_unit", "previous_version")),
        pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request.user)
    if obj.status != "published" and not is_admin:
        raise PermissionDenied("This policy isn't published.")
    profile = _current_employee_profile(request)
    my_ack = (obj.acknowledgments.filter(employee=profile).first() if profile else None)
    return render(request, "hrm/compliance/hrpolicy/detail.html", {
        "obj": obj, "is_admin": is_admin, "my_ack": my_ack})


@tenant_admin_required
def hrpolicy_edit(request, pk):
    return crud_edit(request, model=HRPolicy, pk=pk, form_class=HRPolicyForm,
                     template="hrm/compliance/hrpolicy/form.html", success_url="hrm:hrpolicy_list")


@tenant_admin_required
@require_POST
def hrpolicy_delete(request, pk):
    return crud_delete(request, model=HRPolicy, pk=pk, success_url="hrm:hrpolicy_list")


@tenant_admin_required
@require_POST
def hrpolicy_publish(request, pk):
    """Publish a policy and, when it requires acknowledgment, raise a pending PolicyAcknowledgment for
    every targeted employee (the whole tenant, or just the applicable org unit). Atomic + idempotent:
    re-publishing tops up any employees who joined since, without duplicating existing rows."""
    obj = get_object_or_404(HRPolicy, pk=pk, tenant=request.tenant)
    if obj.status == "published":
        messages.error(request, "This policy is already published.")
        return redirect("hrm:hrpolicy_detail", pk=obj.pk)

    # Only the pks are needed — don't materialize whole EmployeeProfile rows for a large tenant.
    targets = EmployeeProfile.objects.filter(tenant=request.tenant)
    if obj.applicable_org_unit_id:
        targets = targets.filter(employment__org_unit_id=obj.applicable_org_unit_id)
    target_pks = list(targets.values_list("pk", flat=True))

    try:
        # Savepoint: the `existing` set is read INSIDE the transaction but the status guard above is
        # not, so two concurrent publishes can both get here and collide on
        # unique_together(tenant, policy, employee). That must roll this insert back and report a
        # friendly error, never surface as an unhandled IntegrityError (a 500).
        with transaction.atomic():
            obj.status = "published"
            obj.published_at = timezone.now()
            obj.save(update_fields=["status", "published_at", "updated_at"])
            created = 0
            if obj.requires_acknowledgment:
                existing = set(obj.acknowledgments.values_list("employee_id", flat=True))
                new_rows = [PolicyAcknowledgment(tenant=request.tenant, policy=obj, employee_id=pk_)
                            for pk_ in target_pks if pk_ not in existing]
                PolicyAcknowledgment.objects.bulk_create(new_rows)
                created = len(new_rows)
    except IntegrityError:
        messages.error(request, "This policy was published by someone else just now. Reload to see it.")
        return redirect("hrm:hrpolicy_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "update", {"action": "publish", "acknowledgments": created})
    messages.success(request, f"Policy published. {created} acknowledgment request(s) raised.")
    return redirect("hrm:hrpolicy_detail", pk=obj.pk)
