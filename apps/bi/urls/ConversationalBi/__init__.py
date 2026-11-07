from apps.bi.urls.ConversationalBi.BiConversationSessions import urlpatterns as conversation_urls
from apps.bi.urls.ConversationalBi.NarrativeExplanations import urlpatterns as narrative_urls
from apps.bi.urls.ConversationalBi.NaturalLanguageQueries import urlpatterns as nlq_urls
from apps.bi.urls.ConversationalBi.SearchDiscoveryIndexes import urlpatterns as discovery_urls

urlpatterns = nlq_urls + conversation_urls + narrative_urls + discovery_urls
