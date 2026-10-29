from django.urls import path

from apps.ecommerce.views.Personalization import RecommendationStrategies as views

urlpatterns = [
    path(
        "personalization/strategies/",
        views.recommendationstrategy_list,
        name="recommendationstrategy_list",
    ),
    path(
        "personalization/strategies/create/",
        views.recommendationstrategy_create,
        name="recommendationstrategy_create",
    ),
    path(
        "personalization/strategies/<int:pk>/",
        views.recommendationstrategy_detail,
        name="recommendationstrategy_detail",
    ),
    path(
        "personalization/strategies/<int:pk>/edit/",
        views.recommendationstrategy_edit,
        name="recommendationstrategy_edit",
    ),
    path(
        "personalization/strategies/<int:pk>/delete/",
        views.recommendationstrategy_delete,
        name="recommendationstrategy_delete",
    ),
    path(
        "personalization/strategies/<int:pk>/toggle/",
        views.recommendationstrategy_toggle,
        name="recommendationstrategy_toggle",
    ),
]
