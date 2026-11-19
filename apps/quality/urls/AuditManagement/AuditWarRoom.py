from django.urls import path

from apps.quality.views.AuditManagement.AuditWarRoom import audit_war_room

urlpatterns = [
    path("audits/war-room/", audit_war_room, name="audit_war_room"),
]
