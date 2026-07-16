"""HRM 3.16 Tax & Investment — RegimeComparison views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.TaxInvestment._helpers import _computation_breakdown
from apps.hrm.models import (
    TaxComputation,
)
from apps.hrm.views.TaxInvestment._helpers import _computation_breakdown


@login_required
def tax_regime_comparison(request):
    """Read-only old-vs-new comparison for a chosen TaxComputation (no new model)."""
    comp = None
    comp_id = request.GET.get("computation", "").strip()
    if comp_id.isdigit():
        comp = (TaxComputation.objects.filter(tenant=request.tenant, pk=comp_id)
                .select_related("employee__party", "declaration").first())
    ctx = {
        "comp": comp,
        "computations": (TaxComputation.objects.filter(tenant=request.tenant)
                         .select_related("employee__party").order_by("-financial_year")),
    }
    if comp is not None:
        ctx["breakdown"] = _computation_breakdown(comp)
    return render(request, "hrm/tax/regime_comparison.html", ctx)
