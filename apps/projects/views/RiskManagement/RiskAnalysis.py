"""Projects 7.5 — the Qualitative & Quantitative Analysis board (computed on read; no model).

Bullet **2 Qualitative & Quantitative Analysis** is two lenses over the same register:

* **Qualitative** — the 5x5 probability x impact matrix. Every cell carries the count of register
  rows that fall in it and the severity band's badge; the band is read straight off
  :attr:`ProjectRisk.SEVERITY_BANDS`, so the matrix can never disagree with the register's own
  ``severity_band`` property.
* **Quantitative** — the EMV table (``cost_impact x P(probability)`` per risk, the residual total
  beside it) and, on POST, a seeded **Monte Carlo** of the project's exposure.

**The simulation algorithm (pinned, L35 — never raw ``request.GET`` parsing):** the population is
the selected project's risks with ``cost_impact > 0`` and ``status not in ("closed", "realized")``
(a realized risk's cost is actual, not uncertain); with no project selected it is the tenant's
risks under the same filter. ``rng = random.Random(seed)``; each iteration draws one Bernoulli per
risk and sums the cost of the ones that fire —
``total = sum(r.cost_impact for r in population if rng.random() < PROBABILITY_PCT[r.probability] / 100)``.
Percentiles are **nearest-rank** on the sorted sample list
(``sorted_samples[min(n - 1, int(round(p / 100 * (n - 1))))]`` for p in 10/50/80/90) and
``mean = q2(sum(samples) / n)``. ``overrun_probability`` is the 1dp percentage of iterations whose
sampled exposure exceeds the baseline, and ``contingency_delta = q2(p80 - baseline_total)``.

**Documented simplifications.** Simple random sampling is deliberate — Latin Hypercube and
correlation between risks are deferred (they change the draw, not the arithmetic). ``random`` and
``statistics`` come from the stdlib only: no numpy, no scipy. There is **no stored simulation
table** — a persisted snapshot goes stale the instant a register row changes, exactly like a stored
score.

**Ruling 4 — one writer per column.** This page SIZES the contingency (the P80 over the baseline)
and DISPLAYS it. The write to ``CostControlAccount.contingency`` stays 7.4's; the link between a
risk and its account is the read-only ``contingency_account`` lens. **No chart library** — 7.16 owns
charts; the matrix and the percentile table are the whole rendering here.
"""
import random

from django import forms
from django.db.models import Sum

from apps.core.crud import as_db_int
from apps.projects.models import (
    BudgetRevision, Project, ProjectBudgetLine, ProjectRisk, q2)
from apps.projects.models.RiskManagement.ProjectRisks import PROBABILITY_PCT
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render
from apps.projects.views._helpers import projects as project_choices

#: The effective defaults when the query string carries no (or junk) parameters. Always shown.
DEFAULT_SEED = 42
DEFAULT_ITERATIONS = 1000
MIN_ITERATIONS, MAX_ITERATIONS = 100, 10000

#: The register statuses whose cost is still uncertain. A realized risk's cost is actual spend.
_UNCERTAIN_EXCLUDED = ("closed", "realized")

#: Severity band -> the badge class the matrix and the tables switch on (L33 colour names only).
_BAND_BADGES = {
    "low": "badge-green",
    "medium": "badge-info",
    "high": "badge-amber",
    "critical": "badge-red",
}


class SimulationParamsForm(forms.Form):
    """The Monte Carlo parameters, parsed as a form (L35) so a junk ``?seed=abc`` is a validation
    error that falls back to the default — never a hand-rolled ``int()`` that 500s on a URL anyone
    can type. The 100–10000 range is the view's clamp, not a form rule: an out-of-range
    ``iterations`` is clamped, not discarded, and it must not take a valid ``seed`` down with it
    (the view resolves each field independently)."""

    seed = forms.IntegerField(required=False)
    iterations = forms.IntegerField(required=False)


def _band_for_score(score):
    """The ``SEVERITY_BANDS`` key for a 1-25 score — mirrors ``ProjectRisk.severity_band``."""
    for band, (low, high) in ProjectRisk.SEVERITY_BANDS.items():
        if low <= score <= high:
            return band
    return "low"


def _percentile(ordered, p):
    """Nearest-rank percentile over an already-sorted sample list. ``None`` for an empty list."""
    n = len(ordered)
    if not n:
        return None
    return ordered[min(n - 1, int(round(p / 100 * (n - 1))))]


def _mean(ordered):
    """The arithmetic mean of the samples (``None`` when empty); the caller ``q2``s it."""
    n = len(ordered)
    if not n:
        return None
    return sum(ordered) / n


def _overrun_probability(ordered, baseline_total):
    """1dp percentage of iterations whose exposure exceeds the baseline; ``None`` without one."""
    n = len(ordered)
    if not n or baseline_total is None:
        return None
    over = sum(1 for sample in ordered if sample > baseline_total)
    return round(100 * over / n, 1)


def _build_matrix(register):
    """The 5x5 grid as 5 rows (probability 5 -> 1), each a list of 5 cells (impact 1 -> 5)."""
    buckets = {(p, i): [] for p in range(1, 6) for i in range(1, 6)}
    for risk in register:
        buckets[(risk.probability, risk.impact)].append(risk)
    matrix, matrix_max = [], 0
    for probability in range(5, 0, -1):
        row = []
        for impact in range(1, 6):
            risks = buckets[(probability, impact)]
            count = len(risks)
            matrix_max = max(matrix_max, count)
            row.append({
                "probability": probability,
                "impact": impact,
                "count": count,
                "badge": _BAND_BADGES[_band_for_score(probability * impact)],
                "risks": risks,
            })
        matrix.append(row)
    return matrix, matrix_max


@login_required
def risk_analysis(request):
    tenant = request.tenant
    project_qs = project_choices(tenant)

    project = None
    project_id = as_db_int(request.GET.get("project"))
    if project_id is not None:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()

    register_qs = ProjectRisk.objects.filter(tenant=tenant).select_related("project")
    if project is not None:
        register_qs = register_qs.filter(project=project)
    register = list(register_qs)

    # -- baseline: the 7.4 cost baseline (approved + activated), read-only -----------------------
    baseline, baseline_total = None, None
    if project is not None:
        baseline = (BudgetRevision.objects
                    .filter(tenant=tenant, project=project, status="approved",
                            activated_at__isnull=False)
                    .order_by("-activated_at")
                    .first())
        if baseline is not None:
            baseline_total = q2(ProjectBudgetLine.objects
                                .filter(budget_revision=baseline)
                                .aggregate(total=Sum("amount"))["total"])

    # -- qualitative: the matrix + the EMV table -------------------------------------------------
    matrix, matrix_max = _build_matrix(register)

    emv_rows = [{
        "risk": risk,
        "probability_pct": PROBABILITY_PCT.get(risk.probability, 0),
        "cost_impact": risk.cost_impact,
        "emv": risk.emv,
    } for risk in register]
    emv_rows.sort(key=lambda row: row["emv"], reverse=True)
    emv_total = q2(sum((row["emv"] for row in emv_rows), 0))
    residual_emv_total = q2(sum((risk.residual_emv for risk in register), 0))

    # -- parameters: through the form, never raw parsing (L35) -----------------------------------
    # The form binds the POST body on POST and the query string otherwise, but each field
    # resolves independently and falls back to the query string when the bound data did not
    # supply it: a bookmarked ``?seed=123&iterations=500`` must survive the on-page form's POST
    # (whose action carries only ``?project=``), and one field's junk must not discard the
    # other's valid value.
    params = SimulationParamsForm(request.POST if request.method == "POST" else request.GET)
    query_params = SimulationParamsForm(request.GET)

    def _param(name):
        """One parameter's cleaned value — bound data first, the query string as fallback."""
        for bound in (params, query_params):
            if name in bound.data:
                # Junk in the bound data is junk (default); only an *absent* field falls
                # through to the query string.
                return None if name in bound.errors else bound.cleaned_data.get(name)
        return None

    seed = _param("seed")
    iterations = _param("iterations")
    seed = DEFAULT_SEED if seed is None else seed
    iterations = DEFAULT_ITERATIONS if iterations is None else iterations
    iterations = max(MIN_ITERATIONS, min(MAX_ITERATIONS, iterations))

    # -- quantitative: the seeded Monte Carlo (POST only) ----------------------------------------
    run = request.method == "POST"
    simulation = None
    if run:
        # Derived from the already-materialised register instead of a second table scan — the
        # population is strictly the register's rows with a cost and an uncertain status. The
        # RNG draws in ``population`` order, so the pinned id-ascending order must survive.
        population = sorted(
            (risk for risk in register
             if risk.cost_impact > 0 and risk.status not in _UNCERTAIN_EXCLUDED),
            key=lambda risk: risk.id)
        rng = random.Random(seed)
        # ``PROBABILITY_PCT[...] / 100`` is a pure function of the row, so it is hoisted out of
        # the iterations x n inner loop. The draw order is unchanged, so a seed stays reproducible.
        draws = [(risk.cost_impact, PROBABILITY_PCT.get(risk.probability, 0) / 100)
                 for risk in population]
        samples = [
            sum(cost for cost, p in draws if rng.random() < p)
            for _ in range(iterations)
        ]
        ordered = sorted(samples)
        simulation = {
            "mean": q2(_mean(ordered)),
            "p10": _percentile(ordered, 10),
            "p50": _percentile(ordered, 50),
            "p80": _percentile(ordered, 80),
            "p90": _percentile(ordered, 90),
            "samples": ordered,
            "baseline_total": baseline_total,
            "overrun_probability": _overrun_probability(ordered, baseline_total),
            "contingency_delta": (None if baseline_total is None
                                  else q2(_percentile(ordered, 80) - baseline_total)),
        }

    return render(request, "projects/risk/risk_analysis.html", {
        "projects": project_qs,
        "project": project,
        "baseline": baseline,
        "baseline_total": baseline_total,
        "matrix": matrix,
        "matrix_max": matrix_max,
        "emv_rows": emv_rows[:50],
        "emv_total": emv_total,
        "residual_emv_total": residual_emv_total,
        "seed": seed,
        "iterations": iterations,
        "run": run,
        "simulation": simulation,
    })
