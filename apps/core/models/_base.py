"""Shared base for the core models package.

apps/core/models.py was split into this package. core is a Module 0 FOUNDATION app with
no NavERP sub-modules, so entity files sit FLAT at the package root (mirroring its already-
flat templates/core/<entity>/). The package __init__ re-exports everything, so
``from apps.core.models import X`` is unchanged.

The import block below is the ORIGINAL models.py header, verbatim.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
