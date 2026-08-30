"""Procurement 6.13 Invoice & Voucher Management — InvoiceMatchVariance form.

**There is deliberately no ModelForm.** A variance is written by the match engine and is not
editable: ``variance_abs`` / ``variance_pct`` are derived, ``detected_at`` is system-set, and
every row is deleted and rebuilt by the next ``run_match()``, so a form over them would be a
form over evidence. The one form here carries the single thing a human supplies when they
dispose of an exception — an optional note on the accept action.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403


class InvoiceVarianceAcceptForm(forms.Form):
    """The optional note taken when AP accepts an exception.

    A plain ``Form``, not a ``ModelForm``: it is bound to an ACTION (POST ``accept/``), not to a
    row, and it writes nothing — the view passes the cleaned note into the audit trail.
    """

    note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )
