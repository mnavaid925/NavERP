"""HRM 3.8 Offer Management — Preboardingitems views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.OfferManagement._helpers import _preboarding_or_404
from apps.hrm.models import (
    Offer,
)
from apps.hrm.forms import (
    PreboardingItemForm,
)
from apps.hrm.views.CandidateManagement._helpers import _send_candidate_email
from apps.hrm.views.OfferManagement._helpers import _preboarding_or_404


@login_required
@require_POST
def preboardingitem_add(request, pk):
    offer = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    # Pre-boarding is only meaningful before/at joining — don't add items to a dead offer.
    if offer.is_closed and offer.status != "accepted":
        messages.error(request, "Pre-boarding items can't be added to a declined, rescinded or expired offer.")
        return redirect("hrm:offer_detail", pk=offer.pk)
    form = PreboardingItemForm(request.POST, request.FILES, tenant=request.tenant)
    if form.is_valid():
        item = form.save(commit=False)
        item.tenant = request.tenant
        item.offer = offer
        item.save()
        messages.success(request, "Pre-boarding item added.")
    else:
        messages.error(request, "Could not add the pre-boarding item — check the document type.")
    return redirect("hrm:offer_detail", pk=offer.pk)


@tenant_admin_required  # destructive — dropping a required compliance item is a privileged HR action
@require_POST
def preboardingitem_delete(request, pk):
    item = _preboarding_or_404(request, pk)
    offer_pk = item.offer_id
    write_audit_log(request.user, item, "delete", {"action": "remove_preboarding_item"})
    item.delete()
    messages.success(request, "Pre-boarding item removed.")
    return redirect("hrm:offer_detail", pk=offer_pk)


@login_required
@require_POST
def preboardingitem_mark_submitted(request, pk):
    item = _preboarding_or_404(request, pk)
    if item.status not in ("pending", "rejected"):
        messages.error(request, "Only a pending or rejected pre-boarding item can be (re)submitted.")
        return redirect("hrm:offer_detail", pk=item.offer_id)
    item.status = "submitted"
    item.submitted_at = timezone.now()
    item.verified_by = None  # clear any stale verification from a prior reject so history stays consistent
    item.verified_at = None
    item.save(update_fields=["status", "submitted_at", "verified_by", "verified_at", "updated_at"])
    messages.success(request, "Pre-boarding item marked submitted.")
    return redirect("hrm:offer_detail", pk=item.offer_id)


@tenant_admin_required  # verifying/rejecting a submitted document is a privileged HR action
@require_POST
def preboardingitem_verify(request, pk):
    item = _preboarding_or_404(request, pk)
    item.status = "verified"
    item.verified_by = request.user
    item.verified_at = timezone.now()
    item.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    write_audit_log(request.user, item, "update", {"action": "verify_preboarding"})
    messages.success(request, "Pre-boarding item verified.")
    return redirect("hrm:offer_detail", pk=item.offer_id)


@tenant_admin_required
@require_POST
def preboardingitem_reject(request, pk):
    item = _preboarding_or_404(request, pk)
    item.status = "rejected"
    item.verified_by = request.user
    item.verified_at = timezone.now()
    item.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    write_audit_log(request.user, item, "update", {"action": "reject_preboarding"})
    messages.success(request, "Pre-boarding item rejected — the candidate can re-submit.")
    return redirect("hrm:offer_detail", pk=item.offer_id)


@login_required
@require_POST
def preboardingitem_send_invite(request, pk):
    # Reuses the 3.6 candidate-email pipeline for a pre-boarding document-collection nudge (manual action;
    # scheduled dispatch deferred). Stamps reminder_sent_at, honoring do_not_contact via the helper.
    item = _preboarding_or_404(request, pk)
    candidate = item.offer.application.candidate
    if candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; invite not sent.")
        return redirect("hrm:offer_detail", pk=item.offer_id)
    body = (f"Dear {candidate.name},\n\nPlease upload your {item.get_document_type_display()} to complete "
            f"pre-boarding for your upcoming start. Reply to this email if you have any questions.")
    comm = _send_candidate_email(item.offer.application, template_type="general",
                                 subject="Pre-boarding — document requested", body=body, sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        item.reminder_sent_at = timezone.now()
        item.save(update_fields=["reminder_sent_at", "updated_at"])
        write_audit_log(request.user, comm, "create",
                        {"to": candidate.email, "kind": "preboarding_invite"})
        messages.success(request, "Pre-boarding invite sent to the candidate.")
    return redirect("hrm:offer_detail", pk=item.offer_id)
