"""Inventory 5.15 Quality Control (QC) & Inspection — DefectReport views.

CRUD plus the two resolution verbs (writeoff / close). Edit is open-only (a resolved
report's facts must not be rewritten beneath its ledger leg); delete follows the same
rule — a written-off report's number lives in an immutable StockMove row, so the delete
view refuses anything not open. Write-off and close are admin verbs: they dispose of
stock and close quality findings.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import DefectReportForm
from apps.inventory.models import DefectReport
from apps.inventory.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    """Tenant-scoped queryset with the joins every list/detail page renders."""
    return (DefectReport.objects.filter(tenant=tenant)
            .select_related("item", "location", "lot_serial", "reported_by", "ncr"))


@login_required
def defectreport_list(request):
    qs = _scoped(request.tenant)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    return crud_list(
        request,
        qs,
        "inventory/qc/defectreport/list.html",
        search_fields=["number", "item__sku", "item__name", "description"],
        filters=[],
        extra_context={
            "status_choices": DefectReport.STATUS_CHOICES,
            "status": status,
            "severity_choices": DefectReport.SEVERITY_CHOICES,
            "severity": severity,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def defectreport_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/qc/defectreport/detail.html", {
        "obj": obj,
        # The write-off leg once posted — read from the append-only book.
        "moves": obj.ledger_moves()[:20],
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@login_required
def defectreport_create(request):
    return crud_create(
        request, form_class=DefectReportForm,
        template="inventory/qc/defectreport/form.html",
        success_url="inventory:defectreport_list",
    )


@login_required
def defectreport_edit(request, pk):
    # Server-side status guard held UNDER the row lock across the whole request — a
    # concurrent writeoff()/close() cannot slip between our check and crud_edit's save
    # (review I2; its verbs take the same lock). crud_edit cannot know EDITABLE_STATUSES.
    with transaction.atomic():
        obj = get_object_or_404(DefectReport.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_editable:
            messages.error(
                request,
                f"{obj.number} has been resolved and can no longer be edited.")
            return redirect("inventory:defectreport_detail", pk=obj.pk)
        return crud_edit(
            request, model=DefectReport, pk=pk, form_class=DefectReportForm,
            template="inventory/qc/defectreport/form.html",
            success_url="inventory:defectreport_list",
        )


@tenant_admin_required
@require_POST
def defectreport_delete(request, pk):
    """Delete an OPEN report only — a written-off one's number is provenance in the ledger."""
    with transaction.atomic():
        obj = get_object_or_404(DefectReport.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_editable:
            messages.error(
                request,
                f"{obj.number} has been resolved and cannot be deleted.")
            return redirect("inventory:defectreport_detail", pk=obj.pk)
        write_audit_log(request.user, obj, "delete")
        number = obj.number
        obj.delete()
    messages.success(request, f"{number} deleted.")
    return redirect("inventory:defectreport_list")


@tenant_admin_required
@require_POST
def defectreport_writeoff(request, pk):
    return _run_action(request, pk, "writeoff")


@tenant_admin_required
@require_POST
def defectreport_close(request, pk):
    return _run_action(request, pk, "close")


# -- module-private helpers --------------------------------------------------------------------

_ACTION_MESSAGES = {
    "writeoff": "written off.",
    "close": "closed without write-off.",
}


def _run_action(request, pk, action):
    """Run one resolution verb and turn its refusal into a flash message.

    A refusal is EXPECTED traffic (double-click, stale tab), so it lands as a message
    on the detail page rather than an exception page.
    """
    obj = get_object_or_404(DefectReport, pk=pk, tenant=request.tenant)
    try:
        getattr(obj, action)(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"{obj.number} {_ACTION_MESSAGES[action]}")
    return redirect("inventory:defectreport_detail", pk=obj.pk)
