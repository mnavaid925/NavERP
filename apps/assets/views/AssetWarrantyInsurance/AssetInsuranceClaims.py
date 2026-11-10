from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetWarrantyInsurance.AssetInsuranceClaims import AssetInsuranceClaimForm
from apps.assets.models.AssetWarrantyInsurance.AssetInsuranceClaims import AssetInsuranceClaim
from apps.assets.models.AssetWarrantyInsurance.AssetInsurancePolicies import AssetInsurancePolicy
from apps.assets.views._common import assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_insurance_claim_list(request):
    qs = assets_scope(
        AssetInsuranceClaim.objects.select_related(
            "policy",
            "fixed_asset",
            "operational_asset",
            "currency",
            "claims_officer",
            "adjuster_party",
        ).defer("incident_description", "settlement_notes"),
        request,
    )

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(carrier_claim_number__icontains=q)
            | Q(incident_location__icontains=q)
            | Q(policy__number__icontains=q)
            | Q(policy__policy_number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(claim_status=status_filter)

    peril_filter = request.GET.get("peril_type", "").strip()
    if peril_filter:
        qs = qs.filter(peril_type=peril_filter)

    method_filter = request.GET.get("settlement_method", "").strip()
    if method_filter:
        qs = qs.filter(settlement_method=method_filter)

    pol_filter = request.GET.get("policy", "").strip()
    if pol_filter and pol_filter.isdigit():
        qs = qs.filter(policy_id=int(pol_filter))

    # Aggregates / Stats
    tenant_base = AssetInsuranceClaim.objects.filter(tenant=request.tenant)
    stats = tenant_base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(claim_status__in=["incident_reported", "adjuster_assigned", "proof_of_loss_filed", "under_carrier_review", "approved_pending_payout"])),
        settled=Count("id", filter=Q(claim_status="settled_paid")),
        payout=Sum("settlement_payout_amount", filter=Q(claim_status="settled_paid")),
    )
    total_claims = stats["total"]
    active_claims = stats["active"]
    settled_claims = stats["settled"]
    total_payout_recovered = stats["payout"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "insurance_claims": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "claim_status_choices": AssetInsuranceClaim.CLAIM_STATUS_CHOICES,
        "peril_type_choices": AssetInsuranceClaim.PERIL_TYPE_CHOICES,
        "settlement_method_choices": AssetInsuranceClaim.SETTLEMENT_METHOD_CHOICES,
        "total_claims": total_claims,
        "active_claims": active_claims,
        "settled_claims": settled_claims,
        "total_payout_recovered": total_payout_recovered,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsuranceclaim/list.html", context)


@login_required
def asset_insurance_claim_detail(request, pk):
    claim = get_object_or_404(
        AssetInsuranceClaim.objects.select_related(
            "policy",
            "fixed_asset",
            "operational_asset",
            "incident_report",
            "adjuster_party",
            "currency",
            "claims_officer",
            "proof_of_loss_document",
        ),
        pk=pk,
        tenant=request.tenant,
    )
    context = {
        "claim": claim,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsuranceclaim/detail.html", context)


@login_required
def asset_insurance_claim_create(request):
    initial = {}
    policy_pk = request.GET.get("policy")
    if policy_pk and policy_pk.isdigit():
        pol = AssetInsurancePolicy.objects.filter(pk=int(policy_pk), tenant=request.tenant).first()
        if pol:
            initial["policy"] = pol
            initial["fixed_asset"] = pol.fixed_asset
            initial["operational_asset"] = pol.operational_asset
            initial["currency"] = pol.currency
            initial["deductible_applied"] = pol.deductible_retention

    if request.method == "POST":
        form = AssetInsuranceClaimForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                claim = form.save(commit=False)
                claim.tenant = request.tenant
                if not claim.claims_officer:
                    claim.claims_officer = request.user
                claim.save()
                write_audit_log(
                    user=request.user,
                    obj=claim,
                    action="create",
                    changes={"details": f"Created insurance claim {claim.number} under policy {claim.policy.policy_number}"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Insurance claim {claim.number} filed successfully.")
                return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)
    else:
        form = AssetInsuranceClaimForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "claim": None,
        "is_edit": False,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsuranceclaim/form.html", context)


@login_required
def asset_insurance_claim_edit(request, pk):
    claim = get_object_or_404(AssetInsuranceClaim, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = AssetInsuranceClaimForm(request.POST, instance=claim, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                claim = form.save()
                write_audit_log(
                    user=request.user,
                    obj=claim,
                    action="update",
                    changes={"details": f"Updated insurance claim {claim.number}"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Insurance claim {claim.number} updated.")
                return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)
    else:
        form = AssetInsuranceClaimForm(instance=claim, tenant=request.tenant)

    context = {
        "form": form,
        "claim": claim,
        "is_edit": True,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsuranceclaim/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def asset_insurance_claim_delete(request, pk):
    claim = get_object_or_404(AssetInsuranceClaim, pk=pk, tenant=request.tenant)
    number = claim.number
    with transaction.atomic():
        write_audit_log(
            user=request.user,
            obj=claim,
            action="delete",
            changes={"details": f"Deleted insurance claim {number}"},
            tenant=request.tenant,
        )
        claim.delete()
        messages.success(request, f"Insurance claim {number} deleted.")
    return redirect("assets:asset_insurance_claim_list")


@login_required
@require_POST
def asset_insurance_claim_assign_adjuster(request, pk):
    claim = get_object_or_404(AssetInsuranceClaim, pk=pk, tenant=request.tenant)
    adjuster_name = request.POST.get("adjuster_name", "").strip()
    carrier_ref = request.POST.get("carrier_claim_number", "").strip()

    with transaction.atomic():
        claim.claim_status = "adjuster_assigned"
        if adjuster_name:
            claim.adjuster_name = adjuster_name
        if carrier_ref:
            claim.carrier_claim_number = carrier_ref
        if not claim.date_reported_to_carrier:
            claim.date_reported_to_carrier = timezone.now().date()
        claim.save()
        write_audit_log(
            user=request.user,
            obj=claim,
            action="adjuster",
            changes={"details": f"Assigned adjuster to claim {claim.number}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Claim {claim.number} updated: Adjuster assigned.")
    return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)


@login_required
@require_POST
def asset_insurance_claim_file_proof(request, pk):
    claim = get_object_or_404(AssetInsuranceClaim, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        claim.claim_status = "proof_of_loss_filed"
        claim.proof_of_loss_date = timezone.now().date()
        claim.save(update_fields=["claim_status", "proof_of_loss_date", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=claim,
            action="file_proof",
            changes={"details": f"Filed sworn proof of loss for claim {claim.number}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Proof of loss submitted for claim {claim.number}.")
    return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)


@login_required
@require_POST
def asset_insurance_claim_settle(request, pk):
    claim = get_object_or_404(AssetInsuranceClaim, pk=pk, tenant=request.tenant)
    raw_payout = request.POST.get("settlement_payout_amount", "0.00")
    try:
        payout_amt = Decimal(str(raw_payout).strip()) if raw_payout and str(raw_payout).strip() else Decimal("0.00")
        if not payout_amt.is_finite() or payout_amt < Decimal("0.00") or payout_amt > Decimal("999999999999.99"):
            messages.error(request, "Invalid settlement payout amount. Must be a finite non-negative number up to 999,999,999,999.99.")
            return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, "Invalid numeric value for settlement payout amount.")
        return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)

    raw_salvage = request.POST.get("salvage_recovery_amount", "0.00")
    try:
        salvage_amt = Decimal(str(raw_salvage).strip()) if raw_salvage and str(raw_salvage).strip() else Decimal("0.00")
        if not salvage_amt.is_finite() or salvage_amt < Decimal("0.00") or salvage_amt > Decimal("9999999999.99"):
            messages.error(request, "Invalid salvage recovery amount. Must be a finite non-negative number up to 9,999,999,999.99.")
            return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, "Invalid numeric value for salvage recovery amount.")
        return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)

    settlement_method = request.POST.get("settlement_method", "direct_indemnity_check")
    notes = request.POST.get("settlement_notes", "").strip()

    with transaction.atomic():
        claim.settlement_payout_amount = payout_amt
        claim.salvage_recovery_amount = salvage_amt
        claim.settlement_method = settlement_method
        claim.claim_status = "settled_paid"
        claim.settlement_date = timezone.now().date()
        if notes:
            claim.settlement_notes = notes
        claim.save()
        write_audit_log(
            user=request.user,
            obj=claim,
            action="settle",
            changes={"details": f"Settled insurance claim {claim.number} with payout {payout_amt}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Insurance claim {claim.number} settled and marked paid.")
    return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)


@login_required
@require_POST
def asset_insurance_claim_deny(request, pk):
    claim = get_object_or_404(AssetInsuranceClaim, pk=pk, tenant=request.tenant)
    notes = request.POST.get("settlement_notes", "").strip()

    with transaction.atomic():
        claim.claim_status = "denied_disputed"
        claim.settlement_method = "none_denied"
        claim.settlement_date = timezone.now().date()
        if notes:
            claim.settlement_notes = notes
        claim.save()
        write_audit_log(
            user=request.user,
            obj=claim,
            action="deny",
            changes={"details": f"Insurance claim {claim.number} recorded as denied"},
            tenant=request.tenant,
        )
        messages.warning(request, f"Insurance claim {claim.number} recorded as denied / under dispute.")
    return redirect("assets:asset_insurance_claim_detail", pk=claim.pk)
