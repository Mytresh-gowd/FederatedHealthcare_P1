from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class PatientRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, label='Full name')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'password1', 'password2')
        labels = {
            'username': 'Username',
            'first_name': 'Full name',
        }

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already in use. Please choose another.')
        return username
