from apps.quality.urls.CapaManagement.CapaActions import (
    urlpatterns as capa_actions_urls,
)
from apps.quality.urls.CapaManagement.CapaEffectivenessReviews import (
    urlpatterns as capa_effectiveness_reviews_urls,
)
from apps.quality.urls.CapaManagement.CapaInvestigations import (
    urlpatterns as capa_investigations_urls,
)
from apps.quality.urls.CapaManagement.CapaTrackingBoard import (
    urlpatterns as capa_tracking_board_urls,
)
from apps.quality.urls.CapaManagement.RootCauseAnalyses import (
    urlpatterns as root_cause_analyses_urls,
)
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
from apps.quality.urls.NonConformance.MrbDispositions import (
    urlpatterns as mrb_dispositions_urls,
)
from apps.quality.urls.NonConformance.NcrAnalytics import (
    urlpatterns as ncr_analytics_urls,
)
from apps.quality.urls.NonConformance.NonConformanceReports import (
    urlpatterns as non_conformance_reports_urls,
)
from apps.quality.urls.NonConformance.ProcessDeviations import (
    urlpatterns as process_deviations_urls,
)
from apps.quality.urls.NonConformance.QuarantineContainments import (
    urlpatterns as quarantine_containments_urls,
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
    + capa_investigations_urls
    + root_cause_analyses_urls
    + capa_actions_urls
    + capa_effectiveness_reviews_urls
    + capa_tracking_board_urls
    + non_conformance_reports_urls
    + quarantine_containments_urls
    + mrb_dispositions_urls
    + process_deviations_urls
    + ncr_analytics_urls
)

