"""Procurement 6.1 User Dashboard & Portal — WidgetPreferences model.

**Personalized Overview** bullet says "customizable widgets", so the customization has to be a
stored fact per user, not a hard-coded layout: one row per (tenant, user, widget) with an
``is_visible`` flag. Absence of a row MEANS "visible" — the default overview is the full set and
a user who never touched the toggle form has no rows at all, so the seeder seeds none.

The registry lives here as ``WIDGETS`` (key -> label) because the model is the one place both the
toggle form and the overview view can import without a circular dependency; adding a widget to
the dashboard means adding it to this dict and to the overview template's section list.
"""
from django.conf import settings
from django.db import transaction

from apps.procurement.models._base import *  # noqa: F401,F403


class WidgetPreference(TenantOwned):
    """One user's show/hide choice for one overview widget."""

    #: key -> label. The ORDER of this dict is the order the widgets render in.
    WIDGETS = {
        "approvals": "Pending Approvals",
        "alerts": "Task & Alert Center",
        "spend": "Spend Summary",
        "deadlines": "Approaching Deadlines",
        "activity": "Recent Activity",
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="procurement_widget_prefs")
    widget_key = models.CharField(max_length=40)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["user_id", "id"]
        unique_together = ("tenant", "user", "widget_key")

    def clean(self):
        if self.widget_key not in self.WIDGETS:
            from django.core.exceptions import ValidationError
            raise ValidationError({"widget_key": "Unknown widget."})

    def __str__(self):
        return f"{self.user} · {self.WIDGETS.get(self.widget_key, self.widget_key)} · " \
               f"{'shown' if self.is_visible else 'hidden'}"

    # -- helpers ------------------------------------------------------------------------------

    @classmethod
    def hidden_keys(cls, tenant, user):
        """The set of widget keys this user has explicitly HIDDEN (empty for almost everyone)."""
        if not getattr(user, "pk", None):
            return set()
        return set(cls.objects.filter(tenant=tenant, user=user, is_visible=False)
                   .values_list("widget_key", flat=True))

    @classmethod
    def save_choices(cls, tenant, user, visible_keys):
        """Persist one row per widget from a submitted checkbox set, replacing prior choices.

        Deliberately NOT audited: a widget toggle is a personal layout preference, not business
        data — an AuditLog row per click would spam the very activity feed this module renders.
        """
        # One transaction around the whole replacement: a bare update_or_create loop can race the
        # (tenant, user, widget_key) unique_together mid-loop and leave a half-applied layout.
        with transaction.atomic():
            for key in cls.WIDGETS:
                cls.objects.update_or_create(
                    tenant=tenant, user=user, widget_key=key,
                    defaults={"is_visible": key in visible_keys})
