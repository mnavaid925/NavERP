"""Inventory 5.18 Accounting & Financial Integration — views.

Re-exports every view so ``views.<name>`` resolves from the URLconf.
"""
from .APSync import ap_sync, ap_sync_run
from .ARSync import ar_sync, ar_sync_run
from .GLPostRules import (
    glpostrule_create,
    glpostrule_delete,
    glpostrule_detail,
    glpostrule_edit,
    glpostrule_list,
)
from .JEAutomation import je_automation, je_post_adjustment, je_post_cogs
from .TaxRules import (
    taxrule_create,
    taxrule_delete,
    taxrule_detail,
    taxrule_edit,
    taxrule_list,
)

__all__ = [
    "ap_sync", "ap_sync_run",
    "ar_sync", "ar_sync_run",
    "je_automation", "je_post_adjustment", "je_post_cogs",
    "taxrule_list", "taxrule_detail", "taxrule_create", "taxrule_edit", "taxrule_delete",
    "glpostrule_list", "glpostrule_detail", "glpostrule_create",
    "glpostrule_edit", "glpostrule_delete",
]
