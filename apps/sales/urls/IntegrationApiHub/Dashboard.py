"""Sales 8.18 — Integration & API Hub Dashboard URL patterns."""
from django.urls import path

from apps.sales.views.IntegrationApiHub.Dashboard import (
    hub_dashboard,
    sic_bi_list,
    sic_communication_list,
    sic_erp_list,
    sic_esignature_list,
    sic_marketing_list,
)

urlpatterns = [
    path("hub/", hub_dashboard, name="integration_hub"),
    path("connectors/erp/", sic_erp_list, name="sic_erp_list"),
    path("connectors/marketing/", sic_marketing_list, name="sic_marketing_list"),
    path("connectors/communication/", sic_communication_list, name="sic_communication_list"),
    path("connectors/bi/", sic_bi_list, name="sic_bi_list"),
    path("connectors/esignature/", sic_esignature_list, name="sic_esignature_list"),
]
