"""Projects URLconf package — one sub-package per NavERP sub-module, one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets ``app_name = "projects"``
once and concatenates them.

Django is first-match-wins: within each module the literal routes (`add/`) precede the
``<int:pk>/`` ones, and every first segment (``""`` — the root, i.e. the module landing page
``projects:overview`` — then ``project-requests/``, ``projects/``, ``stakeholders/``,
``kickoffs/``, ``tasks/``, ``dependencies/``, ``milestones/``, ``baselines/``) is a distinct
whole component.

No route in this app uses a converter in its FIRST path component — every first segment is a
literal — so no module can shadow another's namespace. That invariant is what makes the guarantee
hold, and it is the reason ``projects/`` (the charter register, mounted at ``/projects/projects/``)
does not collide with the app's own mount point.
"""
from .ProjectInitiation.Overview import urlpatterns as _pi_overview
from .ProjectInitiation.ProjectKickoffs import urlpatterns as _pi_kickoffs
from .ProjectInitiation.ProjectRequests import urlpatterns as _pi_projectrequests
from .ProjectInitiation.ProjectStakeholders import urlpatterns as _pi_projectstakeholders
from .ProjectInitiation.Projects import urlpatterns as _pi_projects
from .ProjectPlanningScheduling.ProjectMilestones import urlpatterns as _pp_milestones
from .ProjectPlanningScheduling.ProjectTasks import urlpatterns as _pp_tasks
from .ProjectPlanningScheduling.ScheduleBaselines import urlpatterns as _pp_baselines
from .ProjectPlanningScheduling.TaskDependencies import urlpatterns as _pp_dependencies
from .ResourceManagement.CapacityDemand import urlpatterns as _rm_capacitydemand
from .ResourceManagement.ResourceAllocations import urlpatterns as _rm_allocations
from .ResourceManagement.ResourceProfiles import urlpatterns as _rm_profiles
from .ResourceManagement.ResourceTimeEntries import urlpatterns as _rm_timeentries
from .CostManagement.BudgetRevisions import urlpatterns as _cm_budgetrevisions
from .CostManagement.CostControlAccounts import urlpatterns as _cm_controlaccounts
from .CostManagement.ProjectBudgetLines import urlpatterns as _cm_budgetlines
from .CostManagement.ProjectExpenses import urlpatterns as _cm_expenses
from .RiskManagement.IssueEscalations import urlpatterns as _rm_escalations
from .RiskManagement.ProjectIssues import urlpatterns as _rm_issues
from .RiskManagement.ProjectRisks import urlpatterns as _rm_risks
from .RiskManagement.RiskAnalysis import urlpatterns as _rm_riskanalysis
from .RiskManagement.RiskMonitoring import urlpatterns as _rm_riskmonitoring
from .RiskManagement.RiskResponseActions import urlpatterns as _rm_responses
from .QualityManagement.DeliverableInspections import urlpatterns as _qm_inspections
from .QualityManagement.QualityAcceptance import urlpatterns as _qm_acceptance
from .QualityManagement.QualityDefects import urlpatterns as _qm_defects
from .QualityManagement.QualityImprovement import urlpatterns as _qm_improvement
from .QualityManagement.QualityPlans import urlpatterns as _qm_plans
from .QualityManagement.QualityReviews import urlpatterns as _qm_reviews
from .ScopeRequirements.Requirements import urlpatterns as _sr_requirements
from .ScopeRequirements.ScopeChangeRequests import urlpatterns as _sr_changes
from .ScopeRequirements.ScopeItems import urlpatterns as _sr_items
from .ScopeRequirements.ScopeMatrix import urlpatterns as _sr_matrix
from .ScopeRequirements.ScopeVerifications import urlpatterns as _sr_verifications
from .TaskWorkManagement.GanttTimeline import urlpatterns as _tw_gantt
from .TaskWorkManagement.ProjectTasks import urlpatterns as _tw_tasks
from .TaskWorkManagement.TaskBlocks import urlpatterns as _tw_blocks
from .TaskWorkManagement.TaskBoard import urlpatterns as _tw_board
from .TaskWorkManagement.TaskChecklistItems import urlpatterns as _tw_checklistitems
from .TaskWorkManagement.TaskPriority import urlpatterns as _tw_priority
from .CollaborationCommunication.ActivityFeed import urlpatterns as _cc_activityfeed
from .CollaborationCommunication.ChannelMessages import urlpatterns as _cc_messages
from .CollaborationCommunication.Channels import urlpatterns as _cc_channels
from .CollaborationCommunication.DocumentShares import urlpatterns as _cc_shares
from .CollaborationCommunication.Meetings import urlpatterns as _cc_meetings
from .CollaborationCommunication.ProjectNotifications import urlpatterns as _cc_notifications
from .DocumentKnowledgeManagement.Documents import urlpatterns as _dk_documents
from .DocumentKnowledgeManagement.Knowledge import urlpatterns as _dk_knowledge
from .DocumentKnowledgeManagement.ProjectFolders import urlpatterns as _dk_folders
from .DocumentKnowledgeManagement.RepositoryOverview import urlpatterns as _dk_repository
from .DocumentKnowledgeManagement.RetentionBoard import urlpatterns as _dk_retention
from .DocumentKnowledgeManagement.Revisions import urlpatterns as _dk_revisions
from .DocumentKnowledgeManagement.Templates import urlpatterns as _dk_templates
from .TimeAttendanceTracking.ActivityCodes import urlpatterns as _ta_activitycodes
from .TimeAttendanceTracking.OvertimeRecords import urlpatterns as _ta_overtimerecords
from .TimeAttendanceTracking.OvertimeRules import urlpatterns as _ta_overtimerules
from .TimeAttendanceTracking.TimeCalendar import urlpatterns as _ta_calendar
from .TimeAttendanceTracking.UtilizationDashboard import urlpatterns as _ta_utilization
from .PortfolioProgramManagement.Portfolios import urlpatterns as _pfm_portfolios
from .PortfolioProgramManagement.Programs import urlpatterns as _pfm_programs
from .PortfolioProgramManagement.PortfolioInvestments import urlpatterns as _pfm_investments
from .PortfolioProgramManagement.ProgramDependencies import urlpatterns as _pfm_dependencies
from .PortfolioProgramManagement.PortfolioDashboard import urlpatterns as _pfm_dashboard
from .AgileScrumManagement.ProjectEpics import urlpatterns as _asm_epics
from .AgileScrumManagement.ProjectReleases import urlpatterns as _asm_releases
from .AgileScrumManagement.ReleaseRoadmap import urlpatterns as _asm_roadmap
from .AgileScrumManagement.SprintBacklog import urlpatterns as _asm_backlog
from .AgileScrumManagement.SprintExecution import urlpatterns as _asm_execution
from .AgileScrumManagement.SprintImpediments import urlpatterns as _asm_impediments
from .AgileScrumManagement.SprintRetrospectives import urlpatterns as _asm_retrospectives
from .AgileScrumManagement.Sprints import urlpatterns as _asm_sprints
from .AgileScrumManagement.VelocityReport import urlpatterns as _asm_velocity
from .ClientExternalCollaboration.ClientPortals import urlpatterns as _cec_portals
from .ClientExternalCollaboration.ClientFeedbacks import urlpatterns as _cec_feedbacks
from .ClientExternalCollaboration.StatementOfWorks import urlpatterns as _cec_sow
from .ClientExternalCollaboration.VendorHandoffs import urlpatterns as _cec_handoffs
from .ClientExternalCollaboration.ClientInvoices import urlpatterns as _cec_invoices
from .FinancialBillingManagement.RateCards import urlpatterns as _fbm_ratecards
from .FinancialBillingManagement.BillingRuns import urlpatterns as _fbm_billingruns
from .FinancialBillingManagement.RevenueSchedules import urlpatterns as _fbm_revenueschedules
from .FinancialBillingManagement.PaymentRecords import urlpatterns as _fbm_paymentrecords
from .FinancialBillingManagement.FinancialBoards import urlpatterns as _fbm_financialboards
from .ReportingBusinessIntelligence.ReportingHome import urlpatterns as _rbi_home
from .ReportingBusinessIntelligence.ProjectReports import urlpatterns as _rbi_reports
from .ReportingBusinessIntelligence.ReportRuns import urlpatterns as _rbi_runs
from .ReportingBusinessIntelligence.ProjectDashboards import urlpatterns as _rbi_dashboards
from .ReportingBusinessIntelligence.DashboardWidgets import urlpatterns as _rbi_widgets
from .WorkflowAutomation.WorkflowRules import urlpatterns as _wa_rules
from .WorkflowAutomation.ApprovalGates import urlpatterns as _wa_gates
from .WorkflowAutomation.RecurringTasks import urlpatterns as _wa_recurring
from .WorkflowAutomation.Webhooks import urlpatterns as _wa_webhooks
from .WorkflowAutomation.AutomationBoards import urlpatterns as _wa_boards

app_name = "projects"


urlpatterns = (

    _pi_overview
    + _pi_projectrequests
    + _pi_projects
    + _pi_projectstakeholders
    + _pi_kickoffs
    # 7.2 Project Planning & Scheduling — first segments (tasks/, dependencies/, milestones/,
    # baselines/) are disjoint literals from 7.1's, so the order below cannot shadow anything.
    + _pp_tasks
    + _pp_dependencies
    + _pp_milestones
    + _pp_baselines
    # 7.3 Resource Management — first segments (resource-profiles/, allocations/,
    # time-entries/, capacity-demand/) are disjoint literals from 7.1's and 7.2's.
    + _rm_profiles
    + _rm_allocations
    + _rm_timeentries
    + _rm_capacitydemand
    # 7.4 Cost & Budget Management — first segments (budgetlines/, revisions/,
    # controlaccounts/, expenses/) are disjoint literals from 7.1's, 7.2's and 7.3's.
    + _cm_budgetlines
    + _cm_controlaccounts
    + _cm_budgetrevisions
    + _cm_expenses
    # 7.5 Risk & Issue Management — first segments (risks/, responses/, issues/, escalations/,
    # risk-analysis/, risk-monitoring/) are disjoint literals from 7.1's–7.4's. The two computed
    # routes are literal too, so nothing here can shadow another module's namespace.
    + _rm_risks
    + _rm_responses
    + _rm_issues
    + _rm_escalations
    + _rm_riskanalysis
    + _rm_riskmonitoring
    # 7.6 Quality Management — first segments (quality-plans/, quality-reviews/, inspections/,
    # defects/, quality-improvement/, quality-acceptance/) are disjoint literals from 7.1's–7.5's
    # and 7.7's. The two computed routes are literal too, so nothing here can shadow another
    # module's namespace.
    + _qm_plans
    + _qm_reviews
    + _qm_inspections
    + _qm_defects
    + _qm_improvement
    + _qm_acceptance
    # 7.7 Scope & Requirements Management — first segments (requirements/, scope-items/,
    # scope-changes/, scope-verifications/, scope-matrix/) are disjoint literals from 7.1's–7.5's.
    + _sr_requirements
    + _sr_items
    + _sr_changes
    + _sr_verifications
    + _sr_matrix
    # 7.8 Task & Work Management — first segments (checklist-items/, blocks/, task-board/,
    # gantt-timeline/, task-priority/) are disjoint literals from 7.1's–7.7's. The execution
    # verbs deliberately SHARE 7.2's tasks/ segment (execute/start/complete/block/unblock are
    # leaf literals below an <int:pk>, and bulk-update/ is a literal the int converter cannot
    # capture), so no pattern here can shadow a 7.2 route or vice versa.
    + _tw_tasks
    + _tw_checklistitems
    + _tw_blocks
    + _tw_board
    + _tw_gantt
    + _tw_priority
    # 7.9 Collaboration & Communication — first segments (channels/, messages/, shared-documents/,
    # meetings/, agenda-items/, action-items/, notifications/, activity-feed/) are disjoint
    # literals from 7.1's–7.8's and from each other, so nothing here can shadow another module's
    # namespace. Within the notifications module `read-all/` is listed before `<int:pk>/` (a
    # literal first, per the app-wide rule — the int converter could not capture it anyway), and
    # the two child-add routes live as literal leaves below `meetings/<int:pk>/`.
    #
    # `_cc_activityfeed` was imported but NEVER concatenated here, which is why
    # `projects:activity_feed` raised NoReverseMatch and took the whole module overview page
    # (`/projects/`) down with it — three templates reverse that name. Its route is the disjoint
    # literal `activity-feed/`, so it can shadow nothing.
    + _cc_activityfeed
    + _cc_channels
    + _cc_messages
    + _cc_shares
    + _cc_meetings
    + _cc_notifications
    # 7.10 Document & Knowledge Management - first segments (doc-folders/, documents/,
    # document-revisions/, document-templates/, knowledge/, document-repository/,
    # document-retention/) are disjoint literals from 7.1's-7.9's and from each other, so nothing
    # here can shadow another module's namespace. Within knowledge/ the literal search/ precedes
    # the <int:pk>/ ones, and within document-revisions/ the literal compare/ does the same.
    + _dk_folders
    + _dk_documents
    + _dk_revisions
    + _dk_templates
    + _dk_knowledge
    + _dk_repository
    + _dk_retention
    # 7.11 Time & Attendance Tracking — first segments (activity-codes/, overtime-rules/,
    # overtime-records/, utilization/, time-calendar/) are disjoint literals from 7.1's–7.10's.
    + _ta_activitycodes
    + _ta_overtimerules
    + _ta_overtimerecords
    + _ta_utilization
    + _ta_calendar
    # 7.12 Portfolio & Program Management — first segments (portfolios/, programs/,
    # investments/, program-dependencies/, portfolio-dashboard/) are disjoint literals from
    # earlier sub-modules and from each other.
    + _pfm_portfolios
    + _pfm_programs
    + _pfm_investments
    + _pfm_dependencies
    + _pfm_dashboard
    # 7.13 Agile & Scrum Management — first segments (agile/sprints/, agile/epics/,
    # agile/releases/, agile/impediments/, agile/retrospectives/, agile/backlog/,
    # agile/execution/, agile/roadmap/, agile/velocity/) are prefixed with agile/ and
    # are completely disjoint literals from earlier sub-modules and from each other.
    + _asm_sprints
    + _asm_epics
    + _asm_releases
    + _asm_impediments
    + _asm_retrospectives
    + _asm_backlog
    + _asm_execution
    + _asm_roadmap
    + _asm_velocity
    # 7.14 Client & External Collaboration — first segments (client-portals/,
    # client-feedbacks/, statement-of-works/, vendor-handoffs/, client-invoices/)
    # are completely disjoint literals from earlier sub-modules and from each other.
    + _cec_portals
    + _cec_feedbacks
    + _cec_sow
    + _cec_handoffs
    + _cec_invoices
    # 7.15 Financial & Billing Management — first segments (rate-cards/,
    # billing-runs/, revenue-schedules/, payment-records/, financial-pnl/,
    # financial-variance/, ar-aging/, cash-flow-forecast/) are completely disjoint
    # literals from earlier sub-modules and from each other.
    + _fbm_ratecards
    + _fbm_billingruns
    + _fbm_revenueschedules
    + _fbm_paymentrecords
    + _fbm_financialboards
    # 7.16 Reporting & Business Intelligence — every route sits under the one first segment
    # `reporting/`, which no other sub-module in this package uses (grep-verified: `path("reporting`
    # appears nowhere outside this sub-module), so the block cannot shadow an earlier one. Within it
    # the order below is legibility, not precedence: each pattern carries its own trailing slash, so
    # `reporting/` cannot capture `reporting/library/` and `reporting/dashboards/<int:pk>/` cannot
    # capture `reporting/dashboards/<int:pk>/widgets/add/`.
    + _rbi_home
    + _rbi_reports
    + _rbi_runs
    + _rbi_dashboards
    + _rbi_widgets
    # 7.17 Workflow & Automation — first segments (rules/, gates/, recurring/,
    # webhooks/, automation/) are disjoint literals from earlier sub-modules and from each other.
    + _wa_rules
    + _wa_gates
    + _wa_recurring
    + _wa_webhooks
    + _wa_boards
)




