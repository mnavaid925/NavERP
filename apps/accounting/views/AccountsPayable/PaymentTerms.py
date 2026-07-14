"""Accounting 2.3 Accounts Payable — PaymentTerms views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    PaymentTerm,
)
from apps.accounting.forms import (
    PaymentTermForm,
)


# =============================================================== 2.3 AP — Payment terms
@login_required
def payment_term_list(request):
    return crud_list(
        request, PaymentTerm.objects.filter(tenant=request.tenant),
        "accounting/payable/payment_term/list.html",
        search_fields=["name"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def payment_term_create(request):
    return crud_create(request, form_class=PaymentTermForm, template="accounting/payable/payment_term/form.html",
                       success_url="accounting:payment_term_list")


@login_required
def payment_term_detail(request, pk):
    obj = get_object_or_404(PaymentTerm, pk=pk, tenant=request.tenant)
    return render(request, "accounting/payable/payment_term/detail.html", {"obj": obj})


@login_required
def payment_term_edit(request, pk):
    return crud_edit(request, model=PaymentTerm, pk=pk, form_class=PaymentTermForm,
                     template="accounting/payable/payment_term/form.html", success_url="accounting:payment_term_list")


@login_required
@require_POST
def payment_term_delete(request, pk):
    return crud_delete(request, model=PaymentTerm, pk=pk, success_url="accounting:payment_term_list")
