"""HRM 3.38 Talent Management & Succession — NineBox views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TalentPool,
    TalentPoolMembership,
    _NINE_BOX_LABELS,
)


@tenant_admin_required
def talent_nine_box(request):
    """The 9-box grid: ACTIVE memberships bucketed by their COMPUTED performance/potential bands
    (rows = potential high→low, cols = performance low→high — the conventional layout). Optional
    ``?pool=<id>`` scope. Members missing either axis are listed separately as unplaced."""
    qs = (TalentPoolMembership.objects.filter(tenant=request.tenant, status="active")
          .select_related("employee__party", "pool", "review")
          .prefetch_related("review__ratings"))  # see talentpoolmembership_list — the 9-box fallback
    pool_id = request.GET.get("pool", "").strip()
    if pool_id.isdigit():
        qs = qs.filter(pool_id=int(pool_id))
    members = list(qs)  # materialize once — the band properties are pure Python, no extra queries

    bands = ["high", "medium", "low"]
    grid = {(perf, pot): [] for perf in bands for pot in bands}
    unplaced = []
    for m in members:
        perf, pot = m.performance_band, m.potential_band
        if perf and pot:
            grid[(perf, pot)].append(m)
        else:
            unplaced.append(m)

    rows = []
    for pot in bands:                                  # potential: high (top) → low (bottom)
        cells = [{"performance": perf, "potential": pot,
                  "label": _NINE_BOX_LABELS.get((perf, pot)),
                  "members": grid[(perf, pot)]}
                 for perf in ["low", "medium", "high"]]  # performance: low (left) → high (right)
        rows.append({"potential": pot, "cells": cells})

    return render(request, "hrm/talent/nine_box.html", {
        "rows": rows, "unplaced": unplaced, "placed_count": len(members) - len(unplaced),
        "total": len(members),
        "pools": TalentPool.objects.filter(tenant=request.tenant, is_active=True).order_by("pool_type", "name")})
