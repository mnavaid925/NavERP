from django.urls import path

from apps.ecommerce.views.Personalization import PersonalizationConsole as views

urlpatterns = [
    path(
        "personalization/console/",
        views.personalization_console,
        name="personalization_console",
    ),
    path(
        "personalization/console/simulate/",
        views.recommendation_simulate,
        name="recommendation_simulate",
    ),
]
