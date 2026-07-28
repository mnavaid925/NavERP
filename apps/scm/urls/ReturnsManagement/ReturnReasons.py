"""SCM 4.10 Returns Management — ReturnReason routes (prefix ``return-reasons/``).

``return-reasons/`` is first-segment-unique against every prefix in the whole concatenated urlconf
— in particular it is a separate segment from 4.10's own ``return-policies/``,
``return-dispositions/``, ``return-portal/`` and ``return-tracking/``, and from 4.3's
``reorder-rules/`` / ``reorder-alerts/``. The literal ``add/`` route precedes the ``<int:pk>/`` ones.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("return-reasons/", views.returnreason_list, name="returnreason_list"),
    path("return-reasons/add/", views.returnreason_create, name="returnreason_create"),
    path("return-reasons/<int:pk>/", views.returnreason_detail, name="returnreason_detail"),
    path("return-reasons/<int:pk>/edit/", views.returnreason_edit, name="returnreason_edit"),
    path("return-reasons/<int:pk>/delete/", views.returnreason_delete,
         name="returnreason_delete"),
]
