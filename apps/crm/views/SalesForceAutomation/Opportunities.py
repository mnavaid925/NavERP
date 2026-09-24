"""CRM 1.2 Sales Force Automation — Opportunities views (split from apps/crm/views.py)."""
from django.apps import apps as django_apps
from django.urls import NoReverseMatch

from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmTask,
    Opportunity,
    OpportunitySplit,
    Quote,
    Territory,
)
from apps.crm.forms import (
    OpportunityForm,
    OpportunitySplitForm,
)


_OPP_FLOW = ["prospecting", "qualification", "proposal", "negotiation", "closed_won"]
_UNSPECIFIED_CURRENCY = "Unspecified"


def _sales_model(model_name):
    try:
        return django_apps.get_model("sales", model_name)
    except LookupError:
        return None


def _sales_workspace_url(opportunity):
    if opportunity is None or not opportunity.pk:
        return None
    try:
        return reverse(
            "sales:opportunity_workspace_detail",
            kwargs={"opportunity_pk": opportunity.pk},
        )
    except NoReverseMatch:
        return None


def _sales_placement(opportunity, tenant):
    model = _sales_model("OpportunityPipelinePlacement")
    if model is None or tenant is None or opportunity is None or not opportunity.pk:
        return None
    return (
        model.objects.filter(
            tenant=tenant,
            opportunity_id=opportunity.pk,
        )
        .select_related("current_stage", "pipeline")
        .first()
    )


def _sales_transition_functions():
    try:
        from apps.sales.opportunity_services import (
            sales_allowed_transition_stages,
            sales_transition_opportunity,
        )
    except ImportError:
        return None
    return sales_allowed_transition_stages, sales_transition_opportunity


def _sales_next_open_target(placement, functions=None):
    if functions is None:
        functions = _sales_transition_functions()
    if functions is None:
        return None
    allowed = list(functions[0](placement) or [])
    if not allowed:
        return None
    target = allowed[0]
    return target if getattr(target, "stage_kind", None) == "open" else None


def _sales_workspace_message(prefix, opportunity):
    url = _sales_workspace_url(opportunity)
    if url:
        return f"{prefix} Open the Sales workspace: {url}"
    return f"{prefix} Use the Sales workspace to continue."


def _opportunity_advance_redirect(request, opportunity):
    if request.POST.get("next") == "board":
        return redirect("crm:opportunity_board")
    return redirect("crm:opportunity_detail", pk=opportunity.pk)


def _opportunity_currency_label(opportunity):
    currency = getattr(opportunity, "currency", None)
    code = getattr(currency, "code", None)
    return str(code).strip().upper() if code else _UNSPECIFIED_CURRENCY


def _opportunity_board_currency_rows(base):
    rows_by_stage = {}
    query = (
        base.values("stage", "currency_id", "currency__code")
        .annotate(
            count=Count("id"),
            total=Sum("amount"),
            weighted_sum=Sum(
                F("amount") * F("probability"),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            ),
        )
        .order_by("stage", "currency__code", "currency_id")
    )
    for raw in query:
        label = (str(raw["currency__code"]).strip().upper()
                 if raw["currency__code"] else _UNSPECIFIED_CURRENCY)
        row = {
            "currency_id": raw["currency_id"],
            "currency_code": label,
            "currency_label": label,
            "count": raw["count"] or 0,
            "total": Decimal(raw["total"] or 0),
            "weighted": Decimal(raw["weighted_sum"] or 0) / Decimal(100),
            "amount": Decimal(raw["total"] or 0),
            "weighted_amount": Decimal(raw["weighted_sum"] or 0) / Decimal(100),
        }
        rows_by_stage.setdefault(raw["stage"], []).append(row)
    for rows in rows_by_stage.values():
        rows.sort(key=lambda row: (row["currency_label"] == _UNSPECIFIED_CURRENCY,
                                   row["currency_label"]))
    return rows_by_stage


def _sales_close_required_map(opportunities, tenant):
    if not opportunities or tenant is None:
        return {}
    placement_model = _sales_model("OpportunityPipelinePlacement")
    if placement_model is None:
        return {}
    opportunity_ids = [opportunity.pk for opportunity in opportunities]
    placements = list(
        placement_model.objects.filter(
            tenant=tenant,
            opportunity_id__in=opportunity_ids,
        ).select_related("current_stage")
    )
    if not placements:
        return {}
    stage_model = _sales_model("PipelineStage")
    if stage_model is None:
        return {
            placement.opportunity_id: True
            for placement in placements
            if getattr(placement.current_stage, "stage_kind", None) == "open"
        }
    pipeline_ids = {placement.pipeline_id for placement in placements}
    stages = list(
        stage_model.objects.filter(
            tenant=tenant,
            pipeline_id__in=pipeline_ids,
            is_active=True,
        ).values("id", "pipeline_id", "stage_kind", "sequence")
    )
    stages_by_pipeline = {}
    for stage in stages:
        stages_by_pipeline.setdefault(stage["pipeline_id"], []).append(stage)
    required = {}
    for placement in placements:
        current = getattr(placement, "current_stage", None)
        if current is None or getattr(current, "stage_kind", None) != "open":
            continue
        has_next_open = any(
            stage["stage_kind"] == "open" and stage["sequence"] > current.sequence
            for stage in stages_by_pipeline.get(placement.pipeline_id, [])
        )
        required[placement.opportunity_id] = not has_next_open
    return required


@login_required
def opportunity_list(request):
    return crud_list(
        request,
        Opportunity.objects.filter(tenant=request.tenant).select_related(
            "account", "owner", "territory", "currency"
        ),
        "crm/sales/opportunity/list.html",
        search_fields=["name", "number"],
        filters=[("stage", "stage", False), ("forecast_category", "forecast_category", False),
                 ("account", "account_id", True), ("territory", "territory_id", True)],
        extra_context={"stage_choices": Opportunity.STAGE_CHOICES,
                       "forecast_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name"),
                       "territories": Territory.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def opportunity_create(request):
    return crud_create(request, form_class=OpportunityForm, template="crm/sales/opportunity/form.html",
                       success_url="crm:opportunity_list")


@login_required
def opportunity_detail(request, pk):
    obj = get_object_or_404(
        Opportunity.objects.select_related(
            "account", "primary_contact", "owner", "source_lead", "campaign", "territory", "currency"),
        pk=pk, tenant=request.tenant)
    splits = OpportunitySplit.objects.filter(
        tenant=request.tenant, opportunity=obj).select_related("user")
    rev_total = splits.filter(split_type="revenue").aggregate(t=Sum("percentage"))["t"] or 0
    placement = _sales_placement(obj, request.tenant)
    next_open = _sales_next_open_target(placement) if placement is not None else None
    close_required = bool(placement is not None and obj.is_open and next_open is None)
    return render(request, "crm/sales/opportunity/detail.html", {
        "obj": obj,
        "splits": splits,
        "revenue_split_total": rev_total,
        "split_form": OpportunitySplitForm(tenant=request.tenant),
        "quotes": Quote.objects.filter(tenant=request.tenant, opportunity=obj).select_related("account")[:20],
        "tasks": CrmTask.objects.filter(
            tenant=request.tenant, related_opportunity=obj).select_related("owner")[:20],
        "sales_workspace_url": _sales_workspace_url(obj),
        "opportunity_quick_advance": bool(obj.is_open and (placement is None or next_open is not None)),
        "opportunity_sales_close_required": close_required,
    })


@login_required
def opportunity_edit(request, pk):
    return crud_edit(request, model=Opportunity, pk=pk, form_class=OpportunityForm,
                     template="crm/sales/opportunity/form.html", success_url="crm:opportunity_list")


@login_required
@require_POST
def opportunity_delete(request, pk):
    return crud_delete(request, model=Opportunity, pk=pk, success_url="crm:opportunity_list")


@login_required
def opportunity_board(request):
    """Kanban pipeline board — opportunities grouped into a column per stage with per-stage
    count + amount totals (aggregated DB-side; each column previews its top deals)."""
    base = Opportunity.objects.filter(tenant=request.tenant).select_related(
        "account", "owner", "territory", "currency"
    )
    currency_rows_by_stage = _opportunity_board_currency_rows(base)
    columns = []
    board_opportunities = []
    for value, label in Opportunity.STAGE_CHOICES:
        currency_rows = currency_rows_by_stage.get(value, [])
        opps = list(base.filter(stage=value).order_by("-amount")[:50])
        board_opportunities.extend(opps)
        if len(currency_rows) == 1:
            total = currency_rows[0]["total"]
            weighted = currency_rows[0]["weighted"]
            currency_label = currency_rows[0]["currency_label"]
        elif currency_rows:
            total = None
            weighted = None
            currency_label = "Mixed currencies"
        else:
            total = Decimal(0)
            weighted = Decimal(0)
            currency_label = _UNSPECIFIED_CURRENCY
        columns.append({
            "value": value, "label": label,
            "count": sum(row["count"] for row in currency_rows),
            "total": total,
            "weighted": weighted,
            "currency_label": currency_label,
            "currency_rows": currency_rows,
            "mixed_currency": len(currency_rows) > 1,
            "opps": opps,
        })
    close_required = _sales_close_required_map(board_opportunities, request.tenant)
    for opportunity in board_opportunities:
        opportunity.currency_label = _opportunity_currency_label(opportunity)
        opportunity.sales_close_required = close_required.get(opportunity.pk, False)
        opportunity.sales_workspace_url = (
            _sales_workspace_url(opportunity)
            if opportunity.sales_close_required
            else None
        )
    return render(request, "crm/sales/pipeline.html", {"columns": columns})


@login_required
@require_POST
def opportunity_advance(request, pk):
    """Advance an opportunity one stage along the win path (board/detail quick action)."""
    opp = get_object_or_404(
        Opportunity.objects.filter(tenant=request.tenant).select_related("currency"),
        pk=pk,
    )
    placement = _sales_placement(opp, request.tenant)
    if placement is not None:
        functions = _sales_transition_functions()
        target = _sales_next_open_target(placement, functions) if functions is not None else None
        if target is None:
            messages.info(
                request,
                _sales_workspace_message(
                    "This placement needs a Sales workspace decision before it can advance.",
                    opp,
                ),
            )
            return _opportunity_advance_redirect(request, opp)
        try:
            functions[1](
                opportunity=opp,
                target_stage=target,
                tenant=request.tenant,
                user=request.user,
                notes="",
            )
        except ValidationError as exc:
            detail = " ".join(getattr(exc, "messages", [str(exc)]))[:500]
            messages.error(
                request,
                _sales_workspace_message(
                    f"The Sales transition was not applied: {detail}",
                    opp,
                ),
            )
        else:
            opp.refresh_from_db()
            messages.success(request, f"Advanced to {opp.get_stage_display()}.")
        return _opportunity_advance_redirect(request, opp)
    if opp.stage in _OPP_FLOW and opp.stage != "closed_won":
        opp.stage = _OPP_FLOW[_OPP_FLOW.index(opp.stage) + 1]
        if opp.stage == "closed_won":
            opp.probability = 100
            opp.forecast_category = "closed"
        opp.save()
        write_audit_log(request.user, opp, "update", {"operation": "advance", "stage": opp.stage})
        messages.success(request, f"Advanced to {opp.get_stage_display()}.")
    else:
        messages.info(request, "This opportunity can't be advanced further.")
    return _opportunity_advance_redirect(request, opp)


@login_required
@require_POST
def opportunitysplit_add(request, pk):
    opp = get_object_or_404(Opportunity, pk=pk, tenant=request.tenant)
    form = OpportunitySplitForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "Could not add split — check the fields.")
        return redirect("crm:opportunity_detail", pk=opp.pk)
    split = form.save(commit=False)
    split.tenant = request.tenant
    split.opportunity = opp
    try:
        split.clean()
    except ValidationError as e:
        messages.error(request, "; ".join(e.messages))
        return redirect("crm:opportunity_detail", pk=opp.pk)
    split.save()
    messages.success(request, "Split added.")
    return redirect("crm:opportunity_detail", pk=opp.pk)


@login_required
@require_POST
def opportunitysplit_remove(request, split_pk):
    split = get_object_or_404(OpportunitySplit, pk=split_pk, tenant=request.tenant)
    opp_id = split.opportunity_id
    split.delete()
    messages.success(request, "Split removed.")
    return redirect("crm:opportunity_detail", pk=opp_id)
