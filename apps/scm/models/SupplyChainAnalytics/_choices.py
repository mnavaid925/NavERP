"""SCM 4.11 Supply Chain Analytics — the closed vocabularies shared by the three models.

**Why this file exists (import direction).** ``apps/scm/analytics.py`` is the compute layer: it
imports ``apps.scm.models`` to aggregate over 4.1-4.10. If ``KpiTarget.metric`` took its ``choices``
from ``analytics`` the edge would run both ways and the package would not import. So the split is the
one ``apps/crm`` already proved (``models/AnalyticsReporting/_choices.py`` vs ``apps/crm/analytics.py``):

* **this module owns the metric KEYS and their METADATA** — pure data, no queries, no model imports;
* **``analytics.py`` owns the RESOLVERS** and builds ``SCM_METRICS`` by attaching one to each key here.

The edge is therefore one-way (``analytics`` -> ``models`` -> ``_choices``), and both the model layer
and the compute layer read the *same* metadata, so a metric's direction/unit/scope can never disagree
between the tile that renders it and the ``clean()`` that validates a target for it.

**The metric set is CLOSED.** There is no formula field and no user-supplied SQL: a target picks a key
out of :data:`METRIC_CHOICES`. Author-your-own-KPI (a formula language over a semantic layer) is
Module 10's 10.11, not 4.11's — see the module docstring of ``apps/scm/analytics.py``.
"""
from apps.scm.models._base import *  # noqa: F401,F403


# --------------------------------------------------------------------------------------------
# Target / snapshot / alert vocabularies
# --------------------------------------------------------------------------------------------

#: What a target narrows to. Each value has ONE matching nullable FK on ``KpiTarget`` — four typed
#: FKs rather than a generic ``scope_ref`` integer, because a bare int carries neither a tenant nor a
#: type and would happily point at a deleted or cross-tenant row (L40 3: same tenant is not the same
#: subject; an untyped int does not even give you the tenant).
SCOPE_CHOICES = [
    ("all", "Whole network"),
    ("category", "Item category"),
    ("location", "Location"),
    ("carrier", "Carrier"),
    ("vendor", "Supplier"),
]

#: Maps a scope value to the ``KpiTarget`` field that must be set for it. ``all`` maps to None.
#: ``KpiTarget.clean()`` walks this so the "exactly one scope FK, and it matches ``scope``" check is
#: table-driven rather than a five-branch if-chain that drifts when a scope is added.
SCOPE_FIELDS = {
    "all": None,
    "category": "scope_category",
    "location": "scope_location",
    "carrier": "scope_carrier",
    "vendor": "scope_vendor",
}

#: Which way "good" runs. Drives band_for(), the arrow on every tile, and the ordering of the
#: target/warning/critical bands in clean().
DIRECTION_CHOICES = [
    ("higher_is_better", "Higher is better"),
    ("lower_is_better", "Lower is better"),
]

#: The bucket a trend point is measured over.
PERIOD_GRAIN_CHOICES = [
    ("day", "Daily"),
    ("week", "Weekly"),
    ("month", "Monthly"),
    ("quarter", "Quarterly"),
]

#: The rolling window a page/target reads. Same shape as CRM's ANALYTICS_RANGE_CHOICES so the two
#: analytics surfaces offer the operator the same words; resolved by ``analytics.range_bounds()``.
DATE_RANGE_CHOICES = [
    ("last_7", "Last 7 days"),
    ("last_30", "Last 30 days"),
    ("last_90", "Last 90 days"),
    ("quarter", "This quarter"),
    ("year", "This year"),
    ("all", "All time"),
]

#: Severity stamped on the alerts a target raises, and carried by hand-raised ones.
SEVERITY_CHOICES = [
    ("info", "Info"),
    ("warning", "Warning"),
    ("critical", "Critical"),
]

#: Where a measured value fell against its target. ``unknown`` is a real outcome, not a failure: a
#: target with no thresholds set still snapshots its value, it just cannot be banded.
BAND_CHOICES = [
    ("ok", "On target"),
    ("warning", "Warning"),
    ("critical", "Critical"),
    ("unknown", "No target"),
]

#: Groups map one-to-one onto the five NavERP 4.11 bullets and therefore onto the five report pages.
METRIC_GROUP_CHOICES = [
    ("inventory", "Inventory"),
    ("procurement", "Procurement"),
    ("logistics", "Logistics"),
    ("margin", "Margin & cost"),
    ("risk", "Risk & prediction"),
]

#: How a raw Decimal is rendered. ``analytics._display_for`` switches on this.
METRIC_UNIT_CHOICES = [
    ("turns", "Turns"),
    ("days", "Days"),
    ("hours", "Hours"),
    ("pct", "Percent"),
    ("money", "Money"),
    ("count", "Count"),
    ("score", "Score (0-100)"),
]


# --------------------------------------------------------------------------------------------
# The metric catalog
# --------------------------------------------------------------------------------------------
# One entry per computable figure. ``analytics.py`` attaches a resolver to each key and raises at
# import time if a key here has none, so this table and the compute layer cannot drift apart.
#
# Keys:
#   label          human name (also the KpiTarget.metric choice label)
#   group          which of the five report pages owns it
#   unit           how to render it
#   direction      which way "good" runs (a target may override for a deliberately inverted goal)
#   scopes         the SCOPE_CHOICES values this metric can legally narrow to. A carrier scope on a
#                  dead-stock metric is an empty conjunction (L39) - clean() rejects it from here.
#   requires_days  the metric is meaningless without KpiTarget.parameter_days
#   requires_pct   ... without KpiTarget.parameter_pct
#   kind           "scalar" (a number + optional supporting rows) or "table" (rows ARE the result)
#   primary        True = a figure the NavERP 4.11 bullet literally names
# --------------------------------------------------------------------------------------------

_ALL = ("all",)
_ITEM_SCOPES = ("all", "category", "location")
_VENDOR_SCOPES = ("all", "vendor")
_CARRIER_SCOPES = ("all", "carrier")

METRIC_META = {
    # ---- Inventory Dashboards ---------------------------------------------------------------
    # Over StockMove / Item / ItemCategory / Location / LotSerial / ReorderRule.
    "inv_turnover": {
        "label": "Inventory turnover",
        "group": "inventory", "unit": "turns", "direction": "higher_is_better",
        "scopes": _ITEM_SCOPES, "primary": True,
    },
    "inv_days_on_hand": {
        "label": "Days inventory on hand",
        "group": "inventory", "unit": "days", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES,
    },
    "inv_dead_stock_value": {
        "label": "Dead stock value",
        "group": "inventory", "unit": "money", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES, "requires_days": True, "primary": True,
    },
    "inv_aging_over_days_value": {
        "label": "Aging stock value (over N days)",
        "group": "inventory", "unit": "money", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES, "requires_days": True, "primary": True,
    },
    "inv_expiry_risk_value": {
        "label": "Expiry-risk value",
        "group": "inventory", "unit": "money", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES, "requires_days": True,
    },
    "inv_excess_vs_policy_value": {
        "label": "Excess over policy value",
        "group": "inventory", "unit": "money", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES,
    },
    "inv_carrying_cost": {
        "label": "Inventory carrying cost",
        "group": "inventory", "unit": "money", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES, "requires_pct": True,
    },
    "inv_stockout_count": {
        "label": "Items at or below reorder point",
        "group": "inventory", "unit": "count", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES,
    },
    "inv_abc_a_share_pct": {
        "label": "Class-A share of stock value",
        "group": "inventory", "unit": "pct", "direction": "higher_is_better",
        "scopes": _ITEM_SCOPES,
    },

    # ---- Procurement Analytics --------------------------------------------------------------
    # Over PurchaseOrder(+Line) / PurchaseRequisition / RFQ / RFQQuote / GoodsReceiptNote(+Line) /
    # SupplierContract / SupplierScorecard / SupplierCatalogItem / core.Party.
    "spend_total": {
        "label": "Total spend",
        "group": "procurement", "unit": "money", "direction": "lower_is_better",
        "scopes": _VENDOR_SCOPES, "primary": True,
    },
    "spend_off_contract_pct": {
        "label": "Off-contract spend",
        "group": "procurement", "unit": "pct", "direction": "lower_is_better",
        "scopes": _VENDOR_SCOPES, "primary": True,
    },
    "spend_top_supplier_share_pct": {
        "label": "Top-5 supplier share of spend",
        "group": "procurement", "unit": "pct", "direction": "lower_is_better",
        "scopes": _ALL,
    },
    "spend_tail_share_pct": {
        "label": "Tail-supplier share of spend",
        "group": "procurement", "unit": "pct", "direction": "lower_is_better",
        "scopes": _ALL,
    },
    "savings_negotiated": {
        "label": "Negotiated savings (awarded vs median quote)",
        "group": "procurement", "unit": "money", "direction": "higher_is_better",
        "scopes": _VENDOR_SCOPES, "primary": True,
    },
    "savings_price_variance_opportunity": {
        "label": "Price-variance savings opportunity",
        "group": "procurement", "unit": "money", "direction": "higher_is_better",
        "scopes": _VENDOR_SCOPES, "primary": True,
    },
    "supplier_otd_pct": {
        "label": "Supplier on-time delivery",
        "group": "procurement", "unit": "pct", "direction": "higher_is_better",
        "scopes": _VENDOR_SCOPES, "primary": True,
    },
    "supplier_reject_rate_pct": {
        "label": "Supplier reject rate",
        "group": "procurement", "unit": "pct", "direction": "lower_is_better",
        "scopes": _VENDOR_SCOPES, "primary": True,
    },
    "supplier_score_avg": {
        "label": "Average supplier scorecard",
        "group": "procurement", "unit": "score", "direction": "higher_is_better",
        "scopes": _VENDOR_SCOPES, "primary": True,
    },
    "procure_cycle_days": {
        "label": "Requisition-to-order cycle",
        "group": "procurement", "unit": "days", "direction": "lower_is_better",
        "scopes": _VENDOR_SCOPES,
    },
    "procure_lead_days": {
        "label": "Order-to-receipt lead time",
        "group": "procurement", "unit": "days", "direction": "lower_is_better",
        "scopes": _VENDOR_SCOPES,
    },

    # ---- Logistics KPIs ---------------------------------------------------------------------
    # Over Shipment / TrackingEvent / Load / LoadStop / Carrier / CarrierRateCard /
    # FreightInvoice(+Line) / YardVisit.
    "otd_pct": {
        "label": "On-time delivery",
        "group": "logistics", "unit": "pct", "direction": "higher_is_better",
        "scopes": _CARRIER_SCOPES, "primary": True,
    },
    "otif_pct": {
        "label": "On-time in-full (OTIF)",
        "group": "logistics", "unit": "pct", "direction": "higher_is_better",
        "scopes": _CARRIER_SCOPES,
    },
    "freight_cost_per_unit": {
        "label": "Freight cost per unit",
        "group": "logistics", "unit": "money", "direction": "lower_is_better",
        "scopes": _CARRIER_SCOPES, "primary": True,
    },
    "equipment_utilization_pct": {
        "label": "Equipment utilization",
        "group": "logistics", "unit": "pct", "direction": "higher_is_better",
        "scopes": _CARRIER_SCOPES, "primary": True,
    },
    "freight_variance_pct": {
        "label": "Freight billing variance",
        "group": "logistics", "unit": "pct", "direction": "lower_is_better",
        "scopes": _CARRIER_SCOPES,
    },
    "carrier_otd_trend": {
        "label": "Carrier on-time trend (4.6 scorecard)",
        "group": "logistics", "unit": "pct", "direction": "higher_is_better",
        "scopes": _CARRIER_SCOPES,
    },
    "dwell_hours_avg": {
        "label": "Average yard/dock dwell",
        "group": "logistics", "unit": "hours", "direction": "lower_is_better",
        "scopes": ("all", "carrier", "location"),
    },

    # ---- Financial Reporting (operational margin - NOT the statutory ledger, L29) ------------
    # Over SalesOrder(+Line) / StockMove / Item / ItemCategory / FreightInvoice / Shipment /
    # PickTask(+Line) / NonConformance / ReturnDisposition / WarrantyClaimCost / WorkOrder.
    "gross_margin_pct": {
        "label": "Gross margin",
        "group": "margin", "unit": "pct", "direction": "higher_is_better",
        "scopes": ("all", "category"), "primary": True,
    },
    "margin_after_cost_to_serve_pct": {
        "label": "Margin after cost-to-serve",
        "group": "margin", "unit": "pct", "direction": "higher_is_better",
        "scopes": ("all", "category"), "primary": True,
    },
    "supply_cost_stack": {
        "label": "Supply chain cost breakdown",
        "group": "margin", "unit": "money", "direction": "lower_is_better",
        "scopes": _ALL, "kind": "table", "primary": True,
    },
    "ppv_value": {
        "label": "Purchase price variance",
        "group": "margin", "unit": "money", "direction": "lower_is_better",
        "scopes": ("all", "category", "vendor"),
    },
    "scrap_value": {
        "label": "Scrap & write-off value",
        "group": "margin", "unit": "money", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES,
    },

    # ---- Predictive Analytics ---------------------------------------------------------------
    # Deterministic, fully explainable composites over real rows. NOT machine learning: every score
    # here renders its own component arithmetic (the SupplierScorecard.signal_summary precedent,
    # structured into KpiSnapshot.breakdown). Genuine ML/AutoML is Module 10's 10.13.
    "supplier_disruption_score": {
        "label": "Supplier disruption risk",
        "group": "risk", "unit": "score", "direction": "lower_is_better",
        "scopes": _VENDOR_SCOPES, "requires_days": True, "primary": True,
    },
    "demand_spike_count": {
        "label": "Demand spikes detected",
        "group": "risk", "unit": "count", "direction": "lower_is_better",
        "scopes": ("all", "category"), "requires_pct": True, "primary": True,
    },
    "projected_stockout_count": {
        "label": "Projected stockouts within lead time",
        "group": "risk", "unit": "count", "direction": "lower_is_better",
        "scopes": _ITEM_SCOPES, "primary": True,
    },
    "shipments_at_risk_count": {
        "label": "Shipments at risk",
        "group": "risk", "unit": "count", "direction": "lower_is_better",
        "scopes": _CARRIER_SCOPES, "requires_days": True,
    },
}

#: Defaults applied to every entry so a resolver/clean() can read the key unconditionally.
for _meta in METRIC_META.values():
    _meta.setdefault("requires_days", False)
    _meta.setdefault("requires_pct", False)
    _meta.setdefault("kind", "scalar")
    _meta.setdefault("primary", False)
del _meta

#: What ``KpiTarget.metric`` and ``KpiSnapshot.metric`` build their ``choices`` from. Grouped by
#: report page so the dropdown reads the way the sidebar does.
METRIC_CHOICES = [
    (_group_label, [(_key, _meta["label"]) for _key, _meta in METRIC_META.items()
                    if _meta["group"] == _group])
    for _group, _group_label in METRIC_GROUP_CHOICES
]

#: Flat key -> label, for anywhere a grouped list is awkward (CSV headers, admin, snapshot labels).
METRIC_LABELS = {_key: _meta["label"] for _key, _meta in METRIC_META.items()}

#: The five report pages, in sidebar order: group -> (url name, page title).
METRIC_GROUP_PAGES = {
    "inventory": ("scm:inventory_analytics", "Inventory Dashboards"),
    "procurement": ("scm:spend_analytics", "Procurement Analytics"),
    "logistics": ("scm:logistics_kpis", "Logistics KPIs"),
    "margin": ("scm:margin_analytics", "Financial Reporting"),
    "risk": ("scm:disruption_risk", "Predictive Analytics"),
}

#: What a detector can raise. One entry per researched exception class; ``kpi_breach`` is the generic
#: "a KpiTarget crossed its band" and the rest are rule-based exceptions that legitimately have no
#: target behind them.
ALERT_TYPE_CHOICES = [
    ("kpi_breach", "KPI breach"),
    ("dead_stock", "Dead stock"),
    ("expiry_risk", "Expiry risk"),
    ("stockout_risk", "Projected stockout"),
    ("demand_spike", "Demand spike"),
    ("shipment_at_risk", "Shipment at risk"),
    ("stale_tracking", "Stale tracking"),
    ("supplier_risk", "Supplier risk"),
    ("contract_expiry", "Contract expiry"),
    ("off_contract_spend", "Off-contract spend"),
    ("price_variance", "Price variance"),
    ("freight_variance", "Freight variance"),
]

#: Alert lifecycle. ``status`` is editable=False and moves only through the action views.
ALERT_STATUS_CHOICES = [
    ("open", "Open"),
    ("acknowledged", "Acknowledged"),
    ("snoozed", "Snoozed"),
    ("resolved", "Resolved"),
    ("dismissed", "Dismissed"),
]

#: Still demanding attention. The detector re-uses an OPEN row for a repeat breach rather than
#: creating a second one (see SupplyChainAlert's docstring for why this is not a DB constraint).
OPEN_ALERT_STATUSES = ("open", "acknowledged", "snoozed")
