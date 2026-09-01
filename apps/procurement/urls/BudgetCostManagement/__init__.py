"""6.15 Budget & Cost Management URL patterns — one module per views module.

``app_name`` is set once in ``apps/procurement/urls/__init__.py``; this package only concatenates
its five entity/page modules' ``urlpatterns``.

Five first segments are claimed by this sub-module, every one of them a new whole component
checked against the inventory in ``apps/procurement/urls/__init__.py``: ``budget-mappings/``,
``budget-availability/``, ``commitments/``, ``budget-variance/`` (with its literal ``export/``
child) and ``cost-forecasts/``. None is a prefix of any other segment in the app — Django
matches path components, not strings.

This app registers no greedy ``<str:…>`` converter anywhere, so there is no cross-module
shadowing surface to reason about.
"""
from .BudgetMappings import urlpatterns as _bcm_mappings
from .BudgetChecks import urlpatterns as _bcm_checks
from .CommitmentRegister import urlpatterns as _bcm_register
from .VarianceReport import urlpatterns as _bcm_variance
from .CostForecasts import urlpatterns as _bcm_forecasts


urlpatterns = [
    *_bcm_mappings,   # budget-mappings/ CRUD
    *_bcm_checks,     # budget-availability/ advisory checker
    *_bcm_register,   # commitments/ read-only register
    *_bcm_variance,   # budget-variance/ + export/
    *_bcm_forecasts,  # cost-forecasts/ frozen projections (no edit)
]
