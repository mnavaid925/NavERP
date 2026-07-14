"""CRM 1.5 Activity & Communication Management — CommunicationLogs URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Communication logs (1.5 Email & Call Integration — calls + email/BCC sync)
    path("comms/", views.communicationlog_list, name="communicationlog_list"),
    path("comms/add/", views.communicationlog_create, name="communicationlog_create"),
    path("comms/<int:pk>/", views.communicationlog_detail, name="communicationlog_detail"),
    path("comms/<int:pk>/edit/", views.communicationlog_edit, name="communicationlog_edit"),
    path("comms/<int:pk>/delete/", views.communicationlog_delete, name="communicationlog_delete"),
]
