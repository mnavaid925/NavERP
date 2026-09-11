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

# --- 7.4 Cost & Budget Management -------------------------------------------------------------
from .CostManagement.BudgetRevisions import (  # noqa: F401
    BudgetRevisionDecisionForm,
    BudgetRevisionForm,
)
from .CostManagement.CostControlAccounts import CostControlAccountForm  # noqa: F401
from .CostManagement.ProjectBudgetLines import ProjectBudgetLineForm  # noqa: F401
from .CostManagement.ProjectExpenses import ProjectExpenseForm  # noqa: F401

# --- 7.5 Risk & Issue Management --------------------------------------------------------------
# Six forms: the four register ModelForms plus the two plain ``forms.Form`` companions the
# verb-driven steps need (``RiskClosureForm`` for ``rsk_close``, ``IssueResolutionForm`` for
# ``iss_resolve``) — the closure note and the resolution evidence are written by the verb that
# also stamps the evidence fields, never by a generic edit.
from .RiskManagement.IssueEscalations import IssueEscalationForm  # noqa: F401
from .RiskManagement.ProjectIssues import (  # noqa: F401
    IssueResolutionForm,
    ProjectIssueForm,
)
from .RiskManagement.ProjectRisks import ProjectRiskForm, RiskClosureForm  # noqa: F401
from .RiskManagement.RiskResponseActions import RiskResponseActionForm  # noqa: F401

# --- 7.6 Quality Management -------------------------------------------------------------------
# Six forms: the four register ModelForms plus the two plain ``forms.Form`` companions the
# verb-driven gates need (``InspectionAcceptanceForm`` for ``qci_accept``'s usage decision,
# ``DefectResolutionForm`` for ``qdf_resolve``) — the acceptance stamps and the resolution
# evidence are written by the verb that stamps them, never by a generic edit.
from .QualityManagement.DeliverableInspections import (  # noqa: F401
    DeliverableInspectionForm,
    InspectionAcceptanceForm,
)
from .QualityManagement.QualityDefects import (  # noqa: F401
    DefectResolutionForm,
    QualityDefectForm,
)
from .QualityManagement.QualityPlans import QualityPlanForm  # noqa: F401
from .QualityManagement.QualityReviews import QualityReviewForm  # noqa: F401

# --- 7.7 Scope & Requirements Management ------------------------------------------------------
# Nine forms: the four register ModelForms plus the five plain ``forms.Form`` companions the
# verb-driven gates need (a rejection always needs a written reason; a verification, an outcome, a
# CCB decision and an acceptance note are captured by the verb that stamps the evidence columns).
from .ScopeRequirements.Requirements import (  # noqa: F401
    RequirementForm,
    RequirementRejectionForm,
    RequirementVerificationForm,
)
from .ScopeRequirements.ScopeChangeRequests import (  # noqa: F401
    ChangeRejectionForm,
    ScopeChangeForm,
)
from .ScopeRequirements.ScopeItems import ScopeItemForm, ScopeItemOutcomeForm  # noqa: F401
from .ScopeRequirements.ScopeVerifications import (  # noqa: F401
    ScopeVerificationForm,
    VerificationDecisionForm,
)
