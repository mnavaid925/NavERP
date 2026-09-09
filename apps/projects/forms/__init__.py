"""Forms package for the projects app (NavERP Module 7 — Project Management).

One sub-package per NavERP sub-module, one module per entity, mirroring models/ views/ urls/.
Entity modules do ``from apps.projects.forms._common import *`` and the package __init__
re-exports every form, so views and tests import ``from apps.projects.forms import X``.

The shared toolkit lives in ``_common.py``: ``TenantModelForm`` (core), ``TenantUniqueMixin``
(stamps ``instance.tenant`` before ``full_clean()``, so a model ``clean()`` that compares a
chosen FK's tenant can trust it) and ``_reject_foreign`` (a narrowed ``<select>`` is UX, not an
authorization boundary).
"""
# Re-export the shared toolkit, matching apps/accounting/forms/__init__.py and
# apps/crm/forms/__init__.py: without it ``from apps.projects.forms import TenantUniqueMixin``
# (or ``TenantModelForm`` / ``MAX_UPLOAD_BYTES``) raises ImportError — crm's own suite depends on
# exactly this line, so the omission is a live trap for the projects test suite too.
from ._common import *  # noqa: F401,F403

# --- 7.1 Project Initiation & Charter ---------------------------------------------------------
from .ProjectInitiation.ProjectKickoffs import ProjectKickoffForm  # noqa: F401
from .ProjectInitiation.ProjectRequests import (  # noqa: F401
    ProjectRequestDecisionForm,
    ProjectRequestForm,
)
from .ProjectInitiation.ProjectStakeholders import ProjectStakeholderForm  # noqa: F401
from .ProjectInitiation.Projects import ProjectForm  # noqa: F401

# --- 7.2 Project Planning & Scheduling --------------------------------------------------------
from .ProjectPlanningScheduling.ProjectMilestones import MilestoneForm  # noqa: F401
from .ProjectPlanningScheduling.ProjectTasks import TaskForm  # noqa: F401
from .ProjectPlanningScheduling.ScheduleBaselines import BaselineForm  # noqa: F401
from .ProjectPlanningScheduling.TaskDependencies import TaskDependencyForm  # noqa: F401

# --- 7.3 Resource Management ------------------------------------------------------------------
from .ResourceManagement.ResourceAllocations import ResourceAllocationForm  # noqa: F401
from .ResourceManagement.ResourceProfiles import ResourceProfileForm  # noqa: F401
from .ResourceManagement.ResourceTimeEntries import ResourceTimeEntryForm  # noqa: F401
