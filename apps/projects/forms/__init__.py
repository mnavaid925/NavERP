"""Forms package for the projects app (NavERP Module 7 â€” Project Management).

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
# (or ``TenantModelForm`` / ``MAX_UPLOAD_BYTES``) raises ImportError â€” crm's own suite depends on
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
# ``iss_resolve``) â€” the closure note and the resolution evidence are written by the verb that
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
# ``DefectResolutionForm`` for ``qdf_resolve``) â€” the acceptance stamps and the resolution
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

# --- 7.8 Task & Work Management ---------------------------------------------------------------
# FOUR re-exports (the old "three forms, no fourth" wording miscounted the block pair, review M2):
# the checklist-item ModelForm, the execution ModelForm that carries the form-writable half of
# ProjectTask's 7.8 fields (assignee, priority, MoSCoW, the Eisenhower pair, percent_complete â€”
# actual_start/actual_end are verb-written and are on NO form), and the two plain ``forms.Form``
# verb bodies of the block evidence row (a block needs a written reason AND unblock criteria; an
# unblock, a resolution note). TaskBlock itself has no ModelForm by ruling: the row is minted by
# ``tsk_block`` and closed by ``tsk_unblock``, never form-created or edited.
from .TaskWorkManagement.ProjectTasks import TaskExecutionForm  # noqa: F401
from .TaskWorkManagement.TaskBlocks import TaskBlockForm, TaskUnblockForm  # noqa: F401
from .TaskWorkManagement.TaskChecklistItems import TaskChecklistItemForm  # noqa: F401

# --- 7.9 Collaboration & Communication ---------------------------------------------------------
# SEVEN re-exports across FOUR modules â€” and deliberately none for `ProjectNotification`: a
# notification row is minted by a trigger (msg_create/msg_edit, the seeder, later 7.17's rule
# engine) and closed by ntf_mark_read, so it has no ModelForm and no create/edit route, which
# means no forms module for it. `MeetingMinutesForm` is a plain `forms.Form` verb body (the
# `TaskBlockForm` idiom); `MeetingAgendaItemForm` and `MeetingActionItemForm` deliberately EXCLUDE
# `meeting`, because it comes from the URL pk rather than from user input.
from .CollaborationCommunication.ChannelMessages import ChannelMessageForm  # noqa: F401
from .CollaborationCommunication.Channels import ChannelForm  # noqa: F401
from .CollaborationCommunication.DocumentShares import DocumentShareForm  # noqa: F401
from .CollaborationCommunication.Meetings import (  # noqa: F401
    MeetingActionItemForm,
    MeetingAgendaItemForm,
    MeetingForm,
    MeetingMinutesForm,
)

# --- 7.10 Document & Knowledge Management -------------------------------------------------------
# FIVE re-exports across FOUR modules: the folder tree, the document register, the revision UPLOAD
# form (create-path only — a revision has no edit form anywhere, because its immutability is
# structural), the file-backed standards library and the reusable-insight library. The revision
# form deliberately carries NO `revision_no`/`is_approved`: the view assigns the number from
# next_revision_no() inside the save transaction and an upload never approves itself.
from .DocumentKnowledgeManagement.Documents import ProjectDocumentForm  # noqa: F401
from .DocumentKnowledgeManagement.Knowledge import KnowledgeEntryForm  # noqa: F401
from .DocumentKnowledgeManagement.ProjectFolders import ProjectFolderForm  # noqa: F401
from .DocumentKnowledgeManagement.Revisions import ProjectDocumentRevisionUploadForm  # noqa: F401
from .DocumentKnowledgeManagement.Templates import DocumentTemplateForm  # noqa: F401

# --- 7.11 Time & Attendance Tracking ------------------------------------------------------------
from .TimeAttendanceTracking.ActivityCodes import TimeActivityCodeForm  # noqa: F401
from .TimeAttendanceTracking.OvertimeRecords import ProjectOvertimeRecordForm  # noqa: F401
from .TimeAttendanceTracking.OvertimeRules import OvertimeRuleForm  # noqa: F401

# --- 7.12 Portfolio & Program Management --------------------------------------------------------
from .PortfolioProgramManagement.Portfolios import PortfolioForm  # noqa: F401
from .PortfolioProgramManagement.Programs import ProgramForm  # noqa: F401
from .PortfolioProgramManagement.PortfolioInvestments import (  # noqa: F401
    PortfolioInvestmentForm,
    InvestmentDecisionForm,
)
from .PortfolioProgramManagement.ProgramDependencies import ProgramDependencyForm  # noqa: F401

# --- 7.13 Agile & Scrum Management --------------------------------------------------------------
from .AgileScrumManagement.ProjectEpics import ProjectEpicForm  # noqa: F401
from .AgileScrumManagement.ProjectReleases import ProjectReleaseForm  # noqa: F401
from .AgileScrumManagement.SprintImpediments import SprintImpedimentForm  # noqa: F401
from .AgileScrumManagement.SprintRetrospectives import SprintRetrospectiveForm  # noqa: F401
from .AgileScrumManagement.Sprints import SprintForm  # noqa: F401

# --- 7.14 Client & External Collaboration -------------------------------------------------------
from .ClientExternalCollaboration.ClientPortals import ClientPortalAccessForm  # noqa: F401
from .ClientExternalCollaboration.ClientFeedbacks import ClientApprovalRequestForm  # noqa: F401
from .ClientExternalCollaboration.StatementOfWorks import (  # noqa: F401
    SOWAmendmentForm,
    StatementOfWorkForm,
)
from .ClientExternalCollaboration.VendorHandoffs import VendorHandoffForm  # noqa: F401
from .ClientExternalCollaboration.ClientInvoices import ProjectClientInvoiceForm  # noqa: F401

# --- 7.15 Financial & Billing Management --------------------------------------------------------
from .FinancialBillingManagement.RateCards import ProjectRateCardForm  # noqa: F401
from .FinancialBillingManagement.BillingRuns import (  # noqa: F401
    BillingRunDispatchForm,
    ProjectBillingRunForm,
)
from .FinancialBillingManagement.RevenueSchedules import (  # noqa: F401
    ProjectRevenueScheduleForm,
    RevenueScheduleRecognizeForm,
)
from .FinancialBillingManagement.PaymentRecords import (  # noqa: F401
    ContactLogForm,
    PaymentPromiseForm,
    ProjectPaymentRecordForm,
)

# --- 7.17 Workflow & Automation -----------------------------------------------------------------
from .WorkflowAutomation.WorkflowRules import (  # noqa: F401
    ProjectWorkflowRuleForm,
    WorkflowRuleTestForm,
)
from .WorkflowAutomation.ApprovalGates import (  # noqa: F401
    ProjectApprovalGateForm,
    ApprovalDecisionForm,
    ApprovalDelegateForm,
)
from .WorkflowAutomation.RecurringTasks import (  # noqa: F401
    RecurringTaskScheduleForm,
)
from .WorkflowAutomation.Webhooks import (  # noqa: F401
    ProjectWebhookEndpointForm,
    WebhookTestPingForm,
)

# --- 7.16 Reporting & Business Intelligence --------------------------------------
from .ReportingBusinessIntelligence.ProjectReports import ProjectReportForm  # noqa: F401
from .ReportingBusinessIntelligence.ReportRuns import (  # noqa: F401
    ProjectReportIssueForm,
    ProjectReportNarrativeForm,
)
from .ReportingBusinessIntelligence.ProjectDashboards import ProjectDashboardForm  # noqa: F401
from .ReportingBusinessIntelligence.DashboardWidgets import DashboardWidgetForm  # noqa: F401

# --- 7.18 Integration & API Hub -------------------------------------------------
from .IntegrationApiHub.Connectors import (  # noqa: F401
    ConnectorTestForm,
    ProjectIntegrationConnectorForm,
)
from .IntegrationApiHub.FieldMappings import ConnectorFieldMappingForm  # noqa: F401
from .IntegrationApiHub.SyncJobs import ProjectSyncJobForm  # noqa: F401

