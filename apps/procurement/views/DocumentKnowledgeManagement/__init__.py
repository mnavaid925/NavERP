"""Procurement 6.19 Document & Knowledge Management — views sub-package init (docstring-only).

Re-exports live in ``apps/procurement/views/__init__.py`` (6.13/6.14/6.15 precedent) — that is
what makes ``views.<name>`` resolve for the ``apps/procurement/urls/`` package, so a view added
here without a line there is an ``AttributeError`` at URLconf import time, not a 404.

Entity modules: ``Documents`` (the repository register + its life-cycle verbs), ``Revisions``
(the immutable revision chain, its upload/approve/delete verbs), ``Policies`` and
``KnowledgeResources``.
"""
