"""Inventory 5.10 Returns Management — ReturnInspection CRUD views."""
from django.db import transaction
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import (
    ReturnInspectionChecklistFormSet,
    ReturnInspectionForm,
)
from apps.inventory.models import (
    ReturnInspection,
    resolve_disposition_routing,
)
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import ReturnAuthorization, ReturnDisposition, ReturnLine


@login_required
def returninspection_list(request):
    """List warehouse return inspections with search, filtering and KPI strip."""
    qs = (
        ReturnInspection.objects.filter(tenant=request.tenant)
        .select_related(
            "return_authorization",
            "return_authorization__customer",
            "return_line", "item", "inspected_by",
        )
    )

    # Search & filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    condition_grade = request.GET.get("condition_grade", "").strip()
    if condition_grade:
        qs = qs.filter(condition_grade=condition_grade)

    functional_status = request.GET.get("functional_status", "").strip()
    if functional_status:
        qs = qs.filter(functional_status=functional_status)

    # KPIs calculated across the tenant's full inspection register
    all_tenant_qs = ReturnInspection.objects.filter(tenant=request.tenant)
    stats = {
        "total": all_tenant_qs.count(),
        "passed": all_tenant_qs.filter(status="passed").count(),
        "failed": all_tenant_qs.filter(status="failed").count(),
        "quarantined": all_tenant_qs.filter(status="quarantined").count(),
    }

    return crud_list(
        request,
        qs,
        "inventory/returns/returninspection/list.html",
        search_fields=["number", "item__sku", "item__name", "return_authorization__number"],
        filters=(),
        extra_context={
            "stats": stats,
            "status_choices": ReturnInspection.STATUS_CHOICES,
            "status": status,
            "grade_choices": ReturnInspection.GRADE_CHOICES,
            "condition_grade": condition_grade,
            "functional_choices": ReturnInspection.FUNCTIONAL_CHOICES,
            "functional_status": functional_status,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def returninspection_create(request):
    """Create a new return inspection with inline checklist items."""
    initial = {}
    # as_db_int(): ?rma=abc / ?rma=999999999999999999999 must skip the lookup, not raise
    # ValueError/driver errors from the address bar (L11).
    rma_id = as_db_int(request.GET.get("rma"))
    if rma_id:
        rma = ReturnAuthorization.objects.filter(tenant=request.tenant, pk=rma_id).first()
        if rma:
            initial["return_authorization"] = rma
            line_id = as_db_int(request.GET.get("line"))
            if line_id:
                line = rma.lines.filter(pk=line_id).first()
                if line:
                    initial["return_line"] = line
                    initial["item"] = line.item
                    initial["quantity"] = line.quantity_approved

    disp_id = as_db_int(request.GET.get("disp"))
    if disp_id:
        disp = ReturnDisposition.objects.filter(tenant=request.tenant, pk=disp_id).first()
        if disp:
            initial["return_disposition"] = disp
            if disp.return_line:
                initial["return_line"] = disp.return_line
                initial["return_authorization"] = disp.return_line.return_authorization
                initial["item"] = disp.return_line.item
            initial["quantity"] = disp.quantity
            initial["condition_grade"] = disp.condition_grade
            if disp.lot_serial:
                initial["lot_serial"] = disp.lot_serial

    if request.method == "POST":
        form = ReturnInspectionForm(request.POST, tenant=request.tenant)
        formset = ReturnInspectionChecklistFormSet(request.POST, instance=ReturnInspection(tenant=request.tenant))
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                inspection = form.save(commit=False)
                inspection.tenant = request.tenant
                inspection.save()

                formset.instance = inspection
                for ck_form in formset:
                    if ck_form.cleaned_data and not ck_form.cleaned_data.get("DELETE", False):
                        ck = ck_form.save(commit=False)
                        ck.tenant = request.tenant
                        ck.inspection = inspection
                        ck.save()

                write_audit_log(
                    request.user,
                    inspection,
                    "create",
                    {"sku": inspection.item.sku, "grade": inspection.condition_grade},
                )
                messages.success(request, f"Return Inspection {inspection.number} created successfully.")
                return redirect("inventory:returninspection_detail", pk=inspection.pk)
    else:
        form = ReturnInspectionForm(tenant=request.tenant, initial=initial)
        formset = ReturnInspectionChecklistFormSet(instance=ReturnInspection(tenant=request.tenant))

    return render(
        request,
        "inventory/returns/returninspection/form.html",
        {
            "form": form,
            "formset": formset,
            "is_edit": False,
        },
    )


@login_required
def returninspection_detail(request, pk):
    """View full inspection findings, checklist items, and live disposition routing recommendation."""
    inspection = get_object_or_404(
        ReturnInspection.objects.filter(tenant=request.tenant)
        .select_related(
            "return_authorization",
            "return_authorization__customer",
            "return_line",
            "return_disposition",
            "item",
            "item__category",
            "lot_serial",
            "inspected_by",
        ),
        pk=pk,
    )

    checklist_items = inspection.checklist_items.filter(tenant=request.tenant).order_by("id")

    # Resolve disposition routing suggestion live
    route_rule, suggested_disp, dest_loc, route_reason = resolve_disposition_routing(
        inspection.item,
        condition_grade=inspection.condition_grade,
        tenant=request.tenant,
    )

    return render(
        request,
        "inventory/returns/returninspection/detail.html",
        {
            "obj": inspection,
            "checklist_items": checklist_items,
            "route_rule": route_rule,
            "suggested_disp": suggested_disp,
            "dest_loc": dest_loc,
            "route_reason": route_reason,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def returninspection_edit(request, pk):
    """Edit return inspection details and checklist items."""
    inspection = get_object_or_404(
        ReturnInspection.objects.filter(tenant=request.tenant),
        pk=pk,
    )

    if request.method == "POST":
        form = ReturnInspectionForm(request.POST, instance=inspection, tenant=request.tenant)
        formset = ReturnInspectionChecklistFormSet(request.POST, instance=inspection)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                inspection = form.save()
                for ck_form in formset:
                    if ck_form.cleaned_data:
                        if ck_form.cleaned_data.get("DELETE", False):
                            if ck_form.instance.pk:
                                ck_form.instance.delete()
                        else:
                            ck = ck_form.save(commit=False)
                            ck.tenant = request.tenant
                            ck.inspection = inspection
                            ck.save()

                write_audit_log(
                    request.user,
                    inspection,
                    "update",
                    {"grade": inspection.condition_grade, "status": inspection.status},
                )
                messages.success(request, f"Return Inspection {inspection.number} updated successfully.")
                return redirect("inventory:returninspection_detail", pk=inspection.pk)
    else:
        form = ReturnInspectionForm(instance=inspection, tenant=request.tenant)
        formset = ReturnInspectionChecklistFormSet(instance=inspection)

    return render(
        request,
        "inventory/returns/returninspection/form.html",
        {
            "form": form,
            "formset": formset,
            "obj": inspection,
            "is_edit": True,
        },
    )


@tenant_admin_required
@require_POST
def returninspection_delete(request, pk):
    """Delete return inspection record."""
    return crud_delete(
        request,
        model=ReturnInspection,
        pk=pk,
        success_url="inventory:returninspection_list",
    )
