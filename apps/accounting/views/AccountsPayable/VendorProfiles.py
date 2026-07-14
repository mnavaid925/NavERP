"""Accounting 2.3 Accounts Payable — VendorProfiles views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Bill,
    PaymentTerm,
    VendorProfile,
)
from apps.accounting.forms import (
    VendorProfileForm,
)


# ================================================================ 2.3 AP — Vendor profiles
@login_required
def vendor_profile_list(request):
    return crud_list(
        request, VendorProfile.objects.filter(tenant=request.tenant)
        .select_related("party", "payment_terms", "currency"),
        "accounting/payable/vendor_profile/list.html",
        search_fields=["party__name"],
        filters=[("payment_terms", "payment_terms_id", True), ("is_1099", "is_1099", False),
                 ("is_active", "is_active", False)],
        extra_context={"payment_terms": PaymentTerm.objects.filter(tenant=request.tenant)},
    )


@login_required
def vendor_profile_create(request):
    return crud_create(request, form_class=VendorProfileForm, template="accounting/payable/vendor_profile/form.html",
                       success_url="accounting:vendor_profile_list")


@login_required
def vendor_profile_detail(request, pk):
    obj = get_object_or_404(
        VendorProfile.objects.select_related("party", "payment_terms", "currency", "default_expense_account"),
        pk=pk, tenant=request.tenant,
    )
    bills = (Bill.objects.filter(tenant=request.tenant, party=obj.party)
             .order_by("-bill_date")[:5])
    return render(request, "accounting/payable/vendor_profile/detail.html", {"obj": obj, "bills": bills})


@login_required
def vendor_profile_edit(request, pk):
    return crud_edit(request, model=VendorProfile, pk=pk, form_class=VendorProfileForm,
                     template="accounting/payable/vendor_profile/form.html", success_url="accounting:vendor_profile_list")


@login_required
@require_POST
def vendor_profile_delete(request, pk):
    return crud_delete(request, model=VendorProfile, pk=pk, success_url="accounting:vendor_profile_list")
