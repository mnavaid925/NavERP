"""Shared imports for the HRM forms package.

apps/hrm/forms.py was split into this package (one sub-package per sub-module 3.1-3.41, one
module per entity, mirroring models/ views/ urls/). Every entity module does
``from apps.hrm.forms._common import *``; the package __init__ re-exports every form.

The import block below is the ORIGINAL forms.py header, verbatim.
"""
import os
import re
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit, Party


# Photo upload safety: rasterizable-image allowlist + size cap (mirrors core DocumentForm).
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


# Onboarding document upload safety: contracts/forms/scans allowlist + cap (mirrors clean_photo).
ALLOWED_ONBOARDING_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}


MAX_ONBOARDING_DOC_BYTES = 10 * 1024 * 1024  # 10 MB
