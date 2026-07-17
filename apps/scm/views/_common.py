"""Shared imports for the scm views package.

One sub-package per NavERP sub-module (4.1-4.19), one module per entity, mirroring models/ forms/
urls/. Every entity module does ``from apps.scm.views._common import *``; cross-cutting private
helpers live in ``apps/scm/views/_helpers.py``. The package __init__ re-exports every view so the
apps/scm/urls/ package (``views.<name>``) resolves.

Imports inside these packages must be ABSOLUTE: a relative ``from .models import X`` would resolve
to the wrong package one level deeper.
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_detail, crud_edit, crud_list, paginate
# _changed builds the {field: new_value} diff (with the sensitive-field redaction list applied) that
# crud_edit records automatically. The scm form views hand-roll their save path so the inline
# formset commits in the same transaction as its parent, which means they bypass crud_edit — and
# would silently lose that diff. Import it rather than duplicate the redaction logic.
from apps.core.crud import _changed
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
