from django.urls import path

from apps.ecommerce.views.Personalization import ShopperBehaviorEvents as views

urlpatterns = [
    path(
        "personalization/events/",
        views.shopperbehaviorevent_list,
        name="shopperbehaviorevent_list",
    ),
    path(
        "personalization/events/<int:pk>/",
        views.shopperbehaviorevent_detail,
        name="shopperbehaviorevent_detail",
    ),
    path(
        "personalization/events/<int:pk>/delete/",
        views.shopperbehaviorevent_delete,
        name="shopperbehaviorevent_delete",
    ),
]
