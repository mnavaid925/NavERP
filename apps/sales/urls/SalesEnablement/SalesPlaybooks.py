"""Sales 8.9 — URLs for `SalesPlaybook`."""
from django.urls import path

from apps.sales.views.SalesEnablement.SalesPlaybooks import (
    sales_playbook_create,
    sales_playbook_delete,
    sales_playbook_detail,
    sales_playbook_edit,
    sales_playbook_list,
)

urlpatterns = [
    path("enablement/playbooks/", sales_playbook_list, name="sales_playbook_list"),
    path("enablement/playbooks/new/", sales_playbook_create, name="sales_playbook_create"),
    path("enablement/playbooks/<int:pk>/", sales_playbook_detail, name="sales_playbook_detail"),
    path("enablement/playbooks/<int:pk>/edit/", sales_playbook_edit, name="sales_playbook_edit"),
    path("enablement/playbooks/<int:pk>/delete/", sales_playbook_delete, name="sales_playbook_delete"),
]
