"""Procurement 6.16 Supplier Performance & Evaluation — views sub-package init (docstring-only).

Re-exports live in ``apps/procurement/views/__init__.py`` — the app-level package is the single
re-export point (the 6.13/6.14/6.15/6.19 precedent), and that block is what the URLconf's
``views.<name>`` lookups resolve against. A view missing from it is an ``AttributeError`` at
URLconf import time, not a 404.

Five modules, 33 public views:

* ``SupplierKpis`` (5) — the KPI definition register + CRUD.
* ``ScorecardKpiScores`` (7) — the evaluation register over ``scm.SupplierScorecard``, its detail
  page, the one-way ``supplierevaluation_generate`` door, and the score-line register/detail/
  edit/delete. No score CREATE, by design.
* ``SupplierFeedback`` (8) — the 360 response register, CRUD and the submit / decline / expire
  verbs, so every ``STATUS_CHOICES`` value is reachable.
* ``SupplierImprovementPlans`` (10) — the PIP register, CRUD and the activate / monitor /
  acknowledge / close / cancel verbs.
* ``PerformanceBoards`` (3) — benchmark, trend and perception-gap. Read-only: every figure they
  render was frozen onto a ``SupplierKpiScore`` row by ``supplierevaluation_generate``, which is
  the one writer.

Everything ``_``-prefixed in these modules is private helper surface and is deliberately NOT
re-exported — a name in the app-level views package is a name the URLconf may route to.
"""
