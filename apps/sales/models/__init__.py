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
]


