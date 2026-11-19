from django.urls import path

from apps.quality.views.AuditManagement.AuditActionTracker import audit_action_tracker

urlpatterns = [
    path("audits/action-tracker/", audit_action_tracker, name="audit_action_tracker"),
]
