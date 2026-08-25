from .UomCalculator import urlpatterns as _uom_calculator
from .UomConversions import urlpatterns as _uom_conversions

urlpatterns = [
    *_uom_conversions,
    *_uom_calculator,
]
