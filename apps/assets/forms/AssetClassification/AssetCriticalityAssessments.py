from django import forms

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetClassification.AssetCriticalityAssessments import AssetCriticalityAssessment
from apps.core.models import Party
from apps.scm.models import Asset


class AssetCriticalityAssessmentForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetCriticalityAssessment
        fields = [
            "title",
            "asset",
            "assessor",
            "assessment_date",
            "safety_impact",
            "environmental_impact",
            "operational_downtime_impact",
            "financial_impact",
            "regulatory_compliance_impact",
            "is_single_point_of_failure",
            "recommended_strategy",
            "review_cycle_months",
            "next_assessment_due",
            "findings_and_mitigation",
        ]
        exclude = [
            "tenant",
            "number",
            "composite_score",
            "abc_rating",
            "assessment_status",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Annual Criticality Review - Chiller #2"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "assessor": forms.Select(attrs={"class": "form-select"}),
            "assessment_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "safety_impact": forms.Select(
                choices=[(i, f"{i} — {lbl}") for i, lbl in [
                    (1, "Negligible (First aid / No injury)"),
                    (2, "Minor (Medical treatment case)"),
                    (3, "Moderate (Lost time injury)"),
                    (4, "Severe (Irreversible harm / Hospitalization)"),
                    (5, "Catastrophic (Fatality / Major hazard)"),
                ]],
                attrs={"class": "form-select"}
            ),
            "environmental_impact": forms.Select(
                choices=[(i, f"{i} — {lbl}") for i, lbl in [
                    (1, "Zero Release (Contained within drip pan)"),
                    (2, "Minor Release (Remediated immediately on site)"),
                    (3, "Moderate Spill (Exceeds internal threshold)"),
                    (4, "Major Spill (Offsite impact / Regulated report)"),
                    (5, "Catastrophic (Severe ecological / Toxic release)"),
                ]],
                attrs={"class": "form-select"}
            ),
            "operational_downtime_impact": forms.Select(
                choices=[(i, f"{i} — {lbl}") for i, lbl in [
                    (1, "No Impact (Redundant online unit runs)"),
                    (2, "Minor Delay (<2h buffer absorbed)"),
                    (3, "Moderate Line Slowdown (Partial plant throttling)"),
                    (4, "Severe Stoppage (>8h production bottleneck)"),
                    (5, "Total Plant Shutdown (Multi-day outage)"),
                ]],
                attrs={"class": "form-select"}
            ),
            "financial_impact": forms.Select(
                choices=[(i, f"{i} — {lbl}") for i, lbl in [
                    (1, "<$1,000 (Routine component replacement)"),
                    (2, "$1,000 - $10,000 (Minor assembly overhaul)"),
                    (3, "$10,000 - $50,000 (Major rebuild)"),
                    (4, "$50,000 - $250,000 (Critical sub-system renewal)"),
                    (5, ">$250,000 (Catastrophic total loss)"),
                ]],
                attrs={"class": "form-select"}
            ),
            "regulatory_compliance_impact": forms.Select(
                choices=[(i, f"{i} — {lbl}") for i, lbl in [
                    (1, "Minor Internal Warning"),
                    (2, "Notice of Non-Conformance"),
                    (3, "Statutory Audit Finding / Fine"),
                    (4, "Regulatory Stop-Work Order"),
                    (5, "Revocation of License to Operate"),
                ]],
                attrs={"class": "form-select"}
            ),
            "is_single_point_of_failure": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "recommended_strategy": forms.Select(attrs={"class": "form-select"}),
            "review_cycle_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "next_assessment_due": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "findings_and_mitigation": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Failure mode observations, single point of failure justification, mitigation plan..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["asset"].queryset = Asset.objects.filter(
                tenant=self.tenant, is_active=True
            ).select_related("location").order_by("number")
            self.fields["assessor"].queryset = Party.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(self, cleaned_data, ["asset", "assessor"])

        for fld in [
            "safety_impact",
            "environmental_impact",
            "operational_downtime_impact",
            "financial_impact",
            "regulatory_compliance_impact",
        ]:
            val = cleaned_data.get(fld)
            if val is not None and (int(val) < 1 or int(val) > 5):
                self.add_error(fld, "Consequence score must be between 1 and 5.")

        return cleaned_data
