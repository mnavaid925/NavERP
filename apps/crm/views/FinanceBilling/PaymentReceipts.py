"""CRM 1.7 Finance & Billing Management — PaymentReceipts views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    PaymentReceipt,
)
from apps.crm.forms import (
    PaymentReceiptForm,
)


# ------------------------------------------------------------ 1.7 Payment Tracking (PaymentReceipt)
@login_required
def paymentreceipt_list(request):
    return crud_list(
        request,
        PaymentReceipt.objects.filter(tenant=request.tenant).select_related(
            "deal_invoice", "deal_invoice__invoice", "payment"),
        "crm/finance/paymentreceipt/list.html",
        search_fields=["number", "deal_invoice__number", "gateway_txn_id"],
        filters=[("method", "method", False), ("gateway", "gateway", False)],
        extra_context={"method_choices": PaymentReceipt.METHOD_CHOICES,
                       "gateway_choices": PaymentReceipt.GATEWAY_CHOICES},
    )


@login_required
def paymentreceipt_create(request):
    return crud_create(request, form_class=PaymentReceiptForm,
                       template="crm/finance/paymentreceipt/form.html",
                       success_url="crm:paymentreceipt_list")


@login_required
def paymentreceipt_detail(request, pk):
    obj = get_object_or_404(
        PaymentReceipt.objects.select_related(
            "deal_invoice", "deal_invoice__invoice", "deal_invoice__account", "payment"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/finance/paymentreceipt/detail.html", {"obj": obj})


@login_required
def paymentreceipt_edit(request, pk):
    return crud_edit(request, model=PaymentReceipt, pk=pk, form_class=PaymentReceiptForm,
                     template="crm/finance/paymentreceipt/form.html",
                     success_url="crm:paymentreceipt_list")


@login_required
@require_POST
def paymentreceipt_delete(request, pk):
    return crud_delete(request, model=PaymentReceipt, pk=pk, success_url="crm:paymentreceipt_list")


@login_required
def paymentreceipt_print(request, pk):
    """Standalone printable receipt (browser print → PDF). Server-side PDF (weasyprint) deferred."""
    obj = get_object_or_404(
        PaymentReceipt.objects.select_related(
            "deal_invoice", "deal_invoice__invoice", "deal_invoice__account", "payment"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/finance/paymentreceipt/receipt.html",
                  {"obj": obj, "tenant": request.tenant})
