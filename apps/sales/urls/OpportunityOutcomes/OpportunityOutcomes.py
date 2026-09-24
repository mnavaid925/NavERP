from django.urls import path

from apps.sales.views.OpportunityOutcomes.OpportunityOutcomes import (
    opportunity_transition,
    opportunity_win_loss_reason_create,
    opportunity_win_loss_reason_delete,
    opportunity_win_loss_reason_detail,
    opportunity_win_loss_reason_edit,
    opportunity_win_loss_reason_list,
)


urlpatterns = [
    path(
        "opportunity/win-loss-reasons/",
        opportunity_win_loss_reason_list,
        name="opportunity_win_loss_reason_list",
    ),
    path(
        "opportunity/win-loss-reasons/add/",
        opportunity_win_loss_reason_create,
        name="opportunity_win_loss_reason_create",
    ),
    path(
        "opportunity/workspace/<int:opportunity_pk>/transition/",
        opportunity_transition,
        name="opportunity_transition",
    ),
    path(
        "opportunity/win-loss-reasons/<int:pk>/edit/",
        opportunity_win_loss_reason_edit,
        name="opportunity_win_loss_reason_edit",
    ),
    path(
        "opportunity/win-loss-reasons/<int:pk>/delete/",
        opportunity_win_loss_reason_delete,
        name="opportunity_win_loss_reason_delete",
    ),
    path(
        "opportunity/win-loss-reasons/<int:pk>/",
        opportunity_win_loss_reason_detail,
        name="opportunity_win_loss_reason_detail",
    ),
]
