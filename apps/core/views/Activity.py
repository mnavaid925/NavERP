"""core — Activity views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.views._common import _parties
from apps.core.models import (
    Activity,
)
from apps.core.forms import (
    ActivityForm,
)


# -------------------------------------------------------------------------- Activity
@login_required
def activity_list(request):
    return crud_list(
        request, Activity.objects.filter(tenant=request.tenant).select_related("owner", "party"),
        "core/activity/list.html",
        search_fields=["subject"],
        filters=[("kind", "kind", False), ("status", "status", False), ("owner", "owner_id", True)],
        extra_context={"kind_choices": Activity.KIND_CHOICES,
                       "status_choices": Activity.STATUS_CHOICES,
                       "parties": _parties(request),
                       "owners": User.objects.filter(tenant=request.tenant)
                       .only("id", "email", "first_name", "last_name")},
    )


@login_required
def activity_create(request):
    return crud_create(request, form_class=ActivityForm, template="core/activity/form.html",
                       success_url="core:activity_list")


@login_required
def activity_detail(request, pk):
    return crud_detail(request, model=Activity, pk=pk, template="core/activity/detail.html",
                       select_related=["owner", "party"])


@login_required
def activity_edit(request, pk):
    return crud_edit(request, model=Activity, pk=pk, form_class=ActivityForm,
                     template="core/activity/form.html", success_url="core:activity_list")


@login_required
@require_POST
def activity_delete(request, pk):
    return crud_delete(request, model=Activity, pk=pk, success_url="core:activity_list")
