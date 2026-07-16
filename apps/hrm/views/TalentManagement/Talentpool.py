"""HRM 3.38 Talent Management & Succession — Talentpool views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TalentPool,
    TalentPoolMembership,
)
from apps.hrm.forms import (
    TalentPoolForm,
)


# ---- Talent pools -----------------------------------------------------------------------------
@tenant_admin_required
def talentpool_list(request):
    # Annotate the active-member count the template renders per row — the model property picks the
    # annotation up, so the list stays a fixed query count instead of one COUNT per pool.
    # Explicit order_by — annotate() introduces a GROUP BY, which drops Meta.ordering, and an unordered
    # queryset makes the paginator duplicate/skip rows across pages.
    qs = (TalentPool.objects.filter(tenant=request.tenant).select_related("owner__party")
          .annotate(_active_member_count=Count("memberships",
                                               filter=Q(memberships__status="active"), distinct=True))
          .order_by("pool_type", "name"))
    return crud_list(request, qs, "hrm/talent/talentpool/list.html",
                     search_fields=["name", "description"],
                     filters=[("pool_type", "pool_type", False), ("is_active", "is_active", False)],
                     extra_context={"pool_type_choices": TalentPool.POOL_TYPE_CHOICES})


@tenant_admin_required
def talentpool_create(request):
    return crud_create(request, form_class=TalentPoolForm, template="hrm/talent/talentpool/form.html",
                       success_url="hrm:talentpool_list")


@tenant_admin_required
def talentpool_detail(request, pk):
    obj = get_object_or_404(TalentPool.objects.select_related("owner__party"), pk=pk, tenant=request.tenant)
    members = (obj.memberships.select_related("employee__party", "review")
               .prefetch_related("review__ratings")  # the roster renders each member's 9-box quadrant
               .order_by("-created_at"))
    return render(request, "hrm/talent/talentpool/detail.html", {"obj": obj, "members": members})


@tenant_admin_required
def talentpool_edit(request, pk):
    return crud_edit(request, model=TalentPool, pk=pk, form_class=TalentPoolForm,
                     template="hrm/talent/talentpool/form.html", success_url="hrm:talentpool_list")


@tenant_admin_required
@require_POST
def talentpool_delete(request, pk):
    if TalentPoolMembership.objects.filter(tenant=request.tenant, pool_id=pk).exists():
        messages.error(request, "This pool still has members and can't be deleted.")
        return redirect("hrm:talentpool_detail", pk=pk)
    return crud_delete(request, model=TalentPool, pk=pk, success_url="hrm:talentpool_list")
