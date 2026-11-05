from django.urls import path

from apps.bi.views.DataCatalog.CatalogTrustEndorsements import (
    catalog_trust_endorsement_list,
    catalog_trust_endorsement_create,
    catalog_trust_endorsement_detail,
    catalog_trust_endorsement_edit,
    catalog_trust_endorsement_delete,
)

urlpatterns = [
    path("catalog/endorsements/", catalog_trust_endorsement_list, name="catalog_trust_endorsement_list"),
    path("catalog/endorsements/create/", catalog_trust_endorsement_create, name="catalog_trust_endorsement_create"),
    path("catalog/endorsements/<int:pk>/", catalog_trust_endorsement_detail, name="catalog_trust_endorsement_detail"),
    path("catalog/endorsements/<int:pk>/edit/", catalog_trust_endorsement_edit, name="catalog_trust_endorsement_edit"),
    path("catalog/endorsements/<int:pk>/delete/", catalog_trust_endorsement_delete, name="catalog_trust_endorsement_delete"),
]
