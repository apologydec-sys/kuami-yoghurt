import datetime

from django import forms

from .models import EVENT_TYPES


class BookingForm(forms.Form):
    customer_name = forms.CharField(
        max_length=200,
        label="Your Name",
        widget=forms.TextInput(attrs={"placeholder": "Full name", "autocomplete": "name"}),
    )
    customer_email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"placeholder": "email@example.com", "autocomplete": "email"}),
    )
    customer_phone = forms.CharField(
        max_length=30,
        label="Phone / WhatsApp",
        widget=forms.TextInput(attrs={"placeholder": "+233 …", "autocomplete": "tel"}),
    )
    event_type = forms.ChoiceField(
        choices=EVENT_TYPES,
        label="Event Type",
    )
    event_date = forms.DateField(
        label="Event Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    event_time = forms.TimeField(
        required=False,
        label="Event Time (optional)",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    event_location = forms.CharField(
        max_length=500,
        label="Event Location",
        widget=forms.TextInput(attrs={"placeholder": "Venue / City"}),
    )
    guest_count = forms.IntegerField(
        required=False,
        label="Expected Guests (optional)",
        min_value=1,
        max_value=100000,
        widget=forms.NumberInput(attrs={"placeholder": "e.g. 150"}),
    )
    music_preferences = forms.CharField(
        required=False,
        max_length=1000,
        label="Music Preferences",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Genres, artists, specific songs…"}),
    )
    additional_requirements = forms.CharField(
        required=False,
        max_length=2000,
        label="Additional Requirements",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Any other details…"}),
    )

    def clean_event_date(self):
        event_date = self.cleaned_data.get("event_date")
        if event_date and event_date < datetime.date.today():
            raise forms.ValidationError("Event date cannot be in the past.")
        return event_date

    def clean_customer_email(self):
        email = self.cleaned_data.get("customer_email", "").strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise forms.ValidationError("Enter a valid email address.")
        return email
