"""Accounting 2.4 Accounts Receivable — CustomerProfiles views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    CustomerProfile,
    Invoice,
    PaymentTerm,
    ZERO,
)
from apps.accounting.forms import (
    CustomerProfileForm,
)


# ============================================================== 2.4 AR — Customer profiles
@login_required
def customer_profile_list(request):
    return crud_list(
        request, CustomerProfile.objects.filter(tenant=request.tenant)
        .select_related("party", "payment_terms", "currency"),
        "accounting/receivable/customer_profile/list.html",
        search_fields=["party__name"],
        filters=[("payment_terms", "payment_terms_id", True), ("credit_on_hold", "credit_on_hold", False),
                 ("is_active", "is_active", False)],
        extra_context={"payment_terms": PaymentTerm.objects.filter(tenant=request.tenant)},
    )


@login_required
def customer_profile_create(request):
    return crud_create(request, form_class=CustomerProfileForm, template="accounting/receivable/customer_profile/form.html",
                       success_url="accounting:customer_profile_list")


@login_required
def customer_profile_detail(request, pk):
    obj = get_object_or_404(
        CustomerProfile.objects.select_related("party", "payment_terms", "currency", "ar_account"),
        pk=pk, tenant=request.tenant,
    )
    invoices = (Invoice.objects.filter(tenant=request.tenant, party=obj.party)
                .order_by("-issue_date")[:5])
    outstanding = (Invoice.objects.filter(tenant=request.tenant, party=obj.party,
                                          status__in=Invoice.OPEN_STATUSES)
                   .aggregate(s=Sum("total"))["s"] or ZERO)
    return render(request, "accounting/receivable/customer_profile/detail.html", {
        "obj": obj, "invoices": invoices, "outstanding": outstanding,
        "over_limit": obj.credit_limit and outstanding > obj.credit_limit,
    })


@login_required
def customer_profile_edit(request, pk):
    return crud_edit(request, model=CustomerProfile, pk=pk, form_class=CustomerProfileForm,
                     template="accounting/receivable/customer_profile/form.html", success_url="accounting:customer_profile_list")


@login_required
@require_POST
def customer_profile_delete(request, pk):
    return crud_delete(request, model=CustomerProfile, pk=pk, success_url="accounting:customer_profile_list")
