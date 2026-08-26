"""Procurement 6.4 Vendor Management — VendorPortalAccess (VPA-) views.

Binding writes are admin-gated like every other rule table; list/detail stay
member-readable so staff can see which login maps to which supplier before
troubleshooting a gated portal page.
"""
from django.db.models import Count, Q

from apps.core.decorators import tenant_admin_required
from apps.procurement.forms import VendorPortalAccessForm
from apps.procurement.models import VendorPortalAccess
from apps.procurement.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    return (VendorPortalAccess.objects.filter(tenant=tenant)
            .select_related("supplier", "portal_user", "invited_by"))


def _is_admin(request):
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


@login_required
def vpa_list(request):
    # Counts run off a JOIN-FREE queryset on purpose: aggregate() does not strip unused
    # select_related joins, and the footer numbers would otherwise drag four LEFT JOINs
    # through a whole-tenant COUNT on every render.
    base = VendorPortalAccess.objects.filter(tenant=request.tenant)
    counts = base.aggregate(total=Count("id"), active=Count("id", filter=Q(is_active=True)))
    return crud_list(
        request, _scoped(request.tenant),
        "procurement/vendormanagement/portal-access/list.html",
        search_fields=["supplier__name", "portal_user__username", "note"],
        filters=[("state", "is_active", False)],
        extra_context={
            "access_count": counts["total"],
            "active_count": counts["active"],
            "is_admin": _is_admin(request),
        },
    )


@login_required
def vpa_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "procurement/vendormanagement/portal-access/detail.html", {
        "obj": obj,
        "is_admin": _is_admin(request),
    })


@tenant_admin_required
def vpa_create(request):
    """Hand-rolled mirror of crud_create for the ONE thing the generic helper cannot do:
    stamp ``invited_by`` from the session user — the audit column answering who issued
    this binding. Everything else (tenant guard, form flow, messages) matches it exactly."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = VendorPortalAccessForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.invited_by = request.user
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Portal access {obj.number} created.")
            return redirect("procurement:vpa_detail", pk=obj.pk)
    else:
        form = VendorPortalAccessForm(tenant=request.tenant)
    return render(request, "procurement/vendormanagement/portal-access/form.html", {
        "form": form,
        "is_edit": False,
    })


@tenant_admin_required
def vpa_edit(request, pk):
    return crud_edit(
        request, model=VendorPortalAccess, pk=pk, form_class=VendorPortalAccessForm,
        template="procurement/vendormanagement/portal-access/form.html",
        success_url="procurement:vpa_list",
    )


@tenant_admin_required
@require_POST
def vpa_delete(request, pk):
    return crud_delete(request, model=VendorPortalAccess, pk=pk,
                       success_url="procurement:vpa_list")
