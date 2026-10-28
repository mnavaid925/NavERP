from django import forms


class ProductImportForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV File",
        widget=forms.FileInput(attrs={"class": "form-input", "accept": ".csv"}),
        help_text="Upload a comma-separated CSV file containing product and variant records.",
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label="Dry-Run (Validate only, do not save)",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )
    auto_create_categories = forms.BooleanField(
        required=False,
        initial=True,
        label="Auto-create missing categories",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )
