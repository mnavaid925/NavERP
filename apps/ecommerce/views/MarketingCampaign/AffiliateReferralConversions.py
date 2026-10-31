from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MarketingCampaign.AffiliateReferralConversions import AffiliateReferralConversionForm
from apps.ecommerce.models.MarketingCampaign.AffiliateReferralConversions import AffiliateReferralConversion
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def affiliatereferralconversion_list(request):
    qs = ecommerce_scope(AffiliateReferralConversion.objects.all(), request).select_related(
        "affiliate", "order", "referred_customer"
    )

    search_query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    attribution_type = request.GET.get("attribution_type", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(affiliate__name__icontains=search_query)
            | Q(order__number__icontains=search_query)
            | Q(payout_reference__icontains=search_query)
        )

    if status:
        qs = qs.filter(status=status)

    if attribution_type:
        qs = qs.filter(attribution_type=attribution_type)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "conversions": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AffiliateReferralConversion.STATUS_CHOICES,
        "attribution_type_choices": AffiliateReferralConversion.ATTRIBUTION_TYPE_CHOICES,
        "selected_status": status,
        "selected_attribution": attribution_type,
        "search_query": search_query,
        "q": search_query,
    }
    return render(request, "ecommerce/marketing_campaign/conversion/list.html", context)


@login_required
def affiliatereferralconversion_detail(request, pk):
    conversion = ecommerce_object(
        request,
        AffiliateReferralConversion,
        pk,
        select_related=("affiliate", "order", "referred_customer__user"),
    )
    context = {
        "conversion": conversion,
    }
    return render(request, "ecommerce/marketing_campaign/conversion/detail.html", context)


@login_required
@tenant_admin_required
def affiliatereferralconversion_create(request):
    if request.method == "POST":
        form = AffiliateReferralConversionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                conversion = form.save(commit=False)
                conversion.tenant = request.tenant
                conversion.save()
                # Update partner aggregates - do not credit commission until approved
                affiliate = conversion.affiliate
                affiliate.total_orders_referred += 1
                if conversion.status == "approved":
                    affiliate.total_revenue_generated += conversion.order_amount
                    affiliate.total_commission_earned += conversion.commission_amount
                affiliate.save()

                write_audit_log(
                    request.user,
                    conversion,
                    "create",
                    changes={"number": conversion.number, "affiliate": affiliate.name},
                    tenant=request.tenant,
                )
            messages.success(request, f"Referral conversion '{conversion.number}' created successfully.")
            return redirect("ecommerce:affiliatereferralconversion_detail", pk=conversion.pk)
    else:
        form = AffiliateReferralConversionForm(tenant=request.tenant)

    context = {
        "form": form,
    }
    return render(request, "ecommerce/marketing_campaign/conversion/form.html", context)


@login_required
@tenant_admin_required
def affiliatereferralconversion_edit(request, pk):
    conversion = ecommerce_object(request, AffiliateReferralConversion, pk)
    if request.method == "POST":
        form = AffiliateReferralConversionForm(request.POST, instance=conversion, tenant=request.tenant)
        if form.is_valid():
            conversion = form.save()
            write_audit_log(
                request.user,
                conversion,
                "update",
                changes={"number": conversion.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Referral conversion '{conversion.number}' updated successfully.")
            return redirect("ecommerce:affiliatereferralconversion_detail", pk=conversion.pk)
    else:
        form = AffiliateReferralConversionForm(instance=conversion, tenant=request.tenant)

    context = {
        "form": form,
        "conversion": conversion,
    }
    return render(request, "ecommerce/marketing_campaign/conversion/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def affiliatereferralconversion_delete(request, pk):
    with transaction.atomic():
        conversion = ecommerce_object(request, AffiliateReferralConversion, pk)
        number = conversion.number
        affiliate = conversion.affiliate
        if conversion.status in ("approved", "paid"):
            affiliate.total_commission_earned = max(
                Decimal("0.00"), affiliate.total_commission_earned - conversion.commission_amount
            )
            affiliate.total_revenue_generated = max(
                Decimal("0.00"), affiliate.total_revenue_generated - conversion.order_amount
            )
            affiliate.save()
        conversion.delete()
        write_audit_log(
            request.user,
            conversion,
            "delete",
            changes={"number": number},
            tenant=request.tenant,
        )
    messages.success(request, f"Referral conversion '{number}' was deleted.")
    return redirect("ecommerce:affiliatereferralconversion_list")


@login_required
@tenant_admin_required
@require_POST
def affiliatereferralconversion_approve(request, pk):
    with transaction.atomic():
        conversion = get_object_or_404(
            AffiliateReferralConversion.objects.select_for_update(), pk=pk, tenant=request.tenant
        )
        if conversion.status == "approved":
            messages.info(request, f"Conversion '{conversion.number}' is already approved.")
            return redirect("ecommerce:affiliatereferralconversion_detail", pk=conversion.pk)
        if conversion.status != "pending_review":
            messages.warning(
                request,
                f"Conversion '{conversion.number}' cannot be approved from status '{conversion.get_status_display()}'.",
            )
            return redirect("ecommerce:affiliatereferralconversion_detail", pk=conversion.pk)

        conversion.status = "approved"
        conversion.save()

        affiliate = conversion.affiliate
        affiliate.total_revenue_generated += conversion.order_amount
        affiliate.total_commission_earned += conversion.commission_amount
        affiliate.save()

        write_audit_log(
            request.user,
            conversion,
            "approve",
            changes={"number": conversion.number, "affiliate": affiliate.name},
            tenant=request.tenant,
        )
    messages.success(request, f"Conversion '{conversion.number}' approved for payout.")
    return redirect("ecommerce:affiliatereferralconversion_detail", pk=conversion.pk)


@login_required
@tenant_admin_required
@require_POST
def affiliatereferralconversion_void(request, pk):
    with transaction.atomic():
        conversion = get_object_or_404(
            AffiliateReferralConversion.objects.select_for_update(), pk=pk, tenant=request.tenant
        )
        if conversion.status == "voided_refund":
            messages.info(request, f"Conversion '{conversion.number}' is already voided.")
            return redirect("ecommerce:affiliatereferralconversion_detail", pk=conversion.pk)

        was_approved = conversion.status in ("approved", "paid")
        conversion.status = "voided_refund"
        conversion.notes += f"\nVoided on {timezone.now().strftime('%Y-%m-%d %H:%M')} due to refund/cancellation."
        conversion.save()

        if was_approved:
            affiliate = conversion.affiliate
            affiliate.total_commission_earned = max(
                Decimal("0.00"), affiliate.total_commission_earned - conversion.commission_amount
            )
            affiliate.total_revenue_generated = max(
                Decimal("0.00"), affiliate.total_revenue_generated - conversion.order_amount
            )
            affiliate.save()

        write_audit_log(
            request.user,
            conversion,
            "void",
            changes={"number": conversion.number},
            tenant=request.tenant,
        )
    messages.warning(request, f"Conversion '{conversion.number}' voided due to clawback.")
    return redirect("ecommerce:affiliatereferralconversion_detail", pk=conversion.pk)
