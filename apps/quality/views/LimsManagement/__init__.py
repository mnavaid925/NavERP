from apps.quality.views.LimsManagement.LabSamples import (
    lab_sample_create,
    lab_sample_delete,
    lab_sample_detail,
    lab_sample_edit,
    lab_sample_list,
    lab_sample_receive,
)
from apps.quality.views.LimsManagement.LabSpecifications import (
    lab_specification_create,
    lab_specification_delete,
    lab_specification_detail,
    lab_specification_edit,
    lab_specification_list,
)
from apps.quality.views.LimsManagement.LabTestWorksheets import (
    lab_test_worksheet_complete,
    lab_test_worksheet_create,
    lab_test_worksheet_delete,
    lab_test_worksheet_detail,
    lab_test_worksheet_edit,
    lab_test_worksheet_list,
)
from apps.quality.views.LimsManagement.LimsDashboard import (
    lims_dashboard,
    lims_export_csv,
)
from apps.quality.views.LimsManagement.OosInvestigations import (
    oos_investigation_close,
    oos_investigation_create,
    oos_investigation_delete,
    oos_investigation_detail,
    oos_investigation_edit,
    oos_investigation_list,
)

__all__ = [
    "lab_sample_create",
    "lab_sample_delete",
    "lab_sample_detail",
    "lab_sample_edit",
    "lab_sample_list",
    "lab_sample_receive",
    "lab_specification_create",
    "lab_specification_delete",
    "lab_specification_detail",
    "lab_specification_edit",
    "lab_specification_list",
    "lab_test_worksheet_complete",
    "lab_test_worksheet_create",
    "lab_test_worksheet_delete",
    "lab_test_worksheet_detail",
    "lab_test_worksheet_edit",
    "lab_test_worksheet_list",
    "lims_dashboard",
    "lims_export_csv",
    "oos_investigation_close",
    "oos_investigation_create",
    "oos_investigation_delete",
    "oos_investigation_detail",
    "oos_investigation_edit",
    "oos_investigation_list",
]
