from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetClassification.AssetSpecificationTemplates import AssetSpecificationTemplateForm
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetSpecificationTemplates import AssetSpecificationTemplate
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_specification_template_list(request):
    qs = AssetSpecificationTemplate.objects.filter(tenant=request.tenant).select_related("category", "model")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(attribute_key__icontains=q)
            | Q(display_name__icontains=q)
            | Q(unit_of_measure__icontains=q)
            | Q(help_text__icontains=q)
        )

    dtype = request.GET.get("type", "").strip()
    if dtype:
        qs = qs.filter(data_type=dtype)

    category_id = request.GET.get("category", "").strip()
    if category_id and category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))

    # Aggregates for KPI cards
    all_specs = AssetSpecificationTemplate.objects.filter(tenant=request.tenant)
    counts = all_specs.aggregate(
        total=Count("id"),
        numeric=Count("id", filter=Q(data_type="number")),
        text=Count("id", filter=Q(data_type="text")),
        required=Count("id", filter=Q(is_required=True)),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    categories = AssetCategory.objects.filter(tenant=request.tenant, is_active=True).order_by("code")

    context = {
        "templates": page_obj,
        "template_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "data_types": AssetSpecificationTemplate.DATA_TYPE_CHOICES,
        "categories": categories,
        "q": q,
        "selected_type": dtype,
        "selected_category": category_id,
        "total_count": counts["total"] or 0,
        "numeric_count": counts["numeric"] or 0,
        "text_count": counts["text"] or 0,
        "required_count": counts["required"] or 0,
    }
    return render(
        request, "assets/asset_classification/asset_specification_template/list.html", context
    )


@login_required
def asset_specification_template_detail(request, pk):
    template = assets_object(
        request, AssetSpecificationTemplate, pk=pk, select_related=["category", "model"]
    )
    context = {
        "template": template,
    }
    return render(
        request, "assets/asset_classification/asset_specification_template/detail.html", context
    )


@login_required
def asset_specification_template_create(request):
    if request.method == "POST":
        form = AssetSpecificationTemplateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            template = form.save(commit=False)
            template.tenant = request.tenant
            template.save()
            write_audit_log(request.user, template, "create", tenant=request.tenant)
            messages.success(request, f"Specification Attribute '{template.attribute_key}' created successfully.")
            return redirect("assets:asset_specification_template_detail", pk=template.pk)
    else:
        form = AssetSpecificationTemplateForm(tenant=request.tenant)

    context = {
        "form": form,
        "template": None,
        "is_edit": False,
    }
    return render(
        request, "assets/asset_classification/asset_specification_template/form.html", context
    )


@login_required
def asset_specification_template_edit(request, pk):
    template = assets_object(request, AssetSpecificationTemplate, pk=pk)
    if request.method == "POST":
        form = AssetSpecificationTemplateForm(request.POST, instance=template, tenant=request.tenant)
        if form.is_valid():
            template = form.save()
            write_audit_log(request.user, template, "update", tenant=request.tenant)
            messages.success(request, f"Specification Attribute '{template.attribute_key}' updated successfully.")
            return redirect("assets:asset_specification_template_detail", pk=template.pk)
    else:
        form = AssetSpecificationTemplateForm(instance=template, tenant=request.tenant)

    context = {
        "form": form,
        "template": template,
        "is_edit": True,
    }
    return render(
        request, "assets/asset_classification/asset_specification_template/form.html", context
    )


@login_required
@require_POST
@tenant_admin_required
def asset_specification_template_delete(request, pk):
    template = assets_object(request, AssetSpecificationTemplate, pk=pk)
    key = template.attribute_key
    write_audit_log(request.user, template, "delete", tenant=request.tenant)
    template.delete()
    messages.success(request, f"Specification Attribute '{key}' deleted successfully.")
    return redirect("assets:asset_specification_template_list")
