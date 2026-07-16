"""HRM 3.36 Helpdesk — Helpdeskticket views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.Helpdesk._helpers import _ticket_can_view, _ticket_is_agent, _ticket_mark_first_response
from apps.hrm.models import (
    EmployeeProfile,
    HelpdeskCategory,
    HelpdeskTicket,
)
from apps.hrm.forms import (
    HelpdeskTicketForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.Helpdesk._helpers import _ticket_can_view, _ticket_is_agent, _ticket_mark_first_response
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_delete, _hr_request_edit
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _get_user_model


@login_required
def ticket_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, HelpdeskTicket.objects.filter(tenant=request.tenant)
                   .select_related("employee__party", "category", "assignee", "sla_policy"))
    # SLA-breach deep-link (?sla=breached): open + past resolution due, OR open + unanswered past
    # first-response due. Computed in ORM here (the properties can't be filtered on).
    if request.GET.get("sla", "").strip() == "breached":
        now = timezone.now()
        qs = qs.filter(Q(status__in=HelpdeskTicket.OPEN_STATUSES) & (
            Q(resolution_due__lt=now)
            | (Q(first_responded_at__isnull=True) & Q(first_response_due__lt=now))))
    # Satisfaction-survey deep-link (?rated=1): tickets with a CSAT rating captured.
    if request.GET.get("rated", "").strip() == "1":
        qs = qs.filter(satisfaction_rating__isnull=False)
    extra = {"status_choices": HelpdeskTicket.STATUS_CHOICES,
             "priority_choices": HelpdeskTicket.PRIORITY_CHOICES,
             "categories": HelpdeskCategory.objects.filter(tenant=request.tenant, is_active=True)
             .order_by("department", "name"),
             "is_admin": is_admin}
    filters = [("status", "status", False), ("priority", "priority", False), ("category", "category_id", True)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        filters.append(("assignee", "assignee_id", True))
        extra["employees"] = _ss_employees(request)
        extra["agents"] = _get_user_model().objects.filter(tenant=request.tenant).order_by("username")
    return crud_list(request, qs, "hrm/helpdesk/helpdeskticket/list.html",
                     search_fields=["number", "subject", "description", "employee__party__name"],
                     filters=filters, extra_context=extra)


@login_required
def ticket_create(request):
    """Raise a ticket. A non-admin raises for THEMSELVES; an admin may target ``?employee=<id>`` (GET)
    or ``employee_pk`` (POST). The chosen category's default SLA policy + assignee are inherited, and
    ``save()`` stamps the SLA due timestamps from the policy's per-priority targets."""
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
        messages.error(request, "Select an employee to raise this ticket for.")
        return redirect("hrm:ticket_list")
    if request.method == "POST":
        form = HelpdeskTicketForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.employee = target
            obj.status = "new"
            if obj.category_id:
                obj.sla_policy = obj.category.default_sla_policy
                obj.assignee = obj.category.default_assignee
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Ticket {obj.number} raised.")
            return redirect("hrm:ticket_detail", pk=obj.pk)
    else:
        form = HelpdeskTicketForm(tenant=request.tenant)
    return render(request, "hrm/helpdesk/helpdeskticket/form.html", {
        "form": form, "is_edit": False, "is_admin": is_admin,
        "target_employee": target, "employees": _ss_employees(request) if is_admin else None})


@login_required
def ticket_detail(request, pk):
    obj = get_object_or_404(
        HelpdeskTicket.objects.select_related("employee__party", "category", "sla_policy", "assignee"),
        pk=pk, tenant=request.tenant)
    if not _ticket_can_view(request, obj):
        raise PermissionDenied("This ticket belongs to another employee.")
    is_admin = _is_admin(request.user)
    profile = _current_employee_profile(request)
    is_own = profile is not None and obj.employee_id == profile.pk
    return render(request, "hrm/helpdesk/helpdeskticket/detail.html", {
        "obj": obj, "is_admin": is_admin, "is_agent": _ticket_is_agent(request, obj), "is_own": is_own,
        "agents": (_get_user_model().objects.filter(tenant=request.tenant).order_by("username")
                   if is_admin else None),
        "rating_range": [1, 2, 3, 4, 5]})


@login_required
def ticket_edit(request, pk):
    # Requester (or admin) may edit the subject/description/category/priority while the ticket is open.
    return _hr_request_edit(request, HelpdeskTicket, pk, HelpdeskTicketForm,
                            "hrm/helpdesk/helpdeskticket/form.html", "hrm:ticket_detail")


@login_required
@require_POST
def ticket_delete(request, pk):
    return _hr_request_delete(request, HelpdeskTicket, pk, "hrm:ticket_list")


@login_required
@require_POST
def ticket_assign(request, pk):
    """Assign / reassign to a tenant user — admin only. A 'new' ticket becomes 'open'."""
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    if not _is_admin(request.user):
        messages.error(request, "Only an administrator can assign tickets.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    # Status guard mirrors the template (the Assign form is hidden on closed/cancelled tickets) so a
    # crafted POST can't reassign a finished ticket.
    if obj.status in ("closed", "cancelled"):
        messages.error(request, "A closed or cancelled ticket can't be reassigned.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    assignee_id = (request.POST.get("assignee") or "").strip()
    assignee = None
    if assignee_id.isdigit():
        assignee = _get_user_model().objects.filter(tenant=request.tenant, pk=int(assignee_id)).first()
    if assignee is None:
        messages.error(request, "Select a valid assignee.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.assignee = assignee
    fields = ["assignee", "updated_at"]
    if obj.status == "new":
        obj.status = "open"
        fields.append("status")
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": "assign", "assignee": assignee.get_username()})
    messages.success(request, f"Ticket {obj.number} assigned to {assignee.get_username()}.")
    return redirect("hrm:ticket_detail", pk=obj.pk)


@login_required
@require_POST
def ticket_start(request, pk):
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    if not _ticket_is_agent(request, obj):
        messages.error(request, "Only the assignee or an administrator can work this ticket.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    if obj.status not in ("new", "open", "waiting"):
        messages.error(request, "Only a new, open, or waiting ticket can be moved to In Progress.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.status = "in_progress"
    if obj.assignee_id is None:
        obj.assignee = request.user
    _ticket_mark_first_response(obj)
    obj.save(update_fields=["status", "assignee", "first_responded_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "start"})
    messages.success(request, f"Ticket {obj.number} is now in progress.")
    return redirect("hrm:ticket_detail", pk=obj.pk)


@login_required
@require_POST
def ticket_waiting(request, pk):
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    if not _ticket_is_agent(request, obj):
        messages.error(request, "Only the assignee or an administrator can update this ticket.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    if obj.status not in ("open", "in_progress"):
        messages.error(request, "Only an open or in-progress ticket can be set to waiting.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.status = "waiting"
    _ticket_mark_first_response(obj)
    obj.save(update_fields=["status", "first_responded_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "waiting"})
    messages.success(request, f"Ticket {obj.number} is waiting on the requester.")
    return redirect("hrm:ticket_detail", pk=obj.pk)


@login_required
@require_POST
def ticket_resolve(request, pk):
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    if not _ticket_is_agent(request, obj):
        messages.error(request, "Only the assignee or an administrator can resolve this ticket.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    if obj.status not in HelpdeskTicket.OPEN_STATUSES:
        messages.error(request, "Only an open ticket can be resolved.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    notes = (request.POST.get("resolution_notes") or "").strip()
    if not notes:
        messages.error(request, "A resolution note is required to resolve a ticket.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.status = "resolved"
    obj.resolution_notes = notes[:5000]
    obj.resolved_at = timezone.now()
    _ticket_mark_first_response(obj)
    if obj.assignee_id is None:
        obj.assignee = request.user
    obj.save(update_fields=["status", "resolution_notes", "resolved_at", "first_responded_at",
                            "assignee", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "resolve"})
    messages.success(request, f"Ticket {obj.number} resolved.")
    return redirect("hrm:ticket_detail", pk=obj.pk)


@login_required
@require_POST
def ticket_close(request, pk):
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    if not (_can_manage_own_child(request, obj) or _ticket_is_agent(request, obj)):
        messages.error(request, "You can't close this ticket.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    if obj.status in ("closed", "cancelled"):
        messages.error(request, "This ticket is already closed.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.status = "closed"
    obj.closed_at = timezone.now()
    if obj.resolved_at is None:
        obj.resolved_at = obj.closed_at
    obj.save(update_fields=["status", "closed_at", "resolved_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "close"})
    messages.success(request, f"Ticket {obj.number} closed.")
    return redirect("hrm:ticket_detail", pk=obj.pk)


@login_required
@require_POST
def ticket_reopen(request, pk):
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    if not (_can_manage_own_child(request, obj) or _ticket_is_agent(request, obj)):
        messages.error(request, "You can't reopen this ticket.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    if obj.status not in ("resolved", "closed"):
        messages.error(request, "Only a resolved or closed ticket can be reopened.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.status = "open"
    obj.resolved_at = None
    obj.closed_at = None
    obj.save(update_fields=["status", "resolved_at", "closed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reopen"})
    messages.success(request, f"Ticket {obj.number} reopened.")
    return redirect("hrm:ticket_detail", pk=obj.pk)


@login_required
@require_POST
def ticket_cancel(request, pk):
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only cancel your own tickets.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    if obj.status not in HelpdeskTicket.OPEN_STATUSES:
        messages.error(request, "Only an open ticket can be cancelled.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.status = "cancelled"
    obj.closed_at = timezone.now()
    obj.save(update_fields=["status", "closed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Ticket {obj.number} cancelled.")
    return redirect("hrm:ticket_detail", pk=obj.pk)


@login_required
@require_POST
def ticket_feedback(request, pk):
    """Requester-only CSAT (1-5 + comment) after resolution/closure — the Satisfaction Survey bullet."""
    obj = get_object_or_404(HelpdeskTicket, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (profile is not None and obj.employee_id == profile.pk):
        messages.error(request, "Only the requester can rate this ticket.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    if obj.status not in ("resolved", "closed"):
        messages.error(request, "You can rate a ticket only after it's resolved.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    rating = (request.POST.get("satisfaction_rating") or "").strip()
    if rating not in ("1", "2", "3", "4", "5"):
        messages.error(request, "Select a rating from 1 to 5.")
        return redirect("hrm:ticket_detail", pk=obj.pk)
    obj.satisfaction_rating = int(rating)
    obj.satisfaction_comment = (request.POST.get("satisfaction_comment") or "").strip()[:2000]
    obj.satisfaction_at = timezone.now()
    obj.save(update_fields=["satisfaction_rating", "satisfaction_comment", "satisfaction_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "feedback", "rating": obj.satisfaction_rating})
    messages.success(request, "Thanks for your feedback!")
    return redirect("hrm:ticket_detail", pk=obj.pk)
