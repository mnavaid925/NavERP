"""8.4 Sales Forecasting — cross-entity service functions.

A flat single-purpose module at the app root, exactly like `apps/sales/services.py` and
`apps/sales/opportunity_services.py` (backend-package rule 8). These three functions are
**services, not views**: they are called by the view modules, by the seeder and by each
other, and they are deliberately absent from `apps.sales.views.__all__`.

What lives here, and why it is here rather than in a view module:

* `forecast_org_unit_chain` — the rep -> manager -> director rollup walk. It is shared by
  the adjustment views (the "you cannot adjust a level above you" rule) and the scenario
  views (the owner chain on the detail page), so it cannot belong to either one.
* `forecast_submission_snapshot` — the three service-written snapshot figures for a call.
* `forecast_ai_gate` — the 40-won AND 40-lost eligibility gate.

Rulings that are enforced here rather than in a template:

* **No second currency ledger (L29).** `weighted_amount` / `actual_amount` are counted in
  the period's reporting currency only, so a single stored figure is never a sum over
  unlike amounts. The per-currency breakdown keeps its own buckets and the codes are never
  added together.
* **The AI prediction is storage + explanation only.** Nothing is trained, nothing is
  inferred, and no prediction value is ever returned or rendered below the gate.
* **The org walk is iterative, depth-bounded and cycle-safe.** `core.OrgUnit.parent` is a
  self-FK with no cycle validation anywhere in the codebase, so a legacy A->B->A row is
  reachable; the `seen` set turns that into a truncated chain instead of a hung request.
"""
from decimal import Decimal

from django.db.models import Count, Sum

from apps.crm.models import Opportunity
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome
from apps.sales.models.OpportunityPipeline.Pipelines import OpportunityPipelinePlacement

#: Hard cap on the OrgUnit walk. A hierarchy deeper than this is treated as unresolvable
#: rather than walked: a legacy cycle must not become an infinite loop.
ORG_UNIT_CHAIN_MAX_DEPTH = 12

#: The AI eligibility gate (contract 0.5): BOTH sides must clear it, counted from the
#: append-only outcome table. Below it, no prediction value is ever rendered.
AI_GATE_MIN_PER_CLASS = 40


# --------------------------------------------------------------------------- org walk
def forecast_org_unit_chain(org_unit, max_depth=ORG_UNIT_CHAIN_MAX_DEPTH):
    """The chain of `core.OrgUnit` nodes from `org_unit` up to its root, root last.

    There is **no `User.manager` field** anywhere in this codebase, so the rep -> manager ->
    director walk is the `OrgUnit.parent` self-FK. Three hazards, all handled here:

    * `parent` is a self-FK with **no cycle validation anywhere**, so a legacy A->B->A row
      is reachable. A `seen` set of pks stops it instead of hanging the request.
    * the walk is **iterative**, never recursive, so a deep chain cannot blow the stack.
    * it is **depth-bounded**; a chain past the cap is truncated rather than followed.

    Returns `[]` for `None`, so every caller can iterate the result unguarded.
    """
    chain, seen, node, depth = [], set(), org_unit, 0
    while node is not None and depth < max_depth:
        if node.pk in seen:
            break
        seen.add(node.pk)
        chain.append(node)
        node = node.parent
        depth += 1
    return chain


# ------------------------------------------------------------------ snapshot + AI gate
def _period_window(period):
    """``(start_date, end_date)`` for a period, or ``None`` when undated.

    Dates, not datetimes: ``closed_at`` is matched with ``__date__range`` so the window is
    evaluated in the database's own date semantics on both MySQL and SQLite, and a
    timezone offset can never push a boundary close out of the period.
    """
    if not period or not period.start_date or not period.end_date:
        return None
    return period.start_date, period.end_date


def _reporting_currency_id(period):
    """The currency a call's scalar amounts are stated in — the period's, or none."""
    if period is None or not period.reporting_currency_id:
        return None
    return period.reporting_currency_id


def _call_period(submission):
    """The call's period, or ``None`` when it has no computed window to scope by."""
    if not submission.period_id:
        return None
    period = submission.period
    return period if (period.start_date and period.end_date) else None



def _open_opportunities(tenant, owner, territory, pipeline, period):
    """The open opportunities behind this call, inside the period window.

    ``closed_lost`` is excluded: a lost deal is not forecastable. No currency filter is
    applied here — the caller decides, because the scalar snapshot and the per-currency
    breakdown want different things from the same base.
    """
    queryset = Opportunity.objects.filter(tenant=tenant)
    if owner is not None:
        queryset = queryset.filter(owner=owner)
    if territory is not None:
        queryset = queryset.filter(territory=territory)
    if pipeline is not None:
        queryset = queryset.filter(
            pk__in=OpportunityPipelinePlacement.objects.filter(
                pipeline=pipeline, tenant=tenant,
            ).values_list("opportunity_id", flat=True)
        )
    window = _period_window(period)
    if window is not None:
        queryset = queryset.filter(close_date__gte=window[0], close_date__lte=window[1])
    return queryset.exclude(stage="closed_lost")


def _rollup_by_currency(opportunities):
    """``{currency_code: {"weighted": Decimal, "open": int}}`` in ONE pass.

    Each verified currency keeps its own bucket and a missing currency lands in an explicit
    ``unspecified`` rather than defaulting to USD; the codes are never added together.
    Weighting uses ``OpportunityPipelinePlacement.effective_probability`` — the property
    that already prefers ``probability_override`` over the stage probability — and falls
    back to the opportunity's own probability when the deal is not on a pipeline.
    """
    rollups = {}
    for opportunity in opportunities.select_related(
        "currency", "sales_pipeline_placement", "sales_pipeline_placement__current_stage",
    ):
        placement = getattr(opportunity, "sales_pipeline_placement", None)
        probability = (
            placement.effective_probability if placement is not None
            else opportunity.probability
        )
        code = opportunity.currency.code if opportunity.currency_id else "unspecified"
        bucket = rollups.setdefault(code, {"weighted": Decimal("0"), "open": 0})
        bucket["weighted"] += Decimal(opportunity.amount or 0) * Decimal(probability) / Decimal("100")
        bucket["open"] += 1
    for bucket in rollups.values():
        bucket["weighted"] = bucket["weighted"].quantize(Decimal("0.01"))
    return rollups


def forecast_submission_snapshot(submission, tenant=None):
    """The three service-written snapshot figures for one call, as plain ``Decimal``.

    The scalar ``weighted_amount`` and ``actual_amount`` are counted in the period's
    **reporting currency only**, so a single stored figure is never a sum over unlike
    amounts (L29). A period with no reporting currency adopts the call's own single
    currency and reports zero when the call genuinely spans several — the per-currency
    breakdown on the detail page is where those are still visible.

    ``quota_amount`` is frozen by value from ``crm.SalesQuota.target_amount``, so a later
    quota edit never rewrites this call. ``actual_amount`` reads the append-only
    ``sales.OpportunityOutcome`` table for wins closed inside the period window.
    """
    tenant = tenant or submission.tenant
    period = _call_period(submission)
    currency_id = _reporting_currency_id(period)
    reporting_code = period.reporting_currency.code if currency_id is not None else None
    rollups = _rollup_by_currency(_open_opportunities(
        tenant, submission.owner, submission.territory, submission.pipeline, period,
    ))
    if reporting_code is not None:
        weighted = rollups.get(reporting_code, {}).get("weighted", Decimal("0"))
    elif len(rollups) == 1:
        weighted = next(iter(rollups.values()))["weighted"]
    else:
        weighted = Decimal("0")
    quota = (
        Decimal(submission.quota_ref.target_amount or 0)
        if submission.quota_ref_id else Decimal("0")
    )
    actual = Decimal("0")
    window = _period_window(period)
    if window is not None:
        won = OpportunityOutcome.objects.filter(
            tenant=tenant, result="won", closed_at__date__range=window,
        )
        if submission.owner_id:
            won = won.filter(opportunity__owner_id=submission.owner_id)
        if submission.territory_id:
            won = won.filter(opportunity__territory_id=submission.territory_id)
        if currency_id is not None:
            won = won.filter(opportunity__currency_id=currency_id)
        actual = Decimal(won.aggregate(total=Sum("opportunity__amount"))["total"] or 0)
    return {
        "weighted_amount": weighted.quantize(Decimal("0.01")),
        "quota_amount": quota.quantize(Decimal("0.01")),
        "actual_amount": actual.quantize(Decimal("0.01")),
        "currency_codes": sorted(rollups),
    }


def forecast_ai_gate(tenant):
    """``(available, message)`` for the AI block — the 40-won AND 40-lost gate."""
    if tenant is None:
        return False, "Select a tenant workspace to see a prediction."
    counts = {
        row["result"]: row["total"]
        for row in OpportunityOutcome.objects.filter(tenant=tenant)
        .values("result")
        .annotate(total=Count("pk"))
    }
    won = counts.get("won", 0)
    lost = counts.get("lost", 0)
    if won >= AI_GATE_MIN_PER_CLASS and lost >= AI_GATE_MIN_PER_CLASS:
        return True, ""
    return False, (
        f"A prediction needs at least {AI_GATE_MIN_PER_CLASS} won and "
        f"{AI_GATE_MIN_PER_CLASS} lost recorded opportunities. This workspace has "
        f"{won} won and {lost} lost."
    )
