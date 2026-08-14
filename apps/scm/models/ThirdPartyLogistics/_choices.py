"""SCM 4.17 Third-Party Logistics (3PL) — the vocabularies and bounds shared across the sub-module.

**Ownership.** This file is written by the ``LogisticsClients`` (entity 1) backend agent and by nobody
else. ``ClientRateCards``, ``ClientBillingRuns`` and ``ClientSlas`` import from it **by name**
(``from apps.scm.models.ThirdPartyLogistics._choices import ...``) and must never create or edit it.
One writer, three readers — which is the whole reason a shared vocabulary is a file rather than four
copies of a list.

**Why this file exists.** Same rule as ``AssetManagement/_choices.py``, ``LaborManagement/_choices.py``
and ``CustomerPortal/_choices.py``: a vocabulary read by exactly one model stays on that model.
Everything below is read from **two or more directions at once** —

* ``CLIENT_STATUS_CHOICES`` / ``BILLING_CYCLE_CHOICES`` / ``SPACE_MODEL_CHOICES`` /
  ``INTEGRATION_MODE_CHOICES`` — declared on ``LogisticsClient``, filtered on its list page, and read
  again by the two computed report pages (a report whose dropdown offered a different set from the
  column would filter to nothing and look empty rather than wrong).
* ``STORAGE_BILLING_METHOD_CHOICES`` — declared on ``LogisticsClient`` and **branched on by
  ``ClientBillingRun.calculate()``**, which walks the ``StockMove`` ledger five different ways
  depending on it. Two copies of that list would be two chances for a method to exist on the form and
  fall off the end of the ``if`` chain, silently billing zero storage.
* ``CHARGE_CATEGORY_CHOICES`` / ``CHARGE_BASIS_CHOICES`` / ``RATE_PERIOD_CHOICES`` — declared on
  ``ClientRateCardLine``, SNAPSHOTTED onto ``ClientBillingRunLine`` (so a rate card edited next
  quarter cannot rewrite last quarter's invoice), grouped by on the run detail page and read by
  ``calculate()``'s quantity resolvers.
* ``PERIODIC_BASES`` / ``MANUAL_ONLY_BASES`` — the two facts about a charge basis that decide
  behaviour rather than presentation: whether a ``period`` is required, and whether this build can
  MEASURE the quantity at all.
* ``SLA_METRIC_CHOICES`` + ``SLA_METRIC_META`` — declared on ``ClientSLA``, validated against by its
  ``clean()``, dispatched on by ``recompute()`` and rendered as help text on its form.
* The bounds — enforced in ``clean()`` and in the calculators, so the forms, the seeder and every
  future verb inherit them, and quoted back in the messages the views and templates print.

**Pure data — the only import is ``Decimal``.** No model imports, no queries, not even ``_base``
(the ``AssetManagement`` / ``LaborManagement`` precedent, both of which import ``Decimal`` and
nothing else). The dependency edge inside 4.17 therefore only ever runs one way
(``LogisticsClients`` / ``ClientRateCards`` / ``ClientBillingRuns`` / ``ClientSlas`` -> ``_choices``)
and no import cycle is possible.

**``__all__`` is explicit, and ``apps/scm/models/__init__.py`` must re-export these BY NAME rather
than with ``import *``.** Three ``_choices`` modules are already star-imported at the models package
root; a fourth re-declaring a shared token would **silently shadow** one of them, with the winner
decided by import order. Spelling every name out makes such a collision a visible edit instead of a
runtime coin-flip. (Checked at write time: none of the names below is declared anywhere else in
``apps/scm/models``.)

**The CSS dicts.** Colour is decided in exactly one place per vocabulary (the ``KpiSnapshot.BAND_CSS``
precedent) so a badge cannot be styled one way on a list page and another on a detail page. Only the
six classes that actually exist in ``static/css/theme.css`` may appear — ``badge-green`` /
``badge-red`` / ``badge-amber`` / ``badge-info`` / ``badge-muted`` / ``badge-slate``. There is no
``badge-success`` / ``badge-warning`` / ``badge-danger``; those render completely unstyled (L33,
already shipped four times).
"""
from decimal import Decimal

__all__ = [
    # LogisticsClient
    "CLIENT_STATUS_CHOICES", "CLIENT_STATUS_CSS",
    "BILLING_CYCLE_CHOICES",
    "STORAGE_BILLING_METHOD_CHOICES",
    "SPACE_MODEL_CHOICES", "COMMITTED_SPACE_MODELS",
    "INTEGRATION_MODE_CHOICES",
    # ClientRateCard / ClientRateCardLine
    "RATE_CARD_STATUS_CHOICES", "RATE_CARD_STATUS_CSS", "EDITABLE_RATE_CARD_STATUSES",
    "CHARGE_CATEGORY_CHOICES", "CHARGE_CATEGORY_CSS",
    "CHARGE_BASIS_CHOICES", "RATE_PERIOD_CHOICES",
    "PERIODIC_BASES", "MANUAL_ONLY_BASES",
    # ClientBillingRun
    "RUN_STATUS_CHOICES", "RUN_STATUS_CSS", "EDITABLE_RUN_STATUSES",
    # ClientSLA
    "SLA_METRIC_CHOICES", "SLA_UNIT_CHOICES", "SLA_DIRECTION_CHOICES", "SLA_WINDOW_CHOICES",
    "SLA_STATUS_CHOICES", "SLA_STATUS_CSS", "SLA_METRIC_META",
    # bounds
    "MAX_RUN_LINES", "MAX_RATE_CARD_LINES", "MAX_RUN_PERIOD_DAYS", "MAX_MEASUREMENT_ROWS",
    "MAX_COMMITTED_SQFT", "MAX_COMMITTED_PALLETS", "MAX_CLIENT_DEPTH",
]


# =================================================================================================
# LogisticsClient — who the depositor is and how we agreed to bill them
# =================================================================================================

#: The commercial lifecycle of a 3PL client, and it is deliberately a STATUS rather than a verb
#: ladder: the row is staff configuration (the ``PortalAccount`` posture), so an account manager sets
#: it directly on the form. ``prospect`` -> ``onboarding`` -> ``active`` is the normal path;
#: ``suspended`` and ``terminated`` are the two ways it stops, and they are kept apart because they
#: mean different things to a warehouse — suspended stock is still ours to store, terminated stock is
#: being collected.
#:
#: ``max_length=16`` against two 10-char values (``onboarding``, ``terminated``).
CLIENT_STATUS_CHOICES = [
    ("prospect", "Prospect"),
    ("onboarding", "Onboarding"),
    ("active", "Active"),
    ("suspended", "Suspended"),
    ("terminated", "Terminated"),
]

#: ``suspended`` is AMBER and ``terminated`` is SLATE, not both red: a suspension is a live account
#: somebody has to act on, an ended contract is history. A list where every non-active row is red
#: trains the reader to ignore red.
CLIENT_STATUS_CSS = {
    "prospect": "badge-muted",
    "onboarding": "badge-info",
    "active": "badge-green",
    "suspended": "badge-amber",
    "terminated": "badge-slate",
}

#: How often this client is invoiced. Read by ``ClientBillingRun.recalc_amounts()``, which applies
#: the monthly minimum **only** to a monthly client — charging a monthly floor against a weekly run
#: would bill the floor four times a month.
BILLING_CYCLE_CHOICES = [
    ("weekly", "Weekly"),
    ("biweekly", "Bi-weekly"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
]

#: The five storage-billing conventions the surveyed 3PL billing engines actually implement, and the
#: single most consequential setting on the client record: each one walks the append-only
#: ``StockMove`` ledger a **different** way and produces a different number from the same stock.
#:
#: * ``calendar_month`` — the balance at the start of the period, billed for one period.
#: * ``anniversary`` — each receipt bills on its own monthly anniversary (the classic public-warehouse
#:   convention).
#: * ``split_month`` — receipts on days 1-15 bill a full period, days 16-end bill half.
#: * ``average_daily`` — the mean daily balance across the period, walked day by day.
#: * ``snapshot`` — the balance at the end of the period.
#:
#: ``ClientBillingRun.calculate()`` dispatches on this value. It is a CLOSED set for the reason
#: ``KpiTarget``'s metric registry is closed: a sixth convention is a new resolver somebody writes and
#: tests, never a formula a user types into a box.
#:
#: ``max_length=16`` against a 14-char longest value (``calendar_month``).
STORAGE_BILLING_METHOD_CHOICES = [
    ("calendar_month", "Calendar Month"),
    ("anniversary", "Anniversary"),
    ("split_month", "Split Month"),
    ("average_daily", "Average Daily"),
    ("snapshot", "Snapshot"),
]

#: Whether this client rents named space or shares the floor. Drives the "dedicated space" charge
#: basis and the Warehouse Rental Management page.
SPACE_MODEL_CHOICES = [
    ("shared", "Shared"),
    ("dedicated", "Dedicated"),
    ("hybrid", "Hybrid"),
]

#: The space models that MUST carry a commitment figure, and the reason ``LogisticsClient.clean()``
#: refuses a dedicated client with 0 sq ft and 0 pallet positions: a dedicated-space agreement with no
#: number in it prices at zero and nobody notices until the invoice goes out. Its mirror rule is
#: enforced from the other side too — a ``shared`` client carrying a commitment is refused rather than
#: ignored, because a figure a user typed and the system silently dropped is worse than an error.
COMMITTED_SPACE_MODELS = ("dedicated", "hybrid")

#: How this client's orders reach us. **Every value here is a non-secret partner identifier and
#: nothing more (L20).** 4.17 stores no API key, no endpoint URL, no EDI password and no token;
#: credential storage, EDI transport and webhooks are 4.19's. ``none`` is a real answer, not an empty
#: one — a client who emails a spreadsheet has an integration mode, and it is "none".
#:
#: ``max_length=12`` against an 11-char longest value (``marketplace``).
INTEGRATION_MODE_CHOICES = [
    ("none", "None"),
    ("manual", "Manual"),
    ("csv", "CSV"),
    ("api", "API"),
    ("edi", "EDI"),
    ("marketplace", "Marketplace"),
]


# =================================================================================================
# ClientRateCard / ClientRateCardLine — the tariff
# =================================================================================================

#: A tariff's life. ``superseded`` and ``expired`` are kept apart on purpose: one is a card we
#: replaced with a newer version, the other is a card whose own end date simply passed. Both are
#: read-only history, and telling them apart is what makes "why did the price change in April?"
#: answerable.
RATE_CARD_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("superseded", "Superseded"),
    ("expired", "Expired"),
]

RATE_CARD_STATUS_CSS = {
    "draft": "badge-muted",
    "active": "badge-green",
    "superseded": "badge-slate",
    "expired": "badge-amber",
}

#: A rate card may only gain, lose or change LINES while it is a draft. Once it is active it has
#: priced a run, and editing it would silently rewrite an invoice somebody already sent — the reason
#: superseding (a new version) is the only supported way to change an active tariff.
EDITABLE_RATE_CARD_STATUSES = ("draft",)

#: What a charge is FOR. This is the axis the billing run groups by and the axis a client argues
#: about, which is why it is separate from the basis (what it is measured in): "storage" and
#: "outbound" is the conversation, "per pallet position" and "per order" is the arithmetic.
#:
#: ``max_length=16`` against a 14-char longest value (``transportation``).
CHARGE_CATEGORY_CHOICES = [
    ("storage", "Storage"),
    ("receiving", "Receiving"),
    ("outbound", "Outbound"),
    ("value_added", "Value-Added"),
    ("accessorial", "Accessorial"),
    ("transportation", "Transportation"),
    ("recurring", "Recurring"),
    ("minimum", "Minimum"),
]

#: Colour groups by **what the charge is about**, not by severity — a charge category has no
#: severity. ``minimum`` is the one red: a minimum-charge line means the client did not use what they
#: agreed to pay for, which is the single line on an invoice most likely to start an argument, and it
#: should be findable at a glance.
CHARGE_CATEGORY_CSS = {
    "storage": "badge-info",
    "receiving": "badge-green",
    "outbound": "badge-amber",
    "value_added": "badge-slate",
    "accessorial": "badge-muted",
    "transportation": "badge-info",
    "recurring": "badge-slate",
    "minimum": "badge-red",
}

#: What a charge is MEASURED in. **A closed registry, and it will stay closed.** Each value is a
#: quantity resolver somebody wrote against real as-built columns; a rating *expression language*
#: (formulas, nested conditions, user-defined variables) is permanently out of scope for the same
#: reason ``KpiTarget`` refused to grow one — the tier bands (``tier_from`` / ``tier_to``) plus this
#: registry cover the surveyed tariffs, and an expression box covers everything by being untestable.
#:
#: ``max_length=20`` against a 19-char longest value (``per_pallet_position``).
CHARGE_BASIS_CHOICES = [
    ("per_pallet_position", "Per Pallet Position"),
    ("per_sqft", "Per Sq Ft"),
    ("per_cbm", "Per CBM"),
    ("per_unit", "Per Unit"),
    ("per_order", "Per Order"),
    ("per_line", "Per Order Line"),
    ("per_receipt", "Per Receipt"),
    ("per_carton", "Per Carton"),
    ("per_shipment", "Per Shipment"),
    ("per_kg", "Per Kg"),
    ("per_hour", "Per Hour"),
    ("flat_recurring", "Flat Recurring"),
    ("dedicated_space", "Dedicated Space"),
    ("pct_of_value", "% of Value"),
]

#: The unit a PERIODIC rate repeats over. Blank on an event-driven basis, required on a periodic one
#: — both directions enforced in ``ClientRateCardLine.clean()``.
RATE_PERIOD_CHOICES = [
    ("day", "Day"),
    ("week", "Week"),
    ("month", "Month"),
]

#: The bases that repeat over time and therefore REQUIRE a ``period``. A "£3.50 per pallet position"
#: with no period is not a price — it is a number nobody can invoice, because per day and per month
#: differ by a factor of thirty. The rule runs both ways: a ``period`` set on ``per_order`` is refused
#: rather than ignored, because it would be a value the user entered and the calculator never reads.
PERIODIC_BASES = (
    "per_pallet_position",
    "per_sqft",
    "per_cbm",
    "flat_recurring",
    "dedicated_space",
)

#: **PRICEABLE BUT NOT MEASURABLE — the honest gap in this build, stated in one place.**
#:
#: A tariff line on any of these bases is perfectly legitimate and can be saved, priced and shown; it
#: is the QUANTITY that this system cannot derive today, because the measurement simply is not on
#: disk: ``scm.Item`` carries no weight and no dimensions, ``scm.Location`` carries a ``capacity``
#: in "the bin's own units" and no area column, and per-client labour hours are 4.14's.
#:
#: ``ClientBillingRun.calculate()`` therefore writes these lines with ``quantity=0``,
#: ``needs_manual_quantity=True`` and a description that NAMES the missing measurement, so a biller
#: can type the figure in. **It never guesses a conversion factor.** A cubic-metre rate invented from
#: a pallet count is a number that looks authoritative, is wrong, and goes out on an invoice.
MANUAL_ONLY_BASES = (
    "per_sqft",
    "per_cbm",
    "per_kg",
    "per_hour",
    "per_carton",
    "pct_of_value",
)


# =================================================================================================
# ClientBillingRun — the period calculation
# =================================================================================================

#: The billing ladder, and it is a LADDER rather than a form field: ``ClientBillingRun.status`` is
#: ``editable=False`` and moves only through ``calculate()`` / ``approve()`` / ``draft_invoice()`` /
#: ``void()``. A status somebody can pick out of a dropdown is a label, not a state — and this
#: particular one gates whether an invoice may be drafted.
RUN_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("calculated", "Calculated"),
    ("approved", "Approved"),
    ("invoiced", "Invoiced"),
    ("void", "Void"),
]

RUN_STATUS_CSS = {
    "draft": "badge-muted",
    "calculated": "badge-info",
    "approved": "badge-amber",
    "invoiced": "badge-green",
    "void": "badge-slate",
}

#: A run's lines may be recalculated or hand-adjusted only up to the moment it is approved. After
#: approval the figures are what somebody signed off, and after invoicing they are what a customer
#: was billed — neither is a working document any more.
EDITABLE_RUN_STATUSES = ("draft", "calculated")


# =================================================================================================
# ClientSLA — what we promised, and what the ledger says we delivered
# =================================================================================================

#: The nine service metrics 3PL contracts are actually written against. Every one of them is
#: DERIVABLE from rows this application already holds — that is the entry test, and it is why the
#: list is nine rather than thirty. See :data:`SLA_METRIC_META` for exactly which rows each is
#: measured from.
#:
#: ``max_length=24`` against two 22-char values (``inventory_accuracy_pct``,
#: ``order_cycle_time_hours``).
SLA_METRIC_CHOICES = [
    ("on_time_shipment_pct", "On-Time Shipment %"),
    ("otif_pct", "OTIF %"),
    ("same_day_ship_pct", "Same-Day Ship %"),
    ("order_accuracy_pct", "Order Accuracy %"),
    ("inventory_accuracy_pct", "Inventory Accuracy %"),
    ("dock_to_stock_hours", "Dock-to-Stock Hours"),
    ("order_cycle_time_hours", "Order Cycle Time Hours"),
    ("damage_rate_pct", "Damage Rate %"),
    ("shrinkage_pct", "Shrinkage %"),
]

SLA_UNIT_CHOICES = [
    ("pct", "%"),
    ("hours", "Hours"),
    ("days", "Days"),
]

#: Which way is good. Without it a "target 24" on dock-to-stock and a "target 98" on on-time
#: shipment would be compared the same way, and the fast warehouse would read as the breaching one.
SLA_DIRECTION_CHOICES = [
    ("higher_is_better", "Higher is better"),
    ("lower_is_better", "Lower is better"),
]

#: The window a measurement covers. ``monthly`` means the last FULL calendar month and ``quarterly``
#: the last full quarter — never a part-period, because a target measured over four days of a month
#: is not the number anybody agreed to.
SLA_WINDOW_CHOICES = [
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("rolling_30", "Rolling 30 days"),
    ("rolling_90", "Rolling 90 days"),
]

#: **``no_data`` is a first-class answer and is NEVER merged into ``meeting``.** "We have no
#: shipments in this window" and "we hit the target" are different statements, and collapsing them
#: reports a green SLA for a warehouse that did nothing. ``recompute()`` writes ``no_data`` with the
#: reason in ``measurement_summary`` rather than writing a confident 0 (the 4.11 coverage lesson).
SLA_STATUS_CHOICES = [
    ("meeting", "Meeting"),
    ("at_risk", "At Risk"),
    ("breached", "Breached"),
    ("no_data", "No Data"),
]

SLA_STATUS_CSS = {
    "meeting": "badge-green",
    "at_risk": "badge-amber",
    "breached": "badge-red",
    "no_data": "badge-muted",
}

#: The CLOSED metric registry: for each metric, its label, the unit it MUST carry, the direction it
#: MUST be read in, a sensible contractual default, and — the key nobody may drop from the detail
#: page — ``source``, the plain-English statement of which as-built rows the figure is measured from.
#:
#: ``unit`` and ``direction`` are validated against, not merely suggested: ``ClientSLA.clean()``
#: refuses a percentage metric saved with ``hours``, because such a row would compare 98 against 24
#: and breach forever. The defaults are the surveyed contractual norms (99.5% order accuracy, 99%
#: inventory accuracy, 98% on-time, 95% OTIF, 24h dock-to-stock) and are a STARTING POINT the form
#: shows as help text — every one of them is negotiated per client.
#:
#: **``source`` must be rendered.** An SLA number with no statement of what it was computed from is
#: a number a client cannot audit, and the first question they ask is exactly this.
SLA_METRIC_META = {
    "on_time_shipment_pct": {
        "label": "On-Time Shipment %",
        "unit": "pct",
        "direction": "higher_is_better",
        "default_target": Decimal("98.00"),
        "source": "Shipments whose actual pickup date is on or before the planned pickup date, "
                  "over all shipments picked up in the window.",
    },
    "otif_pct": {
        "label": "OTIF %",
        "unit": "pct",
        "direction": "higher_is_better",
        "default_target": Decimal("95.00"),
        "source": "Shipments delivered on or before the planned delivery date whose sales order "
                  "also reached fulfilled/invoiced/closed — on time AND in full — over all "
                  "shipments delivered in the window.",
    },
    "same_day_ship_pct": {
        "label": "Same-Day Ship %",
        "unit": "pct",
        "direction": "higher_is_better",
        "default_target": Decimal("95.00"),
        "source": "Shipments picked up on the same calendar day as their sales order's order date, "
                  "over all shipments picked up in the window.",
    },
    "order_accuracy_pct": {
        "label": "Order Accuracy %",
        "unit": "pct",
        "direction": "higher_is_better",
        "default_target": Decimal("99.50"),
        "source": "Orders in the window with no return raised against a picking-error reason, over "
                  "all orders in the window. Reported as No Data when the return reasons on file "
                  "cannot distinguish a picking error from a customer change of mind.",
    },
    "inventory_accuracy_pct": {
        "label": "Inventory Accuracy %",
        "unit": "pct",
        "direction": "higher_is_better",
        "default_target": Decimal("99.00"),
        "source": "Cycle-count lines whose counted quantity equalled the expected quantity, over all "
                  "counted lines for this client's items in the window.",
    },
    "dock_to_stock_hours": {
        "label": "Dock-to-Stock Hours",
        "unit": "hours",
        "direction": "lower_is_better",
        "default_target": Decimal("24"),
        "source": "Mean hours from a goods receipt to the completion of its putaway task, for this "
                  "client's items. The receipt date is a DATE (it resolves to midnight) while the "
                  "putaway completion is a timestamp, so the figure is accurate to within a day.",
    },
    "order_cycle_time_hours": {
        "label": "Order Cycle Time Hours",
        "unit": "hours",
        "direction": "lower_is_better",
        "default_target": Decimal("24"),
        "source": "Mean hours from a sales order's order date to its shipment's actual pickup. The "
                  "order date is a DATE (midnight), so the figure is accurate to within a day.",
    },
    "damage_rate_pct": {
        "label": "Damage Rate %",
        "unit": "pct",
        "direction": "lower_is_better",
        "default_target": Decimal("0.50"),
        "source": "Negative adjustment movements on this client's items in the window, over the "
                  "quantity received for them in the same window.",
    },
    "shrinkage_pct": {
        "label": "Shrinkage %",
        "unit": "pct",
        "direction": "lower_is_better",
        "default_target": Decimal("0.65"),
        "source": "Net negative adjustment movements on this client's items in the window, over the "
                  "quantity received for them in the same window — unexplained loss rather than "
                  "recorded damage.",
    },
}


# =================================================================================================
# Bounds — enforced in clean() and in the calculators, quoted back in the messages
# =================================================================================================

#: Ceiling on how many lines one billing run may generate. A run walks a whole tariff against a whole
#: period of ledger activity; without a cap a misconfigured card (say a per-line charge against a
#: client with 40,000 order lines) turns one POST into a table scan and a page nobody can open.
MAX_RUN_LINES = 500

#: Ceiling on the lines one rate card may carry. A tariff is a negotiated document, not a data feed.
MAX_RATE_CARD_LINES = 200

#: Ceiling on a billing period, in days. Slightly over a year so a full leap year is legal and a
#: mistyped ``2026`` -> ``2062`` is not. The period is fed to day-by-day walks in ``average_daily``
#: storage, so an unbounded one is a loop somebody can start from a form.
MAX_RUN_PERIOD_DAYS = 366

#: Ceiling on the ledger/measurement rows any single derivation will walk. Both ``calculate()``'s
#: average-daily storage walk and ``ClientSLA.recompute()`` are bounded by it, and both SAY when the
#: bound bit rather than quietly reporting a partial figure as a total.
MAX_MEASUREMENT_ROWS = 20000

#: Ceilings on the space commitments, matching the column shapes exactly:
#: ``committed_sqft`` is ``DecimalField(max_digits=12, decimal_places=2)`` and
#: ``committed_pallet_positions`` is a ``PositiveIntegerField``. Stated here so ``clean()`` can refuse
#: an over-range figure as a field error instead of letting the driver raise ``DataError`` on save.
MAX_COMMITTED_SQFT = Decimal("9999999.99")
MAX_COMMITTED_PALLETS = 1000000

#: How far the parent-client chain may be walked before ``clean()`` gives up and refuses. A 3PL client
#: hierarchy is a handful of levels (group -> division -> brand); ten is generous. The walk exists to
#: catch a CYCLE — A parents B parents A — which without a bound is an infinite loop inside form
#: validation, i.e. a hung request from an ordinary edit.
MAX_CLIENT_DEPTH = 10
