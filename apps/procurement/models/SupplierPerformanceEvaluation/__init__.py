"""Procurement 6.16 Supplier Performance & Evaluation — sub-package init (docstring-only).

Re-exports live in ``apps/procurement/models/__init__.py`` — the app-level package is the single
re-export point (the 6.13/6.14/6.15/6.19 precedent, and every sub-package added since).

Four entity modules:

* ``SupplierKpis`` — ``SupplierKpi`` [SKP-], the KPI definition master: what to measure, which
  way is better, where the bands sit, and :meth:`SupplierKpi.score_and_band`, the ONE scale that
  generate, the manual score edit and the boards all band through.
* ``ScorecardKpiScores`` — ``SupplierKpiScore``, one measured figure per KPI per
  ``scm.SupplierScorecard``, with the definition frozen beside it. Written only by
  ``apps.procurement.performance.generate_scorecard_lines``.
* ``SupplierFeedback`` — ``SupplierFeedback`` [SFB-], one 360 response, internal or supplier
  self-assessment.
* ``SupplierImprovementPlans`` — ``SupplierImprovementPlan`` [SIP-], the work that followed a bad
  number.

**Why the CHOICES / CSS constants are NOT re-exported here, or app-wide.** Two of these modules
each declare a ``STATUS_CHOICES`` and a ``STATUS_CSS`` and they are DIFFERENT enums — the
feedback response lifecycle (requested / submitted / declined / expired) and the improvement-plan
lifecycle (draft / active / monitoring / closed / cancelled). Re-exporting both under one bare
name would silently shadow one with the other, and the loser would be whichever import line came
second — a bug with no error message, only a dropdown quietly offering the wrong four values.

So the vocabularies stay MODULE-SCOPED, which is also how every consumer already reads them:
views and forms import them from the entity module by path
(``from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import
STATUS_CHOICES``), and templates never import at all — they read the ``*_choices`` context keys
the view pins. Each constant is additionally aliased onto its own model class
(``SupplierFeedback.STATUS_CHOICES``, ``SupplierImprovementPlan.STATUS_CHOICES``), mirroring
``VendorSuspension``, so a class-qualified read is unambiguous by construction.
"""
