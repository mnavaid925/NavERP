from apps.quality.urls.ProcessValidation.CleaningValidations import (
    urlpatterns as cleaning_validations_urls,
)
from apps.quality.urls.ProcessValidation.ComputerSystemValidations import (
    urlpatterns as computer_system_validations_urls,
)
from apps.quality.urls.ProcessValidation.ProcessCapabilityStudies import (
    urlpatterns as process_capability_studies_urls,
)
from apps.quality.urls.ProcessValidation.ProcessValidationDashboard import (
    urlpatterns as process_validation_dashboard_urls,
)
from apps.quality.urls.ProcessValidation.ValidationProtocols import (
    urlpatterns as validation_protocols_urls,
)

urlpatterns = (
    process_validation_dashboard_urls
    + validation_protocols_urls
    + process_capability_studies_urls
    + computer_system_validations_urls
    + cleaning_validations_urls
)
