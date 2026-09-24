from django.urls import path

from apps.sales import views


urlpatterns = [
    path("qualifications/", views.lead_qualification_list, name="lead_qualification_list"),
    path("qualifications/add/", views.lead_qualification_create, name="lead_qualification_create"),
    path("qualifications/<int:pk>/", views.lead_qualification_detail, name="lead_qualification_detail"),
    path("qualifications/<int:pk>/edit/", views.lead_qualification_edit, name="lead_qualification_edit"),
    path("qualifications/<int:pk>/delete/", views.lead_qualification_delete, name="lead_qualification_delete"),
    path("qualifications/<int:pk>/partial/", views.lead_qualification_partial, name="lead_qualification_partial"),
    path("qualifications/<int:pk>/qualify/", views.lead_qualification_qualify, name="lead_qualification_qualify"),
    path("qualifications/<int:pk>/disqualify/", views.lead_qualification_disqualify, name="lead_qualification_disqualify"),
    path("qualifications/<int:pk>/archive/", views.lead_qualification_archive, name="lead_qualification_archive"),
    path("qualifications/<int:pk>/recalculate/", views.lead_qualification_recalculate, name="lead_qualification_recalculate"),
    path("qualifications/<int:pk>/route-preview/", views.lead_qualification_route_preview, name="lead_qualification_route_preview"),
]
