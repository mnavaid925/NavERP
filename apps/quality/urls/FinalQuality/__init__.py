from apps.quality.urls.FinalQuality.CertificatesOfConformance import urlpatterns as coc_urls
from apps.quality.urls.FinalQuality.FinalInspectionLots import urlpatterns as fqc_urls
from apps.quality.urls.FinalQuality.OqcHoldBoard import urlpatterns as board_urls
from apps.quality.urls.FinalQuality.PackagingLabelVerifications import urlpatterns as pkg_urls
from apps.quality.urls.FinalQuality.QualityReleaseAuthorizations import urlpatterns as rel_urls

urlpatterns = fqc_urls + coc_urls + pkg_urls + rel_urls + board_urls
