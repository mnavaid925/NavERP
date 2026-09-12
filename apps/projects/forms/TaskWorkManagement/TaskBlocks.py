"""Projects 7.8 — TaskBlock forms.

**No ``TaskBlock`` ModelForm exists — by the evidence-row ruling.** Rows are minted ONLY by the
POST-only ``tsk_block`` verb and closed ONLY by ``tsk_unblock``; there are no
``tbk_create``/``tbk_edit``/``tbk_delete`` routes, so there is nothing for a ModelForm to render
and no generic writer that could touch the verb-written stamps. These two are PLAIN
``forms.Form`` bodies (the ``DefectResolutionForm`` idiom): the verb that binds them also writes
the row's ``tenant``/``task`` and its ``blocked_by``/``blocked_at`` (or
``unblocked_by``/``unblocked_at``) stamps, so the task never appears as a form field — it comes
from the URL's task pk, not from user input.

``TaskBlockForm`` is ``tsk_block``'s body: the reason and the ``unblock_criteria`` are both
required — the exit condition is agreed BEFORE the wait starts (bullet 5's exact ask).
``TaskUnblockForm`` is ``tsk_unblock``'s body: the ``resolution_note`` is required — a block
closed without a recorded resolution is not a resolution (the same rule as
``DefectResolutionForm``).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import forms


class TaskBlockForm(forms.Form):
    """The ``tsk_block`` verb's body: why the task is blocked and what must be true to unblock
    it. Both required — a blocker without an agreed exit condition is not a managed block."""

    reason = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))
    unblock_criteria = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))


class TaskUnblockForm(forms.Form):
    """The ``tsk_unblock`` verb's body: how the ``unblock_criteria`` were met. Required — the
    note is what turns the closed row into readable evidence."""

    resolution_note = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))
