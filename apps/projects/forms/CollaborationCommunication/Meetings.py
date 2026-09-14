"""Projects 7.9 — Meeting forms: the meeting, the minutes verb body, and the two child rows.

``MeetingForm`` carries the meeting's working data — ``project``, ``title``, ``kind``,
``scheduled_start``, ``scheduled_end``, ``location``, ``mode`` and ``recurrence``. ``tenant``,
``number``, ``status``, ``minutes``/``minutes_by``/``minutes_at``, ``actual_start``/``actual_end``
and ``created_by`` are all OFF it: the status machine is driven by ``mtg_start``/``mtg_complete``/
``mtg_cancel``, the minutes by ``mtg_minutes`` — each is the ONE writer of its own state, so the
evidence keeps its timestamps (the 7.4/7.6/7.8 verb-written-stamp idiom).

``MeetingMinutesForm`` is ``mtg_minutes``'s body — a PLAIN ``forms.Form``, not a ModelForm (the
``TaskBlockForm`` / ``DefectResolutionForm`` idiom): the verb that binds it also stamps
``minutes_by``/``minutes_at``, so those never appear as fields.

``MeetingAgendaItemForm`` and ``MeetingActionItemForm`` **exclude ``meeting``**: both are reached
from ``meetings/<pk>/agenda/add/`` and ``meetings/<pk>/actions/add/``, so the meeting comes from
the URL and is stamped by the view. A ``meeting`` field on the form would be a second source of
truth that a crafted POST could point at a different meeting.

``TenantUniqueMixin`` is mixed in FIRST on all three ModelForms (the house idiom). ``clean()`` runs
``_reject_foreign`` on the tenant-scoped FKs and **never** on a ``settings.AUTH_USER_MODEL`` FK
(``presenter``, ``assignee``) — users can be tenant-less, and ``TenantModelForm`` already narrows
their ``<select>`` to the workspace (the 7.8 ``assignee`` exemption).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import (TenantModelForm, TenantUniqueMixin, _reject_foreign,
                                         forms)
from apps.projects.models import Meeting, MeetingActionItem, MeetingAgendaItem


class MeetingForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Meeting
        fields = ["project", "title", "kind", "scheduled_start", "scheduled_end", "location",
                  "mode", "recurrence"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned


class MeetingMinutesForm(forms.Form):
    """The ``mtg_minutes`` verb's body: what was decided and agreed.

    Required — a meeting marked as minuted with an empty minute is not a record of anything. The
    form deliberately cannot move ``status``: writing up a meeting is not completing it.
    """

    minutes = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 8}))


class MeetingAgendaItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MeetingAgendaItem
        # `meeting` is deliberately absent — it comes from the URL's meeting pk (see the module
        # docstring), so it is not a field a crafted POST can repoint.
        fields = ["title", "presenter", "duration_minutes", "sequence"]

    def clean(self):
        cleaned = super().clean()
        # No _reject_foreign: the only FK left is `presenter`, a User (the assignee exemption).
        return cleaned


class MeetingActionItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MeetingActionItem
        # `meeting` is deliberately absent — it comes from the URL's meeting pk.
        fields = ["description", "assignee", "due_date", "task"]

    def clean(self):
        cleaned = super().clean()
        # `assignee` is a User FK — exempt. `task` is a tenant-scoped ProjectTask, so re-checked.
        _reject_foreign(self, cleaned, ["task"])
        return cleaned
