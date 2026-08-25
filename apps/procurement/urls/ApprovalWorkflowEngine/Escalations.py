from django.urls import path

from apps.procurement import views

urlpatterns = [
    # The run verb is a LITERAL route — it must precede any <int:pk> pattern (none
    # exist here today, but the ordering discipline holds app-wide).
    path("escalations/", views.escalation_queue, name="escalation_queue"),
    path("escalations/run/", views.escalation_run, name="escalation_run"),
]
