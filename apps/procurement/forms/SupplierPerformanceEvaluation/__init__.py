"""Procurement 6.16 Supplier Performance & Evaluation — forms sub-package init (docstring-only).

Re-exports live in ``apps/procurement/forms/__init__.py`` — the app-level package is the single
re-export point (the 6.13/6.14/6.15/6.19 precedent).

Four form classes across four entity modules:

* ``SupplierKpis.SupplierKpiForm`` — the KPI definition editor.
* ``ScorecardKpiScores.SupplierKpiScoreEditForm`` — EDIT only. There is deliberately no create
  form: a score line is written by ``performance.generate_scorecard_lines``, and a hand-created
  line would be a measurement with no computation behind it. The edit form exists for the
  ``source="manual"`` case, where the figure is a human's by definition.
* ``SupplierFeedback.SupplierFeedbackForm`` — create/edit of a 360 response request. The four
  lifecycle statuses are NOT on the form; they are reached through the submit / decline / expire
  POST verbs.
* ``SupplierImprovementPlans.SupplierImprovementPlanForm`` — create/edit of a PIP. ``status`` and
  ``outcome`` are likewise off the form and belong to the six verbs.

There is no form for the three boards: they are GET-driven read-only reports whose filter bar is
sanitised against a whitelist in the view, so a junk parameter degrades to "filter ignored"
rather than a page of red text (the 6.14 ``SpendDashboards`` posture).
"""
