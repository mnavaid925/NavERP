"""Sales 8.12 — the six derived Sales Analytics & Intelligence consoles (read-only).

These are the six "board" pages of sub-module 8.12. They are **derived**: every figure is
computed at render time and **nothing is stored** by them. A console never writes — there is no
``form.save()``, no ``write_audit_log`` call and no POST handling anywhere in this module. It
renders over the analytics engines that already exist; it never builds a second one.

CONSOLE -> HELPER MAP (the contract's hard rule — every console names the helper it renders over)

=========================  =====================================================================
Console                    Helper(s) rendered over
=========================  =====================================================================
``analytics_console``      ``apps.sales.opportunity_analytics.sales_health_counts`` +
                           ``apps.sales.opportunity_analytics.sales_pipeline_rollups``
``win_loss_console``       ``apps.sales.opportunity_analytics.sales_win_loss_rows`` +
                           ``apps.sales.opportunity_analytics.sales_competitor_rows``
                           (+ ``WinLossDebrief.decision_drivers`` aggregation)
``velocity_console``       ``apps.sales.opportunity_analytics.sales_stage_age_rows`` +
                           ``apps.sales.opportunity_analytics.sales_pipeline_rollups``
``funnel_console``         ``apps.crm.analytics.compute_report`` (PUBLIC entry point, on an
                           in-memory ``crm.AnalyticsReport`` with ``report_type="funnel"``) +
                           the ``FunnelConversionRecord`` (FNL-) rows
``rep_scorecard_console``  the ``RepPerformanceScorecard`` (RPS-) rows + a live
                           ``apps.sales.models...ActivityLog`` aggregate +
                           ``apps.crm.analytics.compute_report`` (``report_type="sales_performance"``)
``benchmark_console``      the RPS- / FNL- / VCA- benchmark fields + ``apps.sales.models``
                           ``QuotaPlan`` (QPA-)
=========================  =====================================================================

The underscore-private ``crm.analytics._compute_funnel`` / ``._compute_sales_performance`` are
NOT imported across the app boundary — the public ``compute_report`` is the only seam used.

GRACEFUL DEGRADATION (never a 500)
Every call into an analytics helper is wrapped so that a raising helper degrades to an empty
table/dict instead of taking the page down. ``_safe()`` is that wrapper. A console whose helper
failed still renders, with the affected table empty.

ROW SHAPE CONTRACT (the template writer needs this)
Every row list handed to a template is a list of **plain dicts**. Every row carries the four
uniform display keys, so one template can render several row lists:

* ``label``  (str)   — the row's headline name.
* ``value``  (number/str/None) — the row's headline figure.
* ``detail`` (str)   — the secondary line under the headline.
* ``badge``  (str)   — a **colour-named** theme.css badge class (``badge-green`` / ``badge-red``
  / ``badge-amber`` / ``badge-info`` / ``badge-muted`` / ``badge-slate``) or ``""``.

On top of those four, each row list carries its own source keys (documented per console below
and in each view's docstring). Rows that come from a model also carry the model instance under a
descriptive key (``debrief`` / ``analysis`` / ``record`` / ``scorecard``) and the related objects
under their model field names, so ``{{ row.opportunity.name }}`` and ``{{ row.debrief.number }}``
both work.

``stats`` is a **plain dict of numbers** on every console (never a QuerySet), so the template can
render ``.stat-card`` blocks straight from it. The single exception is documented on
``analytics_console``: ``stats.pipeline_health`` is the ``sales_health_counts`` breakdown dict
``{"on_track", "watch", "at_risk"}`` — the flattened ``stats.pipeline_on_track`` /
``stats.pipeline_watch`` / ``stats.pipeline_at_risk`` / ``stats.pipeline_health_total`` keys sit
beside it for a single-number stat card.

No JournalEntry is posted by 8.12 (L29). The revenue shown is a read of the sales records.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.crm.analytics import compute_report
from apps.crm.models import AnalyticsReport
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome
from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import ActivityLog
from apps.sales.models.SalesAnalytics.FunnelConversionRecords import FunnelConversionRecord
from apps.sales.models.SalesAnalytics.RepPerformanceScorecards import RepPerformanceScorecard
from apps.sales.models.SalesAnalytics.StageVelocityAnalyses import StageVelocityAnalysis
from apps.sales.models.SalesAnalytics.WinLossDebriefs import WinLossDebrief
from apps.sales.models.TerritoryQuotaManagement.QuotaPlans import QuotaPlan
from apps.sales.opportunity_analytics import (
    sales_competitor_rows,
    sales_health_counts,
    sales_pipeline_rollups,
    sales_stage_age_rows,
    sales_win_loss_rows,
)

#: The five NavERP.md 8.12 bullet texts, verbatim, in NavERP order, with the console url name
#: each one points at. The sidebar looks a bullet up by its text, so the wording is load-bearing.
BULLET_LINKS = (
    ("Win/Loss Analysis", "sales:win_loss_console"),
    ("Sales Velocity & Cycle Time", "sales:velocity_console"),
    ("Conversion Funnel Analytics", "sales:funnel_console"),
    ("Rep Performance Scorecards", "sales:rep_scorecard_console"),
    ("Benchmarking & Peer Comparison", "sales:benchmark_console"),
)

#: A debrief whose status is one of these has NOT been actioned yet — the open feedback loop.
OPEN_FEEDBACK_STATUSES = ("draft", "submitted", "shared")

#: How many rows a console table renders before it is truncated.
ROW_LIMIT = 25

#: How many "recent" model rows the landing console shows.
RECENT_LIMIT = 10

#: ``ActivityType.kind`` -> the ``activity_totals`` bucket it is counted in. The kind values
#: are singular (call / email / meeting / sms / note); the buckets are the plural names a
#: template reads.
ACTIVITY_KIND_BUCKETS = {
    "call": "calls",
    "email": "emails",
    "meeting": "meetings",
    "sms": "sms",
    "note": "notes",
}

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------
def _safe(call, default):
    """Run ``call`` and fall back to ``default`` when it raises.

    The 8.12 contract makes graceful degradation mandatory: a helper that raises must degrade
    to an empty table with an explanatory message, never a 500. Every optional analytics call
    goes through here.
    """
    try:
        return call()
    except Exception:
        return default


def _console_url(name):
    """``reverse()`` a console url name, degrading to ``""`` when the route is not wired yet.

    The console urls are spliced into ``apps/sales/urls/__init__.py`` in the integrate step; until
    then ``reverse()`` raises ``NoReverseMatch``. A console must still render, so the link is
    empty rather than the page exploding.
    """
    try:
        return reverse(name)
    except NoReverseMatch:
        return ""


def _percentile(values, pct):
    """Return the ``pct`` percentile of ``values`` (linear interpolation), or ``None``.

    Computed in Python: the scorecard row count is small, and pulling a percentile out of the
    database would be a second aggregation engine for no gain.
    """
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * (pct / 100.0)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _mean(values):
    """The arithmetic mean of ``values``, or ``None`` when there are none."""
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)


def _row(label, value, detail="", badge="", **extra):
    """Build one uniform console row: the four display keys plus any source keys."""
    row = {"label": label, "value": value, "detail": detail, "badge": badge}
    row.update(extra)
    return row


def _badge_for_scorecard_rating(rating):
    """Colour-named badge for a scorecard rating (the exact CHOICES value is tested)."""
    if rating == "outstanding":
        return "badge-green"
    if rating == "strong":
        return "badge-green"
    if rating == "on_track":
        return "badge-info"
    if rating == "needs_improvement":
        return "badge-amber"
    if rating == "underperforming":
        return "badge-red"
    return "badge-slate"


def _badge_for_debrief_status(status):
    """Colour-named badge for a debrief status (the exact CHOICES value is tested)."""
    if status == "actioned":
        return "badge-green"
    if status == "closed":
        return "badge-slate"
    if status == "shared":
        return "badge-amber"
    if status == "submitted":
        return "badge-info"
    return "badge-muted"


def _badge_for_rate(value, benchmark=None):
    """Green at or above the benchmark, amber below it, slate when there is no figure at all."""
    if value is None:
        return "badge-slate"
    if benchmark is not None and value < benchmark:
        return "badge-amber"
    return "badge-green"


def _user_name(user):
    """A display name for a user row, or ``""`` when the user is NULL (L10)."""
    if user is None:
        return ""
    return user.get_full_name() or user.username


def _related_name(obj, attribute):
    """The display name of a related row, or ``""`` when the FK is NULL (L10)."""
    if obj is None:
        return ""
    getter = getattr(obj, attribute, None)
    if callable(getter):
        return getter()
    return getter or ""


# ---------------------------------------------------------------------------
# Model -> row builders (one per 8.12 model)
# ---------------------------------------------------------------------------
def _debrief_row(debrief):
    """One ``WinLossDebrief`` as a uniform console row.

    Keys: the four display keys + ``debrief`` (the model instance), ``number``, ``opportunity`` /
    ``opportunity_name``, ``account`` / ``account_name``, ``outcome``, ``primary_reason`` /
    ``primary_reason_name``, ``interviewer`` / ``interviewer_name``, ``action_owner`` /
    ``action_owner_name``, ``communication_log``, ``debriefed_on``, ``interview_channel`` /
    ``interview_channel_display``, ``decision_drivers``, ``buyer_quote``, ``counterfactual``,
    ``feedback_team`` / ``feedback_team_display``, ``action_items``, ``actioned_on``,
    ``status`` / ``status_display``, ``notes``.
    """
    return _row(
        label=debrief.number,
        value=debrief.get_status_display(),
        detail=_related_name(debrief.opportunity, "name"),
        badge=_badge_for_debrief_status(debrief.status),
        debrief=debrief,
        number=debrief.number,
        opportunity=debrief.opportunity,
        opportunity_name=_related_name(debrief.opportunity, "name"),
        account=debrief.account,
        account_name=_related_name(debrief.account, "name"),
        outcome=debrief.outcome,
        primary_reason=debrief.primary_reason,
        primary_reason_name=_related_name(debrief.primary_reason, "name"),
        interviewer=debrief.interviewer,
        interviewer_name=_user_name(debrief.interviewer),
        action_owner=debrief.action_owner,
        action_owner_name=_user_name(debrief.action_owner),
        communication_log=debrief.communication_log,
        debriefed_on=debrief.debriefed_on,
        interview_channel=debrief.interview_channel,
        interview_channel_display=debrief.get_interview_channel_display(),
        decision_drivers=debrief.decision_drivers,
        buyer_quote=debrief.buyer_quote,
        counterfactual=debrief.counterfactual,
        feedback_team=debrief.feedback_team,
        feedback_team_display=debrief.get_feedback_team_display(),
        action_items=debrief.action_items,
        actioned_on=debrief.actioned_on,
        status=debrief.status,
        status_display=debrief.get_status_display(),
        notes=debrief.notes,
    )


def _analysis_row(analysis, live_rank=None):
    """One ``StageVelocityAnalysis`` as a uniform console row.

    Keys: the four display keys + ``analysis`` (the model instance), ``number``, ``pipeline`` /
    ``pipeline_name``, ``pipeline_stage`` / ``stage_name``, ``period_start``, ``period_end``,
    ``opportunity_count``, ``median_days_in_stage``, ``p90_days_in_stage``,
    ``max_days_in_stage``, ``sales_cycle_days``, ``velocity_value``, ``is_bottleneck``,
    ``bottleneck_rank`` (the STORED rank), ``live_rank`` (the rank re-derived at render time —
    ``None`` when the row was not part of a live ranking), ``recommendation``,
    ``benchmark_days``, ``benchmark_source``, ``benchmark_as_of``, ``segment``,
    ``status`` / ``status_display``, ``notes``.
    """
    stage_name = _related_name(analysis.pipeline_stage, "name")
    pipeline_name = _related_name(analysis.pipeline, "name")
    return _row(
        label=stage_name or analysis.number,
        value=analysis.median_days_in_stage,
        detail=pipeline_name,
        badge="badge-amber" if analysis.is_bottleneck else "badge-slate",
        analysis=analysis,
        number=analysis.number,
        pipeline=analysis.pipeline,
        pipeline_name=pipeline_name,
        pipeline_stage=analysis.pipeline_stage,
        stage_name=stage_name,
        period_start=analysis.period_start,
        period_end=analysis.period_end,
        opportunity_count=analysis.opportunity_count,
        median_days_in_stage=analysis.median_days_in_stage,
        p90_days_in_stage=analysis.p90_days_in_stage,
        max_days_in_stage=analysis.max_days_in_stage,
        sales_cycle_days=analysis.sales_cycle_days,
        velocity_value=analysis.velocity_value,
        is_bottleneck=analysis.is_bottleneck,
        bottleneck_rank=analysis.bottleneck_rank,
        live_rank=live_rank,
        recommendation=analysis.recommendation,
        benchmark_days=analysis.benchmark_days,
        benchmark_source=analysis.benchmark_source,
        benchmark_as_of=analysis.benchmark_as_of,
        segment=analysis.segment,
        status=analysis.status,
        status_display=analysis.get_status_display(),
        notes=analysis.notes,
    )


def _funnel_row(record):
    """One ``FunnelConversionRecord`` as a uniform console row.

    Keys: the four display keys + ``record`` (the model instance), ``number``, ``label_text``
    (the record's own label), ``funnel_scope`` / ``funnel_scope_display``, ``from_stage`` /
    ``from_stage_name``, ``to_stage`` / ``to_stage_name``, ``territory`` / ``territory_name``,
    ``owner`` / ``owner_name``, ``source_channel``, ``period_start``, ``period_end``,
    ``entered_count``, ``converted_count``, ``conversion_rate_pct``, ``dropoff_count``,
    ``skipped_count``, ``avg_cycle_days``, ``benchmark_pct``, ``benchmark_source``,
    ``benchmark_as_of``, ``segment``, ``notes``.
    """
    return _row(
        label=record.label,
        value=record.conversion_rate_pct,
        detail="{entered} entered / {converted} converted".format(
            entered=record.entered_count, converted=record.converted_count
        ),
        badge=_badge_for_rate(record.conversion_rate_pct, record.benchmark_pct),
        record=record,
        number=record.number,
        label_text=record.label,
        funnel_scope=record.funnel_scope,
        funnel_scope_display=record.get_funnel_scope_display(),
        from_stage=record.from_stage,
        from_stage_name=_related_name(record.from_stage, "name"),
        to_stage=record.to_stage,
        to_stage_name=_related_name(record.to_stage, "name"),
        territory=record.territory,
        territory_name=_related_name(record.territory, "name"),
        owner=record.owner,
        owner_name=_user_name(record.owner),
        source_channel=record.source_channel,
        period_start=record.period_start,
        period_end=record.period_end,
        entered_count=record.entered_count,
        converted_count=record.converted_count,
        conversion_rate_pct=record.conversion_rate_pct,
        dropoff_count=record.dropoff_count,
        skipped_count=record.skipped_count,
        avg_cycle_days=record.avg_cycle_days,
        benchmark_pct=record.benchmark_pct,
        benchmark_source=record.benchmark_source,
        benchmark_as_of=record.benchmark_as_of,
        segment=record.segment,
        notes=record.notes,
    )


def _scorecard_row(scorecard):
    """One ``RepPerformanceScorecard`` as a uniform console row.

    Keys: the four display keys + ``scorecard`` (the model instance), ``number``, ``rep`` /
    ``rep_name``, ``territory`` / ``territory_name``, ``manager`` / ``manager_name``,
    ``forecast_period``, ``quota_plan``, ``coaching_scorecard``, ``period_start``,
    ``period_end``, the activity block (``activities_logged``, ``calls_logged``,
    ``emails_logged``, ``meetings_logged``, ``meetings_booked``, ``follow_ups_completed``,
    ``activity_minutes``, ``response_time_hours``), the outcome block
    (``opportunities_created``, ``opportunities_won``, ``opportunities_lost``,
    ``pipeline_value``, ``weighted_pipeline_value``, ``win_rate_pct``, ``revenue_closed``,
    ``currency`` / ``currency_code``, ``average_deal_size``, ``sales_cycle_days``), the goal
    block (``quota_target``, ``quota_attainment_pct``, ``goal_gap_value``), ``overall_score``,
    ``rating`` / ``rating_display``, ``strengths``, ``areas_for_improvement``,
    ``coaching_actions``, the benchmark block (``benchmark_win_rate_pct``,
    ``benchmark_cycle_days``, ``benchmark_quota_attainment_pct``, ``benchmark_source``,
    ``benchmark_as_of``), ``segment``, ``status`` / ``status_display``, ``notes``.
    """
    return _row(
        label=_user_name(scorecard.rep) or scorecard.number,
        value=scorecard.win_rate_pct,
        detail=scorecard.get_rating_display(),
        badge=_badge_for_scorecard_rating(scorecard.rating),
        scorecard=scorecard,
        number=scorecard.number,
        rep=scorecard.rep,
        rep_name=_user_name(scorecard.rep),
        territory=scorecard.territory,
        territory_name=_related_name(scorecard.territory, "name"),
        manager=scorecard.manager,
        manager_name=_user_name(scorecard.manager),
        forecast_period=scorecard.forecast_period,
        quota_plan=scorecard.quota_plan,
        coaching_scorecard=scorecard.coaching_scorecard,
        period_start=scorecard.period_start,
        period_end=scorecard.period_end,
        activities_logged=scorecard.activities_logged,
        calls_logged=scorecard.calls_logged,
        emails_logged=scorecard.emails_logged,
        meetings_logged=scorecard.meetings_logged,
        meetings_booked=scorecard.meetings_booked,
        follow_ups_completed=scorecard.follow_ups_completed,
        activity_minutes=scorecard.activity_minutes,
        response_time_hours=scorecard.response_time_hours,
        opportunities_created=scorecard.opportunities_created,
        opportunities_won=scorecard.opportunities_won,
        opportunities_lost=scorecard.opportunities_lost,
        pipeline_value=scorecard.pipeline_value,
        weighted_pipeline_value=scorecard.weighted_pipeline_value,
        win_rate_pct=scorecard.win_rate_pct,
        revenue_closed=scorecard.revenue_closed,
        currency=scorecard.currency,
        currency_code=_related_name(scorecard.currency, "code"),
        average_deal_size=scorecard.average_deal_size,
        sales_cycle_days=scorecard.sales_cycle_days,
        quota_target=scorecard.quota_target,
        quota_attainment_pct=scorecard.quota_attainment_pct,
        goal_gap_value=scorecard.goal_gap_value,
        overall_score=scorecard.overall_score,
        rating=scorecard.rating,
        rating_display=scorecard.get_rating_display(),
        strengths=scorecard.strengths,
        areas_for_improvement=scorecard.areas_for_improvement,
        coaching_actions=scorecard.coaching_actions,
        benchmark_win_rate_pct=scorecard.benchmark_win_rate_pct,
        benchmark_cycle_days=scorecard.benchmark_cycle_days,
        benchmark_quota_attainment_pct=scorecard.benchmark_quota_attainment_pct,
        benchmark_source=scorecard.benchmark_source,
        benchmark_as_of=scorecard.benchmark_as_of,
        segment=scorecard.segment,
        status=scorecard.status,
        status_display=scorecard.get_status_display(),
        notes=scorecard.notes,
    )


def _benchmark_row(model, number, label, value, benchmark, source, as_of, segment, unit=""):
    """One "our metric vs the benchmark" row.

    Keys: the four display keys + ``model`` (the model the benchmark came from), ``number``,
    ``label``, ``value``, ``benchmark``, ``delta`` (``value - benchmark``, ``None`` when either
    side is missing), ``source``, ``as_of``, ``segment``, ``unit``.
    """
    delta = None
    if value is not None and benchmark is not None:
        delta = value - benchmark
    return _row(
        label=label,
        value=value,
        detail=("benchmark {benchmark}".format(benchmark=benchmark) if benchmark is not None else ""),
        badge=_badge_for_rate(value, benchmark),
        model=model,
        number=number,
        benchmark=benchmark,
        delta=delta,
        source=source or "",
        as_of=as_of,
        segment=segment or "",
        unit=unit,
    )


# ---------------------------------------------------------------------------
# Console 1 — the landing board
# ---------------------------------------------------------------------------
@login_required
def analytics_console(request):
    """Console 1 — the Sales Analytics landing board.

    Renders over ``apps.sales.opportunity_analytics.sales_health_counts`` (the pipeline health
    breakdown) and ``apps.sales.opportunity_analytics.sales_pipeline_rollups`` (the open-pipeline
    value by pipeline / stage / currency).

    Context keys: ``stats``, ``bullet_links``, ``recent_debriefs``, ``recent_analyses``.

    * ``stats`` — plain dict of numbers: ``total_debriefs``, ``total_velocity_analyses``,
      ``total_funnel_records``, ``total_scorecards``, ``open_feedback_actions``,
      ``pipeline_health`` (the ``sales_health_counts`` breakdown dict
      ``{"on_track", "watch", "at_risk"}``), plus the flattened ``pipeline_health_total``,
      ``pipeline_on_track``, ``pipeline_watch``, ``pipeline_at_risk`` and the open-pipeline
      ``open_pipeline_value`` / ``open_pipeline_count`` / ``stale_pipeline_count``.
    * ``bullet_links`` — list of ``{"label": str, "url": str}``, one per NavERP.md 8.12 bullet
      (the five bullet texts, verbatim, in NavERP order). The url is built with ``reverse()``.
    * ``recent_debriefs`` — the newest ``WinLossDebrief`` rows as console rows (see
      ``_debrief_row`` for the key list).
    * ``recent_analyses`` — the newest ``StageVelocityAnalysis`` rows as console rows (see
      ``_analysis_row``).
    """
    tenant = getattr(request, "tenant", None)

    debriefs = WinLossDebrief.objects.filter(tenant=tenant).select_related(
        "opportunity",
        "account",
        "primary_reason",
        "interviewer",
        "action_owner",
        "outcome",
        "communication_log",
    )
    analyses = StageVelocityAnalysis.objects.filter(tenant=tenant).select_related(
        "pipeline", "pipeline_stage"
    )
    funnel_records = FunnelConversionRecord.objects.filter(tenant=tenant)
    scorecards = RepPerformanceScorecard.objects.filter(tenant=tenant)
    open_debriefs = debriefs.filter(status__in=OPEN_FEEDBACK_STATUSES)

    health = _safe(lambda: sales_health_counts(tenant), {}) or {}
    rollups = _safe(lambda: sales_pipeline_rollups(tenant), []) or []

    health_total = sum(int(health.get(key) or 0) for key in ("on_track", "watch", "at_risk"))
    open_pipeline_value = sum((row.get("amount") or ZERO) for row in rollups)
    open_pipeline_count = sum(int(row.get("count") or 0) for row in rollups)
    stale_pipeline_count = sum(int(row.get("stale_count") or 0) for row in rollups)

    stats = {
        "total_debriefs": debriefs.count(),
        "total_velocity_analyses": analyses.count(),
        "total_funnel_records": funnel_records.count(),
        "total_scorecards": scorecards.count(),
        "open_feedback_actions": open_debriefs.count(),
        "pipeline_health": health,
        "pipeline_health_total": health_total,
        "pipeline_on_track": int(health.get("on_track") or 0),
        "pipeline_watch": int(health.get("watch") or 0),
        "pipeline_at_risk": int(health.get("at_risk") or 0),
        "open_pipeline_value": open_pipeline_value,
        "open_pipeline_count": open_pipeline_count,
        "stale_pipeline_count": stale_pipeline_count,
    }

    bullet_links = [
        {"label": label, "url": _console_url(url_name)} for label, url_name in BULLET_LINKS
    ]

    context = {
        "stats": stats,
        "bullet_links": bullet_links,
        "recent_debriefs": [
            _debrief_row(debrief) for debrief in debriefs[:RECENT_LIMIT]
        ],
        "recent_analyses": [
            _analysis_row(analysis) for analysis in analyses[:RECENT_LIMIT]
        ],
    }
    return render(request, "sales/salesanalytics/boards/analytics_console.html", context)


# ---------------------------------------------------------------------------
# Console 2 — win/loss analysis
# ---------------------------------------------------------------------------
@login_required
def win_loss_console(request):
    """Console 2 — Win/Loss Analysis.

    Renders over ``apps.sales.opportunity_analytics.sales_win_loss_rows`` (win rate by reason /
    pipeline / currency) and ``apps.sales.opportunity_analytics.sales_competitor_rows`` (the
    competitors we actually lost to), plus the recurring decision drivers aggregated from
    ``WinLossDebrief.decision_drivers``.

    Context keys: ``stats``, ``win_loss_rows``, ``competitor_rows``, ``driver_rows``,
    ``open_actions``, ``result_choices``.

    * ``win_loss_rows`` — the helper rows, each carrying the helper's own keys (``result``,
      ``result_label``, ``reason_code``, ``reason_name``, ``reason_category``,
      ``category_label``, ``pipeline_name``, ``currency_code``, ``count``, ``amount``,
      ``first_closed_at``, ``last_closed_at``) PLUS the four uniform display keys.
    * ``competitor_rows`` — the helper rows, each carrying the helper's own keys (``result``,
      ``result_label``, ``competitor_name``, ``relationship``, ``relationship_label``,
      ``pipeline_name``, ``currency_code``, ``count``, ``amount``) PLUS the four uniform keys.
    * ``driver_rows`` — ``{"driver": str, "count": int, "sentiment": str}`` PLUS the four uniform
      keys. Sorted by count desc, capped at 20.
    * ``open_actions`` — the ``WinLossDebrief`` rows whose status is in
      ``{"draft", "submitted", "shared"}`` (the open feedback loop), as console rows (see
      ``_debrief_row``).
    * ``result_choices`` — ``sales.OpportunityOutcome.RESULT_CHOICES``.
    """
    tenant = getattr(request, "tenant", None)

    win_loss = _safe(lambda: sales_win_loss_rows(tenant), []) or []
    competitors = _safe(lambda: sales_competitor_rows(tenant), []) or []

    win_loss_rows = []
    for raw in win_loss:
        reason_name = raw.get("reason_name") or raw.get("category_label") or "Unclassified"
        result_label = raw.get("result_label") or raw.get("result") or ""
        count = int(raw.get("count") or 0)
        amount = raw.get("amount") or ZERO
        win_loss_rows.append(
            _row(
                label=reason_name,
                value=count,
                detail="{result} · {pipeline} · {currency}".format(
                    result=result_label,
                    pipeline=raw.get("pipeline_name") or "—",
                    currency=raw.get("currency_label") or raw.get("currency_code") or "—",
                ),
                badge="badge-green" if raw.get("result") == "won" else "badge-red",
                **raw
            )
        )

    competitor_rows = []
    for raw in competitors:
        competitor_name = raw.get("competitor_name") or raw.get("competitor") or "Unnamed"
        count = int(raw.get("count") or 0)
        competitor_rows.append(
            _row(
                label=competitor_name,
                value=count,
                detail="{relationship} · {pipeline}".format(
                    relationship=raw.get("relationship_label") or raw.get("relationship") or "—",
                    pipeline=raw.get("pipeline_name") or "—",
                ),
                badge="badge-red" if raw.get("result") == "lost" else "badge-slate",
                **raw
            )
        )

    driver_rows = _decision_driver_rows(tenant)

    open_actions = [
        _debrief_row(debrief)
        for debrief in WinLossDebrief.objects.filter(
            tenant=tenant, status__in=OPEN_FEEDBACK_STATUSES
        ).select_related(
            "opportunity",
            "account",
            "primary_reason",
            "interviewer",
            "action_owner",
            "outcome",
            "communication_log",
        )
    ]

    won_count = sum(int(row.get("count") or 0) for row in win_loss if row.get("result") == "won")
    lost_count = sum(int(row.get("count") or 0) for row in win_loss if row.get("result") == "lost")
    decided = won_count + lost_count
    won_amount = sum(
        (row.get("amount") or ZERO) for row in win_loss if row.get("result") == "won"
    )
    lost_amount = sum(
        (row.get("amount") or ZERO) for row in win_loss if row.get("result") == "lost"
    )
    competitor_names = {
        row.get("competitor_name") for row in competitors if row.get("competitor_name")
    }
    total_debriefs = WinLossDebrief.objects.filter(tenant=tenant).count()

    stats = {
        "total_outcomes": decided,
        "won_count": won_count,
        "lost_count": lost_count,
        "win_rate_pct": round(won_count / decided * 100, 1) if decided else None,
        "total_amount": won_amount + lost_amount,
        "won_amount": won_amount,
        "lost_amount": lost_amount,
        "competitor_count": len(competitor_names),
        "competitor_outcomes": sum(int(row.get("count") or 0) for row in competitors),
        "total_debriefs": total_debriefs,
        "open_actions": len(open_actions),
        "driver_count": len(driver_rows),
        "top_driver": driver_rows[0]["driver"] if driver_rows else "",
    }

    context = {
        "stats": stats,
        "win_loss_rows": win_loss_rows,
        "competitor_rows": competitor_rows,
        "driver_rows": driver_rows,
        "open_actions": open_actions,
        "result_choices": OpportunityOutcome.RESULT_CHOICES,
    }
    return render(request, "sales/salesanalytics/boards/win_loss_console.html", context)


def _decision_driver_rows(tenant):
    """Aggregate the recurring decision drivers across the tenant's debriefs.

    ``WinLossDebrief.decision_drivers`` is a JSON list of ``{"driver": str,
    "sentiment": str, ...}`` dicts. A bare string is tolerated too. The count of each driver
    string is the number of times it was cited; the sentiment is the dominant one. Sorted by
    count desc, capped at 20.
    """
    drivers = WinLossDebrief.objects.filter(tenant=tenant).only("decision_drivers")
    counts = {}
    sentiments = {}
    for debrief in drivers:
        for entry in debrief.decision_drivers or []:
            if isinstance(entry, dict):
                name = str(entry.get("driver") or "").strip()
                sentiment = str(entry.get("sentiment") or "").strip()
            else:
                name = str(entry or "").strip()
                sentiment = ""
            if not name:
                continue
            counts[name] = counts.get(name, 0) + 1
            bucket = sentiments.setdefault(name, {})
            if sentiment:
                bucket[sentiment] = bucket.get(sentiment, 0) + 1

    rows = []
    for name, count in counts.items():
        bucket = sentiments.get(name) or {}
        sentiment = ""
        if bucket:
            sentiment = sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        rows.append(
            _row(
                label=name,
                value=count,
                detail=sentiment or "—",
                badge="badge-red" if sentiment == "negative" else (
                    "badge-green" if sentiment == "positive" else "badge-slate"
                ),
                driver=name,
                count=count,
                sentiment=sentiment,
            )
        )
    rows.sort(key=lambda row: (-row["count"], row["driver"]))
    return rows[:20]


# ---------------------------------------------------------------------------
# Console 3 — sales velocity & cycle time
# ---------------------------------------------------------------------------
@login_required
def velocity_console(request):
    """Console 3 — Sales Velocity & Cycle Time.

    Renders over ``apps.sales.opportunity_analytics.sales_stage_age_rows`` (how long every open
    opportunity has sat in its current stage) and ``apps.sales.opportunity_analytics
    .sales_pipeline_rollups`` (open pipeline by stage), plus the ``StageVelocityAnalysis``
    (VCA-) measurements with a **live** bottleneck rank re-derived at render time.

    Context keys: ``stats``, ``stage_age_rows``, ``rollup_rows``, ``bottleneck_rows``,
    ``aging_rows``.

    * ``stage_age_rows`` — the helper rows (already sorted oldest-first), each carrying the
      helper's own keys (``opportunity_number``, ``opportunity_name``, ``pipeline_name``,
      ``stage_name``, ``stage_kind``, ``account_name``, ``owner_name``, ``territory_name``,
      ``currency_code``, ``amount``, ``effective_probability``, ``weighted_amount``,
      ``stage_age_days``, ``target_days``, ``is_stale``, ``stage_entered_at``, ``close_date``)
      PLUS the four uniform display keys.
    * ``rollup_rows`` — the helper rows (``pipeline_name``, ``stage_name``, ``stage_kind``,
      ``currency_code``, ``count``, ``stale_count``, ``amount``, ``weighted_amount``,
      ``sequence``) PLUS the four uniform keys.
    * ``bottleneck_rows`` — the VCA- rows, sorted by ``median_days_in_stage`` desc, each with
      ``live_rank`` (the rank re-derived at render time) shown BESIDE ``bottleneck_rank`` (the
      stored rank), plus the four uniform keys (see ``_analysis_row``).
    * ``aging_rows`` — the 25 oldest stage-age rows, each with ``days_over_target`` (age minus
      the stage target, ``None`` when the stage has no target) and ``is_stale``, plus the four
      uniform keys.
    """
    tenant = getattr(request, "tenant", None)

    stage_ages = _safe(lambda: sales_stage_age_rows(tenant), []) or []
    rollups = _safe(lambda: sales_pipeline_rollups(tenant), []) or []

    stage_age_rows = []
    for raw in stage_ages:
        age_days = int(raw.get("stage_age_days") or 0)
        target_days = raw.get("target_days")
        stage_age_rows.append(
            _row(
                label=raw.get("opportunity_number") or raw.get("opportunity_name") or "—",
                value=age_days,
                detail="{stage} · {pipeline} · {owner}".format(
                    stage=raw.get("stage_name") or "—",
                    pipeline=raw.get("pipeline_name") or "—",
                    owner=raw.get("owner_name") or "—",
                ),
                badge="badge-red" if raw.get("is_stale") else "badge-slate",
                **raw
            )
        )

    rollup_rows = []
    for raw in rollups:
        rollup_rows.append(
            _row(
                label="{pipeline} · {stage}".format(
                    pipeline=raw.get("pipeline_name") or "—", stage=raw.get("stage_name") or "—"
                ),
                value=raw.get("amount") or ZERO,
                detail="{count} open · {currency}".format(
                    count=raw.get("count") or 0, currency=raw.get("currency_label") or "—"
                ),
                badge="badge-amber" if int(raw.get("stale_count") or 0) else "badge-slate",
                **raw
            )
        )

    analyses = list(
        StageVelocityAnalysis.objects.filter(tenant=tenant).select_related(
            "pipeline", "pipeline_stage"
        )
    )
    analyses.sort(key=lambda item: (item.median_days_in_stage or ZERO), reverse=True)
    bottleneck_rows = [
        _analysis_row(analysis, live_rank=index)
        for index, analysis in enumerate(analyses, start=1)
    ]

    aging_rows = []
    for raw in stage_ages[:ROW_LIMIT]:
        age_days = int(raw.get("stage_age_days") or 0)
        target_days = raw.get("target_days")
        over_target = (age_days - target_days) if target_days is not None else None
        aging_rows.append(
            _row(
                label=raw.get("opportunity_number") or raw.get("opportunity_name") or "—",
                value=age_days,
                detail="{stage} · {account} · {over}".format(
                    stage=raw.get("stage_name") or "—",
                    account=raw.get("account_name") or "—",
                    over=("+{over} days over target".format(over=over_target)
                          if over_target is not None else "no stage target"),
                ),
                badge="badge-red" if raw.get("is_stale") else "badge-slate",
                days_over_target=over_target,
                **raw
            )
        )

    ages = [int(raw.get("stage_age_days") or 0) for raw in stage_ages]
    stale_count = sum(1 for raw in stage_ages if raw.get("is_stale"))
    open_pipeline_value = sum((row.get("amount") or ZERO) for row in rollups)
    weighted_pipeline_value = sum((row.get("weighted_amount") or ZERO) for row in rollups)

    stats = {
        "total_stage_ages": len(stage_ages),
        "stale_count": stale_count,
        "stale_pct": round(stale_count / len(stage_ages) * 100, 1) if stage_ages else None,
        "avg_stage_age_days": round(sum(ages) / len(ages), 1) if ages else None,
        "median_stage_age_days": _percentile(ages, 50),
        "max_stage_age_days": max(ages) if ages else None,
        "bottleneck_count": sum(1 for item in analyses if item.is_bottleneck),
        "stage_count": len({row.get("stage_id") for row in rollups if row.get("stage_id")}),
        "open_pipeline_value": open_pipeline_value,
        "open_pipeline_count": sum(int(row.get("count") or 0) for row in rollups),
        "weighted_pipeline_value": weighted_pipeline_value,
    }

    context = {
        "stats": stats,
        "stage_age_rows": stage_age_rows,
        "rollup_rows": rollup_rows,
        "bottleneck_rows": bottleneck_rows,
        "aging_rows": aging_rows,
    }
    return render(request, "sales/salesanalytics/boards/velocity_console.html", context)


# ---------------------------------------------------------------------------
# Console 4 — conversion funnel analytics
# ---------------------------------------------------------------------------
@login_required
def funnel_console(request):
    """Console 4 — Conversion Funnel Analytics.

    Renders over ``apps.crm.analytics.compute_report`` — the PUBLIC entry point — on an
    **in-memory** ``crm.AnalyticsReport`` with ``report_type="funnel"`` (no saved report row is
    created), plus the ``FunnelConversionRecord`` (FNL-) rows.

    Context keys: ``stats``, ``funnel_rows``, ``funnel_report``, ``benchmark_rows``.

    * ``funnel_rows`` — the FNL- rows for the tenant, newest period first (see ``_funnel_row``
      for the key list).
    * ``funnel_report`` — the ``compute_report`` payload: ``{"summary": [{"label", "value"}],
      "columns": [str], "rows": [[...]], "chart_type": str, "chart_label": str,
      "chart_labels": [...], "chart_data": [...]}``. It is ``{}`` when the report could not be
      computed — ``funnel_report_error`` then carries the explanation.
    * ``benchmark_rows`` — the FNL- rows that carry a benchmark value, each tagged with the model
      it came from (see ``_benchmark_row``).
    """
    tenant = getattr(request, "tenant", None)

    report = AnalyticsReport(
        tenant=tenant,
        name="8.12 Funnel",
        report_type="funnel",
        date_range="last_90",
        group_by="month",
    )
    funnel_report = {}
    funnel_report_error = ""
    try:
        funnel_report = compute_report(report) or {}
    except Exception as error:  # a broken report must degrade, never 500 (contract §5)
        funnel_report = {}
        funnel_report_error = str(error)

    records = list(
        FunnelConversionRecord.objects.filter(tenant=tenant).select_related(
            "from_stage", "to_stage", "territory", "owner"
        )
    )
    records.sort(key=lambda item: (item.period_start or timezone.localdate()), reverse=True)
    funnel_rows = [_funnel_row(record) for record in records]

    benchmark_rows = []
    for record in records:
        if record.benchmark_pct is None:
            continue
        benchmark_rows.append(
            _benchmark_row(
                "FunnelConversionRecord",
                record.number,
                record.label,
                record.conversion_rate_pct,
                record.benchmark_pct,
                record.benchmark_source,
                record.benchmark_as_of,
                record.segment,
                unit="pct",
            )
        )

    rates = [float(record.conversion_rate_pct) for record in records if record.conversion_rate_pct]
    total_entered = sum(record.entered_count for record in records)
    total_converted = sum(record.converted_count for record in records)

    stats = {
        "total_records": len(records),
        "avg_conversion_rate_pct": round(sum(rates) / len(rates), 1) if rates else None,
        "total_entered": total_entered,
        "total_converted": total_converted,
        "total_dropoff": sum(record.dropoff_count for record in records),
        "total_skipped": sum(record.skipped_count for record in records),
        "below_benchmark_count": sum(
            1
            for record in records
            if record.benchmark_pct is not None
            and record.conversion_rate_pct < record.benchmark_pct
        ),
        "benchmark_count": len(benchmark_rows),
        "report_rows": len(funnel_report.get("rows") or []),
    }

    context = {
        "stats": stats,
        "funnel_rows": funnel_rows,
        "funnel_report": funnel_report,
        "funnel_report_error": funnel_report_error,
        "benchmark_rows": benchmark_rows,
    }
    return render(request, "sales/salesanalytics/boards/funnel_console.html", context)


# ---------------------------------------------------------------------------
# Console 5 — rep performance scorecards
# ---------------------------------------------------------------------------
@login_required
def rep_scorecard_console(request):
    """Console 5 — Rep Performance Scorecards.

    Renders over the ``RepPerformanceScorecard`` (RPS-) rows, a live ``sales.ActivityLog``
    aggregate for the period, and ``apps.crm.analytics.compute_report`` on an **in-memory**
    ``crm.AnalyticsReport`` with ``report_type="sales_performance"``.

    Context keys: ``stats``, ``scorecard_rows``, ``leaderboard``, ``team_rollup``,
    ``activity_totals``, ``percentile_bands``.

    * ``scorecard_rows`` — the RPS- rows (see ``_scorecard_row`` for the key list).
    * ``leaderboard`` — the same rows re-sorted by ``win_rate_pct`` desc, best first.
    * ``team_rollup`` — ``{"reps", "scorecards", "pipeline_value", "weighted_pipeline_value",
      "revenue_closed", "win_rate_pct", "quota_target", "quota_attainment_pct",
      "activities_logged", "calls_logged", "emails_logged", "meetings_logged",
      "opportunities_won", "opportunities_lost"}``.
    * ``activity_totals`` — the live ``sales.ActivityLog`` aggregate for the period:
      ``{"total", "calls", "emails", "meetings", "sms", "notes", "other", "auto_captured",
      "planned_minutes", "undated_total", "period_start", "period_end"}``.
    * ``percentile_bands`` — ``{"median": float, "p75": float, "p90": float}`` — the percentiles
      of the RPS- rows' ``win_rate_pct``, computed in Python.
    """
    tenant = getattr(request, "tenant", None)

    scorecards = list(
        RepPerformanceScorecard.objects.filter(tenant=tenant).select_related(
            "rep",
            "territory",
            "manager",
            "currency",
            "forecast_period",
            "quota_plan",
            "coaching_scorecard",
        )
    )
    scorecard_rows = [_scorecard_row(scorecard) for scorecard in scorecards]

    leaderboard = sorted(
        scorecard_rows,
        key=lambda row: (
            -(float(row.get("win_rate_pct") or 0)),
            -(float(row.get("revenue_closed") or 0)),
        ),
    )

    team_rollup = _team_rollup(scorecards)
    activity_totals = _activity_totals(tenant, scorecards)
    percentile_bands = _percentile_bands(scorecards)

    performance_report = {}
    performance_report_error = ""
    try:
        performance_report = compute_report(
            AnalyticsReport(
                tenant=tenant,
                name="8.12 Sales Performance",
                report_type="sales_performance",
                date_range="last_90",
                group_by="month",
            )
        ) or {}
    except Exception as error:  # a broken report must degrade, never 500 (contract §5)
        performance_report = {}
        performance_report_error = str(error)

    stats = {
        "total_scorecards": len(scorecards),
        "rep_count": len({scorecard.rep_id for scorecard in scorecards if scorecard.rep_id}),
        "avg_win_rate_pct": _mean(
            [scorecard.win_rate_pct for scorecard in scorecards]
        ),
        "total_pipeline_value": team_rollup["pipeline_value"],
        "total_weighted_pipeline_value": team_rollup["weighted_pipeline_value"],
        "total_revenue_closed": team_rollup["revenue_closed"],
        "avg_quota_attainment_pct": team_rollup["quota_attainment_pct"],
        "on_track_count": sum(
            1
            for scorecard in scorecards
            if scorecard.rating in ("outstanding", "strong", "on_track")
        ),
        "total_activities_logged": team_rollup["activities_logged"],
        "activity_total": activity_totals["total"],
        "report_rows": len(performance_report.get("rows") or []),
    }

    context = {
        "stats": stats,
        "scorecard_rows": scorecard_rows,
        "leaderboard": leaderboard,
        "team_rollup": team_rollup,
        "activity_totals": activity_totals,
        "percentile_bands": percentile_bands,
        "performance_report": performance_report,
        "performance_report_error": performance_report_error,
    }
    return render(request, "sales/salesanalytics/boards/rep_scorecard_console.html", context)


def _team_rollup(scorecards):
    """Sum the tenant's scorecards into one team-level dict."""
    reps = {scorecard.rep_id for scorecard in scorecards if scorecard.rep_id}
    pipeline_value = sum((scorecard.pipeline_value or ZERO) for scorecard in scorecards)
    weighted_pipeline_value = sum(
        (scorecard.weighted_pipeline_value or ZERO) for scorecard in scorecards
    )
    revenue_closed = sum((scorecard.revenue_closed or ZERO) for scorecard in scorecards)
    quota_target = sum((scorecard.quota_target or ZERO) for scorecard in scorecards)
    won = sum(scorecard.opportunities_won for scorecard in scorecards)
    lost = sum(scorecard.opportunities_lost for scorecard in scorecards)
    decided = won + lost
    attainment = (
        round(revenue_closed / quota_target * 100, 1) if quota_target else None
    )
    return {
        "reps": len(reps),
        "scorecards": len(scorecards),
        "pipeline_value": pipeline_value,
        "weighted_pipeline_value": weighted_pipeline_value,
        "revenue_closed": revenue_closed,
        "win_rate_pct": round(won / decided * 100, 1) if decided else None,
        "quota_target": quota_target,
        "quota_attainment_pct": attainment,
        "activities_logged": sum(scorecard.activities_logged for scorecard in scorecards),
        "calls_logged": sum(scorecard.calls_logged for scorecard in scorecards),
        "emails_logged": sum(scorecard.emails_logged for scorecard in scorecards),
        "meetings_logged": sum(scorecard.meetings_logged for scorecard in scorecards),
        "opportunities_won": won,
        "opportunities_lost": lost,
    }


def _activity_totals(tenant, scorecards):
    """Aggregate the tenant's live ``sales.ActivityLog`` rows for the scorecard period.

    The period is the most recent scorecard's ``period_start``..``period_end``; with no
    scorecard the last 90 days are used. Rows are bucketed by ``ActivityType.kind``
    (call / email / meeting / sms / note).
    """
    period_start = None
    period_end = None
    for scorecard in scorecards:
        if scorecard.period_end and (period_end is None or scorecard.period_end > period_end):
            period_end = scorecard.period_end
            period_start = scorecard.period_start
    if period_end is None:
        today = timezone.localdate()
        period_end = today
        period_start = today - timedelta(days=90)

    logs = ActivityLog.objects.filter(tenant=tenant)
    undated_total = logs.filter(occurred_on__isnull=True).count()
    in_period = logs.filter(
        occurred_on__isnull=False, occurred_on__gte=period_start, occurred_on__lte=period_end
    )

    totals = {
        "total": in_period.count(),
        "calls": 0,
        "emails": 0,
        "meetings": 0,
        "sms": 0,
        "notes": 0,
        "other": 0,
        "auto_captured": 0,
        "planned_minutes": 0,
        "undated_total": undated_total,
        "period_start": period_start,
        "period_end": period_end,
    }
    for row in in_period.values("activity_type__kind").annotate(total=Count("id")):
        kind = str(row.get("activity_type__kind") or "").strip().lower()
        count = int(row.get("total") or 0)
        bucket = ACTIVITY_KIND_BUCKETS.get(kind)
        if bucket is None:
            totals["other"] = totals["other"] + count
            continue
        totals[bucket] = totals[bucket] + count
    totals["auto_captured"] = in_period.filter(is_auto_captured=True).count()
    totals["planned_minutes"] = sum(
        (value or 0) for value in in_period.values_list("planned_minutes", flat=True)
    )
    return totals


def _percentile_bands(scorecards):
    """The median / 75th / 90th percentile of the scorecards' ``win_rate_pct``."""
    rates = [
        float(scorecard.win_rate_pct) for scorecard in scorecards if scorecard.win_rate_pct is not None
    ]
    return {
        "median": _percentile(rates, 50) or 0.0,
        "p75": _percentile(rates, 75) or 0.0,
        "p90": _percentile(rates, 90) or 0.0,
    }


# ---------------------------------------------------------------------------
# Console 6 — benchmarking & peer comparison
# ---------------------------------------------------------------------------
@login_required
def benchmark_console(request):
    """Console 6 — Benchmarking & Peer Comparison.

    Renders over the RPS- / FNL- / VCA- **benchmark fields** (the hand-entered benchmark
    values, their source and their as-of date) and over ``apps.sales.models``
    ``QuotaPlan`` (QPA-) for the quota side of the goal gap.

    Context keys: ``stats``, ``peer_rows``, ``percentile_bands``, ``benchmark_rows``,
    ``goal_gap_rows``.

    * ``peer_rows`` — one row per rep (the rep's most recent scorecard), each carrying
      ``rep`` / ``rep_name``, ``scorecard``, ``number``, ``win_rate_pct``,
      ``pipeline_value``, ``revenue_closed``, ``quota_attainment_pct``, ``overall_score``,
      ``rating`` / ``rating_display``, ``segment``, ``benchmark_win_rate_pct``,
      ``goal_gap_value``, plus the four uniform display keys.
    * ``percentile_bands`` — ``{"median": float, "p75": float, "p90": float}`` — the percentiles
      of the RPS- rows' ``win_rate_pct``, computed in Python.
    * ``benchmark_rows`` — every RPS- / FNL- / VCA- row that carries a benchmark value, each
      tagged with the model it came from (see ``_benchmark_row``).
    * ``goal_gap_rows`` — the RPS- rows that carry a ``goal_gap_value``, worst (largest positive
      gap) first, each with ``rep`` / ``rep_name``, ``scorecard``, ``number``,
      ``goal_gap_value``, ``quota_target``, ``revenue_closed``, ``quota_attainment_pct`` plus
      the four uniform display keys.
    """
    tenant = getattr(request, "tenant", None)

    scorecards = list(
        RepPerformanceScorecard.objects.filter(tenant=tenant).select_related(
            "rep",
            "territory",
            "manager",
            "currency",
            "forecast_period",
            "quota_plan",
            "coaching_scorecard",
        )
    )
    scorecards.sort(key=lambda item: (item.period_end or timezone.localdate()), reverse=True)

    peer_rows = _peer_rows(scorecards)
    percentile_bands = _percentile_bands(scorecards)
    benchmark_rows = _benchmark_rows(tenant, scorecards)
    goal_gap_rows = _goal_gap_rows(scorecards)

    quota_plans = list(
        QuotaPlan.objects.filter(tenant=tenant).select_related("quota_ref", "forecast_period")
    )
    quota_target_total = sum(
        (plan.quota_ref.target_amount or ZERO) for plan in quota_plans if plan.quota_ref_id
    )

    stats = {
        "total_scorecards": len(scorecards),
        "rep_count": len({scorecard.rep_id for scorecard in scorecards if scorecard.rep_id}),
        "peer_count": len(peer_rows),
        "avg_win_rate_pct": _mean(
            [scorecard.win_rate_pct for scorecard in scorecards]
        ),
        "median_win_rate_pct": percentile_bands["median"],
        "p75_win_rate_pct": percentile_bands["p75"],
        "p90_win_rate_pct": percentile_bands["p90"],
        "benchmark_rows": len(benchmark_rows),
        "goal_gap_count": len(goal_gap_rows),
        "total_goal_gap": sum((row.get("goal_gap_value") or ZERO) for row in goal_gap_rows),
        "worst_goal_gap": goal_gap_rows[0].get("goal_gap_value") if goal_gap_rows else None,
        "quota_plan_count": len(quota_plans),
        "quota_target_total": quota_target_total,
        "avg_quota_attainment_pct": _percentile(
            [
                float(scorecard.quota_attainment_pct)
                for scorecard in scorecards
                if scorecard.quota_attainment_pct is not None
            ],
            50,
        ),
    }

    context = {
        "stats": stats,
        "peer_rows": peer_rows,
        "percentile_bands": percentile_bands,
        "benchmark_rows": benchmark_rows,
        "goal_gap_rows": goal_gap_rows,
    }
    return render(request, "sales/salesanalytics/boards/benchmark_console.html", context)


def _peer_rows(scorecards):
    """Reduce the scorecards to one row per rep (the rep's most recent scorecard)."""
    latest = {}
    for scorecard in scorecards:
        if scorecard.rep_id is None:
            continue
        if scorecard.rep_id not in latest:
            latest[scorecard.rep_id] = scorecard
    rows = []
    for scorecard in latest.values():
        rows.append(
            _row(
                label=_user_name(scorecard.rep) or scorecard.number,
                value=scorecard.win_rate_pct,
                detail=scorecard.segment or scorecard.get_rating_display(),
                badge=_badge_for_scorecard_rating(scorecard.rating),
                rep=scorecard.rep,
                rep_name=_user_name(scorecard.rep),
                scorecard=scorecard,
                number=scorecard.number,
                win_rate_pct=scorecard.win_rate_pct,
                pipeline_value=scorecard.pipeline_value,
                revenue_closed=scorecard.revenue_closed,
                quota_attainment_pct=scorecard.quota_attainment_pct,
                overall_score=scorecard.overall_score,
                rating=scorecard.rating,
                rating_display=scorecard.get_rating_display(),
                segment=scorecard.segment,
                benchmark_win_rate_pct=scorecard.benchmark_win_rate_pct,
                goal_gap_value=scorecard.goal_gap_value,
                period_start=scorecard.period_start,
                period_end=scorecard.period_end,
            )
        )
    rows.sort(key=lambda row: -(float(row.get("win_rate_pct") or 0)))
    return rows


def _benchmark_rows(tenant, scorecards):
    """Every RPS- / FNL- / VCA- row that carries a benchmark value, tagged with its model."""
    rows = []
    for scorecard in scorecards:
        if scorecard.benchmark_win_rate_pct is not None:
            rows.append(
                _benchmark_row(
                    "RepPerformanceScorecard",
                    scorecard.number,
                    "{rep} — win rate".format(rep=_user_name(scorecard.rep) or scorecard.number),
                    scorecard.win_rate_pct,
                    scorecard.benchmark_win_rate_pct,
                    scorecard.benchmark_source,
                    scorecard.benchmark_as_of,
                    scorecard.segment,
                    unit="pct",
                )
            )
        if scorecard.benchmark_quota_attainment_pct is not None:
            rows.append(
                _benchmark_row(
                    "RepPerformanceScorecard",
                    scorecard.number,
                    "{rep} — quota attainment".format(
                        rep=_user_name(scorecard.rep) or scorecard.number
                    ),
                    scorecard.quota_attainment_pct,
                    scorecard.benchmark_quota_attainment_pct,
                    scorecard.benchmark_source,
                    scorecard.benchmark_as_of,
                    scorecard.segment,
                    unit="pct",
                )
            )
        if scorecard.benchmark_cycle_days is not None:
            rows.append(
                _benchmark_row(
                    "RepPerformanceScorecard",
                    scorecard.number,
                    "{rep} — sales cycle".format(
                        rep=_user_name(scorecard.rep) or scorecard.number
                    ),
                    scorecard.sales_cycle_days,
                    scorecard.benchmark_cycle_days,
                    scorecard.benchmark_source,
                    scorecard.benchmark_as_of,
                    scorecard.segment,
                    unit="days",
                )
            )

    for record in FunnelConversionRecord.objects.filter(tenant=tenant):
        if record.benchmark_pct is None:
            continue
        rows.append(
            _benchmark_row(
                "FunnelConversionRecord",
                record.number,
                record.label,
                record.conversion_rate_pct,
                record.benchmark_pct,
                record.benchmark_source,
                record.benchmark_as_of,
                record.segment,
                unit="pct",
            )
        )

    for analysis in StageVelocityAnalysis.objects.filter(tenant=tenant).select_related(
        "pipeline_stage"
    ):
        if analysis.benchmark_days is None:
            continue
        rows.append(
            _benchmark_row(
                "StageVelocityAnalysis",
                analysis.number,
                "{stage} — median days in stage".format(
                    stage=_related_name(analysis.pipeline_stage, "name") or analysis.number
                ),
                analysis.median_days_in_stage,
                analysis.benchmark_days,
                analysis.benchmark_source,
                analysis.benchmark_as_of,
                analysis.segment,
                unit="days",
            )
        )
    return rows


def _goal_gap_rows(scorecards):
    """The scorecards that carry a goal gap, worst (largest positive gap) first."""
    rows = []
    for scorecard in scorecards:
        if scorecard.goal_gap_value is None:
            continue
        rows.append(
            _row(
                label=_user_name(scorecard.rep) or scorecard.number,
                value=scorecard.goal_gap_value,
                detail="target {target} · closed {closed}".format(
                    target=scorecard.quota_target or ZERO, closed=scorecard.revenue_closed or ZERO
                ),
                badge="badge-red" if scorecard.goal_gap_value > 0 else "badge-green",
                scorecard=scorecard,
                number=scorecard.number,
                rep=scorecard.rep,
                rep_name=_user_name(scorecard.rep),
                goal_gap_value=scorecard.goal_gap_value,
                quota_target=scorecard.quota_target,
                revenue_closed=scorecard.revenue_closed,
                quota_attainment_pct=scorecard.quota_attainment_pct,
                period_start=scorecard.period_start,
                period_end=scorecard.period_end,
            )
        )
    rows.sort(key=lambda row: -(float(row.get("goal_gap_value") or 0)))
    return rows
