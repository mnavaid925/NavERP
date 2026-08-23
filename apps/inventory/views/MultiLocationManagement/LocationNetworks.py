"""Inventory 5.12 Multi-Location Management — network CRUD views.

Five thin CRUD wrappers over apps.core.crud for the ``LocationNetwork`` [LNW-] config
row (writes tenant-admin gated; reads member-visible with ``is_admin`` hiding the
affordances). The sub-module's ONE computed page lives in its own module,
``GlobalStock.py``, per the frozen entity-file contract (WarehouseMap precedent).

``_scoped`` is the shared tenant-scoped node queryset: every list/detail page renders
the parent and warehouse joins, so the tree never re-queries them per row.
"""
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.MultiLocationManagement.LocationNetworks import (
    LocationNetworkForm,
)
# Through the leaf module, not the package root: this file shipped during the build
# wave, before apps/inventory/models/__init__.py gained its 5.12 lines (integrate
# phase) — attribute access through the not-yet-wired package would raise at import.
from apps.inventory.models.MultiLocationManagement.LocationNetworks import (
    LocationNetwork,
)
from apps.inventory.views._common import *  # noqa: F401,F403

_IS_ACTIVE_CHOICES = [["active", "Active"], ["inactive", "Inactive"]]


def _is_admin(user):
    """The one admin flag every template receives — same test as the decorator."""
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


def _scoped(tenant):
    """Tenant-scoped node queryset with the joins every list/detail page renders."""
    return (LocationNetwork.objects.filter(tenant=tenant)
            .select_related("parent", "warehouse"))


# -- LocationNetwork CRUD -------------------------------------------------------------------------

@login_required
def locationnetwork_list(request):
    qs = _scoped(request.tenant)
    node_type = request.GET.get("node_type", "").strip()
    if node_type in dict(LocationNetwork.NODE_TYPE_CHOICES):
        qs = qs.filter(node_type=node_type)
    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)
    return crud_list(
        request, qs, "inventory/multilocation/locationnetwork/list.html",
        search_fields=["number", "code", "name"],
        extra_context={
            "node_type_choices": LocationNetwork.NODE_TYPE_CHOICES,
            "node_type": node_type,
            "is_active_choices": _IS_ACTIVE_CHOICES,
            "is_active": is_active,
            "is_admin": _is_admin(request.user),
        },
    )


@login_required
def locationnetwork_detail(request, pk):
    """Node detail: ancestry breadcrumb, direct children and the attached site.

    Hand-rolled rather than crud_detail for the same reason wave_detail is:
    children/path_label depend on the resolved object, and crud_detail's
    extra_context is a plain dict evaluated before the helper runs."""
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    admin = _is_admin(request.user)
    return render(request, "inventory/multilocation/locationnetwork/detail.html", {
        "obj": obj,
        "path_label": obj.path(),
        "children": (obj.children.all().order_by("code")
                     .select_related("warehouse")),
        "is_admin": admin,
    })


@tenant_admin_required
def locationnetwork_create(request):
    return crud_create(
        request, form_class=LocationNetworkForm,
        template="inventory/multilocation/locationnetwork/form.html",
        success_url="inventory:locationnetwork_list",
    )


@tenant_admin_required
def locationnetwork_edit(request, pk):
    return crud_edit(
        request, model=LocationNetwork, pk=pk, form_class=LocationNetworkForm,
        template="inventory/multilocation/locationnetwork/form.html",
        success_url="inventory:locationnetwork_list",
    )


@tenant_admin_required
@require_POST
def locationnetwork_delete(request, pk):
    """Deleting a parent reparents its children to roots via SET_NULL — config rows
    have no ledger legs behind them, so plain crud_delete suffices at any time."""
    return crud_delete(request, model=LocationNetwork, pk=pk,
                       success_url="inventory:locationnetwork_list")
