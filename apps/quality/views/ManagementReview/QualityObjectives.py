import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.quality.forms.ManagementReview.QualityObjectives import (
    QualityObjectiveEvaluateForm,
    QualityObjectiveForm,
)
from apps.quality.models.ManagementReview.QualityObjectives import QualityObjective
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

User = get_user_model()
PAGE_SIZE = 15


@login_required
def quality_objective_list(request):
    qs = quality_scope(QualityObjective.objects.all(), request).select_related("owner", "org_unit")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(action_plan_summary__icontains=q)
        )

    category_filter = request.GET.get("category", "").strip()
    if category_filter:
        qs = qs.filter(category=category_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    rag_filter = request.GET.get("rag_status", "").strip()
    if rag_filter:
        qs = qs.filter(rag_status=rag_filter)

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_filter))

    owner_filter = request.GET.get("owner", "").strip()
    if owner_filter and owner_filter.isdigit():
        qs = qs.filter(owner_id=int(owner_filter))

    year_filter = request.GET.get("year", "").strip()
    if year_filter and year_filter.isdigit():
        qs = qs.filter(period_year=int(year_filter))

    base_tenant_qs = QualityObjective.objects.filter(tenant=request.tenant)
    stats = base_tenant_qs.aggregate(
        on_track_count=Count("id", filter=Q(rag_status="green") | Q(status__in=["on_track", "achieved"])),
        at_risk_count=Count("id", filter=Q(rag_status="amber") | Q(status="at_risk")),
        behind_count=Count("id", filter=Q(rag_status="red") | Q(status="behind")),
    )
    on_track_count = stats["on_track_count"]
    at_risk_count = stats["at_risk_count"]
    behind_count = stats["behind_count"]

    paginator = Paginator(qs, PAGE_SIZE)
    total_count = paginator.count
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    filter_querystring = query_params.urlencode()

    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
    owners = User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name", "username")

    context = {
        "objectives": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_querystring": filter_querystring,
        "total_count": total_count,
        "on_track_count": on_track_count,
        "at_risk_count": at_risk_count,
        "behind_count": behind_count,
        "category_choices": QualityObjective.CATEGORY_CHOICES,
        "status_choices": QualityObjective.STATUS_CHOICES,
        "rag_choices": QualityObjective.RAG_STATUS_CHOICES,
        "org_units": org_units,
        "owners": owners,
        "q": q,
        "selected_category": category_filter,
        "selected_status": status_filter,
        "selected_rag": rag_filter,
        "selected_org_unit": org_unit_filter,
        "selected_owner": owner_filter,
        "selected_year": year_filter,
    }
    return render(request, "quality/managementreview/quality_objective/list.html", context)


@login_required
def quality_objective_detail(request, pk):
    objective = quality_object(request, QualityObjective, pk, select_related=("owner", "org_unit"))
    evaluate_form = QualityObjectiveEvaluateForm(initial={"current_value": objective.current_value})

    is_owner_or_admin = (
        request.user.is_superuser
        or getattr(request.user, "is_tenant_admin", False)
        or getattr(request.user, "is_staff", False)
        or (objective.owner_id and objective.owner_id == request.user.id)
    )
    can_evaluate = is_owner_or_admin and objective.status not in ["draft", "abandoned"]

    context = {
        "objective": objective,
        "variance": objective.variance,
        "is_achieved": objective.is_achieved,
        "evaluate_form": evaluate_form,
        "can_evaluate": can_evaluate,
    }
    return render(request, "quality/managementreview/quality_objective/detail.html", context)


@login_required
def quality_objective_create(request):
    if request.method == "POST":
        form = QualityObjectiveForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                if obj.current_value is not None:
                    obj.evaluate_performance()
                    obj.save()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Quality Objective {obj.number} created successfully.")
            return redirect("quality:quality_objective_detail", pk=obj.pk)
    else:
        form = QualityObjectiveForm(tenant=request.tenant, initial={"period_year": timezone.now().year})

    context = {
        "form": form,
        "objective": None,
        "is_edit": False,
    }
    return render(request, "quality/managementreview/quality_objective/form.html", context)


@login_required
def quality_objective_edit(request, pk):
    objective = quality_object(request, QualityObjective, pk)
    if request.method == "POST":
        form = QualityObjectiveForm(request.POST, instance=objective, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                if obj.current_value is not None:
                    obj.evaluate_performance()
                    obj.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Quality Objective {obj.number} updated successfully.")
            return redirect("quality:quality_objective_detail", pk=obj.pk)
    else:
        form = QualityObjectiveForm(instance=objective, tenant=request.tenant)

    context = {
        "form": form,
        "objective": objective,
        "is_edit": True,
    }
    return render(request, "quality/managementreview/quality_objective/form.html", context)


@login_required
@require_POST
def quality_objective_delete(request, pk):
    objective = quality_object(request, QualityObjective, pk)
    number = objective.number
    with transaction.atomic():
        write_audit_log(request.user, objective, "delete", tenant=request.tenant)
        objective.delete()
    messages.success(request, f"Quality Objective {number} has been deleted.")
    return redirect("quality:quality_objective_list")


@login_required
@require_POST
def quality_objective_evaluate(request, pk):
    objective = quality_object(request, QualityObjective, pk)
    if objective.status in ["draft", "abandoned"]:
        messages.error(request, f"Cannot evaluate a {objective.get_status_display().lower()} quality objective.")
        return redirect("quality:quality_objective_detail", pk=objective.pk)

    is_owner_or_admin = (
        request.user.is_superuser
        or getattr(request.user, "is_tenant_admin", False)
        or getattr(request.user, "is_staff", False)
        or (objective.owner_id and objective.owner_id == request.user.id)
    )
    if not is_owner_or_admin:
        messages.error(request, "Only the designated objective owner or quality administrator can evaluate performance.")
        return redirect("quality:quality_objective_detail", pk=objective.pk)

    form = QualityObjectiveEvaluateForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            objective.current_value = form.cleaned_data["current_value"]
            notes_update = form.cleaned_data.get("notes", "").strip()
            if notes_update:
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
                objective.notes = f"{objective.notes}\n[{timestamp}] Evaluation: {notes_update}".strip()
            objective.evaluate_performance()
            objective.save()
            write_audit_log(request.user, objective, "update", tenant=request.tenant)
        messages.success(request, f"Objective {objective.number} performance evaluated: {objective.get_rag_status_display()}.")
    else:
        messages.error(request, "Invalid performance value provided.")
    return redirect("quality:quality_objective_detail", pk=objective.pk)


@login_required
def quality_objective_export_csv(request):
    qs = quality_scope(QualityObjective.objects.all(), request).select_related("owner", "org_unit")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="quality_objectives.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Objective Number",
        "Title",
        "Category",
        "Planning Year",
        "Cadence",
        "Target Direction",
        "Baseline Value",
        "Target Value",
        "Current Value",
        "Unit",
        "Status",
        "RAG Status",
        "Owner",
        "Org Unit",
        "Target Date",
        "Last Evaluated Date",
    ])

    for obj in qs:
        writer.writerow([
            _csv_safe(obj.number),
            _csv_safe(obj.title),
            _csv_safe(obj.get_category_display()),
            _csv_safe(obj.period_year),
            _csv_safe(obj.get_cadence_display()),
            _csv_safe(obj.get_target_direction_display()),
            _csv_safe(obj.baseline_value),
            _csv_safe(obj.target_value),
            _csv_safe(obj.current_value),
            _csv_safe(obj.metric_unit),
            _csv_safe(obj.get_status_display()),
            _csv_safe(obj.get_rag_status_display()),
            _csv_safe(obj.owner.get_full_name() or obj.owner.username if obj.owner else ""),
            _csv_safe(obj.org_unit.name if obj.org_unit else ""),
            _csv_safe(obj.target_date),
            _csv_safe(obj.last_evaluated_date),
        ])

    return response
