from django.urls import path

from apps.bi.views.CollaborationStorytelling import BiDecisionLogs as views

urlpatterns = [
    path("decisions/", views.bi_decision_log_list, name="bi_decision_log_list"),
    path("decisions/create/", views.bi_decision_log_create, name="bi_decision_log_create"),
    path("decisions/<int:pk>/", views.bi_decision_log_detail, name="bi_decision_log_detail"),
    path("decisions/<int:pk>/edit/", views.bi_decision_log_edit, name="bi_decision_log_edit"),
    path("decisions/<int:pk>/delete/", views.bi_decision_log_delete, name="bi_decision_log_delete"),
]
