from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetWarrantyInsurance.AssetWarrantyClaims import AssetWarrantyClaimForm
from apps.assets.models.AssetWarrantyInsurance.AssetWarranties import AssetWarranty
from apps.assets.models.AssetWarrantyInsurance.AssetWarrantyClaims import AssetWarrantyClaim
from apps.assets.views._common import assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_warranty_claim_list(request):
    qs = assets_scope(
        AssetWarrantyClaim.objects.select_related(
            "warranty",
            "fixed_asset",
            "operational_asset",
            "currency",
            "filed_by",
        ).defer("defect_description", "settlement_notes"),
        request,
    )

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(warrantor_claim_reference__icontains=q)
            | Q(rma_tracking_number__icontains=q)
            | Q(warranty__number__icontains=q)
            | Q(warranty__title__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(claim_status=status_filter)

    res_filter = request.GET.get("resolution_type", "").strip()
    if res_filter:
        qs = qs.filter(resolution_type=res_filter)

    return_filter = request.GET.get("part_return_status", "").strip()
    if return_filter:
        qs = qs.filter(part_return_status=return_filter)

    war_filter = request.GET.get("warranty", "").strip()
    if war_filter and war_filter.isdigit():
        qs = qs.filter(warranty_id=int(war_filter))

    # Aggregates / Stats
    tenant_base = AssetWarrantyClaim.objects.filter(tenant=request.tenant)
    stats = tenant_base.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(claim_status__in=["draft", "submitted", "under_review"])),
        settled=Count("id", filter=Q(claim_status="settled_closed")),
        recovered=Sum("net_recovery_amount", filter=Q(claim_status="settled_closed")),
    )
    total_claims = stats["total"]
    pending_claims = stats["pending"]
    settled_claims = stats["settled"]
    total_net_recovered = stats["recovered"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "warranty_claims": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "claim_status_choices": AssetWarrantyClaim.CLAIM_STATUS_CHOICES,
        "resolution_type_choices": AssetWarrantyClaim.RESOLUTION_TYPE_CHOICES,
        "part_return_status_choices": AssetWarrantyClaim.PART_RETURN_STATUS_CHOICES,
        "total_claims": total_claims,
        "pending_claims": pending_claims,
        "settled_claims": settled_claims,
        "total_net_recovered": total_net_recovered,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarrantyclaim/list.html", context)


@login_required
def asset_warranty_claim_detail(request, pk):
    claim = get_object_or_404(
        AssetWarrantyClaim.objects.select_related(
            "warranty",
            "fixed_asset",
            "operational_asset",
            "maintenance_request",
            "currency",
            "filed_by",
            "approved_by",
            "supporting_document",
        ),
        pk=pk,
        tenant=request.tenant,
    )
    context = {
        "claim": claim,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarrantyclaim/detail.html", context)


@login_required
def asset_warranty_claim_create(request):
    initial = {}
    warranty_pk = request.GET.get("warranty")
    if warranty_pk and warranty_pk.isdigit():
        war = AssetWarranty.objects.filter(pk=int(warranty_pk), tenant=request.tenant).first()
        if war:
            initial["warranty"] = war
            initial["fixed_asset"] = war.fixed_asset
            initial["operational_asset"] = war.operational_asset
            initial["currency"] = war.currency
            initial["deductible_applied"] = war.deductible_amount

    if request.method == "POST":
        form = AssetWarrantyClaimForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                claim = form.save(commit=False)
                claim.tenant = request.tenant
                claim.filed_by = request.user
                claim.save()
                write_audit_log(
                    user=request.user,
                    obj=claim,
                    action="create",
                    changes={"details": f"Created warranty claim {claim.number} for warranty {claim.warranty.number}"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Warranty claim {claim.number} created.")
                return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)
    else:
        form = AssetWarrantyClaimForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "claim": None,
        "is_edit": False,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarrantyclaim/form.html", context)


@login_required
def asset_warranty_claim_edit(request, pk):
    claim = get_object_or_404(AssetWarrantyClaim, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = AssetWarrantyClaimForm(request.POST, instance=claim, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                claim = form.save()
                write_audit_log(
                    user=request.user,
                    obj=claim,
                    action="update",
                    changes={"details": f"Updated warranty claim {claim.number}"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Warranty claim {claim.number} updated.")
                return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)
    else:
        form = AssetWarrantyClaimForm(instance=claim, tenant=request.tenant)

    context = {
        "form": form,
        "claim": claim,
        "is_edit": True,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarrantyclaim/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def asset_warranty_claim_delete(request, pk):
    claim = get_object_or_404(AssetWarrantyClaim, pk=pk, tenant=request.tenant)
    number = claim.number
    with transaction.atomic():
        write_audit_log(
            user=request.user,
            obj=claim,
            action="delete",
            changes={"details": f"Deleted warranty claim {number}"},
            tenant=request.tenant,
        )
        claim.delete()
        messages.success(request, f"Warranty claim {number} deleted.")
    return redirect("assets:asset_warranty_claim_list")


@login_required
@require_POST
def asset_warranty_claim_submit(request, pk):
    claim = get_object_or_404(AssetWarrantyClaim, pk=pk, tenant=request.tenant)
    if claim.claim_status != "draft":
        messages.warning(request, f"Claim {claim.number} is already {claim.get_claim_status_display()}.")
        return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)

    with transaction.atomic():
        claim.claim_status = "submitted"
        claim.submission_date = timezone.now().date()
        # Mark linked warranty as claimed
        if claim.warranty.status == "active":
            claim.warranty.status = "claimed"
            claim.warranty.save(update_fields=["status", "updated_at"])
        claim.save(update_fields=["claim_status", "submission_date", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=claim,
            action="submit",
            changes={"details": f"Submitted warranty claim {claim.number} to warrantor"},
            tenant=request.tenant,
        )
        messages.success(request, f"Warranty claim {claim.number} submitted to warrantor.")
    return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)


@login_required
@require_POST
def asset_warranty_claim_review(request, pk):
    claim = get_object_or_404(AssetWarrantyClaim, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        claim.claim_status = "under_review"
        claim.save(update_fields=["claim_status", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=claim,
            action="review",
            changes={"details": f"Claim {claim.number} marked under technical review"},
            tenant=request.tenant,
        )
        messages.info(request, f"Claim {claim.number} is now under review.")
    return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)


@login_required
@require_POST
def asset_warranty_claim_settle(request, pk):
    claim = get_object_or_404(AssetWarrantyClaim, pk=pk, tenant=request.tenant)
    raw_amount = request.POST.get("approved_amount")
    try:
        if raw_amount is None or str(raw_amount).strip() == "":
            approved_amt = claim.claimed_amount
        else:
            approved_amt = Decimal(str(raw_amount).strip())
            if not approved_amt.is_finite() or approved_amt < Decimal("0.00") or approved_amt > Decimal("9999999999.99"):
                messages.error(request, "Invalid approved amount. Must be a finite non-negative number up to 9,999,999,999.99.")
                return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, "Invalid numeric value for approved amount.")
        return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)

    res_type = request.POST.get("resolution_type", "cash_reimbursement")
    settlement_notes = request.POST.get("settlement_notes", "").strip()

    with transaction.atomic():
        claim.approved_amount = approved_amt
        claim.net_recovery_amount = max(Decimal("0.00"), approved_amt - claim.deductible_applied)
        claim.resolution_type = res_type
        claim.claim_status = "settled_closed"
        claim.settlement_date = timezone.now().date()
        claim.approved_by = request.user
        if settlement_notes:
            claim.settlement_notes = settlement_notes
        claim.save()

        # Check if warranty can be restored to active if no other pending claims
        other_open = claim.warranty.claims.filter(
            claim_status__in=["draft", "submitted", "under_review"]
        ).exclude(pk=claim.pk).exists()
        if not other_open and claim.warranty.status == "claimed":
            claim.warranty.status = "active"
            claim.warranty.save(update_fields=["status", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=claim,
            action="settle",
            changes={"details": f"Settled warranty claim {claim.number} for net recovery {claim.net_recovery_amount}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Warranty claim {claim.number} settled successfully.")
    return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)


@login_required
@require_POST
def asset_warranty_claim_reject(request, pk):
    claim = get_object_or_404(AssetWarrantyClaim, pk=pk, tenant=request.tenant)
    notes = request.POST.get("settlement_notes", "").strip()

    with transaction.atomic():
        claim.claim_status = "rejected"
        claim.resolution_type = "rejected_uncovered"
        claim.settlement_date = timezone.now().date()
        if notes:
            claim.settlement_notes = notes
        claim.save()

        # Check warranty status
        other_open = claim.warranty.claims.filter(
            claim_status__in=["draft", "submitted", "under_review"]
        ).exclude(pk=claim.pk).exists()
        if not other_open and claim.warranty.status == "claimed":
            claim.warranty.status = "active"
            claim.warranty.save(update_fields=["status", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=claim,
            action="reject",
            changes={"details": f"Warranty claim {claim.number} rejected by OEM"},
            tenant=request.tenant,
        )
        messages.warning(request, f"Warranty claim {claim.number} recorded as rejected.")
    return redirect("assets:asset_warranty_claim_detail", pk=claim.pk)
