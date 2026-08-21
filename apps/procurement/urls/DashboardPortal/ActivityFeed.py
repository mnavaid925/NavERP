"""Procurement 6.1 User Dashboard & Portal — Recent Activity Feed routes (prefix ``activity/``)."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("activity/", views.activity_list, name="activity_list"),
    path("activity/<int:pk>/", views.activity_detail, name="activity_detail"),
]
