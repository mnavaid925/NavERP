"""Shared base for the tenants models package.

apps/tenants/models.py was split into this package. tenants is a Module 0 FOUNDATION app with
no NavERP sub-modules, so entity files sit FLAT at the package root (mirroring its already-
flat templates/tenants/<entity>/). The package __init__ re-exports everything, so
``from apps.tenants.models import X`` is unchanged.

The import block below is the ORIGINAL models.py header, verbatim.
"""
import hashlib
import secrets
from django.core.validators import RegexValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from apps.core.models import Tenant
from apps.core.utils import next_number


HEX_COLOR = RegexValidator(
    r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$",
    "Enter a valid hex color, e.g. #2563eb.",
)
