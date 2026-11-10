from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDisposal.AssetScrapSalvages import (
    AssetScrapAbatementForm,
    AssetScrapCertificateForm,
    AssetScrapSalvageForm,
)
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.models.AssetDisposal.AssetScrapSalvages import AssetScrapSalvage
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log


@login_required
def asset_scrap_salvage_list(request):
    qs = assets_scope(
        AssetScrapSalvage.objects.select_related(
            "disposal_request",
            "fixed_asset",
            "operational_asset",
            "recycler_partner",
            "supervisor",
        ).defer("notes"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(cod_number__icontains=q)
            | Q(epa_manifest_number__icontains=q)
            | Q(recycler_partner__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    scrap_method_filter = request.GET.get("scrap_method", "").strip()
    if scrap_method_filter:
        qs = qs.filter(scrap_method=scrap_method_filter)

    recycler_filter = request.GET.get("recycler", "").strip()
    if recycler_filter and recycler_filter.isdigit():
        qs = qs.filter(recycler_partner_id=int(recycler_filter))

    base_tenant_qs = assets_scope(AssetScrapSalvage.objects.all(), request)
    total_scraps = base_tenant_qs.count()
    in_progress_count = base_tenant_qs.filter(
        status__in=["dismantling", "abatement_in_progress", "scrap_transferred"]
    ).count()
    certified_destroyed_count = base_tenant_qs.filter(
        status__in=["certified_destroyed", "settled"]
    ).count()
    proceeds_agg = base_tenant_qs.aggregate(
        proceeds=Sum("salvage_proceeds"),
        weight=Sum("total_scrap_weight_kg"),
    )
    total_salvage_proceeds = proceeds_agg["proceeds"] or Decimal("0.00")
    total_weight_recovered = proceeds_agg["weight"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "scrap_salvages": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetScrapSalvage.STATUS_CHOICES,
        "scrap_method_choices": AssetScrapSalvage.SCRAP_METHOD_CHOICES,
        "recycler_list": Party.objects.filter(tenant=request.tenant),
        "total_scraps": total_scraps,
        "in_progress_count": in_progress_count,
        "certified_destroyed_count": certified_destroyed_count,
        "total_salvage_proceeds": total_salvage_proceeds,
        "total_weight_recovered": total_weight_recovered,
    }
    return render(request, "assets/assetdisposal/asset_scrap_salvage/list.html", context)


@login_required
def asset_scrap_salvage_detail(request, pk):
    scrap_salvage = assets_object(
        request,
        AssetScrapSalvage,
        pk,
        select_related=[
            "disposal_request",
            "fixed_asset",
            "operational_asset",
            "recycler_partner",
            "supervisor",
            "certificate_of_destruction",
            "hazardous_manifest_doc",
        ],
    )

    abatement_form = AssetScrapAbatementForm(initial={
        "hazardous_waste_class": scrap_salvage.hazardous_waste_class,
        "epa_manifest_number": scrap_salvage.epa_manifest_number,
    })
    cert_form = AssetScrapCertificateForm(initial={
        "cod_number": scrap_salvage.cod_number,
        "cod_issue_date": scrap_salvage.cod_issue_date or timezone.now().date(),
        "cod_issuing_agency": scrap_salvage.cod_issuing_agency,
    })

    context = {
        "scrap_salvage": scrap_salvage,
        "abatement_form": abatement_form,
        "cert_form": cert_form,
    }
    return render(request, "assets/assetdisposal/asset_scrap_salvage/detail.html", context)


@login_required
def asset_scrap_salvage_create(request):
    if request.method == "POST":
        form = AssetScrapSalvageForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                if not instance.supervisor:
                    instance.supervisor = request.user
                instance.calculate_net_recovery()
                if instance.status == "draft":
                    instance.status = "dismantling"
                instance.save()

                # Sync disposal request to in_progress if approved
                dr = instance.disposal_request
                if dr and dr.status == "approved":
                    dr.status = "in_progress"
                    dr.save(update_fields=["status", "updated_at"])

                write_audit_log(request.user, instance, "create", tenant=request.tenant)
            messages.success(request, f"Scrap job {instance.number} created successfully.")
            return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)
    else:
        initial = {}
        dr_id = request.GET.get("disposal_request")
        if dr_id and dr_id.isdigit():
            initial["disposal_request"] = int(dr_id)
            dr = assets_scope(AssetDisposalRequest.objects.all(), request).filter(pk=int(dr_id)).first()
            if dr and dr.fixed_asset:
                initial["fixed_asset"] = dr.fixed_asset.pk
                if dr.operational_asset:
                    initial["operational_asset"] = dr.operational_asset.pk
        form = AssetScrapSalvageForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "scrap_salvage": None,
        "is_edit": False,
    }
    return render(request, "assets/assetdisposal/asset_scrap_salvage/form.html", context)


@login_required
def asset_scrap_salvage_edit(request, pk):
    instance = assets_object(request, AssetScrapSalvage, pk)
    if instance.status in ["settled", "cancelled"]:
        messages.error(request, f"Scrap job {instance.number} is {instance.get_status_display()} and cannot be edited.")
        return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)

    if request.method == "POST":
        form = AssetScrapSalvageForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.calculate_net_recovery()
                instance.save()
                write_audit_log(request.user, instance, "update", tenant=request.tenant)
            messages.success(request, f"Scrap job {instance.number} updated successfully.")
            return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)
    else:
        form = AssetScrapSalvageForm(instance=instance, tenant=request.tenant)

    context = {
        "form": form,
        "scrap_salvage": instance,
        "is_edit": True,
    }
    return render(request, "assets/assetdisposal/asset_scrap_salvage/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def asset_scrap_salvage_delete(request, pk):
    instance = assets_object(request, AssetScrapSalvage, pk)
    if instance.status in ["certified_destroyed", "settled"]:
        messages.error(request, f"Certified or settled scrap record {instance.number} cannot be deleted.")
        return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)

    with transaction.atomic():
        write_audit_log(request.user, instance, "delete", tenant=request.tenant)
        instance.delete()
    messages.success(request, f"Scrap job {instance.number} deleted successfully.")
    return redirect("assets:asset_scrap_salvage_list")


@login_required
@require_POST
def asset_scrap_salvage_certify_abatement(request, pk):
    instance = assets_object(request, AssetScrapSalvage, pk)
    form = AssetScrapAbatementForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            instance.abatement_certified = True
            instance.abatement_date = timezone.now().date()
            instance.epa_manifest_number = form.cleaned_data["epa_manifest_number"]
            if form.cleaned_data.get("hazardous_waste_class"):
                instance.hazardous_waste_class = form.cleaned_data["hazardous_waste_class"]
            if form.cleaned_data.get("abatement_notes"):
                instance.notes += f"\n[Abatement Verified]: {form.cleaned_data['abatement_notes']}"
            instance.status = "scrap_transferred"
            instance.save(update_fields=[
                "abatement_certified",
                "abatement_date",
                "epa_manifest_number",
                "hazardous_waste_class",
                "notes",
                "status",
                "updated_at",
            ])
            write_audit_log(request.user, instance, "update", tenant=request.tenant)
        messages.success(request, f"Hazardous waste abatement certified for job {instance.number}. Status advanced.")
    else:
        messages.error(request, "Abatement certification requires a valid EPA manifest number.")
    return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)


@login_required
@require_POST
def asset_scrap_salvage_record_cod(request, pk):
    instance = assets_object(request, AssetScrapSalvage, pk)
    form = AssetScrapCertificateForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            instance.cod_number = form.cleaned_data["cod_number"]
            instance.cod_issue_date = form.cleaned_data["cod_issue_date"]
            instance.cod_issuing_agency = form.cleaned_data["cod_issuing_agency"]
            instance.status = "certified_destroyed"
            instance.save(update_fields=[
                "cod_number",
                "cod_issue_date",
                "cod_issuing_agency",
                "status",
                "updated_at",
            ])
            write_audit_log(request.user, instance, "update", tenant=request.tenant)
        messages.success(request, f"Certificate of Destruction (CoD) {instance.cod_number} recorded. Status updated to Certified Destroyed.")
    else:
        messages.error(request, "Certificate of Destruction requires CoD serial number, date, and issuing agency.")
    return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)


@login_required
@require_POST
def asset_scrap_salvage_settle(request, pk):
    instance = assets_object(request, AssetScrapSalvage, pk)
    if instance.status == "settled":
        messages.info(request, f"Scrap job {instance.number} has already been settled.")
        return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)

    with transaction.atomic():
        instance.completion_date = timezone.now().date()
        instance.status = "settled"
        instance.calculate_net_recovery()
        instance.save(update_fields=["completion_date", "status", "net_salvage_recovery", "updated_at"])

        # Sync salvage proceeds & dismantling costs to parent disposal request
        dr = instance.disposal_request
        if dr:
            dr.actual_gross_proceeds = (dr.actual_gross_proceeds or Decimal("0.00")) + instance.salvage_proceeds
            dr.actual_removal_cost = (dr.actual_removal_cost or Decimal("0.00")) + instance.dismantling_cost
            dr.calculate_gain_loss()
            dr.save(update_fields=["actual_gross_proceeds", "actual_removal_cost", "realized_gain_loss", "updated_at"])

        write_audit_log(request.user, instance, "update", tenant=request.tenant)
    messages.success(
        request,
        f"Scrap settlement closed for {instance.number}. Salvage proceeds (${instance.salvage_proceeds}) "
        f"and dismantling costs (${instance.dismantling_cost}) synchronized to disposal request."
    )
    return redirect("assets:asset_scrap_salvage_detail", pk=instance.pk)
