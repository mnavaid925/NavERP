"""HRM 3.10 Leave Management — Policy views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.LeaveManagement._helpers import _accrual_target, _policy_year
from apps.hrm.models import (
    EmployeeProfile,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
    ZERO,
)
from apps.hrm.views.LeaveManagement._helpers import _accrual_target, _policy_year


@login_required
def leave_policy(request):
    """Standalone Leave Policy page (no model, mirrors ``org_chart``): each ``LeaveType``'s accrual /
    carry-forward / encashment config for a selected year + admin run actions that mutate allocations."""
    tenant = request.tenant
    year = _policy_year(request)
    leave_types = (LeaveType.objects.filter(tenant=tenant).order_by("name")
                   if tenant is not None else LeaveType.objects.none())
    rows_by_type = {}
    active_employees = 0
    if tenant is not None:
        for r in (LeaveAllocation.objects.filter(tenant=tenant, year=year)
                  .values("leave_type_id")
                  .annotate(n=Count("pk"), total=Sum("allocated_days"), carried=Sum("carried_forward"))):
            rows_by_type[r["leave_type_id"]] = r
        active_employees = (EmployeeProfile.objects.filter(tenant=tenant)
                            .exclude(employment__status="terminated").count())
    policy_rows = [{
        "lt": lt,
        "alloc_count": rows_by_type.get(lt.pk, {}).get("n", 0),
        "total_days": rows_by_type.get(lt.pk, {}).get("total") or Decimal("0"),
        "carried": rows_by_type.get(lt.pk, {}).get("carried") or Decimal("0"),
    } for lt in leave_types]
    return render(request, "hrm/leave/policy.html", {
        "policy_rows": policy_rows,
        "year": year,
        "next_year": year + 1,
        "prev_year": year - 1,
        "active_employees": active_employees,
        "current_year": timezone.localdate().year,
    })


@tenant_admin_required  # accrual mutates every employee's entitlement — privileged
@require_POST
def leave_accrual_run(request):
    tenant = request.tenant
    year = _policy_year(request)
    today = timezone.localdate()
    ZERO = Decimal("0")
    employees = list(EmployeeProfile.objects.filter(tenant=tenant).exclude(employment__status="terminated"))
    leave_types = list(LeaveType.objects.filter(tenant=tenant, is_active=True).exclude(accrual_rule="none"))
    touched = 0
    with transaction.atomic():
        for lt in leave_types:
            target = _accrual_target(lt, year, today.year, today.month)
            cap = lt.max_balance or ZERO
            for emp in employees:
                alloc, _ = LeaveAllocation.objects.get_or_create(
                    tenant=tenant, employee=emp, leave_type=lt, year=year,
                    defaults={"allocated_days": ZERO, "status": "active"})
                total = target + (alloc.carried_forward or ZERO)
                if cap > ZERO:
                    total = min(total, cap)
                if alloc.allocated_days != total or alloc.status != "active":
                    alloc.allocated_days = total
                    alloc.status = "active"
                    alloc.save(update_fields=["allocated_days", "status", "updated_at"])
                    touched += 1
    # AuditLog.action is a 10-char choices field (create/update/delete) — keep the verb in `changes`.
    write_audit_log(request.user, None, "update",
                    changes={"action": "leave_accrual_run", "year": year, "allocations_updated": touched},
                    tenant=tenant)
    messages.success(request, f"Accrual run for {year}: {touched} allocation(s) updated "
                              f"across {len(leave_types)} accruing leave type(s).")
    return redirect(f"{reverse('hrm:leave_policy')}?year={year}")


@tenant_admin_required  # carry-forward mutates next-year entitlements — privileged
@require_POST
def leave_carryforward_run(request):
    tenant = request.tenant
    year = _policy_year(request)
    dest_year = year + 1
    ZERO = Decimal("0")
    leave_types = list(LeaveType.objects.filter(tenant=tenant, is_active=True, max_carry_forward__gt=0))
    type_ids = [lt.pk for lt in leave_types]
    cf_cap = {lt.pk: (lt.max_carry_forward or ZERO) for lt in leave_types}
    bal_cap = {lt.pk: (lt.max_balance or ZERO) for lt in leave_types}  # dest-year total cap
    # Source-year approved usage per (employee, leave_type) in one grouped query (avoids per-row N+1).
    used_map = {}
    for r in (LeaveRequest.objects.filter(tenant=tenant, status="approved", start_date__year=year,
                                          leave_type_id__in=type_ids)
              .values("employee_id", "leave_type_id").annotate(s=Sum("days"))):
        used_map[(r["employee_id"], r["leave_type_id"])] = r["s"] or ZERO
    touched = 0
    with transaction.atomic():
        for src in (LeaveAllocation.objects
                    .filter(tenant=tenant, year=year, leave_type_id__in=type_ids)):
            used = used_map.get((src.employee_id, src.leave_type_id), ZERO)
            # Net out both taken (LeaveRequest) and cashed-out (LeaveEncashment) days — a day already
            # encashed must not also be carried forward (a type can be both encashable + carriable).
            balance = (src.allocated_days or ZERO) - used - (src.encashed_days or ZERO)
            carry = min(max(balance, ZERO), cf_cap.get(src.leave_type_id, ZERO))
            dst, _ = LeaveAllocation.objects.get_or_create(
                tenant=tenant, employee_id=src.employee_id, leave_type_id=src.leave_type_id, year=dest_year,
                defaults={"allocated_days": ZERO, "status": "active"})
            # Replace this run's own prior contribution instead of double-adding (idempotent).
            new_total = (dst.allocated_days or ZERO) - (dst.carried_forward or ZERO) + carry
            cap = bal_cap.get(src.leave_type_id, ZERO)
            if cap > ZERO:
                new_total = min(new_total, cap)  # never push the dest-year total past max_balance
            if dst.allocated_days != new_total or dst.carried_forward != carry or dst.status != "active":
                dst.allocated_days = new_total
                dst.carried_forward = carry
                dst.status = "active"
                dst.save(update_fields=["allocated_days", "carried_forward", "status", "updated_at"])
                touched += 1
    write_audit_log(request.user, None, "update",
                    changes={"action": "leave_carryforward_run", "from_year": year, "to_year": dest_year,
                             "allocations_updated": touched}, tenant=tenant)
    messages.success(request, f"Carry-forward {year} → {dest_year}: {touched} allocation(s) updated.")
    return redirect(f"{reverse('hrm:leave_policy')}?year={dest_year}")
