"""SCM 4.10 Returns Management — the receiving-bench routes (prefix ``return-dispositions/``).

**Deliberately ``return-dispositions/`` and not ``dispositions/``** — the generic segment is one
Module 5 will want for its own "Disposition Routing" bullet, and 4.10 has declared itself the owner
of the TABLE, not of the whole word.

``post/`` is the ONE route in all of 4.10 that can write to the append-only stock ledger.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("return-dispositions/", views.returndisposition_list, name="returndisposition_list"),
    path("return-dispositions/add/", views.returndisposition_create,
         name="returndisposition_create"),
    path("return-dispositions/<int:pk>/", views.returndisposition_detail,
         name="returndisposition_detail"),
    path("return-dispositions/<int:pk>/edit/", views.returndisposition_edit,
         name="returndisposition_edit"),
    path("return-dispositions/<int:pk>/delete/", views.returndisposition_delete,
         name="returndisposition_delete"),
    path("return-dispositions/<int:pk>/decide/", views.returndisposition_decide,
         name="returndisposition_decide"),
    # THE ledger write — the only one in 4.10.
    path("return-dispositions/<int:pk>/post/", views.returndisposition_post,
         name="returndisposition_post"),
    path("return-dispositions/<int:pk>/split/", views.returndisposition_split,
         name="returndisposition_split"),
    path("return-dispositions/<int:pk>/mark-refurbished/",
         views.returndisposition_mark_refurbished, name="returndisposition_mark_refurbished"),
]
