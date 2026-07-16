"""HRM 3.16 Tax & Investment — Taxregimeconfig views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TaxRegimeConfig,
    TaxSlabBand,
)
from apps.hrm.forms import (
    TaxRegimeConfigForm,
    TaxSlabBandForm,
)


# --------------------------------------------------- TaxRegimeConfig (+ inline slab bands)
@login_required
def taxregimeconfig_list(request):
    return crud_list(
        request, TaxRegimeConfig.objects.filter(tenant=request.tenant),
        "hrm/tax/taxregimeconfig/list.html",
        search_fields=["financial_year", "tax_law_reference"],
        filters=[("financial_year", "financial_year", False), ("regime", "regime", False)],
        extra_context={"regime_choices": TaxRegimeConfig.REGIME_CHOICES},
    )


@login_required
def taxregimeconfig_create(request):
    return crud_create(request, form_class=TaxRegimeConfigForm,
                       template="hrm/tax/taxregimeconfig/form.html", success_url="hrm:taxregimeconfig_list")


@login_required
def taxregimeconfig_detail(request, pk):
    obj = get_object_or_404(TaxRegimeConfig, pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/taxregimeconfig/detail.html", {
        "obj": obj,
        "slab_bands": obj.slab_bands.order_by("sequence", "income_from"),
        "band_form": TaxSlabBandForm(tenant=request.tenant),
    })


@login_required
def taxregimeconfig_edit(request, pk):
    return crud_edit(request, model=TaxRegimeConfig, pk=pk, form_class=TaxRegimeConfigForm,
                     template="hrm/tax/taxregimeconfig/form.html", success_url="hrm:taxregimeconfig_list")


@login_required
@require_POST
def taxregimeconfig_delete(request, pk):
    return crud_delete(request, model=TaxRegimeConfig, pk=pk, success_url="hrm:taxregimeconfig_list")


@login_required
@require_POST
def taxslabband_create(request, config_pk):
    config = get_object_or_404(TaxRegimeConfig, pk=config_pk, tenant=request.tenant)
    form = TaxSlabBandForm(request.POST,
                           instance=TaxSlabBand(tenant=request.tenant, config=config),
                           tenant=request.tenant)
    if form.is_valid():
        form.save()
        write_audit_log(request.user, config, "update", {"action": "slab_add"})
        messages.success(request, "Slab band added.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("hrm:taxregimeconfig_detail", pk=config.pk)


@login_required
def taxslabband_edit(request, config_pk, pk):
    config = get_object_or_404(TaxRegimeConfig, pk=config_pk, tenant=request.tenant)
    band = get_object_or_404(TaxSlabBand, pk=pk, tenant=request.tenant, config=config)
    if request.method == "POST":
        form = TaxSlabBandForm(request.POST, instance=band, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, config, "update", {"action": "slab_edit"})
            messages.success(request, "Slab band updated.")
            return redirect("hrm:taxregimeconfig_detail", pk=config.pk)
    else:
        form = TaxSlabBandForm(instance=band, tenant=request.tenant)
    return render(request, "hrm/tax/taxregimeconfig/band_form.html",
                  {"form": form, "obj": band, "config": config, "is_edit": True})


@login_required
@require_POST
def taxslabband_delete(request, config_pk, pk):
    config = get_object_or_404(TaxRegimeConfig, pk=config_pk, tenant=request.tenant)
    band = get_object_or_404(TaxSlabBand, pk=pk, tenant=request.tenant, config=config)
    band.delete()
    write_audit_log(request.user, config, "update", {"action": "slab_delete"})
    messages.success(request, "Slab band removed.")
    return redirect("hrm:taxregimeconfig_detail", pk=config.pk)
