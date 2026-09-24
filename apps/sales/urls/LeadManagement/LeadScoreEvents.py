from django.urls import path

from apps.sales import views


urlpatterns = [
    path("score-events/", views.lead_score_event_list, name="lead_score_event_list"),
    path("score-events/adjust/", views.lead_score_event_adjust, name="lead_score_event_adjust"),
    path("score-events/recompute/", views.lead_score_event_recompute, name="lead_score_event_recompute"),
    path("score-events/<int:pk>/", views.lead_score_event_detail, name="lead_score_event_detail"),
    path("score-events/<int:pk>/correct/", views.lead_score_event_correct, name="lead_score_event_correct"),
]
