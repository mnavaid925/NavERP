"""CRM 1.2 Sales Force Automation — Opportunities views (split from apps/crm/views.py)."""
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


# Forward-only stage flow used by the board's quick-advance button.
_OPP_FLOW = ["prospecting", "qualification", "proposal", "negotiation", "closed_won"]


# ------------------------------------------------------------ Opportunities (1.2)
@login_required
def opportunity_list(request):
    return crud_list(
        request,
        Opportunity.objects.filter(tenant=request.tenant).select_related("account", "owner", "territory"),
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
            "account", "primary_contact", "owner", "source_lead", "campaign", "territory"),
        pk=pk, tenant=request.tenant)
    splits = OpportunitySplit.objects.filter(
        tenant=request.tenant, opportunity=obj).select_related("user")
    rev_total = splits.filter(split_type="revenue").aggregate(t=Sum("percentage"))["t"] or 0
    return render(request, "crm/sales/opportunity/detail.html", {
        "obj": obj,
        "splits": splits,
        "revenue_split_total": rev_total,
        "split_form": OpportunitySplitForm(tenant=request.tenant),
        "quotes": Quote.objects.filter(tenant=request.tenant, opportunity=obj).select_related("account")[:20],
        "tasks": CrmTask.objects.filter(
            tenant=request.tenant, related_opportunity=obj).select_related("owner")[:20],
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
    base = Opportunity.objects.filter(tenant=request.tenant).select_related("account", "owner", "territory")
    # One grouped query for all per-stage count + amount totals (instead of 6 aggregate round-trips).
    stage_agg = {r["stage"]: r for r in base.values("stage").annotate(c=Count("id"), total=Sum("amount"))}
    columns = []
    for value, label in Opportunity.STAGE_CHOICES:
        row = stage_agg.get(value, {})
        columns.append({
            "value": value, "label": label,
            "count": row.get("c") or 0, "total": row.get("total") or 0,
            "opps": list(base.filter(stage=value).order_by("-amount")[:50]),
        })
    return render(request, "crm/sales/pipeline.html", {"columns": columns})


@login_required
@require_POST
def opportunity_advance(request, pk):
    """Advance an opportunity one stage along the win path (board/detail quick action)."""
    opp = get_object_or_404(Opportunity, pk=pk, tenant=request.tenant)
    if opp.stage in _OPP_FLOW and opp.stage != "closed_won":
        opp.stage = _OPP_FLOW[_OPP_FLOW.index(opp.stage) + 1]
        if opp.stage == "closed_won":
            opp.probability = 100
            opp.forecast_category = "closed"
        opp.save()  # save() stamps stage_changed_at
        write_audit_log(request.user, opp, "update", {"action": "advance", "stage": opp.stage})
        messages.success(request, f"Advanced to {opp.get_stage_display()}.")
    else:
        messages.info(request, "This opportunity can't be advanced further.")
    # Fixed destinations only (no user-controlled redirect → no open-redirect).
    if request.POST.get("next") == "board":
        return redirect("crm:opportunity_board")
    return redirect("crm:opportunity_detail", pk=opp.pk)


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
        split.clean()  # enforces revenue splits ≤ 100% across the opportunity
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
