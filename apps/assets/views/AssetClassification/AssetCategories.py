from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetClassification.AssetCategories import AssetCategoryForm
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_category_list(request):
    qs = AssetCategory.objects.filter(tenant=request.tenant).select_related("parent")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(name__icontains=q)
            | Q(unspsc_code__icontains=q)
            | Q(unspsc_title__icontains=q)
            | Q(description__icontains=q)
        )

    cat_type = request.GET.get("type", "").strip()
    if cat_type:
        qs = qs.filter(category_type=cat_type)

    parent_id = request.GET.get("parent", "").strip()
    if parent_id and parent_id.isdigit():
        qs = qs.filter(parent_id=int(parent_id))

    # Aggregates for KPI tiles
    all_tenant_cats = AssetCategory.objects.filter(tenant=request.tenant)
    counts = all_tenant_cats.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        root=Count("id", filter=Q(parent__isnull=True)),
        machinery=Count("id", filter=Q(category_type="machinery")),
        facility=Count("id", filter=Q(category_type="facility")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    parent_categories = (
        AssetCategory.objects.filter(tenant=request.tenant, parent__isnull=True, is_active=True)
        .order_by("code")
    )

    context = {
        "categories": page_obj,
        "category_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "category_types": AssetCategory.CATEGORY_TYPE_CHOICES,
        "parent_categories": parent_categories,
        "q": q,
        "search_query": q,
        "selected_type": cat_type,
        "selected_parent": parent_id,
        "total_count": counts["total"] or 0,
        "active_count": counts["active"] or 0,
        "root_count": counts["root"] or 0,
        "machinery_count": counts["machinery"] or 0,
        "facility_count": counts["facility"] or 0,
    }
    return render(request, "assets/asset_classification/asset_category/list.html", context)


@login_required
def asset_category_detail(request, pk):
    category = assets_object(request, AssetCategory, pk=pk, select_related=["parent"])
    children = category.children.filter(tenant=request.tenant).order_by("code")
    models_qs = category.models.filter(tenant=request.tenant).select_related("manufacturer").order_by("model_number")
    spec_templates = category.spec_templates.filter(tenant=request.tenant).order_by("display_order")

    context = {
        "category": category,
        "children": children,
        "models": models_qs,
        "spec_templates": spec_templates,
    }
    return render(request, "assets/asset_classification/asset_category/detail.html", context)


@login_required
def asset_category_create(request):
    if request.method == "POST":
        form = AssetCategoryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            category = form.save(commit=False)
            category.tenant = request.tenant
            category.save()
            write_audit_log(request.user, category, "create", tenant=request.tenant)
            messages.success(request, f"Asset Category {category.code} created successfully.")
            return redirect("assets:asset_category_detail", pk=category.pk)
    else:
        form = AssetCategoryForm(tenant=request.tenant)

    context = {
        "form": form,
        "category": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_classification/asset_category/form.html", context)


@login_required
def asset_category_edit(request, pk):
    category = assets_object(request, AssetCategory, pk=pk)
    if request.method == "POST":
        form = AssetCategoryForm(request.POST, instance=category, tenant=request.tenant)
        if form.is_valid():
            category = form.save()
            write_audit_log(request.user, category, "update", tenant=request.tenant)
            messages.success(request, f"Asset Category {category.code} updated successfully.")
            return redirect("assets:asset_category_detail", pk=category.pk)
    else:
        form = AssetCategoryForm(instance=category, tenant=request.tenant)

    context = {
        "form": form,
        "category": category,
        "is_edit": True,
    }
    return render(request, "assets/asset_classification/asset_category/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def asset_category_delete(request, pk):
    category = assets_object(request, AssetCategory, pk=pk)
    # Check for active children or dependent models
    child_count = category.children.filter(tenant=request.tenant).count()
    model_count = category.models.filter(tenant=request.tenant).count()
    if child_count > 0 or model_count > 0:
        messages.error(
            request,
            f"Cannot delete category {category.code} because it contains "
            f"{child_count} sub-categories and {model_count} equipment models. Reassign them first.",
        )
        return redirect("assets:asset_category_detail", pk=category.pk)

    code = category.code
    write_audit_log(request.user, category, "delete", tenant=request.tenant)
    category.delete()
    messages.success(request, f"Asset Category {code} deleted successfully.")
    return redirect("assets:asset_category_list")
