"""Inventory 5.7 Stock Movement & Transfers — TransferRoute views.

Standard tenant-scoped CRUD over the routing catalog (**Transfer Routing bullet**).
The routes attach to movements at submit time on the board; nothing here posts,
moves, or gates anything. Like 5.3's policy catalog, the WRITES are tenant-admin
gated — a route decides what a submitted movement may travel by; reads stay open
to every signed-in member.
"""
from apps.core.decorators import tenant_admin_required
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import TransferRouteForm
from apps.inventory.models import TransferRoute


def _scoped(tenant):
    return (TransferRoute.objects.filter(tenant=tenant)
            .select_related("origin_location", "destination_location"))


@login_required
def transferroute_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/transfers/route/list.html",
        search_fields=["name", "code", "origin_location__code", "destination_location__code"],
        filters=[("mode", "mode", False), ("is_active", "is_active", False)],
        extra_context={
            "mode_choices": TransferRoute.MODE_CHOICES,
            # Writes are tenant-admin gated server-side; hide the affordances to match.
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def transferroute_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    # Movements that actually travel this route, newest first — usage proof, not a claim.
    transfers = (obj.transfers.select_related("from_location", "to_location")
                 .order_by("-transfer_date", "-id")[:10])
    return render(request, "inventory/transfers/route/detail.html", {
        "obj": obj,
        "transfers": transfers,
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@login_required
@tenant_admin_required
def transferroute_create(request):
    return crud_create(
        request, form_class=TransferRouteForm,
        template="inventory/transfers/route/form.html",
        success_url="inventory:transferroute_list",
    )


@login_required
@tenant_admin_required
def transferroute_edit(request, pk):
    return crud_edit(
        request, model=TransferRoute, pk=pk, form_class=TransferRouteForm,
        template="inventory/transfers/route/form.html",
        success_url="inventory:transferroute_list",
    )


@login_required
@tenant_admin_required
@require_POST
def transferroute_delete(request, pk):
    # The spine's FK is SET_NULL precisely so a route can be retired without touching
    # history: movements that used it keep their number trail in core.AuditLog.
    return crud_delete(request, model=TransferRoute, pk=pk,
                       success_url="inventory:transferroute_list")
