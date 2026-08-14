"""SCM 4.18 Finance & Accounting Integration — the ``DutyTariff`` form.

What a human types here is the DUTY SCHEDULE: a classification, an origin, a rate and the dates it
applies between. What a human never types is ``number`` (minted in ``TenantNumbered.save()``) or
``tenant`` (stamped by ``crud_create`` and, earlier, by :class:`TenantUniqueMixin`).

--------------------------------------------------------------------------------------------------
``TenantUniqueMixin`` IS LOAD-BEARING HERE — do not "simplify" it away
--------------------------------------------------------------------------------------------------
``DutyTariff`` carries ``unique_together ("tenant", "hs_code", "country_of_origin",
"effective_from")``, and **re-entering an HS code / origin / start date that already exists is the
ordinary mistake on this page** — it is precisely what somebody does when a duty schedule changes and
they type the new rate against the old start date.

Django skips a ``unique_together`` **entirely** if ANY of its member fields is excluded from
validation, and ``tenant`` is never a form field, so it is always excluded. Without the mixin the
duplicate sails through ``is_valid()`` and raises an uncaught ``IntegrityError`` — a 500 on a
mainline CRUD path, triggered by an everyday user error. Both halves of the mixin are needed and
neither is sufficient alone:

* its ``__init__`` half stamps ``instance.tenant`` **before** validation, so the check runs against a
  real workspace rather than ``None`` (``crud_create`` only assigns the tenant AFTER ``is_valid()``);
* its ``validate_unique`` half discards ``tenant`` from the exclusion set, which is what actually
  re-enables the constraint.

It is mixed in **BEFORE** ``TenantModelForm`` so its ``__init__`` runs first in the MRO: it calls up
to ``TenantModelForm`` (which builds ``self.fields`` and applies the widget/FK-scoping pass) and only
then stamps the tenant, so both are in place by the time this class's own ``__init__`` body runs.

Stamping the tenant early has a second effect worth naming: it is what makes the cross-tenant leg of
``DutyTariff.clean()`` live on the CREATE path, which is the path a crafted POST takes. With
``tenant_id`` still ``None`` that guard is the exact case it skips, i.e. dead code.

--------------------------------------------------------------------------------------------------
NO FORM WRITES A COSTED RATE
--------------------------------------------------------------------------------------------------
Nothing on this page restates history. ``LandedCostCharge`` **snapshots** ``duty_rate_pct`` at the
moment a charge is entered, so editing a tariff here changes what the NEXT lookup defaults to and
never what an already-costed receipt was costed at.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _reject_foreign

# `TaxCode` is accounting's MASTER, not scm's — the same one-way peer-app import `_common.py`
# already makes for `Currency`. Named explicitly rather than taken off the star import: `_common`
# carries no `__all__`, so anything arriving that way would be invisible to a reader of this file.
from apps.accounting.models import TaxCode

from apps.scm.models import DutyTariff


def _tax_code_qs(tenant):
    """Active tax codes for this workspace — and NOTHING for a workspace-less caller.

    ``TenantModelForm`` already scopes every FK whose target carries a ``tenant`` column, but only
    ``if tenant is not None``; a tenant-less caller (the superuser has ``tenant=None`` BY DESIGN)
    falls through to the UNSCOPED default manager and would be offered every workspace's tax codes.
    Re-filtering from the model rather than chaining off the base's result makes the scoping true by
    CONSTRUCTION instead of true by the caller having behaved — the ``_scope_to_tenant`` idiom from
    4.13/4.15/4.17, stated for the single field this form needs it for.
    """
    if tenant is None:
        return TaxCode.objects.none()
    return TaxCode.objects.filter(tenant=tenant, is_active=True).order_by("name")


def _keep_current(form, name, base_queryset):
    """Union the field's CURRENTLY-STORED choice back into the narrowed queryset.

    ``tax_code`` is narrowed to ``is_active=True``. A tax code that was deactivated AFTER a tariff
    was pointed at it would therefore vanish from the dropdown — and because the field is optional
    (``null=True``), the missing option does not fail validation: it silently resolves to ``None``
    and **clears the link** for somebody who only came to fix a typo in the description. Silent data
    loss on an edit is worse than an extra option, so the stored value is unioned back in.

    A no-op whenever the stored value still qualifies, which is the common case; it exists for the
    one that no longer does. ``base_queryset`` is the UN-narrowed one so any ``select_related`` a
    dropdown's ``__str__`` needs survives the rebuild.

    (This is an addition to the frozen contract, which specified only the ``is_active=True``
    narrowing — see the module note in the agent hand-off. It changes no context key and no field
    list.)
    """
    if name not in form.fields:
        return
    current = getattr(form.instance, f"{name}_id", None)
    if current is None:
        return
    narrowed = form.fields[name].queryset
    form.fields[name].queryset = base_queryset.filter(
        Q(pk__in=narrowed.values("pk")) | Q(pk=current)).distinct()


class DutyTariffForm(TenantUniqueMixin, TenantModelForm):
    """The duty schedule row: classification, origin, rate, window and the recoverable counterpart."""

    class Meta:
        model = DutyTariff
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added to the
        # model later; an exclude list fails OPEN and would quietly enrol it into the form.
        #
        # Deliberately ABSENT, and why: `tenant` (stamped by `TenantUniqueMixin.__init__` before
        # validation and by `crud_create` after it — never typed); `number` (auto `DTY-#####`, minted
        # in `TenantNumbered.save()`; nobody types a document number); `created_at` / `updated_at`
        # (automatic — a system `*_at` on a form gets silently TRUNCATED by a DateInput, L22).
        # The model has no other columns, so this list is the whole editable surface.
        fields = ["hs_code", "country_of_origin", "description", "duty_rate_pct",
                  "effective_from", "effective_to", "tax_code", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "tax_code" in self.fields:
            self.fields["tax_code"].queryset = _tax_code_qs(self.tenant)
            _keep_current(self, "tax_code", TaxCode.objects.all())

        # The two help texts the frozen contract names verbatim. Set here rather than on the model so
        # they read as INSTRUCTIONS TO THE TYPIST — the model's own help_text states what the column
        # means, and the difference matters most on `effective_from`, where "required" is a design
        # decision (a NULL member silently disables the unique key in MySQL) rather than a fact about
        # duty schedules.
        if "country_of_origin" in self.fields:
            self.fields["country_of_origin"].help_text = (
                "Leave blank to apply to any country of origin.")
        if "effective_from" in self.fields:
            self.fields["effective_from"].help_text = (
                "Required — a rate with no start date cannot be looked up by transaction date.")

    def clean(self):
        """Re-check the chosen tax code against this workspace at the FORM boundary.

        ``DutyTariff.clean()`` carries the same rule and is the guard at the DATABASE boundary (it
        also covers the shell and the seeder); this repeats it here because **a narrowed ``<select>``
        has never held against a crafted POST** — this form is reachable by any logged-in member of
        any workspace, and an unscoped ``ModelChoiceField`` both displays another tenant's rows and
        ACCEPTS their pk from a hand-built body.

        ``_reject_foreign`` is preferred over an inline check for the second reason its docstring
        gives: it keys the error on a field the FORM has, which is what makes it renderable rather
        than a ``ValueError`` out of ``add_error``.

        Everything else — the date ordering and the HS-code/origin normalisation — stays in the
        model's ``clean()``, once, where it also holds on every non-form write path.

        ``DutyTariff.TENANT_SCOPED_FKS`` is exactly ``("tax_code",)`` — the model constant is passed
        rather than a literal so a pointer added there later is covered here the same day.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, DutyTariff.TENANT_SCOPED_FKS)
        return cleaned
