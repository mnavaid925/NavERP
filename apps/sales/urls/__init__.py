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
from .SalesForecasting.ForecastPeriods import urlpatterns as _forecast_periods
from .SalesForecasting.ForecastSubmissions import urlpatterns as _forecast_submissions
from .SalesForecasting.ForecastAdjustments import urlpatterns as _forecast_adjustments
from .SalesForecasting.ForecastScenarios import urlpatterns as _forecast_scenarios
from .OpportunityPipeline.Pipelines import urlpatterns as _pipelines
from .OpportunityTeams.OpportunityTeams import urlpatterns as _teams
from .CompetitiveIntelligence.CompetitiveIntelligence import urlpatterns as _competitors
from .OpportunityOutcomes.OpportunityOutcomes import urlpatterns as _outcomes
from .Workspace.Workspace import urlpatterns as _workspace

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
    # 8.4 Sales Forecasting. Placed after the 8.3 boards and before the 8.2 pipelines per
    # contract 5.6. Every group starts with the distinct literal segment `forecast/` and no
    # sales route is a `<str:...>` catch-all, so the position cannot shadow anything.
    *_forecast_periods,
    *_forecast_submissions,
    *_forecast_adjustments,
    *_forecast_scenarios,
    *_pipelines,
    *_teams,
    *_competitors,
    *_outcomes,
    *_workspace,
]

