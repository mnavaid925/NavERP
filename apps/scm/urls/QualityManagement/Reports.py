"""SCM 4.9 Quality Management — Certificate of Analysis routes (prefix ``coa/``).

The literal report page comes first; the two per-inspection actions sit under ``<int:pk>/``. The
``pk`` is a ``QualityInspection``, not a certificate: there is no certificate table — the
certificate IS the stamped inspection.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("coa/", views.coa_report, name="coa_report"),
    path("coa/<int:pk>/issue/", views.coa_issue, name="coa_issue"),
    path("coa/<int:pk>/print/", views.coa_print, name="coa_print"),
]
