from django import forms


class StartConversationForm(forms.Form):
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
