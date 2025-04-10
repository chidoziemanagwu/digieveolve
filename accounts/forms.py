# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User
from django.db import transaction
from django.core.exceptions import ValidationError

class CustomLoginForm(AuthenticationForm):
    # Add this field for Turnstile
    cf_turnstile_response = forms.CharField(required=False)  # Make it not required in the form

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add any custom initialization here

class StudentRegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=255,
        required=True,
        label='First Name',
        error_messages={
            'required': 'First Name is required.',
            'max_length': 'First Name cannot be more than 255 characters.'
        }
    )
    last_name = forms.CharField(
        max_length=255,
        required=True,
        label='Last Name',
        error_messages={
            'required': 'Last Name is required.',
            'max_length': 'Last Name cannot be more than 255 characters.'
        }
    )
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=True)
    terms = forms.BooleanField(
        required=True,
        label='I agree to the Terms and Conditions',
        error_messages={
            'required': 'You must accept the Terms and Conditions to register.'
        }
    )

    # Add this field for Turnstile
    cf_turnstile_response = forms.CharField(required=False)  # Make it not required in the form

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'password1', 'password2')
        error_messages = {
            'password2': {
                'password_mismatch': 'Confirm Password does not match the Main Password.',
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Main Password'
        self.fields['password2'].label = 'Confirm Password'
        self.fields['password1'].help_text = 'Password must be at least 6 characters long and contain at least one number.'

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if len(password) < 6:
            raise ValidationError('Password must be at least 6 characters long.')
        if not any(char.isdigit() for char in password):
            raise ValidationError('Password must contain at least one number.')
        return password

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Confirm Password does not match the Main Password.')
        return password2

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone.isdigit():
            raise ValidationError("Phone number should contain only digits.")
        return phone

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data['phone']
        user.is_student = True
        user.user_type = 'student'

        if commit:
            user.save()

        return user