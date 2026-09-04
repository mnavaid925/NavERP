"""Procurement 6.17 Risk & Compliance Management — screening + hit forms.

Three shapes:

* ``ComplianceScreeningForm`` — capture or amend one lookup. Everything the WORKFLOW owns is
  excluded: ``status`` (the three verbs move it), the two derived hit counters, every ``*_by`` /
  ``*_at`` stamp, ``decision_note`` and ``suspension``. ``tenant`` and ``number`` are the
  system's. ``screened_by`` is stamped by the view from ``request.user`` — a form field for "who
  ran this check" is an attribution anybody could forge.
* ``ScreeningHitForm`` — capture one potential match. ``screening`` is NOT a field: it comes from
  the URL, and accepting it from a POST would be a straightforward IDOR onto another workspace's
  screening. Every adjudication column is excluded — that is ``dispose()``'s job.
* ``ScreeningHitDispositionForm`` — a plain ``forms.Form`` that validates the adjudication POST.
  Offers ONLY the terminal dispositions (never ``open``), and the note is REQUIRED for every one
  of them, ``false_positive`` included.

``method`` is narrowed to ``SELECTABLE_METHODS`` in ``__init__`` AND re-checked in
``clean_method``: ``api_feed`` stays in the model's vocabulary so a future list connector writes
the same rows with no migration, but a human — or a hand-crafted POST — may not claim an
automated feed ran.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.Screenings import (
    DISPOSITION_CHOICES, METHOD_CHOICES, SELECTABLE_METHODS, TERMINAL_DISPOSITIONS,
    ComplianceScreening, ScreeningHit)


class ComplianceScreeningForm(TenantUniqueMixin, TenantModelForm):
    """Capture or amend one sanctions / denied-party lookup.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``ComplianceScreening.clean()`` compares each chosen FK's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected as
    cross-tenant.
    """

    class Meta:
        model = ComplianceScreening
        fields = ["party", "list_source", "checkpoint", "method", "screened_on", "list_as_of",
                  "reference", "result", "match_threshold", "threshold_rationale",
                  "next_rescreen_on", "evidence", "notes"]
        widgets = {
            # The three DateFields need no widget here: TenantModelForm replaces every DateField
            # widget with a type="date" input of its own, so declaring one would be discarded.
            "threshold_rationale": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        # ``api_feed`` is deliberately absent: it exists so a future connector can write these
        # rows unchanged, and a person filling this form did not run an automated feed.
        self.fields["method"].choices = [
            (value, label) for value, label in METHOD_CHOICES if value in SELECTABLE_METHODS]

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either.
            for name in ("party", "evidence"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        from apps.core.models import Document, Party

        # TenantModelForm has already scoped both of these to the tenant (each target model
        # carries a ``tenant`` column). The narrowing below is the EXTRA rule per axis — only
        # suppliers can be screened, and evidence is listed newest-first — not the tenant
        # boundary itself.
        self.fields["party"].queryset = (
            Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))
        self.fields["evidence"].queryset = (
            Document.objects.filter(tenant=tenant).order_by("-uploaded_at", "-id"))
        self.fields["evidence"].empty_label = "- none attached -"

    def clean_method(self):
        """Refuse a method a human may not claim, whatever the POST said."""
        method = self.cleaned_data.get("method")
        if method not in SELECTABLE_METHODS:
            raise ValidationError(
                "Choose how the lookup was actually performed. An automated list feed is not "
                "connected yet and cannot be recorded by hand.")
        return method

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, ["party", "evidence"])
        return cleaned


class ScreeningHitForm(TenantModelForm):
    """Capture one potential match a screening returned.

    Deliberately NOT a ``TenantUniqueMixin`` subclass: ``ScreeningHit`` is tenant-LESS (the
    parent FK is the scope), so there is no ``instance.tenant_id`` for the mixin to stamp and
    reading one would raise. ``TenantModelForm`` alone is right here — it supplies the widget
    styling and the ``tenant=`` signature every other form in this app has.

    There is no ``_reject_foreign`` call and that is not an omission: after the exclusions below
    this form carries no FK at all. ``screening`` comes from the URL and is resolved by the view
    with ``screening__tenant=request.tenant`` — the one place that boundary belongs.
    """

    class Meta:
        model = ScreeningHit
        fields = ["matched_name", "matched_list", "match_score", "match_type", "entry_reference",
                  "program", "country", "remarks"]
        widgets = {
            "remarks": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean_matched_name(self):
        name = (self.cleaned_data.get("matched_name") or "").strip()
        if not name:
            raise ValidationError("A hit must name the list entry it matched.")
        return name


class ScreeningHitDispositionForm(forms.Form):
    """Validate one adjudication POST.

    Only TERMINAL dispositions are offered — re-opening an adjudicated hit is not a thing this
    module does. The note is REQUIRED for every disposition including ``false_positive``: a
    cleared false positive with no recorded reasoning is indistinguishable from a check that was
    never performed, which is exactly the finding a recordkeeping examination writes up.
    """

    disposition = forms.ChoiceField(
        choices=[(value, label) for value, label in DISPOSITION_CHOICES
                 if value in TERMINAL_DISPOSITIONS],
        label="Disposition",
        widget=forms.Select(attrs={"class": "form-select"}))
    disposition_note = forms.CharField(
        required=True, label="Reasoning",
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3,
                                     "placeholder": "Why is this the right call?"}),
        help_text="Required for every disposition, false positives included.")

    def __init__(self, *args, tenant=None, **kwargs):
        # ``tenant`` is accepted and held so this form has the same call signature as every other
        # form in the app; nothing here is tenant-scoped, and a forms.Form that REJECTED tenant=
        # would be the one needing a special case at the call site.
        self.tenant = tenant
        super().__init__(*args, **kwargs)

    def clean_disposition_note(self):
        note = (self.cleaned_data.get("disposition_note") or "").strip()
        if not note:
            raise ValidationError("Record why this hit was adjudicated the way it was.")
        return note
