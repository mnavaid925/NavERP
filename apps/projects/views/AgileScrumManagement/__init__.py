"""Projects 7.13 Agile & Scrum Management views package."""
from .ProjectEpics import epc_create, epc_delete, epc_detail, epc_edit, epc_list
from .ProjectReleases import (
    rel_create,
    rel_delete,
    rel_detail,
    rel_edit,
    rel_list,
    rel_publish,
)
from .ReleaseRoadmap import release_roadmap
from .SprintBacklog import sprint_backlog
from .SprintExecution import sprint_execution
from .SprintImpediments import (
    imp_create,
    imp_delete,
    imp_detail,
    imp_edit,
    imp_list,
    imp_resolve,
)
from .SprintRetrospectives import (
    ret_close,
    ret_create,
    ret_delete,
    ret_detail,
    ret_edit,
    ret_list,
    ret_open,
)
from .Sprints import (
    spt_cancel,
    spt_complete,
    spt_create,
    spt_delete,
    spt_detail,
    spt_edit,
    spt_list,
    spt_start,
)
from .VelocityReport import velocity_report

__all__ = [
    "spt_list",
    "spt_create",
    "spt_detail",
    "spt_edit",
    "spt_delete",
    "spt_start",
    "spt_complete",
    "spt_cancel",
    "epc_list",
    "epc_create",
    "epc_detail",
    "epc_edit",
    "epc_delete",
    "rel_list",
    "rel_create",
    "rel_detail",
    "rel_edit",
    "rel_delete",
    "rel_publish",
    "imp_list",
    "imp_create",
    "imp_detail",
    "imp_edit",
    "imp_delete",
    "imp_resolve",
    "ret_list",
    "ret_create",
    "ret_detail",
    "ret_edit",
    "ret_delete",
    "ret_open",
    "ret_close",
    "sprint_backlog",
    "sprint_execution",
    "release_roadmap",
    "velocity_report",
]
