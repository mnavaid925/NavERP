"""Shared imports for the CRM forms package.

apps/crm/forms.py was split into this package (one sub-package per CRM sub-module, one module per
entity, mirroring apps/crm/views/ and apps/crm/models/). Every entity module does
``from apps.crm.forms._common import *`` then imports only the models it binds. The package __init__
re-exports every form, so ``from apps.crm.forms import LeadForm`` keeps working unchanged.

The shared base ``apps.core.forms.TenantModelForm`` auto-scopes every FK dropdown to the active
tenant and applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``,
and system-set fields (``resolved_at``/``completed_at``/``views_count``/``converted_party``).
"""
import os

from django import forms

from apps.accounting.models import Invoice, Payment  # 1.7 reuses the accounting ledger (L29)
from apps.core.forms import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES, TenantModelForm
from apps.core.models import Party
