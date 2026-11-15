from django import forms

from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord


class ElectronicSignatureForm(forms.Form):
    signature_meaning = forms.ChoiceField(
        choices=ElectronicSignatureRecord.MEANING_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Meaning of Signature (Intent)",
    )
    signer_title = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Lead QA Specialist"}),
        label="Professional Title",
    )
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Specific review comments or notes..."}),
        label="Signature Remarks",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Re-enter your account password"}),
        label="Password Re-Authentication (21 CFR Part 11)",
        help_text="To execute a binding electronic signature, you must re-authenticate your credentials.",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.user or not self.user.check_password(password):
            raise forms.ValidationError("Invalid credentials. Electronic signature rejected per FDA 21 CFR § 11.200.")
        return password
