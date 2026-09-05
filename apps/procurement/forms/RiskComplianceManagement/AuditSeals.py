"""Procurement 6.17 Risk & Compliance Management - the audit seal form.

**One field, and the shortest form in the sub-module for a reason.**

``AuditSealForm`` carries ``note`` and nothing else. Every other column on ``AuditSeal`` is
DERIVED - the id range, the row count, the period, the digest, the previous digest, the chain
digest, the algorithm, who sealed it and the three verification stamps - and every one of them is
declared ``editable=False`` on the model, so Django's ``ModelForm`` machinery would refuse to
render them even if this ``Meta.fields`` list asked for them.

That belt-and-braces is deliberate. **A digest anybody can type is not evidence**: the whole claim
this entity makes is "these entries hash to this value", and a form field that reached the digest
would turn that into "these entries hash to whatever the last person to press Save wanted". So the
exclusion is stated twice - once by ``editable=False`` on the column, once by this whitelist - and
a reviewer reading either one arrives at the same rule.

**There is no create template.** Sealing is a POST button on the register (``auditseal_create``,
``@tenant_admin_required`` + ``@require_POST``) with this single optional note beside it, not a
page you fill in. The pinned context for ``auditseal_list`` carries no ``form`` key precisely
because of that, and the button's POST is validated by binding this form to ``request.POST``.

**And there is no edit form at all** - no ``auditseal_edit``, no ``auditseal_delete`` (contract 3,
model docstring). A seal whose contents can be edited proves nothing, and deleting one breaks the
chain it exists to protect. This is the documented deviation from the CRUD-completeness rule, and
the pages say so where somebody would otherwise look for the buttons.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` - the sub-package is not re-exported until the
# Integrator lands it, and a package-level import would be a star-import cycle at URLconf import
# time.
from apps.procurement.models.RiskComplianceManagement.AuditSeals import AuditSeal


class AuditSealForm(TenantModelForm):
    """Clean the one operator-supplied field on a seal: why it was taken.

    ``TenantModelForm`` rather than a plain ``forms.Form`` so the field inherits the model's own
    255-character limit instead of a second copy of it drifting out of step, and so the widget
    picks up the house ``form-input`` class like every other form in the app. It takes ``tenant=``
    for the same reason every sibling does, though it has no FK to scope with it.

    **This form deliberately cannot save.** The object it describes is built by
    ``AuditSeal.seal_now()``, which is where the range is chosen under a lock, the digest computed
    and the chain linked; a ``form.save()`` would write a seal with an empty digest, a zero range
    and no chain - a row that looks like evidence and is not. Rather than leave that footgun for
    whoever wires the next surface, ``save()`` refuses and says where to go instead.
    """

    class Meta:
        model = AuditSeal
        fields = ["note"]
        labels = {"note": "Why this seal is being taken (optional)"}
        help_texts = {
            "note": "Recorded on the seal exactly as typed, and never used in a confirm dialog "
                    "or a filename. Leave it blank for a routine seal.",
        }
        widgets = {
            "note": forms.TextInput(attrs={
                "placeholder": "e.g. month-end close, or before the external audit visit",
                "maxlength": "255",
            }),
        }

    def clean_note(self):
        """Collapse surrounding whitespace so a note of spaces is stored as no note at all."""
        return (self.cleaned_data.get("note") or "").strip()

    def save(self, commit=True):
        raise NotImplementedError(
            "AuditSealForm validates the note only - it cannot create a seal. Call "
            "AuditSeal.seal_now(tenant, user, note) instead, which picks the id range under a "
            "lock, computes the digest and links the chain.")
