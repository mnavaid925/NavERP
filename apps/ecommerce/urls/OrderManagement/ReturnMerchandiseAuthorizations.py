from django.urls import path

from apps.ecommerce.views.OrderManagement import ReturnMerchandiseAuthorizations as views

urlpatterns = [
    path("returns/", views.returnmerchandiseauthorization_list, name="returnmerchandiseauthorization_list"),
    path("returns/create/", views.returnmerchandiseauthorization_create, name="returnmerchandiseauthorization_create"),
    path("returns/<int:pk>/", views.returnmerchandiseauthorization_detail, name="returnmerchandiseauthorization_detail"),
    path("returns/<int:pk>/edit/", views.returnmerchandiseauthorization_edit, name="returnmerchandiseauthorization_edit"),
    path("returns/<int:pk>/delete/", views.returnmerchandiseauthorization_delete, name="returnmerchandiseauthorization_delete"),
    path("returns/<int:pk>/complete/", views.returnmerchandiseauthorization_complete, name="returnmerchandiseauthorization_complete"),
]
