"""Inventory QualityControl views package (Sub-module 5.15)."""
from .DefectReports import (
    defectreport_close,
    defectreport_create,
    defectreport_delete,
    defectreport_detail,
    defectreport_edit,
    defectreport_list,
    defectreport_writeoff,
)
from .QcChecklists import (
    qcchecklist_create,
    qcchecklist_delete,
    qcchecklist_detail,
    qcchecklist_edit,
    qcchecklist_list,
)
from .QcRoutingRules import (
    qcroutingrule_create,
    qcroutingrule_delete,
    qcroutingrule_detail,
    qcroutingrule_edit,
    qcroutingrule_list,
)
from .QuarantineOrders import (
    quarantineorder_cancel,
    quarantineorder_create,
    quarantineorder_delete,
    quarantineorder_detail,
    quarantineorder_edit,
    quarantineorder_list,
    quarantineorder_quarantine,
    quarantineorder_release,
    quarantineorder_scrap,
)

__all__ = [
    "defectreport_close",
    "defectreport_create",
    "defectreport_delete",
    "defectreport_detail",
    "defectreport_edit",
    "defectreport_list",
    "defectreport_writeoff",
    "qcchecklist_create",
    "qcchecklist_delete",
    "qcchecklist_detail",
    "qcchecklist_edit",
    "qcchecklist_list",
    "qcroutingrule_create",
    "qcroutingrule_delete",
    "qcroutingrule_detail",
    "qcroutingrule_edit",
    "qcroutingrule_list",
    "quarantineorder_cancel",
    "quarantineorder_create",
    "quarantineorder_delete",
    "quarantineorder_detail",
    "quarantineorder_edit",
    "quarantineorder_list",
    "quarantineorder_quarantine",
    "quarantineorder_release",
    "quarantineorder_scrap",
]
