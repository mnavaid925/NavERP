"""Views for AssetSpaceChargeback (11.17 Tenant & Occupancy Coordination)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import JournalEntry, JournalLine
from apps.assets.forms.SpaceFacilityAsset.AssetSpaceChargebacks import AssetSpaceChargebackForm
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.models.SpaceFacilityAsset.AssetSpaceChargebacks import AssetSpaceChargeback
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.SpaceFacilityAsset._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_tenant_admin_user,
    parse_pos_int,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log


def _filtered_chargebacks_queryset(request):
    base_qs = assets_scope(AssetSpaceChargeback.objects.all(), request)
    qs = base_qs.select_related(
        "facility_space",
        "shared_building_system",
        "lease_contract",
        "charged_org_unit",
        "occupant_party",
        "currency",
        "fiscal_period",
        "journal_entry",
        "ar_invoice",
    ).defer("notes")

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(facility_space__code__icontains=q)
            | Q(charged_org_unit__name__icontains=q)
            | Q(occupant_party__name__icontains=q)
        )

    qs = apply_choice_filter(
        qs,
        request,
        "coordination_type",
        allowed_values=dict(AssetSpaceChargeback.COORDINATION_TYPE_CHOICES),
    )
    qs = apply_choice_filter(
        qs,
        request,
        "allocation_basis",
        allowed_values=dict(AssetSpaceChargeback.ALLOCATION_BASIS_CHOICES),
    )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values=dict(AssetSpaceChargeback.STATUS_CHOICES),
    )
    qs = apply_fk_filter(qs, request, "facility_space")
    qs = apply_fk_filter(qs, request, "charged_org_unit")
    return base_qs, qs, q


@login_required
def asset_space_chargeback_list(request):
    """List departmental space chargebacks, CAM/utility recoveries, & TI allocations."""
    base_qs, qs, q = _filtered_chargebacks_queryset(request)
    kpis = base_qs.aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(status="approved")),
        posted=Count("id", filter=Q(status__in=("posted_to_gl", "invoiced"))),
        net_sum=Sum("net_chargeback_amount", filter=~Q(status="disputed")),
    )

    paginator = Paginator(qs.order_by("-period_start", "-number"), PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    spaces = (
        assets_scope(AssetFacilitySpace.objects.all(), request)
        .only("id", "number", "code", "name")
        .order_by("code", "name")
    )
    org_units = (
        assets_scope(OrgUnit.objects.all(), request)
        .only("id", "code", "name")
        .order_by("name")
    )

    return render(
        request,
        "assets/spacefacilityasset/asset_space_chargeback/list.html",
        {
            "chargebacks": page_obj,
            "paginator": paginator,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "total_count": kpis["total"] or 0,
            "approved_count": kpis["approved"] or 0,
            "posted_count": kpis["posted"] or 0,
            "total_net_chargeback": kpis["net_sum"] or Decimal("0.00"),
            "coordination_type_choices": AssetSpaceChargeback.COORDINATION_TYPE_CHOICES,
            "basis_choices": AssetSpaceChargeback.ALLOCATION_BASIS_CHOICES,
            "status_choices": AssetSpaceChargeback.STATUS_CHOICES,
            "spaces": spaces,
            "org_units": org_units,
            "search_query": q,
        },
    )


@login_required
def asset_space_chargeback_export_csv(request):
    """Export filtered space chargebacks & TI allocations as formula-safe CSV."""
    _base, qs, _q = _filtered_chargebacks_queryset(request)
    rows = []
    for cb in qs.order_by("-period_start", "-number")[:5000]:
        rows.append(
            [
                cb.number,
                cb.title,
                cb.get_coordination_type_display(),
                cb.get_allocation_basis_display(),
                cb.facility_space.code if cb.facility_space else "",
                cb.charged_org_unit.name if cb.charged_org_unit else "",
                cb.occupant_party.name if cb.occupant_party else "",
                cb.period_start.isoformat() if cb.period_start else "",
                cb.period_end.isoformat() if cb.period_end else "",
                f"{cb.allocated_area_sqft:.2f}",
                f"{cb.allocation_share_pct:.2f}",
                f"{cb.base_cost_amount:.2f}",
                f"{cb.shared_cam_amount:.2f}",
                f"{cb.utility_recovery_amount:.2f}",
                f"{cb.ti_improvement_cost:.2f}",
                f"{cb.ti_allowance_offset:.2f}",
                f"{cb.net_chargeback_amount:.2f}",
                cb.currency.code if cb.currency else "",
                cb.get_status_display(),
                str(cb.journal_entry_id or ""),
            ]
        )
    return csv_export_response(
        filename="asset_space_chargebacks.csv",
        headers=[
            "Number",
            "Title",
            "Coordination Type",
            "Allocation Basis",
            "Space",
            "Charged Org Unit",
            "Occupant Party",
            "Period Start",
            "Period End",
            "Allocated SqFt",
            "Share %",
            "Base Cost",
            "Shared CAM",
            "Utility Recovery",
            "TI Cost",
            "TI Allowance",
            "Net Chargeback",
            "Currency",
            "Status",
            "Journal Entry ID",
        ],
        rows=rows,
    )


@login_required
def asset_space_chargeback_create(request):
    """Create a space chargeback / occupancy coordination entry with optional ?facility_space= prefill."""
    tenant = getattr(request, "tenant", None)
    initial = {}
    space_pk = parse_pos_int(request.GET.get("facility_space"))
    if space_pk is not None and tenant is not None:
        space = AssetFacilitySpace.objects.filter(tenant=tenant, pk=space_pk).first()
        if space is not None:
            initial["facility_space"] = space.pk

    if request.method == "POST":
        form = AssetSpaceChargebackForm(request.POST, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                chargeback = form.save(commit=False)
                chargeback.tenant = tenant
                chargeback.save()
                write_audit_log(
                    request.user,
                    chargeback,
                    "create",
                    changes={
                        "number": chargeback.number,
                        "coordination_type": chargeback.coordination_type,
                        "net_chargeback_amount": str(chargeback.net_chargeback_amount),
                    },
                    tenant=tenant,
                )
            messages.success(request, f"Space chargeback {chargeback.number} created.")
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
    else:
        form = AssetSpaceChargebackForm(initial=initial, tenant=tenant)

    return render(
        request,
        "assets/spacefacilityasset/asset_space_chargeback/form.html",
        {
            "form": form,
            "chargeback": None,
            "is_edit": False,
            "title": "New Space Chargeback / Coordination",
        },
    )


@login_required
def asset_space_chargeback_detail(request, pk):
    """View chargeback financial breakdown, TI amortization, and GL JournalEntry linkage."""
    chargeback = get_object_or_404(
        assets_scope(
            AssetSpaceChargeback.objects.select_related(
                "facility_space",
                "shared_building_system",
                "lease_contract",
                "fixed_asset",
                "charged_org_unit",
                "occupant_party",
                "currency",
                "fiscal_period",
                "expense_gl_account",
                "recovery_gl_account",
                "journal_entry",
                "ar_invoice",
                "approved_by",
            ),
            request,
        ),
        pk=pk,
    )
    can_edit = chargeback.can_edit and chargeback.journal_entry_id is None
    admin_user = is_tenant_admin_user(request.user)
    can_approve = admin_user and chargeback.status in ("draft", "pending_approval")
    can_post_gl = (
        admin_user
        and chargeback.journal_entry_id is None
        and chargeback.status == "approved"
    )
    return render(
        request,
        "assets/spacefacilityasset/asset_space_chargeback/detail.html",
        {
            "chargeback": chargeback,
            "can_edit": can_edit,
            "can_delete": can_edit,
            "can_approve": can_approve,
            "can_post_gl": can_post_gl,
        },
    )


@login_required
def asset_space_chargeback_edit(request, pk):
    """Edit a draft or disputed space chargeback."""
    chargeback = assets_object(AssetSpaceChargeback, pk, request)
    if not chargeback.can_edit or chargeback.journal_entry_id is not None:
        messages.error(
            request,
            f"Chargeback {chargeback.number} ({chargeback.get_status_display()}) cannot be edited.",
        )
        return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

    tenant = getattr(request, "tenant", None)
    if request.method == "POST":
        form = AssetSpaceChargebackForm(request.POST, instance=chargeback, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                chargeback = form.save()
                write_audit_log(
                    request.user,
                    chargeback,
                    "update",
                    changes={
                        "number": chargeback.number,
                        "net_chargeback_amount": str(chargeback.net_chargeback_amount),
                    },
                    tenant=tenant,
                )
            messages.success(request, f"Space chargeback {chargeback.number} updated.")
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
    else:
        form = AssetSpaceChargebackForm(instance=chargeback, tenant=tenant)

    return render(
        request,
        "assets/spacefacilityasset/asset_space_chargeback/form.html",
        {
            "form": form,
            "chargeback": chargeback,
            "is_edit": True,
            "title": f"Edit {chargeback.number}",
        },
    )


@login_required
@require_POST
def asset_space_chargeback_delete(request, pk):
    """Delete an unposted draft or disputed space chargeback."""
    chargeback = assets_object(AssetSpaceChargeback, pk, request)
    if not chargeback.can_edit or chargeback.journal_entry_id is not None:
        messages.error(
            request,
            f"Chargeback {chargeback.number} ({chargeback.get_status_display()}) cannot be deleted.",
        )
        return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

    number = chargeback.number
    try:
        with transaction.atomic():
            write_audit_log(
                request.user,
                chargeback,
                "delete",
                changes={"number": number, "status": chargeback.status},
                tenant=getattr(request, "tenant", None),
            )
            chargeback.delete()
    except ProtectedError:
        messages.error(request, f"Cannot delete {number} because linked records depend on it.")
        return redirect("assets:asset_space_chargeback_detail", pk=pk)

    messages.success(request, f"Space chargeback {number} deleted.")
    return redirect("assets:asset_space_chargeback_list")


@login_required
@require_POST
def asset_space_chargeback_submit_approval(request, pk):
    """Submit a draft or disputed chargeback for tenant-admin approval."""
    with transaction.atomic():
        chargeback = get_object_or_404(
            assets_scope(AssetSpaceChargeback.objects.select_for_update(), request),
            pk=pk,
        )
        if chargeback.status not in ("draft", "disputed"):
            messages.error(
                request,
                f"Only Draft or Disputed chargebacks can be submitted (currently {chargeback.get_status_display()}).",
            )
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
        chargeback.status = "pending_approval"
        chargeback.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            chargeback,
            "submit",
            changes={"number": chargeback.number, "status": "pending_approval"},
            tenant=chargeback.tenant,
        )
    messages.success(request, f"Chargeback {chargeback.number} submitted for approval.")
    return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_space_chargeback_approve(request, pk):
    """Approve a space chargeback (tenant admin only)."""
    with transaction.atomic():
        chargeback = get_object_or_404(
            assets_scope(AssetSpaceChargeback.objects.select_for_update(), request),
            pk=pk,
        )
        if chargeback.status not in ("draft", "pending_approval"):
            messages.error(
                request,
                f"Chargeback {chargeback.number} cannot be approved from {chargeback.get_status_display()}.",
            )
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
        chargeback.status = "approved"
        chargeback.approved_by = request.user
        chargeback.approved_at = timezone.now()
        chargeback.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(
            request.user,
            chargeback,
            "approve",
            changes={
                "number": chargeback.number,
                "net_chargeback_amount": str(chargeback.net_chargeback_amount),
            },
            tenant=chargeback.tenant,
        )
    messages.success(request, f"Chargeback {chargeback.number} approved.")
    return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_space_chargeback_post_gl(request, pk):
    """Post an approved space chargeback to Accounting GL as a balanced two-line JournalEntry."""
    with transaction.atomic():
        chargeback = get_object_or_404(
            assets_scope(
                AssetSpaceChargeback.objects.select_for_update().select_related(
                    "fiscal_period",
                    "expense_gl_account",
                    "recovery_gl_account",
                    "charged_org_unit",
                    "occupant_party",
                    "currency",
                ),
                request,
            ),
            pk=pk,
        )
        if chargeback.journal_entry_id is not None:
            messages.info(request, f"Chargeback {chargeback.number} is already posted to GL.")
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
        if chargeback.status != "approved":
            messages.error(
                request,
                f"Chargeback {chargeback.number} must be Approved before GL posting.",
            )
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

        amt = chargeback.net_chargeback_amount or Decimal("0.00")
        if amt <= Decimal("0.00"):
            messages.error(request, "Net chargeback amount must be greater than 0.00 before GL posting.")
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

        fiscal_period = chargeback.fiscal_period
        expense_gl = chargeback.expense_gl_account
        recovery_gl = chargeback.recovery_gl_account

        if fiscal_period is None or expense_gl is None or recovery_gl is None:
            messages.error(
                request,
                "Fiscal period, expense GL account, and recovery GL account are required for GL posting.",
            )
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

        for fk_label, rel in (
            ("Fiscal period", fiscal_period),
            ("Expense GL account", expense_gl),
            ("Recovery GL account", recovery_gl),
            ("Charged org unit", chargeback.charged_org_unit),
            ("Occupant party", chargeback.occupant_party),
        ):
            if rel is not None and getattr(rel, "tenant_id", None) != chargeback.tenant_id:
                messages.error(request, f"{fk_label} belongs to another workspace.")
                return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

        if not fiscal_period.is_open:
            messages.error(
                request,
                f"Fiscal period {fiscal_period.name} is {fiscal_period.status} (must be open).",
            )
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

        if expense_gl.pk == recovery_gl.pk:
            messages.error(request, "Expense and recovery GL accounts must be distinct.")
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)

        now = timezone.now()
        je = JournalEntry.objects.create(
            tenant=chargeback.tenant,
            entry_type="recurring",
            entry_date=chargeback.period_end,
            fiscal_period=fiscal_period,
            description=f"Space Chargeback {chargeback.number} — {chargeback.title}"[:500],
            reference=chargeback.number[:100],
            status="posted",
            created_by=request.user,
            approved_by=request.user,
            posted_at=now,
        )
        debit_line = JournalLine(
            entry=je,
            gl_account=expense_gl,
            debit=amt,
            credit=Decimal("0.00"),
            description=f"{chargeback.number} Space Cost Allocation"[:255],
            party=chargeback.occupant_party,
            org_unit=chargeback.charged_org_unit,
            currency=chargeback.currency,
        )
        debit_line.full_clean()
        debit_line.save()

        credit_line = JournalLine(
            entry=je,
            gl_account=recovery_gl,
            debit=Decimal("0.00"),
            credit=amt,
            description=f"{chargeback.number} Facility Cost Recovery"[:255],
            party=chargeback.occupant_party,
            org_unit=chargeback.charged_org_unit,
            currency=chargeback.currency,
        )
        credit_line.full_clean()
        credit_line.save()

        chargeback.journal_entry = je
        chargeback.status = "posted_to_gl"
        chargeback.save(update_fields=["journal_entry", "status", "updated_at"])
        write_audit_log(
            request.user,
            chargeback,
            "post_gl",
            changes={
                "number": chargeback.number,
                "journal_entry": str(je.number),
                "amount": str(amt),
            },
            tenant=chargeback.tenant,
        )
    messages.success(request, f"Posted {chargeback.number} to General Ledger ({je.number}).")
    return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)


@login_required
@require_POST
def asset_space_chargeback_dispute(request, pk):
    """Flag an unposted pending or approved chargeback as Disputed."""
    with transaction.atomic():
        chargeback = get_object_or_404(
            assets_scope(AssetSpaceChargeback.objects.select_for_update(), request),
            pk=pk,
        )
        if chargeback.journal_entry_id is not None:
            messages.error(request, f"Chargeback {chargeback.number} is already posted to GL and cannot be disputed.")
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
        if chargeback.status not in ("pending_approval", "approved"):
            messages.error(
                request,
                f"Chargeback {chargeback.number} cannot be disputed from {chargeback.get_status_display()}.",
            )
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
        chargeback.status = "disputed"
        chargeback.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            chargeback,
            "dispute",
            changes={"number": chargeback.number, "status": "disputed"},
            tenant=chargeback.tenant,
        )
    messages.warning(request, f"Chargeback {chargeback.number} marked Disputed.")
    return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_space_chargeback_close(request, pk):
    """Close and archive a completed or resolved space chargeback (tenant admin only)."""
    with transaction.atomic():
        chargeback = get_object_or_404(
            assets_scope(AssetSpaceChargeback.objects.select_for_update(), request),
            pk=pk,
        )
        if chargeback.status == "closed":
            messages.info(request, f"Chargeback {chargeback.number} is already closed.")
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
        if chargeback.status not in ("posted_to_gl", "invoiced", "approved", "disputed"):
            messages.error(
                request,
                f"Close is only allowed after submission/resolution (currently {chargeback.get_status_display()}).",
            )
            return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
        chargeback.status = "closed"
        chargeback.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            chargeback,
            "close",
            changes={"number": chargeback.number, "status": "closed"},
            tenant=chargeback.tenant,
        )
    messages.success(request, f"Chargeback {chargeback.number} closed.")
    return redirect("assets:asset_space_chargeback_detail", pk=chargeback.pk)
