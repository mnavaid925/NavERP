"""Sales 8.14 — Views for `DealRegistration`."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.forms.PartnerChannel.DealRegistrations import DealRegistrationForm
from apps.sales.models.PartnerChannel.DealRegistrations import (
    EXCLUSIVITY_CHOICES,
    REGISTRATION_STATUS_CHOICES,
    DealRegistration,
)


@login_required
def deal_registration_list(request):
    qs = (
        DealRegistration.objects.filter(tenant=request.tenant)
        .select_related("partner", "customer_account", "currency", "reviewed_by", "opportunity")
        .order_by("-submission_date", "-estimated_value")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(deal_name__icontains=q)
            | Q(number__icontains=q)
            | Q(partner__name__icontains=q)
            | Q(customer_account__name__icontains=q)
            | Q(partner_rep_name__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    exclusivity_status = request.GET.get("exclusivity_status", "").strip()
    if exclusivity_status:
        qs = qs.filter(exclusivity_status=exclusivity_status)

    partner_id = request.GET.get("partner", "").strip()
    if partner_id and partner_id.isdigit():
        qs = qs.filter(partner_id=int(partner_id))

    stats = qs.aggregate(
        total_count=Count("id"),
        approved_count=Count("id", filter=Q(status="approved")),
        pending_count=Count("id", filter=Q(status__in=["submitted", "under_review"])),
        conflicted_count=Count("id", filter=Q(is_conflicted=True)),
        total_pipeline=Sum("estimated_value"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    partners = (
        Party.objects.filter(tenant=request.tenant, roles__role="partner")
        .distinct()
        .order_by("name")
    )
    if not partners.exists():
        partners = Party.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "deal_registrations": page_obj.object_list,
        "status_choices": REGISTRATION_STATUS_CHOICES,
        "exclusivity_choices": EXCLUSIVITY_CHOICES,
        "partners": partners,
        "stats": stats,
        "q": q,
        "selected_status": status,
        "selected_exclusivity": exclusivity_status,
        "selected_partner": partner_id,
    }
    return render(request, "sales/partnerchannel/dealregistration/list.html", context)


@login_required
def deal_registration_detail(request, pk):
    deal_registration = get_object_or_404(
        DealRegistration.objects.filter(tenant=request.tenant).select_related(
            "partner", "customer_account", "currency", "reviewed_by", "opportunity"
        ),
        pk=pk,
    )

    conflicts = deal_registration.channel_conflicts.filter(tenant=request.tenant).order_by("-created_at")

    context = {
        "deal_registration": deal_registration,
        "conflicts": conflicts,
    }
    return render(request, "sales/partnerchannel/dealregistration/detail.html", context)


@login_required
def deal_registration_create(request):
    if request.method == "POST":
        form = DealRegistrationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            # Auto-assign 90-day protection window if approved directly
            if obj.status == "approved" and not obj.protection_start_date:
                obj.protection_start_date = timezone.localdate()
                obj.protection_end_date = obj.protection_start_date + timezone.timedelta(days=90)
                obj.exclusivity_status = "exclusive"
            if obj.status in ("approved", "rejected") and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
            obj.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="DealRegistration",
                object_id=str(obj.pk),
                details=f"Registered deal {obj.number} — {obj.deal_name}",
            )
            messages.success(request, f"Deal registration {obj.number} created successfully.")
            return redirect("sales:deal_registration_detail", pk=obj.pk)
    else:
        form = DealRegistrationForm(tenant=request.tenant)

    return render(request, "sales/partnerchannel/dealregistration/form.html", {"form": form, "is_edit": False})


@login_required
def deal_registration_edit(request, pk):
    obj = get_object_or_404(DealRegistration.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = DealRegistrationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            reg = form.save(commit=False)
            if reg.status == "approved" and not reg.protection_start_date:
                reg.protection_start_date = timezone.localdate()
                reg.protection_end_date = reg.protection_start_date + timezone.timedelta(days=90)
                reg.exclusivity_status = "exclusive"
            if reg.status in ("approved", "rejected") and not reg.reviewed_at:
                reg.reviewed_at = timezone.now()
                reg.reviewed_by = request.user
            reg.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="DealRegistration",
                object_id=str(obj.pk),
                details=f"Updated deal registration {obj.number}",
            )
            messages.success(request, f"Deal registration {obj.number} updated successfully.")
            return redirect("sales:deal_registration_detail", pk=obj.pk)
    else:
        form = DealRegistrationForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/partnerchannel/dealregistration/form.html",
        {"form": form, "deal_registration": obj, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def deal_registration_delete(request, pk):
    obj = get_object_or_404(DealRegistration.objects.filter(tenant=request.tenant), pk=pk)
    number = obj.number
    obj.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="DealRegistration",
        object_id=str(pk),
        details=f"Deleted deal registration {number}",
    )
    messages.success(request, f"Deal registration {number} deleted successfully.")
    return redirect("sales:deal_registration_list")


@require_POST
@login_required
def deal_registration_convert(request, pk):
    """Convert an approved deal registration into a live crm.Opportunity."""
    reg = get_object_or_404(DealRegistration.objects.filter(tenant=request.tenant), pk=pk)

    if reg.opportunity:
        messages.info(request, f"Deal registration {reg.number} was already converted to opportunity {reg.opportunity.number}.")
        return redirect("sales:deal_registration_detail", pk=reg.pk)

    if reg.status != "approved":
        messages.error(request, f"Deal registration {reg.number} cannot be converted because it is not approved.")
        return redirect("sales:deal_registration_detail", pk=reg.pk)

    with transaction.atomic():
        opp = Opportunity.objects.create(
            tenant=request.tenant,
            account=reg.customer_account,
            title=reg.deal_name,
            amount=reg.estimated_value,
            expected_close_date=reg.expected_close_date,
            stage="Proposal/Price Quote",
            probability=60,
            lead_source="Partner",
            description=f"Converted from Partner Deal Registration {reg.number} (Partner: {reg.partner.name})",
        )
        reg.opportunity = opp
        reg.status = "converted"
        reg.save(update_fields=["opportunity", "status", "updated_at"])

        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="convert",
            model_name="DealRegistration",
            object_id=str(reg.pk),
            details=f"Converted deal registration {reg.number} to Opportunity {opp.number}",
        )

    messages.success(request, f"Deal registration {reg.number} successfully converted to Opportunity {opp.number}.")
    return redirect("sales:deal_registration_detail", pk=reg.pk)
