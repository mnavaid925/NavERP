"""Shared imports for the CRM views package.

apps/crm/views.py was split into this package (one sub-package per CRM sub-module 1.1-1.12,
one module per entity). Every entity module does ``from apps.crm.views._common import *`` to
pull in the common Django + core toolkit, then adds only the models/forms it uses. The package
__init__ re-exports every view so ``apps/crm/urls.py`` (``from . import views`` / ``views.<name>``)
keeps working unchanged.
"""
import hashlib
import hmac
import json
import secrets
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Avg, Count, DecimalField, F, Max, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template import Context, Engine, Library
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import ContactMethod, Party, PartyRole
from apps.core.utils import write_audit_log

User = get_user_model()
