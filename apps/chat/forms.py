from django import forms


class StartConversationForm(forms.Form):
    customer_name = forms.CharField(
        max_length=200,
        label="Your Name",
        widget=forms.TextInput(
            attrs={"placeholder": "Full name", "autocomplete": "name"}
        ),
    )
    customer_email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={"placeholder": "email@example.com", "autocomplete": "email"}
        ),
    )
    customer_phone = forms.CharField(
        max_length=30,
        required=False,
        label="Phone / WhatsApp (optional)",
        widget=forms.TextInput(
            attrs={"placeholder": "+233 …", "autocomplete": "tel"}
        ),
    )
    initial_message = forms.CharField(
        max_length=2000,
        label="Message",
        widget=forms.Textarea(
            attrs={"rows": 5, "placeholder": "Type your message here…"}
        ),
    )

    def clean_initial_message(self):
        content = self.cleaned_data.get("initial_message", "")
        if not content.strip():
            raise forms.ValidationError("Message cannot be blank.")
        return content.strip()

    def clean_customer_name(self):
        name = self.cleaned_data.get("customer_name", "")
        if not name.strip():
            raise forms.ValidationError("Name cannot be blank.")
        return name.strip()


class MessageForm(forms.Form):
    content = forms.CharField(
        max_length=2000,
        label="Message",
        strip=True,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Type your message…"}
        ),
    )

    def clean_content(self):
        content = self.cleaned_data.get("content", "")
        if not content.strip():
            raise forms.ValidationError("Message cannot be blank.")
        return content.strip()
