"""Procurement 6.2 Requisition Management — models package.

One module per entity; the package __init__ re-exports every model. The requisition DOCUMENTS
themselves stay 4.1's ``scm.PurchaseRequisition`` (L36 — extend the spine, never re-declare it):
this sub-module adds the management layer AROUND that spine —

* ``RequisitionTemplate`` / ``RequisitionTemplateLine`` — reusable recurring-order blueprints that
  APPLY into a fresh ``scm.PurchaseRequisition`` draft;
* ``RequisitionAmendment`` / ``RequisitionAmendmentLine`` — the approve-gated change/cancel
  workflow for requisitions that are already past direct editing (scm only lets a draft or a
  still-pending one be edited in place).
"""
from .Amendments import RequisitionAmendment, RequisitionAmendmentLine
from .Templates import RequisitionTemplate, RequisitionTemplateLine

__all__ = [
    "RequisitionAmendment",
    "RequisitionAmendmentLine",
    "RequisitionTemplate",
    "RequisitionTemplateLine",
]
