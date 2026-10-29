from django import forms

from apps.ecommerce.models.Personalization.ShopperBehaviorEvents import ShopperBehaviorEvent


class ShopperBehaviorEventFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-input", "placeholder": "Session key, event #, user..."}
        ),
    )
    event_type = forms.ChoiceField(
        choices=[("", "All Event Types")] + ShopperBehaviorEvent.EVENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
