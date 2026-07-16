"""HRM 3.7 Interview Process — Interview views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.InterviewProcess._helpers import _form_changes, _interview_or_404, _send_interview_email, _transition_interview
from apps.hrm.models import (
    INTERVIEW_MODE_CHOICES,
    INTERVIEW_STATUS_CHOICES,
    Interview,
    InterviewPanelist,
    JobApplication,
    RSVP_STATUS_CHOICES,
)
from apps.hrm.forms import (
    InterviewForm,
    InterviewPanelistForm,
)
from apps.hrm.views.InterviewProcess._helpers import _form_changes, _interview_or_404, _send_interview_email, _transition_interview


# --------------------------------------------------------------- Interviews (3.7) CRUD + hub
@login_required
def interview_list(request):
    qs = (Interview.objects.filter(tenant=request.tenant)
          .select_related("application__candidate", "application__requisition")
          .annotate(panelist_count=Count("panelists", distinct=True))
          .order_by("-scheduled_at"))  # explicit ordering after annotate (paginator needs it)
    return crud_list(
        request, qs, "hrm/interview/interview/list.html",
        search_fields=["number", "title", "application__candidate__first_name",
                       "application__candidate__last_name", "application__requisition__title",
                       "application__number"],
        filters=[("status", "status", False), ("mode", "mode", False),
                 ("application", "application_id", True)],
        extra_context={
            "status_choices": INTERVIEW_STATUS_CHOICES,
            "mode_choices": INTERVIEW_MODE_CHOICES,
            "applications": JobApplication.objects.filter(tenant=request.tenant)
            .select_related("candidate", "requisition").order_by("-applied_at")[:200],
        },
    )


@login_required
def interview_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = InterviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.scheduled_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Interview {obj.number} scheduled.")
            return redirect("hrm:interview_detail", pk=obj.pk)
    else:
        # Pre-select the application when arriving from an application/candidate hub.
        form = InterviewForm(tenant=request.tenant,
                             initial={"application": request.GET.get("application") or None})
    return render(request, "hrm/interview/interview/form.html", {"form": form, "is_edit": False})


@login_required
def interview_detail(request, pk):
    obj = get_object_or_404(
        Interview.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition", "scheduled_by"), pk=pk)
    panelists = obj.panelists.select_related("interviewer").all()
    feedback_entries = (obj.feedback_entries.select_related("submitted_by", "panelist__interviewer")
                        .annotate(avg_rating=Avg("criteria__rating")).order_by("-created_at"))
    return render(request, "hrm/interview/interview/detail.html", {
        "obj": obj,
        "panelists": panelists,
        "feedback_entries": feedback_entries,
        "panelist_form": InterviewPanelistForm(tenant=request.tenant),
        "rsvp_choices": RSVP_STATUS_CHOICES,
    })


@login_required
def interview_edit(request, pk):
    # `status`/`scheduled_by`/reminder stamps aren't on the form, so they're preserved. Land back on the
    # detail hub (not the list) so the user can keep managing the panel/status after editing.
    obj = get_object_or_404(Interview.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = InterviewForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", _form_changes(form))
            messages.success(request, "Interview updated.")
            return redirect("hrm:interview_detail", pk=obj.pk)
    else:
        form = InterviewForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/interview/interview/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # destructive — cascades panelists, scorecards and criteria; matches the
@require_POST           # admin-only delete button in the templates (security-review #2)
def interview_delete(request, pk):
    return crud_delete(request, model=Interview, pk=pk, success_url="hrm:interview_list")


@login_required
@require_POST
def interview_confirm(request, pk):
    return _transition_interview(request, pk, "confirmed", "Interview confirmed.")


@login_required
@require_POST
def interview_start(request, pk):
    return _transition_interview(request, pk, "in_progress", "Interview marked in progress.")


@login_required
@require_POST
def interview_complete(request, pk):
    return _transition_interview(request, pk, "completed", "Interview completed.")


@login_required
@require_POST
def interview_cancel(request, pk):
    return _transition_interview(request, pk, "cancelled", "Interview cancelled.")


@login_required
@require_POST
def interview_no_show(request, pk):
    return _transition_interview(request, pk, "no_show", "Interview marked as no-show.")


@login_required
@require_POST
def interview_reschedule(request, pk):
    obj = _interview_or_404(request, pk)
    raw = request.POST.get("scheduled_at", "").strip()
    dt = parse_datetime(raw) if raw else None
    if dt is None:
        messages.error(request, "Enter a valid new date and time to reschedule.")
        return redirect("hrm:interview_detail", pk=obj.pk)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    obj.scheduled_at = dt
    obj.status = "rescheduled"  # reopens a closed round so it can proceed again
    obj.save(update_fields=["scheduled_at", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reschedule", "scheduled_at": dt.isoformat()})
    if dt < timezone.now():
        messages.warning(request, "Interview rescheduled — note the new time is in the past.")
    else:
        messages.success(request, "Interview rescheduled.")
    return redirect("hrm:interview_detail", pk=obj.pk)


@login_required
@require_POST
def interview_panelist_add(request, pk):
    interview = _interview_or_404(request, pk)
    form = InterviewPanelistForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        _, created = InterviewPanelist.objects.get_or_create(
            interview=interview, interviewer=cd["interviewer"],
            defaults={"tenant": request.tenant, "role": cd["role"],
                      "briefing_notes": cd["briefing_notes"]})
        if created:
            messages.success(request, "Panelist added.")
        else:
            messages.info(request, "That interviewer is already on the panel.")
    else:
        messages.error(request, "Select an interviewer to add to the panel.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_panelist_remove(request, pk, panelist_pk):
    interview = _interview_or_404(request, pk)
    panelist = get_object_or_404(InterviewPanelist, pk=panelist_pk, interview=interview, tenant=request.tenant)
    panelist.delete()
    messages.success(request, "Panelist removed.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_panelist_rsvp(request, pk, panelist_pk):
    interview = _interview_or_404(request, pk)
    panelist = get_object_or_404(InterviewPanelist, pk=panelist_pk, interview=interview, tenant=request.tenant)
    new_rsvp = request.POST.get("rsvp_status", "")
    if new_rsvp not in dict(RSVP_STATUS_CHOICES):
        messages.error(request, "Invalid RSVP status.")
        return redirect("hrm:interview_detail", pk=interview.pk)
    panelist.rsvp_status = new_rsvp
    panelist.save(update_fields=["rsvp_status", "updated_at"])
    messages.success(request, "RSVP updated.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_send_invite(request, pk):
    interview = _interview_or_404(request, pk)
    if interview.application.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; invite not sent.")
        return redirect("hrm:interview_detail", pk=interview.pk)
    comm = _send_interview_email(interview, template_type="interview_invite",
                                 default_subject="Interview Invitation", sent_by=request.user)
    # The panel is invited alongside the candidate — stamp not-yet-notified seats.
    interview.panelists.filter(notified_at__isnull=True).update(notified_at=timezone.now())
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        write_audit_log(request.user, comm, "create",
                        {"to": interview.application.candidate.email, "kind": "interview_invite"})
        messages.success(request, f"Invite sent to {interview.application.candidate.name}.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_send_reminder(request, pk):
    interview = _interview_or_404(request, pk)
    if interview.application.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; reminder not sent.")
        return redirect("hrm:interview_detail", pk=interview.pk)
    comm = _send_interview_email(interview, template_type="interview_reminder",
                                 default_subject="Interview Reminder", sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        interview.reminder_sent_at = timezone.now()
        interview.save(update_fields=["reminder_sent_at", "updated_at"])
        write_audit_log(request.user, comm, "create",
                        {"to": interview.application.candidate.email, "kind": "interview_reminder"})
        messages.success(request, "Reminder sent to the candidate.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_request_feedback(request, pk):
    """Nudge the panel to submit their scorecards — emails the panelist Users directly (best-effort) and
    stamps ``feedback_reminder_sent_at``. Internal email only; SMS/automated dispatch deferred."""
    interview = _interview_or_404(request, pk)
    emails = [p.interviewer.email for p in interview.panelists.select_related("interviewer")
              if p.interviewer.email]
    if emails:
        candidate_name = interview.application.candidate.name
        subject = f"Please submit your scorecard — {interview.title}"
        body = (f"You interviewed {candidate_name} ({interview.title}, Round {interview.round_number}).\n"
                f"Please submit your interview feedback / scorecard in NavERP HRM.")
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, emails, fail_silently=True)
        except Exception:  # never let a transport failure 500 the request
            pass
    interview.feedback_reminder_sent_at = timezone.now()
    interview.save(update_fields=["feedback_reminder_sent_at", "updated_at"])
    write_audit_log(request.user, interview, "update",
                    {"action": "request_feedback", "panelists": len(emails)})
    messages.success(request, f"Feedback requested from {len(emails)} panelist(s).")
    return redirect("hrm:interview_detail", pk=interview.pk)
