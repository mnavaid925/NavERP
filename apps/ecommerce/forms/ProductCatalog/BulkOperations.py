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

    def clean_csv_file(self):
        uploaded_file = self.cleaned_data.get("csv_file")
        if uploaded_file:
            if not uploaded_file.name.lower().endswith(".csv"):
                raise forms.ValidationError("Only .csv files are supported.")
            if uploaded_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("CSV file size must not exceed 5MB.")
        return uploaded_file
