"""Accounting 2.6 Fixed Assets — AssetDisposals views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _first_account, _post_journal_entry
from apps.accounting.models import (
    AssetDisposal,
    ZERO,
)
from apps.accounting.forms import (
    AssetDisposalForm,
)


# --------------------------------------------------------------- Asset disposals
@login_required
def asset_disposal_list(request):
    return crud_list(
        request, AssetDisposal.objects.filter(tenant=request.tenant).select_related("asset"),
        "accounting/assets/asset_disposal/list.html",
        search_fields=["number", "asset__name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": AssetDisposal.STATUS_CHOICES},
    )


@login_required
def asset_disposal_create(request):
    return crud_create(request, form_class=AssetDisposalForm, template="accounting/assets/asset_disposal/form.html",
                       success_url="accounting:asset_disposal_list")


@login_required
def asset_disposal_detail(request, pk):
    obj = get_object_or_404(AssetDisposal.objects.select_related("asset", "journal_entry"),
                            pk=pk, tenant=request.tenant)
    return render(request, "accounting/assets/asset_disposal/detail.html", {
        "obj": obj, "computed_gain_loss": obj.computed_gain_loss() if obj.status == "draft" else obj.gain_loss,
    })


@login_required
def asset_disposal_edit(request, pk):
    disposal = get_object_or_404(AssetDisposal, pk=pk, tenant=request.tenant)
    if disposal.is_locked:
        messages.error(request, "A posted disposal cannot be edited.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    return crud_edit(request, model=AssetDisposal, pk=pk, form_class=AssetDisposalForm,
                     template="accounting/assets/asset_disposal/form.html", success_url="accounting:asset_disposal_list")


@login_required
@require_POST
def asset_disposal_delete(request, pk):
    disposal = get_object_or_404(AssetDisposal, pk=pk, tenant=request.tenant)
    if disposal.is_locked:
        messages.error(request, "A posted disposal cannot be deleted.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    return crud_delete(request, model=AssetDisposal, pk=pk, success_url="accounting:asset_disposal_list")


@tenant_admin_required
@require_POST
def asset_disposal_post(request, pk):
    disposal = get_object_or_404(AssetDisposal.objects.select_related("asset"), pk=pk, tenant=request.tenant)
    if disposal.is_locked:
        messages.error(request, "This disposal is already posted.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    asset = disposal.asset
    cost_acct = asset.asset_account or _first_account(request.tenant, "asset", "1600") \
        or _first_account(request.tenant, "asset")
    accum_acct = asset.accumulated_account or _first_account(request.tenant, "asset", "1690") \
        or _first_account(request.tenant, "asset")
    cash_acct = _first_account(request.tenant, "asset", "1000") or _first_account(request.tenant, "asset")
    gain_acct = _first_account(request.tenant, "income")
    loss_acct = _first_account(request.tenant, "expense")
    if not (cost_acct and cash_acct and gain_acct and loss_acct):
        messages.error(request, "Configure asset, cash, income and expense accounts before disposing.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    gain_loss = disposal.computed_gain_loss()
    legs = [
        (cash_acct, disposal.proceeds or ZERO, ZERO, None, asset.location),
        (accum_acct, asset.accumulated_depreciation or ZERO, ZERO, None, asset.location),
        (cost_acct, ZERO, asset.acquisition_cost or ZERO, None, asset.location),
    ]
    if gain_loss > ZERO:
        legs.append((gain_acct, ZERO, gain_loss, None, asset.location))
    elif gain_loss < ZERO:
        legs.append((loss_acct, -gain_loss, ZERO, None, asset.location))
    with transaction.atomic():
        je = _post_journal_entry(request.tenant, request.user,
                                 f"Disposal of {asset.number} {asset.name}", legs, reference=disposal.number)
        if je is None:
            messages.error(request, "Disposal entry did not balance — nothing was posted.")
            return redirect("accounting:asset_disposal_detail", pk=pk)
        disposal.gain_loss = gain_loss
        disposal.journal_entry = je
        disposal.status = "posted"
        disposal.save(update_fields=["gain_loss", "journal_entry", "status", "updated_at"])
        asset.status = "disposed"
        asset.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, disposal, "update", {"action": "post_disposal",
                                                       "gain_loss": str(gain_loss)})
    messages.success(request, f"Disposal {disposal.number} posted ({'gain' if gain_loss >= 0 else 'loss'} {abs(gain_loss)}).")
    return redirect("accounting:asset_disposal_detail", pk=pk)
