"""HRM 3.20 Continuous Feedback — Kudosbadge views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.ContinuousFeedback._helpers import _visible_feedback_q
from apps.hrm.models import (
    KudosBadge,
)
from apps.hrm.forms import (
    KudosBadgeForm,
)
from apps.hrm.views.ContinuousFeedback._helpers import _visible_feedback_q


# ------------------------------------------------------------ KudosBadge (3.20 recognition catalog)
@login_required
def kudosbadge_list(request):
    return crud_list(
        request,
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        KudosBadge.objects.filter(tenant=request.tenant)
        .annotate(num_feedback=Count("feedback_items")).order_by("name"),
        "hrm/performance/kudosbadge/list.html",
        search_fields=("name", "linked_value"),
        filters=[("is_active", "is_active", False)],
    )


@login_required
def kudosbadge_create(request):
    return crud_create(request, form_class=KudosBadgeForm,
                       template="hrm/performance/kudosbadge/form.html",
                       success_url="hrm:kudosbadge_list")


@login_required
def kudosbadge_detail(request, pk):
    obj = get_object_or_404(KudosBadge, pk=pk, tenant=request.tenant)
    # Confidentiality: a badge's award list must NOT leak private/team feedback recipients to an
    # outsider — filter the recent awards through the SAME visibility gate as feedback_list, so each
    # viewer sees only the badge-carrying feedback they're allowed to (public / own / team).
    recent_qs = obj.feedback_items.filter(tenant=request.tenant).select_related("receiver__party")
    vq = _visible_feedback_q(request)
    if vq is not None:
        recent_qs = recent_qs.filter(vq)
    recent = list(recent_qs.order_by("-created_at")[:10])
    return render(request, "hrm/performance/kudosbadge/detail.html",
                  {"obj": obj, "recent_feedback": recent})


@login_required
def kudosbadge_edit(request, pk):
    return crud_edit(request, model=KudosBadge, pk=pk, form_class=KudosBadgeForm,
                     template="hrm/performance/kudosbadge/form.html",
                     success_url="hrm:kudosbadge_list")


@login_required
@require_POST
def kudosbadge_delete(request, pk):
    return crud_delete(request, model=KudosBadge, pk=pk, success_url="hrm:kudosbadge_list")
