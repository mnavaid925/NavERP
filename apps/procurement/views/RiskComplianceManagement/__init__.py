"""Procurement 6.17 Risk & Compliance Management — sub-package init (docstring-only).

Re-exports live in ``apps/procurement/views/__init__.py`` — the app-level package is the single
re-export point, and it is what makes ``views.<name>`` resolve from the urls package
(6.13/6.14/6.15 precedent). Entity modules: ``Screenings`` (the screening register, its detail
page, capture/amend, the three decision verbs and the re-screening board) and ``ScreeningHits``
(the cross-screening resolution queue and the adjudication verb).
"""
