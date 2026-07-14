"""CRM 1.12 Inventory & Vendor Management — PartnerPortal views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    PartnerPortalAccess,
    ProductStock,
    PurchaseOrder,
)


# ------------------------------------------------------------ 1.12 Partner portal (partner-facing)
def _portal_access(request):
    """Return the active PartnerPortalAccess row for the logged-in portal user, or None."""
    if not request.user.is_authenticated:
        return None
    return (PartnerPortalAccess.objects
            .filter(portal_user=request.user, tenant=request.tenant, is_active=True)
            .select_related("partner_party").first())


@login_required
def portal_dashboard(request):
    access = _portal_access(request)
    if access is None:
        messages.error(request, "You don't have partner portal access.")
        return redirect("dashboard:home")
    po_count = PurchaseOrder.objects.filter(tenant=request.tenant, vendor=access.partner_party).count()
    return render(request, "crm/vendor/portal_dashboard.html", {"access": access, "po_count": po_count})


@login_required
def portal_po_list(request):
    access = _portal_access(request)
    if access is None:
        messages.error(request, "You don't have partner portal access.")
        return redirect("dashboard:home")
    orders = (PurchaseOrder.objects
              .filter(tenant=request.tenant, vendor=access.partner_party)
              .order_by("-created_at"))
    page_obj = paginate(request, orders)
    return render(request, "crm/vendor/portal_po/list.html",
                  {"access": access, "object_list": page_obj.object_list, "page_obj": page_obj})


@login_required
def portal_stock(request):
    access = _portal_access(request)
    if access is None or not access.can_view_stock:
        messages.error(request, "You don't have access to stock levels.")
        return redirect("crm:portal_dashboard" if access else "dashboard:home")
    products = ProductStock.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    page_obj = paginate(request, products)
    return render(request, "crm/vendor/portal_stock.html",
                  {"access": access, "object_list": page_obj.object_list, "page_obj": page_obj})
