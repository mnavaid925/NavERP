"""HRM 3.8 Offer Management — OfferLetter views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.OfferManagement._helpers import _offer_or_404
from apps.hrm.views.CandidateManagement._helpers import _apply_merge
from apps.hrm.views.OfferManagement._helpers import _offer_or_404


@login_required
def offer_letter_print(request, pk):
    """Server-rendered printable offer letter (3.8). Merges the chosen ``OfferLetterTemplate.body_html``
    tokens against the offer/candidate/tenant (reusing ``_apply_merge``), falling back to a generated body
    when no template is linked. Pure read/render — an offer letter can be reprinted freely (mirrors the
    offboarding relieving/experience letters)."""
    obj = _offer_or_404(request, pk)
    candidate = obj.application.candidate
    hiring_manager = obj.requisition.hiring_manager
    ctx = {
        "{{candidate_name}}": candidate.name,
        "{{job_title}}": obj.requisition.title,
        "{{base_salary}}": f"{obj.base_salary:,.2f}",
        "{{currency}}": obj.currency,
        "{{start_date}}": obj.start_date.strftime("%B %d, %Y") if obj.start_date else "",
        "{{company_name}}": getattr(request.tenant, "name", ""),
        "{{hiring_manager_name}}": (hiring_manager.party.name if hiring_manager else "the hiring team"),
    }
    if obj.offer_letter_template:
        letter_body = _apply_merge(obj.offer_letter_template.body_html, ctx)
    else:
        letter_body = (
            f"Dear {candidate.name},\n\nWe are delighted to offer you the position of "
            f"{obj.requisition.title} at {ctx['{{company_name}}']}. Your annual base salary will be "
            f"{obj.currency} {obj.base_salary:,.2f}, with a proposed start date of "
            f"{ctx['{{start_date}}'] or 'a date to be confirmed'}.\n\nWe look forward to welcoming you "
            f"to the team.\n\nSincerely,\n{ctx['{{hiring_manager_name}}']}")
    return render(request, "hrm/offer/offer_letter.html", {
        "offer": obj,
        "application": obj.application,
        "candidate": candidate,
        "letter_body": letter_body,
        "today": timezone.localdate(),
    })
