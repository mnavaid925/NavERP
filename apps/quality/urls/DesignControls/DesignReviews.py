from django.urls import path

from apps.quality.views.DesignControls import DesignReviews as views

urlpatterns = [
    path("design-controls/reviews/", views.design_review_list, name="design_review_list"),
    path("design-controls/reviews/export/", views.design_review_export, name="design_review_export"),
    path("design-controls/reviews/create/", views.design_review_create, name="design_review_create"),
    path("design-controls/reviews/<int:pk>/", views.design_review_detail, name="design_review_detail"),
    path("design-controls/reviews/<int:pk>/edit/", views.design_review_edit, name="design_review_edit"),
    path("design-controls/reviews/<int:pk>/delete/", views.design_review_delete, name="design_review_delete"),
    path("design-controls/reviews/<int:pk>/approve-gate/", views.design_review_approve_gate, name="design_review_approve_gate"),
]
