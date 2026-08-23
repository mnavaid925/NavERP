"""Inventory 5.9 Order Management & Fulfillment — wave + membership forms.

A wave header is planner configuration: no workflow fields (status/released_at/closed_at
are system-set by the verbs), so they stay off the form entirely. ``TenantUniqueMixin``
stamps ``instance.tenant`` during CREATE validation so the models' cross-tenant
``clean()`` cannot falsely reject before the CRUD helper assigns the real tenant (SEC-1
two-jobs rule), and ``_reject_foreign`` re-checks every chosen FK where it renders as a
field error — a narrowed ``<select>`` is UX, not an authorization boundary. There is
deliberately NO queryset narrowing beyond that: both scm targets carry their own
``tenant``, so ``TenantModelForm`` already scopes them (5.4 precedent).

The membership form is an inline detail-page add-row, not a standalone page [FROZEN]:
the view stamps ``instance.wave`` (and the mixin stamps ``tenant``) BEFORE ``is_valid()``
so model validation sees a fully-parented row — an unstamped parent would make the
unique_together check silently skip or the clean() guard read nothing.
"""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models.FulfillmentOrchestration import (
    FulfillmentWave,
    FulfillmentWaveOrder,
)


class FulfillmentWaveForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit one planned wave. Status moves only through the release/close/cancel
    verbs — never through this form."""

    class Meta:
        model = FulfillmentWave
        fields = ["description", "location", "carrier", "ship_method",
                  "planned_ship_date", "cutoff_at", "priority", "criteria_text", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["location", "carrier"])
        return cleaned


class FulfillmentWaveOrderForm(TenantUniqueMixin, TenantModelForm):
    """Add ONE sales order to the wave stamped onto ``instance.wave`` by the view.

    The release lock is enforced twice on this path — here for early, readable feedback
    and again in ``FulfillmentWaveOrder.clean()`` for non-form writers — because both
    fire inside the same ``is_valid()`` call only when the view pre-check passed but the
    row flipped concurrently. ``wave`` is NOT a form field — this form never renders a
    wave picker."""

    class Meta:
        model = FulfillmentWaveOrder
        fields = ["sales_order"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["sales_order"])
        if self.instance.wave_id and self.instance.wave.status != "planned":
            self.add_error(
                None,
                f"{self.instance.wave.number} is "
                f"{self.instance.wave.get_status_display().lower()} — its membership can "
                f"no longer be changed.")
        # unique_together ("wave","sales_order") never form-validates — "wave" is not a
        # form field, so validate_unique skips the constraint entirely and the second
        # identical POST dies as an uncaught IntegrityError on save(). Check it here,
        # where it renders as a readable form error instead of a 500.
        sales_order = cleaned.get("sales_order")
        if sales_order is not None and self.instance.wave_id:
            dupes = FulfillmentWaveOrder.objects.filter(
                wave_id=self.instance.wave_id, sales_order=sales_order)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error("__all__",
                               "That sales order is already in this wave.")
        return cleaned
