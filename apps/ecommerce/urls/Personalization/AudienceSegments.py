from django.urls import path

from apps.ecommerce.views.Personalization import AudienceSegments as views

urlpatterns = [
    path(
        "personalization/segments/",
        views.audiencesegment_list,
        name="audiencesegment_list",
    ),
    path(
        "personalization/segments/create/",
        views.audiencesegment_create,
        name="audiencesegment_create",
    ),
    path(
        "personalization/segments/<int:pk>/",
        views.audiencesegment_detail,
        name="audiencesegment_detail",
    ),
    path(
        "personalization/segments/<int:pk>/edit/",
        views.audiencesegment_edit,
        name="audiencesegment_edit",
    ),
    path(
        "personalization/segments/<int:pk>/delete/",
        views.audiencesegment_delete,
        name="audiencesegment_delete",
    ),
    path(
        "personalization/segments/<int:pk>/toggle/",
        views.audiencesegment_toggle,
        name="audiencesegment_toggle",
    ),
    path(
        "personalization/segments/<int:pk>/recalculate/",
        views.audiencesegment_recalculate,
        name="audiencesegment_recalculate",
    ),
]
