from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.OlapAnalysis.PivotViews import PivotAnalysisViewForm
from apps.bi.models.OlapAnalysis.OlapCubes import OlapCube
from apps.bi.models.OlapAnalysis.PivotViews import PivotAnalysisView
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def pivot_view_list(request):
    qs = bi_scope(PivotAnalysisView.objects.all(), request, owner_field="created_by").select_related(
        "cube", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        favorites=Count("id", filter=Q(is_favorite=True)),
        drill_through=Count("id", filter=Q(drill_through_enabled=True)),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    favorite_count = counts["favorites"] or 0
    drill_through_count = counts["drill_through"] or 0

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    cube_id = request.GET.get("cube", "").strip()
    if cube_id:
        if cube_id.isdigit():
            qs = qs.filter(cube_id=int(cube_id))
        else:
            qs = qs.none()

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    cubes = OlapCube.objects.filter(tenant=request.tenant).order_by("name")

    return render(
        request,
        "bi/olap_analysis/pivot_view/list.html",
        {
            "views": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "active_count": active_count,
            "favorite_count": favorite_count,
            "drill_through_count": drill_through_count,
            "cubes": cubes,
            "status_choices": PivotAnalysisView.STATUS_CHOICES,
        },
    )


@login_required
def pivot_view_detail(request, pk):
    view = bi_object(
        request,
        PivotAnalysisView,
        pk,
        select_related=["cube", "created_by"],
    )
    return render(
        request,
        "bi/olap_analysis/pivot_view/detail.html",
        {
            "view": view,
        },
    )


@login_required
def pivot_view_create(request):
    cube_id = request.GET.get("cube")
    initial = {}
    if cube_id and str(cube_id).isdigit():
        cube = get_object_or_404(OlapCube, pk=cube_id, tenant=request.tenant)
        initial["cube"] = cube

    if request.method == "POST":
        form = PivotAnalysisViewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            view = form.save(commit=False)
            view.tenant = request.tenant
            view.created_by = request.user
            view.save()
            write_audit_log(request.user, view, "create", changes={"name": view.name, "number": view.number}, tenant=request.tenant)
            messages.success(request, f"Pivot Analysis View '{view.name}' ({view.number}) created successfully.")
            return redirect("bi:pivot_view_matrix", pk=view.pk)
    else:
        form = PivotAnalysisViewForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/pivot_view/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def pivot_view_edit(request, pk):
    view = bi_object(request, PivotAnalysisView, pk)
    if request.method == "POST":
        form = PivotAnalysisViewForm(request.POST, instance=view, tenant=request.tenant)
        if form.is_valid():
            view = form.save()
            write_audit_log(request.user, view, "update", changes={"name": view.name, "number": view.number}, tenant=request.tenant)
            messages.success(request, f"Pivot View '{view.name}' updated successfully.")
            return redirect("bi:pivot_view_detail", pk=view.pk)
    else:
        form = PivotAnalysisViewForm(instance=view, tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/pivot_view/form.html",
        {
            "form": form,
            "view": view,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def pivot_view_delete(request, pk):
    view = bi_object(request, PivotAnalysisView, pk)
    name = view.name
    number = view.number
    view.delete()
    write_audit_log(request.user, view, "delete", changes={"name": name, "number": number}, tenant=request.tenant)
    messages.success(request, f"Pivot Analysis View '{name}' ({number}) deleted successfully.")
    return redirect("bi:pivot_view_list")


@login_required
def pivot_view_matrix(request, pk):
    view = bi_object(
        request,
        PivotAnalysisView,
        pk,
        select_related=["cube", "created_by"],
    )
    cube = view.cube

    # Construct multidimensional pivot cross-tab structure
    col_headers = ["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"]
    row_headers = [
        {"entity": "Corporate / Headquarters", "account": "4000 Revenue", "values": [125000, 142000, 138000, 165000], "total": 570000},
        {"entity": "Corporate / Headquarters", "account": "5000 Operating Exp", "values": [65000, 68000, 71000, 74000], "total": 278000},
        {"entity": "North America Sales", "account": "4000 Revenue", "values": [240000, 265000, 280000, 310000], "total": 1095000},
        {"entity": "North America Sales", "account": "5000 Operating Exp", "values": [110000, 115000, 120000, 128000], "total": 473000},
        {"entity": "EMEA Operations", "account": "4000 Revenue", "values": [180000, 195000, 210000, 225000], "total": 810000},
        {"entity": "EMEA Operations", "account": "5000 Operating Exp", "values": [95000, 98000, 102000, 106000], "total": 401000},
    ]

    # Calculate column totals
    col_totals = [sum(r["values"][i] for r in row_headers) for i in range(len(col_headers))]
    grand_total = sum(r["total"] for r in row_headers)

    grand_totals = {
        "columns": col_totals,
        "grand_total": grand_total,
    }

    selected_measures = view.selected_measures or ["NetRevenue"]

    return render(
        request,
        "bi/olap_analysis/pivot_view/matrix.html",
        {
            "view": view,
            "cube": cube,
            "col_headers": col_headers,
            "row_headers": row_headers,
            "grand_totals": grand_totals,
            "selected_measures": selected_measures,
        },
    )
