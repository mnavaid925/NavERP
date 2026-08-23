from .CountPrograms import urlpatterns as _st_countprograms
from .PhysicalInventories import urlpatterns as _st_physical
from .VarianceReport import urlpatterns as _st_variance

urlpatterns = [
    *_st_countprograms,
    *_st_physical,
    *_st_variance,
]
