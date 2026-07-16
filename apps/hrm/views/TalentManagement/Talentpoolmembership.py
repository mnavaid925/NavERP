"""HRM 3.38 Talent Management & Succession — Talentpoolmembership views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TalentPool,
    TalentPoolMembership,
)
from apps.hrm.forms import (
    TalentPoolMembershipForm,
)


# ---- Talent pool memberships (the 9-box rows) -------------------------------------------------
@tenant_admin_required
def talentpoolmembership_list(request):
    # review__ratings is prefetched because effective_performance falls back to the review's
    # effective_rating, which (when calibrated_rating is null) derives overall_rating from its rating
    # lines — without this every row would fire a query for them.
    qs = (TalentPoolMembership.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "pool", "review")
          .prefetch_related("review__ratings"))
    return crud_list(request, qs, "hrm/talent/talentpoolmembership/list.html",
                     search_fields=["employee__party__name", "pool__name", "retention_action_plan"],
                     filters=[("pool", "pool_id", True), ("status", "status", False),
                              ("flight_risk", "flight_risk", False)],
                     extra_context={
                         "status_choices": TalentPoolMembership.STATUS_CHOICES,
                         "flight_risk_choices": TalentPoolMembership.FLIGHT_RISK_CHOICES,
                         "pools": TalentPool.objects.filter(tenant=request.tenant, is_active=True)
                         .order_by("pool_type", "name")})


@tenant_admin_required
def talentpoolmembership_create(request):
    return crud_create(request, form_class=TalentPoolMembershipForm,
                       template="hrm/talent/talentpoolmembership/form.html",
                       success_url="hrm:talentpoolmembership_list")


@tenant_admin_required
def talentpoolmembership_detail(request, pk):
    # Bespoke (not crud_detail) so the review's rating lines can be prefetched — the 9-box fallback
    # derives the performance axis from review.effective_rating, which reads them when calibrated_rating
    # is null. Without this the detail page fires one extra query.
    obj = get_object_or_404(
        TalentPoolMembership.objects.select_related("employee__party", "pool", "review")
        .prefetch_related("review__ratings"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/talent/talentpoolmembership/detail.html", {"obj": obj})


@tenant_admin_required
def talentpoolmembership_edit(request, pk):
    return crud_edit(request, model=TalentPoolMembership, pk=pk, form_class=TalentPoolMembershipForm,
                     template="hrm/talent/talentpoolmembership/form.html",
                     success_url="hrm:talentpoolmembership_list")


@tenant_admin_required
@require_POST
def talentpoolmembership_delete(request, pk):
    return crud_delete(request, model=TalentPoolMembership, pk=pk,
                       success_url="hrm:talentpoolmembership_list")
