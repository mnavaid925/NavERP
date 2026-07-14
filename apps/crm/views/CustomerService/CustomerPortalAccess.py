"""CRM 1.4 Customer Service & Support — CustomerPortalAccess views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CustomerPortalAccess,
)
from apps.crm.forms import (
    CustomerPortalAccessForm,
)


# ------------------------------------------------------------ Customer portal access (1.4, admin)
@login_required
def customerportalaccess_list(request):
    return crud_list(
        request,
        CustomerPortalAccess.objects.filter(tenant=request.tenant).select_related("customer_party", "portal_user"),
        "crm/service/customerportalaccess/list.html",
        search_fields=["number", "customer_party__name", "portal_user__username"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@tenant_admin_required  # granting a customer a portal login that reads their cases is an IAM action
def customerportalaccess_create(request):
    return crud_create(request, form_class=CustomerPortalAccessForm,
                       template="crm/service/customerportalaccess/form.html",
                       success_url="crm:customerportalaccess_list")


@login_required
def customerportalaccess_detail(request, pk):
    obj = get_object_or_404(
        CustomerPortalAccess.objects.select_related("customer_party", "portal_user"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/service/customerportalaccess/detail.html", {"obj": obj})


@tenant_admin_required
def customerportalaccess_edit(request, pk):
    return crud_edit(request, model=CustomerPortalAccess, pk=pk, form_class=CustomerPortalAccessForm,
                     template="crm/service/customerportalaccess/form.html",
                     success_url="crm:customerportalaccess_list")


@tenant_admin_required
@require_POST
def customerportalaccess_delete(request, pk):
    return crud_delete(request, model=CustomerPortalAccess, pk=pk,
                       success_url="crm:customerportalaccess_list")
