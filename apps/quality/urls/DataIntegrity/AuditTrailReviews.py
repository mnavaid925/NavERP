from django.urls import path

from apps.quality.views.DataIntegrity import AuditTrailReviews as views

urlpatterns = [
    path("audit-reviews/", views.audit_trail_review_list, name="audit_trail_review_list"),
    path("audit-reviews/create/", views.audit_trail_review_create, name="audit_trail_review_create"),
    path("audit-reviews/<int:pk>/", views.audit_trail_review_detail, name="audit_trail_review_detail"),
    path("audit-reviews/<int:pk>/edit/", views.audit_trail_review_edit, name="audit_trail_review_edit"),
    path("audit-reviews/<int:pk>/delete/", views.audit_trail_review_delete, name="audit_trail_review_delete"),
]
