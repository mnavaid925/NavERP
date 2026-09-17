from django.urls import path
from apps.projects import views

urlpatterns = [
    path("time-calendar/", views.time_calendar, name="time_calendar"),
]
