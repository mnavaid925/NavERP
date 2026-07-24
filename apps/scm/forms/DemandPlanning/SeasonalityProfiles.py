"""SCM 4.7 Demand Planning — SeasonalityProfile form + index formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import SeasonalityIndex, SeasonalityProfile


class SeasonalityProfileForm(TenantUniqueMixin, TenantModelForm):
    """The profile header.

    EXCLUDES `number` (auto) and `last_derived_at` (stamped by the derive action). `item`, `category`,
    `location` and `cannibalized_category` all carry their own tenant, so the base class scopes every
    dropdown. `derived_from_years` stays ON the form — it is an INPUT to the derive action, not a
    result of it.
    """

    class Meta:
        model = SeasonalityProfile
        fields = ["name", "profile_type", "bucket", "scope", "item", "category", "location",
                  "event_start", "event_end", "uplift_pct", "cannibalization_pct",
                  "cannibalized_category", "promotion_mechanic", "derived_from_years",
                  "is_active", "notes"]
        widgets = {
            "event_start": forms.DateInput(attrs={"type": "date"}),
            "event_end": forms.DateInput(attrs={"type": "date"}),
        }


class SeasonalityIndexForm(TenantModelForm):
    """One period's multiplier. `sample_size` is excluded — it records how much history the derive
    action averaged, and typing it would fake a confidence the curve does not have."""

    class Meta:
        model = SeasonalityIndex
        fields = ["period_number", "period_label", "index_factor"]


SeasonalityIndexFormSet = inlineformset_factory(
    SeasonalityProfile, SeasonalityIndex, form=SeasonalityIndexForm, extra=3, can_delete=True,
)
