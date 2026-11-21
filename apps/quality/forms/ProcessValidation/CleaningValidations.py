from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation
from apps.quality.models.ProcessValidation.CleaningValidations import CleaningValidation
from apps.quality.models.ProcessValidation.ValidationProtocols import ValidationProtocol

User = get_user_model()


class CleaningValidationForm(TenantModelForm):
    class Meta:
        model = CleaningValidation
        fields = [
            "title",
            "equipment_train_tag",
            "target_residue",
            "cleaning_agent_used",
            "worst_case_rationale",
            "calculation_basis",
            "min_daily_dose_active_mg",
            "max_daily_dose_subsequent_mg",
            "smallest_batch_size_kg",
            "safety_factor",
            "toxicological_pde_mg_day",
            "total_surface_area_sqcm",
            "swab_sampling_area_sqcm",
            "rinse_volume_liters",
            "analytical_method",
            "method_recovery_percentage",
            "dirty_hold_time_hours",
            "clean_hold_time_hours",
            "consecutive_successful_runs",
            "is_visually_clean",
            "worst_swab_result_ug",
            "worst_rinse_result_ppm",
            "cleaning_status",
            "next_revalidation_date",
            "notes",
            "validation_protocol",
            "cleaning_sop",
            "analytical_lead",
            "qa_approver",
            "linked_deviation",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Solid Dose Granulation Train Cleaning Validation"}),
            "equipment_train_tag": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Granulator G-01 + Fluid Bed Dryer FBD-01"}),
            "target_residue": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Ibuprofen Active Ingredient / CIP-100 Detergent"}),
            "cleaning_agent_used": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2% CIP-100 Alkaline Wash followed by WFI"}),
            "worst_case_rationale": forms.Select(attrs={"class": "form-select"}),
            "calculation_basis": forms.Select(attrs={"class": "form-select"}),
            "min_daily_dose_active_mg": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "max_daily_dose_subsequent_mg": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "smallest_batch_size_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "safety_factor": forms.NumberInput(attrs={"class": "form-input", "step": "0.1"}),
            "toxicological_pde_mg_day": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "total_surface_area_sqcm": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "swab_sampling_area_sqcm": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "rinse_volume_liters": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "analytical_method": forms.Select(attrs={"class": "form-select"}),
            "method_recovery_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "dirty_hold_time_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.1"}),
            "clean_hold_time_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.1"}),
            "consecutive_successful_runs": forms.NumberInput(attrs={"class": "form-input"}),
            "is_visually_clean": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "worst_swab_result_ug": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "worst_rinse_result_ppm": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "cleaning_status": forms.Select(attrs={"class": "form-select"}),
            "next_revalidation_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Visual inspection notes, sampling locations, and recleaning rationale"}),
            "validation_protocol": forms.Select(attrs={"class": "form-select"}),
            "cleaning_sop": forms.Select(attrs={"class": "form-select"}),
            "analytical_lead": forms.Select(attrs={"class": "form-select"}),
            "qa_approver": forms.Select(attrs={"class": "form-select"}),
            "linked_deviation": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "username")
            self.fields["analytical_lead"].queryset = user_qs
            self.fields["qa_approver"].queryset = user_qs
            self.fields["validation_protocol"].queryset = ValidationProtocol.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["cleaning_sop"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["linked_deviation"].queryset = ProcessDeviation.objects.filter(tenant=self.tenant).order_by("title")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "validation_protocol",
                "cleaning_sop",
                "analytical_lead",
                "qa_approver",
                "linked_deviation",
            ],
        )

        basis = cleaned.get("calculation_basis")
        if basis == "therapeutic_dose":
            if not cleaned.get("min_daily_dose_active_mg"):
                self.add_error("min_daily_dose_active_mg", "Minimum daily dose of active is required for therapeutic dose calculation basis.")
            if not cleaned.get("max_daily_dose_subsequent_mg"):
                self.add_error("max_daily_dose_subsequent_mg", "Maximum daily dose of subsequent product is required for therapeutic dose calculation basis.")
            if not cleaned.get("safety_factor"):
                self.add_error("safety_factor", "Safety factor is required for therapeutic dose calculation basis.")
        elif basis == "toxicological_pde":
            if not cleaned.get("toxicological_pde_mg_day"):
                self.add_error("toxicological_pde_mg_day", "Toxicological PDE / ADE is required for toxicological PDE calculation basis.")
            if not cleaned.get("max_daily_dose_subsequent_mg"):
                self.add_error("max_daily_dose_subsequent_mg", "Maximum daily dose of subsequent product is required for toxicological PDE calculation basis.")

        return cleaned
