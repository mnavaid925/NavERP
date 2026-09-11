"""Projects 7.5 — the Risk Monitoring & Reporting board (computed on read; no model; GET-only).

Bullet **5 Risk Monitoring & Reporting** is five lenses over the register, none of them a stored
snapshot — a snapshot is stale the instant a register row changes:

* **Top risks** — the register ordered by the ordinal pair (``-probability, -impact,
  -cost_impact``). ``score`` is a Python property, not a column, so a stable DB ordering is the
  honest one (the ``rsk_list`` ``?top=1`` precedent).
* **Burn-down** — register rows aggregated by the month of ``identified_date``: count, summed
  ``score`` and summed EMV per period. Aggregated **in Python** because ``score`` is not a column,
  so a ``values(...).annotate(Sum(...))`` cannot compute it. ``bar_pct`` scales each period's
  ``score_total`` against the largest period's (0-safe).
* **Review queue** — risks whose ``review_date`` has passed while they are still live
  (``review_date`` set, ``< today``, status not in ``("realized", "closed")``), ordered by date.
* **Tolerance** — the documented default appetite (``ProjectRisk.TOLERANCE_BANDS`` — High and
  Critical): the count of open risks above it is the flag. A per-tenant appetite is 7.19's.
* **Lessons lens** — the closed risks' and resolved/closed issues' ``lessons_learned`` read back
  newest-first. It is a LENS, not a store: the knowledge repository is 7.10's (Ruling 3).

**No chart library** (7.16 owns charts) and **no stored snapshot**: the burn-down is CSS bars
(``style="width: {{ row.bar_pct }}%"``) and every figure is recomputed on each request.
"""
from collections import Counter

from apps.core.crud import as_db_int
from apps.projects.models import Project, ProjectIssue, ProjectRisk, q2
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render, timezone
from apps.projects.views._helpers import projects as project_choices

#: The register statuses a risk is still live from — everything but the two terminals.
_LIVE_EXCLUDED = ("realized", "closed")

#: The tolerance label shown on the flag line. The bands themselves live on the model.
TOLERANCE_LABEL = "High / Critical"


def _open_risks(register):
    """The still-live subset of an already-materialised register."""
    return [risk for risk in register if risk.status not in _LIVE_EXCLUDED]


def _burndown(register):
    """Aggregate the register by ``identified_date`` month, ascending, with a 0-safe bar scale."""
    periods = {}
    for risk in register:
        day = risk.identified_date
        key = day.strftime("%Y-%m")
        bucket = periods.setdefault(key, {
            "period": key,
            "label": day.strftime("%b %Y"),
            "count": 0,
            "score_total": 0,
            "emv_total": 0,
        })
        bucket["count"] += 1
        bucket["score_total"] += risk.score
        bucket["emv_total"] += risk.emv
    rows = [periods[key] for key in sorted(periods)]
    for row in rows:
        row["emv_total"] = q2(row["emv_total"])
    burndown_max = max((row["score_total"] for row in rows), default=0)
    for row in rows:
        row["bar_pct"] = (round(100 * row["score_total"] / burndown_max, 1)
                          if burndown_max else 0.0)
    return rows, burndown_max


def _lessons(tenant, register, project=None):
    """Newest-first ``lessons_learned`` from closed risks and resolved/closed issues, cap 25.

    The issue half is anchored to the selected ``project`` exactly like the register the other
    lenses read — with ``?project=`` set, another project's lessons must not leak into the board.
    """
    entries = []
    for risk in register:
        if risk.status == "closed" and (risk.lessons_learned or "").strip():
            entries.append({
                "kind": "Risk",
                "obj": risk,
                "lesson": risk.lessons_learned,
                "at": risk.closed_at or risk.updated_at,
            })
    issues = (ProjectIssue.objects
              .filter(tenant=tenant, status__in=("resolved", "closed"))
              .exclude(lessons_learned=""))
    if project is not None:
        issues = issues.filter(project=project)
    issues = issues.select_related("project")
    for issue in issues:
        if (issue.lessons_learned or "").strip():
            entries.append({
                "kind": "Issue",
                "obj": issue,
                "lesson": issue.lessons_learned,
                "at": issue.resolved_at or issue.updated_at,
            })
    entries.sort(key=lambda entry: entry["at"], reverse=True)
    return entries[:25]


@login_required
def risk_monitoring(request):
    tenant = request.tenant
    project_qs = project_choices(tenant)

    project = None
    project_id = as_db_int(request.GET.get("project"))
    if project_id is not None:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()

    register_qs = (ProjectRisk.objects.filter(tenant=tenant)
                   .select_related("project", "owner"))
    if project is not None:
        register_qs = register_qs.filter(project=project)
    register = list(register_qs)

    open_risks = _open_risks(register)
    open_count = len(open_risks)
    closed_count = sum(1 for risk in register if risk.status == "closed")
    realized_count = sum(1 for risk in register if risk.status == "realized")

    top_risks = sorted(
        register,
        key=lambda risk: (-risk.probability, -risk.impact, -risk.cost_impact, -risk.id))[:25]

    burndown_rows, burndown_max = _burndown(register)

    today = timezone.localdate()
    review_queue = sorted(
        (risk for risk in register
         if risk.review_date and risk.review_date < today
         and risk.status not in _LIVE_EXCLUDED),
        key=lambda risk: risk.review_date)
    review_due_count = len(review_queue)

    above_tolerance_count = sum(
        1 for risk in open_risks if risk.severity_band in ProjectRisk.TOLERANCE_BANDS)
    tolerance = {
        "threshold": TOLERANCE_LABEL,
        "band": sorted(ProjectRisk.TOLERANCE_BANDS),
        "above": above_tolerance_count,
    }

    lessons = _lessons(tenant, register, project)
    lessons_count = len(lessons)

    category_counter = Counter(risk.category for risk in register)
    by_category = {label: category_counter.get(value, 0)
                   for value, label in ProjectRisk.CATEGORY_CHOICES}
    band_counter = Counter(risk.severity_band for risk in register)
    # The band vocabulary is the model's own — a second inline copy here could drift from
    # ``SEVERITY_BANDS`` without any error (a fifth band would silently drop off this strip).
    by_band = {label: band_counter.get(band, 0)
               for band, label in ProjectRisk._BAND_LABELS.items()}

    return render(request, "projects/risk/risk_monitoring.html", {
        "projects": project_qs,
        "project": project,
        "open_count": open_count,
        "closed_count": closed_count,
        "realized_count": realized_count,
        "top_risks": top_risks,
        "burndown_rows": burndown_rows,
        "burndown_max": burndown_max,
        "review_queue": review_queue,
        "review_due_count": review_due_count,
        "tolerance": tolerance,
        "above_tolerance_count": above_tolerance_count,
        "lessons": lessons,
        "lessons_count": lessons_count,
        "by_category": by_category,
        "by_band": by_band,
    })
