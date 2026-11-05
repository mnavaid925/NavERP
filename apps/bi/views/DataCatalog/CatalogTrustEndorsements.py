from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.DataCatalog.CatalogTrustEndorsements import CatalogTrustEndorsementForm
from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.models.DataCatalog.CatalogTrustEndorsements import CatalogTrustEndorsement
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def catalog_trust_endorsement_list(request):
    queryset = (
        bi_scope(CatalogTrustEndorsement.objects.all(), request)
        .select_related("asset", "attested_by")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(review_comments__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
        )

    endorsement_type_filter = request.GET.get("endorsement_type", "").strip()
    if endorsement_type_filter:
        queryset = queryset.filter(endorsement_type=endorsement_type_filter)

    verdict_filter = request.GET.get("verdict", "").strip()
    if verdict_filter:
        queryset = queryset.filter(verdict=verdict_filter)

    asset_filter = request.GET.get("asset", "").strip()
    if asset_filter and asset_filter.isdigit():
        queryset = queryset.filter(asset_id=int(asset_filter))

    all_tenant_endorsements = bi_scope(CatalogTrustEndorsement.objects.all(), request)
    counts = all_tenant_endorsements.aggregate(
        total=Count("id"),
        certified=Count("id", filter=Q(verdict="approved_certified")),
        deprecated=Count("id", filter=Q(verdict="deprecated_scheduled_retirement")),
    )
    total_count = counts["total"] or 0
    certified_count = counts["certified"] or 0
    deprecated_count = counts["deprecated"] or 0

    paginator = Paginator(queryset.order_by("-created_at"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "endorsements": page_obj,
        "endorsement_type_choices": CatalogTrustEndorsement.ENDORSEMENT_TYPE_CHOICES,
        "verdict_choices": CatalogTrustEndorsement.VERDICT_CHOICES,
        "total_count": total_count,
        "certified_count": certified_count,
        "deprecated_count": deprecated_count,
    }
    return render(request, "bi/data_catalog/catalog_trust_endorsement/list.html", context)


@login_required
def catalog_trust_endorsement_detail(request, pk):
    endorsement = bi_object(
        request,
        CatalogTrustEndorsement,
        pk,
        select_related=("asset", "attested_by"),
    )
    checklist_items = endorsement.criteria_checklist_json or {}
    context = {
        "endorsement": endorsement,
        "checklist_items": checklist_items,
    }
    return render(request, "bi/data_catalog/catalog_trust_endorsement/detail.html", context)


def _recalculate_asset_rating(asset):
    if not asset:
        return
    ratings = CatalogTrustEndorsement.objects.filter(
        tenant=asset.tenant,
        asset=asset,
        rating_value__isnull=False,
    ).aggregate(avg=Avg("rating_value"))
    if ratings["avg"] is not None:
        asset.average_rating = Decimal(str(round(ratings["avg"], 2)))
    else:
        asset.average_rating = Decimal("0.00")
    asset.save(update_fields=["average_rating"])


@login_required
def catalog_trust_endorsement_create(request):
    initial = {}
    asset_param = request.GET.get("asset")
    if asset_param and asset_param.isdigit():
        initial["asset"] = asset_param

    if request.method == "POST":
        form = CatalogTrustEndorsementForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                endorsement = form.save(commit=False)
                endorsement.tenant = request.tenant
                endorsement.attested_by = request.user
                endorsement.save()

                if endorsement.asset:
                    _recalculate_asset_rating(endorsement.asset)

                write_audit_log(
                    request.user,
                    endorsement,
                    "create",
                    changes=f"Attested endorsement {endorsement.number} ({endorsement.get_verdict_display()}) for {endorsement.asset.name}",
                    tenant=request.tenant,
                )
            messages.success(request, f"Endorsement {endorsement.number} recorded successfully.")
            return redirect("bi:catalog_trust_endorsement_detail", pk=endorsement.pk)
    else:
        form = CatalogTrustEndorsementForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "endorsement": None,
        "is_edit": False,
    }
    return render(request, "bi/data_catalog/catalog_trust_endorsement/form.html", context)


@login_required
def catalog_trust_endorsement_edit(request, pk):
    endorsement = bi_object(request, CatalogTrustEndorsement, pk)
    if not (
        endorsement.attested_by == request.user
        or getattr(request.user, "is_tenant_admin", False)
        or request.user.is_superuser
    ):
        raise PermissionDenied("Only the original reviewer or tenant administrator can edit this endorsement.")

    if request.method == "POST":
        form = CatalogTrustEndorsementForm(request.POST, instance=endorsement, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                old_asset = endorsement.asset
                endorsement = form.save()
                if endorsement.asset:
                    _recalculate_asset_rating(endorsement.asset)
                if old_asset and old_asset != endorsement.asset:
                    _recalculate_asset_rating(old_asset)
                write_audit_log(
                    request.user,
                    endorsement,
                    "update",
                    changes=f"Updated endorsement {endorsement.number}",
                    tenant=request.tenant,
                )
            messages.success(request, f"Endorsement {endorsement.number} updated successfully.")
            return redirect("bi:catalog_trust_endorsement_detail", pk=endorsement.pk)
    else:
        form = CatalogTrustEndorsementForm(instance=endorsement, tenant=request.tenant)

    context = {
        "form": form,
        "endorsement": endorsement,
        "is_edit": True,
    }
    return render(request, "bi/data_catalog/catalog_trust_endorsement/form.html", context)


@require_POST
@tenant_admin_required
def catalog_trust_endorsement_delete(request, pk):
    endorsement = bi_object(request, CatalogTrustEndorsement, pk)
    endorsement_number = endorsement.number
    asset = endorsement.asset
    with transaction.atomic():
        write_audit_log(
            request.user,
            endorsement,
            "delete",
            changes=f"Deleted endorsement {endorsement_number}",
            tenant=request.tenant,
        )
        endorsement.delete()
        if asset:
            _recalculate_asset_rating(asset)
    messages.success(request, f"Endorsement {endorsement_number} was deleted.")
    return redirect("bi:catalog_trust_endorsement_list")
