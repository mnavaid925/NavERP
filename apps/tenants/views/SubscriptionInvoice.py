"""tenants — SubscriptionInvoice views (split from apps/tenants/views.py)."""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    SubscriptionInvoice,
)
from apps.tenants.forms import (
    SubscriptionInvoiceForm,
)


# ========================================================= SubscriptionInvoice
@tenant_admin_required
def subscriptioninvoice_list(request):
    return crud_list(
        request, SubscriptionInvoice.objects.filter(tenant=request.tenant).select_related("subscription"),
        "tenants/subscriptioninvoice/list.html",
        search_fields=["number"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": SubscriptionInvoice.STATUS_CHOICES},
    )


@tenant_admin_required
def subscriptioninvoice_create(request):
    return crud_create(request, form_class=SubscriptionInvoiceForm,
                       template="tenants/subscriptioninvoice/form.html",
                       success_url="tenants:subscriptioninvoice_list")


@tenant_admin_required
def subscriptioninvoice_detail(request, pk):
    obj = get_object_or_404(SubscriptionInvoice.objects.select_related("subscription"),
                            pk=pk, tenant=request.tenant)
    return render(request, "tenants/subscriptioninvoice/detail.html", {"obj": obj})


@tenant_admin_required
def subscriptioninvoice_edit(request, pk):
    return crud_edit(request, model=SubscriptionInvoice, pk=pk, form_class=SubscriptionInvoiceForm,
                     template="tenants/subscriptioninvoice/form.html",
                     success_url="tenants:subscriptioninvoice_list")


@tenant_admin_required
@require_POST
def subscriptioninvoice_delete(request, pk):
    return crud_delete(request, model=SubscriptionInvoice, pk=pk,
                       success_url="tenants:subscriptioninvoice_list")
