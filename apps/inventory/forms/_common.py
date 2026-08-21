"""Shared toolkit for the inventory forms package.

One sub-package per NavERP sub-module, one module per entity, mirroring models/ views/ urls/.
Entity modules do ``from apps.inventory.forms._common import *`` and then name any private helper
they use on an explicit second import line. The package __init__ re-exports every form.

This is a local copy of the proven apps/scm pattern — peer apps deliberately don't import each
other's internals:

* ``TenantModelForm`` (from core) auto-scopes a ModelChoiceField when the TARGET model carries its
  own ``tenant`` — true for every FK this app points at (``scm.Item``, ``accounting.Currency`` is
  global and filtered by hand).
* ``TenantUniqueMixin`` makes a tenant-including ``unique_together`` actually validate at the form
  boundary; without it a duplicate attribute name passes ``is_valid()`` and dies as an uncaught
  IntegrityError (a 500) on ``.save()``.
* ``_reject_foreign`` is the crafted-POST re-check: a narrowed ``<select>`` is UX, not an
  authorization boundary, so every tenant-scoped FK is re-checked here where it renders as a field
  error instead of leaking another workspace's row into this one.
"""
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.core.forms import MAX_UPLOAD_BYTES, TenantModelForm


class TenantUniqueMixin:
    """Makes a model's ``unique_together`` that INCLUDES ``tenant`` actually validate on a form.

    The instance needs its tenant before ``validate_unique()`` runs — `tenant` is never a form
    field and the CRUD helpers only assign it AFTER ``is_valid()`` — and `tenant` must be removed
    from the validation exclusions, because Django skips a ``unique_together`` entirely if ANY of
    its fields is excluded. Mix in BEFORE TenantModelForm.

    SECOND role, easy to miss: ``__init__`` also stamps ``instance.tenant`` for models with NO
    unique constraint at all. Any model ``clean()`` that compares a chosen FK's tenant against
    ``self.tenant_id`` (ProductFile's foreign-item check) reads that stamp during
    ``full_clean()`` on CREATE — without it every create would be falsely rejected as
    cross-tenant, because the CRUD helpers only assign the real tenant after ``is_valid()``.
    So the mixin stays on every form whose model carries such a check, constraint or not.
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


def _active_currencies(form):
    """Constrain a ``currency`` field to active currencies. Currency is GLOBAL (no tenant FK), so
    the TenantModelForm base cannot scope it.

    The stored value is unioned back in: a currency deactivated AFTER a price row was saved must
    stay selectable on that row's edit form, or submitting the untouched form would clean to None
    and silently wipe the field (the scm ``_keep_current`` rule, inlined for one call site)."""
    if "currency" in form.fields:
        from apps.accounting.models import Currency
        current_id = getattr(form.instance, "currency_id", None)
        condition = Q(is_active=True)
        if current_id:
            condition |= Q(pk=current_id)
        form.fields["currency"].queryset = Currency.objects.filter(condition)


def _reject_foreign(form, cleaned, names):
    """Field-error any chosen FK whose row belongs to another workspace.

    Same rule and same reasoning as scm's copy: the error keys on a field the FORM has, so it
    renders; it does not depend on the instance's tenant having been stamped first, so it is live
    on the create path too. ``names`` is each form's own tenant-scoped FK list.
    """
    tenant_id = form.tenant.pk if form.tenant is not None else None
    for name in names:
        chosen = cleaned.get(name)
        if chosen is None:
            continue
        if getattr(chosen, "tenant_id", None) != tenant_id:
            form.add_error(name, "That record belongs to another workspace.")
