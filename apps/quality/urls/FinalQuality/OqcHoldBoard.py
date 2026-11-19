from django.urls import path

from apps.quality.views.FinalQuality import OqcHoldBoard as views

urlpatterns = [
    path("hold-and-release-board/", views.oqc_hold_board, name="oqc_hold_board"),
]
