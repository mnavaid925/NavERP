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
)
