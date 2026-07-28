"""SCM 4.9 Quality Management — QualityAudit views: schedule → run → findings → report → close.

Plain ``crud_*`` for the CRUD (there is no child formset — an audit's findings are
``NonConformance`` rows, not inline children), plus the lifecycle actions and the one action that
makes ``NonConformance.source="audit"`` honest: ``qualityaudit_add_finding`` is the ONLY code path
in the app that creates such a row.

Nothing here touches Item, LotSerial or StockMove — see the model docstring.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _date_window, _need_tenant
from apps.scm.forms._common import _employee_parties
from apps.scm.models import NonConformance, QualityAudit
from apps.scm.forms import QualityAuditFindingForm, QualityAuditForm


@login_required
def qualityaudit_list(request):
    findings = NonConformance.objects.filter(audit_id=OuterRef("pk"))
    qs = (QualityAudit.objects.filter(tenant=request.tenant)
          .select_related("auditee_party", "auditee_org_unit", "checklist_plan", "lead_auditor")
          .annotate(
              # `_agg` suffixes: `major_count`/`minor_count` are read-only @propertys on the model,
              # and Django cannot set an annotation onto a property when instantiating each row —
              # the list page 500s with "AttributeError: can't set attribute". Check the model
              # before naming any annotation.
              major_count_agg=Count("findings", distinct=True,
                                    filter=Q(findings__severity__in=QualityAudit.MAJOR_SEVERITIES)),
              minor_count_agg=Count("findings", distinct=True,
                                    filter=~Q(findings__severity__in=QualityAudit.MAJOR_SEVERITIES)),
              # "Any still open?" is a yes/no on the row and the close guard's own test — Exists
              # stops at the first match where a third Count would widen the GROUP BY.
              has_open_finding=Exists(
                  findings.filter(status__in=QualityAudit.OPEN_FINDING_STATUSES)))
          # Explicit: the two annotate()s set a GROUP BY, which unsets QuerySet.ordered and makes
          # the paginator warn on every page load (4.8 finding).
          .order_by("-planned_date", "-id"))
    qs = _date_window(qs, request.GET, "planned_date")
    stats = QualityAudit.objects.filter(tenant=request.tenant).aggregate(
        planned=Count("id", filter=Q(status="planned")),
        in_progress=Count("id", filter=Q(status="in_progress")),
        reported=Count("id", filter=Q(status="reported")),
        closed=Count("id", filter=Q(status="closed")),
        high_risk=Count("id", filter=Q(risk_level="high") & ~Q(status__in=("closed", "cancelled"))),
    )
    return crud_list(
        request, qs, "scm/quality/qualityaudit/list.html",
        search_fields=["number", "title", "standard", "scope", "notes"],
        filters=[("audit_type", "audit_type", False), ("status", "status", False),
                 ("risk_level", "risk_level", False), ("lead_auditor", "lead_auditor_id", True)],
        extra_context={
            "type_choices": QualityAudit.AUDIT_TYPE_CHOICES,
            "status_choices": QualityAudit.STATUS_CHOICES,
            "risk_choices": QualityAudit.RISK_LEVEL_CHOICES,
            "auditors": _employee_parties(request.tenant),
            "stats": stats,
        },
    )


@login_required
def qualityaudit_create(request):
    if _need_tenant(request):
        return redirect("scm:qualityaudit_list")
    return crud_create(request, form_class=QualityAuditForm,
                       template="scm/quality/qualityaudit/form.html",
                       success_url="scm:qualityaudit_list")


@login_required
def qualityaudit_edit(request, pk):
    obj = get_object_or_404(QualityAudit, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"Audit {obj.number} is {obj.get_status_display().lower()} and "
                                "can no longer be edited.")
        return redirect("scm:qualityaudit_detail", pk=pk)
    return crud_edit(request, model=QualityAudit, pk=pk, form_class=QualityAuditForm,
                     template="scm/quality/qualityaudit/form.html",
                     success_url="scm:qualityaudit_list")


@login_required
def qualityaudit_detail(request, pk):
    obj = get_object_or_404(
        QualityAudit.objects.select_related("auditee_party", "auditee_org_unit", "checklist_plan",
                                            "lead_auditor"),
        pk=pk, tenant=request.tenant)
    findings = list(obj.findings.select_related("item", "owner", "supplier").all())
    return render(request, "scm/quality/qualityaudit/detail.html", {
        "obj": obj,
        "checklist": (obj.checklist_plan.characteristics.select_related("uom").all()
                      if obj.checklist_plan_id else []),
        "findings": findings,
        # Counted off the list already in memory rather than three more aggregates on a page that
        # has just fetched every row.
        "major_count": sum(1 for f in findings if f.severity in QualityAudit.MAJOR_SEVERITIES),
        "minor_count": sum(1 for f in findings if f.severity not in QualityAudit.MAJOR_SEVERITIES),
        "open_finding_count": sum(1 for f in findings
                                  if f.status in QualityAudit.OPEN_FINDING_STATUSES),
        "capa_actions": obj.capa_actions.select_related("owner", "supplier").all(),
        "finding_form": QualityAuditFindingForm(tenant=request.tenant),
    })


@login_required
@require_POST
def qualityaudit_delete(request, pk):
    obj = get_object_or_404(QualityAudit, pk=pk, tenant=request.tenant)
    if obj.status != "planned":
        messages.error(request, "Only a planned audit can be deleted — cancel it instead so its "
                                "history survives.")
        return redirect("scm:qualityaudit_detail", pk=pk)
    # NonConformance.audit and CapaAction.audit are SET_NULL, so deleting would silently orphan the
    # findings rather than error — and an orphaned `source="audit"` row is a finding nobody can
    # trace back to an audit.
    if obj.findings.exists():
        messages.error(request, "This audit has findings and cannot be deleted — cancel it "
                                "instead.")
        return redirect("scm:qualityaudit_detail", pk=pk)
    return crud_delete(request, model=QualityAudit, pk=pk, success_url="scm:qualityaudit_list")


# ============================================================= lifecycle
def _transition(request, pk, *, from_statuses, to_status, verb, stamp=None):
    """Shared status move — lock, re-read INSIDE the transaction, guard, stamp, audit, redirect."""
    with transaction.atomic():
        obj = get_object_or_404(QualityAudit.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in from_statuses:
            messages.error(request, f"This audit can't be {verb} from "
                                    f"{obj.get_status_display().lower()}.")
            return redirect("scm:qualityaudit_detail", pk=pk)
        fields = ["status", "updated_at"]
        obj.status = to_status
        for field, value in (stamp or {}).items():
            setattr(obj, field, value)
            fields.append(field)
        obj.save(update_fields=list(dict.fromkeys(fields)))
    write_audit_log(request.user, obj, "update", {"action": verb, "status": to_status})
    messages.success(request, f"Audit {obj.number} {verb}.")
    return redirect("scm:qualityaudit_detail", pk=pk)


@login_required
@require_POST
def qualityaudit_start(request, pk):
    return _transition(request, pk, from_statuses=("planned",), to_status="in_progress",
                       verb="started", stamp={"actual_start": timezone.localdate()})


@login_required
@require_POST
def qualityaudit_complete(request, pk):
    """Report the audit. Refuses while the conclusion is blank — the narrative IS the report."""
    obj = get_object_or_404(QualityAudit, pk=pk, tenant=request.tenant)
    if obj.status == "in_progress" and not (obj.conclusion or "").strip():
        messages.error(request, "Write the audit conclusion before reporting it — edit the audit "
                                "and fill it in.")
        return redirect("scm:qualityaudit_detail", pk=pk)
    return _transition(request, pk, from_statuses=("in_progress",), to_status="reported",
                       verb="reported", stamp={"actual_end": timezone.localdate()})


@login_required
@require_POST
def qualityaudit_close(request, pk):
    """Close the audit — refused while any finding is still outstanding.

    Closure verification is the point of the whole register (Intelex / TrackWise): an audit closed
    over live findings is a clean report that hides open work. The GUARD is what protects this, not
    a permission gate — closing an audit whose findings are all genuinely closed is bookkeeping,
    and the privileged writes in 4.9 are the ones that move stock status or sign off a decision.
    """
    obj = get_object_or_404(QualityAudit, pk=pk, tenant=request.tenant)
    open_findings = obj.findings.filter(status__in=QualityAudit.OPEN_FINDING_STATUSES).count()
    if obj.status == "reported" and open_findings:
        messages.error(request, f"{open_findings} finding(s) are still open — close them before "
                                "closing the audit.")
        return redirect("scm:qualityaudit_detail", pk=pk)
    return _transition(request, pk, from_statuses=("reported",), to_status="closed", verb="closed")


@login_required
@require_POST
def qualityaudit_cancel(request, pk):
    return _transition(request, pk, from_statuses=("planned", "in_progress"),
                       to_status="cancelled", verb="cancelled")


@login_required
@require_POST
def qualityaudit_add_finding(request, pk):
    """Raise a finding — a ``NonConformance(source="audit")``, NOT a second findings table.

    This view is the ONLY creator of ``source="audit"`` rows in the whole app, which is what makes
    that choice value truthful rather than decorative. ``@login_required``: an auditor recording
    what they saw is ordinary work, and the row lands OPEN for someone to own.
    """
    obj = get_object_or_404(QualityAudit.objects.select_related("lead_auditor"),
                            pk=pk, tenant=request.tenant)
    if obj.status not in ("in_progress", "reported"):
        messages.error(request, "Start the audit before recording findings against it.")
        return redirect("scm:qualityaudit_detail", pk=pk)
    form = QualityAuditFindingForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("scm:qualityaudit_detail", pk=pk)
    with transaction.atomic():
        finding = NonConformance(
            tenant=request.tenant, source="audit", audit=obj,
            title=form.cleaned_data["title"], description=form.cleaned_data["description"],
            severity=form.cleaned_data["severity"],
            defect_category=form.cleaned_data["defect_category"],
            owner=form.cleaned_data.get("owner"), due_date=form.cleaned_data.get("due_date"),
            detected_by=obj.lead_auditor, detected_on=timezone.localdate(),
        )
        finding.save()
    write_audit_log(request.user, finding, "create",
                    {"action": "add_finding", "audit": obj.number,
                     "severity": finding.severity})
    messages.success(request, f"Finding {finding.number} recorded against {obj.number}.")
    return redirect("scm:qualityaudit_detail", pk=pk)


@login_required
def qualityaudit_print(request, pk):
    """The printable audit report — scope, checklist, findings and conclusion on one page."""
    obj = get_object_or_404(
        QualityAudit.objects.select_related("auditee_party", "auditee_org_unit", "checklist_plan",
                                            "lead_auditor"),
        pk=pk, tenant=request.tenant)
    findings = list(obj.findings.select_related("item", "owner").all())
    return render(request, "scm/quality/qualityaudit/report.html", {
        "obj": obj,
        "checklist": (obj.checklist_plan.characteristics.select_related("uom").all()
                      if obj.checklist_plan_id else []),
        "findings": findings,
        "major_count": sum(1 for f in findings if f.severity in QualityAudit.MAJOR_SEVERITIES),
        "minor_count": sum(1 for f in findings if f.severity not in QualityAudit.MAJOR_SEVERITIES),
        "printed_at": timezone.now(),
    })
