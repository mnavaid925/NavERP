"""Projects 7.6 — QualityReview routes (prefix ``quality-reviews/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``quality-reviews/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("quality-reviews/", views.qrv_list, name="qrv_list"),
    path("quality-reviews/add/", views.qrv_create, name="qrv_create"),
    path("quality-reviews/<int:pk>/", views.qrv_detail, name="qrv_detail"),
    path("quality-reviews/<int:pk>/edit/", views.qrv_edit, name="qrv_edit"),
    path("quality-reviews/<int:pk>/delete/", views.qrv_delete, name="qrv_delete"),
    path("quality-reviews/<int:pk>/report/", views.qrv_report, name="qrv_report"),
    path("quality-reviews/<int:pk>/close/", views.qrv_close, name="qrv_close"),
]
