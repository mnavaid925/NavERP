"""Procurement 6.8 Contract Management — contract authoring + signer forms.

The authoring form writes the SCM-owned ``SupplierContract`` spine row (the same
"Module 6 writes into the spine" posture as 6.1's Quick Requisition Entry): a draft
agreement is created from the clause library, never re-modelled. Status and the
lifecycle verbs stay scm's — this form only sets the header terms a buyer drafts.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import ContractClauseLink, ContractSigner
from apps.scm.models import SupplierContract


def _supplier_parties(tenant):
    """Parties this tenant can buy from — the exact 6.5 helper rule (supplier OR vendor)."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


class ContractAuthoringForm(TenantModelForm):
    """Header terms of a NEW supplier agreement, drafted from the clause library."""

    class Meta:
        model = SupplierContract
        # EXCLUDED and why: ``number`` is the spine's own auto-number; ``status`` moves
        # through scm's lifecycle verbs; ``owner``/``document``/``parent_contract`` are
        # stamped elsewhere; clause wording lives in the clause-link formset below.
        fields = ["title", "party", "contract_type", "currency", "payment_terms",
                  "start_date", "end_date", "contract_value",
                  "auto_renew", "renewal_notice_days", "terms_summary"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["party"].queryset = _supplier_parties(tenant)
            from apps.accounting.models import Currency, PaymentTerm
            if "currency" in self.fields:
                self.fields["currency"].queryset = Currency.objects.filter(
                    tenant=tenant).order_by("code")
            if "payment_terms" in self.fields:
                self.fields["payment_terms"].queryset = PaymentTerm.objects.filter(
                    tenant=tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["party", "currency", "payment_terms"])
        start_date, end_date = cleaned.get("start_date"), cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date",
                           "The end date cannot be before the start date.")
        return cleaned


class ClauseLinkForm(forms.ModelForm):
    """One library clause selected onto the agreement (with optional negotiated wording)."""

    class Meta:
        model = ContractClauseLink
        fields = ["clause", "section_order", "custom_text"]
        widgets = {"custom_text": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["clause"].queryset = _active_clauses(tenant)


def _active_clauses(tenant):
    """Active library clauses for one workspace (the clause picker's queryset)."""
    from apps.procurement.models import ContractClause

    return ContractClause.objects.filter(
        tenant=tenant, is_active=True).order_by("category", "title")


class BaseClauseLinkFormSet(forms.BaseInlineFormSet):
    """Keeps the drafted clause set coherent: no duplicate clauses on one agreement."""

    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            clause = form.cleaned_data.get("clause")
            if clause is None:
                continue
            if clause.pk in seen:
                raise forms.ValidationError(
                    f"Clause '{clause.title}' is selected more than once.")
            seen.add(clause.pk)


ClauseLinkFormSet = inlineformset_factory(
    SupplierContract, ContractClauseLink, form=ClauseLinkForm,
    formset=BaseClauseLinkFormSet, extra=3, can_delete=True, max_num=25, validate_max=True,
)


class ContractSignerForm(TenantModelForm):
    """One signature slot — internal stakeholder or supplier representative."""

    class Meta:
        model = ContractSigner
        fields = ["role", "signer_party", "signer_name", "signer_email"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["signer_party"].queryset = _supplier_parties(tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["signer_party"])
        role = cleaned.get("role")
        party = cleaned.get("signer_party")
        if role == "supplier" and party is None:
            self.add_error(
                "signer_party",
                "A supplier signature needs the supplier identity it binds.")
        if role == "internal" and party is not None:
            self.add_error("signer_party",
                           "Internal signatures do not carry a supplier identity.")
        return cleaned
