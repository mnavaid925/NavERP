"""SCM — the vocabularies shared across MORE THAN ONE sub-module.

**Why this file sits at the package ROOT and not inside a sub-module folder.** Every other
``_choices.py`` in this app is documented as *"the vocabularies shared across more than one entity
**in the sub-module**"* (``AssetManagement/_choices.py:1-5``). ``STORAGE_CONDITION_CHOICES`` is not
that: it is read from **three sub-modules at once** — 4.3's :class:`~apps.scm.models.Item`, 4.3's
:class:`~apps.scm.models.Location` and 4.15's :class:`~apps.scm.models.ColdChainMonitor`. Putting it
in ``ColdChainManagement/_choices.py`` would make an OLDER sub-module (4.3, imported first by
``models/__init__.py``) reach into a NEWER sub-module's private module — a dependency edge pointing
backwards, and one that every future reader of ``Items.py`` would have to learn 4.15 to understand.

**It is deliberately NOT merged into ``_base.py``.** ``_base`` is star-imported by every entity
module in the app, so anything added there lands in forty namespaces at once — exactly the shadowing
hazard the 4.14 re-export comment (``models/__init__.py:292-298``) warns about. This module is
imported **by name**, never with ``*``, from the three files that actually read it.

**Pure data — no queries, no model imports, not even ``_base``.** Nothing here can import anything
from ``apps.scm``, so the partially-initialised ``apps.scm.models`` package that sits in
``sys.modules`` while ``Items.py`` is being imported is never asked for a name it has not bound yet.
If this ever does turn circular, the fix is to MOVE the constant, never to duplicate the list.
``__all__`` is explicit so an incidental name (``Decimal``) cannot leak into an importer.
"""
from decimal import Decimal

__all__ = [
    "STORAGE_CONDITION_CHOICES",
    "STORAGE_CONDITION_RANGES",
    "FROZEN_CONDITIONS",
    "COLD_CONDITIONS",
]


#: The temperature class a thing must be kept at. Written on an **item** (what this product needs),
#: on a **location** (what this zone or bin provides) and on a **cold-chain monitor** (what this
#: monitoring point is watching for) — which together turn "cold storage inventory" from a table
#: into a query, with no ``StorageCondition`` master to maintain and reconcile.
#:
#: The bands in the labels are the recognised industry ones and are there so nobody has to look them
#: up before choosing; they are **documentation, not enforcement**. The numbers that actually decide
#: whether something is in range are ``ColdChainMonitor.min_temperature`` / ``max_temperature``,
#: which are explicit per monitor precisely because a validated 2-8 °C fridge and a 2-8 °C reefer on
#: a five-day sea leg are not the same monitoring problem.
#:
#: Drivers: the user-defined temperature zones (chiller / deep freeze / blast / ambient) that
#: Made4net, AEB, Datex and Logimax all ship; SmartSense's walk-in / chiller / display-case classes;
#: ELPRO's product-level assessment.
#:
#: Longest value is ``controlled_rt`` at 12, so all three columns are ``max_length=14``. The extra
#: two characters are deliberate headroom — the 4.10 lesson is that a longer value added later is a
#: column WIDEN on tables that by then have rows in them, not "a one-line choices change".
STORAGE_CONDITION_CHOICES = [
    ("ambient", "Ambient (no temperature control)"),
    ("controlled_rt", "Controlled Room Temperature (15 to 25 °C)"),
    ("cool", "Cool (8 to 15 °C)"),
    ("chilled", "Chilled / Refrigerated (2 to 8 °C)"),
    ("frozen", "Frozen (-25 to -15 °C)"),
    ("deep_frozen", "Deep Frozen (-45 to -25 °C)"),
    ("cryogenic", "Cryogenic (-196 to -150 °C)"),
]

#: Suggested ``(min, max)`` for each class, in °C.
#:
#: **Used for ONE thing only: pre-filling a monitor's explicit limit columns in the create form and
#: in the seeder.** Nothing reads this dict at query time, no report derives a verdict from it, and
#: ``ColdChainMonitor.save()`` never rewrites a limit from it. The columns stay the single source of
#: truth — a model that recomputes its own limits has two writers, and the excursion record
#: snapshots whichever one happened to win.
#:
#: ``ambient`` maps to ``(None, None)``: "no temperature control" has no band to pre-fill, and
#: inventing one would put limits on a monitor whose whole point is that it has none. A caller
#: unpacks the pair and skips a ``None`` side — a one-sided band is legitimate everywhere in 4.15.
STORAGE_CONDITION_RANGES = {
    "ambient": (None, None),
    "controlled_rt": (Decimal("15"), Decimal("25")),
    "cool": (Decimal("8"), Decimal("15")),
    "chilled": (Decimal("2"), Decimal("8")),
    "frozen": (Decimal("-25"), Decimal("-15")),
    "deep_frozen": (Decimal("-45"), Decimal("-25")),
    "cryogenic": (Decimal("-196"), Decimal("-150")),
}

#: The classes for which **mean kinetic temperature honestly answers ``None``**. USP <1079.2> states
#: that MKT does not apply to frozen product or to freeze-thaw cycling: the Arrhenius weighting
#: models a chemical degradation rate that a frozen product simply is not undergoing, and quoting a
#: figure anyway would let a warm spell on a freezer be "offset" by the hours either side of it.
#:
#: Declared here rather than in ``ColdChainManagement/_choices.py`` because it is a property of the
#: shared vocabulary — the same reasoning that keeps the vocabulary itself out of 4.15's folder.
FROZEN_CONDITIONS = frozenset({"frozen", "deep_frozen", "cryogenic"})

#: What "cold storage" means for the Cold Storage Inventory report's item and location filters.
#: ``cool`` and ``controlled_rt`` are deliberately OUT: a controlled-room-temperature store is
#: temperature-*controlled* but it is not cold storage, and folding it in would put every ordinary
#: dry-goods bin on a page whose job is to show the refrigerated ones.
COLD_CONDITIONS = frozenset({"chilled", "frozen", "deep_frozen", "cryogenic"})
