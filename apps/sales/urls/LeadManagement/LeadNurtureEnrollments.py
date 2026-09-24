from django.urls import path

from apps.sales import views


urlpatterns = [
    path("nurture-enrollments/", views.lead_nurture_enrollment_list, name="lead_nurture_enrollment_list"),
    path("nurture-enrollments/add/", views.lead_nurture_enrollment_create, name="lead_nurture_enrollment_create"),
    path("nurture-enrollments/<int:pk>/", views.lead_nurture_enrollment_detail, name="lead_nurture_enrollment_detail"),
    path("nurture-enrollments/<int:pk>/edit/", views.lead_nurture_enrollment_edit, name="lead_nurture_enrollment_edit"),
    path("nurture-enrollments/<int:pk>/delete/", views.lead_nurture_enrollment_delete, name="lead_nurture_enrollment_delete"),
    path("nurture-enrollments/<int:pk>/activate/", views.lead_nurture_enrollment_activate, name="lead_nurture_enrollment_activate"),
    path("nurture-enrollments/<int:pk>/pause/", views.lead_nurture_enrollment_pause, name="lead_nurture_enrollment_pause"),
    path("nurture-enrollments/<int:pk>/resume/", views.lead_nurture_enrollment_resume, name="lead_nurture_enrollment_resume"),
    path("nurture-enrollments/<int:pk>/complete/", views.lead_nurture_enrollment_complete, name="lead_nurture_enrollment_complete"),
    path("nurture-enrollments/<int:pk>/cancel/", views.lead_nurture_enrollment_cancel, name="lead_nurture_enrollment_cancel"),
    path("nurture-enrollments/<int:pk>/reply/", views.lead_nurture_enrollment_reply, name="lead_nurture_enrollment_reply"),
    path("nurture-enrollments/<int:pk>/convert-exit/", views.lead_nurture_enrollment_convert_exit, name="lead_nurture_enrollment_convert_exit"),
]
