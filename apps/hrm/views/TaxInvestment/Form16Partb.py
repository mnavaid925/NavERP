"""HRM 3.16 Tax & Investment — Form16Partb views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.TaxInvestment._helpers import _computation_breakdown
from apps.hrm.models import (
    StatutoryConfig,
    TaxComputation,
)
from apps.hrm.views.TaxInvestment._helpers import _computation_breakdown


@login_required
def form16_partb(request, pk):
    """Form 16 Part B data/report view (PDF rendering deferred). Part A fields come from the linked
    StatutoryReturn + StatutoryConfig; Part B from this computation + its declaration lines."""
    obj = get_object_or_404(
        TaxComputation.objects.select_related("employee__party", "declaration", "statutory_return"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/form16_partb.html", {
        "obj": obj,
        "config": StatutoryConfig.objects.filter(tenant=request.tenant).first(),
        "breakdown": _computation_breakdown(obj),
        "lines": obj.declaration.lines.all(),
    })
