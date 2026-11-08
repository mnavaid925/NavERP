from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import FixedAsset
from apps.assets.forms.AssetProcurement.AssetCapitalizations import AssetCapitalizationForm
from apps.assets.models.AssetProcurement.AssetAcquisitionReceipts import AssetAcquisitionReceipt
from apps.assets.models.AssetProcurement.AssetCapitalizations import AssetCapitalization
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log


@login_required
def asset_capitalization_list(request):
    """List asset capitalization events with status, depreciation method filters, search, and pagination."""
    queryset = assets_scope(AssetCapitalization.objects.all(), request).select_related(
        "acquisition_receipt",
        "requisition",
        "cip_gl_account",
        "asset_gl_account",
        "fixed_asset",
        "operational_asset",
        "capitalized_by",
    )

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(asset_name__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        queryset = queryset.filter(status=status)

    method = request.GET.get("method", "").strip()
    if method:
        queryset = queryset.filter(depreciation_method=method)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "capitalizations": page_obj,
        "page_obj": page_obj,
        "status_choices": AssetCapitalization.STATUS_CHOICES,
        "method_choices": AssetCapitalization.DEPRECIATION_METHOD_CHOICES,
    }
    return render(request, "assets/asset_procurement/asset_capitalization/list.html", context)


@login_required
def asset_capitalization_detail(request, pk):
    """Display comprehensive details of an asset capitalization event."""
    capitalization = assets_object(
        request,
        AssetCapitalization,
        pk,
        select_related=(
            "acquisition_receipt",
            "requisition",
            "cip_gl_account",
            "asset_gl_account",
            "fixed_asset",
            "operational_asset",
            "capitalized_by",
        ),
    )
    return render(
        request,
        "assets/asset_procurement/asset_capitalization/detail.html",
        {"capitalization": capitalization},
    )


@login_required
def asset_capitalization_create(request):
    """Create a new asset capitalization event with cost basis breakdown."""
    initial = {}
    receipt_pk = request.GET.get("receipt", "").strip()
    if receipt_pk and receipt_pk.isdigit():
        receipt = assets_scope(AssetAcquisitionReceipt.objects.all(), request).filter(pk=int(receipt_pk)).first()
        if receipt:
            initial["acquisition_receipt"] = receipt
            initial["requisition"] = receipt.requisition
            initial["title"] = f"Capitalization of {receipt.title}"
            initial["asset_name"] = receipt.title
            if receipt.requisition and receipt.requisition.estimated_cost:
                initial["purchase_cost"] = receipt.requisition.estimated_cost

    if request.method == "POST":
        form = AssetCapitalizationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cap = form.save(commit=False)
            cap.tenant = request.tenant
            cap.save()
            write_audit_log(
                request.user,
                cap,
                "create",
                changes={"details": f"Created capitalization event {cap.number} for {cap.asset_name} (Cost: {cap.total_cost_basis})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Capitalization {cap.number} created successfully.")
            return redirect("assets:asset_capitalization_detail", pk=cap.pk)
    else:
        form = AssetCapitalizationForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_capitalization/form.html",
        {"form": form, "capitalization": None, "is_edit": False},
    )


@login_required
def asset_capitalization_edit(request, pk):
    """Update details of an asset capitalization event."""
    capitalization = assets_object(request, AssetCapitalization, pk)
    if capitalization.status == "capitalized":
        messages.error(request, f"Capitalization {capitalization.number} cannot be edited because it is already capitalized into the fixed asset ledger.")
        return redirect("assets:asset_capitalization_detail", pk=capitalization.pk)

    if request.method == "POST":
        form = AssetCapitalizationForm(request.POST, instance=capitalization, tenant=request.tenant)
        if form.is_valid():
            cap = form.save()
            write_audit_log(
                request.user,
                cap,
                "update",
                changes={"details": f"Updated capitalization {cap.number} (Cost: {cap.total_cost_basis})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Capitalization {cap.number} updated successfully.")
            return redirect("assets:asset_capitalization_detail", pk=cap.pk)
    else:
        form = AssetCapitalizationForm(instance=capitalization, tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_capitalization/form.html",
        {"form": form, "capitalization": capitalization, "is_edit": True},
    )


@login_required
@require_POST
def asset_capitalization_delete(request, pk):
    """Delete an asset capitalization event."""
    capitalization = assets_object(request, AssetCapitalization, pk)
    if capitalization.status == "capitalized":
        messages.error(request, f"Capitalization {capitalization.number} cannot be deleted because it is already capitalized. Please reverse it first.")
        return redirect("assets:asset_capitalization_detail", pk=capitalization.pk)
    number = capitalization.number
    write_audit_log(
        request.user,
        capitalization,
        "delete",
        changes={"details": f"Deleted capitalization {number}"},
        tenant=request.tenant,
    )
    capitalization.delete()
    messages.success(request, f"Asset Capitalization {number} was deleted.")
    return redirect("assets:asset_capitalization_list")


@login_required
@require_POST
def asset_capitalization_execute(request, pk):
    """Execute formal asset capitalization: initializes FixedAsset and updates status."""
    with transaction.atomic():
        capitalization = get_object_or_404(
            AssetCapitalization.objects.select_for_update(),
            tenant=request.tenant,
            pk=pk,
        )
        if not capitalization.can_execute_capitalization():
            messages.error(request, f"Capitalization {capitalization.number} cannot be executed in state '{capitalization.get_status_display()}'.")
            return redirect("assets:asset_capitalization_detail", pk=capitalization.pk)
        # Automatically create financial fixed asset in Module 2 if not explicitly linked
        if not capitalization.fixed_asset:
            fa = FixedAsset(
                tenant=request.tenant,
                name=capitalization.asset_name,
                category=(capitalization.requisition.get_asset_category_display() if capitalization.requisition else "Capital Equipment"),
                acquisition_cost=capitalization.total_cost_basis,
                salvage_value=capitalization.salvage_value,
                useful_life_months=capitalization.useful_life_months,
                method=capitalization.depreciation_method,
                in_service_date=capitalization.in_service_date,
                asset_account=capitalization.asset_gl_account,
                status="active",
                notes=f"Capitalized from {capitalization.number}",
            )
            fa.save()
            capitalization.fixed_asset = fa

        # Mark upstream receipt as capitalized if present
        if capitalization.acquisition_receipt:
            receipt = capitalization.acquisition_receipt
            receipt.status = "capitalized"
            receipt.save(update_fields=["status", "updated_at"])

        capitalization.status = "capitalized"
        capitalization.capitalized_by = request.user
        capitalization.capitalized_at = timezone.now()
        capitalization.save(update_fields=["status", "fixed_asset", "capitalized_by", "capitalized_at", "updated_at"])

        write_audit_log(
            request.user,
            capitalization,
            "update",
            changes={"action": "execute_capitalization", "details": f"Executed capitalization {capitalization.number} into Fixed Asset {capitalization.fixed_asset.number if capitalization.fixed_asset else ''}"},
            tenant=request.tenant,
        )
    messages.success(request, f"Asset Capitalization {capitalization.number} successfully completed and capitalized into Fixed Assets.")
    return redirect("assets:asset_capitalization_detail", pk=capitalization.pk)


@login_required
@require_POST
def asset_capitalization_reverse(request, pk):
    """Reverse an executed capitalization event."""
    capitalization = assets_object(request, AssetCapitalization, pk)
    if not capitalization.can_reverse():
        messages.error(request, f"Capitalization {capitalization.number} cannot be reversed in state '{capitalization.get_status_display()}'.")
        return redirect("assets:asset_capitalization_detail", pk=capitalization.pk)

    with transaction.atomic():
        capitalization.status = "reversed"
        capitalization.save(update_fields=["status", "updated_at"])

        write_audit_log(
            request.user,
            capitalization,
            "update",
            changes={"action": "reverse_capitalization", "details": f"Reversed capitalization {capitalization.number}"},
            tenant=request.tenant,
        )
    messages.warning(request, f"Asset Capitalization {capitalization.number} has been reversed.")
    return redirect("assets:asset_capitalization_detail", pk=capitalization.pk)
