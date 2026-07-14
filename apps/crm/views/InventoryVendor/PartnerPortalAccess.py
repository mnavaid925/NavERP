"""CRM 1.12 Inventory & Vendor Management — PartnerPortalAccess views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    PartnerPortalAccess,
)
from apps.crm.forms import (
    PartnerPortalAccessForm,
)


# ------------------------------------------------------------ 1.12 Partner portal access (admin)
@login_required
def partnerportalaccess_list(request):
    return crud_list(
        request,
        PartnerPortalAccess.objects.filter(tenant=request.tenant).select_related(
            "partner_party", "portal_user"),
        "crm/vendor/partnerportalaccess/list.html",
        search_fields=["number", "partner_party__name", "portal_user__username"],
        filters=[("is_active", "is_active", False), ("access_level", "access_level", False)],
        extra_context={"access_choices": PartnerPortalAccess.ACCESS_CHOICES},
    )


@login_required
def partnerportalaccess_create(request):
    return crud_create(request, form_class=PartnerPortalAccessForm,
                       template="crm/vendor/partnerportalaccess/form.html",
                       success_url="crm:partnerportalaccess_list")


@login_required
def partnerportalaccess_detail(request, pk):
    obj = get_object_or_404(
        PartnerPortalAccess.objects.select_related("partner_party", "portal_user"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/vendor/partnerportalaccess/detail.html", {"obj": obj})


@login_required
def partnerportalaccess_edit(request, pk):
    return crud_edit(request, model=PartnerPortalAccess, pk=pk, form_class=PartnerPortalAccessForm,
                     template="crm/vendor/partnerportalaccess/form.html",
                     success_url="crm:partnerportalaccess_list")


@login_required
@require_POST
def partnerportalaccess_delete(request, pk):
    return crud_delete(request, model=PartnerPortalAccess, pk=pk,
                       success_url="crm:partnerportalaccess_list")
