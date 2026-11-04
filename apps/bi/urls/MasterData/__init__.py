from apps.bi.urls.MasterData.MdmGoldenRecordUrls import urlpatterns as golden_record_urls
from apps.bi.urls.MasterData.MdmHierarchyNodeUrls import urlpatterns as hierarchy_node_urls
from apps.bi.urls.MasterData.MdmOverviewUrls import urlpatterns as overview_urls
from apps.bi.urls.MasterData.MdmReferenceCodeUrls import urlpatterns as reference_code_urls
from apps.bi.urls.MasterData.MdmSurvivorshipRuleUrls import urlpatterns as survivorship_rule_urls

urlpatterns = (
    overview_urls
    + golden_record_urls
    + survivorship_rule_urls
    + hierarchy_node_urls
    + reference_code_urls
)

__all__ = ["urlpatterns"]
