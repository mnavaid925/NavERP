from django import forms

from apps.crm.models import Lead
from apps.sales.forms._common import TenantActionForm, tenant_leads
from apps.sales.models import LeadScoreEvent


class LeadScoreAdjustmentForm(TenantActionForm):
    lead = forms.ModelChoiceField(queryset=Lead.objects.none())
    score_delta = forms.IntegerField(min_value=-100, max_value=100)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["lead"].queryset = tenant_leads(tenant)


class LeadScoreCorrectionForm(TenantActionForm):
    lead = forms.ModelChoiceField(queryset=Lead.objects.none())
    corrects_event = forms.ModelChoiceField(queryset=LeadScoreEvent.objects.none())
    score_delta = forms.IntegerField(min_value=-100, max_value=100)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["lead"].queryset = tenant_leads(tenant)
        self.fields["corrects_event"].queryset = LeadScoreEvent.objects.filter(
            tenant=tenant,
            corrects_event__isnull=True,
        ).filter(corrections__isnull=True)

    def clean(self):
        cleaned = super().clean()
        lead = cleaned.get("lead")
        event = cleaned.get("corrects_event")
        score_delta = cleaned.get("score_delta")
        if lead and event:
            if event.lead_id != lead.pk:
                self.add_error("corrects_event", "Choose an event for the selected lead.")
            if score_delta is not None and score_delta != -event.score_delta:
                self.add_error("score_delta", "A correction must use the inverse score delta.")
            if LeadScoreEvent.objects.filter(tenant=self.tenant, corrects_event=event).exists():
                self.add_error("corrects_event", "That score event has already been corrected.")
        return cleaned
