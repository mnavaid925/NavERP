"""Shared imports for the projects views package.

One sub-package per NavERP sub-module, one module per entity, mirroring models/ forms/ urls/.
Every entity module does ``from apps.projects.views._common import *``. The package __init__
re-exports every view so the apps/projects/urls/ package (``views.<name>``) resolves.

Imports inside these packages must be ABSOLUTE: a relative ``from .models import X`` would
resolve to the wrong package one level deeper.

**Audit action length:** ``core.AuditLog.action`` is ``varchar(10)``. Every action string this
app writes is ≤ 10 characters (``create`` / ``update`` / ``delete`` / ``submit`` / ``approve`` /
``reject`` / ``convert`` / ``return`` / ``schedule`` / ``held`` / ``complete`` / ``baseline``);
the verb itself goes in ``changes``. See the contract file.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_detail, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
