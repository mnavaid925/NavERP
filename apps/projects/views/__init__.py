"""Views package for the projects app (NavERP Module 7 — Project Management).

One sub-package per NavERP sub-module, one module per entity, mirroring models/ forms/ urls/.
Entity modules do ``from apps.projects.views._common import *`` and the package __init__
re-exports every view, so the urls package resolves ``views.prq_list``.

Context-var contract (pinned, L7 — an unpinned name renders blank at 200):
  * list  -> ``object_list`` + ``page_obj`` + ``q`` (+ the view's filter choices)
  * detail/edit object -> ``obj``
  * form  -> ``form`` + ``is_edit``
The per-entity extras are frozen in ``.claude/tasks/contract-projects-7.1.md``.
"""
# --- 7.1 Project Initiation & Charter ---------------------------------------------------------
from .ProjectInitiation.Overview import overview  # noqa: F401
from .ProjectInitiation.ProjectKickoffs import (  # noqa: F401
    pko_complete,
    pko_create,
    pko_delete,
    pko_detail,
    pko_edit,
    pko_list,
    pko_mark_baseline_set,
    pko_mark_held,
    pko_schedule,
)
from .ProjectInitiation.ProjectRequests import (  # noqa: F401
    prq_approve,
    prq_convert,
    prq_create,
    prq_delete,
    prq_detail,
    prq_edit,
    prq_list,
    prq_reject,
    prq_return_for_information,
    prq_submit,
)
from .ProjectInitiation.ProjectStakeholders import (  # noqa: F401
    pst_create,
    pst_delete,
    pst_detail,
    pst_edit,
    pst_list,
)
from .ProjectInitiation.Projects import (  # noqa: F401
    prj_approve_charter,
    prj_create,
    prj_delete,
    prj_detail,
    prj_edit,
    prj_list,
    prj_submit_charter,
)

# --- 7.2 Project Planning & Scheduling --------------------------------------------------------
from .ProjectPlanningScheduling.ProjectMilestones import (  # noqa: F401
    mst_achieve,
    mst_create,
    mst_delete,
    mst_detail,
    mst_edit,
    mst_list,
)
from .ProjectPlanningScheduling.ProjectTasks import (  # noqa: F401
    tsk_create,
    tsk_delete,
    tsk_detail,
    tsk_edit,
    tsk_list,
    tsk_tree,
)
from .ProjectPlanningScheduling.ScheduleBaselines import (  # noqa: F401
    bsl_activate,
    bsl_create,
    bsl_delete,
    bsl_detail,
    bsl_edit,
    bsl_list,
    bsl_promote,
)
from .ProjectPlanningScheduling.TaskDependencies import (  # noqa: F401
    dep_create,
    dep_delete,
    dep_detail,
    dep_edit,
    dep_list,
)

# --- 7.3 Resource Management ------------------------------------------------------------------
from .ResourceManagement.CapacityDemand import capacity_demand  # noqa: F401
from .ResourceManagement.ResourceAllocations import (  # noqa: F401
    ral_assign,
    ral_cancel,
    ral_commit,
    ral_complete,
    ral_create,
    ral_delete,
    ral_detail,
    ral_edit,
    ral_list,
    ral_substitute,
)
from .ResourceManagement.ResourceProfiles import (  # noqa: F401
    rsp_create,
    rsp_delete,
    rsp_detail,
    rsp_edit,
    rsp_list,
)
from .ResourceManagement.ResourceTimeEntries import (  # noqa: F401
    rte_approve,
    rte_approve_week,
    rte_create,
    rte_delete,
    rte_detail,
    rte_edit,
    rte_list,
    rte_reject,
    rte_submit,
)

# --- 7.4 Cost & Budget Management -------------------------------------------------------------
from .CostManagement.BudgetRevisions import (  # noqa: F401
    bvr_activate,
    bvr_approve,
    bvr_create,
    bvr_delete,
    bvr_detail,
    bvr_edit,
    bvr_list,
    bvr_reject,
    bvr_submit,
)
from .CostManagement.CostControlAccounts import (  # noqa: F401
    cca_create,
    cca_delete,
    cca_detail,
    cca_edit,
    cca_list,
)
from .CostManagement.ProjectBudgetLines import (  # noqa: F401
    pbl_create,
    pbl_delete,
    pbl_detail,
    pbl_edit,
    pbl_list,
)
from .CostManagement.ProjectExpenses import (  # noqa: F401
    pex_create,
    pex_delete,
    pex_detail,
    pex_edit,
    pex_list,
    pex_post,
    pex_void,
)
