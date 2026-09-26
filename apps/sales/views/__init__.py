from .LeadManagement.Overview import lead_handoff, lead_overview
from .LeadManagement.LeadScoreEvents import (
    lead_score_event_adjust,
    lead_score_event_correct,
    lead_score_event_detail,
    lead_score_event_list,
    lead_score_event_recompute,
)
from .LeadManagement.LeadQualifications import (
    lead_qualification_archive,
    lead_qualification_create,
    lead_qualification_delete,
    lead_qualification_detail,
    lead_qualification_disqualify,
    lead_qualification_edit,
    lead_qualification_list,
    lead_qualification_partial,
    lead_qualification_qualify,
    lead_qualification_recalculate,
    lead_qualification_route_preview,
)
from .LeadManagement.LeadRoutingRules import (
    lead_routing_rule_create,
    lead_routing_rule_delete,
    lead_routing_rule_detail,
    lead_routing_rule_edit,
    lead_routing_rule_list,
    lead_routing_rule_preview,
    lead_routing_rule_run,
    lead_routing_rule_toggle,
)
from .LeadManagement.LeadNurtureEnrollments import (
    lead_nurture_enrollment_activate,
    lead_nurture_enrollment_cancel,
    lead_nurture_enrollment_complete,
    lead_nurture_enrollment_convert_exit,
    lead_nurture_enrollment_create,
    lead_nurture_enrollment_delete,
    lead_nurture_enrollment_detail,
    lead_nurture_enrollment_edit,
    lead_nurture_enrollment_list,
    lead_nurture_enrollment_pause,
    lead_nurture_enrollment_reply,
    lead_nurture_enrollment_resume,
)
from .ContactAccountManagement.PartyEnrichment import (
    party_enrichment_apply,
    party_enrichment_detail,
    party_enrichment_export,
    party_enrichment_list,
    party_enrichment_reject,
    party_enrichment_request,
)
from .ContactAccountManagement.AccountStakeholders import (
    account_stakeholder_create,
    account_stakeholder_delete,
    account_stakeholder_detail,
    account_stakeholder_edit,
    account_stakeholder_export,
    account_stakeholder_list,
)
from .ContactAccountManagement.AccountClassifications import (
    account_classification_create,
    account_classification_delete,
    account_classification_detail,
    account_classification_edit,
    account_classification_export,
    account_classification_list,
)
from .ContactAccountManagement.AccountPlans import (
    account_plan_activate,
    account_plan_archive,
    account_plan_complete,
    account_plan_create,
    account_plan_delete,
    account_plan_detail,
    account_plan_edit,
    account_plan_export,
    account_plan_list,
    account_plan_review_due,
)
from .ContactAccountManagement.AccountBoards import (
    account_coverage,
    account_hierarchy,
    account_white_space,
    account_workspace,
    account_workspace_export,
)
from .OpportunityPipeline.Pipelines import (
    opportunity_pipeline_board,
    opportunity_pipeline_create,
    opportunity_pipeline_delete,
    opportunity_pipeline_detail,
    opportunity_pipeline_edit,
    opportunity_pipeline_list,
    opportunity_pipeline_set_default,
    opportunity_pipeline_stage_create,
    opportunity_pipeline_stage_delete,
    opportunity_pipeline_stage_edit,
    opportunity_pipeline_stage_reorder,
    opportunity_pipeline_stages,
    opportunity_pipeline_visibility,
)
from .OpportunityTeams.OpportunityTeams import (
    opportunity_team_member_add,
    opportunity_team_member_edit,
    opportunity_team_member_remove,
)
from .CompetitiveIntelligence.CompetitiveIntelligence import (
    opportunity_competitor_link_add,
    opportunity_competitor_link_edit,
    opportunity_competitor_link_remove,
    opportunity_competitor_profile_create,
    opportunity_competitor_profile_delete,
    opportunity_competitor_profile_detail,
    opportunity_competitor_profile_edit,
    opportunity_competitor_profile_list,
)
from .OpportunityOutcomes.OpportunityOutcomes import (
    opportunity_transition,
    opportunity_win_loss_reason_create,
    opportunity_win_loss_reason_delete,
    opportunity_win_loss_reason_detail,
    opportunity_win_loss_reason_edit,
    opportunity_win_loss_reason_list,
)
from .SalesForecasting.ForecastBoards import (
    forecast_accuracy,
    forecast_attainment,
    forecast_board,
    forecast_call,
)
from .SalesForecasting.ForecastPeriods import (
    forecast_period_create,
    forecast_period_delete,
    forecast_period_detail,
    forecast_period_edit,
    forecast_period_export,
    forecast_period_list,
    forecast_period_lock,
    forecast_period_unlock,
)
from .SalesForecasting.ForecastSubmissions import (
    forecast_submission_approve,
    forecast_submission_create,
    forecast_submission_delete,
    forecast_submission_detail,
    forecast_submission_edit,
    forecast_submission_export,
    forecast_submission_list,
    forecast_submission_reject,
    forecast_submission_submit,
)
from .SalesForecasting.ForecastAdjustments import (
    forecast_adjustment_create,
    forecast_adjustment_delete,
    forecast_adjustment_detail,
    forecast_adjustment_edit,
    forecast_adjustment_export,
    forecast_adjustment_list,
    forecast_adjustment_revert,
)
from .SalesForecasting.ForecastScenarios import (
    forecast_scenario_apply,
    forecast_scenario_create,
    forecast_scenario_delete,
    forecast_scenario_detail,
    forecast_scenario_edit,
    forecast_scenario_list,
    forecast_scenario_select,
)
from .Workspace import (
    opportunity_place,
    opportunity_unplace,
    opportunity_workspace_detail,
    opportunity_workspace_list,
)
from .QuoteProposalCPQ import *

# View functions exported for URLconf routing and external imports
__all__ = [
    name for name in globals()
    if name.startswith((
        "lead_", "party_enrichment_", "account_", "opportunity_",
        "forecast_", "cpq_", "quote_", "product_bundle_"
    ))
]


