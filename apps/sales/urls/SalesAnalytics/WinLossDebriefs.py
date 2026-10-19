"""Sales 8.12 — URLs for `WinLossDebrief`."""
from django.urls import path

from apps.sales.views.SalesAnalytics import WinLossDebriefs as views

urlpatterns = [
    path("sales-analytics/win-loss-debriefs/", views.win_loss_debrief_list, name="win_loss_debrief_list"),
    path("sales-analytics/win-loss-debriefs/create/", views.win_loss_debrief_create, name="win_loss_debrief_create"),
    path("sales-analytics/win-loss-debriefs/<int:pk>/", views.win_loss_debrief_detail, name="win_loss_debrief_detail"),
    path("sales-analytics/win-loss-debriefs/<int:pk>/edit/", views.win_loss_debrief_edit, name="win_loss_debrief_edit"),
    path("sales-analytics/win-loss-debriefs/<int:pk>/delete/", views.win_loss_debrief_delete, name="win_loss_debrief_delete"),
]
