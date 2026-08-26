"""Procurement 6.4 Vendor Management — login-gated vendor portal views.

The SUPPLIER side of 6.4: a bound vendor login sees its own purchase orders, its own
invoice submissions and payment position, and its own sourcing bids — filing new invoice
submissions and completing/submitting draft bids. The refusal ladder mirrors crm 1.4's
customer portal: no access row → refused; an access row without a linked supplier → refused
(a NULL scope must never widen into unlinked rows); a suspended supplier can look around
but every submission attempt is refused.
"""
from django.db import transaction
from django.db.models import Count, Q

from apps.procurement.forms import VendorBidForm, VendorInvoiceSubmissionForm
from apps.procurement.models import (
    SourcingBid,
    SourcingEvent,
    VendorInvoiceSubmission,
    VendorPortalAccess,
    VendorSuspension,
)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseOrder, SupplierProfile


def _vendor_access(request):
    """Return ``(access, supplier, refusal)`` for the logged-in user.

    ``refusal`` is None when the caller may proceed, else a ready redirect response (same
    ladder as crm 1.4's customer portal). On success the supplier's active suspension is
    computed ONCE here and attached to ``access`` as ``access.suspension``; views pass it
    on to templates as **``suspension``** — NOT ``block``: Django's template engine pushes
    its own BlockNode into every context under the name ``block``, so a context variable
    of that name is silently shadowed and ``{% if block %}`` is always truthy.
    """
    access = VendorPortalAccess.for_user(request.tenant, request.user)
    if access is None:
        messages.error(request, "You don't have vendor portal access.")
        return None, None, redirect("dashboard:home")
    supplier = access.supplier
    if supplier is None:  # WARNING: an unlinked portal account would otherwise match every
        # NULL-supplier row in the tenant — refuse rather than leak (same guard as crm).
        messages.error(request, "Your portal account has no linked supplier — contact support.")
        return access, None, redirect("dashboard:home")
    access.suspension = VendorSuspension.blocking_for(request.tenant, supplier.pk)
    return access, supplier, None


@login_required
def vendor_portal_home(request):
    access, supplier, refusal = _vendor_access(request)
    if refusal is not None:
        return refusal
    suspension = access.suspension
    pos_qs = (PurchaseOrder.objects.filter(tenant=request.tenant, vendor=supplier)
              .exclude(status__in=("cancelled",)))
    pos = pos_qs.order_by("-order_date", "-id")[:10]
    subs_qs = (VendorInvoiceSubmission.objects
               .filter(tenant=request.tenant, submitted_by=request.user))
    profile = SupplierProfile.objects.filter(tenant=request.tenant, party=supplier).first()
    # "Track payments" — read-only projection of accounting's AP ledger for THIS supplier.
    # SCM computes no AR/AP of its own (same posture as 4.16 showing invoices): these are
    # accounting's bills, shown, never recalculated. Local import keeps the apps decoupled
    # at load time; the query is scoped to the bound party so nothing else can leak in.
    from apps.accounting.models import Bill

    bills = (Bill.objects.filter(tenant=request.tenant, party=supplier)
             .exclude(status="void")
             .select_related("currency").order_by("-bill_date", "-id")[:6])
    # One aggregate for both submission counters instead of two COUNT round-trips; the PO
    # count stands alone because it filters a different model.
    sub_stats = subs_qs.aggregate(
        in_review=Count("id", filter=Q(status__in=("submitted", "under_review"))),
        accepted=Count("id", filter=Q(status="accepted")),
    )
    return render(request, "procurement/vendormanagement/portal_home.html", {
        "access": access,
        "supplier": supplier,
        "profile": profile,
        "pos": pos,
        "my_submissions": subs_qs.order_by("-created_at")[:5],
        "stats": {
            "orders_on_file": pos_qs.count(),
            "in_review": sub_stats["in_review"],
            "accepted": sub_stats["accepted"],
        },
        "suspension": suspension,
        "bills": bills,
        "today": timezone.localdate(),
    })


@login_required
def vendor_invoice_new(request):
    access, supplier, refusal = _vendor_access(request)
    if refusal is not None:
        return refusal
    suspension = access.suspension
    if request.method == "POST":
        if suspension is not None:
            messages.error(request,
                           "Your account is currently suspended/blacklisted — contact procurement.")
            return redirect("procurement:vendor_portal_home")
        form = VendorInvoiceSubmissionForm(request.POST, supplier=supplier,
                                           tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                # Force origin server-side — a portal user files only for their own supplier,
                # never another one, whatever the POST carries.
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.supplier = supplier
                obj.submitted_by = request.user
                obj.save()
                write_audit_log(request.user, obj, "create")
            messages.success(request,
                             f"Submission {obj.number} received — procurement will review it.")
            return redirect("procurement:vendor_portal_home")
    else:
        form = VendorInvoiceSubmissionForm(supplier=supplier, tenant=request.tenant)
    return render(request, "procurement/vendormanagement/invoice_new.html", {
        "form": form,
        "supplier": supplier,
        "suspension": suspension,
    })


# -- sourcing bids through the portal (6.5's deferred gated supplier page) ------------------------

def _own_bid_or_bounce(request, supplier, pk):
    """The bound supplier's OWN bid, or None after flashing a bounce. Ownership is checked
    against the ACCESS-derived supplier — never a POST field — so one vendor login can
    never open another company's proposal."""
    obj = (SourcingBid.objects.filter(tenant=request.tenant, pk=pk)
           .select_related("event").first())
    if obj is None or obj.supplier_id != supplier.pk:
        messages.error(request, "That bid is not yours to manage.")
        return None
    return obj


@login_required
def vendor_portal_bids(request):
    access, supplier, refusal = _vendor_access(request)
    if refusal is not None:
        return refusal
    bids = (SourcingBid.objects
            .filter(tenant=request.tenant, supplier=supplier)
            .select_related("event").order_by("-created_at", "-id"))
    return render(request, "procurement/vendormanagement/portal_bids.html", {
        "supplier": supplier,
        "bids": bids,
        "suspension": access.suspension,
        "today": timezone.localdate(),
    })


@login_required
def vendor_portal_bid_edit(request, pk):
    """Complete a DRAFT bid. Submitted/decided proposals are immutable evidence — the
    gate refuses them the same way the staff console does."""
    access, supplier, refusal = _vendor_access(request)
    if refusal is not None:
        return refusal
    bid = _own_bid_or_bounce(request, supplier, pk)
    if bid is None:
        return redirect("procurement:vendor_portal_bids")
    if bid.status != "draft":
        messages.error(request,
                       f"Bid {bid.number} was already submitted — it can no longer be edited.")
        return redirect("procurement:vendor_portal_bids")
    if request.method == "POST":
        form = VendorBidForm(request.POST, instance=bid, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                # Server-forced origin: the bid keeps its own event and supplier whatever
                # the payload carries; only draft CONTENT is editable here.
                obj.event = bid.event
                obj.supplier = supplier
                obj.save()
            write_audit_log(request.user, bid, "update", {"scope": "portal-draft"})
            messages.success(request,
                             f"Bid {bid.number} saved — submit it when you are ready.")
            return redirect("procurement:vendor_portal_bids")
    else:
        form = VendorBidForm(instance=bid, tenant=request.tenant)
    return render(request, "procurement/vendormanagement/portal_bid_edit.html", {
        "form": form,
        "bid": bid,
        "supplier": supplier,
        "suspension": access.suspension,
    })


@login_required
@require_POST
def vendor_portal_bid_submit(request, pk):
    """draft → submitted through SourcingBid.submit() under the SAME double lock the staff
    console uses (bid + event), so a portal submit racing event-close cannot slip through.
    A blocked supplier may not file — consistent with the invoice gate."""
    access, supplier, refusal = _vendor_access(request)
    if refusal is not None:
        return refusal
    bid = _own_bid_or_bounce(request, supplier, pk)
    if bid is None:
        return redirect("procurement:vendor_portal_bids")
    if access.suspension is not None:
        messages.error(request,
                       "Your account is currently suspended/blacklisted — contact procurement.")
        return redirect("procurement:vendor_portal_bids")
    with transaction.atomic():
        locked = SourcingBid.objects.select_for_update().get(pk=bid.pk, tenant=request.tenant)
        SourcingEvent.objects.select_for_update().get(pk=locked.event_id)
        if locked.submit(request.user):
            write_audit_log(request.user, locked, "submit", {"via": "portal"})
            messages.success(request,
                             f"Bid {locked.number} submitted for evaluation — thank you.")
        else:
            messages.error(request,
                           f"Bid {locked.number} cannot be submitted — it was already sent or "
                           f"the sourcing event is no longer open.")
    return redirect("procurement:vendor_portal_bids")
