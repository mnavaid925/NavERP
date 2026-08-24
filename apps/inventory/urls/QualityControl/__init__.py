"""Inventory QualityControl URL patterns package (Sub-module 5.15)."""
from .DefectReports import urlpatterns as _defectreports
from .QcChecklists import urlpatterns as _qcchecklists
from .QcRoutingRules import urlpatterns as _qcroutingrules
from .QuarantineOrders import urlpatterns as _quarantineorders

urlpatterns = [
    *_qcchecklists,
    *_qcroutingrules,
    *_quarantineorders,
    *_defectreports,
]
