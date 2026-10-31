from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MarketingCampaign.AffiliatePartners import AffiliatePartnerForm
from apps.ecommerce.models.MarketingCampaign.AffiliatePartners import AffiliatePartner
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def affiliatepartner_list(request):
    qs = ecommerce_scope(AffiliatePartner.objects.all(), request).select_related(
        "party", "customer_profile"
    )

    search_query = request.GET.get("q", "").strip()
    partner_type = request.GET.get("partner_type", "").strip()
    status = request.GET.get("status", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(referral_code__icontains=search_query)
            | Q(referral_link_slug__icontains=search_query)
            | Q(party__name__icontains=search_query)
        )

    if partner_type:
        qs = qs.filter(partner_type=partner_type)

    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "partners": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "partner_type_choices": AffiliatePartner.PARTNER_TYPE_CHOICES,
        "status_choices": AffiliatePartner.STATUS_CHOICES,
        "commission_type_choices": AffiliatePartner.COMMISSION_TYPE_CHOICES,
        "selected_type": partner_type,
        "selected_status": status,
        "search_query": search_query,
        "q": search_query,
    }
    return render(request, "ecommerce/marketing_campaign/affiliate/list.html", context)


@login_required
def affiliatepartner_detail(request, pk):
    partner = ecommerce_object(
        request,
        AffiliatePartner,
        pk,
        select_related=("party", "customer_profile"),
    )
    conversions = partner.conversions.select_related("order", "referred_customer")[:20]
    context = {
        "partner": partner,
        "conversions": conversions,
    }
    return render(request, "ecommerce/marketing_campaign/affiliate/detail.html", context)


@login_required
@tenant_admin_required
def affiliatepartner_create(request):
    if request.method == "POST":
        form = AffiliatePartnerForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            partner = form.save(commit=False)
            partner.tenant = request.tenant
            partner.save()
            write_audit_log(
                request.user,
                partner,
                "create",
                changes={"number": partner.number, "name": partner.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Affiliate partner '{partner.name}' created successfully.")
            return redirect("ecommerce:affiliatepartner_detail", pk=partner.pk)
    else:
        form = AffiliatePartnerForm(tenant=request.tenant)

    context = {
        "form": form,
    }
    return render(request, "ecommerce/marketing_campaign/affiliate/form.html", context)


@login_required
@tenant_admin_required
def affiliatepartner_edit(request, pk):
    partner = ecommerce_object(request, AffiliatePartner, pk)
    if request.method == "POST":
        form = AffiliatePartnerForm(request.POST, instance=partner, tenant=request.tenant)
        if form.is_valid():
            partner = form.save()
            write_audit_log(
                request.user,
                partner,
                "update",
                changes={"number": partner.number, "name": partner.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Affiliate partner '{partner.name}' updated successfully.")
            return redirect("ecommerce:affiliatepartner_detail", pk=partner.pk)
    else:
        form = AffiliatePartnerForm(instance=partner, tenant=request.tenant)

    context = {
        "form": form,
        "partner": partner,
    }
    return render(request, "ecommerce/marketing_campaign/affiliate/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def affiliatepartner_delete(request, pk):
    partner = ecommerce_object(request, AffiliatePartner, pk)
    name = partner.name
    number = partner.number
    partner.delete()
    write_audit_log(
        request.user,
        partner,
        "delete",
        changes={"number": number, "name": name},
        tenant=request.tenant,
    )
    messages.success(request, f"Affiliate partner '{name}' was deleted.")
    return redirect("ecommerce:affiliatepartner_list")


@login_required
@tenant_admin_required
@require_POST
def affiliatepartner_approve(request, pk):
    with transaction.atomic():
        partner = get_object_or_404(
            AffiliatePartner.objects.select_for_update(), pk=pk, tenant=request.tenant
        )
        if partner.status == "active":
            messages.info(request, f"Affiliate partner '{partner.name}' is already active.")
            return redirect("ecommerce:affiliatepartner_detail", pk=partner.pk)
        if partner.status != "pending_approval":
            messages.warning(
                request,
                f"Affiliate partner '{partner.name}' cannot be approved from status '{partner.get_status_display()}'.",
            )
            return redirect("ecommerce:affiliatepartner_detail", pk=partner.pk)

        partner.status = "active"
        partner.save()
        write_audit_log(
            request.user,
            partner,
            "approve",
            changes={"number": partner.number, "name": partner.name},
            tenant=request.tenant,
        )
    messages.success(request, f"Affiliate partner '{partner.name}' has been approved and activated.")
    return redirect("ecommerce:affiliatepartner_detail", pk=partner.pk)
