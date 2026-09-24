from django.urls import path

from apps.sales.views.OpportunityTeams.OpportunityTeams import (
    opportunity_team_member_add,
    opportunity_team_member_edit,
    opportunity_team_member_remove,
)

urlpatterns = [
    path(
        "opportunity/workspace/<int:opportunity_pk>/team/add/",
        opportunity_team_member_add,
        name="opportunity_team_member_add",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/team/<int:member_pk>/edit/",
        opportunity_team_member_edit,
        name="opportunity_team_member_edit",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/team/<int:member_pk>/remove/",
        opportunity_team_member_remove,
        name="opportunity_team_member_remove",
    ),
]
