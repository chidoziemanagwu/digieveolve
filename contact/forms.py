from django import forms
from .models import Contact

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['first_name', 'last_name', 'email', 'subject', 'message']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': 'Enter your first name',
                'required': True,
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Enter your last name',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'name@company.com',
                'required': True,
            }),
            'subject': forms.TextInput(attrs={
                'placeholder': 'What is this about?',
                'required': True,
            }),
            'message': forms.Textarea(attrs={
                'placeholder': 'Write your message here...',
                'rows': 6,
                'required': True,
            }),
        }