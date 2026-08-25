"""Inventory 5.18 Accounting & Financial Integration — URL re-exports."""
from .GLPostRules import urlpatterns as _fin_glpostrules
from .JEAutomation import urlpatterns as _fin_jeautomation
from .TaxRules import urlpatterns as _fin_taxrules

urlpatterns = [
    *_fin_taxrules,      # TaxRule CRUD
    *_fin_glpostrules,   # GLPostRule CRUD
    *_fin_jeautomation,  # AP/AR sync queues + JE automation board & verbs
]

__all__ = ["urlpatterns"]
