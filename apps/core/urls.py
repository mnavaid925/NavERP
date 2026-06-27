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
    ]
)
