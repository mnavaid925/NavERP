from .AssetBuildingSystems import urlpatterns as building_system_urlpatterns
from .AssetFacilitySpaces import urlpatterns as facility_space_urlpatterns
from .AssetFurnitureFixtures import urlpatterns as furniture_fixture_urlpatterns
from .AssetSpaceChargebacks import urlpatterns as space_chargeback_urlpatterns
from .InfrastructureBoard import urlpatterns as infrastructure_board_urlpatterns

urlpatterns = (
    facility_space_urlpatterns
    + building_system_urlpatterns
    + infrastructure_board_urlpatterns
    + furniture_fixture_urlpatterns
    + space_chargeback_urlpatterns
)
