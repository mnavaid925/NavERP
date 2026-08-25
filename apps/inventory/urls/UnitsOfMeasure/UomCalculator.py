from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("conversion-calculator/", views.uom_calculator, name="uom_calculator"),
]
