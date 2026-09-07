"""Shared toolkit for the projects forms package.

One sub-package per NavERP sub-module, one module per entity, mirroring models/ views/ urls/.
Entity modules do ``from apps.projects.forms._common import *`` and then name any private helper
they use on an explicit second import line. The package __init__ re-exports every form.

This is a local copy of the proven apps/scm + apps/inventory + apps/procurement pattern — peer
apps deliberately don't import each other's internals:

* ``TenantModelForm`` (from core) auto-scopes a ModelChoiceField when the TARGET model carries its
  own ``tenant``.
* ``TenantUniqueMixin`` has a SECOND role that matters here: any model ``clean()`` that compares a
  chosen FK's tenant against ``self.tenant_id`` reads the stamp it makes — without it every create
  is falsely rejected as cross-tenant, because the CRUD helpers only assign the real tenant AFTER
  ``is_valid()``. Mix in BEFORE TenantModelForm on every form whose model carries such checks.
* ``_reject_foreign`` is the crafted-POST re-check: a narrowed ``<select>`` is UX, not an
  authorization boundary, so every tenant-scoped FK is re-checked where it renders as a field
  error instead of leaking another workspace's row into this one.

**Gotcha (L29):** ``accounting.Currency`` is GLOBAL — it has no ``tenant`` column. Core's
``TenantModelForm`` already skips scoping for models without a ``tenant`` field, and
``_reject_foreign`` must NOT be applied to it either: comparing ``currency.tenant`` would raise
``AttributeError``. Every other FK on these forms is tenant-scoped.
"""
from django import forms
from django.core.exceptions import ValidationError  # noqa: F401

from apps.core.forms import TenantModelForm


class TenantUniqueMixin:
    """Stamps ``instance.tenant`` before ``full_clean()`` runs on CREATE.

    Also drops ``tenant`` from the unique-validation exclusions so the per-model
    ``unique_together`` actually binds — see ``ProjectStakeholder.clean()``, which is the row
    this matters most for (its second constraint is only partial at the DB level).
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

    The error keys on a field the FORM has, so it renders; it does not depend on the instance's
    tenant having been stamped first. ``names`` is each form's own tenant-scoped FK list — never
    pass a global model (``accounting.Currency``) here.
    """
    tenant_id = form.tenant.pk if form.tenant is not None else None
    for name in names:
        chosen = cleaned.get(name)
        if chosen is None:
            continue
        if getattr(chosen, "tenant_id", None) != tenant_id:
            form.add_error(name, "That record belongs to another workspace.")
