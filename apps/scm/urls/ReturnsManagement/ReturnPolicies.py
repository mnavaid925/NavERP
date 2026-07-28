"""SCM 4.10 Returns Management — ReturnPolicy routes (prefix ``return-policies/``).

The literal ``add/`` route sits before the ``<int:pk>/`` ones, per the urls-package ordering rule
(Django is first-match-wins, so order is behaviour).
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("return-policies/", views.returnpolicy_list, name="returnpolicy_list"),
    path("return-policies/add/", views.returnpolicy_create, name="returnpolicy_create"),
    path("return-policies/<int:pk>/", views.returnpolicy_detail, name="returnpolicy_detail"),
    path("return-policies/<int:pk>/edit/", views.returnpolicy_edit, name="returnpolicy_edit"),
    path("return-policies/<int:pk>/delete/", views.returnpolicy_delete,
         name="returnpolicy_delete"),
]
