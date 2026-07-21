"""SCM 4.6 Transportation Management System — Carrier views (master + rate cards + scorecard)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant
from apps.scm.forms._common import _carrier_parties
from apps.scm.models import Carrier
from apps.scm.forms import CarrierForm, CarrierRateCardFormSet


@login_required
def carrier_list(request):
    qs = Carrier.objects.filter(tenant=request.tenant).select_related("party")
    return crud_list(
        request, qs, "scm/transportation/carrier/list.html",
        search_fields=["number", "party__name", "scac_code", "mc_number"],
        filters=[("status", "status", False), ("primary_mode", "primary_mode", False),
                 ("carrier_type", "carrier_type", False)],
        extra_context={
            "status_choices": Carrier.STATUS_CHOICES,
            "mode_choices": Carrier._meta.get_field("primary_mode").choices,
            "carrier_type_choices": Carrier.CARRIER_TYPE_CHOICES,
        },
    )


@login_required
def carrier_create(request):
    return _carrier_form(request, instance=None)


@login_required
def carrier_edit(request, pk):
    obj = get_object_or_404(Carrier, pk=pk, tenant=request.tenant)
    return _carrier_form(request, instance=obj)


def _carrier_form(request, instance):
    """Header + rate-card formset saved in ONE transaction (mirrors _salesorder_form)."""
    if instance is None and _need_tenant(request):
        return redirect("scm:carrier_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = CarrierForm(request.POST, instance=instance, tenant=request.tenant)
        formset = CarrierRateCardFormSet(request.POST, instance=instance,
                                         form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                carrier = form.save(commit=False)
                carrier.tenant = request.tenant
                carrier.save()
                formset.instance = carrier
                formset.save()
            write_audit_log(request.user, carrier, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Carrier {carrier.name} saved.")
            return redirect("scm:carrier_detail", pk=carrier.pk)
    else:
        form = CarrierForm(instance=instance, tenant=request.tenant)
        formset = CarrierRateCardFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/transportation/carrier/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def carrier_detail(request, pk):
    obj = get_object_or_404(Carrier.objects.select_related("party"), pk=pk, tenant=request.tenant)
    rate_cards = list(obj.rate_cards.select_related("currency"))
    # Recent shipments this carrier executed — one bounded query, newest first.
    recent_shipments = list(obj.shipments.order_by("-id")[:10])
    return render(request, "scm/transportation/carrier/detail.html", {
        "obj": obj,
        "rate_cards": rate_cards,
        "recent_shipments": recent_shipments,
    })


@login_required
@require_POST
def carrier_delete(request, pk):
    obj = get_object_or_404(Carrier, pk=pk, tenant=request.tenant)
    # FreightInvoice.carrier is PROTECT — a carrier with audited freight can't be deleted, so guard
    # here with a friendly message instead of letting crud_delete raise ProtectedError (a 500).
    if obj.freight_invoices.exists():
        messages.error(request, "This carrier has freight invoices and can't be deleted — set it inactive instead.")
        return redirect("scm:carrier_detail", pk=pk)
    return crud_delete(request, model=Carrier, pk=pk, success_url="scm:carrier_list")


@login_required
@require_POST
def carrier_recompute_scorecard(request, pk):
    """Re-derive the on-time-delivery score from this carrier's delivered-shipment history."""
    # select_related so write_audit_log -> str(obj) -> Carrier.name -> party.name doesn't chain-fetch.
    obj = get_object_or_404(Carrier.objects.select_related("party"), pk=pk, tenant=request.tenant)
    obj.recompute_scorecard()
    write_audit_log(request.user, obj, "update",
                    {"action": "recompute_scorecard", "on_time_delivery_pct": str(obj.on_time_delivery_pct)})
    messages.success(request, f"Scorecard recomputed for {obj.name}.")
    return redirect("scm:carrier_detail", pk=pk)
