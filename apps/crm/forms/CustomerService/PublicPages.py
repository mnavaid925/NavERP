"""CRM 1.4 Customer Service & Support — PublicPages forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403


class PublicSatisfactionForm(forms.Form):
    """CSAT on the public case-status page — a plain Form (no tenant binding)."""

    rating = forms.ChoiceField(choices=[(i, str(i)) for i in range(1, 6)],
                               widget=forms.Select(attrs={"class": "form-select"}))
    comment = forms.CharField(max_length=2000, required=False,
                              widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))


class PublicCommentForm(forms.Form):
    """A public reply on the case-status page / portal — plain Form, length-capped."""

    body = forms.CharField(max_length=4000,
                           widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))
