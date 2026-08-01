"""SCM 4.12 Contract & Compliance — the computed freight-emissions report (NO new table).

WHAT THIS IS. A GLEC Framework v3.2 / ISO 14083 shaped tonne-km estimate over the 4.6 rows that
already exist: ``tonne_km = (Shipment.weight_kg / 1000) * Load.distance_km``, priced with a small
closed table of well-to-wheel gCO2e-per-tonne-km factors keyed on the shipment's mode (falling back
to its load's mode). 4.6 stored ``Load.distance_km`` and ``Shipment.weight_kg`` expressly so this
could be computed rather than typed.

WHAT THIS IS NOT. It is an OPERATIONAL ESTIMATE and the page says so on screen. It is not a
statutory disclosure: CSRD/GHG-Protocol reporting is an accounting concern (L29), not SCM's. It is
not audited, it applies no allocation for empty running or backhaul, and its factors are defaults
rather than carrier-specific measured intensities. It never says "AI" — there is no model here, only
arithmetic the page shows its own working for (the 4.11 precedent).

COVERAGE, NOT A CONFIDENT ZERO. A shipment with no load, a load with no ``distance_km``, or a
shipment with no ``weight_kg`` CANNOT be measured. Those rows are counted and reported as excluded
rather than being folded in as zero — a green zero that actually means "we had no data" is the
failure mode 4.11 fixed in ``projected_stockout_count``, and it is worse here because the number
looks like an environmental result. An empty tenant renders the same shape with a zero coverage line
and ``None`` totals; it must not 500 (the 4.11 ``supplier_disruption_score`` first-run defect).

CONTEXT-VARIABLE CONTRACT (templates/scm/compliance/carbon_footprint.html reads exactly these):
    date_from, date_to          -- date | None, the resolved window (defaults to the last 12 months)
    date_from_raw, date_to_raw  -- str, echoed back into the filter inputs verbatim
    window_invalid              -- bool, True when a typed date was junk and the default was used
    mode, mode_choices          -- str, list[(value, label)] for the mode dropdown
    carrier_id, carriers        -- str, queryset for the carrier dropdown
    total_tco2e                 -- Decimal | None (None = nothing measurable, NOT zero)
    total_tonne_km              -- Decimal | None
    measured_count              -- int, shipments that could be computed
    excluded_count              -- int, shipments in the window that could not
    considered_count            -- int, measured + excluded
    coverage_pct                -- Decimal | None (None when considered_count == 0)
    intensity_g_per_tonne_km    -- Decimal | None, the blended realised intensity
    by_month, by_mode, by_carrier -- list[dict], each with the keys named in the loops below
    declared                    -- dict of supplier-DECLARED scope 1/2/3 totals (clearly not ours)
    declared_count              -- int, assessments behind `declared`
    factors                     -- list[(mode_label, factor)] rendered as the method table
    factor_source               -- str, the factor table's provenance line
    method_note                 -- str, the limitations paragraph
    export_qs                   -- str, the current filter re-encoded for the CSV link
"""
import csv
import datetime
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.utils.http import urlencode

from apps.scm.views._common import *  # noqa: F401,F403
# q2 lives in the MODELS toolkit, not the views one — views/_common.py deliberately does not
# re-export it. Same import the 4.11 alert views use (SupplyChainAlerts.py:52).
from apps.scm.models._base import q2
from apps.scm.models import Carrier, Shipment, SustainabilityAssessment
from apps.scm.models.TransportationManagement.Carriers import MODE_CHOICES

# The factor table, its provenance string and the limitations paragraph all live in
# models/ContractCompliance/_choices.py — ONE table with two readers (this report and the page's
# method section), which is exactly what that module exists for. A second copy here drifted from it
# within one build: four of seven values already disagreed.
from apps.scm.models.ContractCompliance._choices import (  # noqa: E402
    CARBON_METHOD_NOTE, EMISSION_FACTORS, EMISSION_FACTOR_SOURCE,
)

_GRAMS_PER_TONNE = Decimal("1000000")  # gCO2e -> tCO2e
_KG_PER_TONNE = Decimal("1000")


def _parse_date(raw):
    """A ``YYYY-MM-DD`` GET value as a date, or ``None`` if it is anything else.

    Returns None rather than raising: the window comes out of the query string, so a hand-typed or
    truncated value must drop the filter, never 500 (L11's rule applied to a date instead of an int).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _window(request):
    """Resolve the reporting window, defaulting to the last 12 months.

    Also reports whether a value was typed and rejected, so the page can say "showing the default
    window" instead of silently ignoring what somebody asked for.
    """
    raw_from = (request.GET.get("date_from") or "").strip()
    raw_to = (request.GET.get("date_to") or "").strip()
    date_from, date_to = _parse_date(raw_from), _parse_date(raw_to)
    invalid = bool(raw_from and date_from is None) or bool(raw_to and date_to is None)
    today = timezone.localdate()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date_to - datetime.timedelta(days=365)
    if date_from > date_to:
        # A reversed window is a typo, not an empty result — swap rather than render nothing.
        date_from, date_to = date_to, date_from
        invalid = True
    return date_from, date_to, raw_from, raw_to, invalid


def _shipment_date(shipment):
    """The date a shipment is attributed to: actual delivery if known, else planned pickup.

    Emissions belong to when the freight actually moved. ``actual_delivery_at`` is a datetime and
    ``planned_pickup_date`` a date, so this normalises to a date either way.
    """
    if shipment.actual_delivery_at:
        return timezone.localtime(shipment.actual_delivery_at).date()
    return shipment.planned_pickup_date


def _measure(shipment):
    """``(tonne_km, factor, grams)`` for one shipment, or ``None`` when it cannot be measured.

    Returning None — rather than a zero triple — is the whole contract of this function: the caller
    counts these as EXCLUDED and reports the coverage, instead of averaging a fabricated zero into
    everybody else's intensity.
    """
    load = shipment.load
    distance = load.distance_km if load is not None else None
    weight = shipment.weight_kg
    if distance is None or weight is None:
        return None
    if distance <= 0 or weight <= 0:
        # A zero-distance or zero-weight row is a data-entry stub, not a carbon-free movement.
        return None
    mode = shipment.mode or (load.mode if load is not None else "")
    factor = EMISSION_FACTORS.get(mode)
    if factor is None:
        # The factor table is a CLOSED set. A mode added to 4.6 without a factor here is a coverage
        # gap the page must REPORT, not a movement to score with a substituted default — the same
        # rule that excludes a shipment with no weight rather than calling it zero.
        return None
    tonne_km = (Decimal(weight) / _KG_PER_TONNE) * Decimal(distance)
    return tonne_km, factor, tonne_km * factor


def _collect(request):
    """Everything both the page and the CSV need, computed once from one queryset.

    Deliberately a single ``select_related`` pass in Python rather than three aggregate queries: the
    per-row factor lookup depends on a fallback between two columns, which is not expressible as a
    plain ``Sum`` without a ``Case``/``When`` ladder that would have to be kept in step with
    ``EMISSION_FACTORS`` by hand. One query, one loop, and the factor table stays the only place a
    factor is written down.
    """
    date_from, date_to, raw_from, raw_to, invalid = _window(request)
    mode = (request.GET.get("mode") or "").strip()
    carrier_raw = (request.GET.get("carrier") or "").strip()

    qs = (Shipment.objects.filter(tenant=request.tenant)
          .select_related("load", "carrier")
          .exclude(status="cancelled"))
    if mode in EMISSION_FACTORS:
        qs = qs.filter(mode=mode)
    if carrier_raw.isdecimal():
        qs = qs.filter(carrier_id=int(carrier_raw))

    months, modes, carriers_agg = {}, {}, {}
    total_grams = Decimal("0")
    total_tonne_km = Decimal("0")
    measured = excluded = 0

    for shipment in qs:
        moved_on = _shipment_date(shipment)
        if moved_on is None or moved_on < date_from or moved_on > date_to:
            continue
        result = _measure(shipment)
        if result is None:
            excluded += 1
            continue
        tonne_km, _factor, grams = result
        measured += 1
        total_grams += grams
        total_tonne_km += tonne_km

        key = moved_on.strftime("%Y-%m")
        bucket = months.setdefault(key, {"label": moved_on.strftime("%b %Y"), "grams": Decimal("0"),
                                         "tonne_km": Decimal("0"), "count": 0})
        bucket["grams"] += grams
        bucket["tonne_km"] += tonne_km
        bucket["count"] += 1

        mode_key = shipment.mode or (shipment.load.mode if shipment.load_id else "") or "unknown"
        mrow = modes.setdefault(mode_key, {"label": dict(MODE_CHOICES).get(mode_key, "Unknown"),
                                           "grams": Decimal("0"), "tonne_km": Decimal("0"),
                                           "count": 0})
        mrow["grams"] += grams
        mrow["tonne_km"] += tonne_km
        mrow["count"] += 1

        cname = shipment.carrier.name if shipment.carrier_id else "— unassigned —"
        crow = carriers_agg.setdefault(cname, {"label": cname, "grams": Decimal("0"),
                                               "tonne_km": Decimal("0"), "count": 0})
        crow["grams"] += grams
        crow["tonne_km"] += tonne_km
        crow["count"] += 1

    considered = measured + excluded

    def _row(row):
        """Convert one accumulator into its rendered shape (grams -> tCO2e, quantized)."""
        return {**row, "tco2e": q2(row["grams"] / _GRAMS_PER_TONNE),
                "tonne_km": q2(row["tonne_km"])}

    # Months sort on the "YYYY-MM" DICT KEY, never on the label: "Apr 2026" sorts above "Jan 2026"
    # alphabetically, which would silently scramble the trend line.
    by_month = [_row(months[key]) for key in sorted(months)]
    # Mode and carrier sort by contribution — biggest emitter first is what the page is read for.
    by_mode = sorted((_row(r) for r in modes.values()), key=lambda r: r["tco2e"], reverse=True)
    by_carrier = sorted((_row(r) for r in carriers_agg.values()),
                        key=lambda r: r["tco2e"], reverse=True)

    # Supplier-DECLARED scope totals for the same window. Shown beside our estimate and labelled as
    # theirs: it is a different number measured by somebody else, and merging the two would invent a
    # total nobody computed.
    declared_qs = SustainabilityAssessment.objects.filter(
        tenant=request.tenant, assessment_date__gte=date_from, assessment_date__lte=date_to)
    declared = declared_qs.aggregate(
        scope1=Sum("scope1_tco2e"), scope2=Sum("scope2_tco2e"), scope3=Sum("scope3_tco2e"))

    return {
        "date_from": date_from, "date_to": date_to,
        "date_from_raw": raw_from, "date_to_raw": raw_to, "window_invalid": invalid,
        "mode": mode, "mode_choices": MODE_CHOICES,
        "carrier_id": carrier_raw, "carriers": Carrier.objects.filter(tenant=request.tenant),
        # None, never 0, when nothing could be measured — see the module docstring.
        "total_tco2e": q2(total_grams / _GRAMS_PER_TONNE) if measured else None,
        "total_tonne_km": q2(total_tonne_km) if measured else None,
        "measured_count": measured, "excluded_count": excluded, "considered_count": considered,
        "coverage_pct": (q2(Decimal(measured) * 100 / Decimal(considered))
                         if considered else None),
        "intensity_g_per_tonne_km": (q2(total_grams / total_tonne_km)
                                     if total_tonne_km > 0 else None),
        "by_month": by_month, "by_mode": by_mode, "by_carrier": by_carrier,
        "declared": declared, "declared_count": declared_qs.count(),
        "factors": [(dict(MODE_CHOICES).get(k, k), v) for k, v in EMISSION_FACTORS.items()],
        "factor_source": EMISSION_FACTOR_SOURCE,
        "method_note": CARBON_METHOD_NOTE,
        "export_qs": urlencode({k: v for k, v in (
            ("date_from", raw_from), ("date_to", raw_to), ("mode", mode),
            ("carrier", carrier_raw)) if v}),
    }


@login_required
def carbon_footprint_report(request):
    return render(request, "scm/compliance/carbon_footprint.html", _collect(request))


@login_required
def carbon_footprint_report_export(request):
    """The same figures as CSV — same querysets, same window params (the 4.11 export precedent)."""
    data = _collect(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="carbon-footprint.csv"'
    writer = csv.writer(response)
    writer.writerow(["NavERP — freight emissions estimate (GLEC v3.2 / ISO 14083 shaped)"])
    writer.writerow(["Operational estimate from default factors — NOT an audited or statutory figure"])
    writer.writerow(["Window", data["date_from"], data["date_to"]])
    writer.writerow(["Shipments measured", data["measured_count"]])
    writer.writerow(["Shipments excluded (no distance and/or no weight)", data["excluded_count"]])
    writer.writerow(["Coverage %", data["coverage_pct"] if data["coverage_pct"] is not None else "n/a"])
    writer.writerow(["Total tCO2e", data["total_tco2e"] if data["total_tco2e"] is not None else "n/a"])
    writer.writerow(["Total tonne-km", data["total_tonne_km"] if data["total_tonne_km"] is not None else "n/a"])
    writer.writerow([])
    for title, rows in (("By month", data["by_month"]), ("By mode", data["by_mode"]),
                        ("By carrier", data["by_carrier"])):
        writer.writerow([title])
        writer.writerow(["Bucket", "Shipments", "Tonne-km", "tCO2e"])
        for row in rows:
            writer.writerow([row["label"], row["count"], row["tonne_km"], row["tco2e"]])
        writer.writerow([])
    writer.writerow(["Supplier-declared (their figures, not ours)"])
    writer.writerow(["Assessments", data["declared_count"]])
    for scope in ("scope1", "scope2", "scope3"):
        value = data["declared"].get(scope)
        writer.writerow([scope, value if value is not None else "n/a"])
    return response
