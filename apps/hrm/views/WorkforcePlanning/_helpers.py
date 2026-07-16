"""HRM 3.40 Workforce Planning — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    WorkforceScenario,
)


def _annotate_plan_totals(qs):
    """Annotate the headcount totals WorkforcePlan's properties prefer — without this, rendering N plans
    fires 2N SUM queries (the properties fall back to per-instance aggregates)."""
    return qs.annotate(_total_current=Coalesce(Sum("lines__current_headcount"), 0),
                       _total_planned=Coalesce(Sum("lines__planned_headcount"), 0))


def _normalize_baseline(scenario):
    """Enforce "at most one baseline per plan": when a scenario is saved as the baseline, clear the
    flag on every sibling scenario of the same plan."""
    if scenario.is_baseline:
        WorkforceScenario.objects.filter(plan=scenario.plan).exclude(pk=scenario.pk).update(
            is_baseline=False)
