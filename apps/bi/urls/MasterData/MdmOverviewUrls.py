from django.urls import path
from apps.bi.views.MasterData import MdmOverviewViews as views

urlpatterns = [
    path("mdm/overview/", views.mdm_overview, name="mdm_overview"),
]
