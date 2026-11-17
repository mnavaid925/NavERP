from django.urls import path

from apps.quality.views.RiskManagement.FmeaMatrix import (
    fmea_matrix,
    fmea_matrix_export,
    risk_traceability_matrix,
    risk_traceability_matrix_export,
)

urlpatterns = [
    path("risk-matrix/", fmea_matrix, name="fmea_matrix"),
    path("risk-matrix/export/", fmea_matrix_export, name="fmea_matrix_export"),
    path("risk-traceability/", risk_traceability_matrix, name="risk_traceability_matrix"),
    path("risk-traceability/export/", risk_traceability_matrix_export, name="risk_traceability_matrix_export"),
]
