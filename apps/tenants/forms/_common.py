"""Shared toolkit for the tenants forms package.

apps/tenants/forms.py was split into this package. tenants is a Module 0 FOUNDATION app with
no NavERP sub-modules, so entity files sit FLAT at the package root (mirroring its already-
flat templates/tenants/<entity>/). The package __init__ re-exports everything, so
``from apps.tenants.forms import X`` is unchanged.

The import block below is the ORIGINAL forms.py header, verbatim.
"""
from django import forms
from apps.core.forms import TenantModelForm
