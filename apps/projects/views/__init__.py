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

# --- 7.5 Risk & Issue Management --------------------------------------------------------------
# The four registers' CRUD sets, their seven lifecycle verbs (all POST-only, so a GET is a 405),
# and the two computed pages (no model — the 7.3 capacity_demand precedent).
from .RiskManagement.IssueEscalations import (  # noqa: F401
    esc_create,
    esc_delete,
    esc_detail,
    esc_edit,
    esc_list,
)
from .RiskManagement.ProjectIssues import (  # noqa: F401
    iss_close,
    iss_create,
    iss_delete,
    iss_detail,
    iss_edit,
    iss_escalate,
    iss_list,
    iss_resolve,
)
from .RiskManagement.ProjectRisks import (  # noqa: F401
    rsk_close,
    rsk_create,
    rsk_delete,
    rsk_detail,
    rsk_edit,
    rsk_list,
    rsk_realize,
    rsk_reopen,
)
from .RiskManagement.RiskAnalysis import risk_analysis  # noqa: F401
from .RiskManagement.RiskMonitoring import risk_monitoring  # noqa: F401
from .RiskManagement.RiskResponseActions import (  # noqa: F401
    rra_complete,
    rra_create,
    rra_delete,
    rra_detail,
    rra_edit,
    rra_list,
)

# --- 7.6 Quality Management -------------------------------------------------------------------
# The four registers' CRUD sets, their ten lifecycle verbs (all POST-only, so a GET is a 405),
# and the two computed pages (no model — the 7.3 capacity_demand / 7.5 risk_analysis precedent).
from .QualityManagement.DeliverableInspections import (  # noqa: F401
    qci_accept,
    qci_create,
    qci_delete,
    qci_detail,
    qci_edit,
    qci_list,
    qci_record,
    qci_reject,
)
from .QualityManagement.QualityAcceptance import quality_acceptance  # noqa: F401
from .QualityManagement.QualityDefects import (  # noqa: F401
    qdf_close,
    qdf_create,
    qdf_delete,
    qdf_detail,
    qdf_edit,
    qdf_list,
    qdf_raise_issue,
    qdf_resolve,
)
from .QualityManagement.QualityImprovement import quality_improvement  # noqa: F401
from .QualityManagement.QualityPlans import (  # noqa: F401
    qpl_approve,
    qpl_create,
    qpl_delete,
    qpl_detail,
    qpl_edit,
    qpl_list,
    qpl_supersede,
)
from .QualityManagement.QualityReviews import (  # noqa: F401
    qrv_close,
    qrv_create,
    qrv_delete,
    qrv_detail,
    qrv_edit,
    qrv_list,
    qrv_report,
)

# --- 7.7 Scope & Requirements Management ------------------------------------------------------
# The four registers' CRUD sets, their sixteen lifecycle verbs (all POST-only, so a GET is a 405),
# and the one computed page (the traceability matrix + creep board — no model, the 7.3
# capacity_demand / 7.5 risk_analysis precedent).
from .ScopeRequirements.Requirements import (  # noqa: F401
    req_approve,
    req_create,
    req_delete,
    req_detail,
    req_edit,
    req_implement,
    req_list,
    req_reject,
    req_submit,
    req_verify,
)
from .ScopeRequirements.ScopeChangeRequests import (  # noqa: F401
    scr_approve,
    scr_create,
    scr_delete,
    scr_detail,
    scr_edit,
    scr_implement,
    scr_list,
    scr_reject,
    scr_review,
    scr_submit,
)
from .ScopeRequirements.ScopeItems import (  # noqa: F401
    sci_create,
    sci_delete,
    sci_detail,
    sci_edit,
    sci_list,
    sci_realize,
    sci_retire,
    sci_validate,
)
from .ScopeRequirements.ScopeMatrix import scope_matrix  # noqa: F401
from .ScopeRequirements.ScopeVerifications import (  # noqa: F401
    svr_accept,
    svr_create,
    svr_delete,
    svr_detail,
    svr_edit,
    svr_list,
    svr_reject,
    svr_waive,
)

# --- 7.8 Task & Work Management ---------------------------------------------------------------
# The execution verb layer on ProjectTask (execute/start/complete/block/unblock + the bulk
# updater), the checklist register with its one-time tick toggle, the block evidence register
# (list/detail only — rows are minted and closed by verbs, never created from a page) and the
# three computed pages: the kanban board, the gantt timeline and the priority lens, all derived
# on read over the registers (the 7.5 boards ruling).
from .TaskWorkManagement.GanttTimeline import gantt_timeline  # noqa: F401
from .TaskWorkManagement.ProjectTasks import (  # noqa: F401
    tsk_block,
    tsk_bulk_update,
    tsk_complete,
    tsk_execute,
    tsk_start,
    tsk_unblock,
)
from .TaskWorkManagement.TaskBlocks import tbk_detail, tbk_list  # noqa: F401
from .TaskWorkManagement.TaskBoard import task_board  # noqa: F401
from .TaskWorkManagement.TaskChecklistItems import (  # noqa: F401
    tcl_check,
    tcl_create,
    tcl_delete,
    tcl_detail,
    tcl_edit,
    tcl_list,
)
from .TaskWorkManagement.TaskPriority import task_priority  # noqa: F401
