from django.urls import path

from apps.documents.views.RecordsManagement import DispositionReview as views

urlpatterns = [
    path("records/disposition-board/", views.disposition_review_board, name="disposition_review_board"),
]
