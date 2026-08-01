"""SCM 4.12 Contract & Compliance — ComplianceRequirement + ComplianceCheck routes.

Two first segments, ``compliance-requirements/`` and ``compliance-checks/``, both checked against
the WHOLE concatenated urlconf rather than against this block alone: nothing anywhere in ``scm``
starts with ``compliance``. They cannot shadow each other either — Django matches whole path
components and never splits one at the hyphen, so ``compliance-checks`` is not a sub-path of
``compliance-requirements``.

A ``ComplianceCheck`` is a tenant-less child reached through ``requirement__tenant``, so it has no
list and no detail page: it is rendered as a timeline on its parent's detail page. That is why the
CRUD-completeness rule's "every model with a list page" clause does not apply to it — but it still
gets create (through the parent), edit and delete, which is why the two child routes exist at all.
The child's edit/delete hang off ``compliance-checks/<int:pk>/`` rather than nesting under the
parent: a check's pk already identifies it, and nesting would let a caller pair a real check with
somebody else's requirement id and invite the view to trust the wrong half of the pair.

``add/`` is literal and MUST precede ``<int:pk>/`` — first-match-wins, so a pk route above it would
swallow the create page. No greedy ``<str:…>`` converter is introduced here.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("compliance-requirements/", views.compliancerequirement_list,
         name="compliancerequirement_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("compliance-requirements/add/", views.compliancerequirement_create,
         name="compliancerequirement_create"),
    path("compliance-requirements/<int:pk>/", views.compliancerequirement_detail,
         name="compliancerequirement_detail"),
    path("compliance-requirements/<int:pk>/edit/", views.compliancerequirement_edit,
         name="compliancerequirement_edit"),
    path("compliance-requirements/<int:pk>/delete/", views.compliancerequirement_delete,
         name="compliancerequirement_delete"),
    # Appending a check is what advances the parent's status and its next due date, so it is a
    # route on the PARENT: the child never exists without one.
    path("compliance-requirements/<int:pk>/checks/add/", views.compliancerequirement_record_check,
         name="compliancerequirement_record_check"),

    # The child's own two routes — see the module docstring for why they are not nested.
    path("compliance-checks/<int:pk>/edit/", views.compliancecheck_edit,
         name="compliancecheck_edit"),
    path("compliance-checks/<int:pk>/delete/", views.compliancecheck_delete,
         name="compliancecheck_delete"),
]
