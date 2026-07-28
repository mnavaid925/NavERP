"""SCM 4.9 Quality Management — QualityAudit routes (prefix ``quality-audits/``).

``quality-audits/``, not ``audits/``: the shorter segment reads as a system audit trail
(``core.AuditLog``) rather than a quality programme, and a future Module-0 audit-log page would
then have nowhere obvious to live.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("quality-audits/", views.qualityaudit_list, name="qualityaudit_list"),
    path("quality-audits/add/", views.qualityaudit_create, name="qualityaudit_create"),
    path("quality-audits/<int:pk>/", views.qualityaudit_detail, name="qualityaudit_detail"),
    path("quality-audits/<int:pk>/edit/", views.qualityaudit_edit, name="qualityaudit_edit"),
    path("quality-audits/<int:pk>/delete/", views.qualityaudit_delete,
         name="qualityaudit_delete"),
    path("quality-audits/<int:pk>/start/", views.qualityaudit_start, name="qualityaudit_start"),
    path("quality-audits/<int:pk>/complete/", views.qualityaudit_complete,
         name="qualityaudit_complete"),
    path("quality-audits/<int:pk>/close/", views.qualityaudit_close, name="qualityaudit_close"),
    path("quality-audits/<int:pk>/cancel/", views.qualityaudit_cancel,
         name="qualityaudit_cancel"),
    # The ONLY creator of NonConformance(source="audit") rows.
    path("quality-audits/<int:pk>/add-finding/", views.qualityaudit_add_finding,
         name="qualityaudit_add_finding"),
    path("quality-audits/<int:pk>/print/", views.qualityaudit_print, name="qualityaudit_print"),
]
