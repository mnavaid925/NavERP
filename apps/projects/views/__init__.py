"""Views package for the projects app (NavERP Module 7 — Project Management).

One sub-package per NavERP sub-module, one module per entity, mirroring models/ forms/ urls/.
Entity modules do ``from apps.projects.views._common import *`` and the package __init__
re-exports every view, so the urls package resolves ``views.prq_list``.

Context-var contract (pinned, L7 — an unpinned name renders blank at 200):
  * list  -> ``object_list`` + ``page_obj`` + ``q`` (+ the view's filter choices)
  * detail/edit object -> ``obj``
  * form  -> ``form`` + ``is_edit``
The per-entity extras are frozen in ``.claude/tasks/contract-projects-7.1.md``.
"""
