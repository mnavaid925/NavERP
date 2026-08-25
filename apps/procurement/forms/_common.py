"""Shared toolkit for the procurement forms package.

One sub-package per NavERP sub-module, one module per entity, mirroring models/ views/ urls/.
Entity modules do ``from apps.procurement.forms._common import *`` and then name any private
helper they use on an explicit second import line. The package __init__ re-exports every form.

This is a local copy of the proven apps/scm + apps/inventory pattern — peer apps deliberately
don't import each other's internals:

* ``TenantModelForm`` (from core) auto-scopes a ModelChoiceField when the TARGET model carries its
  own ``tenant``.
* ``_reject_foreign`` is the crafted-POST re-check: a narrowed ``<select>`` is UX, not an
  authorization boundary, so every tenant-scoped FK is re-checked where it renders as a field
  error instead of leaking another workspace's row into this one.

6.2 adds inline formsets (template lines / amendment line changes), so ``forms`` and
``inlineformset_factory`` join the shared toolkit here rather than each entity module importing
its own copy.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.core.forms import TenantModelForm


class TenantUniqueMixin:
    """Stamps ``instance.tenant`` before ``full_clean()`` runs on CREATE.

    SECOND role of the scm/inventory mixin matters most here: any model ``clean()``
    that compares a chosen FK's tenant against ``self.tenant_id`` reads that stamp —
    without it every create is falsely rejected as cross-tenant, because the CRUD
    helpers only assign the real tenant AFTER ``is_valid()``. Mix in BEFORE
    TenantModelForm on every form whose model carries such checks.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

    def validate_unique(self):
        exclude = set(self._get_validation_exclusions())
        exclude.discard("tenant")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)


def _reject_foreign(form, cleaned, names):
    """Field-error any chosen FK whose row belongs to another workspace.

    Same rule and same reasoning as scm's copy: the error keys on a field the FORM has, so it
    renders; it does not depend on the instance's tenant having been stamped first. ``names`` is
    each form's own tenant-scoped FK list.
    """
    tenant_id = form.tenant.pk if form.tenant is not None else None
    for name in names:
        chosen = cleaned.get(name)
        if chosen is None:
            continue
        if getattr(chosen, "tenant_id", None) != tenant_id:
            form.add_error(name, "That record belongs to another workspace.")
