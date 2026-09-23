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
    rte_relog,
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

# --- 7.9 Collaboration & Communication ---------------------------------------------------------
# The channel register with its archive toggle, the message register with the mention-to-
# notification trigger, the share register with revoke plus the single-editor claim pair, the
# meeting register with its three lifecycle verbs and minutes capture (plus the two child
# registers' CRUD and tick verbs, all of which land back on the meeting), the notification inbox
# with its two read verbs, and the merged activity feed. 40 routes across six modules.
from .CollaborationCommunication.ActivityFeed import activity_feed  # noqa: F401
from .CollaborationCommunication.ChannelMessages import (  # noqa: F401
    msg_create,
    msg_delete,
    msg_edit,
    msg_list,
)
from .CollaborationCommunication.Channels import (  # noqa: F401
    chn_archive,
    chn_create,
    chn_delete,
    chn_detail,
    chn_edit,
    chn_list,
)
from .CollaborationCommunication.DocumentShares import (  # noqa: F401
    dsh_claim,
    dsh_create,
    dsh_delete,
    dsh_detail,
    dsh_edit,
    dsh_list,
    dsh_release,
    dsh_revoke,
)
from .CollaborationCommunication.Meetings import (  # noqa: F401
    agi_cover,
    agi_create,
    agi_delete,
    agi_edit,
    mai_create,
    mai_delete,
    mai_edit,
    mai_toggle,
    mtg_cancel,
    mtg_complete,
    mtg_create,
    mtg_delete,
    mtg_detail,
    mtg_edit,
    mtg_list,
    mtg_minutes,
    mtg_start,
)
from .CollaborationCommunication.ProjectNotifications import (  # noqa: F401
    ntf_delete,
    ntf_detail,
    ntf_list,
    ntf_mark_all_read,
    ntf_mark_read,
)

# --- 7.10 Document & Knowledge Management -------------------------------------------------------
# Absolute imports (the package rule): one module per entity plus the two computed pages. The
# revision views carry the chain's ONLY writers (upload/approve/restore/delete) and the document
# views carry the five life-cycle verbs (checkout/checkin/archive/hold/release) plus the re-index.
from .DocumentKnowledgeManagement.Documents import (  # noqa: F401
    pdm_archive,
    pdm_checkin,
    pdm_checkout,
    pdm_create,
    pdm_delete,
    pdm_detail,
    pdm_edit,
    pdm_hold,
    pdm_list,
    pdm_release,
    pdm_reindex,
)
from .DocumentKnowledgeManagement.Knowledge import (  # noqa: F401
    kne_create,
    kne_delete,
    kne_detail,
    kne_edit,
    kne_list,
    kne_publish,
    kne_search,
    kne_use,
)
from .DocumentKnowledgeManagement.ProjectFolders import (  # noqa: F401
    pfd_archive,
    pfd_create,
    pfd_delete,
    pfd_detail,
    pfd_edit,
    pfd_list,
)
from .DocumentKnowledgeManagement.RepositoryOverview import doc_repository  # noqa: F401
from .DocumentKnowledgeManagement.RetentionBoard import (  # noqa: F401
    doc_retention,
    doc_retention_run,
)
from .DocumentKnowledgeManagement.Revisions import (  # noqa: F401
    pdv_approve,
    pdv_compare,
    pdv_delete,
    pdv_list,
    pdv_restore,
    pdv_upload,
)
from .DocumentKnowledgeManagement.Templates import (  # noqa: F401
    dtm_create,
    dtm_delete,
    dtm_detail,
    dtm_edit,
    dtm_list,
    dtm_publish,
)

# --- 7.11 Time & Attendance Tracking ------------------------------------------------------------
from .TimeAttendanceTracking.ActivityCodes import (  # noqa: F401
    tac_create,
    tac_delete,
    tac_detail,
    tac_edit,
    tac_list,
)
from .TimeAttendanceTracking.OvertimeRecords import (  # noqa: F401
    pot_approve,
    pot_create,
    pot_delete,
    pot_detail,
    pot_edit,
    pot_list,
    pot_reject,
    pot_submit,
)
from .TimeAttendanceTracking.OvertimeRules import (  # noqa: F401
    otr_create,
    otr_delete,
    otr_detail,
    otr_edit,
    otr_list,
)
from .TimeAttendanceTracking.TimeCalendar import time_calendar  # noqa: F401
from .TimeAttendanceTracking.UtilizationDashboard import utilization_dashboard  # noqa: F401

# --- 7.12 Portfolio & Program Management --------------------------------------------------------
from .PortfolioProgramManagement.Portfolios import (  # noqa: F401
    prt_create,
    prt_delete,
    prt_detail,
    prt_edit,
    prt_list,
)
from .PortfolioProgramManagement.Programs import (  # noqa: F401
    pgm_create,
    pgm_delete,
    pgm_detail,
    pgm_edit,
    pgm_list,
)
from .PortfolioProgramManagement.PortfolioInvestments import (  # noqa: F401
    pin_create,
    pin_defer,
    pin_delete,
    pin_detail,
    pin_edit,
    pin_fund,
    pin_list,
    pin_reject,
)
from .PortfolioProgramManagement.ProgramDependencies import (  # noqa: F401
    pdep_clear,
    pdep_create,
    pdep_delete,
    pdep_detail,
    pdep_edit,
    pdep_list,
    pdep_reopen,
)
from .PortfolioProgramManagement.PortfolioDashboard import pfm_dashboard  # noqa: F401

# --- 7.13 Agile & Scrum Management --------------------------------------------------------------
from .AgileScrumManagement.ProjectEpics import (  # noqa: F401
    epc_create,
    epc_delete,
    epc_detail,
    epc_edit,
    epc_list,
)
from .AgileScrumManagement.ProjectReleases import (  # noqa: F401
    rel_create,
    rel_delete,
    rel_detail,
    rel_edit,
    rel_list,
    rel_publish,
)
from .AgileScrumManagement.ReleaseRoadmap import release_roadmap  # noqa: F401
from .AgileScrumManagement.SprintBacklog import sprint_backlog  # noqa: F401
from .AgileScrumManagement.SprintExecution import sprint_execution  # noqa: F401
from .AgileScrumManagement.SprintImpediments import (  # noqa: F401
    imp_create,
    imp_delete,
    imp_detail,
    imp_edit,
    imp_list,
    imp_resolve,
)
from .AgileScrumManagement.SprintRetrospectives import (  # noqa: F401
    ret_close,
    ret_create,
    ret_delete,
    ret_detail,
    ret_edit,
    ret_list,
    ret_open,
)
from .AgileScrumManagement.Sprints import (  # noqa: F401
    spt_cancel,
    spt_complete,
    spt_create,
    spt_delete,
    spt_detail,
    spt_edit,
    spt_list,
    spt_start,
)
from .AgileScrumManagement.VelocityReport import velocity_report  # noqa: F401

# --- 7.14 Client & External Collaboration -------------------------------------------------------
from .ClientExternalCollaboration.ClientPortals import (  # noqa: F401
    cpa_create,
    cpa_delete,
    cpa_detail,
    cpa_edit,
    cpa_list,
)
from .ClientExternalCollaboration.ClientFeedbacks import (  # noqa: F401
    cfb_approve,
    cfb_create,
    cfb_delete,
    cfb_detail,
    cfb_edit,
    cfb_list,
    cfb_reject,
)
from .ClientExternalCollaboration.StatementOfWorks import (  # noqa: F401
    sow_activate,
    sow_amendment_create,
    sow_create,
    sow_delete,
    sow_detail,
    sow_edit,
    sow_list,
)
from .ClientExternalCollaboration.VendorHandoffs import (  # noqa: F401
    vhd_accept,
    vhd_create,
    vhd_delete,
    vhd_detail,
    vhd_edit,
    vhd_list,
    vhd_reject,
)
from .ClientExternalCollaboration.ClientInvoices import (  # noqa: F401
    pci_create,
    pci_delete,
    pci_detail,
    pci_edit,
    pci_generate_invoice,
    pci_list,
)

# --- 7.15 Financial & Billing Management --------------------------------------------------------
from .FinancialBillingManagement.RateCards import (  # noqa: F401
    rtc_create,
    rtc_delete,
    rtc_detail,
    rtc_edit,
    rtc_list,
)
from .FinancialBillingManagement.BillingRuns import (  # noqa: F401
    pbr_approve,
    pbr_create,
    pbr_delete,
    pbr_detail,
    pbr_dispatch,
    pbr_edit,
    pbr_generate_invoice,
    pbr_list,
    pbr_preview_pdf,
)
from .FinancialBillingManagement.RevenueSchedules import (  # noqa: F401
    prs_approve,
    prs_create,
    prs_delete,
    prs_detail,
    prs_edit,
    prs_list,
    prs_lock,
    prs_recognize,
)
from .FinancialBillingManagement.PaymentRecords import (  # noqa: F401
    ppr_create,
    ppr_delete,
    ppr_detail,
    ppr_edit,
    ppr_escalate,
    ppr_list,
    ppr_log_contact,
    ppr_record_promise,
    ppr_resolve,
)
from .FinancialBillingManagement.FinancialBoards import (  # noqa: F401
    ar_aging,
    cash_flow_forecast,
    financial_pnl,
    financial_variance,
)

# --- 7.17 Workflow & Automation -----------------------------------------------------------------
from .WorkflowAutomation.WorkflowRules import (  # noqa: F401
    pwf_list,
    pwf_detail,
    pwf_create,
    pwf_edit,
    pwf_delete,
    pwf_toggle_active,
    pwf_test_run,
    pwf_execute_now,
)
from .WorkflowAutomation.ApprovalGates import (  # noqa: F401
    par_list,
    par_detail,
    par_create,
    par_edit,
    par_delete,
    par_approve,
    par_reject,
    par_escalate,
    par_delegate,
    par_cancel,
)
from .WorkflowAutomation.RecurringTasks import (  # noqa: F401
    rts_list,
    rts_detail,
    rts_create,
    rts_edit,
    rts_delete,
    rts_toggle_active,
    rts_generate_task,
    rts_skip_next,
)
from .WorkflowAutomation.Webhooks import (  # noqa: F401
    pwh_list,
    pwh_detail,
    pwh_create,
    pwh_edit,
    pwh_delete,
    pwh_toggle_active,
    pwh_test_ping,
    pwh_rotate_secret,
    pwh_delivery_list,
    pwh_delivery_detail,
)
from .WorkflowAutomation.AutomationBoards import (  # noqa: F401
    automation_overview,
    approval_inbox,
    recurrence_calendar,
    webhook_diagnostics,
)

# --- 7.16 Reporting & Business Intelligence --------------------------------------
from .ReportingBusinessIntelligence.ReportingHome import (  # noqa: F401
    rbi_home,
    report_library,
    report_standard,
    exec_pack,
)
from .ReportingBusinessIntelligence.ProjectReports import (  # noqa: F401
    rep_list,
    rep_create,
    rep_edit,
    rep_detail,
    rep_delete,
    rep_run,
    rep_freeze,
    rep_favorite,
    rep_csv,
    rep_json,
)
from .ReportingBusinessIntelligence.ReportRuns import (  # noqa: F401
    run_list,
    run_detail,
    run_narrative,
    run_issue,
    run_archive,
    run_delete,
    run_csv,
)
from .ReportingBusinessIntelligence.ProjectDashboards import (  # noqa: F401
    pdb_home,
    pdb_list,
    pdb_detail,
    pdb_create,
    pdb_edit,
    pdb_delete,
)
from .ReportingBusinessIntelligence.DashboardWidgets import (  # noqa: F401
    wdg_create,
    wdg_edit,
    wdg_delete,
    wdg_move,
)

# --- 7.18 Integration & API Hub -------------------------------------------------
from .IntegrationApiHub.Connectors import (  # noqa: F401
    ixc_list,
    ixc_detail,
    ixc_create,
    ixc_edit,
    ixc_delete,
    ixc_rotate_credential,
    ixc_test,
    ixc_toggle_active,
    connector_health,
)
from .IntegrationApiHub.FieldMappings import (  # noqa: F401
    ixm_list,
    ixm_detail,
    ixm_create,
    ixm_edit,
    ixm_delete,
)
from .IntegrationApiHub.SyncJobs import (  # noqa: F401
    syj_list,
    syj_detail,
    syj_create,
    syj_edit,
    syj_delete,
    syj_run,
    syj_toggle_active,
)
from .IntegrationApiHub.SyncRuns import (  # noqa: F401
    syr_list,
    syr_detail,
    syr_retry,
)
from .IntegrationApiHub.HubBoards import (  # noqa: F401
    integration_hub,
    sync_monitor,
)

# --- 7.19 Master Data & Configuration -------------------------------------------
from .MasterDataConfiguration.ProjectTemplates import (  # noqa: F401
    ptm_list,
    ptm_create,
    ptm_detail,
    ptm_edit,
    ptm_delete,
    ptm_instantiate,
)
from .MasterDataConfiguration.ProjectCustomFields import (  # noqa: F401
    pcf_list,
    pcf_create,
    pcf_detail,
    pcf_edit,
    pcf_delete,
)
from .MasterDataConfiguration.ProjectTeams import (  # noqa: F401
    pte_list,
    pte_create,
    pte_detail,
    pte_edit,
    pte_delete,
    pte_add_member,
    pte_remove_member,
)
from .MasterDataConfiguration.ProjectLocaleSettings import (  # noqa: F401
    pls_list,
    pls_create,
    pls_detail,
    pls_edit,
    pls_delete,
    pls_set_default,
)
from .MasterDataConfiguration.ConfigurationHub import (  # noqa: F401
    configuration_hub,
)


