"""SCM 4.9 Quality Management — NonConformance routes (prefix ``nonconformances/``).

``disposition/`` is the one route here that can write to the stock ledger; the rest change state
only. All seven verb routes sit under ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("nonconformances/", views.nonconformance_list, name="nonconformance_list"),
    path("nonconformances/add/", views.nonconformance_create, name="nonconformance_create"),
    path("nonconformances/<int:pk>/", views.nonconformance_detail, name="nonconformance_detail"),
    path("nonconformances/<int:pk>/edit/", views.nonconformance_edit,
         name="nonconformance_edit"),
    path("nonconformances/<int:pk>/delete/", views.nonconformance_delete,
         name="nonconformance_delete"),
    path("nonconformances/<int:pk>/investigate/", views.nonconformance_investigate,
         name="nonconformance_investigate"),
    # Lot status — posts NO StockMove (ruling (b)).
    path("nonconformances/<int:pk>/quarantine/", views.nonconformance_quarantine,
         name="nonconformance_quarantine"),
    path("nonconformances/<int:pk>/release-lot/", views.nonconformance_release_lot,
         name="nonconformance_release_lot"),
    # The MRB decision — the ONE action in 4.9 that can post to the ledger.
    path("nonconformances/<int:pk>/disposition/", views.nonconformance_disposition,
         name="nonconformance_disposition"),
    path("nonconformances/<int:pk>/close/", views.nonconformance_close,
         name="nonconformance_close"),
    path("nonconformances/<int:pk>/cancel/", views.nonconformance_cancel,
         name="nonconformance_cancel"),
    path("nonconformances/<int:pk>/raise-capa/", views.nonconformance_raise_capa,
         name="nonconformance_raise_capa"),
]
