"""Procurement 6.1 User Dashboard & Portal — Quick Requisition Entry view.

**Quick Requisition Entry** bullet: the fast-track one-screen path into the procure-to-pay chain.
The spine stays 4.1's ``scm.PurchaseRequisition`` (L36): this view WRITES a header + its single
line inside ONE transaction, recalcs the derived total, and hands off to scm's requisition detail
page where submit/approve live. This module declares no requisition storage of its own.
"""
from django.db import transaction

from apps.procurement.forms import QuickRequisitionForm
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine


@login_required
def quickreq_create(request):
    """Draft a single-line requisition in one submit.

    Everything sensitive defaults safely: the requisition is raised under the SIGNED-IN user's
    name (never a choosable requester), starts as ``draft`` so scm's approval workflow still sees
    it, and the derived ``estimated_total`` comes from ``recalc_totals()`` rather than trusting
    any client-supplied figure. On success the user lands on the scm detail page to review/submit.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before raising requisitions.")
        return redirect("dashboard:home")

    recent = (PurchaseRequisition.objects.filter(tenant=request.tenant, requester=request.user)
              .order_by("-created_at", "-id")[:5])

    if request.method == "POST":
        form = QuickRequisitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cleaned = form.cleaned_data
            # One transaction so a line failure can never leave an empty header behind.
            with transaction.atomic():
                req = PurchaseRequisition.objects.create(
                    tenant=request.tenant,
                    title=cleaned["title"],
                    requester=request.user,
                    org_unit=cleaned.get("org_unit"),
                    currency=cleaned.get("currency"),
                    required_by=cleaned.get("required_by"),
                    justification=cleaned.get("justification") or "",
                )
                PurchaseRequisitionLine.objects.create(
                    requisition=req,
                    item_description=cleaned["item_description"],
                    sku_hint=cleaned.get("sku_hint") or "",
                    uom_hint=cleaned.get("uom_hint") or "",
                    quantity=cleaned["quantity"],
                    estimated_unit_price=cleaned.get("estimated_unit_price") or 0,
                    gl_account=cleaned.get("gl_account"),
                    needed_by=cleaned.get("required_by"),
                )
                req.recalc_totals()
            write_audit_log(request.user, req, "create")
            messages.success(request, f"Requisition {req.number} drafted — review and submit it "
                                      f"for approval when ready.")
            return redirect("scm:requisition_detail", pk=req.pk)
    else:
        form = QuickRequisitionForm(tenant=request.tenant)

    return render(request, "procurement/dashboardportal/quickrequisition.html", {
        "form": form,
        "recent": recent,
    })
