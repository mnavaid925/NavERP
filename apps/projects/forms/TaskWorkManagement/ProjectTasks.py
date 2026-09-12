"""Projects 7.8 — ProjectTask execution form.

``TaskExecutionForm`` is the EXECUTION write surface on ``ProjectTask`` — deliberately separate
from 7.2's planning ``TaskForm``: the plan (project, parent, dates, effort, status, sequence) is
7.2's write and this form cannot touch it. ``Meta.fields`` is exactly the six form-writable
execution fields, in order; ``actual_start``/``actual_end`` are unreachable on ANY form by the
model's ``editable=False`` — they are VERB-WRITTEN by ``tsk_start``/``tsk_complete`` only (the
7.4/7.6 stamp idiom), and ``status`` itself moves only through the POST-only verbs.

``assignee`` is the one FK deliberately left OUT of ``_reject_foreign`` (the ``TaskForm.owner``
precedent): it is a User FK and users can be tenant-less (the superuser), so a tenant comparison
would reject legitimate picks — the form therefore defines **no ``clean()`` override** (nothing
to re-check). Its choices still come from the tenant's users via ``TenantModelForm``'s
auto-scoping, exactly as ``owner``'s do on the planning form.

There is no ``TaskBlock`` ModelForm anywhere in this package — the block bodies are plain
``forms.Form`` in ``TaskBlocks.py`` (the evidence-row ruling).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models import ProjectTask


class TaskExecutionForm(TenantUniqueMixin, TenantModelForm):
    """The ``tsk_execute`` page's body — who does the task, how urgently, how far along.

    Every field here is execution state on the task row itself; the plan fields stay on 7.2's
    ``TaskForm`` and the stamps stay with the verbs. ``assignee`` is intentionally not
    ``_reject_foreign``-checked — users can be tenant-less (the ``owner`` precedent above).
    """

    class Meta:
        model = ProjectTask
        fields = [
            "assignee", "priority", "moscow", "is_urgent", "is_important", "percent_complete",
        ]
