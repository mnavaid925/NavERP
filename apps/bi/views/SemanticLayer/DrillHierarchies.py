from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.SemanticLayer.DrillHierarchyForms import DrillHierarchyForm
from apps.bi.models.SemanticLayer.DrillHierarchies import DrillHierarchy
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def drill_hierarchy_list(request):
    queryset = (
        bi_scope(DrillHierarchy.objects.all(), request)
        .select_related("semantic_model")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    model_filter = request.GET.get("model", "").strip()
    if model_filter:
        queryset = queryset.filter(semantic_model_id=model_filter)

    hierarchy_type_filter = request.GET.get("hierarchy_type", "").strip()
    if hierarchy_type_filter:
        queryset = queryset.filter(hierarchy_type=hierarchy_type_filter)

    is_active_filter = request.GET.get("is_active", "").strip()
    if is_active_filter in ("1", "true", "True"):
        queryset = queryset.filter(is_active=True)
    elif is_active_filter in ("0", "false", "False"):
        queryset = queryset.filter(is_active=False)

    total_count = queryset.count()
    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    semantic_models = bi_scope(SemanticModel.objects.all(), request).order_by("name")

    context = {
        "hierarchies": page_obj,
        "drill_hierarchies": page_obj,
        "object_list": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "search_query": q,
        "model_filter": model_filter,
        "hierarchy_type_filter": hierarchy_type_filter,
        "is_active_filter": is_active_filter,
        "hierarchy_type_choices": DrillHierarchy.HIERARCHY_TYPE_CHOICES,
        "semantic_models": semantic_models,
    }
    return render(request, "bi/semantic_layer/drill_hierarchy/list.html", context)


@login_required
def drill_hierarchy_detail(request, pk):
    hierarchy = bi_object(
        request,
        DrillHierarchy,
        pk,
        select_related=("semantic_model",),
    )

    context = {
        "hierarchy": hierarchy,
        "drill_hierarchy": hierarchy,
        "object": hierarchy,
    }
    return render(request, "bi/semantic_layer/drill_hierarchy/detail.html", context)


@login_required
def drill_hierarchy_create(request):
    initial = {}
    model_param = request.GET.get("model")
    if model_param:
        initial["semantic_model"] = model_param

    if request.method == "POST":
        form = DrillHierarchyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            hierarchy = form.save(commit=False)
            hierarchy.tenant = request.tenant
            hierarchy.save()
            write_audit_log(
                request.tenant,
                request.user,
                "create",
                "DrillHierarchy",
                hierarchy.pk,
                f"Created drill hierarchy {hierarchy.name} ({hierarchy.number})",
            )
            messages.success(request, f"Drill Hierarchy '{hierarchy.name}' created successfully.")
            return redirect("bi:drill_hierarchy_detail", pk=hierarchy.pk)
    else:
        form = DrillHierarchyForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "bi/semantic_layer/drill_hierarchy/form.html", context)


@login_required
def drill_hierarchy_edit(request, pk):
    hierarchy = bi_object(request, DrillHierarchy, pk)
    if request.method == "POST":
        form = DrillHierarchyForm(request.POST, instance=hierarchy, tenant=request.tenant)
        if form.is_valid():
            hierarchy = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "update",
                "DrillHierarchy",
                hierarchy.pk,
                f"Updated drill hierarchy {hierarchy.name} ({hierarchy.number})",
            )
            messages.success(request, f"Drill Hierarchy '{hierarchy.name}' updated successfully.")
            return redirect("bi:drill_hierarchy_detail", pk=hierarchy.pk)
    else:
        form = DrillHierarchyForm(instance=hierarchy, tenant=request.tenant)

    context = {
        "form": form,
        "hierarchy": hierarchy,
        "drill_hierarchy": hierarchy,
        "object": hierarchy,
        "is_edit": True,
    }
    return render(request, "bi/semantic_layer/drill_hierarchy/form.html", context)


@login_required
@require_POST
def drill_hierarchy_delete(request, pk):
    hierarchy = bi_object(request, DrillHierarchy, pk)
    name = hierarchy.name
    num = hierarchy.number
    hierarchy.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "delete",
        "DrillHierarchy",
        pk,
        f"Deleted drill hierarchy {name} ({num})",
    )
    messages.success(request, f"Drill Hierarchy '{name}' ({num}) deleted successfully.")
    return redirect("bi:drill_hierarchy_list")
