"""Procurement 6.4 Vendor Management — VendorInvoiceSubmission staff views.

CRUD-lite BY DESIGN: submissions ARRIVE from the vendor portal (see Portal.py) — staff never
create or edit one. The register exists to REVIEW them (start review → accept/reject) and to
delete junk. Accepting is a review decision ONLY: nothing posts anywhere; the approved bill
is keyed into Accounting › Accounts Payable.
"""
from django.db import transaction
from django.db.models import Count, Q

from apps.core.decorators import tenant_admin_required
from apps.procurement.forms import SubmissionReviewForm
from apps.procurement.models import VendorInvoiceSubmission
from apps.procurement.views._common import *  # noqa: F401,F403

#: Statuses from which a review action may still be taken.
REVIEWABLE_STATUSES = ("submitted", "under_review")


def _is_admin(request):
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _scoped(tenant):
    return (VendorInvoiceSubmission.objects.filter(tenant=tenant)
            .select_related("supplier", "purchase_order", "submitted_by", "reviewed_by"))


@login_required
def vis_list(request):
    # Join-free COUNT: aggregate() keeps select_related joins, and the footer badges do
    # not need them (see the same note on vsu_list).
    counts = (VendorInvoiceSubmission.objects.filter(tenant=request.tenant)
              .aggregate(pending=Count("id", filter=Q(status__in=("submitted", "under_review"))),
                         accepted=Count("id", filter=Q(status="accepted"))))
    return crud_list(
        request, _scoped(request.tenant),
        "procurement/vendormanagement/invoice-submission/list.html",
        search_fields=["invoice_ref", "supplier__name", "note"],
        filters=[("status", "status", False)],
        extra_context={
            "status_choices": VendorInvoiceSubmission.STATUS_CHOICES,
            "pending_count": counts["pending"],
            "accepted_count": counts["accepted"],
            "is_admin": _is_admin(request),
        },
    )


@login_required
def vis_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "procurement/vendormanagement/invoice-submission/detail.html", {
        "obj": obj,
        "is_admin": _is_admin(request),
    })


def _decide(request, pk, *, decision):
    """Shared accept/reject machinery — status-gated and row-locked, so a double POST cannot
    re-decide an already-decided submission."""
    with transaction.atomic():
        obj = get_object_or_404(VendorInvoiceSubmission.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in REVIEWABLE_STATUSES:
            messages.info(request,
                          f"Submission {obj.number} was already "
                          f"{obj.get_status_display().lower()} — no further decision applies.")
            return redirect("procurement:vis_detail", pk=obj.pk)
        form = SubmissionReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Review note must be 2000 characters or fewer.")
            return redirect("procurement:vis_detail", pk=obj.pk)
        obj.status = decision
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.review_note = form.cleaned_data["review_note"]
        obj.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note",
                                "updated_at"])
        write_audit_log(request.user, obj, decision)
    if decision == "accepted":
        messages.success(request,
                         f"Submission {obj.number} accepted. NO GL posting happened — "
                         f"acceptance is a review decision; key the bill in "
                         f"Accounting › Accounts Payable.")
    else:
        messages.success(request,
                         f"Submission {obj.number} rejected — review decision only, nothing "
                         f"was posted.")
    return redirect("procurement:vis_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def vis_accept(request, pk):
    return _decide(request, pk, decision="accepted")


@login_required
@tenant_admin_required
@require_POST
def vis_reject(request, pk):
    return _decide(request, pk, decision="rejected")


@login_required
@tenant_admin_required
@require_POST
def vis_start_review(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(VendorInvoiceSubmission.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status != "submitted":
            messages.info(request,
                          f"Submission {obj.number} is {obj.get_status_display().lower()} — "
                          f"review starts from 'Submitted' only.")
            return redirect("procurement:vis_detail", pk=obj.pk)
        # Move to under_review only; the review trail (reviewed_by/at/note) stays untouched
        # until the actual accept/reject decision lands.
        obj.status = "under_review"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "review")
    messages.success(request, f"Submission {obj.number} marked Under Review.")
    return redirect("procurement:vis_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def vis_delete(request, pk):
    """Junk removal only. A REVIEWED submission is evidence of a decision someone made —
    deleting an accepted/rejected row would hollow out the register, so the gate refuses
    anything past 'submitted' (mirrors vsu_delete's pending-only rule)."""
    obj = get_object_or_404(VendorInvoiceSubmission, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(request,
                       f"Submission {obj.number} has been reviewed ({obj.get_status_display()}) "
                       f"— it is register history and cannot be deleted. Reject it instead if "
                       f"it is still open.")
        return redirect("procurement:vis_detail", pk=obj.pk)
    return crud_delete(request, model=VendorInvoiceSubmission, pk=pk,
                       success_url="procurement:vis_list")
