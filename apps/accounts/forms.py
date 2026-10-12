from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction

from .models import UserProfile

User = get_user_model()


class RegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        label="First name",
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        max_length=150,
        label="Last name",
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    phone_number = forms.CharField(
        max_length=32,
        label="Phone number",
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
    )
    location = forms.CharField(
        max_length=120,
        label="Town or city",
        widget=forms.TextInput(attrs={"autocomplete": "address-level2"}),
    )
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_username(self):
        username = User.normalize_username(self.cleaned_data["username"].strip())
        if User._default_manager.filter(username=username).exists():
            raise forms.ValidationError("That username is already in use.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        if password1:
            candidate = User(
                username=cleaned_data.get("username", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                password_validation.validate_password(password1, candidate)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
        )
        UserProfile.objects.create(
            user=user,
            phone_number=self.cleaned_data["phone_number"].strip(),
            location=self.cleaned_data["location"].strip(),
        )
        return user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")

    class Meta:
        model = UserProfile
        fields = ["phone_number", "location"]
        labels = {
            "phone_number": "Phone number",
            "location": "Town or city",
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name

    @transaction.atomic
    def save(self, commit=True):
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        if commit:
            self.user.save(update_fields=["first_name", "last_name"])
        return super().save(commit=commit)


class AccountAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
