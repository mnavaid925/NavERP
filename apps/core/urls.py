from django.urls import path

from . import views

app_name = "core"


def crud(slug, name):
    """Generate the 5 standard CRUD routes for a model."""
    return [
        path(f"{slug}/", getattr(views, f"{name}_list"), name=f"{name}_list"),
        path(f"{slug}/add/", getattr(views, f"{name}_create"), name=f"{name}_create"),
        path(f"{slug}/<int:pk>/", getattr(views, f"{name}_detail"), name=f"{name}_detail"),
        path(f"{slug}/<int:pk>/edit/", getattr(views, f"{name}_edit"), name=f"{name}_edit"),
        path(f"{slug}/<int:pk>/delete/", getattr(views, f"{name}_delete"), name=f"{name}_delete"),
    ]


urlpatterns = (
    crud("org-units", "orgunit")
    + crud("parties", "party")
    + crud("party-roles", "partyrole")
    + crud("addresses", "address")
    + crud("contact-methods", "contactmethod")
    + crud("relationships", "partyrelationship")
    + crud("employments", "employment")
    + crud("activities", "activity")
    + crud("documents", "document")
    + [
        path("audit-logs/", views.auditlog_list, name="auditlog_list"),
        path("audit-logs/<int:pk>/", views.auditlog_detail, name="auditlog_detail"),
        # Global header search
        path("search/", views.global_search, name="search"),
        path("search/suggest/", views.global_search_suggest, name="search_suggest"),
        # 0.6 module access scope — literal segments BEFORE the <int:pk> routes
        path("module-scopes/", views.module_scope_list, name="module_scope_list"),
        path("module-scopes/sync/", views.module_scope_sync, name="module_scope_sync"),
        path("module-scopes/add/", views.module_scope_create, name="module_scope_create"),
        path("module-scopes/<int:pk>/", views.module_scope_detail, name="module_scope_detail"),
        path("module-scopes/<int:pk>/edit/", views.module_scope_edit, name="module_scope_edit"),
        path("module-scopes/<int:pk>/delete/", views.module_scope_delete, name="module_scope_delete"),
        path("field-masks/", views.field_mask_list, name="field_mask_list"),
        path("field-masks/add/", views.field_mask_create, name="field_mask_create"),
        path("field-masks/<int:pk>/edit/", views.field_mask_edit, name="field_mask_edit"),
        path("field-masks/<int:pk>/delete/", views.field_mask_delete, name="field_mask_delete"),
        path("access-matrix/", views.access_matrix, name="access_matrix"),
    ]
)
