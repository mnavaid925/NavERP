"""HRM 3.8 Offer Management — Offer views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.OfferManagement._helpers import _offer_or_404
from apps.hrm.models import (
    OFFER_DECLINE_REASON_CHOICES,
    OFFER_STATUS_CHOICES,
    Offer,
    SIGNATURE_STATUS_CHOICES,
)
from apps.hrm.forms import (
    OfferApprovalForm,
    OfferForm,
    PreboardingItemForm,
)
from apps.hrm.views.CandidateManagement._helpers import _send_candidate_email
from apps.hrm.views.InterviewProcess._helpers import _form_changes
from apps.hrm.views.OfferManagement._helpers import _offer_or_404
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date


# --------------------------------------------------------------- Offers (3.8) CRUD + hub
@login_required
def offer_list(request):
    qs = (Offer.objects.filter(tenant=request.tenant)
          .select_related("application__candidate", "application__requisition")
          .order_by("-created_at"))
    return crud_list(
        request, qs, "hrm/offer/offer/list.html",
        search_fields=["number", "application__candidate__first_name",
                       "application__candidate__last_name", "application__requisition__title"],
        filters=[("status", "status", False), ("signature_status", "signature_status", False),
                 ("currency", "currency", False)],
        extra_context={
            "status_choices": OFFER_STATUS_CHOICES,
            "signature_status_choices": SIGNATURE_STATUS_CHOICES,
        },
    )


@login_required
def offer_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = OfferForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            # Default the currency from the requisition's salary_currency when the recruiter left it blank.
            if not obj.currency:
                obj.currency = obj.application.requisition.salary_currency or "USD"
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Offer {obj.number} created.")
            return redirect("hrm:offer_detail", pk=obj.pk)
    else:
        form = OfferForm(tenant=request.tenant,
                         initial={"application": request.GET.get("application") or None})
    return render(request, "hrm/offer/offer/form.html", {"form": form, "is_edit": False})


@login_required
def offer_detail(request, pk):
    obj = get_object_or_404(
        Offer.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition", "offer_letter_template",
                        "created_by", "extended_by"), pk=pk)
    approvals = obj.approvals.select_related("approver", "decided_by").all()
    background_checks = obj.background_checks.select_related("initiated_by").all()
    preboarding_items = obj.preboarding_items.select_related("verified_by").all()
    approved = sum(1 for s in approvals if s.status == "approved")
    all_approved = len(approvals) > 0 and approved == len(approvals)
    return render(request, "hrm/offer/offer/detail.html", {
        "obj": obj,
        "approvals": approvals,
        "background_checks": background_checks,
        "preboarding_items": preboarding_items,
        "approval_progress": (approved, len(approvals)),
        "all_approved": all_approved,
        "approval_form": OfferApprovalForm(tenant=request.tenant),
        "preboarding_form": PreboardingItemForm(tenant=request.tenant),
        "decline_reason_choices": OFFER_DECLINE_REASON_CHOICES,
    })


@login_required
def offer_edit(request, pk):
    # Editable only while a draft (mirrors jobrequisition_edit locking during the approval flow). Editing is
    # locked once submitted because the approval chain — including the executive-step comp threshold — is
    # built at submit time and not recomputed; a comp change under approval would silently invalidate it.
    # A pending-approval offer is reopened for edits via reject-step (back to draft). `status` and the
    # workflow stamps aren't on the form, so they're preserved.
    obj = get_object_or_404(Offer.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status != "draft":
        messages.error(request, "Only a draft offer can be edited. Reject the approval to reopen it for changes.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    if request.method == "POST":
        form = OfferForm(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.currency:
                obj.currency = obj.application.requisition.salary_currency or "USD"
            obj.save()
            write_audit_log(request.user, obj, "update", _form_changes(form))
            messages.success(request, "Offer updated.")
            return redirect("hrm:offer_detail", pk=obj.pk)
    else:
        form = OfferForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/offer/offer/form.html", {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # destructive — cascades approvals/background-checks/preboarding items; admin-only
@require_POST           # and only while a draft (mirrors jobrequisition_delete)
def offer_delete(request, pk):
    obj = get_object_or_404(Offer.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status != "draft":
        messages.error(request, "Only a draft offer can be deleted.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Offer deleted.")
    return redirect("hrm:offer_list")


# --- Offer workflow state-machine actions (all privileged; the form never sets these fields) ---
@tenant_admin_required
@require_POST
def offer_submit(request, pk):
    obj = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft offer can be submitted for approval.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    with transaction.atomic():
        generate_offer_approval_chain(obj)  # idempotent: builds the default chain only when none exist
        # Reset any prior decisions so a re-submit (after a rejected step reopened the offer to draft)
        # re-approves cleanly from the top — otherwise a step left at "rejected" would never return to
        # pending and offer_approve_step would flip the offer to approved once the other steps cleared,
        # skipping it. Mirrors jobrequisition_submit's rejected-resubmit chain reset.
        obj.approvals.update(status="pending", decided_at=None, decided_by=None, comments="")
        obj.status = "pending_approval"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit", "to": obj.status})
    messages.success(request, f"Offer {obj.number} submitted for approval.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_approve_step(request, pk):
    obj = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only an offer pending approval can be approved.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    if step is None:
        messages.error(request, "No pending approval step to approve.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    with transaction.atomic():
        step.status = "approved"
        step.decided_at = timezone.now()
        step.decided_by = request.user
        step.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
        # When the last pending step clears, the whole offer is approved.
        if not obj.approvals.filter(status="pending").exists():
            obj.status = "approved"
            obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update",
                        {"action": "approve_step", "step": step.step_order, "to": obj.status})
    if obj.status == "approved":
        messages.success(request, f"Final approval recorded — {obj.number} is approved.")
    else:
        messages.success(request, f"Approval step #{step.step_order} approved.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_reject_step(request, pk):
    # A rejected step reopens the offer to draft (mirrors jobrequisition_return) rather than inventing a
    # terminal "rejected" status — OFFER_STATUS_CHOICES stays exactly as researched. The chain is reset so
    # a fresh submit re-approves from the top.
    obj = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only an offer pending approval can be rejected.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    with transaction.atomic():
        if step is not None:
            step.status = "rejected"
            step.decided_at = timezone.now()
            step.decided_by = request.user
            step.comments = request.POST.get("comments", "").strip()[:2000]
            step.save(update_fields=["status", "decided_at", "decided_by", "comments", "updated_at"])
        # Reset the rest of the chain and reopen for revision.
        obj.approvals.exclude(pk=step.pk if step else None).update(
            status="pending", decided_at=None, decided_by=None, comments="")
        obj.status = "draft"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject_step"})
    messages.success(request, f"Offer {obj.number} sent back for revision.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_extend(request, pk):
    # The P0 "approval blocks extension" gate: an offer can only be extended once fully approved.
    obj = _offer_or_404(request, pk)
    if obj.status != "approved":
        messages.error(request, "Only a fully-approved offer can be extended to the candidate.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "extended"
    obj.extended_by = request.user
    obj.extended_at = timezone.now()
    if obj.signature_status == "not_sent":
        obj.signature_status = "sent"
    obj.save(update_fields=["status", "extended_by", "extended_at", "signature_status", "updated_at"])
    # Email the candidate the offer (reuses the existing "offer" template-type + append-only log).
    comm = _send_candidate_email(obj.application, template_type="offer", sent_by=request.user)
    write_audit_log(request.user, obj, "update", {"action": "extend"})
    if comm is None:
        messages.warning(request, f"Offer {obj.number} extended — but no email was sent "
                                  "(candidate has no email or is do-not-contact).")
    else:
        messages.success(request, f"Offer {obj.number} extended to {obj.application.candidate.name}.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@login_required
@require_POST
def offer_accept(request, pk):
    # Marks the candidate's acceptance: advances the application to "hired" (existing 3.6 fields), raises
    # the pre-boarding checklist, and logs an acceptance communication. A regular tenant user can record
    # this (it's data entry of the candidate's response, not an authority action).
    obj = _offer_or_404(request, pk)
    if obj.status != "extended":
        messages.error(request, "Only an extended offer can be marked accepted.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    with transaction.atomic():
        obj.status = "accepted"
        obj.accepted_at = timezone.now()
        if obj.signature_status in ("not_sent", "sent", "viewed"):
            obj.signature_status = "signed"
        obj.save(update_fields=["status", "accepted_at", "signature_status", "updated_at"])
        # Drive the recruiting pipeline to hired (reuse existing JobApplication fields — no schema change).
        app = obj.application
        app.stage = "hired"
        app.hired_on = _date.today()
        app.stage_changed_at = timezone.now()
        app.save(update_fields=["stage", "hired_on", "stage_changed_at", "updated_at"])
        # TODO (3.3 hand-off): full onboarding (OnboardingProgram) is created from its own entry points on
        # the join date; pre-boarding here only collects pre-start documents.
        generate_preboarding_checklist(obj)
        write_audit_log(request.user, obj, "update", {"action": "accept", "application": app.number})
    _send_candidate_email(obj.application, template_type="offer",
                          subject="Offer Accepted — Welcome Aboard",
                          body=f"Dear {obj.application.candidate.name},\n\nThank you for accepting our offer "
                               f"for {obj.application.requisition.title}. We'll be in touch with pre-boarding "
                               f"next steps.", sent_by=request.user)
    messages.success(request, f"Offer {obj.number} accepted — {obj.application.candidate.name} marked hired.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@login_required
@require_POST
def offer_decline(request, pk):
    obj = _offer_or_404(request, pk)
    if obj.status != "extended":
        messages.error(request, "Only an extended offer can be marked declined.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    reason = request.POST.get("decline_reason", "").strip()
    if reason not in dict(OFFER_DECLINE_REASON_CHOICES):
        messages.error(request, "Select a valid decline reason.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "declined"
    obj.declined_at = timezone.now()
    obj.decline_reason = reason
    obj.decline_notes = request.POST.get("decline_notes", "").strip()[:2000]
    obj.save(update_fields=["status", "declined_at", "decline_reason", "decline_notes", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "decline", "reason": reason})
    messages.success(request, f"Offer {obj.number} marked declined.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required  # rescinding a live offer is a sensitive HR action
@require_POST
def offer_rescind(request, pk):
    obj = _offer_or_404(request, pk)
    if obj.status not in ("pending_approval", "approved", "extended"):
        messages.error(request, "Only a pending, approved or extended offer can be rescinded.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "rescinded"
    obj.rescinded_at = timezone.now()
    obj.save(update_fields=["status", "rescinded_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "rescind"})
    messages.success(request, f"Offer {obj.number} rescinded.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_expire(request, pk):
    # Manual "let it lapse" action, available once an extended offer is past its response deadline
    # (automated cron expiry is deferred, mirroring the manual-action convention throughout HRM).
    obj = _offer_or_404(request, pk)
    if obj.status != "extended":
        messages.error(request, "Only an extended offer can be expired.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    if not obj.is_overdue:
        messages.error(request, "This offer's response deadline hasn't passed yet.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "expired"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "expire"})
    messages.success(request, f"Offer {obj.number} marked expired.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@login_required
@require_POST
def offer_send_email(request, pk):
    # Ad-hoc resend of the offer-letter email at any non-terminal status.
    obj = _offer_or_404(request, pk)
    if obj.is_closed:
        messages.error(request, "This offer is closed — no email sent.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    if obj.application.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; email not sent.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    comm = _send_candidate_email(obj.application, template_type="offer", sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        write_audit_log(request.user, comm, "create",
                        {"to": obj.application.candidate.email, "kind": "offer"})
        messages.success(request, f"Offer email sent to {obj.application.candidate.name}.")
    return redirect("hrm:offer_detail", pk=obj.pk)
