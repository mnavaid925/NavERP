"""HRM 3.19 Performance Review — CalibrationBoard views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PerformanceReview,
    ReviewCycle,
    ZERO,
)


@tenant_admin_required
def calibration_board(request):
    """Report view (no model) — a cycle's manager reviews sorted by effective rating for
    side-by-side calibration. ?cycle=<id> selects the cycle."""
    cycles = ReviewCycle.objects.filter(tenant=request.tenant).order_by("-self_review_start")
    cycle = None
    reviews = []
    cycle_id = request.GET.get("cycle", "").strip()
    if cycle_id.isdigit():
        cycle = ReviewCycle.objects.filter(tenant=request.tenant, pk=int(cycle_id)).first()
    if cycle is None:
        cycle = cycles.first()
    if cycle is not None:
        reviews = list(PerformanceReview.objects.filter(
            tenant=request.tenant, cycle=cycle, review_type="manager")
            .select_related("subject__party", "reviewer__party")
            .prefetch_related("ratings"))
        # Sort by effective rating (calibrated-or-overall) desc; None ratings sort last.
        # BUG FIX: `ZERO` was referenced without a local definition or import — every review with
        # no ratings yet (effective_rating is None, the common state for a brand-new manager
        # review) raised NameError and 500'd this entire view.
        ZERO = Decimal("0")
        reviews.sort(key=lambda r: (r.effective_rating is None,
                                    -(r.effective_rating or ZERO)))
    return render(request, "hrm/performance/calibration_board.html", {
        "cycles": cycles, "cycle": cycle, "reviews": reviews})
