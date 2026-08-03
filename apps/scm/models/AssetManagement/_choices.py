"""SCM 4.13 Asset Management — the vocabularies shared across more than one entity in the sub-module.

**Why this file exists.** Same rule as ``ContractCompliance/_choices.py``: a vocabulary read by exactly
one model lives on that model (``Asset.ASSET_TYPE_CHOICES``, ``MaintenanceWorkOrder.SOURCE_CHOICES``).
The seven below are read from **two or more directions at once** —

* ``CRITICALITY_CHOICES`` — declared on ``Asset``, filtered on the work-order list (jobs on critical
  assets first) and read by the PM forecast board.
* ``PRIORITY_CHOICES`` / ``WORK_TYPE_CHOICES`` — a ``MaintenancePlan`` *carries* them so the
  ``MaintenanceWorkOrder`` it generates can be *stamped* with them. One vocabulary, or the generate
  action silently drops a value the target column will not accept.
* ``PROBLEM_CODE_CHOICES`` / ``CAUSE_CODE_CHOICES`` / ``REMEDY_CODE_CHOICES`` — written on the work
  order, read back by the failure-analysis panel on the asset detail page.
* ``METER_SOURCE_CHOICES`` — written by ``MeterReading`` create and by the work-order **complete**
  verb.

**Pure data — no queries, no model imports, not even ``_base``.** ``apps/scm/models/__init__.py``
star-imports this module *before* the four entity modules, so the dependency edge can only ever run
one way and no import cycle is possible. ``__all__`` is explicit because of that star import: without
it every incidental name here (``Decimal``) would leak into ``apps.scm.models``.

**The CSS dicts.** Colour is decided in exactly one place per vocabulary (the ``KpiSnapshot.BAND_CSS``
precedent) so a badge cannot be styled one way on the list page and another on the detail page. Only
the six classes that actually exist in ``static/css/theme.css`` may appear —
``badge-green / badge-red / badge-amber / badge-info / badge-muted / badge-slate``. There is no
``badge-success`` / ``badge-warning`` / ``badge-danger``; those render completely unstyled (L33).
"""
from decimal import Decimal

__all__ = [
    "CRITICALITY_CHOICES", "CRITICALITY_CSS",
    "PRIORITY_CHOICES", "PRIORITY_CSS",
    "WORK_TYPE_CHOICES", "WORK_TYPE_CSS",
    "PROBLEM_CODE_CHOICES", "CAUSE_CODE_CHOICES", "REMEDY_CODE_CHOICES",
    "METER_SOURCE_CHOICES",
    "MAX_LABOUR_RATE",
]


#: How much it hurts when this asset stops. Drives work-order prioritisation and the PM board's
#: ordering — Fiix ("assign importance levels to assets so work is prioritised"), Infor asset
#: criticality, eMaint criticality as a standard field.
CRITICALITY_CHOICES = [
    ("critical", "Critical"),   # line stops / safety / regulatory exposure
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
]

CRITICALITY_CSS = {
    "critical": "badge-red",
    "high": "badge-amber",
    "medium": "badge-info",
    "low": "badge-muted",
}

#: Urgency of one job. Carried by a plan (so generated jobs inherit it) and set directly on an
#: ad-hoc request — MaintainX's request-to-prioritised-work-order flow.
PRIORITY_CHOICES = [
    ("urgent", "Urgent"),
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
]

PRIORITY_CSS = {
    "urgent": "badge-red",
    "high": "badge-amber",
    "medium": "badge-info",
    "low": "badge-muted",
}

#: What kind of work this is. Infor's reactive -> preventive -> predictive -> condition-based maturity
#: curve, plus Odoo's preventive/corrective split. ``calibration`` reserves the slot 4.9's research
#: parked here; ``predictive`` is the seam 11.7 / IoT will write into. Longest value is 10 chars
#: (``preventive`` / ``inspection``) — the column is ``max_length=12`` for headroom, because a
#: 13-char value added later is a column widen, not "a one-line choices change".
WORK_TYPE_CHOICES = [
    ("preventive", "Preventive"),
    ("corrective", "Corrective"),
    ("breakdown", "Breakdown"),
    ("inspection", "Inspection"),
    ("calibration", "Calibration"),
    ("predictive", "Predictive"),
    ("safety", "Safety"),
]

WORK_TYPE_CSS = {
    "preventive": "badge-green",
    "corrective": "badge-amber",
    "breakdown": "badge-red",
    "inspection": "badge-info",
    "calibration": "badge-info",
    "predictive": "badge-slate",
    "safety": "badge-red",
}

#: **Maximo's failure hierarchy** — failure class -> problem -> cause -> remedy — is the canonical
#: model here, and SAP's damage/cause catalogs are the same idea. The three lists below are that
#: hierarchy flattened to its bottom three levels, kept CLOSED on purpose: a closed vocabulary is
#: what makes "which cause costs us the most downtime?" answerable with a ``GROUP BY`` and no sensor
#: stack at all. Free-text symptoms would make the same page impossible.
#: ``other`` is present in all three so a technician is never forced into a wrong code — the honest
#: escape hatch keeps the other values trustworthy.
PROBLEM_CODE_CHOICES = [
    ("no_start", "Will not start"),
    ("overheating", "Overheating"),
    ("vibration", "Excessive vibration"),
    ("leak", "Leak"),
    ("noise", "Abnormal noise"),
    ("jam_blockage", "Jam / blockage"),
    ("electrical_fault", "Electrical fault"),
    ("hydraulic_fault", "Hydraulic / pneumatic fault"),
    ("wear", "Wear / worn part"),
    ("corrosion", "Corrosion"),
    ("calibration_drift", "Out of calibration"),
    ("software_fault", "Control / software fault"),
    ("other", "Other"),
]

CAUSE_CODE_CHOICES = [
    ("lack_of_lubrication", "Lack of lubrication"),
    ("contamination", "Contamination"),
    ("misalignment", "Misalignment"),
    ("fatigue", "Material fatigue"),
    ("overload", "Overload / over-speed"),
    ("operator_error", "Operator error"),
    ("design_defect", "Design defect"),
    ("material_defect", "Material / part defect"),
    ("environmental", "Environmental (heat, dust, damp)"),
    ("age_wear", "Normal age / wear"),
    ("improper_install", "Improper installation or repair"),
    ("unknown", "Unknown"),
    ("other", "Other"),
]

REMEDY_CODE_CHOICES = [
    ("repair", "Repaired in place"),
    ("replace_part", "Replaced part"),
    ("adjust_align", "Adjusted / realigned"),
    ("lubricate", "Lubricated"),
    ("clean", "Cleaned"),
    ("recalibrate", "Recalibrated"),
    ("software_update", "Software / parameter update"),
    ("operator_retrain", "Operator retrained"),
    ("no_action", "No fault found — no action"),
    ("monitor", "Monitoring, no action yet"),
    ("other", "Other"),
]

#: Where a meter reading came from. ``sensor`` is written by nothing in this pass — it is the seam
#: left open for 11.7 / IoT ingestion, and it is declared now so that feed lands as a new *row
#: source* rather than a schema change.
METER_SOURCE_CHOICES = [
    ("manual", "Manual entry"),
    ("work_order", "Captured on a work order"),
    ("sensor", "Sensor / IoT feed"),
]

#: Ceiling on ``MaintenanceWorkOrder.labour_rate``. Same reasoning as
#: ``Manufacturing/WorkCenters.py:60-67``: ``q4()`` **clamps** rather than raising, editing a work
#: order is only ``@login_required``, and an absurd rate does not stay local — it flows straight into
#: the job's ``total_cost()``, the asset's ``maintenance_cost_to_date()`` and the repair-vs-replace
#: ratio on the depreciation report. One poisoned row would move three pages, so the ceiling is a
#: validator on the way in, not a clamp on the way out.
MAX_LABOUR_RATE = Decimal("100000")
