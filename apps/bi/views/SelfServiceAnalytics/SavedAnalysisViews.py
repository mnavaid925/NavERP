from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.bi.forms.SelfServiceAnalytics.SavedAnalysisViews import (
    SavedAnalysisViewForm,
    SavedAnalysisViewShareForm,
)
from apps.bi.models.SelfServiceAnalytics.AdHocQueries import AdHocQuery
from apps.bi.models.SelfServiceAnalytics.SavedAnalysisViews import SavedAnalysisView
from apps.bi.views._common import bi_object, bi_scope
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log


@login_required
def saved_analysis_view_list(request):
    qs = bi_scope(SavedAnalysisView.objects.all(), request, owner_field="created_by").select_related(
        "query", "org_unit", "created_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    scope = request.GET.get("scope", "").strip()
    if scope:
        qs = qs.filter(sharing_scope=scope)

    is_favorite = request.GET.get("favorite", "").strip()
    if is_favorite in ("1", "true", "True"):
        qs = qs.filter(is_favorite=True)

    is_template = request.GET.get("template", "").strip()
    if is_template in ("1", "true", "True"):
        qs = qs.filter(is_template=True)

    org_units = OrgUnit.objects.filter(tenant=request.tenant)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "bi/self_service_analytics/saved_analysis_view/list.html",
        {
            "views": page_obj.object_list,
            "page_obj": page_obj,
            "scope_choices": SavedAnalysisView.SHARING_SCOPE_CHOICES,
            "org_units": org_units,
        },
    )


@login_required
def saved_analysis_view_detail(request, pk):
    view_obj = bi_object(
        request,
        SavedAnalysisView,
        pk,
        select_related=("query", "org_unit", "parent_view", "created_by"),
    )

    # Increment view counter
    view_obj.view_count += 1
    view_obj.last_viewed_at = timezone.now()
    view_obj.save(update_fields=["view_count", "last_viewed_at", "updated_at"])

    return render(
        request,
        "bi/self_service_analytics/saved_analysis_view/detail.html",
        {
            "view_obj": view_obj,
            "query": view_obj.query,
        },
    )


@login_required
def saved_analysis_view_create(request):
    queries = AdHocQuery.objects.filter(tenant=request.tenant)
    org_units = OrgUnit.objects.filter(tenant=request.tenant)

    initial = {}
    query_param = request.GET.get("query")
    if query_param and query_param.isdigit():
        initial["query"] = int(query_param)

    if request.method == "POST":
        form = SavedAnalysisViewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            view_obj = form.save(commit=False)
            view_obj.tenant = request.tenant
            view_obj.created_by = request.user
            view_obj.save()

            write_audit_log(
                user=request.user,
                obj=view_obj,
                action="create",
                tenant=request.tenant,
                changes={"description": f"Created saved analysis view {view_obj.name} ({view_obj.number})"},
            )
            messages.success(request, f"Saved view '{view_obj.name}' created.")
            return redirect("bi:saved_analysis_view_detail", pk=view_obj.pk)
    else:
        form = SavedAnalysisViewForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "bi/self_service_analytics/saved_analysis_view/form.html",
        {
            "form": form,
            "is_edit": False,
            "queries": queries,
            "org_units": org_units,
        },
    )


@login_required
def saved_analysis_view_edit(request, pk):
    view_obj = bi_object(request, SavedAnalysisView, pk)
    queries = AdHocQuery.objects.filter(tenant=request.tenant)
    org_units = OrgUnit.objects.filter(tenant=request.tenant)

    if request.method == "POST":
        form = SavedAnalysisViewForm(request.POST, instance=view_obj, tenant=request.tenant)
        if form.is_valid():
            view_obj = form.save()
            write_audit_log(
                user=request.user,
                obj=view_obj,
                action="update",
                tenant=request.tenant,
                changes={"description": f"Updated saved analysis view {view_obj.name} ({view_obj.number})"},
            )
            messages.success(request, f"Saved view '{view_obj.name}' updated successfully.")
            return redirect("bi:saved_analysis_view_detail", pk=view_obj.pk)
    else:
        form = SavedAnalysisViewForm(instance=view_obj, tenant=request.tenant)

    return render(
        request,
        "bi/self_service_analytics/saved_analysis_view/form.html",
        {
            "form": form,
            "view_obj": view_obj,
            "is_edit": True,
            "queries": queries,
            "org_units": org_units,
        },
    )


@login_required
@require_POST
def saved_analysis_view_delete(request, pk):
    view_obj = bi_object(request, SavedAnalysisView, pk)
    name = view_obj.name
    number = view_obj.number

    write_audit_log(
        user=request.user,
        obj=view_obj,
        action="delete",
        tenant=request.tenant,
        changes={"description": f"Deleted saved analysis view {name} ({number})"},
    )
    view_obj.delete()
    messages.success(request, f"Saved view '{name}' ({number}) deleted.")
    return redirect("bi:saved_analysis_view_list")


@login_required
def saved_analysis_view_clone(request, pk):
    original = bi_object(request, SavedAnalysisView, pk)

    base_slug = slugify(f"Copy of {original.name}")[:90] or "view-copy"
    slug = base_slug
    counter = 1
    while SavedAnalysisView.objects.filter(tenant=request.tenant, slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    cloned = SavedAnalysisView.objects.create(
        tenant=request.tenant,
        name=f"Copy of {original.name}",
        slug=slug,
        description=original.description,
        query=original.query,
        sharing_scope="personal",
        org_unit=original.org_unit,
        is_template=False,
        is_favorite=False,
        parent_view=original,
        created_by=request.user,
    )

    write_audit_log(
        user=request.user,
        obj=cloned,
        action="create",
        tenant=request.tenant,
        changes={"description": f"Forked analysis view from {original.number} as {cloned.number}"},
    )
    messages.success(request, f"Cloned view into personal workspace as '{cloned.name}'.")
    return redirect("bi:saved_analysis_view_detail", pk=cloned.pk)


@login_required
def saved_analysis_view_share(request, pk):
    view_obj = bi_object(request, SavedAnalysisView, pk)

    if request.method == "POST":
        form = SavedAnalysisViewShareForm(request.POST, instance=view_obj, tenant=request.tenant)
        if form.is_valid():
            view_obj = form.save()
            write_audit_log(
                user=request.user,
                obj=view_obj,
                action="update",
                tenant=request.tenant,
                changes={"description": f"Updated sharing permissions for {view_obj.name} ({view_obj.number})"},
            )
            messages.success(request, f"Sharing scope updated to '{view_obj.get_sharing_scope_display()}'.")
            return redirect("bi:saved_analysis_view_detail", pk=view_obj.pk)
    else:
        form = SavedAnalysisViewShareForm(instance=view_obj, tenant=request.tenant)

    return render(
        request,
        "bi/self_service_analytics/saved_analysis_view/share.html",
        {
            "form": form,
            "view_obj": view_obj,
        },
    )


@login_required
def saved_analysis_view_explore(request, pk):
    view_obj = bi_object(
        request,
        SavedAnalysisView,
        pk,
        select_related=("query", "org_unit", "created_by"),
    )
    query = view_obj.query

    # Increment view counter
    view_obj.view_count += 1
    view_obj.last_viewed_at = timezone.now()
    view_obj.save(update_fields=["view_count", "last_viewed_at", "updated_at"])

    chart_config = query.chart_config_json or {}
    fields_config = query.fields_config_json or [
        {"field": "period", "label": "Period"},
        {"field": "revenue", "label": "Revenue"},
    ]

    preview_results = {
        "columns": [f.get("label", f.get("field")) for f in fields_config],
        "rows": [
            {"Period": "2026-Q1", "Revenue": "$145,200.00"},
            {"Period": "2026-Q2", "Revenue": "$189,450.00"},
            {"Period": "2026-Q3", "Revenue": "$210,100.00"},
            {"Period": "2026-Q4", "Revenue": "$255,800.00"},
        ],
    }

    return render(
        request,
        "bi/self_service_analytics/saved_analysis_view/explore.html",
        {
            "view_obj": view_obj,
            "query": query,
            "chart_config": chart_config,
            "preview_results": preview_results,
        },
    )
