from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import FieldDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity, Territory
from apps.sales.forms.OpportunityPipeline.Pipelines import (
    PipelineForm,
    PipelineStageForm,
    PipelineStageOrderForm,
)
from apps.sales.models.OpportunityPipeline.Pipelines import (
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
)
from apps.sales.opportunity_analytics import (
    SALES_HEALTH_CHOICES,
    opportunity_pipeline_health_projection,
    sales_pipeline_currency_totals,
    sales_pipeline_rollups,
    sales_stage_age_rows,
)
from apps.sales.opportunity_services import (
    sales_create_pipeline,
    sales_delete_pipeline_stage,
    sales_reorder_pipeline_stages,
    sales_save_pipeline,
    sales_save_pipeline_stage,
    sales_set_default_pipeline,
)


OPPORTUNITY_PIPELINE_ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]


def _opportunity_pipeline_is_admin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def _opportunity_pipeline_int(value):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 < parsed <= 9223372036854775807 else None


def _opportunity_pipeline_validation_message(exc):
    return " ".join(exc.messages)


@login_required
def opportunity_pipeline_list(request):
    queryset = Pipeline.objects.filter(tenant=request.tenant)
    q = request.GET.get("q", "").strip()[:200]
    active = request.GET.get("active", "").strip().lower()
    if q:
        queryset = queryset.filter(Q(name__icontains=q) | Q(number__icontains=q) | Q(description__icontains=q))
    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)
    else:
        active = ""
    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    stats = Pipeline.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        default=Count("id", filter=Q(is_active=True, is_default=True)),
    )
    return render(
        request,
        "sales/opportunity/pipeline/list.html",
        {
            "object_list": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "active": active,
            "active_choices": OPPORTUNITY_PIPELINE_ACTIVE_CHOICES,
            "stats": stats,
        },
    )


@tenant_admin_required
def opportunity_pipeline_create(request):
    form = PipelineForm(
        request.POST if request.method == "POST" else None,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        try:
            pipeline = sales_create_pipeline(request.tenant, form.cleaned_data, request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Pipeline created with its baseline stages.")
            return redirect("sales:opportunity_pipeline_detail", pk=pipeline.pk)
    return render(
        request,
        "sales/opportunity/pipeline/form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def opportunity_pipeline_detail(request, pk):
    obj = get_object_or_404(
        Pipeline.objects.prefetch_related("stages"),
        pk=pk,
        tenant=request.tenant,
    )
    stages = list(obj.stages.all())
    placement_count = obj.placements.count()
    open_placement_count = obj.placements.filter(current_stage__stage_kind="open").count()
    return render(
        request,
        "sales/opportunity/pipeline/detail.html",
        {
            "obj": obj,
            "stages": stages,
            "placement_count": placement_count,
            "open_placement_count": open_placement_count,
            "can_edit": _opportunity_pipeline_is_admin(request.user),
        },
    )


@tenant_admin_required
def opportunity_pipeline_edit(request, pk):
    obj = get_object_or_404(Pipeline, pk=pk, tenant=request.tenant)
    form = PipelineForm(
        request.POST if request.method == "POST" else None,
        instance=obj,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        try:
            sales_save_pipeline(obj, request.tenant, request.user, form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Pipeline updated.")
            return redirect("sales:opportunity_pipeline_detail", pk=obj.pk)
    return render(
        request,
        "sales/opportunity/pipeline/form.html",
        {"form": form, "is_edit": True, "obj": obj},
    )


@require_POST
@tenant_admin_required
def opportunity_pipeline_delete(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(
            Pipeline.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        try:
            with transaction.atomic():
                write_audit_log(
                    request.user,
                    obj,
                    "delete",
                    {"operation": "delete_pipeline"},
                    tenant=request.tenant,
                )
                obj.delete()
        except ValidationError as exc:
            messages.error(request, _opportunity_pipeline_validation_message(exc))
        else:
            messages.success(request, "Pipeline deleted.")
    return redirect("sales:opportunity_pipeline_list")


@login_required
def opportunity_pipeline_stages(request, pk):
    pipeline = get_object_or_404(Pipeline, pk=pk, tenant=request.tenant)
    stages = list(pipeline.stages.all())
    reorder_form = PipelineStageOrderForm(
        request.POST if request.method == "POST" else None,
        tenant=request.tenant,
        pipeline=pipeline,
    )
    if request.method == "POST":
        if not _opportunity_pipeline_is_admin(request.user):
            raise PermissionDenied("Tenant administrator access required.")
        if reorder_form.is_valid():
            try:
                sales_reorder_pipeline_stages(
                    pipeline,
                    request.tenant,
                    request.user,
                    reorder_form.cleaned_data["ordered_stage_ids"],
                )
            except ValidationError as exc:
                messages.error(request, _opportunity_pipeline_validation_message(exc))
            else:
                messages.success(request, "Pipeline stage order updated.")
                return redirect("sales:opportunity_pipeline_stages", pk=pipeline.pk)
        else:
            messages.error(request, "Choose every pipeline stage exactly once.")
    return render(
        request,
        "sales/opportunity/pipeline/stages.html",
        {
            "pipeline": pipeline,
            "stages": stages,
            "stage_form": PipelineStageForm(tenant=request.tenant, pipeline=pipeline),
            "reorder_form": reorder_form,
            "stage_kind_choices": PipelineStage.STAGE_KIND_CHOICES,
            "crm_stage_choices": PipelineStage.CRM_STAGE_KEY_CHOICES,
            "forecast_choices": PipelineStage.FORECAST_CATEGORY_CHOICES,
        },
    )


def _opportunity_pipeline_stage_editor(request, pipeline, stage=None):
    is_edit = stage is not None
    form = PipelineStageForm(
        request.POST if request.method == "POST" else None,
        instance=stage,
        tenant=request.tenant,
        pipeline=pipeline,
    )
    if request.method == "POST" and form.is_valid():
        try:
            sales_save_pipeline_stage(
                stage or PipelineStage(),
                request.tenant,
                request.user,
                form.cleaned_data,
                pipeline=pipeline,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Pipeline stage saved.")
            return redirect("sales:opportunity_pipeline_stages", pk=pipeline.pk)
    return render(
        request,
        "sales/opportunity/pipeline/form.html",
        {
            "form": form,
            "is_edit": is_edit,
            "pipeline": pipeline,
            "stage": stage,
            "stages": list(pipeline.stages.all()),
            "stage_kind_choices": PipelineStage.STAGE_KIND_CHOICES,
            "crm_stage_choices": PipelineStage.CRM_STAGE_KEY_CHOICES,
            "forecast_choices": PipelineStage.FORECAST_CATEGORY_CHOICES,
        },
    )


@tenant_admin_required
def opportunity_pipeline_stage_create(request, pk):
    pipeline = get_object_or_404(Pipeline, pk=pk, tenant=request.tenant)
    return _opportunity_pipeline_stage_editor(request, pipeline)


@tenant_admin_required
def opportunity_pipeline_stage_edit(request, pk, stage_pk):
    pipeline = get_object_or_404(Pipeline, pk=pk, tenant=request.tenant)
    stage = get_object_or_404(
        PipelineStage,
        pk=stage_pk,
        pipeline=pipeline,
        tenant=request.tenant,
    )
    return _opportunity_pipeline_stage_editor(request, pipeline, stage=stage)


@require_POST
@tenant_admin_required
def opportunity_pipeline_stage_delete(request, pk, stage_pk):
    pipeline = get_object_or_404(Pipeline, pk=pk, tenant=request.tenant)
    stage = get_object_or_404(
        PipelineStage,
        pk=stage_pk,
        pipeline=pipeline,
        tenant=request.tenant,
    )
    try:
        sales_delete_pipeline_stage(stage, request.tenant, request.user)
    except ValidationError as exc:
        messages.error(request, _opportunity_pipeline_validation_message(exc))
    else:
        messages.success(request, "Pipeline stage deleted.")
    return redirect("sales:opportunity_pipeline_stages", pk=pipeline.pk)


@require_POST
@tenant_admin_required
def opportunity_pipeline_stage_reorder(request, pk):
    pipeline = get_object_or_404(Pipeline, pk=pk, tenant=request.tenant)
    form = PipelineStageOrderForm(request.POST, tenant=request.tenant, pipeline=pipeline)
    if not form.is_valid():
        messages.error(request, "Choose every pipeline stage exactly once.")
        return redirect("sales:opportunity_pipeline_stages", pk=pipeline.pk)
    try:
        sales_reorder_pipeline_stages(
            pipeline,
            request.tenant,
            request.user,
            form.cleaned_data["ordered_stage_ids"],
        )
    except ValidationError as exc:
        messages.error(request, _opportunity_pipeline_validation_message(exc))
    else:
        messages.success(request, "Pipeline stage order updated.")
    return redirect("sales:opportunity_pipeline_stages", pk=pipeline.pk)


@require_POST
@tenant_admin_required
def opportunity_pipeline_set_default(request, pk):
    pipeline = get_object_or_404(Pipeline, pk=pk, tenant=request.tenant)
    try:
        sales_set_default_pipeline(pipeline, request.tenant, request.user)
    except ValidationError as exc:
        messages.error(request, _opportunity_pipeline_validation_message(exc))
    else:
        messages.success(request, "Default pipeline updated.")
    return redirect("sales:opportunity_pipeline_detail", pk=pipeline.pk)


def _opportunity_pipeline_filtered_placements(
    tenant,
    pipeline,
    owner_id,
    territory_id,
    currency,
):
    if tenant is None or pipeline is None:
        return OpportunityPipelinePlacement.objects.none()
    queryset = OpportunityPipelinePlacement.objects.filter(
        tenant=tenant,
        pipeline=pipeline,
    ).select_related(
        "current_stage",
        "opportunity",
        "opportunity__owner",
        "opportunity__territory",
        "opportunity__account",
        "opportunity__currency",
    )
    if owner_id is not None:
        queryset = queryset.filter(opportunity__owner_id=owner_id)
    if territory_id is not None:
        queryset = queryset.filter(opportunity__territory_id=territory_id)
    if currency:
        if currency == "__unspecified__":
            queryset = queryset.filter(opportunity__currency__isnull=True)
        else:
            queryset = queryset.filter(opportunity__currency__code=currency)
    return queryset.order_by("-opportunity__amount", "opportunity_id")


def _opportunity_pipeline_unplaced_opportunities(tenant, owner_id, territory_id, currency):
    if tenant is None:
        return Opportunity.objects.none()
    queryset = Opportunity.objects.filter(
        tenant=tenant,
        stage__in=Opportunity.OPEN_STAGES,
    ).exclude(sales_pipeline_placement__isnull=False)
    if owner_id is not None:
        queryset = queryset.filter(owner_id=owner_id)
    if territory_id is not None:
        queryset = queryset.filter(territory_id=territory_id)
    if currency:
        try:
            Opportunity._meta.get_field("currency")
        except FieldDoesNotExist:
            if currency != "__unspecified__":
                return Opportunity.objects.none()
        else:
            if currency == "__unspecified__":
                queryset = queryset.filter(currency__isnull=True)
            else:
                queryset = queryset.filter(currency__code=currency)
    return queryset.select_related("owner", "territory", "account").order_by("-amount", "number")[:100]


def _opportunity_pipeline_summary_rows(tenant, pipelines, owner_id, territory_id, currency):
    rollups = sales_pipeline_rollups(
        tenant,
        owner_id=owner_id,
        territory_id=territory_id,
        currency=currency,
    )
    pipeline_map = {pipeline.pk: pipeline for pipeline in pipelines}
    rows = {}
    for rollup in rollups:
        if rollup["pipeline_id"] not in pipeline_map:
            continue
        row = rows.setdefault(
            rollup["pipeline_id"],
            {
                "pipeline_id": rollup["pipeline_id"],
                "pipeline_name": rollup["pipeline_name"],
                "is_default": pipeline_map[rollup["pipeline_id"]].is_default,
                "count": 0,
                "open_count": 0,
                "won_count": 0,
                "lost_count": 0,
                "amount": Decimal("0"),
                "weighted_amount": Decimal("0"),
                "currencies": set(),
                "mixed_currencies": False,
            },
        )
        row["count"] += rollup["count"]
        if rollup["stage_kind"] == "open":
            row["open_count"] += rollup["count"]
        elif rollup["stage_kind"] == "won":
            row["won_count"] += rollup["count"]
        elif rollup["stage_kind"] == "lost":
            row["lost_count"] += rollup["count"]
        row["currencies"].add(rollup["currency_code"])
        if len(row["currencies"]) == 1:
            row["amount"] = Decimal(row["amount"]) + rollup["amount"]
            row["weighted_amount"] = Decimal(row["weighted_amount"]) + rollup["weighted_amount"]
    for row in rows.values():
        row["currencies"] = sorted(row["currencies"])
        row["mixed_currencies"] = len(row["currencies"]) > 1
        if row["mixed_currencies"]:
            row["amount"] = None
            row["weighted_amount"] = None
    return [rows[pipeline_id] for pipeline_id in sorted(rows, key=lambda value: pipeline_map[value].name)]


def _opportunity_pipeline_board_context(request):
    tenant = request.tenant
    pipelines = list(
        Pipeline.objects.filter(tenant=tenant, is_active=True).order_by("-is_default", "name")
    )
    pipeline_id = _opportunity_pipeline_int(request.GET.get("pipeline"))
    selected_pipeline = next(
        (pipeline for pipeline in pipelines if pipeline.pk == pipeline_id),
        None,
    )
    if selected_pipeline is None and pipelines:
        selected_pipeline = pipelines[0]
        pipeline_id = selected_pipeline.pk
    owner_id = _opportunity_pipeline_int(request.GET.get("owner"))
    territory_id = _opportunity_pipeline_int(request.GET.get("territory"))
    owner_ids = Opportunity.objects.filter(tenant=tenant).exclude(owner_id=None).values_list("owner_id", flat=True)
    owner_users = list(
        User.objects.filter(tenant=tenant, is_active=True, pk__in=owner_ids).order_by("email")
    )
    territories = list(
        Territory.objects.filter(tenant=tenant, is_active=True).order_by("name")
    )
    currency_totals = sales_pipeline_currency_totals(
        tenant,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
        territory_id=territory_id,
    )
    available_currencies = {row["filter_value"] for row in currency_totals}
    raw_currency = request.GET.get("currency", "").strip()[:20]
    currency = raw_currency if raw_currency in available_currencies else ""
    health = request.GET.get("health", "").strip().lower()
    if health not in dict(SALES_HEALTH_CHOICES):
        health = ""
    as_of = timezone.now()
    placements = list(
        _opportunity_pipeline_filtered_placements(
            tenant,
            selected_pipeline,
            owner_id,
            territory_id,
            currency,
        )
    )
    opportunities = [placement.opportunity for placement in placements]
    health_projection = opportunity_pipeline_health_projection(
        tenant,
        opportunities,
        placements,
        as_of=as_of,
    )
    health_counts = {"on_track": 0, "watch": 0, "at_risk": 0}
    for health_row in health_projection.values():
        health_counts[health_row["status"]] += 1
    stage_age_rows = sales_stage_age_rows(
        tenant,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
        territory_id=territory_id,
        currency=currency,
        as_of=as_of,
    )
    stage_age_by_opportunity = {
        row["opportunity_id"]: row for row in stage_age_rows
    }
    cards_by_stage = {}
    for placement in placements:
        health_row = health_projection[placement.opportunity_id]
        if health and health_row["status"] != health:
            continue
        age_row = stage_age_by_opportunity.get(placement.opportunity_id, {})
        card = {
            "placement": placement,
            "opportunity": placement.opportunity,
            "health": health_row,
            "effective_probability": placement.effective_probability,
            "weighted_amount": Decimal(placement.opportunity.amount or 0)
            * placement.effective_probability
            / 100,
            "stage_age_days": age_row.get("stage_age_days", 0),
            "is_stale": age_row.get("is_stale", False),
            "currency_label": getattr(
                getattr(placement.opportunity, "currency", None),
                "code",
                "Unspecified",
            ),
        }
        cards_by_stage.setdefault(placement.current_stage_id, []).append(card)
    columns = []
    if selected_pipeline is not None:
        for stage in PipelineStage.objects.filter(
            tenant=tenant,
            pipeline=selected_pipeline,
            is_active=True,
        ).order_by("sequence", "pk"):
            cards = cards_by_stage.get(stage.pk, [])
            card_currencies = {card["currency_label"] for card in cards}
            if len(card_currencies) > 1:
                amount = None
                weighted_amount = None
            else:
                amount = sum(
                    (Decimal(card["opportunity"].amount or 0) for card in cards),
                    Decimal("0"),
                )
                weighted_amount = sum(
                    (Decimal(card["weighted_amount"]) for card in cards),
                    Decimal("0"),
                )
            columns.append(
                {
                    "stage": stage,
                    "stage_id": stage.pk,
                    "label": stage.name,
                    "value": stage.code,
                    "sequence": stage.sequence,
                    "count": len(cards),
                    "amount": amount,
                    "weighted_amount": weighted_amount,
                    "stale_count": sum(1 for card in cards if card["is_stale"]),
                    "opportunities": cards,
                }
            )
    return {
        "pipelines": pipelines,
        "selected_pipeline": selected_pipeline,
        "columns": columns,
        "unplaced_opportunities": _opportunity_pipeline_unplaced_opportunities(
            tenant,
            owner_id,
            territory_id,
            currency,
        ),
        "summary_rows": _opportunity_pipeline_summary_rows(
            tenant,
            pipelines,
            owner_id,
            territory_id,
            currency,
        ),
        "currency_totals": currency_totals,
        "health_counts": health_counts,
        "owner_users": owner_users,
        "territories": territories,
        "health_choices": SALES_HEALTH_CHOICES,
        "pipeline_id": pipeline_id,
        "owner_id": owner_id,
        "territory_id": territory_id,
        "health": health,
        "currency": currency,
    }


@login_required
def opportunity_pipeline_board(request):
    return render(
        request,
        "sales/opportunity/pipeline/board.html",
        _opportunity_pipeline_board_context(request),
    )


@login_required
def opportunity_pipeline_visibility(request):
    context = _opportunity_pipeline_board_context(request)
    date_from = parse_date(request.GET.get("date_from", ""))
    date_to = parse_date(request.GET.get("date_to", ""))
    context.update(
        {
            "stage_age_rows": sales_stage_age_rows(
                request.tenant,
                pipeline_id=context["pipeline_id"],
                owner_id=context["owner_id"],
                territory_id=context["territory_id"],
                currency=context["currency"],
                health=context["health"],
                date_from=date_from,
                date_to=date_to,
            ),
            "win_loss_rows": [],
            "competitor_rows": [],
            "date_from": date_from,
            "date_to": date_to,
        }
    )
    return render(
        request,
        "sales/opportunity/pipeline/visibility.html",
        context,
    )
