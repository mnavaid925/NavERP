from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetWarrantyInsurance.AssetWarranties import AssetWarrantyForm
from apps.assets.models import AssetCategory
from apps.assets.models.AssetWarrantyInsurance.AssetWarranties import AssetWarranty
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_warranty_list(request):
    qs = assets_scope(
        AssetWarranty.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "warrantor_party",
            "currency",
        ).defer("terms_and_conditions"),
        request,
    )

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(warranty_certificate_number__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__tag_code__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(warrantor_party__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    warranty_type_filter = request.GET.get("warranty_type", "").strip()
    if warranty_type_filter:
        qs = qs.filter(warranty_type=warranty_type_filter)

    coverage_scope_filter = request.GET.get("coverage_scope", "").strip()
    if coverage_scope_filter:
        qs = qs.filter(coverage_scope=coverage_scope_filter)

    cat_filter = request.GET.get("category", "").strip()
    if cat_filter and cat_filter.isdigit():
        qs = qs.filter(asset_category_id=int(cat_filter))

    # Aggregates / Stats over tenant base
    tenant_base = AssetWarranty.objects.filter(tenant=request.tenant)
    today = timezone.now().date()
    sixty_days_hence = today + timedelta(days=60)

    stats = tenant_base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        expiring=Count("id", filter=Q(status="expiring_soon") | Q(status="active", end_date__lte=sixty_days_hence, end_date__gte=today)),
        claimed=Count("id", filter=Q(status="claimed")),
    )
    total_warranties = stats["total"]
    active_warranties = stats["active"]
    expiring_soon_count = stats["expiring"]
    claimed_count = stats["claimed"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "warranties": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetWarranty.STATUS_CHOICES,
        "warranty_type_choices": AssetWarranty.WARRANTY_TYPE_CHOICES,
        "coverage_scope_choices": AssetWarranty.COVERAGE_SCOPE_CHOICES,
        "category_list": AssetCategory.objects.filter(tenant=request.tenant),
        "total_warranties": total_warranties,
        "active_warranties": active_warranties,
        "expiring_soon_count": expiring_soon_count,
        "claimed_count": claimed_count,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarranty/list.html", context)


@login_required
def asset_warranty_detail(request, pk):
    warranty = get_object_or_404(
        AssetWarranty.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "warrantor_party",
            "currency",
            "contract_document",
            "service_contract",
            "registered_by",
        ),
        pk=pk,
        tenant=request.tenant,
    )
    claims = warranty.claims.select_related("currency", "filed_by").order_by("-incident_date")
    context = {
        "warranty": warranty,
        "claims": claims,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarranty/detail.html", context)


@login_required
def asset_warranty_create(request):
    if request.method == "POST":
        form = AssetWarrantyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                warranty = form.save(commit=False)
                warranty.tenant = request.tenant
                warranty.registered_by = request.user
                warranty.save()
                write_audit_log(
                    tenant=request.tenant,
                    user=request.user,
                    action="asset_warranty.create",
                    model_name="AssetWarranty",
                    object_id=warranty.pk,
                    details=f"Created warranty {warranty.number} - {warranty.title}",
                )
                messages.success(request, f"Warranty {warranty.number} successfully registered.")
                return redirect("assets:asset_warranty_detail", pk=warranty.pk)
    else:
        form = AssetWarrantyForm(tenant=request.tenant)

    context = {
        "form": form,
        "warranty": None,
        "is_edit": False,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarranty/form.html", context)


@login_required
def asset_warranty_edit(request, pk):
    warranty = get_object_or_404(AssetWarranty, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = AssetWarrantyForm(request.POST, instance=warranty, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                warranty = form.save()
                write_audit_log(
                    tenant=request.tenant,
                    user=request.user,
                    action="asset_warranty.edit",
                    model_name="AssetWarranty",
                    object_id=warranty.pk,
                    details=f"Updated warranty {warranty.number} - {warranty.title}",
                )
                messages.success(request, f"Warranty {warranty.number} updated.")
                return redirect("assets:asset_warranty_detail", pk=warranty.pk)
    else:
        form = AssetWarrantyForm(instance=warranty, tenant=request.tenant)

    context = {
        "form": form,
        "warranty": warranty,
        "is_edit": True,
    }
    return render(request, "assets/assetwarrantyinsurance/assetwarranty/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def asset_warranty_delete(request, pk):
    warranty = get_object_or_404(AssetWarranty, pk=pk, tenant=request.tenant)
    number = warranty.number
    with transaction.atomic():
        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="asset_warranty.delete",
            model_name="AssetWarranty",
            object_id=warranty.pk,
            details=f"Deleted warranty {number}",
        )
        warranty.delete()
        messages.success(request, f"Warranty {number} deleted.")
    return redirect("assets:asset_warranty_list")


@login_required
@require_POST
def asset_warranty_activate(request, pk):
    warranty = get_object_or_404(AssetWarranty, pk=pk, tenant=request.tenant)
    if warranty.status != "draft":
        messages.warning(request, f"Warranty {warranty.number} is already {warranty.get_status_display()}.")
        return redirect("assets:asset_warranty_detail", pk=warranty.pk)

    with transaction.atomic():
        warranty.status = "active"
        warranty.save(update_fields=["status", "updated_at"])
        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="asset_warranty.activate",
            model_name="AssetWarranty",
            object_id=warranty.pk,
            details=f"Activated warranty {warranty.number}",
        )
        messages.success(request, f"Warranty {warranty.number} is now active.")
    return redirect("assets:asset_warranty_detail", pk=warranty.pk)


@login_required
@require_POST
def asset_warranty_renew(request, pk):
    warranty = get_object_or_404(AssetWarranty, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        # Extend end_date by 1 year from current end_date or today, whichever is later
        base_date = max(warranty.end_date, timezone.now().date())
        warranty.end_date = base_date + timedelta(days=365)
        warranty.status = "active"
        warranty.save(update_fields=["end_date", "status", "updated_at"])
        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="asset_warranty.renew",
            model_name="AssetWarranty",
            object_id=warranty.pk,
            details=f"Renewed warranty {warranty.number} to {warranty.end_date}",
        )
        messages.success(request, f"Warranty {warranty.number} renewed through {warranty.end_date}.")
    return redirect("assets:asset_warranty_detail", pk=warranty.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_warranty_void(request, pk):
    warranty = get_object_or_404(AssetWarranty, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        warranty.status = "voided"
        warranty.save(update_fields=["status", "updated_at"])
        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action="asset_warranty.void",
            model_name="AssetWarranty",
            object_id=warranty.pk,
            details=f"Voided warranty {warranty.number}",
        )
        messages.info(request, f"Warranty {warranty.number} has been voided.")
    return redirect("assets:asset_warranty_detail", pk=warranty.pk)
