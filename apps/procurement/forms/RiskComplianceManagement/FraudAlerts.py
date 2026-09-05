"""Procurement 6.17 Risk & Compliance Management — fraud alert forms.

Three shapes:

* ``FraudAlertForm`` — the HAND-RAISE path, for what no rule can see. A tip-off, a pattern
  somebody noticed, a supplier relationship the system has no column for. It is deliberately
  the same register the scan writes into, so a human finding and a machine finding get the same
  triage, the same disposition vocabulary and the same audit trail.
* ``FraudScanForm`` — the scan window and rule selection.
* ``FraudDispositionForm`` — validates the four disposition POSTs.

**The exclusions are the contract.** Nothing on the alert that the SYSTEM or the WORKFLOW owns
is offered here and none of it can be posted: ``tenant`` and ``number`` are system-stamped,
``dedupe_key`` and ``detected_at`` belong to detection, and ``status`` / ``resolution_note`` /
``resolved_by`` / ``resolved_at`` / ``suspension`` move only through the four verb methods on the
model. ``severity`` IS on the form on purpose — it is a default the rule stamped, not a verdict,
and a reviewer must be able to re-grade a row the engine over-called.
"""
from datetime import date

from django.utils import timezone

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.FraudAlerts import (
    MAX_SCAN_WINDOW_DAYS, RULE_CHOICES, FraudAlert)

#: The seven tenant-scoped source pointers ``_reject_foreign`` re-checks. ``assigned_to`` is NOT
#: in this list: ``TenantModelForm`` already narrows it to this workspace's users, and a blanket
#: reject-foreign on it would refuse a tenant-less superuser the model deliberately allows.
_POINTER_FKS = ["vendor", "related_party", "requisition", "purchase_order", "supplier_invoice",
                "approval", "screening"]

#: What a disposition POST's ``action`` may say, mapped to (verb method, note required).
#: Anything else is refused HERE rather than reaching the model (L11 — it arrives from a POST).
DISPOSITION_ACTIONS = {
    "investigate": ("investigate", False),
    "substantiate": ("substantiate", True),
    "unsubstantiate": ("unsubstantiate", True),
    "refer": ("refer", True),
}

#: Only ``substantiate`` may carry a block link — the other three are not decisions that stop a
#: supplier trading, and offering the picker on them would imply they were.
_SUSPENSION_ACTIONS = ("substantiate",)


class FraudAlertForm(TenantUniqueMixin, TenantModelForm):
    """Raise or amend one fraud alert by hand.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``FraudAlert.clean()`` compares each chosen FK's tenant against ``self.tenant_id``, and
    without the stamp every CREATE would be falsely rejected as cross-tenant.
    """

    class Meta:
        model = FraudAlert
        fields = ["rule", "severity", "document_date", "amount", "detail", "matched_on",
                  "assigned_to", "vendor", "related_party", "requisition", "purchase_order",
                  "supplier_invoice", "approval", "screening"]
        widgets = {
            # document_date needs no widget here: TenantModelForm replaces every DateField widget
            # with a type="date" input of its own, so declaring one would be discarded.
            "detail": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
            "matched_on": forms.TextInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        # ``amount`` is nullable and meaningfully so — a conflict-of-interest overlap has no
        # amount. Saying that on the field stops somebody typing 0 to fill the box.
        self.fields["amount"].required = False
        self.fields["document_date"].required = True

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either.
            for name in _POINTER_FKS + ["assigned_to"]:
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        from apps.core.models import Party

        # TenantModelForm has already scoped each of these to the tenant (every target model
        # carries a ``tenant`` column, User included). The narrowing below is the EXTRA rule per
        # axis — suppliers on one side, anybody on the other, newest documents first — never the
        # tenant boundary, which is re-checked in clean() regardless.
        self.fields["vendor"].queryset = (
            Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))
        # NOT narrowed to employees: the second party of an overlap is an employee in rule 1 and
        # a SECOND SUPPLIER in rule 3, so restricting it either way would make one of the two
        # rules un-raisable by hand.
        self.fields["related_party"].queryset = (
            Party.objects.filter(tenant=tenant).order_by("name"))
        for name in ("requisition", "purchase_order", "supplier_invoice", "approval",
                     "screening"):
            self.fields[name].queryset = self.fields[name].queryset.order_by("-id")
            self.fields[name].empty_label = "- none -"
        self.fields["vendor"].empty_label = "- none -"
        self.fields["related_party"].empty_label = "- none -"
        self.fields["assigned_to"].queryset = (
            self.fields["assigned_to"].queryset.order_by("username"))
        self.fields["assigned_to"].empty_label = "- nobody yet -"

    def clean_document_date(self):
        """Refuse a fact dated in the future.

        ``document_date`` is the date of the FACT, never the detection date, so a future one is
        either a typo or an attempt to park an alert outside every ageing bucket.
        """
        value = self.cleaned_data.get("document_date")
        if value and value > timezone.localdate():
            raise ValidationError(
                "An alert records something that already happened. Enter the date of the fact, "
                "not a date in the future.")
        return value

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped pointer against the workspace: the narrowed <select>
        # above is presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, _POINTER_FKS)

        # The model's clean() says the same thing, but saying it here keys the error onto a field
        # the FORM has, so it renders next to the control instead of as a page-level non-field
        # error the operator has to guess the cause of.
        if not any(cleaned.get(name) for name in _POINTER_FKS):
            self.add_error("vendor", ValidationError(
                "Point the alert at something — a supplier, a requisition, an order, an invoice, "
                "an approval or a screening. An accusation with no evidence cannot be reviewed."))
        return cleaned


class FraudScanForm(forms.Form):
    """The scan window and which rules to run.

    A plain ``forms.Form`` rather than hand-parsing ``request.POST``: ``DateField`` and
    ``MultipleChoiceField`` already refuse junk in exactly the places hand-parsing gets it wrong
    (L11/L35), and the window cap below needs two real ``date`` objects to subtract.
    """

    start = forms.DateField(
        required=True, label="From",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"},
                               format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
        help_text="Inclusive. The scan reads facts dated on or after this day.")
    end = forms.DateField(
        required=True, label="To",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"},
                               format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
        help_text="EXCLUSIVE. The scan stops before this day, so two adjacent windows never "
                  "double-count the boundary.")
    rules = forms.MultipleChoiceField(
        required=False, choices=RULE_CHOICES, label="Rules",
        widget=forms.CheckboxSelectMultiple,
        help_text="Leave every box clear to run all six.")

    def __init__(self, *args, tenant=None, **kwargs):
        # ``tenant`` is accepted and held so this form has the same call signature as every other
        # form in the app; nothing here is tenant-scoped, and a forms.Form that REJECTED tenant=
        # would be the one needing a special case at the call site.
        self.tenant = tenant
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start"), cleaned.get("end")

        # L35b — the prerequisite gets its OWN REJECTION branch, not a silent fall-through. An
        # elif chain whose bounds are all conditional reports "valid" when a bound is missing,
        # which here would mean running an UNBOUNDED scan because one date failed to parse. Both
        # fields are required=True, so field-level validation has normally already rejected it;
        # the belt to that braces is the explicit error below, which guarantees this form can
        # never come back valid without a usable window no matter how the fields are subclassed
        # or overridden later.
        if not isinstance(start, date) or not isinstance(end, date):
            if not self.errors:
                self.add_error(None, ValidationError(
                    "Enter both ends of the window. A scan with no bounds is not a narrower "
                    "scan — it is every record in the workspace."))
            return cleaned

        if end <= start:
            self.add_error("end", ValidationError(
                "The end of the window has to come after its start. The end date is exclusive, "
                "so a single-day scan runs from that day to the next."))
        elif (end - start).days > MAX_SCAN_WINDOW_DAYS:
            # Measured ARITHMETICALLY. Building the range to count it would be exactly the
            # payload this cap exists to refuse (L40 §1).
            self.add_error("end", ValidationError(
                "That window covers %(span)s days and the cap is %(cap)s. A scan is a click, not "
                "a background job — narrow the window and run it twice.",
                params={"span": (end - start).days, "cap": MAX_SCAN_WINDOW_DAYS}))
        return cleaned

    def selected_rules(self):
        """The rules to run, or ``None`` for all of them.

        ``None`` rather than the full list so the model's own "unknown names are ignored" path is
        never asked to interpret an empty selection as "run nothing".
        """
        chosen = self.cleaned_data.get("rules") or []
        return list(chosen) or None


class FraudDispositionForm(forms.Form):
    """Validate one disposition POST — investigate, substantiate, unsubstantiate or refer.

    The three TERMINAL actions require a note. A closure with no recorded reasoning is
    indistinguishable from an alert nobody looked at, which is exactly the finding an audit
    writes up — and on this register the closure being explained is an accusation being dropped.

    ``suspension`` is offered only alongside ``substantiate`` and is optional even there. It
    LINKS a block somebody already raised in the 6.4 register; it never raises one. Parking a
    question and stopping a supplier trading are different decisions.
    """

    action = forms.ChoiceField(
        choices=[(value, value) for value in DISPOSITION_ACTIONS],
        label="Decision",
        widget=forms.HiddenInput())
    resolution_note = forms.CharField(
        required=False, label="Reasoning",
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3,
                                     "placeholder": "What did you find, and what happens now?"}),
        help_text="Required for every closing decision, including a false positive.")
    suspension = forms.ModelChoiceField(
        required=False, queryset=None, label="Link a vendor block",
        empty_label="- no block linked -",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Optional. A block already raised in the vendor suspension register. Recording "
                  "it here links the two; it does not raise or lift anything.")

    def __init__(self, *args, tenant=None, alert=None, **kwargs):
        self.tenant = tenant
        self.alert = alert
        super().__init__(*args, **kwargs)

        from apps.procurement.models.VendorManagement.VendorSuspensions import VendorSuspension

        # Narrowed to THIS workspace and THIS alert's supplier. A block against a different
        # supplier is not evidence about this one, and the boundary is re-checked in clean()
        # because a narrowed <select> is UX rather than an authorization gate.
        queryset = VendorSuspension.objects.none()
        if tenant is not None and alert is not None and alert.vendor_id:
            queryset = (VendorSuspension.objects
                        .filter(tenant=tenant, supplier_id=alert.vendor_id)
                        .select_related("supplier")
                        .order_by("-starts_on", "-id"))
        self.fields["suspension"].queryset = queryset

    def clean_resolution_note(self):
        return (self.cleaned_data.get("resolution_note") or "").strip()

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")

        # L35b again — the prerequisite is its own branch. Without it, a missing/unknown action
        # would skip every rule below and the form would report VALID, which is how a POST with
        # no action at all ends up being treated as an approved disposition.
        if action not in DISPOSITION_ACTIONS:
            self.add_error("action", ValidationError(
                "Choose whether to investigate this alert, substantiate it, mark it a false "
                "positive, or refer it on."))
            return cleaned

        _verb, note_required = DISPOSITION_ACTIONS[action]
        if note_required and not cleaned.get("resolution_note"):
            self.add_error("resolution_note", ValidationError(
                "Record what you found. Closing a fraud alert with no stated reasoning is "
                "indistinguishable from an alert nobody looked at."))

        suspension = cleaned.get("suspension")
        if suspension is not None:
            if action not in _SUSPENSION_ACTIONS:
                self.add_error("suspension", ValidationError(
                    "A vendor block can only be linked to a substantiated alert."))
            elif self.tenant is None or suspension.tenant_id != self.tenant.pk:
                self.add_error("suspension", "That record belongs to another workspace.")
            elif self.alert is not None and suspension.supplier_id != self.alert.vendor_id:
                self.add_error("suspension", ValidationError(
                    "That block is against a different supplier."))
        return cleaned

    @property
    def verb_name(self):
        """The model method this POST asks for, or ``None`` — read only after ``is_valid()``."""
        action = self.cleaned_data.get("action")
        return DISPOSITION_ACTIONS[action][0] if action in DISPOSITION_ACTIONS else None
