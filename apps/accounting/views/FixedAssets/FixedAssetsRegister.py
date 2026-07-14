"""Accounting 2.6 Fixed Assets — FixedAssetsRegister views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _first_account, _post_journal_entry
from apps.accounting.models import (
    FixedAsset,
    ZERO,
)
from apps.accounting.forms import (
    FixedAssetForm,
)


# ============================================================== 2.6 Fixed Assets
@login_required
def fixed_asset_list(request):
    return crud_list(
        request, FixedAsset.objects.filter(tenant=request.tenant).select_related("location"),
        "accounting/assets/fixed_asset/list.html",
        search_fields=["number", "name", "category"],
        filters=[("status", "status", False), ("method", "method", False)],
        extra_context={"status_choices": FixedAsset.STATUS_CHOICES, "method_choices": FixedAsset.METHOD_CHOICES},
    )


@login_required
def fixed_asset_create(request):
    return crud_create(request, form_class=FixedAssetForm, template="accounting/assets/fixed_asset/form.html",
                       success_url="accounting:fixed_asset_list")


@login_required
def fixed_asset_detail(request, pk):
    obj = get_object_or_404(
        FixedAsset.objects.select_related("custodian", "location", "asset_account",
                                          "accumulated_account", "expense_account"),
        pk=pk, tenant=request.tenant)
    return render(request, "accounting/assets/fixed_asset/detail.html", {
        "obj": obj,
        "book_value": obj.book_value(),
        "next_depreciation": obj.period_depreciation(),
        "disposals": obj.disposals.all()[:5],
    })


@login_required
def fixed_asset_edit(request, pk):
    return crud_edit(request, model=FixedAsset, pk=pk, form_class=FixedAssetForm,
                     template="accounting/assets/fixed_asset/form.html", success_url="accounting:fixed_asset_list")


@login_required
@require_POST
def fixed_asset_delete(request, pk):
    # Lock the row and re-check the guard + delete in one transaction so a concurrent depreciation
    # run can't slip a row in between the check and the delete (code-review #3).
    with transaction.atomic():
        asset = get_object_or_404(FixedAsset.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if asset.accumulated_depreciation or asset.disposals.exists():
            messages.error(request, "Cannot delete an asset that has been depreciated or disposed.")
            return redirect("accounting:fixed_asset_detail", pk=pk)
        write_audit_log(request.user, asset, "delete")
        asset.delete()
    messages.success(request, "Deleted successfully.")
    return redirect("accounting:fixed_asset_list")


@tenant_admin_required
@require_POST
def fixed_asset_depreciate(request, pk):
    asset = get_object_or_404(FixedAsset, pk=pk, tenant=request.tenant)
    if asset.status != "active":
        messages.error(request, "Only an in-service asset can be depreciated.")
        return redirect("accounting:fixed_asset_detail", pk=pk)
    amount = asset.period_depreciation()
    if amount <= ZERO:
        messages.info(request, "This asset is already fully depreciated.")
        return redirect("accounting:fixed_asset_detail", pk=pk)
    expense = asset.expense_account or _first_account(request.tenant, "expense", "6")
    accum = asset.accumulated_account or _first_account(request.tenant, "asset", "1500") \
        or _first_account(request.tenant, "asset")
    if not (expense and accum):
        messages.error(request, "Configure a depreciation expense account and an accumulated-depreciation account first.")
        return redirect("accounting:fixed_asset_detail", pk=pk)
    with transaction.atomic():
        je = _post_journal_entry(
            request.tenant, request.user, f"Depreciation — {asset.number} {asset.name}",
            [(expense, amount, ZERO, None, asset.location), (accum, ZERO, amount, None, asset.location)],
            reference=asset.number)
        asset.accumulated_depreciation = (asset.accumulated_depreciation or ZERO) + amount
        asset.last_depreciation_date = timezone.localdate()
        asset.save(update_fields=["accumulated_depreciation", "last_depreciation_date", "updated_at"])
    write_audit_log(request.user, asset, "update", {"action": "depreciate", "amount": str(amount),
                                                    "journal_entry": je.number if je else None})
    messages.success(request, f"Posted {amount} depreciation for {asset.number}.")
    return redirect("accounting:fixed_asset_detail", pk=pk)
