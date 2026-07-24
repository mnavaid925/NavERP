"""SCM 4.7 Demand Planning — SeasonalityProfile views (seasonality analysis + promotional events)."""
from datetime import timedelta

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _item_qs, _location_qs, _need_tenant
from apps.scm.models import ItemCategory, SeasonalityIndex, SeasonalityProfile
from apps.scm.models.DemandPlanning._history import demand_series_map
from apps.scm.forms import SeasonalityIndexFormSet, SeasonalityProfileForm

ZERO = Decimal("0")


@login_required
def seasonalityprofile_list(request):
    qs = (SeasonalityProfile.objects.filter(tenant=request.tenant)
          .select_related("item", "category", "location"))
    return crud_list(
        request, qs, "scm/demandplanning/seasonalityprofile/list.html",
        search_fields=["number", "name", "notes", "item__sku", "item__name"],
        filters=[("profile_type", "profile_type", False), ("scope", "scope", False),
                 ("bucket", "bucket", False), ("is_active", "is_active", False),
                 ("item", "item_id", True), ("category", "category_id", True),
                 ("location", "location_id", True)],
        extra_context={
            "type_choices": SeasonalityProfile.PROFILE_TYPE_CHOICES,
            "scope_choices": SeasonalityProfile.SCOPE_CHOICES,
            "bucket_choices": SeasonalityProfile.BUCKET_CHOICES,
            "items": _item_qs(request.tenant),
            "categories": ItemCategory.objects.filter(tenant=request.tenant),
            "locations": _location_qs(request.tenant),
        },
    )


@login_required
def seasonalityprofile_create(request):
    return _seasonalityprofile_form(request, instance=None)


@login_required
def seasonalityprofile_edit(request, pk):
    obj = get_object_or_404(SeasonalityProfile, pk=pk, tenant=request.tenant)
    return _seasonalityprofile_form(request, instance=obj)


def _seasonalityprofile_form(request, instance):
    """Header + index formset saved in ONE transaction (the _load_form pattern)."""
    if instance is None and _need_tenant(request):
        return redirect("scm:seasonalityprofile_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = SeasonalityProfileForm(request.POST, instance=instance, tenant=request.tenant)
        formset = SeasonalityIndexFormSet(request.POST, instance=instance,
                                          form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                profile = form.save(commit=False)
                profile.tenant = request.tenant
                profile.save()
                formset.instance = profile
                formset.save()
            write_audit_log(request.user, profile, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Seasonality profile {profile.number} saved.")
            return redirect("scm:seasonalityprofile_detail", pk=profile.pk)
    else:
        form = SeasonalityProfileForm(instance=instance, tenant=request.tenant)
        formset = SeasonalityIndexFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/demandplanning/seasonalityprofile/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def seasonalityprofile_detail(request, pk):
    obj = get_object_or_404(
        SeasonalityProfile.objects.select_related("item", "category", "location",
                                                  "cannibalized_category"),
        pk=pk, tenant=request.tenant)
    indices = list(obj.indices.all())
    peak = max((row.index_factor for row in indices), default=Decimal("1"))
    return render(request, "scm/demandplanning/seasonalityprofile/detail.html", {
        "obj": obj,
        "indices": indices,
        # Bar widths are relative to the tallest period, so a flat curve doesn't render as a
        # full-width block and a 3x peak doesn't overflow the card.
        "peak_factor": peak if peak > ZERO else Decimal("1"),
        "forecasts": obj.forecasts.select_related("item")[:10],
    })


@login_required
@require_POST
def seasonalityprofile_delete(request, pk):
    return crud_delete(request, model=SeasonalityProfile, pk=pk,
                       success_url="scm:seasonalityprofile_list")


def _derive_source_series(profile, years):
    """The history this profile's indices are averaged from — derived, never a stored table.

    An item-scoped profile reads its item; a category-scoped one sums its category's items through
    the BATCHED ``demand_series_map`` — one grouped query for the whole category rather than one
    aggregate per SKU, which a 300-item category would otherwise turn into 300 round trips inside a
    single synchronous POST. Nothing is lost by going item-level here: the source is
    ``sales_orders``, for which ``demand_series`` ignores ``location`` anyway.

    A location- or global-scoped profile has no single demand stream to fit, so it returns nothing
    and the caller says so rather than inventing a curve.
    """
    from apps.scm.models import Item as ItemModel
    end = timezone.localdate()
    start = end - timedelta(days=365 * max(int(years or 2), 1))
    # period_from_launch is a lifecycle grain, not a calendar one — derive it monthly.
    bucket = profile.bucket if profile.bucket in ("week", "month", "quarter") else "month"
    if profile.item_id:
        item_ids = [profile.item_id]
    elif profile.category_id:
        item_ids = list(ItemModel.objects.filter(tenant_id=profile.tenant_id,
                                                 category_id=profile.category_id)
                        .values_list("pk", flat=True))
    else:
        return [], bucket
    series_map = demand_series_map(profile.tenant_id, item_ids, start=start, end=end, bucket=bucket)
    combined = {}
    for series in series_map.values():
        for period_start, qty in series:
            combined[period_start] = combined.get(period_start, ZERO) + qty
    return sorted(combined.items()), bucket


@login_required
@require_POST
def seasonalityprofile_derive(request, pk):
    """Fill the index rows from the derived demand history.

    Each period's factor is its mean demand ÷ the overall mean — a de-seasonalising ratio, which is
    why a flat history correctly produces 1.0000 everywhere rather than noise. ``sample_size`` records
    how many observations went into each factor, so a one-year "curve" is visibly a guess.
    """
    profile = get_object_or_404(SeasonalityProfile, pk=pk, tenant=request.tenant)
    series, _bucket = _derive_source_series(profile, profile.derived_from_years)
    if not series:
        messages.error(request, "No demand history to derive from — this profile needs an item or a "
                                "category with sales history.")
        return redirect("scm:seasonalityprofile_detail", pk=pk)
    grouped = {}
    for period_start, qty in series:
        grouped.setdefault(profile.period_number_for(period_start), []).append(qty)
    overall = sum((qty for _, qty in series), ZERO) / Decimal(len(series))
    if overall <= ZERO:
        messages.error(request, "Demand history exists but totals zero — nothing to index.")
        return redirect("scm:seasonalityprofile_detail", pk=pk)

    from apps.scm.models.DemandPlanning._history import period_label as label_for
    labels = {}
    for period_start, _qty in series:
        labels.setdefault(profile.period_number_for(period_start), label_for(period_start, _bucket))
    with transaction.atomic():
        existing = {row.period_number: row for row in profile.indices.all()}
        created, updated = [], []
        for number, values in grouped.items():
            factor = (sum(values, ZERO) / Decimal(len(values)) / overall).quantize(Decimal("0.0001"))
            row = existing.get(number) or SeasonalityIndex(profile=profile, period_number=number)
            row.index_factor = factor
            row.sample_size = len(values)
            row.period_label = row.period_label or labels.get(number, "")
            (updated if row.pk else created).append(row)
        SeasonalityIndex.objects.bulk_create(created)
        if updated:
            SeasonalityIndex.objects.bulk_update(
                updated, ["index_factor", "sample_size", "period_label"])
        profile.last_derived_at = timezone.now()
        profile.save(update_fields=["last_derived_at", "updated_at"])
    write_audit_log(request.user, profile, "update",
                    {"action": "derive_indices", "periods": len(grouped)})
    messages.success(request, f"Derived {len(grouped)} index periods from "
                              f"{len(series)} periods of demand history.")
    return redirect("scm:seasonalityprofile_detail", pk=pk)
