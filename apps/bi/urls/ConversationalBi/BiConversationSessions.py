from django.urls import path

from apps.bi.views.ConversationalBi import BiConversationSessions as views

urlpatterns = [
    path("conversations/", views.bi_conversation_session_list, name="bi_conversation_session_list"),
    path("conversations/workspace/", views.bi_chat_workspace, name="bi_chat_workspace"),
    path("conversations/create/", views.bi_conversation_session_create, name="bi_conversation_session_create"),
    path("conversations/<int:pk>/", views.bi_conversation_session_detail, name="bi_conversation_session_detail"),
    path("conversations/<int:pk>/edit/", views.bi_conversation_session_edit, name="bi_conversation_session_edit"),
    path("conversations/<int:pk>/delete/", views.bi_conversation_session_delete, name="bi_conversation_session_delete"),
    path("conversations/<int:pk>/toggle-pin/", views.bi_conversation_session_toggle_pin, name="bi_conversation_session_toggle_pin"),
    path("conversations/<int:pk>/close/", views.bi_conversation_session_close, name="bi_conversation_session_close"),
    path("conversations/<int:pk>/ask/", views.bi_conversation_session_ask, name="bi_conversation_session_ask"),
]
