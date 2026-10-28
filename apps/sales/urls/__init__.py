from .LeadManagement.Overview import urlpatterns as _overview
from .LeadManagement.LeadScoreEvents import urlpatterns as _score_events
from .LeadManagement.LeadQualifications import urlpatterns as _qualifications
from .LeadManagement.LeadRoutingRules import urlpatterns as _routing_rules
from .LeadManagement.LeadNurtureEnrollments import urlpatterns as _nurture
from .ContactAccountManagement.PartyEnrichment import urlpatterns as _enrichment
from .ContactAccountManagement.AccountStakeholders import urlpatterns as _stakeholders
from .ContactAccountManagement.AccountClassifications import urlpatterns as _classifications
from .ContactAccountManagement.AccountPlans import urlpatterns as _plans
from .ContactAccountManagement.AccountBoards import urlpatterns as _boards
from .SalesForecasting.ForecastBoards import urlpatterns as _forecast_boards
from .SalesForecasting.ForecastPeriods import urlpatterns as _forecast_periods
from .SalesForecasting.ForecastSubmissions import urlpatterns as _forecast_submissions
from .SalesForecasting.ForecastAdjustments import urlpatterns as _forecast_adjustments
from .SalesForecasting.ForecastScenarios import urlpatterns as _forecast_scenarios
from .OpportunityPipeline.Pipelines import urlpatterns as _pipelines
from .OpportunityTeams.OpportunityTeams import urlpatterns as _teams
from .CompetitiveIntelligence.CompetitiveIntelligence import urlpatterns as _competitors
from .OpportunityOutcomes.OpportunityOutcomes import urlpatterns as _outcomes
from .Workspace.Workspace import urlpatterns as _workspace
from .QuoteProposalCPQ import urlpatterns as _quote_cpq
# 8.6 Order Management. The `orders/` prefix was verified free against every prefix already
# mounted under `sales:`, and board_patterns is spliced in FIRST inside the package because it
# carries the literal routes (Django resolves first-match-wins).
from .OrderManagement import urlpatterns as _order_management
# 8.7 Territory & Quota Management. Extends crm.Territory and crm.SalesQuota by FK.
from .TerritoryQuotaManagement import urlpatterns as _territory_quota
# 8.8 Sales Activity & Task Management. Extends the CRM 1.5 activity stack (crm.CommunicationLog /
# crm.CrmTask / crm.CalendarEvent) by FK or by generating into it; declares no second activity, task
# or calendar master.
#
# BOTH of the next two edits are required and neither is sufficient alone: the import here without
# the `+ _sales_activity` concatenation below is a complete no-op that still leaves `manage.py check`
# perfectly clean while every reverse() for these names raises NoReverseMatch (L54's second rule).
from .SalesActivityTaskManagement import urlpatterns as _sales_activity
# 8.9 Sales Enablement
from .SalesEnablement import urlpatterns as _sales_enablement
# 8.10 Incentive Compensation Management
from .IncentiveCompensation import urlpatterns as _incentive_compensation
# 8.11 Customer Success & Account Management
from .CustomerSuccess import urlpatterns as _customer_success
# 8.13 Marketing Alignment & Attribution. Extends crm.Campaign / crm.Lead / crm.Opportunity and
# sales.EnablementContent by FK; declares no second campaign, lead, opportunity or content master.
from .MarketingAlignment import urlpatterns as _marketing_alignment
# 8.12 Sales Analytics & Intelligence. Extends the Sales 8.2 win/loss spine and the CRM
# opportunity / lead / territory masters by FK; declares no second reason, outcome,
# competitor, quota, currency, activity or report master.
from .SalesAnalytics import urlpatterns as _sales_analytics
# 8.14 Partner & Channel Management.
from .PartnerChannel import urlpatterns as _partner_channel
# 8.15 Contract & Subscription Management.
from .ContractSubscriptionManagement import urlpatterns as _contract_subscription
# 8.16 Mobile Sales
from .MobileSales import urlpatterns as _mobile_sales
# 8.17 Workflow & Process Automation. Extends crm.Lead/Opportunity/Case/Territory,
# sales.CPQQuote/OrderHold/CustomerContract/QuoteApprovalRule/MobileDealAlert, scm.SalesOrder,
# accounts.User/Role, core.JobDefinition/NotificationRule by FK or as write targets; declares no
# second workflow registry, notification channel or approval gate.
from .WorkflowProcessAutomation import urlpatterns as _workflow_automation
# 8.18 Integration & API Hub (L55 Coexistence: 5th integration register across NavERP)
from .IntegrationApiHub import urlpatterns as _integration_api_hub
# 8.19 Master Data & Configuration
from .MasterDataConfiguration import urlpatterns as _master_data_config

app_name = "sales"

urlpatterns = [
    *_overview,
    *_score_events,
    *_qualifications,
    *_routing_rules,
    *_nurture,
    *_enrichment,
    *_stakeholders,
    *_classifications,
    *_plans,
    *_boards,
    # 8.4 Sales Forecasting.
    *_forecast_boards,
    *_forecast_periods,
    *_forecast_submissions,
    *_forecast_adjustments,
    *_forecast_scenarios,
    # 8.5 Quote & Proposal Management (CPQ).
    *_quote_cpq,
    # 8.6 Order Management.
    *_order_management,
    # 8.7 Territory & Quota Management.
    *_territory_quota,
    # 8.8 Sales Activity & Task Management.
    *_sales_activity,
    # 8.9 Sales Enablement.
    *_sales_enablement,
    # 8.10 Incentive Compensation Management.
    *_incentive_compensation,
    # 8.11 Customer Success & Account Management.
    *_customer_success,
    # 8.13 Marketing Alignment & Attribution.
    *_marketing_alignment,
    # 8.12 Sales Analytics & Intelligence.
    *_sales_analytics,
    # 8.14 Partner & Channel Management.
    *_partner_channel,
    # 8.15 Contract & Subscription Management.
    *_contract_subscription,
    # 8.16 Mobile Sales.
    *_mobile_sales,
    # 8.17 Workflow & Process Automation.
    *_workflow_automation,
    # 8.18 Integration & API Hub.
    *_integration_api_hub,
    # 8.19 Master Data & Configuration.
    *_master_data_config,
    *_pipelines,
    *_teams,
    *_competitors,
    *_outcomes,
    *_workspace,
]




