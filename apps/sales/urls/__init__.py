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
    *_pipelines,
    *_teams,
    *_competitors,
    *_outcomes,
    *_workspace,
]

