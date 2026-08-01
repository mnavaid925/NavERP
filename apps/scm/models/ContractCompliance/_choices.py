"""SCM 4.12 Contract & Compliance — the one shared, model-free table in the sub-module.

**Why this file exists at all.** Every 4.12 *vocabulary* (licence types, document types, compliance
frameworks, EcoVadis medals) lives on the model that owns it, because exactly one model reads each
one. This module holds the single piece of 4.12 data that is read from **two directions at once**:
the modal carbon factors. The sustainability report view multiplies them out to draw the page, and
the test suite multiplies them out to assert the page is right. If each held its own copy, the test
would be asserting against itself and a wrong factor would ship green. One table, two readers.

**Pure data — no queries, no model imports, not even ``_base``.** This module is imported by
``apps/scm/models/__init__.py`` *before* the entity modules and by a report view that also imports
models; keeping it dependency-free means the edge can only ever run one way and no import cycle is
possible. ``__all__`` is explicit because ``__init__`` star-imports this module: without it, every
incidental name here would leak into ``apps.scm.models``.

**What the factors are, and what they are NOT.** These are *default* modal intensities in
gCO2e per tonne-kilometre — the order of magnitude the GLEC Framework v3.2 / ISO 14083 default
tables put each mode at, used for a screening estimate when nothing better is available. They are
not carrier-measured emissions, not fuel-based primary data, and not a reporting-grade Scope 3
figure. The gap between modes (ocean ~8, air ~500) is the decision-grade signal here; the second
digit of any single factor is not. ``CARBON_METHOD_NOTE`` says exactly this **on the page**, because
an unlabelled tonne of CO2e on a dashboard gets quoted in a sustainability report, and a screening
estimate quoted as a measurement is the failure mode this constant exists to prevent.

The keys mirror 4.6's ``MODE_CHOICES`` (``apps/scm/models/TransportationManagement/Carriers.py:23``)
value-for-value. They are re-typed rather than imported so this module stays model-free; a mode
added to 4.6 without a factor here reads as "no factor for this mode" (the report must report that
coverage gap, never silently score the shipment as zero-carbon).
"""
from decimal import Decimal

__all__ = ["EMISSION_FACTORS", "EMISSION_FACTOR_SOURCE", "CARBON_METHOD_NOTE"]


#: gCO2e per tonne-kilometre, well-to-wheel, by 4.6 transport mode. CLOSED set: a shipment whose
#: mode is absent here has no factor, and the report says so rather than substituting a zero.
EMISSION_FACTORS = {
    "truckload": Decimal("62"),     # full truckload, high load factor
    "ltl": Decimal("102"),          # less-than-truckload — the same truck, worse utilisation
    "parcel": Decimal("800"),       # courier van + last mile, the most intense mode per tonne-km
    "ocean": Decimal("8"),          # container vessel — two orders of magnitude below air
    "air": Decimal("500"),          # freighter/belly-hold long haul
    "rail": Decimal("22"),
    "intermodal": Decimal("35"),    # rail line-haul blended with road drayage at both ends
}

#: Printed next to every figure the factors produce, so the number on screen carries its provenance.
EMISSION_FACTOR_SOURCE = (
    "Default modal emission factors, GLEC Framework v3.2 / ISO 14083 (gCO2e per tonne-km)"
)

#: The limitations paragraph the carbon page renders above the table. Deliberately long and
#: deliberately unavoidable — see this module's docstring.
CARBON_METHOD_NOTE = (
    "Screening estimate only. Each shipment is scored as chargeable weight x distance x the default "
    "factor for its transport mode, so it reflects the mode and the lane, not the carrier, the "
    "vehicle, the fuel or the actual load factor. Shipments missing a weight, a distance or a mode "
    "are excluded and reported as a coverage gap rather than counted as zero. These figures are not "
    "carrier-reported data and are not a reporting-grade Scope 3 inventory: use them to compare "
    "lanes and modes, not to publish a footprint."
)
