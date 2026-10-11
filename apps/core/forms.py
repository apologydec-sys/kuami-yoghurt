from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Your name", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "Your email", "autocomplete": "email"}),
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Phone / WhatsApp (optional)", "autocomplete": "tel"}),
    )
    subject = forms.CharField(
        max_length=300,
        widget=forms.TextInput(attrs={"placeholder": "Subject"}),
    )
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"placeholder": "Your message", "rows": 6}),
    )

    def clean_message(self):
        message = self.cleaned_data.get("message", "")
        if len(message.strip()) < 10:
            raise forms.ValidationError("Message must be at least 10 characters.")
        return message
