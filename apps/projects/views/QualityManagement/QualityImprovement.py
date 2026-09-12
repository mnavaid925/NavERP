"""Projects 7.6 — the Continuous Improvement & Maturity board (computed on read; no model).

Bullet **4 Continuous Improvement** as one GET-only page over the register and the punch list:

* **The improvement register** — the ``kaizen_event`` / ``retrospective`` reviews with their
  improvement actions, owners and due dates (the ceremony and the minutes are 7.13's and 7.9's;
  the repository the lessons feed is 7.10's — Ruling 6).
* **The process-maturity assessment** — a computed 1–5 score over the reviews' own
  ``maturity_score`` entries (60%) and the defect closure rate (40%), banded CMMI-style. **No
  stored maturity table** — a stored score goes stale the instant a review is scored or a defect
  closes (the 7.5 Monte-Carlo ruling). With no scored reviews and no defects there is no score at
  all — a band computed from nothing would be a lie.
* **The defect trend** — opened vs dispositioned per month over the last six months, CSS bars,
  **not a chart** (7.16 owns charts).
* **The lessons lens** — closed defects that left a non-empty ``lessons_learned``, newest first,
  cap 25 (the 7.5 monitoring page's lessons idiom).

Closure counts defects whose status is ``resolved`` or ``closed``: a dispositioned defect has had
its work done even if the bureaucratic close has not run yet, and a maturity figure that ignores
dispositioned work under-plates the project.
"""
import datetime

from django.db.models import Avg, Count

from apps.core.crud import as_db_int
from apps.projects.models import Project, QualityDefect, QualityReview
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render
from apps.projects.views._helpers import projects as project_choices

#: The bullet-4 improvement half of the review-type vocabulary.
_IMPROVEMENT_TYPES = ("kaizen_event", "retrospective")

#: Improvement statuses that still owe work — the open-action count reads them.
_OPEN_IMPROVEMENT_STATUSES = ("planned", "in_progress")

#: The live defect statuses — an open punch list is what the closure rate is measured against.
_OPEN_DEFECT_STATUSES = ("open", "in_progress")

#: A defect that has been dispositioned — resolved or closed, the closure rate's numerator.
_CLOSED_DEFECT_STATUSES = ("resolved", "closed")

#: How many months the trend table reaches back (including the current one).
_TREND_MONTHS = 6

#: Working-set cap on the trend's single date pass (the RiskAnalysis register-cap idiom). A
#: register large enough to hit it makes the trend a partial view — but an unparameterised
#: whole-table pass in the request thread is the worse failure.
_REGISTER_CAP = 2000

#: Cap on the rendered register rows and the lessons lens — the page is a lens, not a register.
_ROW_CAP = 25

#: CMMI-style bands for the computed 1–5 maturity score: (upper bound, badge class).
_MATURITY_BANDS = [
    (1.9999, ("Initial", "badge-red")),
    (2.9999, ("Managed", "badge-amber")),
    (3.9999, ("Defined", "badge-info")),
    (4.9999, ("Quantitatively Managed", "badge-green")),
    (5.0, ("Optimizing", "badge-green")),
]


def _maturity_band(score):
    for upper, band in _MATURITY_BANDS:
        if score <= upper:
            return band
    return _MATURITY_BANDS[-1][1]


def _compute_maturity(defects, review_agg):
    """The 1–5 maturity figure over this scope's reviews and defects — computed, never stored.

    60% the reviews' own ``maturity_score`` average, 40% the defect closure rate. The review
    half arrives pre-aggregated (a ``Count``/``Avg`` over ``maturity_score``) so the whole
    register is never materialised for one average. With no scored reviews the closure rate
    stands alone; with neither, the score is ``None`` and the template renders the no-data
    state rather than a band computed from nothing.
    """
    defects_total = defects.count()
    defects_closed = defects.filter(status__in=_CLOSED_DEFECT_STATUSES).count()
    closure_pct = round(defects_closed / defects_total * 100) if defects_total else 0
    closure_component = closure_pct / 20  # 0–100% onto the 0–5 scale
    reviews_scored = review_agg["n"] or 0
    if reviews_scored:
        score = round(0.6 * review_agg["avg"] + 0.4 * closure_component, 1)
    elif defects_total:
        score = round(closure_component, 1)
    else:
        score = None
    maturity = {
        # 0.0 is a real score (defects exist, 0% closure) — ``has_score`` lets the template
        # distinguish "no score computed" from a falsy zero and still render the band.
        "has_score": score is not None,
        "reviews_scored": reviews_scored,
        "defects_total": defects_total,
        "defects_closed": defects_closed,
        "closure_pct": closure_pct,
        "score": score,
        "band": None,
        "badge": "badge-muted",
    }
    if score is not None:
        maturity["band"], maturity["badge"] = _maturity_band(score)
    return maturity


def _defect_trend(defects):
    """Opened vs dispositioned per month over the last ``_TREND_MONTHS`` months — period rows for
    CSS bars, scaled against the busiest single figure. One capped pass over the two date columns
    buckets the months in Python (the RiskAnalysis register-cap idiom) instead of two COUNTs per
    month — the ``resolved_at`` half wraps the column and would be unindexable anyway. The stamp
    is converted to a local date, the same semantics the ``__date`` lookup gave, so the month
    bounds stay plain dates — no aware/naive datetime mixing."""
    today = timezone.localdate()
    months = []
    year, month = today.year, today.month
    for _ in range(_TREND_MONTHS):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()

    buckets = {m: {"opened": 0, "closed": 0} for m in months}
    for row in defects.values("identified_date", "resolved_at")[:_REGISTER_CAP]:
        identified = row["identified_date"]
        if identified is not None and (identified.year, identified.month) in buckets:
            buckets[(identified.year, identified.month)]["opened"] += 1
        resolved_at = row["resolved_at"]
        if resolved_at is not None:
            resolved = timezone.localdate(resolved_at)
            if (resolved.year, resolved.month) in buckets:
                buckets[(resolved.year, resolved.month)]["closed"] += 1

    rows, trend_max = [], 0
    for year, month in months:
        start = datetime.date(year, month, 1)
        counts = buckets[(year, month)]
        trend_max = max(trend_max, counts["opened"], counts["closed"])
        rows.append({"period": f"{year:04d}-{month:02d}",
                     "label": start.strftime("%b %Y"),
                     "opened": counts["opened"], "closed": counts["closed"]})
    for row in rows:
        row["bar_pct"] = (round(max(row["opened"], row["closed"]) / trend_max * 100)
                          if trend_max else 0)
    return rows, trend_max


@login_required
def quality_improvement(request):
    tenant = request.tenant
    project = None
    project_id = as_db_int(request.GET.get("project"))
    if project_id is not None:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()

    reviews_qs = QualityReview.objects.filter(tenant=tenant).select_related(
        "project", "reviewer", "improvement_owner")
    defects_qs = QualityDefect.objects.filter(tenant=tenant).select_related(
        "project", "wbs_node", "owner")
    if project is not None:
        reviews_qs = reviews_qs.filter(project=project)
        defects_qs = defects_qs.filter(project=project)

    improvement_rows = list(reviews_qs.filter(review_type__in=_IMPROVEMENT_TYPES)
                            .order_by("-review_date", "-id")[:_ROW_CAP])
    # The maturity figure needs one aggregate over the scored reviews — the register itself is
    # never materialised for an average.
    review_agg = reviews_qs.aggregate(n=Count("maturity_score"), avg=Avg("maturity_score"))

    trend_rows, trend_max = _defect_trend(defects_qs)

    closed_with_lesson = (defects_qs.filter(status="closed")
                          .exclude(lessons_learned="").order_by("-created_at", "-id"))
    lessons = [{"obj": d, "lesson": d.lessons_learned} for d in closed_with_lesson[:_ROW_CAP]]
    lessons_count = closed_with_lesson.count()

    return render(request, "projects/quality/quality_improvement.html", {
        "projects": project_choices(tenant),
        "project": project,
        "improvement_rows": improvement_rows,
        "maturity": _compute_maturity(defects_qs, review_agg),
        "defect_trend_rows": trend_rows,
        "defect_trend_max": trend_max,
        "lessons": lessons,
        "lessons_count": lessons_count,
        "open_defect_count": defects_qs.filter(status__in=_OPEN_DEFECT_STATUSES).count(),
        "improvement_open_count": reviews_qs.filter(
            review_type__in=_IMPROVEMENT_TYPES,
            improvement_status__in=_OPEN_IMPROVEMENT_STATUSES).count(),
    })
