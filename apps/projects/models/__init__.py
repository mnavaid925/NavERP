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

# --- 7.8 Task & Work Management ---------------------------------------------------------------
# Two new tables, no third: the checklist tick inside a task and the block/unblock evidence row
# (minted by ``tsk_block``, closed by ``tsk_unblock``, frozen as evidence after — never
# form-created, edited or deleted). The execution fields (assignee, priority, MoSCoW, the
# Eisenhower pair, percent_complete and the verb-written actual_start/actual_end stamps) extend
# ``ProjectTask`` IN PLACE — the documented 7.2 hand-off — and the kanban board, the gantt
# timeline and the priority lens are computed pages: none of them is a table, because a stored
# board goes stale the instant a task moves (the 7.4 EVM / 7.5 simulation / 7.6 boards ruling).
from .TaskWorkManagement.TaskBlocks import TaskBlock  # noqa: F401
from .TaskWorkManagement.TaskChecklistItems import TaskChecklistItem  # noqa: F401

# --- 7.9 Collaboration & Communication ---------------------------------------------------------
# Six new tables across five entity modules, and no seventh: the channel owns the conversation,
# the message carries the thread (a self-FK) and the mention audience, the share records who may
# do what with an already-stored `core.Document` (7.10 owns the repository and its versions), the
# meeting holds its agenda and its action items as children in ONE file (the `Invoices.py` =
# `Invoice` + `InvoiceLine` rule — neither child has an independent register), and the
# notification is the per-recipient delivery row. The merged ACTIVITY FEED is a computed page —
# no table, because a stored feed goes stale the instant a message lands (the 7.4 EVM / 7.5
# simulation / 7.6 boards / 7.8 board ruling).
from .CollaborationCommunication.ChannelMessages import ChannelMessage  # noqa: F401
from .CollaborationCommunication.Channels import Channel  # noqa: F401
from .CollaborationCommunication.DocumentShares import DocumentShare  # noqa: F401
from .CollaborationCommunication.Meetings import (  # noqa: F401
    Meeting,
    MeetingActionItem,
    MeetingAgendaItem,
)
from .CollaborationCommunication.ProjectNotifications import ProjectNotification  # noqa: F401

# --- 7.10 Document & Knowledge Management -------------------------------------------------------
# Five new tables, no sixth: the per-project folder tree, the document REGISTER (metadata, the
# expected/placeholder state, the cooperative check-out lock, retention intent, the archive and
# legal-hold flags, the integer revision pointer and the denormalized search copy), the immutable
# revision chain, the tenant-wide standards library and the reusable-insight library. This
# sub-module deliberately does NOT touch `core.Document` (a GFK register cannot be tenant-filtered,
# joined or faceted — procurement 6.19's recorded rejection): 7.9's `DocumentShare` keeps FK-ing
# `core.Document` and is shown here as a read-only lens. The repository overview, the retention &
# archiving board and the knowledge search are computed pages — no tables, because a stored board
# goes stale the instant a document is approved (the 7.4 EVM / 7.5 simulation / 7.6 / 7.8 / 7.9
# ruling). Nothing here deletes anything on a schedule: retention is an intent a human reads.
from .DocumentKnowledgeManagement.Documents import ProjectDocument  # noqa: F401
from .DocumentKnowledgeManagement.Knowledge import KnowledgeEntry  # noqa: F401
from .DocumentKnowledgeManagement.ProjectFolders import ProjectFolder  # noqa: F401
from .DocumentKnowledgeManagement.Revisions import ProjectDocumentRevision  # noqa: F401
from .DocumentKnowledgeManagement.Templates import DocumentTemplate  # noqa: F401

# --- 7.11 Time & Attendance Tracking ------------------------------------------------------------
from .TimeAttendanceTracking.ActivityCodes import TimeActivityCode  # noqa: F401
from .TimeAttendanceTracking.OvertimeRecords import ProjectOvertimeRecord  # noqa: F401
from .TimeAttendanceTracking.OvertimeRules import OvertimeRule  # noqa: F401

# --- 7.12 Portfolio & Program Management --------------------------------------------------------
from .PortfolioProgramManagement.Portfolios import Portfolio  # noqa: F401
from .PortfolioProgramManagement.Programs import Program  # noqa: F401
from .PortfolioProgramManagement.PortfolioInvestments import PortfolioInvestment  # noqa: F401
from .PortfolioProgramManagement.ProgramDependencies import ProgramDependency  # noqa: F401

# --- 7.13 Agile & Scrum Management --------------------------------------------------------------
from .AgileScrumManagement.ProjectEpics import ProjectEpic  # noqa: F401
from .AgileScrumManagement.ProjectReleases import ProjectRelease  # noqa: F401
from .AgileScrumManagement.Sprints import Sprint  # noqa: F401
from .AgileScrumManagement.SprintImpediments import SprintImpediment  # noqa: F401
from .AgileScrumManagement.SprintRetrospectives import SprintRetrospective  # noqa: F401

# --- 7.14 Client & External Collaboration -------------------------------------------------------
from .ClientExternalCollaboration.ClientPortals import ClientPortalAccess  # noqa: F401
from .ClientExternalCollaboration.ClientFeedbacks import ClientApprovalRequest  # noqa: F401
from .ClientExternalCollaboration.StatementOfWorks import StatementOfWork, SOWAmendment  # noqa: F401
from .ClientExternalCollaboration.VendorHandoffs import VendorHandoff  # noqa: F401
from .ClientExternalCollaboration.ClientInvoices import ProjectClientInvoice  # noqa: F401

# --- 7.15 Financial & Billing Management --------------------------------------------------------
from .FinancialBillingManagement.RateCards import ProjectRateCard  # noqa: F401
from .FinancialBillingManagement.BillingRuns import ProjectBillingRun  # noqa: F401
from .FinancialBillingManagement.RevenueSchedules import ProjectRevenueSchedule  # noqa: F401
from .FinancialBillingManagement.PaymentRecords import ProjectPaymentRecord  # noqa: F401

# --- 7.16 Reporting & Business Intelligence ------------------------------------------------------
from .ReportingBusinessIntelligence.ProjectReports import ProjectReport  # noqa: F401
from .ReportingBusinessIntelligence.ReportRuns import ProjectReportRun  # noqa: F401
from .ReportingBusinessIntelligence.ProjectDashboards import ProjectDashboard  # noqa: F401
from .ReportingBusinessIntelligence.DashboardWidgets import DashboardWidget  # noqa: F401

# 7.17 Workflow & Automation
from .WorkflowAutomation.WorkflowRules import (  # noqa: F401
    ProjectWorkflowRule,
    WorkflowExecutionLog,
)
from .WorkflowAutomation.ApprovalGates import (  # noqa: F401
    ProjectApprovalGate,
)
from .WorkflowAutomation.RecurringTasks import (  # noqa: F401
    RecurringTaskSchedule,
)
from .WorkflowAutomation.Webhooks import (  # noqa: F401
    ProjectWebhookEndpoint,
    ProjectWebhookDelivery,
)
