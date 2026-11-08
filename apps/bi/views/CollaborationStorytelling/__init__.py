from apps.bi.views.CollaborationStorytelling.BiDataStories import (
    bi_data_story_create,
    bi_data_story_delete,
    bi_data_story_detail,
    bi_data_story_edit,
    bi_data_story_export_office,
    bi_data_story_list,
    bi_data_story_presentation,
)
from apps.bi.views.CollaborationStorytelling.BiDecisionLogs import (
    bi_decision_log_create,
    bi_decision_log_delete,
    bi_decision_log_detail,
    bi_decision_log_edit,
    bi_decision_log_list,
)
from apps.bi.views.CollaborationStorytelling.BiSharedWorkspaces import (
    bi_shared_workspace_create,
    bi_shared_workspace_delete,
    bi_shared_workspace_detail,
    bi_shared_workspace_edit,
    bi_shared_workspace_list,
)
from apps.bi.views.CollaborationStorytelling.BiVisualComments import (
    bi_visual_comment_create,
    bi_visual_comment_delete,
    bi_visual_comment_detail,
    bi_visual_comment_edit,
    bi_visual_comment_list,
    bi_visual_comment_resolve,
)

__all__ = [
    "bi_shared_workspace_list",
    "bi_shared_workspace_create",
    "bi_shared_workspace_detail",
    "bi_shared_workspace_edit",
    "bi_shared_workspace_delete",
    "bi_data_story_list",
    "bi_data_story_create",
    "bi_data_story_detail",
    "bi_data_story_edit",
    "bi_data_story_delete",
    "bi_data_story_presentation",
    "bi_data_story_export_office",
    "bi_visual_comment_list",
    "bi_visual_comment_create",
    "bi_visual_comment_detail",
    "bi_visual_comment_edit",
    "bi_visual_comment_delete",
    "bi_visual_comment_resolve",
    "bi_decision_log_list",
    "bi_decision_log_create",
    "bi_decision_log_detail",
    "bi_decision_log_edit",
    "bi_decision_log_delete",
]
