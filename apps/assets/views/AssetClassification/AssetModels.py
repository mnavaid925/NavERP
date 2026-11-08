from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetClassification.AssetModels import AssetModelForm
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.scm.models import Asset


@login_required
def asset_model_list(request):
    qs = AssetModel.objects.filter(tenant=request.tenant).select_related("category", "manufacturer")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(model_number__icontains=q)
            | Q(name__icontains=q)
            | Q(manufacturer__name__icontains=q)
            | Q(manufacturer_name_fallback__icontains=q)
            | Q(description__icontains=q)
            | Q(technical_specifications__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(model_status=status)

    category_id = request.GET.get("category", "").strip()
    if category_id and category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))

    # Aggregates for KPI tiles
    all_models = AssetModel.objects.filter(tenant=request.tenant)
    counts = all_models.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(model_status="active")),
        phased_out=Count("id", filter=Q(model_status="phased_out")),
        discontinued=Count("id", filter=Q(model_status="discontinued")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    categories = AssetCategory.objects.filter(tenant=request.tenant, is_active=True).order_by("code")

    context = {
        "models": page_obj,
        "model_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "model_statuses": AssetModel.MODEL_STATUS_CHOICES,
        "categories": categories,
        "q": q,
        "selected_status": status,
        "selected_category": category_id,
        "total_count": counts["total"] or 0,
        "active_count": counts["active"] or 0,
        "phased_out_count": counts["phased_out"] or 0,
        "discontinued_count": counts["discontinued"] or 0,
    }
    return render(request, "assets/asset_classification/asset_model/list.html", context)


@login_required
def asset_model_detail(request, pk):
    model = assets_object(request, AssetModel, pk=pk, select_related=["category", "manufacturer"])
    spec_templates = model.spec_templates.filter(tenant=request.tenant).order_by("display_order")

    # Find physically deployed scm.Asset instances matching this model number
    deployed_assets = (
        Asset.objects.filter(tenant=request.tenant, model_number__iexact=model.model_number)
        .select_related("location", "custodian")
        .order_by("number")[:15]
    )
    deployed_count = Asset.objects.filter(tenant=request.tenant, model_number__iexact=model.model_number).count()

    context = {
        "model": model,
        "spec_templates": spec_templates,
        "deployed_assets": deployed_assets,
        "deployed_count": deployed_count,
    }
    return render(request, "assets/asset_classification/asset_model/detail.html", context)


@login_required
def asset_model_create(request):
    if request.method == "POST":
        form = AssetModelForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            model = form.save(commit=False)
            model.tenant = request.tenant
            model.save()
            write_audit_log(request.user, model, "create", tenant=request.tenant)
            messages.success(request, f"Equipment Model {model.model_number} created successfully.")
            return redirect("assets:asset_model_detail", pk=model.pk)
    else:
        form = AssetModelForm(tenant=request.tenant)

    context = {
        "form": form,
        "model": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_classification/asset_model/form.html", context)


@login_required
def asset_model_edit(request, pk):
    model = assets_object(request, AssetModel, pk=pk)
    if request.method == "POST":
        form = AssetModelForm(request.POST, instance=model, tenant=request.tenant)
        if form.is_valid():
            model = form.save()
            write_audit_log(request.user, model, "update", tenant=request.tenant)
            messages.success(request, f"Equipment Model {model.model_number} updated successfully.")
            return redirect("assets:asset_model_detail", pk=model.pk)
    else:
        form = AssetModelForm(instance=model, tenant=request.tenant)

    context = {
        "form": form,
        "model": model,
        "is_edit": True,
    }
    return render(request, "assets/asset_classification/asset_model/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def asset_model_delete(request, pk):
    model = assets_object(request, AssetModel, pk=pk)
    # Check if deployed physical assets match this model number
    deployed_count = Asset.objects.filter(tenant=request.tenant, model_number__iexact=model.model_number).count()
    if deployed_count > 0:
        messages.error(
            request,
            f"Cannot delete model {model.model_number} because {deployed_count} registered "
            f"assets currently reference this model number. Retire or update them first.",
        )
        return redirect("assets:asset_model_detail", pk=model.pk)

    model_number = model.model_number
    write_audit_log(request.user, model, "delete", tenant=request.tenant)
    model.delete()
    messages.success(request, f"Equipment Model {model_number} deleted successfully.")
    return redirect("assets:asset_model_list")
