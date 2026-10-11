from django import forms

from .models import VideoCategory


class VideoSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Search videos…"}),
    )
    category = forms.ModelChoiceField(
        queryset=VideoCategory.objects.all(),
        required=False,
        empty_label="All Categories",
    )
