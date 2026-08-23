"""Inventory ReturnsManagement URL patterns package (Sub-module 5.10)."""
from .DispositionRoutingRules import urlpatterns as _dispositionrules
from .ReturnInspections import urlpatterns as _inspections
from .ReturnsWorkbench import urlpatterns as _workbench

urlpatterns = [
    *_workbench,
    *_inspections,
    *_dispositionrules,
]
