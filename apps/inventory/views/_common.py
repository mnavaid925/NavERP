"""Shared imports for the inventory views package.

One sub-package per NavERP sub-module, one module per entity, mirroring models/ forms/ urls/.
Every entity module does ``from apps.inventory.views._common import *``. The package __init__
re-exports every view so the apps/inventory/urls/ package (``views.<name>``) resolves.

Imports inside these packages must be ABSOLUTE: a relative ``from .models import X`` would resolve
to the wrong package one level deeper.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_detail, crud_edit, crud_list
from apps.core.utils import write_audit_log
