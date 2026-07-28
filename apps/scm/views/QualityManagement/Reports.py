"""SCM 4.9 Quality Management — the Certificate of Analysis pages.

The NavERP "Certificate of Analysis (CoA)" bullet is a REPORT, not a CRUD list — the
``scm:mrp_report`` / ``scm:safety_stock_report`` / ``scm:valuation_report`` precedent. There is no
``CertificateOfAnalysis`` table: a certificate IS an outgoing ``QualityInspection`` that has been
stamped with a ``coa_number``, an issue date and a recipient, printed over the result rows flagged
``include_on_coa``.

Three views, one rule between them: :meth:`QualityInspection.coa_blockers` decides what may be
certified. The report shows the first blocker, the issue action refuses with all of them, and the
print page refuses to render at all before a number exists. AlisQI's rule — never issue a
certificate containing an out-of-specification value — lives in that one method, so the three can
never drift apart.
"""
from datetime import datetime

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _date_window, _item_qs
from apps.scm.forms._common import _customer_parties
from apps.scm.models import InspectionResult, QualityInspection
from apps.scm.forms import QualityInspectionCoAIssueForm

from apps.core.utils import next_number


@login_required
def coa_report(request):
    """Every outgoing inspection and where it stands on certification.

    The two ``Exists()`` annotations answer the template's actual question — "is there a failing /
    an unrecorded included characteristic?" — which is a yes/no, not a count. A ``Count()`` here
    would GROUP BY the whole result table per row and unset ``QuerySet.ordered`` into the bargain.
    """
    included = InspectionResult.objects.filter(inspection_id=OuterRef("pk"), include_on_coa=True)
    qs = (QualityInspection.objects
          .filter(tenant=request.tenant, inspection_type="outgoing")
          .select_related("item", "lot_serial__item", "plan",
                          "shipment__sales_order__customer", "coa_issued_to", "inspector")
          .annotate(has_failing_result=Exists(included.filter(result="fail")),
                    has_pending_result=Exists(included.filter(result="pending")))
          .order_by("-inspected_on", "-id"))

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(coa_number__icontains=q)
                       | Q(item__sku__icontains=q) | Q(item__name__icontains=q)
                       | Q(lot_serial__number__icontains=q))
    # L11: never hand a non-numeric value to an int FK filter — the same guard crud_list applies.
    for param, lookup in (("item", "item_id"),
                          ("customer", "shipment__sales_order__customer_id")):
        value = request.GET.get(param, "").strip()
        if value.isdigit():
            qs = qs.filter(**{lookup: int(value)})
    state = request.GET.get("coa_state", "").strip()
    if state == "issued":
        qs = qs.exclude(coa_number="")
    elif state == "blocked":
        # "Blocked" as SQL can see it: not yet certified and something the database knows about is
        # wrong. The full seven-rule verdict is per-row (coa_blockers below) — this narrows the
        # page, it does not replace the rule.
        qs = qs.filter(coa_number="").filter(
            Q(has_failing_result=True) | Q(has_pending_result=True)
            | ~Q(status="passed") | ~Q(usage_decision__in=QualityInspection.ACCEPTING_DECISIONS))
    elif state == "ready":
        qs = qs.filter(coa_number="", status="passed",
                       usage_decision__in=QualityInspection.ACCEPTING_DECISIONS,
                       has_failing_result=False, has_pending_result=False)
    qs = _date_window(qs, request.GET, "inspected_on")

    page_obj = paginate(request, qs)
    rows = []
    for inspection in page_obj.object_list:
        blockers = inspection.coa_blockers()
        rows.append({
            "obj": inspection,
            "blockers": blockers,
            # The template shows ONE reason — a column of seven strings is unreadable, and the
            # issue action lists them all when somebody actually tries.
            "first_blocker": blockers[0] if blockers else "",
            "coa_ready": not blockers,
        })
    return render(request, "scm/quality/coa/report.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "state_choices": [("issued", "Issued"), ("ready", "Ready to issue"),
                          ("blocked", "Blocked")],
        "items": _item_qs(request.tenant),
        "customers": _customer_parties(request.tenant),
        "issue_form": QualityInspectionCoAIssueForm(tenant=request.tenant),
    })


@tenant_admin_required
@require_POST
def coa_issue(request, pk):
    """Stamp the certificate. Tenant-admin gated — this issues a document to a customer.

    The ``coa_number`` is re-read INSIDE the lock so a double POST cannot burn two numbers on one
    inspection; an already-issued row is an idempotent ``messages.info`` plus a redirect to the
    print page, not an error.
    """
    form = QualityInspectionCoAIssueForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("scm:coa_report")
    issued_to = form.cleaned_data.get("coa_issued_to")
    issued_on = form.cleaned_data.get("issued_on")
    with transaction.atomic():
        obj = get_object_or_404(
            QualityInspection.objects.select_for_update().select_related("item", "lot_serial"),
            pk=pk, tenant=request.tenant)
        if obj.coa_number:
            messages.info(request, f"Certificate {obj.coa_number} has already been issued for "
                                   f"{obj.number}.")
            return redirect("scm:coa_print", pk=pk)
        blockers = obj.coa_blockers()
        if blockers:
            # Each blocker as its own message: they are independent reasons and joining them into
            # one sentence makes the list unreadable exactly when it matters.
            for blocker in blockers:
                messages.error(request, blocker)
            return redirect("scm:coa_report")
        # Belt-and-braces on top of next_number's field-ordered lookup: MySQL has no partial unique
        # index, so a `coa_number` column that is blank on most rows cannot carry a DB constraint to
        # catch a collision. Re-check explicitly instead — a certificate is a customer-facing
        # document and two of them sharing a number is not something to discover later.
        candidate = next_number(QualityInspection, request.tenant, "COA", field="coa_number")
        taken = set(QualityInspection.objects
                    .filter(tenant=request.tenant, coa_number__startswith="COA-")
                    .values_list("coa_number", flat=True))
        while candidate in taken:
            sequence = int(candidate.rsplit("-", 1)[1]) + 1
            candidate = f"COA-{sequence:05d}"
        obj.coa_number = candidate
        # The form bounds `issued_on` to 2000-2100, so combining it into an aware datetime here
        # cannot overflow the way an unbounded 9999-12-31 did in 4.8.
        obj.coa_issued_on = (
            timezone.make_aware(datetime.combine(issued_on, datetime.min.time()),
                                timezone.get_current_timezone())
            if issued_on else timezone.now())
        obj.coa_issued_to = issued_to
        obj.save(update_fields=["coa_number", "coa_issued_on", "coa_issued_to", "updated_at"])
    write_audit_log(request.user, obj, "update", {
        "action": "coa_issue", "coa_number": obj.coa_number,
        "issued_to": str(issued_to) if issued_to else ""})
    messages.success(request, f"Certificate {obj.coa_number} issued for {obj.number}.")
    return redirect("scm:coa_print", pk=pk)


@login_required
def coa_print(request, pk):
    """The certificate itself.

    Refuses to render an unissued one. A "preview" of a certificate is a document that looks
    exactly like the real thing but has not been signed off, and the whole value of the number is
    that it only exists once somebody accepted responsibility for the figures.
    """
    obj = get_object_or_404(
        QualityInspection.objects.select_related(
            "item", "item__uom", "lot_serial", "plan", "inspector", "coa_issued_to",
            "shipment__sales_order__customer"),
        pk=pk, tenant=request.tenant)
    if not obj.coa_number:
        messages.error(request, "No certificate has been issued for this inspection yet — issue "
                                "it from the Certificate of Analysis page first.")
        return redirect("scm:qualityinspection_detail", pk=pk)
    return render(request, "scm/quality/coa/print.html", {
        "obj": obj,
        "results": obj.coa_results,
        "customer": (obj.coa_issued_to
                     or (obj.shipment.sales_order.customer
                         if obj.shipment_id and obj.shipment.sales_order_id else None)),
        "printed_at": timezone.now(),
    })
