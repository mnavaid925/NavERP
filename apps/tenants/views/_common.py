"""Shared toolkit for the tenants views package.

apps/tenants/views.py was split into this package. tenants is a Module 0 FOUNDATION app with
no NavERP sub-modules, so entity files sit FLAT at the package root (mirroring its already-
flat templates/tenants/<entity>/). The package __init__ re-exports everything, so
``from apps.tenants.views import X`` is unchanged.

The import block below is the ORIGINAL views.py header, verbatim.
"""
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.tenants import stripe_utils


KEY_REVEAL_SESSION = "_key_reveal"
