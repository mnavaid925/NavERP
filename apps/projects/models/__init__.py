"""Models package for the projects app (NavERP Module 7 — Project Management).

One sub-package per NavERP sub-module (7.1-…), one module per entity. Entity modules do
``from apps.projects.models._base import *`` and the package __init__ re-exports every model, so
``from apps.projects.models import Project`` works everywhere (admin, seeder, tests, views).

**Spine reuse (L28/L29):** this app declares ONLY its own four 7.1 tables. The people and
structure it points at live on the unified core spine — ``core.Party`` (client / stakeholder /
external requester), ``core.OrgUnit``, ``core.Document`` (the signed charter),
``core.Activity`` (kickoff meeting + onboarding items, GFK'd), ``accounting.Currency`` (global,
no tenant column) and ``crm.Opportunity`` (request provenance). Every one of those is referenced
**by string** so no cross-app model import happens at module level.

**The three PRJ- models:** ``accounting.Project`` and ``crm.CrmProject`` already mint ``PRJ-``
numbers. They are pre-spine stand-ins and are NOT touched from here — see the note on
``Project`` itself.
"""
