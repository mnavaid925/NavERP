"""Procurement 6.1 User Dashboard & Portal — overview widget toggle form."""
from django import forms

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.models import WidgetPreference


class WidgetToggleForm(forms.Form):
    """Which overview widgets the signed-in user wants to see.

    A plain checkbox multiple-choice over the model's own registry, so the form can never offer a
    key the model does not know. The view persists through ``WidgetPreference.save_choices`` —
    absence of a row still MEANS visible; only an explicit uncheck writes ``is_visible=False``.
    """

    widgets = forms.MultipleChoiceField(
        required=False,
        choices=[(key, label) for key, label in WidgetPreference.WIDGETS.items()],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check"}),
        label="Show on my overview")

    def __init__(self, *args, initial_visible=(), **kwargs):
        super().__init__(*args, **kwargs)
        if "widgets" in self.initial or initial_visible:
            self.fields["widgets"].initial = list(initial_visible)
