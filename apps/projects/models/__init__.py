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
# Re-export the shared base/toolkit, matching apps/accounting/models/__init__.py and
# apps/crm/models/__init__.py: without it ``from apps.projects.models import TenantNumbered`` (or
# ``q2`` / ``next_number``) raises ImportError, which is a live trap for the test suite.
from ._base import *  # noqa: F401,F403

# --- 7.1 Project Initiation & Charter ---------------------------------------------------------
from .ProjectInitiation.ProjectKickoffs import ProjectKickoff  # noqa: F401
from .ProjectInitiation.ProjectRequests import ProjectRequest  # noqa: F401
from .ProjectInitiation.ProjectStakeholders import ProjectStakeholder  # noqa: F401
from .ProjectInitiation.Projects import Project  # noqa: F401

# --- 7.2 Project Planning & Scheduling --------------------------------------------------------
from .ProjectPlanningScheduling.ProjectMilestones import ProjectMilestone  # noqa: F401
from .ProjectPlanningScheduling.ProjectTasks import ProjectTask  # noqa: F401
from .ProjectPlanningScheduling.ScheduleBaselines import ScheduleBaseline  # noqa: F401
from .ProjectPlanningScheduling.TaskDependencies import TaskDependency  # noqa: F401
