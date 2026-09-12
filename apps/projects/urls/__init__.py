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
)
