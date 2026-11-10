from apps.assets.urls.AssetCompliance.AssetComplianceAudits import urlpatterns as audit_patterns
from apps.assets.urls.AssetCompliance.AssetComplianceFrameworks import urlpatterns as framework_patterns
from apps.assets.urls.AssetCompliance.AssetComplianceIncidents import urlpatterns as incident_patterns
from apps.assets.urls.AssetCompliance.AssetPermitLicenses import urlpatterns as permit_patterns

urlpatterns = framework_patterns + audit_patterns + permit_patterns + incident_patterns
