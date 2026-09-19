"""core — 0.10's mechanisms: setting resolution, feature resolution, custom-field validation.

Kept out of the views so each rule is testable with fixed inputs, and so the resolution ORDER is
readable in one place rather than implied by whichever view happens to read a value.

Three rules worth stating explicitly, because each is a place the convenient answer differs from the
correct one:

* `get_setting()` returns the DEFINITION's default when a tenant has no override — and reports which
  of the two it read. A tenant with no row is not a missing setting; it is a tenant taking the
  default, and a caller that cannot tell the difference cannot show it on a page.
* `is_feature_enabled()` returns False for an unknown key. An unrecognised flag is not an enabled
  feature: defaulting to True would mean a typo in a template silently ships a half-built feature.
* `validate_custom_value()` validates against the DEFINITION, so a choice value not in the list, or a
  decimal that is not a decimal, is refused on write rather than stored and mis-rendered later.
"""
import datetime
import re
from decimal import Decimal, InvalidOperation

from .models import CustomFieldDefinition, FeatureFlag, SettingDefinition, SettingValue


class SettingResult:
    """A resolved setting plus where it came from. `is_default` is what a page shows the operator."""

    __slots__ = ("key", "value", "raw", "is_default", "definition")

    def __init__(self, key, value, raw, is_default, definition):
        self.key = key
        self.value = value
        self.raw = raw
        self.is_default = is_default
        self.definition = definition

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<SettingResult {self.key}={self.value!r} default={self.is_default}>"


#: Type coercion for the stored string. Kept small and explicit: an uncoercible value falls back to
#: the raw string rather than raising, because a bad stored value must not 500 a page that merely
#: reads a setting.
def _coerce(value_type, raw):
    if raw is None:
        return None
    if value_type == "integer":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if value_type == "decimal":
        try:
            return Decimal(str(raw))
        except (TypeError, InvalidOperation):
            return raw
    if value_type == "boolean":
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if value_type == "date":
        try:
            return datetime.date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            return raw
    return raw


def get_setting(tenant, key, default=None):
    """Resolve one setting for one tenant.

    Resolution order: the tenant's override, else the definition's default, else `default`. Returns a
    `SettingResult` so the caller can say "showing the default" rather than pretending it was set.
    An unknown key returns a result with `definition=None` and the caller's `default` — it never
    invents a definition, because a setting that is not in the registry is not a setting.
    """
    definition = SettingDefinition.objects.filter(key=key).first()
    if definition is None:
        return SettingResult(key, default, None, True, None)
    override = SettingValue.objects.filter(tenant=tenant, definition=definition).first()
    if override is not None:
        return SettingResult(key, _coerce(definition.value_type, override.value), override.value,
                             False, definition)
    return SettingResult(key, _coerce(definition.value_type, definition.default_value),
                         definition.default_value, True, definition)


def is_feature_enabled(tenant, key, user=None):
    """Resolve one feature flag for one tenant, optionally for one user.

    Order:
      1. no row, or the row is off            -> False
      2. `applies_to_plan` set and the tenant's plan differs -> False
      3. `exempt_roles` non-empty and the user's role is not in it -> False
      4. otherwise -> True

    Step 3 is why `user` is a parameter: a role-scoped flag is enabled for the workspace but visible
    to a subset, and a caller that does not pass the user gets the workspace-level answer.
    """
    if tenant is None or not key:
        return False
    flag = FeatureFlag.objects.filter(tenant=tenant, key=key).first()
    if flag is None or not flag.is_enabled:
        return False
    if flag.applies_to_plan and getattr(tenant, "plan", None) != flag.applies_to_plan:
        return False
    role_ids = set(flag.exempt_roles.values_list("pk", flat=True))
    if role_ids and (user is None or getattr(user, "role_id", None) not in role_ids):
        return False
    return True


def validate_custom_value(definition, raw):
    """Validate one raw value against its definition. Returns (ok, coerced, error_message)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if definition.is_required:
            return False, None, "This field is required."
        return True, None, ""

    if definition.field_type == "integer":
        try:
            return True, int(raw), ""
        except (TypeError, ValueError):
            return False, None, "Enter a whole number."
    if definition.field_type == "decimal":
        try:
            return True, str(Decimal(str(raw))), ""
        except (TypeError, InvalidOperation):
            return False, None, "Enter a number."
    if definition.field_type == "boolean":
        return True, str(raw).strip().lower() in ("1", "true", "yes", "on"), ""
    if definition.field_type == "date":
        try:
            return True, datetime.date.fromisoformat(str(raw)).isoformat(), ""
        except (TypeError, ValueError):
            return False, None, "Enter a date as YYYY-MM-DD."
    if definition.field_type == "choice":
        allowed = [str(c) for c in (definition.choices or [])]
        if str(raw) not in allowed:
            return False, None, f"Choose one of: {', '.join(allowed) or '(none configured)'}."
        return True, str(raw), ""
    # text / textarea
    if definition.validation_regex:
        try:
            if not re.fullmatch(definition.validation_regex, str(raw)):
                return False, None, "That value does not match the required format."
        except re.error:
            # A broken regex on the definition must not block every write — the definition is the
            # thing that is wrong, and the page surfaces it rather than failing the user's save.
            return True, str(raw), ""
    return True, str(raw), ""


#: Models that mint a prefix through their OWN save() with a hardcoded literal rather than declaring
#: `NUMBER_PREFIX` on a `TenantNumbered` subclass. They are invisible to `prefix_usage()`'s scan, so
#: they are listed here explicitly and surfaced on the board.
#:
#: `tenants.SubscriptionInvoice` is the one real case: it predates `TenantNumbered` and its `save()`
#: calls `next_number(SubscriptionInvoice, self.tenant, "SINV")` directly. Found by probing the
#: reconciliation board rather than trusting it — the board was reporting SINV as "configured but
#: nothing mints it", which was a FALSE NEGATIVE.
LITERAL_PREFIX_MODELS = {
    "SINV": ["tenants.SubscriptionInvoice"],
}


def prefix_usage():
    """Reconcile configured prefixes against the prefixes models actually mint.

    Returns:
      * `used`            — prefixes both configured and minted;
      * `configured_only` — a scheme whose prefix nothing detected mints (see the blind spot below);
      * `model_only`      — a prefix minted with no scheme behind it (undocumented numbering);
      * `model_prefixes`  — prefix -> the models declaring it via `NUMBER_PREFIX`.

    The last two are the whole reason this exists: both are silent, and both are the kind of thing an
    operator only discovers from a document number that does not look like the others.

    **Blind spot, stated rather than hidden.** The scan reads the `NUMBER_PREFIX` class attribute, so
    it covers every `TenantNumbered` subclass — which is essentially all numbering in the repo. It
    does NOT see a model that mints a prefix through its own `save()` with a hardcoded literal;
    `LITERAL_PREFIX_MODELS` lists those, and they are merged in here so the answer stays correct
    rather than merely plausible.
    """
    from django.apps import apps as django_apps
    from .models import NumberingScheme

    model_prefixes = {}
    for model in django_apps.get_models():
        prefix = getattr(model, "NUMBER_PREFIX", None)
        if prefix and getattr(model._meta, "abstract", False) is False:
            model_prefixes.setdefault(prefix, []).append(
                f"{model._meta.app_label}.{model.__name__}")
    for prefix, labels in LITERAL_PREFIX_MODELS.items():
        model_prefixes.setdefault(prefix, [])
        for label in labels:
            if label not in model_prefixes[prefix]:
                model_prefixes[prefix].append(label)
    configured = set(NumberingScheme.objects.values_list("prefix", flat=True))
    minted = set(model_prefixes)
    return {
        "used": sorted(configured & minted),
        "configured_only": sorted(configured - minted),
        "model_only": sorted(minted - configured),
        "model_prefixes": model_prefixes,
        "literal_prefixes": sorted(LITERAL_PREFIX_MODELS),
    }
