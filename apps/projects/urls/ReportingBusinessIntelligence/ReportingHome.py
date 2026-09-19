"""Projects 7.16 Reporting & Business Intelligence — ReportingHome URLs (four GET pages).

No route in this module carries a converter, so nothing here can shadow a neighbour's pk route, and
the four literals are order-independent among themselves.
"""
from django.urls import path

from apps.projects.views.ReportingBusinessIntelligence import ReportingHome as views

urlpatterns = [
    path("reporting/", views.rbi_home, name="rbi_home"),
    path("reporting/library/", views.report_library, name="report_library"),
    path("reporting/standard/", views.report_standard, name="report_standard"),
    path("reporting/exec-pack/", views.exec_pack, name="exec_pack"),
]
