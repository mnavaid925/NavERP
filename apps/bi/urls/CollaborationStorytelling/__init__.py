from apps.bi.urls.CollaborationStorytelling.BiDataStories import urlpatterns as story_urls
from apps.bi.urls.CollaborationStorytelling.BiDecisionLogs import urlpatterns as decision_urls
from apps.bi.urls.CollaborationStorytelling.BiSharedWorkspaces import urlpatterns as workspace_urls
from apps.bi.urls.CollaborationStorytelling.BiVisualComments import urlpatterns as comment_urls

urlpatterns = workspace_urls + story_urls + comment_urls + decision_urls
