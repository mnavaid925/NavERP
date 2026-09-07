"""Forms package for the projects app (NavERP Module 7 — Project Management).

One sub-package per NavERP sub-module, one module per entity, mirroring models/ views/ urls/.
Entity modules do ``from apps.projects.forms._common import *`` and the package __init__
re-exports every form, so views and tests import ``from apps.projects.forms import X``.

The shared toolkit lives in ``_common.py``: ``TenantModelForm`` (core), ``TenantUniqueMixin``
(stamps ``instance.tenant`` before ``full_clean()``, so a model ``clean()`` that compares a
chosen FK's tenant can trust it) and ``_reject_foreign`` (a narrowed ``<select>`` is UX, not an
authorization boundary).
"""
# --- 7.1 Project Initiation & Charter ---------------------------------------------------------
from .ProjectInitiation.ProjectKickoffs import ProjectKickoffForm  # noqa: F401
from .ProjectInitiation.ProjectRequests import (  # noqa: F401
    ProjectRequestDecisionForm,
    ProjectRequestForm,
)
from .ProjectInitiation.ProjectStakeholders import ProjectStakeholderForm  # noqa: F401
from .ProjectInitiation.Projects import ProjectForm  # noqa: F401
