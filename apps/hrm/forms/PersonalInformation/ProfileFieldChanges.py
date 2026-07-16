"""HRM 3.25 Personal Information — ProfileFieldChanges forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeInfoChangeRequest,
)
from apps.hrm.forms.PersonalInformation._helpers import _ThemedForm


class ProfileFieldChangeForm(_ThemedForm):
    """Employee proposes a new value for ONE sensitive ``EmployeeProfile`` field (or legal name). One
    generic text input drives every sensitive field; ``clean()`` validates the value per the selected
    field (date fields must parse; text fields respect the model column's max_length) so a bad value
    is caught at submission, not later at approval time inside ``apply()``."""

    # Date fields must parse; text fields are length-capped to their EmployeeProfile column widths.
    _DATE_FIELDS = ("date_of_birth", "passport_expiry")
    _MAX_LENGTHS = {"legal_name": 255, "national_id": 100, "national_id_type": 50, "passport_number": 50}

    field_name = forms.ChoiceField(
        choices=[(f, f.replace("_", " ").title()) for f in EmployeeInfoChangeRequest.SENSITIVE_PROFILE_FIELDS])
    new_value = forms.CharField(max_length=255, label="New value",
                                help_text="For date fields (Date of Birth / Passport Expiry) use YYYY-MM-DD.")
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        from django.utils.dateparse import parse_date
        cleaned = super().clean()
        field, value = cleaned.get("field_name"), cleaned.get("new_value")
        if not field or value is None:
            return cleaned
        if field in self._DATE_FIELDS and parse_date(value) is None:
            self.add_error("new_value", "Enter a valid date in YYYY-MM-DD format.")
        max_len = self._MAX_LENGTHS.get(field)
        if max_len and len(value) > max_len:
            self.add_error("new_value", f"This value must be at most {max_len} characters.")
        return cleaned
