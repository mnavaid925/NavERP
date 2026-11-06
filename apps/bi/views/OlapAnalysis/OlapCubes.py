from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.OlapAnalysis.OlapCubes import OlapCubeForm
from apps.bi.models.OlapAnalysis.OlapCubes import OlapCube
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def olap_cube_list(request):
    qs = bi_scope(OlapCube.objects.all(), request, owner_field="created_by").select_related(
        "semantic_model", "warehouse_table", "default_hierarchy", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        rolap=Count("id", filter=Q(storage_mode="rolap")),
        rollup=Count("id", filter=Q(storage_mode="summary_rollup")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    rolap_count = counts["rolap"] or 0
    rollup_count = counts["rollup"] or 0

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    storage_mode = request.GET.get("storage_mode", "").strip()
    if storage_mode:
        qs = qs.filter(storage_mode=storage_mode)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "bi/olap_analysis/olap_cube/list.html",
        {
            "cubes": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "active_count": active_count,
            "rolap_count": rolap_count,
            "rollup_count": rollup_count,
            "storage_mode_choices": OlapCube.STORAGE_MODE_CHOICES,
            "status_choices": OlapCube.STATUS_CHOICES,
        },
    )


@login_required
def olap_cube_detail(request, pk):
    cube = bi_object(
        request,
        OlapCube,
        pk,
        select_related=["semantic_model", "warehouse_table", "default_hierarchy", "created_by"],
    )
    pivot_views = cube.pivot_views.filter(tenant=request.tenant).order_by("-created_at")[:10]
    scenarios = cube.scenarios.filter(tenant=request.tenant).order_by("-created_at")[:10]

    return render(
        request,
        "bi/olap_analysis/olap_cube/detail.html",
        {
            "cube": cube,
            "pivot_views": pivot_views,
            "scenarios": scenarios,
        },
    )


@login_required
def olap_cube_create(request):
    if request.method == "POST":
        form = OlapCubeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cube = form.save(commit=False)
            cube.tenant = request.tenant
            cube.created_by = request.user
            cube.save()
            write_audit_log(request.user, "create", cube, {"name": cube.name, "number": cube.number})
            messages.success(request, f"OLAP Cube '{cube.name}' ({cube.number}) created successfully.")
            return redirect("bi:olap_cube_detail", pk=cube.pk)
    else:
        form = OlapCubeForm(tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/olap_cube/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def olap_cube_edit(request, pk):
    cube = bi_object(request, OlapCube, pk)
    if request.method == "POST":
        form = OlapCubeForm(request.POST, instance=cube, tenant=request.tenant)
        if form.is_valid():
            cube = form.save()
            write_audit_log(request.user, "update", cube, {"name": cube.name, "number": cube.number})
            messages.success(request, f"OLAP Cube '{cube.name}' updated successfully.")
            return redirect("bi:olap_cube_detail", pk=cube.pk)
    else:
        form = OlapCubeForm(instance=cube, tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/olap_cube/form.html",
        {
            "form": form,
            "cube": cube,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def olap_cube_delete(request, pk):
    cube = bi_object(request, OlapCube, pk)
    name = cube.name
    number = cube.number
    cube.delete()
    write_audit_log(request.user, "delete", cube, {"name": name, "number": number})
    messages.success(request, f"OLAP Cube '{name}' ({number}) deleted successfully.")
    return redirect("bi:olap_cube_list")


@login_required
@require_POST
def olap_cube_refresh(request, pk):
    cube = bi_object(request, OlapCube, pk)
    cube.last_refreshed_at = timezone.now()
    cube.save(update_fields=["last_refreshed_at", "updated_at"])
    write_audit_log(request.user, "refresh", cube, {"last_refreshed_at": str(cube.last_refreshed_at)})
    messages.success(request, f"OLAP Cube '{cube.name}' aggregations refreshed successfully.")
    return redirect("bi:olap_cube_detail", pk=cube.pk)
