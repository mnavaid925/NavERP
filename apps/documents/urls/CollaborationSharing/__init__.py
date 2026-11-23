from apps.documents.urls.CollaborationSharing.CoauthorSessions import (
    urlpatterns as coauthor_sessions_urls,
)
from apps.documents.urls.CollaborationSharing.CollaborationHub import (
    urlpatterns as collaboration_hub_urls,
)
from apps.documents.urls.CollaborationSharing.DocumentActivities import (
    urlpatterns as document_activities_urls,
)
from apps.documents.urls.CollaborationSharing.DocumentShares import (
    urlpatterns as document_shares_urls,
)
from apps.documents.urls.CollaborationSharing.DocumentTasks import (
    urlpatterns as document_tasks_urls,
)
from apps.documents.urls.CollaborationSharing.PublicShare import (
    urlpatterns as public_share_urls,
)

urlpatterns = (
    collaboration_hub_urls
    + public_share_urls
    + document_shares_urls
    + coauthor_sessions_urls
    + document_tasks_urls
    + document_activities_urls
)
