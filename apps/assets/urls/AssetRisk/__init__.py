from apps.assets.urls.AssetRisk.AssetBusinessContinuityPlans import urlpatterns as continuity_patterns
from apps.assets.urls.AssetRisk.AssetCyberSecurityProfiles import urlpatterns as cyber_patterns
from apps.assets.urls.AssetRisk.AssetRiskMitigationActions import urlpatterns as mitigation_patterns
from apps.assets.urls.AssetRisk.AssetRiskRegisters import urlpatterns as risk_patterns

urlpatterns = risk_patterns + continuity_patterns + cyber_patterns + mitigation_patterns
