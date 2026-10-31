from django.urls import path

from apps.ecommerce.views.ReviewUgc import ProductQuestionAnswers as views

urlpatterns = [
    path("questions/", views.productquestionanswer_list, name="productquestionanswer_list"),
    path("questions/create/", views.productquestionanswer_create, name="productquestionanswer_create"),
    path("questions/<int:pk>/", views.productquestionanswer_detail, name="productquestionanswer_detail"),
    path("questions/<int:pk>/edit/", views.productquestionanswer_edit, name="productquestionanswer_edit"),
    path("questions/<int:pk>/delete/", views.productquestionanswer_delete, name="productquestionanswer_delete"),
    path("questions/<int:pk>/respond/", views.productquestionanswer_respond, name="productquestionanswer_respond"),
]
