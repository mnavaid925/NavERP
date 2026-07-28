"""SCM 4.9 Quality Management — QualityInspection views: the inspection lifecycle.

Nothing in this file posts a StockMove — a quarantine flips ``LotSerial.status`` and posts NOTHING
(ruling (b)), and the only ledger effect in 4.9 belongs to a scrap disposition on the NCR. What the
actions here DO change is state that gates a certificate, so they follow the same discipline as a
posting: ``@require_POST``, inside ``transaction.atomic()``, behind ``select_for_update()`` with the
status re-read INSIDE the transaction. Without that re-read two concurrent POSTs (a double-click, a
retry, a replay) can both see ``passed`` and each stamp a usage decision or flip a lot's status.

``@tenant_admin_required`` is reserved for the three privileged writes: the usage decision (a
sign-off) and the two lot-status flips (they change what the warehouse may ship). Everything else —
starting, completing, generating results, proposing an NCR — is ordinary inspector work.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_date_window, _item_qs, _need_tenant, _supplier_parties)
from apps.scm.forms._common import _employee_parties
from apps.scm.models import LotSerial, NonConformance, QualityInspection
from apps.scm.forms import (InspectionResultFormSet, QualityInspectionDecisionForm,
                            QualityInspectionForm)

ZERO = Decimal("0")


@login_required
def qualityinspection_list(request):
    qs = (QualityInspection.objects.filter(tenant=request.tenant)
          # lot_serial__item because LotSerial.__str__ reads item.sku — the FK alone still leaves
          # that hop lazy, which is a query per row.
          .select_related("item", "lot_serial__item", "plan", "inspector", "supplier", "location")
          # The list only asks "does this one have an NCR?" — Exists stops at the first match,
          # where a Count would GROUP BY the whole NCR table (and unset QuerySet.ordered).
          .annotate(has_ncr=Exists(
              NonConformance.objects.filter(inspection_id=OuterRef("pk")))))
    qs = _date_window(qs, request.GET, "inspected_on")
    stats = QualityInspection.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status__in=("draft", "in_progress"))),
        passed=Count("id", filter=Q(status="passed")),
        failed=Count("id", filter=Q(status="failed")),
        on_hold=Count("id", filter=Q(status="on_hold")),
        ncrs_raised=Count("id", filter=Q(action_taken="ncr_raised")),
    )
    return crud_list(
        request, qs, "scm/quality/qualityinspection/list.html",
        search_fields=["number", "notes", "coa_number", "item__sku", "item__name",
                       "lot_serial__number", "supplier_coa_reference"],
        filters=[("status", "status", False), ("inspection_type", "inspection_type", False),
                 ("usage_decision", "usage_decision", False), ("item", "item_id", True),
                 ("supplier", "supplier_id", True), ("inspector", "inspector_id", True)],
        extra_context={
            "status_choices": QualityInspection.STATUS_CHOICES,
            "type_choices": QualityInspection.INSPECTION_TYPE_CHOICES,
            "decision_choices": QualityInspection.USAGE_DECISION_CHOICES,
            "items": _item_qs(request.tenant),
            "suppliers": _supplier_parties(request.tenant),
            "inspectors": _employee_parties(request.tenant),
            "stats": stats,
        },
    )


@login_required
def qualityinspection_create(request):
    return _qualityinspection_form(request, instance=None)


@login_required
def qualityinspection_edit(request, pk):
    obj = get_object_or_404(QualityInspection, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"Inspection {obj.number} is "
                                f"{obj.get_status_display().lower()} and can no longer be edited.")
        return redirect("scm:qualityinspection_detail", pk=pk)
    return _qualityinspection_form(request, instance=obj)


def _qualityinspection_form(request, instance):
    """Header + result formset in ONE transaction.

    A brand-new inspection that names a plan gets its results snapshotted on save, so the inspector
    has the checklist without a second click. ``generate_results()`` is a no-op once any result row
    exists, so this can never overwrite a set that has been filled in.

    ``formset.instance = form.instance`` before ``formset.is_valid()`` — see
    ``_inspectionplan_form`` for why that line is load-bearing rather than tidiness.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:qualityinspection_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = QualityInspectionForm(request.POST, instance=instance, tenant=request.tenant)
        formset = InspectionResultFormSet(request.POST, instance=instance,
                                          form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance
        if form_ok and formset.is_valid():
            with transaction.atomic():
                inspection = form.save(commit=False)
                inspection.tenant = request.tenant
                inspection.save()
                formset.instance = inspection
                formset.save()
                generated = inspection.generate_results()
            write_audit_log(request.user, inspection, "update" if is_edit else "create",
                            _changed(form))
            if generated:
                messages.success(request, f"Inspection {inspection.number} saved — {generated} "
                                          "characteristic(s) snapshotted from the plan.")
            else:
                messages.success(request, f"Inspection {inspection.number} saved.")
            return redirect("scm:qualityinspection_detail", pk=inspection.pk)
    else:
        form = QualityInspectionForm(instance=instance, tenant=request.tenant,
                                     initial={} if is_edit else {"inspected_on": timezone.localdate()})
        formset = InspectionResultFormSet(instance=instance,
                                          form_kwargs={"tenant": request.tenant})
    return render(request, "scm/quality/qualityinspection/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def qualityinspection_detail(request, pk):
    obj = get_object_or_404(
        QualityInspection.objects.select_related(
            "plan", "item", "lot_serial__item", "location", "supplier", "inspector",
            "goods_receipt", "work_order__item", "shipment", "coa_issued_to"),
        pk=pk, tenant=request.tenant)
    # _result_rows() caches on the instance, so the verdict, the counts, the CoA list and every one
    # of the seven blockers below share ONE query rather than firing eight.
    results = obj._result_rows()
    return render(request, "scm/quality/qualityinspection/detail.html", {
        "obj": obj,
        "results": results,
        "evaluated_result": obj.evaluated_result,
        "failed_count": obj.failed_count,
        "pending_count": obj.pending_count,
        "mandatory_pending_count": obj.mandatory_pending_count,
        "has_critical_failure": obj.has_critical_failure,
        "coa_results": obj.coa_results,
        "coa_blockers": obj.coa_blockers(),
        "nonconformances": obj.nonconformances.select_related("item", "owner").all(),
        "decision_form": QualityInspectionDecisionForm(),
    })


@login_required
@require_POST
def qualityinspection_delete(request, pk):
    obj = get_object_or_404(QualityInspection, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft or in-progress inspection can be deleted — cancel "
                                "it instead so its history survives.")
        return redirect("scm:qualityinspection_detail", pk=pk)
    if obj.nonconformances.exists():
        messages.error(request, "This inspection has raised non-conformance reports and cannot be "
                                "deleted — cancel it instead.")
        return redirect("scm:qualityinspection_detail", pk=pk)
    if obj.coa_number:
        messages.error(request, f"Certificate {obj.coa_number} has been issued against this "
                                "inspection — it cannot be deleted.")
        return redirect("scm:qualityinspection_detail", pk=pk)
    return crud_delete(request, model=QualityInspection, pk=pk,
                       success_url="scm:qualityinspection_list")


# ============================================================= lifecycle (no stock effect)
def _transition(request, pk, *, from_statuses, to_status, verb, stamp=None):
    """Shared status move — lock, re-read, guard, stamp, audit, redirect.

    ``select_for_update()`` with the status read INSIDE the transaction is what makes a
    double-submitted POST idempotent: the second one sees the status the first one wrote and is
    bounced with a message, instead of both passing the guard they entered with.
    """
    with transaction.atomic():
        obj = get_object_or_404(QualityInspection.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in from_statuses:
            messages.error(request, f"This inspection can't be {verb} from "
                                    f"{obj.get_status_display().lower()}.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        fields = ["status", "updated_at"]
        obj.status = to_status
        for field, value in (stamp or {}).items():
            setattr(obj, field, value)
            fields.append(field)
        obj.save(update_fields=list(dict.fromkeys(fields)))
    write_audit_log(request.user, obj, "update", {"action": verb, "status": to_status})
    messages.success(request, f"Inspection {obj.number} {verb}.")
    return redirect("scm:qualityinspection_detail", pk=pk)


@login_required
@require_POST
def qualityinspection_start(request, pk):
    return _transition(request, pk, from_statuses=("draft",), to_status="in_progress",
                       verb="started")


@login_required
@require_POST
def qualityinspection_hold(request, pk):
    return _transition(request, pk, from_statuses=("draft", "in_progress"), to_status="on_hold",
                       verb="put on hold")


@login_required
@require_POST
def qualityinspection_resume(request, pk):
    return _transition(request, pk, from_statuses=("on_hold",), to_status="in_progress",
                       verb="resumed")


@login_required
@require_POST
def qualityinspection_cancel(request, pk):
    return _transition(request, pk, from_statuses=("draft", "in_progress", "on_hold"),
                       to_status="cancelled", verb="cancelled")


@login_required
@require_POST
def qualityinspection_generate_results(request, pk):
    """Snapshot the plan's characteristics onto result rows — the only writer of that block."""
    with transaction.atomic():
        obj = get_object_or_404(QualityInspection.objects.select_for_update().select_related("plan"),
                                pk=pk, tenant=request.tenant)
        if obj.plan_id is None:
            messages.error(request, "Pick an inspection plan first — there are no characteristics "
                                    "to copy without one.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        created = obj.generate_results()
    if not created:
        # Information, not an error: a filled-in result set is deliberately never overwritten, and
        # somebody clicking the button twice has not done anything wrong.
        messages.info(request, "This inspection already has results — they are a snapshot and are "
                               "never re-copied from the plan.")
        return redirect("scm:qualityinspection_detail", pk=pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "generate_results", "characteristics": created})
    messages.success(request, f"Snapshotted {created} characteristic(s) from {obj.plan.code}.")
    return redirect("scm:qualityinspection_detail", pk=pk)


@login_required
@require_POST
def qualityinspection_complete(request, pk):
    """Close the inspection at the verdict the RESULT ROWS say — never a typed one."""
    with transaction.atomic():
        obj = get_object_or_404(QualityInspection.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status != "in_progress":
            messages.error(request, "Start the inspection before completing it.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        if not obj._result_rows():
            messages.error(request, "There are no results to judge — generate them from the plan "
                                    "first.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        outstanding = obj.mandatory_pending_count
        if outstanding:
            messages.error(request, f"{outstanding} mandatory characteristic(s) still have no "
                                    "recorded value.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        verdict = obj.evaluated_result
        obj.status = "passed" if verdict == "pass" else "failed"
        obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    {"action": "complete", "status": obj.status, "verdict": verdict})
    messages.success(request, f"Inspection {obj.number} completed — {obj.get_status_display()}.")
    return redirect("scm:qualityinspection_detail", pk=pk)


@tenant_admin_required
@require_POST
def qualityinspection_decide(request, pk):
    """Record the SAP-style usage decision. Tenant-admin gated: this is a formal sign-off."""
    form = QualityInspectionDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("scm:qualityinspection_detail", pk=pk)
    decision = form.cleaned_data["usage_decision"]
    note = (form.cleaned_data.get("notes") or "").strip()
    with transaction.atomic():
        obj = get_object_or_404(QualityInspection.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in ("passed", "failed"):
            messages.error(request, "Complete the inspection before deciding what happens to the "
                                    "lot.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        obj.usage_decision = decision
        fields = ["usage_decision", "updated_at"]
        if note:
            stamp = f"[{timezone.localdate():%Y-%m-%d} {obj.get_usage_decision_display()}] {note}"
            obj.notes = f"{obj.notes}\n{stamp}".strip()
            fields.append("notes")
        obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update",
                    {"action": "decide", "usage_decision": decision})
    messages.success(request, f"Usage decision on {obj.number}: "
                              f"{obj.get_usage_decision_display()}.")
    return redirect("scm:qualityinspection_detail", pk=pk)


def _flip_lot_status(request, pk, *, to_status, require_status, verb, action_taken=None):
    """Move the inspected lot between ``available`` and ``quarantine``.

    Posts NO StockMove — ruling (b). The goods are physically where they were; quarantine is a
    STATUS, and on-hand is always ``Sum(quantity)`` over the append-only ledger. A parallel "blocked
    quantity" column would be a second source of truth for a number the ledger already answers.

    The lock is taken on the LOT, not the inspection: two inspections of the same batch flipping it
    at once is the race that matters.
    """
    with transaction.atomic():
        obj = get_object_or_404(QualityInspection.objects.select_related("lot_serial"),
                                pk=pk, tenant=request.tenant)
        if obj.lot_serial_id is None:
            messages.error(request, "This inspection names no lot or serial, so there is nothing "
                                    "to quarantine or release.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        lot = (LotSerial.objects.select_for_update()
               .filter(pk=obj.lot_serial_id, tenant=request.tenant).first())
        if lot is None:
            messages.error(request, "The lot on this inspection no longer exists.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        if lot.status != require_status:
            messages.error(request, f"Lot {lot.number} is {lot.get_status_display().lower()} — it "
                                    f"cannot be {verb}.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        lot.status = to_status
        lot.save(update_fields=["status", "updated_at"])
        if action_taken and obj.action_taken != action_taken:
            obj.action_taken = action_taken
            obj.save(update_fields=["action_taken", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    {"action": verb, "lot": lot.number, "lot_status": to_status})
    messages.success(request, f"Lot {lot.number} {verb}. No stock movement was posted — the goods "
                              "have not moved.")
    return redirect("scm:qualityinspection_detail", pk=pk)


@tenant_admin_required
@require_POST
def qualityinspection_quarantine(request, pk):
    return _flip_lot_status(request, pk, to_status="quarantine", require_status="available",
                            verb="quarantined", action_taken="quarantined")


@tenant_admin_required
@require_POST
def qualityinspection_release_lot(request, pk):
    return _flip_lot_status(request, pk, to_status="available", require_status="quarantine",
                            verb="released")


@login_required
@require_POST
def qualityinspection_raise_ncr(request, pk):
    """Propose a non-conformance from a failed inspection — compute-then-convert.

    Oracle auto-creates the NC; NavERP PROPOSES it: the draft lands OPEN with everything the
    inspection already knows pre-filled, and a human owns it from there. ``@login_required``, not
    tenant-admin, for the same reason ``mrp_create_workorder`` is: this creates a draft document,
    it does not move stock or sign anything off.
    """
    with transaction.atomic():
        obj = get_object_or_404(
            QualityInspection.objects.select_for_update().select_related("item", "inspector"),
            pk=pk, tenant=request.tenant)
        if obj.status != "failed" and obj.usage_decision != "reject":
            messages.error(request, "Raise a non-conformance from a failed inspection or a "
                                    "rejected usage decision.")
            return redirect("scm:qualityinspection_detail", pk=pk)
        existing = obj.nonconformances.first()
        if existing is not None:
            # Once only. Re-clicking is not an error — it is somebody looking for the NCR they
            # already raised, so take them to it.
            messages.info(request, f"{existing.number} was already raised from this inspection.")
            return redirect("scm:nonconformance_detail", pk=existing.pk)
        ncr = NonConformance(
            tenant=request.tenant, source="inspection", inspection=obj,
            goods_receipt_id=obj.goods_receipt_id, work_order_id=obj.work_order_id,
            shipment_id=obj.shipment_id, item_id=obj.item_id, lot_serial_id=obj.lot_serial_id,
            location_id=obj.location_id, supplier_id=obj.supplier_id,
            quantity_affected=obj.quantity_rejected or ZERO,
            uom_id=obj.item.uom_id if obj.item_id else None,
            severity="critical" if obj.has_critical_failure else "major",
            title=f"Failed inspection {obj.number} — {obj.item.sku}",
            description=(f"Raised from quality inspection {obj.number} on "
                         f"{obj.inspected_on:%Y-%m-%d}. {obj.failed_count} characteristic(s) out "
                         f"of specification."),
            detected_by_id=obj.inspector_id, detected_on=obj.inspected_on,
        )
        ncr.save()
        obj.action_taken = "ncr_raised"
        obj.save(update_fields=["action_taken", "updated_at"])
    write_audit_log(request.user, ncr, "create",
                    {"action": "raise_ncr", "inspection": obj.number})
    messages.success(request, f"{ncr.number} raised from {obj.number} — review the detail and the "
                              "cost of quality before dispositioning.")
    return redirect("scm:nonconformance_detail", pk=ncr.pk)
