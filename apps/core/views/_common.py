"""Shared toolkit for the core views package.

apps/core/views.py was split into this package. core is a Module 0 FOUNDATION app with
no NavERP sub-modules, so entity files sit FLAT at the package root (mirroring its already-
flat templates/core/<entity>/). The package __init__ re-exports everything, so
``from apps.core.views import X`` is unchanged.

The import block below is the ORIGINAL views.py header, verbatim.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from apps.core.crud import crud_create, crud_delete, crud_detail, crud_edit, crud_list
from apps.core.search import run_search
from apps.core.decorators import tenant_admin_required
from apps.core.models import (
    Party,
)


User = get_user_model()


def _parties(request):
    return Party.objects.filter(tenant=request.tenant)
