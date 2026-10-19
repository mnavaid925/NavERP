"""Sales 8.12 — Forms for `WinLossDebrief`."""
from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesAnalytics.WinLossDebriefs import WinLossDebrief


class WinLossDebriefForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = WinLossDebrief
        fields = [
            "opportunity",
            "outcome",
            "primary_reason",
            "account",
            "interviewer",
            "action_owner",
            "communication_log",
            "debriefed_on",
            "interview_channel",
            "decision_drivers",
            "buyer_quote",
            "counterfactual",
            "feedback_team",
            "action_items",
            "actioned_on",
            "status",
            "notes",
        ]
        widgets = {
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "outcome": forms.Select(attrs={"class": "form-select"}),
            "primary_reason": forms.Select(attrs={"class": "form-select"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "interviewer": forms.Select(attrs={"class": "form-select"}),
            "action_owner": forms.Select(attrs={"class": "form-select"}),
            "communication_log": forms.Select(attrs={"class": "form-select"}),
            "debriefed_on": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "interview_channel": forms.Select(attrs={"class": "form-select"}),
            "decision_drivers": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 4,
                    "placeholder": '[{"driver": "…", "sentiment": "negative", "weight": 4, "quote": "…"}]',
                }
            ),
            "buyer_quote": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "counterfactual": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "feedback_team": forms.Select(attrs={"class": "form-select"}),
            "action_items": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "actioned_on": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean_decision_drivers(self, value):
        """Validate the *shape* of the decision-driver list.

        Django's auto-generated ``forms.JSONField`` has already rejected a
        malformed JSON document by the time this runs; what is left is the
        structural contract: a list of driver objects, each with a non-empty
        ``driver`` name, a ``sentiment`` of positive/negative, a ``weight``
        between 1 and 5 (defaulting to 1) and an optional ``quote``.
        """
        if value is None:
            # Blank textarea -> no drivers. The column is NOT NULL, so an empty
            # list (not None) is what must reach the model.
            return []
        if not isinstance(value, list):
            raise ValidationError("Decision drivers must be a JSON list of driver objects.")

        cleaned = []
        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise ValidationError(f"Decision driver {index} must be a JSON object.")

            driver = item.get("driver")
            if not isinstance(driver, str) or not driver.strip():
                raise ValidationError(
                    f"Decision driver {index} needs a non-empty 'driver' name."
                )

            sentiment = item.get("sentiment")
            if sentiment not in {"positive", "negative"}:
                raise ValidationError(
                    f"Decision driver {index} needs a 'sentiment' of 'positive' or 'negative'."
                )

            weight = item.get("weight", 1)
            if isinstance(weight, bool) or not isinstance(weight, int) or not 1 <= weight <= 5:
                raise ValidationError(
                    f"Decision driver {index} needs a 'weight' whole number between 1 and 5."
                )

            quote = item.get("quote", "")
            if quote is None:
                quote = ""
            if not isinstance(quote, str):
                raise ValidationError(f"Decision driver {index} needs a text 'quote'.")

            cleaned.append(
                {
                    "driver": driver.strip(),
                    "sentiment": sentiment,
                    "weight": weight,
                    "quote": quote,
                }
            )
        return cleaned

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(
            self,
            cleaned_data,
            [
                "opportunity",
                "outcome",
                "primary_reason",
                "account",
                "interviewer",
                "action_owner",
                "communication_log",
            ],
        )
        return cleaned_data
