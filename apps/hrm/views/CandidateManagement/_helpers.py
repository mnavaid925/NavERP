"""HRM 3.6 Candidate Management — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    CandidateCommunication,
    CandidateEmailTemplate,
)


# Stage → the auto-send template type fired when an application advances into that stage.
_STAGE_AUTO_TEMPLATE = {
    "screening": "shortlisted",
    "phone_screen": "phone_screen_invite",
    "assessment": "assessment_invite",
    "interview": "interview_invite",
    "offer": "offer",
}


def _user_display(user):
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


def _apply_merge(text, ctx):
    for key, value in ctx.items():
        text = text.replace(key, str(value))
    return text


def _send_candidate_email(application, *, template=None, template_type=None, subject=None, body=None,
                          sent_by=None):
    """Render merge fields, send a candidate email (console backend in dev), and log an append-only
    ``CandidateCommunication``. Honors ``do_not_contact`` (skips, returns None). Resolves a template by
    instance or by an active type. Returns the logged row, or None when nothing was sent."""
    candidate = application.candidate
    if candidate.do_not_contact:
        return None
    tenant = application.tenant
    if template is None and template_type:
        template = (CandidateEmailTemplate.objects
                    .filter(tenant=tenant, template_type=template_type, is_active=True)
                    .order_by("pk").first())
    if subject is None and template is not None:
        subject = template.subject
    if body is None and template is not None:
        body = template.body_html
    if not body:
        return None
    ctx = {
        "{{candidate_name}}": candidate.name,
        "{{job_title}}": application.requisition.title,
        "{{company_name}}": getattr(tenant, "name", ""),
        "{{recruiter_name}}": _user_display(sent_by) or "the hiring team",
        "{{application_number}}": application.number or "",
    }
    subject = _apply_merge(subject or "", ctx)
    body = _apply_merge(body, ctx)
    status = "sent"
    try:
        sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [candidate.email])
        status = "sent" if sent else "failed"
    except Exception:  # never let a mail/transport failure 500 the request — log it as failed instead
        status = "failed"
    return CandidateCommunication.objects.create(
        tenant=tenant, candidate=candidate, application=application, template=template,
        channel="email", direction="outbound", subject=subject[:500], body=body,
        sent_by=sent_by, delivery_status=status)


def _auto_send_for_stage(application, stage, sent_by):
    """Fire the matching ``is_auto_send`` template (if any) for a stage transition."""
    template_type = _STAGE_AUTO_TEMPLATE.get(stage)
    if not template_type:
        return
    template = (CandidateEmailTemplate.objects
                .filter(tenant=application.tenant, template_type=template_type,
                        is_active=True, is_auto_send=True)
                .order_by("pk").first())
    if template is not None:
        _send_candidate_email(application, template=template, sent_by=sent_by)
