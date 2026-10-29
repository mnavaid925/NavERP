from django.urls import path

from apps.ecommerce.views.Personalization import PersonalizedExperiences as views

urlpatterns = [
    path(
        "personalization/experiences/",
        views.personalizedexperience_list,
        name="personalizedexperience_list",
    ),
    path(
        "personalization/experiences/create/",
        views.personalizedexperience_create,
        name="personalizedexperience_create",
    ),
    path(
        "personalization/experiences/<int:pk>/",
        views.personalizedexperience_detail,
        name="personalizedexperience_detail",
    ),
    path(
        "personalization/experiences/<int:pk>/edit/",
        views.personalizedexperience_edit,
        name="personalizedexperience_edit",
    ),
    path(
        "personalization/experiences/<int:pk>/delete/",
        views.personalizedexperience_delete,
        name="personalizedexperience_delete",
    ),
    path(
        "personalization/experiences/<int:pk>/toggle/",
        views.personalizedexperience_toggle,
        name="personalizedexperience_toggle",
    ),
]
