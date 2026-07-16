"""HRM 3.20 Continuous Feedback — FeedbackDashboard views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    Feedback,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


@login_required
@require_POST
def feedback_delete(request, pk):
    obj = get_object_or_404(Feedback, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    # A tenant admin may delete any; the giver may delete only their own, still-unacknowledged row.
    if not (_is_admin(request.user)
            or (obj.status != "acknowledged" and profile is not None and profile.pk == obj.giver_id)):
        messages.error(request, "Only a tenant admin (or the giver, before acknowledgement) can delete this feedback.")
        return redirect("hrm:feedback_detail", pk=obj.pk)
    return crud_delete(request, model=Feedback, pk=pk, success_url="hrm:feedback_list")


@login_required
@require_POST
def feedback_acknowledge(request, pk):
    obj = get_object_or_404(Feedback, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.receiver_id)):
        raise PermissionDenied("Only the recipient can acknowledge this feedback.")
    if obj.status == "given":
        obj.status = "acknowledged"
        obj.acknowledged_at = timezone.now()
        obj.save(update_fields=["status", "acknowledged_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, f"Feedback {obj.number} acknowledged.")
    else:
        messages.error(request, "Only given feedback can be acknowledged.")
    return redirect("hrm:feedback_detail", pk=obj.pk)


@login_required
def feedback_respond(request, pk):
    """Turn a 'requested' ask into a response — a thin redirect to the create form pre-wired with
    ?respond_to=<pk> (the create view sets requested_from + status='given')."""
    ask = get_object_or_404(Feedback, pk=pk, tenant=request.tenant, status="requested")
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == ask.receiver_id)):
        raise PermissionDenied("Only the person asked can respond to this feedback request.")
    return redirect(f"{reverse('hrm:feedback_create')}?respond_to={ask.pk}")


@login_required
def feedback_dashboard(request):
    """Computed view (NO model) — a given/received/requested feedback summary for one employee, plus
    a per-type breakdown and a 30-day received-velocity count. Every employee sees their OWN
    dashboard; a tenant admin can view any via ?employee=<pk>. All ORM aggregation, no stored column
    (mirrors Objective.progress_pct / calibration_board)."""
    is_admin = _is_admin(request.user)
    target = _current_employee_profile(request)
    employees = None
    if is_admin:
        employees = (EmployeeProfile.objects.filter(tenant=request.tenant)
                     .select_related("party").order_by("party__name"))
        emp_id = request.GET.get("employee", "").strip()
        if emp_id.isdigit():
            target = (EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_id))
                      .select_related("party").first())
        elif target is None:
            target = employees.first()
    base = (Feedback.objects.filter(tenant=request.tenant)
            .select_related("giver__party", "receiver__party"))  # dashboard rows don't render the badge
    given = received = requested = []
    given_by_type = received_by_type = []
    given_count = received_count = requested_count = recent_30d_received = 0
    if target is not None:
        done = ("given", "acknowledged")
        given = list(base.filter(giver=target, status__in=done).order_by("-created_at")[:10])
        received = list(base.filter(receiver=target, status__in=done).order_by("-created_at")[:10])
        requested = list(base.filter(giver=target, status="requested").order_by("-created_at")[:10])
        type_labels = dict(Feedback.FEEDBACK_TYPE_CHOICES)
        given_by_type = [
            {"type": type_labels.get(r["feedback_type"], r["feedback_type"]), "count": r["c"]}
            for r in base.filter(giver=target, status__in=done)
            .values("feedback_type").annotate(c=Count("pk")).order_by("-c")]
        received_by_type = [
            {"type": type_labels.get(r["feedback_type"], r["feedback_type"]), "count": r["c"]}
            for r in base.filter(receiver=target, status__in=done)
            .values("feedback_type").annotate(c=Count("pk")).order_by("-c")]
        given_count = sum(x["count"] for x in given_by_type)
        received_count = sum(x["count"] for x in received_by_type)
        requested_count = base.filter(giver=target, status="requested").count()
        cutoff = timezone.now() - timedelta(days=30)
        recent_30d_received = base.filter(
            receiver=target, status__in=done, created_at__gte=cutoff).count()
    return render(request, "hrm/performance/feedback_dashboard.html", {
        "target": target,
        "employees": employees,
        "is_admin": is_admin,
        "given": given,
        "received": received,
        "requested": requested,
        "given_by_type": given_by_type,
        "received_by_type": received_by_type,
        "given_count": given_count,
        "received_count": received_count,
        "requested_count": requested_count,
        "recent_30d_received": recent_30d_received,
    })
