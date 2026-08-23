"""Inventory ReturnsManagement views package (Sub-module 5.10)."""
from .DispositionRoutingRules import (
    dispositionrule_create,
    dispositionrule_delete,
    dispositionrule_detail,
    dispositionrule_edit,
    dispositionrule_list,
)
from .ReturnInspections import (
    returninspection_create,
    returninspection_delete,
    returninspection_detail,
    returninspection_edit,
    returninspection_list,
)
from .ReturnsWorkbench import returns_workbench

__all__ = [
    "returninspection_list",
    "returninspection_create",
    "returninspection_detail",
    "returninspection_edit",
    "returninspection_delete",
    "dispositionrule_list",
    "dispositionrule_create",
    "dispositionrule_detail",
    "dispositionrule_edit",
    "dispositionrule_delete",
    "returns_workbench",
]
