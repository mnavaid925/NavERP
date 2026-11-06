from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.PerformanceScorecards.StrategicObjectives import StrategicObjectiveForm
from apps.bi.models.PerformanceScorecards.StrategicObjectives import StrategicObjective
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log


@login_required
def strategic_objective_list(request):
    qs = bi_scope(StrategicObjective.objects.all(), request, owner_field="owner").select_related(
        "parent_objective", "org_unit", "owner"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        achieved=Count("id", filter=Q(status="achieved")),
        on_track=Count("id", filter=Q(rag_status="green")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    achieved_count = counts["achieved"] or 0
    on_track_count = counts["on_track"] or 0

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(statement_of_intent__icontains=q)
        )

    perspective = request.GET.get("perspective", "").strip()
    if perspective:
        qs = qs.filter(perspective=perspective)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    rag_status = request.GET.get("rag_status", "").strip()
    if rag_status:
        qs = qs.filter(rag_status=rag_status)

    org_unit = request.GET.get("org_unit", "").strip()
    if org_unit:
        qs = qs.filter(org_unit_id=org_unit)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    objectives = paginator.get_page(page_number)

    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "objectives": objectives,
        "perspective_choices": StrategicObjective.PERSPECTIVE_CHOICES,
        "status_choices": StrategicObjective.STATUS_CHOICES,
        "rag_choices": StrategicObjective.RAG_STATUS_CHOICES,
        "org_units": org_units,
        "stats": {
            "total": total_count,
            "active": active_count,
            "achieved": achieved_count,
            "on_track": on_track_count,
        },
    }
    return render(request, "bi/kpi_performance_scorecards/strategic_objective/list.html", context)


@login_required
def strategic_objective_detail(request, pk):
    objective = bi_object(
        request,
        StrategicObjective,
        pk,
        select_related=("parent_objective", "org_unit", "owner"),
        prefetch_related=("child_objectives", "scorecard_kpis__kpi", "scorecard_kpis__scorecard"),
    )
    child_objectives = objective.child_objectives.all().order_by("sort_order", "name")
    assigned_kpis = objective.scorecard_kpis.select_related("kpi", "scorecard").order_by("scorecard__name", "kpi__name")

    context = {
        "objective": objective,
        "child_objectives": child_objectives,
        "assigned_kpis": assigned_kpis,
    }
    return render(request, "bi/kpi_performance_scorecards/strategic_objective/detail.html", context)


@login_required
@tenant_admin_required
def strategic_objective_create(request):
    if request.method == "POST":
        form = StrategicObjectiveForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.owner:
                obj.owner = request.user
            obj.save()
            obj.recalculate_alignment()

            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="StrategicObjective",
                object_id=str(obj.pk),
                object_repr=str(obj),
                change_summary=f"Created Strategic Objective {obj.number} ({obj.name})",
            )
            messages.success(request, f"Strategic Objective '{obj.name}' created.")
            return redirect(obj.get_absolute_url())
    else:
        form = StrategicObjectiveForm(tenant=request.tenant)

    context = {
        "form": form,
        "objective": None,
        "is_edit": False,
    }
    return render(request, "bi/kpi_performance_scorecards/strategic_objective/form.html", context)


@login_required
@tenant_admin_required
def strategic_objective_edit(request, pk):
    obj = bi_object(request, StrategicObjective, pk)
    if request.method == "POST":
        form = StrategicObjectiveForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            obj.recalculate_alignment()

            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="StrategicObjective",
                object_id=str(obj.pk),
                object_repr=str(obj),
                change_summary=f"Updated Strategic Objective {obj.number} ({obj.name})",
            )
            messages.success(request, f"Strategic Objective '{obj.name}' updated.")
            return redirect(obj.get_absolute_url())
    else:
        form = StrategicObjectiveForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "objective": obj,
        "is_edit": True,
    }
    return render(request, "bi/kpi_performance_scorecards/strategic_objective/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def strategic_objective_delete(request, pk):
    obj = bi_object(request, StrategicObjective, pk)
    obj_name = obj.name
    obj_num = obj.number
    obj.delete()

    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="StrategicObjective",
        object_id=str(pk),
        object_repr=f"{obj_num} - {obj_name}",
        change_summary=f"Deleted Strategic Objective {obj_num} ({obj_name})",
    )
    messages.success(request, f"Strategic Objective '{obj_name}' deleted.")
    return redirect("bi:strategic_objective_list")
