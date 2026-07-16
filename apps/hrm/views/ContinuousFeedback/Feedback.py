"""HRM 3.20 Continuous Feedback — Feedback views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.ContinuousFeedback._helpers import _can_edit_feedback, _can_view_feedback, _feedback_giver_display, _visible_feedback_q
from apps.hrm.models import (
    EmployeeProfile,
    Feedback,
    KudosBadge,
)
from apps.hrm.forms import (
    FeedbackForm,
)
from apps.hrm.views.ContinuousFeedback._helpers import _can_edit_feedback, _can_view_feedback, _feedback_giver_display, _visible_feedback_q
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ------------------------------------------------------------ Feedback (3.20 real-time + request-pull)
@login_required
def feedback_list(request):
    qs = (Feedback.objects.filter(tenant=request.tenant)
          .select_related("giver__party", "receiver__party", "badge"))  # the list row only needs these
    vq = _visible_feedback_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    profile = _current_employee_profile(request)
    is_admin = _is_admin(request.user)
    # Given/received/requested cuts (mirror ?mine=1 on performancereview_list).
    if request.GET.get("given") == "1":
        qs = qs.filter(giver=profile) if profile is not None else qs.none()
    if request.GET.get("received") == "1":
        qs = qs.filter(receiver=profile) if profile is not None else qs.none()
    if request.GET.get("requested") == "1":
        qs = qs.filter(status="requested")
    if request.GET.get("is_anonymous") == "1":
        qs = qs.filter(is_anonymous=True)
    # Only an admin may search by giver name — otherwise a non-admin could correlate an anonymous
    # giver by searching their real name and seeing the masked row surface (an info leak).
    search = ["number", "message", "receiver__party__name"]
    if is_admin:
        search.append("giver__party__name")
    return crud_list(
        request, qs,
        "hrm/performance/feedback/list.html",
        search_fields=tuple(search),
        filters=[("feedback_type", "feedback_type", False), ("visibility", "visibility", False),
                 ("status", "status", False), ("receiver", "receiver_id", True),
                 ("badge", "badge_id", True)],
        extra_context={
            "feedback_type_choices": Feedback.FEEDBACK_TYPE_CHOICES,
            "visibility_choices": Feedback.VISIBILITY_CHOICES,
            "status_choices": Feedback.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "badges": KudosBadge.objects.filter(tenant=request.tenant, is_active=True).order_by("name"),
            "is_admin": is_admin,
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def feedback_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    giver = _current_employee_profile(request)
    # Responding to a pull-request? ?respond_to=<pk> links the new row back at the 'requested' ask.
    respond_id = request.GET.get("respond_to") or request.POST.get("respond_to")
    respond_to = None
    if respond_id and str(respond_id).isdigit():
        respond_to = Feedback.objects.filter(
            tenant=request.tenant, pk=int(respond_id), status="requested").first()
        # Only the person who was ASKED (the request's receiver) — or an admin — may respond.
        if respond_to is not None and not _is_admin(request.user):
            if giver is None or giver.pk != respond_to.receiver_id:
                respond_to = None
    if request.method == "POST":
        form = FeedbackForm(request.POST, tenant=request.tenant, viewer_profile=giver)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.giver = giver
            if respond_to is not None:
                obj.requested_from = respond_to
                obj.status = "given"
            elif obj.feedback_type == "request":
                obj.status = "requested"
            else:
                obj.status = "given"
            # giver is set server-side (after form validation) — run the model's giver!=receiver guard.
            try:
                obj.clean()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                obj.save()
                # Close the answered request so it can't be re-answered and drops out of the pending
                # "Requests" views — the response row carries the content forward via requested_from.
                if respond_to is not None and respond_to.status == "requested":
                    respond_to.status = "responded"
                    respond_to.save(update_fields=["status", "updated_at"])
                    write_audit_log(request.user, respond_to, "update", {"action": "responded"})
                write_audit_log(request.user, obj, "create")
                messages.success(request, f"Feedback {obj.number} created.")
                return redirect("hrm:feedback_detail", pk=obj.pk)
    else:
        initial = {}
        if respond_to is not None:
            initial = {"receiver": respond_to.giver_id, "feedback_type": "appreciation"}
        form = FeedbackForm(tenant=request.tenant, initial=initial, viewer_profile=giver)
    return render(request, "hrm/performance/feedback/form.html",
                  {"form": form, "is_edit": False, "respond_to": respond_to})


@login_required
def feedback_detail(request, pk):
    obj = get_object_or_404(
        Feedback.objects.select_related(
            "giver__party", "receiver__party", "badge", "related_objective",
            "related_review", "requested_from"),  # detail only shows related_review.number, not its subject
        pk=pk, tenant=request.tenant)
    if not _can_view_feedback(request, obj):
        raise PermissionDenied("You do not have access to this feedback.")
    profile = _current_employee_profile(request)
    is_receiver = profile is not None and profile.pk == obj.receiver_id
    is_giver = profile is not None and profile.pk == obj.giver_id
    return render(request, "hrm/performance/feedback/detail.html", {
        "obj": obj,
        "giver_display": _feedback_giver_display(request, obj),
        "can_edit": _can_edit_feedback(request, obj),
        "is_receiver": is_receiver,
        "is_giver": is_giver,
        # The recipient acknowledges given feedback; the person asked responds to a request.
        "can_acknowledge": is_receiver and obj.status == "given",
        "can_respond": is_receiver and obj.status == "requested",
    })


@login_required
def feedback_edit(request, pk):
    obj = get_object_or_404(Feedback, pk=pk, tenant=request.tenant)
    if not _can_edit_feedback(request, obj):
        messages.error(request, "Only the giver or a tenant admin can edit this feedback, and only before it is acknowledged.")
        return redirect("hrm:feedback_detail", pk=obj.pk)
    return crud_edit(request, model=Feedback, pk=pk, form_class=FeedbackForm,
                     template="hrm/performance/feedback/form.html",
                     success_url="hrm:feedback_list")
