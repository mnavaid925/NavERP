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

# --- 7.3 Resource Management ------------------------------------------------------------------
from .ResourceManagement.ResourceAllocations import ResourceAllocation  # noqa: F401
from .ResourceManagement.ResourceProfiles import ResourceProfile  # noqa: F401
from .ResourceManagement.ResourceTimeEntries import ResourceTimeEntry  # noqa: F401

# --- 7.4 Cost & Budget Management -------------------------------------------------------------
from .CostManagement.BudgetRevisions import BudgetRevision  # noqa: F401
from .CostManagement.CostControlAccounts import CostControlAccount  # noqa: F401
from .CostManagement.ProjectBudgetLines import ProjectBudgetLine  # noqa: F401
from .CostManagement.ProjectExpenses import ProjectExpense  # noqa: F401

# --- 7.5 Risk & Issue Management --------------------------------------------------------------
# Four new tables, no fifth: the register, its response actions, the issue log and the recorded
# escalation path. Every score, band, EMV and simulation figure is a derived property or a
# computed view — none of them is a column (the 7.1 ROI / 7.4 EVM ruling).
from .RiskManagement.IssueEscalations import IssueEscalation  # noqa: F401
from .RiskManagement.ProjectIssues import ProjectIssue  # noqa: F401
from .RiskManagement.ProjectRisks import ProjectRisk  # noqa: F401
from .RiskManagement.RiskResponseActions import RiskResponseAction  # noqa: F401

# --- 7.6 Quality Management -------------------------------------------------------------------
# Four new tables, no fifth: the acceptance-criteria plan, the structured quality event (QA and
# continuous improvement discriminated by review_type), the deliverable inspection (QC execution
# AND the acceptance decision on one row) and the punch-list defect. Every pass rate, punch-list
# count and maturity figure is a derived property or a computed view — none is a column — and the
# enterprise NCR/CAPA/audit/inspection tables are scm 4.9's (Ruling 1).
from .QualityManagement.DeliverableInspections import DeliverableInspection  # noqa: F401
from .QualityManagement.QualityDefects import QualityDefect  # noqa: F401
from .QualityManagement.QualityPlans import QualityPlan  # noqa: F401
from .QualityManagement.QualityReviews import QualityReview  # noqa: F401

# --- 7.7 Scope & Requirements Management ------------------------------------------------------
# Four new tables: the requirement register (with its traceability links), the boundary /
# assumption / constraint registry, the CCB change register and the deliverable acceptance log.
# The traceability MATRIX and the creep figures are computed pages — neither is a table, because a
# stored matrix goes stale the instant a link changes (the 7.4 EVM / 7.5 simulation ruling).
from .ScopeRequirements.Requirements import Requirement  # noqa: F401
from .ScopeRequirements.ScopeChangeRequests import ScopeChangeRequest  # noqa: F401
from .ScopeRequirements.ScopeItems import ScopeItem  # noqa: F401
from .ScopeRequirements.ScopeVerifications import ScopeVerification  # noqa: F401
