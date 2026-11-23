from apps.documents.views.CollaborationSharing.CoauthorSessions import (
    coauthor_session_create,
    coauthor_session_delete,
    coauthor_session_detail,
    coauthor_session_edit,
    coauthor_session_heartbeat,
    coauthor_session_list,
)
from apps.documents.views.CollaborationSharing.CollaborationHub import (
    collaboration_hub,
)
from apps.documents.views.CollaborationSharing.DocumentActivities import (
    document_activity_detail,
    document_activity_list,
    document_activity_mark_all_read,
    document_activity_mark_read,
)
from apps.documents.views.CollaborationSharing.DocumentShares import (
    document_share_create,
    document_share_delete,
    document_share_detail,
    document_share_edit,
    document_share_list,
    document_share_revoke,
)
from apps.documents.views.CollaborationSharing.DocumentTasks import (
    document_task_create,
    document_task_delete,
    document_task_detail,
    document_task_edit,
    document_task_list,
    document_task_toggle_complete,
)
from apps.documents.views.CollaborationSharing.PublicShare import (
    public_share_download,
    public_share_preview,
)

__all__ = [
    "collaboration_hub",
    "public_share_preview",
    "public_share_download",
    "document_share_list",
    "document_share_detail",
    "document_share_create",
    "document_share_edit",
    "document_share_delete",
    "document_share_revoke",
    "coauthor_session_list",
    "coauthor_session_detail",
    "coauthor_session_create",
    "coauthor_session_edit",
    "coauthor_session_delete",
    "coauthor_session_heartbeat",
    "document_task_list",
    "document_task_detail",
    "document_task_create",
    "document_task_edit",
    "document_task_delete",
    "document_task_toggle_complete",
    "document_activity_list",
    "document_activity_detail",
    "document_activity_mark_read",
    "document_activity_mark_all_read",
]
