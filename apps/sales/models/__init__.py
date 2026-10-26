from ._base import TenantEventOwned, TenantNumbered, TenantOwned
from .LeadManagement.LeadScoreEvents import LeadScoreEvent
from .LeadManagement.LeadQualifications import LeadQualification
from .LeadManagement.LeadRoutingRules import LeadRoutingRule, validate_routing_conditions
from .LeadManagement.LeadNurtureEnrollments import LeadNurtureEnrollment
from .ContactAccountManagement.PartyEnrichment import PartyEnrichmentEvent, validate_enrichment_changes
from .ContactAccountManagement.AccountStakeholders import AccountStakeholder
from .ContactAccountManagement.AccountClassifications import AccountClassification
from .ContactAccountManagement.AccountPlans import AccountPlan
from .OpportunityPipeline.Pipelines import (
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
    _validate_pipeline_criteria,
)
from .OpportunityTeams.OpportunityTeams import OpportunityTeamMember
from .CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfile,
    OpportunityCompetitor,
)
from .OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityOutcome,
    WinLossReason,
)
from .SalesForecasting.ForecastPeriods import ForecastPeriod
from .SalesForecasting.ForecastSubmissions import ForecastSubmission
from .SalesForecasting.ForecastAdjustments import ForecastAdjustment
from .SalesForecasting.ForecastScenarios import ForecastScenario
from .QuoteProposalCPQ.CPQQuotes import CPQQuote
from .QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLine
from .QuoteProposalCPQ.ProductBundles import ProductBundleOption
from .QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRule
# 8.6 Order Management. These EXTEND scm.SalesOrder (owned by SCM 4.5) by FK — none of them
# is a second order master. See the package docstring for the full L36/L37 ruling.
from .OrderManagement.OrderAmendments import OrderAmendment, OrderAmendmentLine
from .OrderManagement.OrderHolds import OrderHold
from .OrderManagement.OrderValidationRules import OrderValidationRule
from .OrderManagement.RevenueSchedules import PerformanceObligation, RevenueSchedule

# 8.7 Territory & Quota Management. These EXTEND crm.Territory and crm.SalesQuota (both owned by
# CRM 1.2) by FK — none of them is a second territory or quota master. See the package docstring.
from .TerritoryQuotaManagement.AccountTerritoryAssignments import AccountTerritoryAssignment
from .TerritoryQuotaManagement.QuotaPlans import PLAN_PARAMETER_KEYS, QuotaPlan
from .TerritoryQuotaManagement.TerritoryMembers import TerritoryMember
from .TerritoryQuotaManagement.TerritoryRules import (
    TERRITORY_FIELDS,
    TerritoryRule,
    validate_territory_conditions,
)
# 8.8 Sales Activity & Task Management. These EXTEND the CRM 1.5 activity stack by FK or by
# generating into it — none is a second activity/task/calendar master. See the package docstring.
from .SalesActivityTaskManagement.ActivityTypes import ActivityType
from .SalesActivityTaskManagement.ActivityLogs import (
    AUTO_CAPTURE_SOURCES,
    CAPTURE_SOURCE_CHOICES,
    ActivityLog,
)
from .SalesActivityTaskManagement.TaskTemplates import TaskTemplate, TaskTemplateStep
from .SalesActivityTaskManagement.SalesPlanCycles import ActivityGoal, SalesPlanCycle

# 8.9 Sales Enablement. Extends 8.2 CompetitorProfile and CRM 1.5 CommunicationLog.
from .SalesEnablement.EnablementContents import EnablementContent
from .SalesEnablement.SalesPlaybooks import SalesPlaybook
from .SalesEnablement.SalesCertifications import SalesCertification
from .SalesEnablement.CoachingScorecards import CoachingScorecard

# 8.10 Incentive Compensation Management.
from .IncentiveCompensation.CommissionPlans import CommissionPlan
from .IncentiveCompensation.CommissionEarnings import CommissionEarning
from .IncentiveCompensation.CommissionStatements import CommissionStatement
from .IncentiveCompensation.CommissionAdjustments import CommissionAdjustment

# 8.11 Customer Success & Account Management.
from .CustomerSuccess.CustomerHealthScores import CustomerHealthScore
from .CustomerSuccess.CustomerRenewals import CustomerRenewal
from .CustomerSuccess.CustomerOnboardings import CustomerOnboarding
from .CustomerSuccess.CustomerBusinessReviews import CustomerBusinessReview
from .MarketingAlignment import (
    ATTRIBUTION_MODEL_CHOICES,
    ATTRIBUTION_STATUS_CHOICES,
    ENGAGEMENT_CHANNEL_CHOICES,
    ENGAGEMENT_TYPE_CHOICES,
    EVENT_STATUS_CHOICES,
    EVENT_TYPE_CHOICES,
    FOLLOWUP_STATUS_CHOICES,
    HANDOFF_SOURCE_CHOICES,
    HANDOFF_STATUS_CHOICES,
    REGISTRATION_SOURCE_CHOICES,
    REGISTRATION_STATUS_CHOICES,
    TOUCH_CHANNEL_CHOICES,
    TOUCH_POSITION_CHOICES,
    TOUCH_TYPE_CHOICES,
    AttributionTouchpoint,
    CampaignAttribution,
    ContentEngagement,
    EventRegistration,
    MarketingEvent,
    MqlHandoff,
)

# 8.12 Sales Analytics & Intelligence. These EXTEND the Sales 8.2 win/loss spine
# (WinLossReason / OpportunityOutcome) and the Sales 8.9 coaching rubric by FK, and they
# EXTEND the CRM opportunity / lead / territory / communication-log masters by FK. They
# declare NO reason, outcome, competitor, quota, currency, activity, report or coaching
# master of their own -- see the package docstring for the L36/L37 ruling.
from .SalesAnalytics import (
    DEBRIEF_STATUS_CHOICES,
    FEEDBACK_TEAM_CHOICES,
    FUNNEL_SCOPE_CHOICES,
    INTERVIEW_CHANNEL_CHOICES,
    SCORECARD_RATING_CHOICES,
    SCORECARD_STATUS_CHOICES,
    VELOCITY_STATUS_CHOICES,
    FunnelConversionRecord,
    RepPerformanceScorecard,
    StageVelocityAnalysis,
    WinLossDebrief,
)
# 8.14 Partner & Channel Management. These EXTEND core.Party, crm.Opportunity,
# crm.Territory and accounting.Currency -- none is a duplicate company or deal table.
from .PartnerChannel import (
    ChannelConflict,
    DealRegistration,
    JointAccountPlan,
    PartnerProfile,
)
# 8.15 Contract & Subscription Management. Reuses core.Party, sales.CPQQuote,
# scm.SalesOrder, accounting.Currency, core.Document, crm.DocTemplate, accounts.User.
# Commercial customer subscriptions (CSB-) separate from tenants.Subscription.
from .ContractSubscriptionManagement import (
    BILLING_CADENCE_CHOICES,
    CONTRACT_STATUS_CHOICES,
    CONTRACT_TYPE_CHOICES,
    OBLIGATION_STATUS_CHOICES,
    OBLIGATION_TYPE_CHOICES,
    PENALTY_STATUS_CHOICES,
    PRICING_MODEL_CHOICES,
    SUBSCRIPTION_STATUS_CHOICES,
    USAGE_STATUS_CHOICES,
    ContractObligation,
    CustomerContract,
    CustomerSubscription,
    UsageMeterRecord,
)
# 8.16 Mobile Sales. Reuses core.Party, core.Address, core.Document, accounts.User,
# crm.Opportunity, crm.CommunicationLog, sales.CPQQuote, sales.FieldSalesRoute.
from .MobileSales import (
    ALERT_TYPE_CHOICES,
    OPTIMIZATION_STATUS_CHOICES,
    PLATFORM_CHOICES,
    PUSH_STATUS_CHOICES,
    ROUTE_STATUS_CHOICES,
    SYNC_STATUS_CHOICES,
    URGENCY_CHOICES,
    VERIFICATION_STATUS_CHOICES,
    VISIT_OUTCOME_CHOICES,
    VISIT_PURPOSE_CHOICES,
    FieldCheckIn,
    FieldSalesRoute,
    MobileDealAlert,
    MobileDeviceSession,
)
# 8.17 Workflow & Process Automation. Reuses crm.Lead/Opportunity/Case/Territory,
# sales.CPQQuote/OrderHold/CustomerContract/QuoteApprovalRule/MobileDealAlert, scm.SalesOrder,
# accounts.User/Role, core.JobDefinition/NotificationRule/WorkflowDefinition.
from .WorkflowProcessAutomation import (
    PROCESS_NODE_TYPES,
    SAT_TO_MDA_ALERT_TYPE,
    TARGET_ENTITY_CHOICES,
    TARGET_KIND_CHOICES,
    SalesAlertTrigger,
    SalesApprovalDecision,
    SalesAssignmentRule,
    SalesProcessDefinition,
    validate_process_conditions,
    validate_process_nodes,
)

__all__ = [
    "TenantEventOwned", "TenantNumbered", "TenantOwned", "LeadScoreEvent",
    "LeadQualification", "LeadRoutingRule", "LeadNurtureEnrollment", "validate_routing_conditions",
    "PartyEnrichmentEvent", "validate_enrichment_changes", "AccountStakeholder",
    "AccountClassification", "AccountPlan",
    "Pipeline", "PipelineStage", "OpportunityPipelinePlacement", "_validate_pipeline_criteria",
    "OpportunityTeamMember",
    "CompetitorProfile", "OpportunityCompetitor",
    "WinLossReason", "OpportunityOutcome",
    "ForecastPeriod", "ForecastSubmission", "ForecastAdjustment", "ForecastScenario",
    "CPQQuote", "CPQQuoteLine", "ProductBundleOption", "QuoteApprovalRule",
    # 8.6 Order Management
    "OrderValidationRule", "OrderHold", "OrderAmendment", "OrderAmendmentLine",
    "RevenueSchedule", "PerformanceObligation",
    # 8.7 Territory & Quota Management
    "TerritoryRule", "TERRITORY_FIELDS", "validate_territory_conditions",
    "AccountTerritoryAssignment", "TerritoryMember", "QuotaPlan", "PLAN_PARAMETER_KEYS",
    # 8.8 Sales Activity & Task Management. These EXTEND the CRM 1.5 activity stack
    # (crm.CommunicationLog / crm.CrmTask / crm.CalendarEvent) by FK or by generating into it — none
    # of them is a second activity, task or calendar master. See the package docstring for L36/L37.
    "ActivityType", "ActivityLog", "CAPTURE_SOURCE_CHOICES", "AUTO_CAPTURE_SOURCES",
    "TaskTemplate", "TaskTemplateStep", "SalesPlanCycle", "ActivityGoal",
    # 8.9 Sales Enablement
    "EnablementContent", "SalesPlaybook", "SalesCertification", "CoachingScorecard",
    # 8.10 Incentive Compensation Management
    "CommissionPlan", "CommissionEarning", "CommissionStatement", "CommissionAdjustment",
    # 8.11 Customer Success & Account Management
    "CustomerHealthScore", "CustomerRenewal", "CustomerOnboarding", "CustomerBusinessReview",
    # 8.13 Marketing Alignment & Attribution. These EXTEND the CRM campaign / lead / opportunity
    # masters and the Sales 8.9 content master by FK -- none of them is a second campaign,
    # lead, opportunity, account or content master. See the package docstring for L36/L37.
    "AttributionTouchpoint", "CampaignAttribution", "MqlHandoff",
    "ContentEngagement", "MarketingEvent", "EventRegistration",
    "TOUCH_CHANNEL_CHOICES", "TOUCH_TYPE_CHOICES", "TOUCH_POSITION_CHOICES",
    "ATTRIBUTION_MODEL_CHOICES", "ATTRIBUTION_STATUS_CHOICES",
    "HANDOFF_STATUS_CHOICES", "HANDOFF_SOURCE_CHOICES",
    "ENGAGEMENT_TYPE_CHOICES", "ENGAGEMENT_CHANNEL_CHOICES",
    "EVENT_TYPE_CHOICES", "EVENT_STATUS_CHOICES",
    "REGISTRATION_STATUS_CHOICES", "REGISTRATION_SOURCE_CHOICES",
    "FOLLOWUP_STATUS_CHOICES",
    # 8.12 Sales Analytics & Intelligence
    "WinLossDebrief", "StageVelocityAnalysis",
    "FunnelConversionRecord", "RepPerformanceScorecard",
    "INTERVIEW_CHANNEL_CHOICES", "FEEDBACK_TEAM_CHOICES", "DEBRIEF_STATUS_CHOICES",
    "VELOCITY_STATUS_CHOICES", "FUNNEL_SCOPE_CHOICES",
    "SCORECARD_RATING_CHOICES", "SCORECARD_STATUS_CHOICES",
    # 8.14 Partner & Channel Management
    "PartnerProfile", "DealRegistration", "JointAccountPlan", "ChannelConflict",
    # 8.15 Contract & Subscription Management
    "CustomerContract", "CustomerSubscription", "UsageMeterRecord", "ContractObligation",
    "CONTRACT_TYPE_CHOICES", "CONTRACT_STATUS_CHOICES",
    "SUBSCRIPTION_STATUS_CHOICES", "PRICING_MODEL_CHOICES", "BILLING_CADENCE_CHOICES",
    "USAGE_STATUS_CHOICES", "OBLIGATION_TYPE_CHOICES", "OBLIGATION_STATUS_CHOICES",
    "PENALTY_STATUS_CHOICES",
    # 8.16 Mobile Sales
    "FieldSalesRoute", "FieldCheckIn", "MobileDeviceSession", "MobileDealAlert",
    "ROUTE_STATUS_CHOICES", "OPTIMIZATION_STATUS_CHOICES",
    "VERIFICATION_STATUS_CHOICES", "VISIT_PURPOSE_CHOICES", "VISIT_OUTCOME_CHOICES",
    "PLATFORM_CHOICES", "SYNC_STATUS_CHOICES",
    "ALERT_TYPE_CHOICES", "URGENCY_CHOICES", "PUSH_STATUS_CHOICES",
    # 8.17 Workflow & Process Automation
    "SalesProcessDefinition", "SalesAssignmentRule", "SalesApprovalDecision", "SalesAlertTrigger",
    "validate_process_conditions", "validate_process_nodes",
    "TARGET_ENTITY_CHOICES", "TARGET_KIND_CHOICES", "PROCESS_NODE_TYPES", "SAT_TO_MDA_ALERT_TYPE",
]





