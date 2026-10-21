from apps.sales.urls.PartnerChannel.ChannelConflicts import urlpatterns as conflict_urls
from apps.sales.urls.PartnerChannel.DealRegistrations import urlpatterns as deal_urls
from apps.sales.urls.PartnerChannel.JointAccountPlans import urlpatterns as joint_plan_urls
from apps.sales.urls.PartnerChannel.PartnerProfiles import urlpatterns as partner_urls

urlpatterns = [
    *partner_urls,
    *deal_urls,
    *joint_plan_urls,
    *conflict_urls,
]
