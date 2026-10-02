"""Sales 8.8 — URLs for the playbook register.

Six routes. **THE ORDER INSIDE THIS FILE IS BEHAVIOUR**: the literal ``task-templates/add/`` MUST
precede ``task-templates/<int:pk>/``.

``generate/`` is **POST-only** in the view, and is the reason: it materialises ``crm.CrmTask`` rows
across every target in the book and stamps the template's frozen receipt, all inside one
transaction. A GET that did that would let a link preview run a rep's entire playbook.

Every pattern begins with the literal ``task-templates/``, verified free against the whole
concatenated ``sales:urlpatterns`` list.
"""
from django.urls import path

from apps.sales.views.SalesActivityTaskManagement.TaskTemplates import (
    task_template_create,
    task_template_delete,
    task_template_detail,
    task_template_edit,
    task_template_generate,
    task_template_list,
)

urlpatterns = [
    path("task-templates/", task_template_list, name="task_template_list"),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path("task-templates/add/", task_template_create, name="task_template_create"),
    # The POST-only verb, listed before the keyed pages for readability.
    path("task-templates/<int:pk>/generate/", task_template_generate, name="task_template_generate"),
    path("task-templates/<int:pk>/edit/", task_template_edit, name="task_template_edit"),
    path("task-templates/<int:pk>/delete/", task_template_delete, name="task_template_delete"),
    # The bare keyed page is LAST.
    path("task-templates/<int:pk>/", task_template_detail, name="task_template_detail"),
]