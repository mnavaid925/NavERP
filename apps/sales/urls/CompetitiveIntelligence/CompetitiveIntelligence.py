from django.urls import path

from apps.sales.views.CompetitiveIntelligence.CompetitiveIntelligence import (
    opportunity_competitor_link_add,
    opportunity_competitor_link_edit,
    opportunity_competitor_link_remove,
    opportunity_competitor_profile_create,
    opportunity_competitor_profile_delete,
    opportunity_competitor_profile_detail,
    opportunity_competitor_profile_edit,
    opportunity_competitor_profile_list,
)


urlpatterns = [
    path(
        "opportunity/competitors/",
        opportunity_competitor_profile_list,
        name="opportunity_competitor_profile_list",
    ),
    path(
        "opportunity/competitors/add/",
        opportunity_competitor_profile_create,
        name="opportunity_competitor_profile_create",
    ),
    path(
        "opportunity/competitors/<int:pk>/",
        opportunity_competitor_profile_detail,
        name="opportunity_competitor_profile_detail",
    ),
    path(
        "opportunity/competitors/<int:pk>/edit/",
        opportunity_competitor_profile_edit,
        name="opportunity_competitor_profile_edit",
    ),
    path(
        "opportunity/competitors/<int:pk>/delete/",
        opportunity_competitor_profile_delete,
        name="opportunity_competitor_profile_delete",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/competitors/add/",
        opportunity_competitor_link_add,
        name="opportunity_competitor_link_add",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/competitors/<int:competitor_pk>/edit/",
        opportunity_competitor_link_edit,
        name="opportunity_competitor_link_edit",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/competitors/<int:competitor_pk>/remove/",
        opportunity_competitor_link_remove,
        name="opportunity_competitor_link_remove",
    ),
]
