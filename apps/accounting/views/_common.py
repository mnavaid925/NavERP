"""Shared imports for the accounting views package.

apps/accounting/views.py + views_advanced.py were split into this package (one sub-package per
sub-module 2.1-2.15, one module per entity, mirroring models/ forms/ urls/). Every entity module does
``from apps.accounting.views._common import *``; the cross-cutting private helpers (GL posting,
period guards, doc-status recompute, journal reversal, cash position, AR/AP aging, account balances)
live in ``apps/accounting/views/_helpers.py``. The package __init__ re-exports every view so the
apps/accounting/urls/ package (``views.<name>``) is unchanged.

Imports inside these packages must be ABSOLUTE: a relative ``from .models import X`` would resolve to
the wrong package one level deeper.
"""
import csv
import io
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
