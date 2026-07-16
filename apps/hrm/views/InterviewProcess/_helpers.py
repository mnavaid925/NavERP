"""HRM 3.7 Interview Process — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    CandidateEmailTemplate,
    INTERVIEW_TERMINAL_STATUSES,
    Interview,
)
from apps.hrm.views.CandidateManagement._helpers import _send_candidate_email


# ============================================================ 3.7 Interview Process
# Interviews hang off the 3.6 JobApplication spine. Invites/reminders to the CANDIDATE reuse the 3.6
# _send_candidate_email pipeline (honors do_not_contact + logs CandidateCommunication); the panel
# feedback request emails internal panelist Users directly (best-effort). Status is workflow-owned —
# only the action POSTs below mutate it. Live calendar/Zoom/Teams/Meet/SMS dispatch is deferred.
def _interview_detail_lines(interview):
    """Compose the interview-specific lines appended to an invite/reminder email body (the template
    body's merge fields cover candidate/job; these literal lines carry the schedule + link)."""
    lines = [
        f"Interview: {interview.title} (Round {interview.round_number})",
        f"When: {interview.scheduled_at:%Y-%m-%d %H:%M} ({interview.duration_minutes} min)",
        f"Mode: {interview.get_mode_display()}",
    ]
    if interview.location:
        lines.append(f"Location: {interview.location}")
    if interview.meeting_url:
        lines.append(f"Meeting link: {interview.meeting_url}")
    return "\n".join(lines)


def _send_interview_email(interview, *, template_type, default_subject, sent_by):
    """Send an interview invite/reminder to the candidate, reusing the 3.6 candidate-email pipeline +
    append-only log. Resolves the matching active CandidateEmailTemplate (if any) for the body, then
    appends the interview specifics. Returns the logged CandidateCommunication, or None (do_not_contact
    / nothing to send)."""
    application = interview.application
    template = (CandidateEmailTemplate.objects
                .filter(tenant=interview.tenant, template_type=template_type, is_active=True)
                .order_by("pk").first())
    base_body = template.body_html if template is not None else ""
    body = (base_body + "\n\n" if base_body else "") + _interview_detail_lines(interview)
    subject = template.subject if template is not None else default_subject
    return _send_candidate_email(application, template=template, subject=subject, body=body, sent_by=sent_by)


def _interview_or_404(request, pk):
    return get_object_or_404(
        Interview.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition"), pk=pk)


def _form_changes(form):
    """Compact {field: new_value} of changed fields for the audit log (the 3.7/3.8 forms carry no
    sensitive fields, so no redaction needed — mirrors apps.core.crud._changed)."""
    return {name: str(form.cleaned_data.get(name))[:200] for name in getattr(form, "changed_data", [])}


def _transition_interview(request, pk, new_status, success_msg):
    obj = _interview_or_404(request, pk)
    if obj.status in INTERVIEW_TERMINAL_STATUSES:
        messages.error(request, "This interview is closed. Reschedule it to reopen.")
        return redirect("hrm:interview_detail", pk=obj.pk)
    obj.status = new_status
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": f"status:{new_status}"})
    messages.success(request, success_msg)
    return redirect("hrm:interview_detail", pk=obj.pk)
