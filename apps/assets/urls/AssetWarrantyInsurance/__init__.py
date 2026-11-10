from apps.assets.urls.AssetWarrantyInsurance.AssetInsuranceClaims import urlpatterns as insurance_claims_urls
from apps.assets.urls.AssetWarrantyInsurance.AssetInsurancePolicies import urlpatterns as insurance_policies_urls
from apps.assets.urls.AssetWarrantyInsurance.AssetWarranties import urlpatterns as warranties_urls
from apps.assets.urls.AssetWarrantyInsurance.AssetWarrantyClaims import urlpatterns as warranty_claims_urls

urlpatterns = (
    warranties_urls
    + warranty_claims_urls
    + insurance_policies_urls
    + insurance_claims_urls
)

__all__ = ["urlpatterns"]
