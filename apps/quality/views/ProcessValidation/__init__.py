from apps.quality.views.ProcessValidation.CleaningValidations import (
    cleaning_validation_create,
    cleaning_validation_delete,
    cleaning_validation_detail,
    cleaning_validation_edit,
    cleaning_validation_export,
    cleaning_validation_list,
)
from apps.quality.views.ProcessValidation.ComputerSystemValidations import (
    computer_system_validation_create,
    computer_system_validation_delete,
    computer_system_validation_detail,
    computer_system_validation_edit,
    computer_system_validation_export,
    computer_system_validation_list,
)
from apps.quality.views.ProcessValidation.ProcessCapabilityStudies import (
    process_capability_study_create,
    process_capability_study_delete,
    process_capability_study_detail,
    process_capability_study_edit,
    process_capability_study_export,
    process_capability_study_list,
)
from apps.quality.views.ProcessValidation.ProcessValidationDashboard import (
    process_validation_dashboard,
)
from apps.quality.views.ProcessValidation.ValidationProtocols import (
    validation_protocol_create,
    validation_protocol_delete,
    validation_protocol_detail,
    validation_protocol_edit,
    validation_protocol_export,
    validation_protocol_list,
)

__all__ = [
    "cleaning_validation_create",
    "cleaning_validation_delete",
    "cleaning_validation_detail",
    "cleaning_validation_edit",
    "cleaning_validation_export",
    "cleaning_validation_list",
    "computer_system_validation_create",
    "computer_system_validation_delete",
    "computer_system_validation_detail",
    "computer_system_validation_edit",
    "computer_system_validation_export",
    "computer_system_validation_list",
    "process_capability_study_create",
    "process_capability_study_delete",
    "process_capability_study_detail",
    "process_capability_study_edit",
    "process_capability_study_export",
    "process_capability_study_list",
    "process_validation_dashboard",
    "validation_protocol_create",
    "validation_protocol_delete",
    "validation_protocol_detail",
    "validation_protocol_edit",
    "validation_protocol_export",
    "validation_protocol_list",
]
