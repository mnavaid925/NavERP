from django.urls import path

from apps.sales.views.Workspace import (
    opportunity_place,
    opportunity_unplace,
    opportunity_workspace_detail,
    opportunity_workspace_list,
)


urlpatterns = [
    path("opportunity/", opportunity_workspace_list, name="opportunity_workspace_list"),
    path(
        "opportunity/workspace/<int:opportunity_pk>/place/",
        opportunity_place,
        name="opportunity_place",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/unplace/",
        opportunity_unplace,
        name="opportunity_unplace",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/",
        opportunity_workspace_detail,
        name="opportunity_workspace_detail",
    ),
]
