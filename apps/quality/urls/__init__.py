from apps.quality.urls.DesignControls.DesignInputs import (
    urlpatterns as design_inputs_urls,
)
from apps.quality.urls.DesignControls.DesignProjects import (
    urlpatterns as design_projects_urls,
)
from apps.quality.urls.DesignControls.DesignReviews import (
    urlpatterns as design_reviews_urls,
)
from apps.quality.urls.DesignControls.DesignVerifications import (
    urlpatterns as design_verifications_urls,
)
from apps.quality.urls.DesignControls.TraceabilityMatrix import (
    urlpatterns as traceability_matrix_urls,
)
from apps.quality.urls.DocumentControl.ControlledDocuments import (
    urlpatterns as controlled_documents_urls,
)
from apps.quality.urls.DocumentControl.DocumentAcknowledgments import (
    urlpatterns as document_acknowledgments_urls,
)
from apps.quality.urls.DocumentControl.DocumentChangeOrders import (
    urlpatterns as document_change_orders_urls,
)
from apps.quality.urls.DocumentControl.ElectronicSignatures import (
    urlpatterns as electronic_signatures_urls,
)
from apps.quality.urls.RiskManagement.FmeaMatrix import (
    urlpatterns as fmea_matrix_urls,
)
from apps.quality.urls.RiskManagement.RiskAssessments import (
    urlpatterns as risk_assessments_urls,
)
from apps.quality.urls.RiskManagement.RiskControlMeasures import (
    urlpatterns as risk_control_measures_urls,
)
from apps.quality.urls.RiskManagement.RiskManagementPlans import (
    urlpatterns as risk_management_plans_urls,
)
from apps.quality.urls.RiskManagement.RiskReviewRecords import (
    urlpatterns as risk_review_records_urls,
)

app_name = "quality"

urlpatterns = (
    controlled_documents_urls
    + document_change_orders_urls
    + electronic_signatures_urls
    + document_acknowledgments_urls
    + design_projects_urls
    + design_inputs_urls
    + design_reviews_urls
    + design_verifications_urls
    + traceability_matrix_urls
    + risk_management_plans_urls
    + risk_assessments_urls
    + risk_control_measures_urls
    + risk_review_records_urls
    + fmea_matrix_urls
)

